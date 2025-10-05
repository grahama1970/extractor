#!/usr/bin/env python3
from __future__ import annotations

"""
07k: Table span/header hierarchy reconstruction (heuristic).
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List

import typer
from loguru import logger

app = typer.Typer(help="Table header tier reconstruction.")

UP_RE = re.compile(r"^[A-Z0-9 _/\-]+$")


def is_header_row(row: List[str]) -> bool:
    tokens = [c.strip() for c in (row or []) if c and c.strip()]
    if not tokens:
        return False
    up = sum(1 for t in tokens if UP_RE.match(t) and len(t) <= 30)
    return (up / max(1, len(tokens))) >= 0.6


@app.command()
def run(
    reflow_json: Path = typer.Option(..., "--reflow", exists=True),
    output_dir: Path = typer.Option(Path("data/results/pipeline"), "-o"),
    max_header_rows: int = typer.Option(3, "--max-header-rows"),
):
    doc = json.loads(reflow_json.read_text())
    table_headers: Dict[str, Any] = {}
    for sec in doc.get("reflowed_sections", doc.get("sections", [])):
        for blk in sec.get("reflowed_json", {}).get("blocks", []):
            if blk.get("type") != "table":
                continue
            rows = blk.get("rows") or []
            header_tiers = []
            for i, r in enumerate(rows[:max_header_rows]):
                if is_header_row(r):
                    header_tiers.append(r)
                else:
                    break
            if len(header_tiers) > 1:
                table_headers[blk.get("anchor_id")] = {"header_tiers": header_tiers}

    out_dir = output_dir / "07k_table_span_refiner" / "json_output"
    out_dir.mkdir(parents=True, exist_ok=True)
    outp = out_dir / "07k_table_spans.json"
    outp.write_text(json.dumps({"tables": table_headers, "deterministic": True, "hash_component": "07k"}, indent=2))
    logger.success(f"07k: wrote {outp} (multi-tier tables={len(table_headers)})")


if __name__ == "__main__":
    app()

