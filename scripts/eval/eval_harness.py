#!/usr/bin/env python3
import json
from pathlib import Path
import typer

app = typer.Typer(help="Simple evaluation harness (skeleton)")

@app.command()
def run(gold_dir: Path = typer.Option(..., "--gold"), system_reflow: Path = typer.Option(..., "--system", exists=True)):
    sys_doc = json.loads(system_reflow.read_text())
    gold_sections = json.loads((gold_dir / "sections.json").read_text())
    sys_titles = {s.get("title", "") for s in sys_doc.get("reflowed_sections", sys_doc.get("sections", []))}
    gold_titles = {s.get("title", "") for s in gold_sections.get("sections", [])}
    inter = len(sys_titles & gold_titles)
    prec = inter / max(1, len(sys_titles))
    rec = inter / max(1, len(gold_titles))
    typer.echo(f"Section overlap precision={prec:.2f} recall={rec:.2f}")

if __name__ == "__main__":
    app()

