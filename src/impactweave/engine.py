from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from .diff import compare_contracts
from .loader import ProjectManifest
from .models import ChangeKind, ContractChange, Evidence, ImpactFinding, ImpactReport, Severity, Verdict


def _evidence_index(items: list[Evidence]) -> dict[tuple[str, str, str], Evidence]:
    index: dict[tuple[str, str, str], Evidence] = {}
    for item in items:
        key = (item.producer, item.consumer, item.contract)
        current = index.get(key)
        if current is None or item.confidence > current.confidence or item.observed_at > current.observed_at:
            index[key] = item
    return index


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
    findings: list[ImpactFinding] = []
    unknown: list[str] = []
    changed_contracts = {item.contract for item in changes if item.severity == Severity.BREAKING}

    for contract in sorted(changed_contracts):
        edges = edges_by_contract.get(contract, [])
        if not edges:
            unknown.append(f"{contract}: no consumer edges")
        for producer, consumer, _declared in sorted(edges):
            observed = evidence.get((producer, consumer, contract))
            for change in [
                item for item in changes if item.contract == contract and item.severity == Severity.BREAKING
            ]:
                findings.append(
                    ImpactFinding(
                        consumer=consumer,
                        producer=producer,
                        contract=contract,
                        path=change.path,
                        severity=change.severity,
                        reason=change.reason,
                        confidence=observed.confidence if observed else None,
                        evidence_source=observed.source if observed else None,
                    )
                )
    if manifest.strict:
        for contract in sorted(changed_contracts):
            for producer, consumer, _declared in edges_by_contract.get(contract, []):
                if (producer, consumer, contract) not in evidence:
                    unknown.append(f"{producer}->{consumer}:{contract}: missing observed evidence")

    breaking = sum(1 for item in changes if item.severity == Severity.BREAKING)
    warning = sum(1 for item in changes if item.severity == Severity.WARNING)
    info = sum(1 for item in changes if item.severity == Severity.INFO)
    if breaking and (unknown if manifest.strict else []):
        verdict = Verdict.REVIEW
    elif breaking:
        verdict = Verdict.FAIL
    elif warning:
        verdict = Verdict.WARN
    else:
        verdict = Verdict.PASS
    return ImpactReport(
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
        },
    )
