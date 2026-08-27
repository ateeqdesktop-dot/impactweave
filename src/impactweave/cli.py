from __future__ import annotations

from pathlib import Path

import typer

from .engine import build_report
from .loader import load_manifest
from .planner import build_test_plan, git_changed_paths
from .report import to_json, to_markdown, to_sarif, to_test_plan_json, to_test_plan_markdown, to_test_plan_sarif

app = typer.Typer(no_args_is_help=True, add_completion=False)


def _emit(manifest: Path, output: Path | None, format: str) -> None:
    if format not in {"markdown", "json", "sarif"}:
        raise typer.BadParameter("format must be markdown, json, or sarif")
    report = build_report(load_manifest(manifest))
    content = {"markdown": to_markdown, "json": to_json, "sarif": to_sarif}[format](report)
    if output:
        output.write_text(content, encoding="utf-8")
    else:
        typer.echo(content, nl=False)
    if report.verdict.value in {"fail", "review"}:
        raise typer.Exit(code=1)


def _emit_test_plan(manifest: Path, changed_paths: list[str], output: Path | None, format: str) -> None:
    if format not in {"markdown", "json", "sarif"}:
        raise typer.BadParameter("format must be markdown, json, or sarif")
    report = build_test_plan(load_manifest(manifest), changed_paths)
    content = {
        "markdown": to_test_plan_markdown,
        "json": to_test_plan_json,
        "sarif": to_test_plan_sarif,
    }[format](report)
    if output:
        output.write_text(content, encoding="utf-8")
    else:
        typer.echo(content, nl=False)
    if report.verdict.value == "review":
        raise typer.Exit(code=1)


@app.command()
def validate(manifest: Path = typer.Argument(..., exists=True, readable=True)) -> None:
    """Validate a Nexus manifest without planning impact."""
    load_manifest(manifest)
    typer.echo("valid")


@app.command()
def plan(
    manifest: Path = typer.Argument(..., exists=True, readable=True),
    output: Path | None = typer.Option(None, "--output", "-o"),
    format: str = typer.Option("markdown", "--format", case_sensitive=False),
) -> None:
    """Rehearse a proposed contract change and emit an explainable report."""
    _emit(manifest, output, format)


@app.command()
def nexus(
    manifest: Path = typer.Argument(..., exists=True, readable=True),
    output: Path | None = typer.Option(None, "--output", "-o"),
    format: str = typer.Option("markdown", "--format", case_sensitive=False),
) -> None:
    """Run the ImpactWeave Nexus graph-aware decision engine."""
    _emit(manifest, output, format)


@app.command("test-plan")
def test_plan(
    manifest: Path = typer.Argument(..., exists=True, readable=True),
    changed: list[str] = typer.Option(
        [], "--changed", help="Relative path changed by the patch; repeat for multiple paths."
    ),
    repo: Path = typer.Option(Path("."), "--repo", exists=True, file_okay=False, dir_okay=True),
    base: str | None = typer.Option(None, "--base", help="Git base ref used with --head."),
    head: str | None = typer.Option(None, "--head", help="Git head ref used with --base."),
    output: Path | None = typer.Option(None, "--output", "-o"),
    format: str = typer.Option("markdown", "--format", case_sensitive=False),
) -> None:
    """Build a conservative test plan from changed paths or a Git diff; never runs tests."""
    if bool(base) != bool(head):
        raise typer.BadParameter("--base and --head must be provided together")
    if changed and (base or head):
        raise typer.BadParameter("use either --changed or --base/--head, not both")
    if base and head:
        changed = git_changed_paths(repo, base, head)
    if not changed:
        raise typer.BadParameter("provide --changed at least once or provide --base and --head")
    _emit_test_plan(manifest, changed, output, format)


if __name__ == "__main__":
    app()
