from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from impactweave.engine import build_report
from impactweave.loader import ProjectManifest
from impactweave.models import (
    ContractField,
    ContractKind,
    ContractSnapshot,
    Edge,
    Evidence,
    GraphEdge,
    GraphNode,
    NodeKind,
)
from impactweave.report import to_json, to_sarif


def test_graph_path_and_observed_coverage() -> None:
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
    manifest = ProjectManifest(
        contracts=[before],
        proposed=[after],
        edges=[Edge(producer="checkout", consumer="billing", contract="orders")],
        evidence=[
            Evidence(
                producer="checkout",
                consumer="billing",
                contract="orders",
                confidence=0.94,
                source="trace",
                observed_at=datetime.now(timezone.utc),
            )
        ],
        nodes=[
            GraphNode(id="checkout", kind=NodeKind.COMPONENT),
            GraphNode(id="contract:orders", kind=NodeKind.CONTRACT),
            GraphNode(id="billing", kind=NodeKind.COMPONENT),
        ],
        graph_edges=[
            GraphEdge(source="checkout", target="contract:orders", kind="produces"),
            GraphEdge(source="contract:orders", target="billing", kind="consumes"),
        ],
    )
    report = build_report(manifest)
    assert report.findings[0].coverage.value == "observed"
    assert report.findings[0].graph_path == ["checkout", "contract:orders", "billing"]
    assert report.artifact_digest == build_report(manifest).artifact_digest
    assert report.findings[0].impact_score >= 60


def test_stale_evidence_requires_review_and_is_not_confidence() -> None:
    before = ContractSnapshot(name="orders", version="1", kind=ContractKind.EVENT_JSON)
    after = ContractSnapshot(
        name="orders",
        version="2",
        kind=ContractKind.EVENT_JSON,
        fields=[ContractField(path="/id", type="string", required=True)],
    )
    manifest = ProjectManifest(
        contracts=[before],
        proposed=[after],
        edges=[Edge(producer="a", consumer="b", contract="orders")],
        evidence=[
            Evidence(
                producer="a",
                consumer="b",
                contract="orders",
                confidence=1.0,
                source="old",
                observed_at=datetime.now(timezone.utc) - timedelta(days=90),
            )
        ],
        stale_after_days=30,
    )
    report = build_report(manifest)
    assert report.verdict.value == "review"
    assert report.findings[0].coverage.value == "stale"
    assert report.findings[0].confidence is None


def test_sarif_contains_tool_and_result() -> None:
    before = ContractSnapshot(name="orders", version="1", kind=ContractKind.EVENT_JSON)
    after = ContractSnapshot(
        name="orders",
        version="2",
        kind=ContractKind.EVENT_JSON,
        fields=[ContractField(path="/id", type="string", required=True)],
    )
    report = build_report(ProjectManifest(contracts=[before], proposed=[after]))
    sarif = to_sarif(report)
    assert '"name": "ImpactWeave Nexus"' in sarif
    assert '"version": "2.1.0"' in sarif
    assert to_json(report).count(report.artifact_digest) == 1


def test_graph_edges_cannot_reference_unknown_nodes() -> None:
    with pytest.raises(ValueError, match="unknown nodes"):
        ProjectManifest(
            contracts=[ContractSnapshot(name="x", version="1", kind=ContractKind.HTTP_JSON)],
            nodes=[GraphNode(id="a", kind=NodeKind.COMPONENT)],
            graph_edges=[GraphEdge(source="a", target="missing", kind="calls")],
        )
