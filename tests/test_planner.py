from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from typer.testing import CliRunner

from impactweave.cli import app
from impactweave.engine import build_report
from impactweave.loader import ProjectManifest, load_manifest
from impactweave.models import ContractField, ContractKind, ContractSnapshot, Edge
from impactweave.models import TestObservation as Observation
from impactweave.models import TestPlanVerdict as PlanVerdict
from impactweave.planner import build_test_plan, git_changed_paths
from impactweave.report import (
    to_json,
    to_markdown,
    to_sarif,
    to_test_plan_json,
    to_test_plan_markdown,
    to_test_plan_sarif,
)

FIXTURE = Path(__file__).parents[1] / "fixtures" / "test-plan.yaml"
RUNNER = CliRunner()


@pytest.fixture()
def manifest():
    return load_manifest(FIXTURE)


def test_changed_checkout_selects_direct_and_critical_tests(manifest) -> None:
    report = build_test_plan(manifest, ["src/checkout/cart.py"])

    assert report.verdict is PlanVerdict.SAFE_SUBSET
    assert report.selected_tests == ["e2e.critical", "lint", "unit.checkout"]
    assert report.skipped_tests == ["contract.api", "unit.billing"]
    assert report.unknown_paths == []
    checkout = next(item for item in report.decisions if item.test_id == "unit.checkout")
    assert checkout.matched_paths == ["src/checkout/cart.py"]
    assert report.artifact_digest == build_test_plan(manifest, ["src/checkout/cart.py"]).artifact_digest


def test_ignored_docs_change_keeps_only_always_run(manifest) -> None:
    report = build_test_plan(manifest, ["docs/architecture.md"])

    assert report.verdict is PlanVerdict.SAFE_SUBSET
    assert report.selected_tests == ["lint"]
    assert report.skipped_tests == ["contract.api", "e2e.critical", "unit.billing", "unit.checkout"]


def test_unknown_path_falls_back_to_full_suite(manifest) -> None:
    report = build_test_plan(manifest, ["generated/runtime.bin"])

    assert report.verdict is PlanVerdict.FULL_SUITE
    assert report.selected_tests == ["contract.api", "e2e.critical", "lint", "unit.billing", "unit.checkout"]
    assert report.unknown_paths == ["generated/runtime.bin"]
    assert any("full-suite safety" in reason for reason in report.fallback_reasons)


def test_tracked_configuration_change_falls_back_to_full_suite(manifest) -> None:
    report = build_test_plan(manifest, ["pyproject.toml"])

    assert report.verdict is PlanVerdict.FULL_SUITE
    assert any("tracked paths changed" in reason for reason in report.fallback_reasons)


def test_max_selected_policy_is_safe(manifest) -> None:
    report = build_test_plan(manifest, ["src/checkout/cart.py", "src/billing/invoice.py"])

    assert report.verdict is PlanVerdict.FULL_SUITE
    assert "selected test count exceeds policy limit" in report.fallback_reasons


def test_stale_observation_is_ignored(manifest) -> None:
    manifest.test_observations = [
        Observation(
            test_id="unit.checkout",
            paths=["src/checkout/**"],
            source="old-coverage",
            observed_at=datetime.now(timezone.utc) - timedelta(days=90),
        )
    ]
    report = build_test_plan(manifest, ["mystery/unknown.py"])

    assert report.verdict is PlanVerdict.FULL_SUITE
    assert "old-coverage" not in report.decisions[0].evidence_sources


def test_disabled_fallback_requires_review(manifest) -> None:
    manifest.test_policy.fallback_on_unknown = False
    report = build_test_plan(manifest, ["mystery/unknown.py"])

    assert report.verdict is PlanVerdict.REVIEW
    assert report.selected_tests == ["lint"]
    assert any("explicit review" in reason for reason in report.fallback_reasons)


def test_no_targets_falls_back_to_full_suite() -> None:
    manifest = ProjectManifest(
        contracts=[ContractSnapshot(name="x", version="1", kind=ContractKind.EVENT_JSON)],
        tests=[],
    )
    report = build_test_plan(manifest, ["src/main.py"])

    assert report.verdict is PlanVerdict.FULL_SUITE
    assert report.selected_tests == []
    assert report.fallback_reasons[0] == "manifest declares no test targets"


def test_invalid_paths_are_rejected(manifest) -> None:
    with pytest.raises(ValueError, match="relative paths"):
        build_test_plan(manifest, ["/tmp/outside"])
    with pytest.raises(ValueError, match="inside the repository"):
        build_test_plan(manifest, ["../outside"])


def test_planner_never_executes_declared_command(manifest, tmp_path: Path) -> None:
    marker = tmp_path / "should-not-exist"
    manifest.tests[0].command = ["touch", str(marker)]

    build_test_plan(manifest, ["src/checkout/cart.py"])

    assert not marker.exists()


def test_report_formats_are_machine_and_human_readable(manifest) -> None:
    report = build_test_plan(manifest, ["generated/runtime.bin"])
    json_output = to_test_plan_json(report)
    markdown_output = to_test_plan_markdown(report)
    sarif_output = to_test_plan_sarif(report)

    assert '"verdict": "full_suite"' in json_output
    assert "## Decisions" in markdown_output
    assert "impactweave/unmapped-path" in sarif_output
    assert report.artifact_digest in markdown_output


def test_legacy_report_formats_still_work() -> None:
    before = ContractSnapshot(
        name="orders",
        version="1",
        kind=ContractKind.EVENT_JSON,
        fields=[ContractField(path="/id", type="string", required=True)],
    )
    after = ContractSnapshot(
        name="orders",
        version="2",
        kind=ContractKind.EVENT_JSON,
        fields=[ContractField(path="/id", type="integer", required=True)],
    )
    report = build_report(
        ProjectManifest(
            contracts=[before],
            proposed=[after],
            edges=[Edge(producer="checkout", consumer="billing", contract="orders")],
        )
    )
    assert "ImpactWeave Nexus report" in to_markdown(report)
    assert '"schema_version": "2"' in to_json(report)
    assert "impactweave/orders" in to_sarif(report)


def test_cli_emits_test_plan_json() -> None:
    result = RUNNER.invoke(app, ["test-plan", str(FIXTURE), "--changed", "src/checkout/cart.py", "--format", "json"])

    assert result.exit_code == 0
    assert '"verdict": "safe_subset"' in result.stdout


def test_cli_requires_a_source_of_changed_paths() -> None:
    result = RUNNER.invoke(app, ["test-plan", str(FIXTURE)])

    assert result.exit_code != 0
    assert "Usage:" in result.output


def test_invalid_observation_reference_is_rejected(tmp_path: Path) -> None:
    content = FIXTURE.read_text(encoding="utf-8").replace("test_id: unit.checkout", "test_id: missing", 1)
    path = tmp_path / "invalid.yaml"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(ValueError, match="unknown tests"):
        load_manifest(path)


def test_git_diff_reader_is_passive(tmp_path: Path) -> None:
    import subprocess

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "a.txt").write_text("before\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "a.txt"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-qm",
            "base",
        ],
        check=True,
    )
    (tmp_path / "a.txt").write_text("after\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "a.txt"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-qm",
            "head",
        ],
        check=True,
    )

    assert git_changed_paths(tmp_path, "HEAD~1", "HEAD") == ["a.txt"]
    with pytest.raises(ValueError, match="must not start"):
        git_changed_paths(tmp_path, "-bad", "HEAD")
