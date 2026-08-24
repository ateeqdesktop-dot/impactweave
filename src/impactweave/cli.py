from __future__ import annotations

from pathlib import Path

import typer

from .engine import build_report
from .loader import load_manifest
from .report import to_json, to_markdown, to_sarif

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


if __name__ == "__main__":
    app()
