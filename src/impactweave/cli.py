from __future__ import annotations

from pathlib import Path

import typer

from .engine import build_report
from .loader import load_manifest
from .report import to_json, to_markdown

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.command()
def validate(manifest: Path = typer.Argument(..., exists=True, readable=True)) -> None:
    """Validate a manifest without planning impact."""
    load_manifest(manifest)
    typer.echo("valid")


@app.command()
def plan(
    manifest: Path = typer.Argument(..., exists=True, readable=True),
    output: Path | None = typer.Option(None, "--output", "-o"),
    format: str = typer.Option("markdown", "--format", case_sensitive=False),
) -> None:
    """Rehearse a proposed contract change and emit a report."""
    if format not in {"markdown", "json"}:
        raise typer.BadParameter("format must be markdown or json")
    report = build_report(load_manifest(manifest))
    content = to_markdown(report) if format == "markdown" else to_json(report)
    if output:
        output.write_text(content, encoding="utf-8")
    else:
        typer.echo(content, nl=False)
    if report.verdict.value in {"fail", "review"}:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
