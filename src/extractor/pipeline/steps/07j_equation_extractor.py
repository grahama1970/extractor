#!/usr/bin/env python3
from __future__ import annotations

"""
07j: Equation & variable extraction (heuristic).
"""

import json
import re
import hashlib
from pathlib import Path
from typing import Any, Dict, List

import typer
from loguru import logger

app = typer.Typer(help="Equation extractor")

MATH_SYMBOLS = set("=+−–*/^∑∏√≈≠≤≥<>±()[]{}|%")
VAR_RE = re.compile(r"\b([A-Za-z][A-Za-z0-9_]*)\b")


def math_density(text: str) -> float:
    if not text:
        return 0.0
    math_chars = sum(1 for c in text if c in MATH_SYMBOLS)
    return math_chars / max(1, len(text))


@app.command()
def run(
    reflow_json: Path = typer.Option(..., "--reflow", exists=True),
    output_dir: Path = typer.Option(Path("data/results/pipeline"), "-o"),
    density_threshold: float = typer.Option(0.08, "--density-th"),
    min_length: int = typer.Option(10, "--min-len"),
):
    doc = json.loads(reflow_json.read_text())
    equations: List[Dict[str, Any]] = []
    variables: Dict[str, set] = {}
    eq_counter = 1
    for sec in doc.get("reflowed_sections", doc.get("sections", [])):
        for blk in sec.get("reflowed_json", {}).get("blocks", []):
            if blk.get("type") != "paragraph":
                continue
            text = blk.get("text") or ""
            dens = math_density(text)
            if dens >= density_threshold and len(text) >= min_length and "=" in text:
                eq_id = f"eq::{hashlib.sha256((str(eq_counter)+text[:80]).encode()).hexdigest()[:12]}"
                eq_vars = []
                for m in VAR_RE.finditer(text):
                    v = m.group(1)
                    if v.lower() in ("and", "or", "the", "of", "in", "for", "if", "not", "is"):
                        continue
                    eq_vars.append(v)
                    variables.setdefault(v, set()).add(eq_id)
                equations.append(
                    {
                        "equation_id": eq_id,
                        "section_id": sec.get("id") or sec.get("section_id"),
                        "anchor_candidates": [blk.get("anchor_id")],
                        "text": text,
                        "variable_symbols": sorted(set(eq_vars)),
                        "hash": hashlib.sha256(text.encode()).hexdigest(),
                    }
                )
                eq_counter += 1

    var_list = []
    for sym, eqs in variables.items():
        var_list.append(
            {
                "symbol": sym,
                "equations": sorted(eqs),
                "variable_id": f"var::{hashlib.sha256(sym.encode()).hexdigest()[:12]}",
            }
        )

    out_dir = output_dir / "07j_equation_extractor" / "json_output"
    out_dir.mkdir(parents=True, exist_ok=True)
    outp = out_dir / "07j_equations.json"
    outp.write_text(
        json.dumps(
            {
                "equations": equations,
                "variables": var_list,
                "deterministic": True,
                "hash_component": "07j",
            },
            indent=2,
        )
    )
    logger.success(f"07j: wrote {outp} (equations={len(equations)}, variables={len(var_list)})")


if __name__ == "__main__":
    app()

