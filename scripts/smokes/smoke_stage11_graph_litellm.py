#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "python-dotenv",
#   "typer>=0.12",
#   "litellm>=1.74.7",
# ]
# ///
from __future__ import annotations

import os
import sys
import json
import asyncio
import typer
from dotenv import load_dotenv, find_dotenv


app = typer.Typer(add_completion=False, help="Smoke: Stage 11 graph rationales via litellm_call (no DB)")


@app.command()
def main(
    timeout: int = typer.Option(30, "--timeout"),
):
    try:
        load_dotenv(find_dotenv(usecwd=True) or None)
        os.environ.setdefault("LITELLM_HTTPX", "1")
        sys.path.insert(0, os.path.abspath("src"))
        import importlib.util
        from pathlib import Path

        p = Path("src/extractor/pipeline/steps/11_arango_create_graph.py").resolve()
        spec = importlib.util.spec_from_file_location("stage11", str(p))
        if not spec or not spec.loader:
            raise SystemExit("Failed to load stage 11 module")
        stage11 = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(stage11)  # type: ignore[attr-defined]

        enrich = getattr(stage11, "enrich_edges_with_rationales")
        # Build tiny doc graph with two docs
        edges = [{"_from": "pdf_objects/docA", "_to": "pdf_objects/docB"}]
        doc_text_map = {
            "pdf_objects/docA": "The Branch History Table records branch predictions.",
            "pdf_objects/docB": "The predictor uses the BHT to update outcomes.",
        }

        async def run_once():
            await enrich(edges, doc_text_map)
            return edges

        out_edges = asyncio.run(run_once())
        ok = bool(out_edges and isinstance(out_edges[0].get("rationale", ""), str) and out_edges[0].get("rationale_model"))
        outdir = os.path.join("scripts", "artifacts")
        os.makedirs(outdir, exist_ok=True)
        with open(os.path.join(outdir, "stage11_litellm.json"), "w", encoding="utf-8") as f:
            json.dump({"ok": ok, "edges": out_edges}, f, ensure_ascii=False, indent=2)
        if not ok:
            raise SystemExit("Stage 11 rationales missing fields")
        typer.echo("OK: Stage 11 litellm rationales returned")
    except Exception as e:
        typer.echo(f"Smoke failed: {e}", err=True)
        raise SystemExit(1)


if __name__ == "__main__":
    app()
