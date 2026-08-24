from __future__ import annotations

import hashlib
import json
from collections import defaultdict, deque
from datetime import datetime, timezone

from .diff import compare_contracts
from .loader import ProjectManifest
from .models import (
    ChangeKind,
    ContractChange,
    CoverageState,
    Evidence,
    ImpactFinding,
    ImpactReport,
    Severity,
    Verdict,
)


def _evidence_index(items: list[Evidence]) -> dict[tuple[str, str, str], Evidence]:
    index: dict[tuple[str, str, str], Evidence] = {}
    for item in items:
        key = (item.producer, item.consumer, item.contract)
        current = index.get(key)
        if current is None or (item.confidence, item.observed_at.isoformat()) > (
            current.confidence,
            current.observed_at.isoformat(),
        ):
            index[key] = item
    return index


def _path(adjacency: dict[str, list[str]], starts: list[str], target: str, max_hops: int) -> list[str]:
    queue: deque[tuple[str, list[str]]] = deque((item, [item]) for item in sorted(set(starts)))
    seen = set(starts)
    while queue:
        current, trail = queue.popleft()
        if current == target:
            return trail
        if len(trail) - 1 >= max_hops:
            continue
        for neighbor in sorted(adjacency.get(current, [])):
            if neighbor not in seen:
                seen.add(neighbor)
                queue.append((neighbor, trail + [neighbor]))
    return []


def _graph(manifest: ProjectManifest) -> dict[str, list[str]]:
    adjacency: dict[str, list[str]] = defaultdict(list)
    for graph_edge in manifest.graph_edges:
        adjacency[graph_edge.source].append(graph_edge.target)
    for legacy_edge in manifest.edges:
        contract = f"contract:{legacy_edge.contract}"
        adjacency[legacy_edge.producer].append(contract)
        adjacency[contract].append(legacy_edge.consumer)
    for values in adjacency.values():
        values.sort()
    return adjacency


def _coverage(observed: Evidence | None, stale_after_days: int) -> CoverageState:
    if observed is None:
        return CoverageState.UNKNOWN
    age_days = (datetime.now(timezone.utc) - observed.observed_at).days
    return CoverageState.STALE if age_days > stale_after_days else CoverageState.OBSERVED


def _digest(report: ImpactReport) -> str:
    payload = report.model_dump(mode="json")
    payload["generated_at"] = "redacted-for-determinism"
    payload["artifact_digest"] = ""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()


def build_report(manifest: ProjectManifest) -> ImpactReport:
    current = manifest.contract_map
    proposed = manifest.proposed_map
    changes: list[ContractChange] = []
    for name in sorted(set(current) | set(proposed)):
        if name not in current:
            changes.append(
                ContractChange(
                    contract=name,
                    path="/",
                    kind=ChangeKind.ADDED,
                    severity=Severity.BREAKING,
                    reason="new contract has no baseline",
                )
            )
        elif name not in proposed:
            continue
        else:
            changes.extend(compare_contracts(current[name], proposed[name]))

    edges_by_contract: dict[str, list[tuple[str, str, bool]]] = defaultdict(list)
    for edge in manifest.edges:
        edges_by_contract[edge.contract].append((edge.producer, edge.consumer, edge.declared))
    evidence = _evidence_index(manifest.evidence)
    adjacency = _graph(manifest)
    findings: list[ImpactFinding] = []
    unknown: list[str] = []
    changed_contracts = {item.contract for item in changes if item.severity == Severity.BREAKING}

    for contract in sorted(changed_contracts):
        edges = edges_by_contract.get(contract, [])
        if not edges:
            unknown.append(f"{contract}: no consumer edges")
        for producer, consumer, _declared in sorted(edges):
            observed = evidence.get((producer, consumer, contract))
            coverage = _coverage(observed, manifest.stale_after_days)
            graph_path = _path(adjacency, [producer], consumer, manifest.max_hops)
            if not graph_path:
                graph_path = [producer, f"contract:{contract}", consumer]
            for change in (
                item for item in changes if item.contract == contract and item.severity == Severity.BREAKING
            ):
                confidence = observed.confidence if observed and coverage != CoverageState.STALE else None
                score = min(
                    100, 60 + (0 if change.kind == ChangeKind.CHANGED else 15) + (0 if confidence is not None else 20)
                )
                findings.append(
                    ImpactFinding(
                        consumer=consumer,
                        producer=producer,
                        contract=contract,
                        path=change.path,
                        severity=change.severity,
                        reason=change.reason,
                        confidence=confidence,
                        evidence_source=observed.source if observed and coverage != CoverageState.STALE else None,
                        coverage=coverage,
                        impact_score=score,
                        graph_path=graph_path,
                    )
                )
            if manifest.strict and coverage in {CoverageState.UNKNOWN, CoverageState.STALE}:
                unknown.append(f"{producer}->{consumer}:{contract}: {coverage.value} evidence")

    breaking = sum(1 for item in changes if item.severity == Severity.BREAKING)
    warning = sum(1 for item in changes if item.severity == Severity.WARNING)
    info = sum(1 for item in changes if item.severity == Severity.INFO)
    if breaking and unknown and manifest.strict:
        verdict = Verdict.REVIEW
    elif breaking:
        verdict = Verdict.FAIL
    elif warning:
        verdict = Verdict.WARN
    else:
        verdict = Verdict.PASS
    report = ImpactReport(
        generated_at=datetime.now(timezone.utc),
        verdict=verdict,
        changes=sorted(changes, key=lambda x: (x.contract, x.path, x.reason)),
        findings=sorted(findings, key=lambda x: (x.contract, x.consumer, x.path)),
        unknown_edges=sorted(set(unknown)),
        summary={
            "changes": len(changes),
            "breaking": breaking,
            "warning": warning,
            "info": info,
            "findings": len(findings),
            "unknown": len(set(unknown)),
            "observed": sum(item.coverage == CoverageState.OBSERVED for item in findings),
            "stale": sum(item.coverage == CoverageState.STALE for item in findings),
        },
    )
    report.artifact_digest = _digest(report)
    return report
