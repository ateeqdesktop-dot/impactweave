from __future__ import annotations

import fnmatch
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from .loader import ProjectManifest
from .models import TestDecision, TestPlanReport, TestPlanVerdict, TestTarget

MAX_DIFF_BYTES = 2_000_000


def _normalise_path(value: str) -> str:
    path = value.replace("\\", "/").strip()
    if not path or path.startswith("/") or "\x00" in path:
        raise ValueError("changed paths must be non-empty relative paths")
    pure_path = PurePosixPath(path)
    if ".." in pure_path.parts:
        raise ValueError("changed paths must stay inside the repository")
    normalised = str(pure_path)
    if normalised == "." or normalised == ".." or normalised.startswith("../"):
        raise ValueError("changed paths must stay inside the repository")
    return normalised


def _matches(path: str, pattern: str) -> bool:
    candidate = path.lstrip("./")
    rule = pattern.replace("\\", "/").lstrip("./")
    if not rule:
        return False
    return (
        fnmatch.fnmatchcase(candidate, rule)
        or PurePosixPath(candidate).match(rule)
        or (rule.startswith("**/") and fnmatch.fnmatchcase(candidate, rule[3:]))
    )


def _digest(report: TestPlanReport) -> str:
    payload = report.model_dump(mode="json")
    payload["artifact_digest"] = ""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _latest_observations(manifest: ProjectManifest) -> dict[str, list[tuple[str, str]]]:
    now = datetime.now(timezone.utc)
    result: dict[str, list[tuple[str, str]]] = {}
    for item in manifest.test_observations:
        age = (now - item.observed_at).days
        if age <= manifest.test_policy.stale_after_days:
            result.setdefault(item.test_id, []).extend((path, item.source) for path in item.paths)
    return result


def _matched_test(
    target: TestTarget, changed: list[str], observations: list[tuple[str, str]]
) -> tuple[list[str], list[str]]:
    matches: list[str] = []
    sources: list[str] = []
    for path in changed:
        if any(_matches(path, pattern) for pattern in target.paths):
            matches.append(path)
            sources.append("declared-path-map")
        elif any(_matches(path, pattern) for pattern, _source in observations):
            matches.append(path)
            sources.extend(source for pattern, source in observations if _matches(path, pattern))
    return sorted(set(matches)), sorted(set(sources))


def _target_decision(target: TestTarget, changed: list[str], observations: list[tuple[str, str]]) -> TestDecision:
    if target.always:
        return TestDecision(
            test_id=target.id,
            selected=True,
            reason="always-run target",
            command=target.command,
            tags=target.tags,
            estimated_seconds=target.estimated_seconds,
        )
    matched, sources = _matched_test(target, changed, observations)
    if matched:
        return TestDecision(
            test_id=target.id,
            selected=True,
            reason="changed paths match the test ownership contract",
            matched_paths=matched,
            command=target.command,
            tags=target.tags,
            estimated_seconds=target.estimated_seconds,
            evidence_sources=sources,
        )
    return TestDecision(
        test_id=target.id,
        selected=False,
        reason="no changed path matches the test ownership contract",
        command=target.command,
        tags=target.tags,
        estimated_seconds=target.estimated_seconds,
        evidence_sources=sources,
    )


def build_test_plan(manifest: ProjectManifest, changed_paths: list[str]) -> TestPlanReport:
    """Create a conservative, explainable test plan without executing target commands."""
    changed = sorted({_normalise_path(path) for path in changed_paths})
    effective = [
        path for path in changed if not any(_matches(path, pattern) for pattern in manifest.test_policy.ignored_paths)
    ]
    observations = _latest_observations(manifest)
    decisions = [_target_decision(target, effective, observations.get(target.id, [])) for target in manifest.tests]
    matched_paths = {path for decision in decisions for path in decision.matched_paths}
    unknown = sorted(set(effective) - matched_paths)
    fallback_reasons: list[str] = []
    review_required = False
    selected = sorted({decision.test_id for decision in decisions if decision.selected})

    if not manifest.tests:
        fallback_reasons.append("manifest declares no test targets")
    tracked = sorted(
        path for path in effective if any(_matches(path, pattern) for pattern in manifest.test_policy.tracked_paths)
    )
    if tracked:
        fallback_reasons.append("tracked paths changed: " + ", ".join(tracked))
    if unknown and manifest.test_policy.fallback_on_unknown:
        fallback_reasons.append("unmapped paths require full-suite safety: " + ", ".join(unknown))
    elif unknown:
        review_required = True
        fallback_reasons.append("unmapped paths require explicit review: " + ", ".join(unknown))
    if len(selected) > manifest.test_policy.max_selected:
        fallback_reasons.append("selected test count exceeds policy limit")
    if fallback_reasons and not review_required:
        verdict = TestPlanVerdict.FULL_SUITE
        selected = sorted(target.id for target in manifest.tests)
        fallback_reason = "full-suite fallback: " + "; ".join(fallback_reasons)
        decisions = [
            decision.model_copy(update={"selected": True, "reason": fallback_reason}) for decision in decisions
        ]
    elif review_required or not selected:
        verdict = TestPlanVerdict.REVIEW
        if not selected:
            fallback_reasons.append("no test target can be justified by the changed paths")
    else:
        verdict = TestPlanVerdict.SAFE_SUBSET

    report = TestPlanReport(
        verdict=verdict,
        changed_paths=changed,
        decisions=sorted(decisions, key=lambda item: item.test_id),
        selected_tests=selected,
        skipped_tests=sorted(target.id for target in manifest.tests if target.id not in selected),
        unknown_paths=unknown,
        fallback_reasons=fallback_reasons,
        summary={
            "changed_paths": len(changed),
            "effective_paths": len(effective),
            "selected_tests": len(selected),
            "skipped_tests": len(manifest.tests) - len(selected),
            "unknown_paths": len(unknown),
            "full_suite": verdict == TestPlanVerdict.FULL_SUITE,
            "safe_subset": verdict == TestPlanVerdict.SAFE_SUBSET,
        },
    )
    report.artifact_digest = _digest(report)
    return report


def git_changed_paths(repo: str | Path, base: str, head: str) -> list[str]:
    """Read names from Git only; never checks out code or executes project commands."""
    if not base or not head or base.startswith("-") or head.startswith("-"):
        raise ValueError("git refs must be non-empty and must not start with '-'")
    completed = subprocess.run(
        ["git", "-C", str(Path(repo).resolve()), "diff", "--name-only", f"{base}...{head}"],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    raw = completed.stdout.encode("utf-8")
    if len(raw) > MAX_DIFF_BYTES:
        raise ValueError(f"git diff output exceeds {MAX_DIFF_BYTES} bytes")
    return [_normalise_path(line) for line in completed.stdout.splitlines() if line.strip()]
