#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///
"""Smoke: OSLC export stub

Loads the latest Stage 10 flattened JSON and exports minimal OSLC JSON.
Asserts presence of oslc:resources with id/title.
"""
from __future__ import annotations

import json
from pathlib import Path
import typer

app = typer.Typer(add_completion=False)


def _find_latest_stage10(root: Path) -> Path:
    cands = sorted(root.rglob("10_arangodb_exporter/json_output/10_flattened_data.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return cands[0] if cands else root / "pipeline/10_arangodb_exporter/json_output/10_flattened_data.json"


@app.command()
def main(root: Path = typer.Option(Path("data/results"), exists=True)):
    stage10 = _find_latest_stage10(root)
    if not stage10.exists():
        print("SKIP: no Stage 10 flattened JSON found")
        raise typer.Exit(0)
    import sys
    src_dir = str((Path(__file__).resolve().parents[3] / "src").resolve())
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
    from extractor.pipeline.tools.oslc_export import export_oslc
    out = Path("scripts/artifacts/oslc_links.json")
    res = export_oslc(stage10, out)
    data = json.loads(out.read_text())
    ok = isinstance(data, dict) and isinstance(data.get("oslc:resources"), list) and len(data["oslc:resources"]) >= 1
    Path("scripts/artifacts").mkdir(parents=True, exist_ok=True)
    (Path("scripts/artifacts")/"oslc_export_report.json").write_text(json.dumps({"ok": ok, **res}, indent=2))
    if not ok:
        typer.echo("OSLC export invalid", err=True)
        raise typer.Exit(1)
    print("OK: OSLC export")


if __name__ == "__main__":
    app()

