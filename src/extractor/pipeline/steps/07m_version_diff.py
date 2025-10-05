#!/usr/bin/env python3
from __future__ import annotations

"""
07m: Version diff between two 07e reflow JSONs.
"""

import json
import hashlib
from pathlib import Path
from typing import Any, Dict

import typer
from loguru import logger

app = typer.Typer(help="Version diff generator.")


def block_sig(b: Dict[str, Any]) -> str:
    core = {
        "type": b.get("type"),
        "text": b.get("text") if b.get("type") == "paragraph" else None,
        "columns": b.get("columns") if b.get("type") == "table" else None,
        "rows_hash": hashlib.sha256(
            json.dumps(b.get("rows"), sort_keys=True, default=str).encode()
        ).hexdigest()
        if b.get("rows")
        else None,
        "caption": b.get("caption") if b.get("type") == "figure" else None,
    }
    return hashlib.sha256(json.dumps(core, sort_keys=True).encode()).hexdigest()


@app.command()
def run(
    old_reflow_json: Path = typer.Option(..., "--old", exists=True),
    new_reflow_json: Path = typer.Option(..., "--new", exists=True),
    output_dir: Path = typer.Option(Path("data/results/pipeline"), "-o"),
):
    old = json.loads(old_reflow_json.read_text())
    new = json.loads(new_reflow_json.read_text())
    old_index: Dict[str, str] = {}
    for s in old.get("reflowed_sections", old.get("sections", [])):
        for b in s.get("reflowed_json", {}).get("blocks", []):
            a = b.get("anchor_id")
            if a:
                old_index[a] = block_sig(b)
    deltas = []
    current_anchors = set()
    for s in new.get("reflowed_sections", new.get("sections", [])):
        for b in s.get("reflowed_json", {}).get("blocks", []):
            a = b.get("anchor_id")
            if not a:
                continue
            current_anchors.add(a)
            sig = block_sig(b)
            if a not in old_index:
                deltas.append({"anchor_id": a, "change_type": "added"})
            elif old_index[a] != sig:
                deltas.append({"anchor_id": a, "change_type": "modified"})
    for a in old_index.keys() - current_anchors:
        deltas.append({"anchor_id": a, "change_type": "removed"})
    out_dir = output_dir / "07m_version_diff" / "json_output"
    out_dir.mkdir(parents=True, exist_ok=True)
    outp = out_dir / "07m_deltas.json"
    outp.write_text(json.dumps({"deltas": deltas, "deterministic": True, "hash_component": "07m"}, indent=2))
    logger.success(f"07m: wrote {outp} (changes={len(deltas)})")


if __name__ == "__main__":
    app()

