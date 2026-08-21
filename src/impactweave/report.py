from __future__ import annotations

import json

from .models import ImpactReport


def to_json(report: ImpactReport) -> str:
    payload = report.model_dump(mode="json")
    payload["generated_at"] = "redacted-for-determinism"
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def to_markdown(report: ImpactReport) -> str:
    lines = [f"# ImpactWeave report: `{report.verdict.value}`", "", "| Metric | Count |", "|---|---:|"]
    lines.extend(f"| {key} | {value} |" for key, value in sorted(report.summary.items()))
    lines.extend(["", "## Contract changes", "", "| Contract | Path | Severity | Reason |", "|---|---|---|---|"])
    for change in report.changes:
        lines.append(f"| `{change.contract}` | `{change.path}` | **{change.severity.value}** | {change.reason} |")
    lines.extend(
        [
            "",
            "## Consumer impact",
            "",
            "| Producer | Consumer | Contract | Path | Confidence | Evidence |",
            "|---|---|---|---|---:|---|",
        ]
    )
    for finding in report.findings:
        confidence = "unknown" if finding.confidence is None else f"{finding.confidence:.2f}"
        evidence = finding.evidence_source or "none"
        row = (
            f"| `{finding.producer}` | `{finding.consumer}` | `{finding.contract}` | "
            f"`{finding.path}` | {confidence} | {evidence} |"
        )
        lines.append(row)
    if report.unknown_edges:
        lines.extend(["", "## Unknown edges", ""])
        lines.extend(f"- {item}" for item in report.unknown_edges)
    return "\n".join(lines) + "\n"
