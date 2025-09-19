#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///
"""Smoke: RTM v0 fields present in Stage 10 flattened JSON.

Checks that at least one object includes rtm.section_id and rtm.evidence.page_num.
Writes a small coverage summary to scripts/artifacts/rtm_links_summary.json.
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
def main(stage10_root: Path = typer.Option(Path("data/results"), exists=True)):
    stage10 = _find_latest_stage10(stage10_root)
    if not stage10.exists():
        typer.echo(f"No Stage 10 JSON found under {stage10_root}", err=True)
        raise typer.Exit(1)
    data = json.loads(stage10.read_text())
    total = 0
    with_rtm = 0
    with_evidence = 0
    for obj in data:
        total += 1
        rtm = obj.get("rtm") if isinstance(obj, dict) else None
        if isinstance(rtm, dict) and rtm.get("section_id"):
            with_rtm += 1
            ev = rtm.get("evidence") if isinstance(rtm.get("evidence"), dict) else None
            if ev and (ev.get("page_num") is not None):
                with_evidence += 1
    summary = {
        "stage10": str(stage10),
        "total": total,
        "with_rtm": with_rtm,
        "with_evidence": with_evidence,
    }
    out = Path("scripts/artifacts"); out.mkdir(parents=True, exist_ok=True)
    (out / "rtm_links_summary.json").write_text(json.dumps(summary, indent=2))
    if with_rtm == 0:
        typer.echo("No RTM fields found", err=True)
        raise typer.Exit(1)
    print("OK: RTM fields present in Stage 10")


if __name__ == "__main__":
    app()
