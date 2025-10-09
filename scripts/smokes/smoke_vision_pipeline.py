#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["typer>=0.12.3","rich>=13.7.1","jq==1.7.0.post0"]
# ///
from __future__ import annotations
import json, sys
from pathlib import Path
import typer
from rich.console import Console

app = typer.Typer(add_completion=False)
console = Console()


@app.command()
def main(
    pipeline_root: Path = typer.Option(Path("data/results/pipeline"), exists=True),
):
    """Quick sanity: Stage 06 caption non-empty; Stage 03 verified JSON present."""
    ok = True
    s06_json = pipeline_root / "06_figure_extractor/json_output/06_figures.json"
    if s06_json.exists():
        data = json.loads(s06_json.read_text())
        figs = data.get("figures") or []
        if not figs or not (figs[0].get("ai_description") or "").strip():
            console.print("[red]Stage 06: missing/non-empty ai_description.[/red]")
            ok = False
        else:
            console.print("[green]Stage 06: caption OK.[/green]")
    else:
        console.print("[red]Stage 06: figures JSON not found.[/red]")
        ok = False

    s03_json = pipeline_root / "03_suspicious_headers/json_output/03_verified_blocks.json"
    if s03_json.exists():
        try:
            blocks = json.loads(s03_json.read_text()).get("blocks") or []
            console.print(f"[green]Stage 03: verified_blocks present (blocks={len(blocks)}).[/green]")
        except Exception as e:
            console.print(f"[red]Stage 03: failed to parse verified_blocks.json: {e}[/red]")
            ok = False
    else:
        console.print("[yellow]Stage 03: verified_blocks.json not found.[/yellow]")

    raise typer.Exit(0 if ok else 1)


if __name__ == "__main__":
    app()

