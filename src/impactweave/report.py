from __future__ import annotations

import json

from .models import ImpactReport


def to_json(report: ImpactReport) -> str:
    payload = report.model_dump(mode="json")
    payload["generated_at"] = "redacted-for-determinism"
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def to_markdown(report: ImpactReport) -> str:
    lines = [
        f"# ImpactWeave Nexus report: `{report.verdict.value}`",
        "",
        f"> Artifact digest: `{report.artifact_digest}`",
        "",
        "| Metric | Count |",
        "|---|---:|",
    ]
    lines.extend(f"| {_cell(key)} | {value} |" for key, value in sorted(report.summary.items()))
    lines.extend(["", "## Contract changes", "", "| Contract | Path | Severity | Reason |", "|---|---|---|---|"])
    for change in report.changes:
        lines.append(
            f"| `{_cell(change.contract)}` | `{_cell(change.path)}` | **{change.severity.value}** | "
            f"{_cell(change.reason)} |"
        )
    lines.extend(
        [
            "",
            "## Consumer impact — explainable paths",
            "",
            "| Producer | Consumer | Contract | Path | Coverage | Confidence | Score | Graph path |",
            "|---|---|---|---|---|---:|---:|---|",
        ]
    )
    for finding in report.findings:
        confidence = "unknown" if finding.confidence is None else f"{finding.confidence:.2f}"
        trail = " → ".join(finding.graph_path) or "unresolved"
        lines.append(
            f"| `{_cell(finding.producer)}` | `{_cell(finding.consumer)}` | `{_cell(finding.contract)}` | "
            f"`{_cell(finding.path)}` | `{finding.coverage.value}` | {confidence} | "
            f"{finding.impact_score} | `{_cell(trail)}` |"
        )
    if report.unknown_edges:
        lines.extend(["", "## Review required", ""])
        lines.extend(f"- {_cell(item)}" for item in report.unknown_edges)
    return "\n".join(lines) + "\n"


def to_sarif(report: ImpactReport) -> str:
    results = []
    for finding in report.findings:
        level = "error" if finding.severity.value == "breaking" else "warning"
        results.append(
            {
                "ruleId": f"impactweave/{finding.contract}/{finding.path}",
                "level": level,
                "message": {
                    "text": f"{finding.reason} [{finding.coverage.value}; impact score {finding.impact_score}]"
                },
                "locations": [{"physicalLocation": {"artifactLocation": {"uri": "impactweave.yaml"}}}],
                "properties": {"graphPath": finding.graph_path, "coverage": finding.coverage.value},
            }
        )
    payload = {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [
            {"tool": {"driver": {"name": "ImpactWeave Nexus", "version": report.schema_version}}, "results": results}
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"
