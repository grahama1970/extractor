#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12",
# ]
# ///
from __future__ import annotations

import json
from pathlib import Path
import typer

app = typer.Typer(add_completion=False)


@app.command()
def main(
    lean4_out: Path = typer.Argument(..., exists=True, readable=True, help="Lean4 OUT.json (batch object)"),
    out_json: Path = typer.Argument(..., help="Output flattened JSON with rtm.lean4_* fields"),
):
    payload = json.loads(lean4_out.read_text())
    proof_results = payload.get("proof_results") or []
    flat: list[dict] = []
    for e in proof_results:
        item = e.get("item", {})
        ctx = item.get("context") or {}
        src = item.get("source_details") or {}
        analysis = e.get("analysis") or {}
        flat.append(
            {
                "section_id": src.get("section_id") or ctx.get("section_id"),
                "doc_id": ctx.get("doc_id"),
                "requirement_text": item.get("requirement_text"),
                "lean4_status": e.get("status"),
                "rtm": {
                    "lean4_norm": analysis.get("normalized_prop"),
                    "lean4_polarity": analysis.get("polarity"),
                    "lean4_shape": analysis.get("shape"),
                    "lean4_lemmas": analysis.get("used_lemmas") or [],
                    "lemma_candidates": analysis.get("lemma_candidates") or [],
                },
            }
        )
    out_json.write_text(json.dumps({"items": flat}, indent=2, ensure_ascii=False))
    typer.secho(f"OK: wrote {out_json}", fg=typer.colors.GREEN)


if __name__ == "__main__":
    app()
