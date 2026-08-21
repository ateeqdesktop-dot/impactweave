from pathlib import Path

import pytest
from typer.testing import CliRunner

from impactweave.cli import app
from impactweave.diff import compare_contracts
from impactweave.engine import build_report
from impactweave.loader import load_evidence_jsonl, load_json, load_manifest
from impactweave.models import ContractField, ContractKind, ContractSnapshot, FieldType, Severity, Verdict
from impactweave.report import to_json, to_markdown

FIXTURE = Path(__file__).parents[1] / "fixtures" / "demo.yaml"


def contract(fields: list[ContractField]) -> ContractSnapshot:
    return ContractSnapshot(name="orders", version="1", kind=ContractKind.HTTP_JSON, fields=fields)


def test_removed_and_required_changes_are_breaking() -> None:
    before = contract(
        [
            ContractField(path="/id", type=FieldType.STRING, required=True),
            ContractField(path="/name", type=FieldType.STRING),
        ]
    )
    after = contract(
        [
            ContractField(path="/id", type=FieldType.INTEGER, required=True),
            ContractField(path="/age", type=FieldType.INTEGER, required=True),
        ]
    )
    changes = compare_contracts(before, after)
    assert {item.path for item in changes} == {"/id", "/name", "/age"}
    assert all(item.severity == Severity.BREAKING for item in changes)


def test_optional_field_is_non_breaking() -> None:
    before = contract([])
    after = contract([ContractField(path="/note", type=FieldType.STRING)])
    changes = compare_contracts(before, after)
    assert changes[0].severity == Severity.INFO


def test_demo_requires_review_when_breaking_edges_lack_evidence() -> None:
    manifest = load_manifest(FIXTURE)
    report = build_report(manifest)
    assert report.verdict == Verdict.REVIEW
    assert report.summary["breaking"] == 3
    assert len(report.findings) == 9


def test_permissive_mode_fails_on_breaking_change_without_review() -> None:
    manifest = load_manifest(FIXTURE)
    manifest.strict = False
    report = build_report(manifest)
    assert report.verdict == Verdict.FAIL


def test_reports_are_stable_except_generated_at() -> None:
    report = build_report(load_manifest(FIXTURE))
    payload = to_json(report)
    assert "redacted-for-determinism" in payload
    assert "orders.created" in payload
    markdown = to_markdown(report)
    assert "Consumer impact" in markdown
    assert "billing" in markdown


def test_timezone_is_required(tmp_path: Path) -> None:
    bad = FIXTURE.read_text(encoding="utf-8").replace("2026-08-20T12:00:00Z", "2026-08-20T12:00:00")
    path = tmp_path / "bad.yaml"
    path.write_text(bad, encoding="utf-8")
    with pytest.raises(ValueError, match="invalid manifest"):
        load_manifest(path)


def test_cli_validate_and_plan_json(tmp_path: Path) -> None:
    runner = CliRunner()
    valid = runner.invoke(app, ["validate", str(FIXTURE)])
    assert valid.exit_code == 0
    output = tmp_path / "impact.json"
    planned = runner.invoke(app, ["plan", str(FIXTURE), "--format", "json", "--output", str(output)])
    assert planned.exit_code == 1
    assert '"verdict": "review"' in output.read_text(encoding="utf-8")


def test_cli_rejects_unknown_format() -> None:
    result = CliRunner().invoke(app, ["plan", str(FIXTURE), "--format", "xml"])
    assert result.exit_code != 0


def test_json_and_jsonl_validation_errors(tmp_path: Path) -> None:
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid JSON"):
        load_json(bad_json)
    evidence = tmp_path / "evidence.jsonl"
    evidence.write_text(
        '{"producer":"a","consumer":"b","contract":"c","confidence":0.5,"source":"test","observed_at":"2026-01-01T00:00:00Z"}\n',
        encoding="utf-8",
    )
    assert load_evidence_jsonl(evidence)[0].consumer == "b"
    evidence.write_text("not-json\n", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid evidence"):
        load_evidence_jsonl(evidence)


def test_unknown_changed_contract_is_reviewed() -> None:
    manifest = load_manifest(FIXTURE)
    manifest.proposed[0].fields.append(ContractField(path="/new", type=FieldType.STRING, required=True))
    manifest.edges.clear()
    report = build_report(manifest)
    assert report.verdict == Verdict.REVIEW
    assert any("no consumer edges" in item for item in report.unknown_edges)
