#!/usr/bin/env python3
from __future__ import annotations

"""
07i: Entity extractor for hardware-like tokens (signals/registers/fields).
"""

import json
import re
import hashlib
from pathlib import Path
from typing import Any, Dict, List

import typer
from loguru import logger

app = typer.Typer(help="Entity extraction (signals/registers/fields).")

SIGNAL_RE = re.compile(r"\b[A-Z][A-Z0-9_]{2,}\b")
REGISTER_RE = re.compile(r"\b([A-Z][A-Z0-9_]{2,}_REG)\b")
FIELD_RE = re.compile(r"\b([A-Z][A-Z0-9_]{1,})\[(\d+):(\d+)\]\b")


def classify_token(tok: str) -> str:
    if REGISTER_RE.match(tok):
        return "register"
    if SIGNAL_RE.match(tok):
        return "signal"
    return "unknown"


@app.command()
def run(
    reflow_json: Path = typer.Option(..., "--reflow", exists=True),
    output_dir: Path = typer.Option(Path("data/results/pipeline"), "-o"),
    min_occurrences: int = typer.Option(2, "--min-occurrences"),
):
    doc = json.loads(reflow_json.read_text())
    occurrences: Dict[str, List[Dict[str, Any]]] = {}
    for sec in doc.get("reflowed_sections", doc.get("sections", [])):
        for blk in sec.get("reflowed_json", {}).get("blocks", []):
            if blk.get("type") != "paragraph":
                continue
            text = blk.get("text") or ""
            for m in SIGNAL_RE.finditer(text):
                tok = m.group(0)
                cat = classify_token(tok)
                if cat == "unknown":
                    continue
                occurrences.setdefault(tok, []).append(
                    {
                        "anchor_id": blk.get("anchor_id"),
                        "section_id": sec.get("id") or sec.get("section_id"),
                        "span": [m.start(), m.end()],
                        "category": cat,
                    }
                )
            for f in FIELD_RE.finditer(text):
                fname = f.group(1)
                msb = int(f.group(2))
                lsb = int(f.group(3))
                occurrences.setdefault(fname, []).append(
                    {
                        "anchor_id": blk.get("anchor_id"),
                        "section_id": sec.get("id") or sec.get("section_id"),
                        "span": [f.start(), f.end()],
                        "category": "field",
                        "bit_range": [msb, lsb],
                    }
                )

    entities = []
    for tok, occ in occurrences.items():
        if len(occ) < min_occurrences:
            continue
        cat = occ[0]["category"]
        entities.append(
            {
                "name": tok,
                "category": cat,
                "occurrences": occ,
                "entity_id": f"ent::{cat}::{hashlib.sha256(tok.encode()).hexdigest()[:12]}",
            }
        )

    out_dir = output_dir / "07i_entity_extractor" / "json_output"
    out_dir.mkdir(parents=True, exist_ok=True)
    outp = out_dir / "07i_entities.json"
    outp.write_text(
        json.dumps({"entities": entities, "deterministic": True, "hash_component": "07i"}, indent=2)
    )
    logger.success(f"07i: wrote {outp} (entities={len(entities)})")


if __name__ == "__main__":
    app()

