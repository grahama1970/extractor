#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path
from typing import Optional

import typer
from dotenv import load_dotenv, find_dotenv


app = typer.Typer(add_completion=False, help="Happy-path PDF extraction: one command, validated output.")


@app.command()
def run(
    pdf: Path = typer.Option(
        Path("data/input/pipeline/BHT_CV32A65X_marked.pdf"),
        exists=True,
        help="Input PDF (defaults to canonical BHT sample)",
    ),
    results: Path = typer.Option(
        Path("data/results/pipeline_happy"), help="Results directory"
    ),
    arango_db: str = typer.Option(
        os.getenv("ARANGO_DATABASE", "pdf_knowledge_base_test"),
        help="ArangoDB database name for this run",
    ),
    verbose: bool = typer.Option(False, "--verbose", help="Echo the full command"),
):
    """Run the pipeline with deterministic toggles and gold validation.

    - Uses fast/deterministic paths for LLM/embeddings to avoid flaky results.
    - Validates each stage against gold invariants and fails fast on mismatch.
    """
    # Load .env and prepare environment
    load_dotenv(find_dotenv() or None)
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", str(Path.cwd() / "src"))
    env["ARANGO_DATABASE"] = arango_db

    results.mkdir(parents=True, exist_ok=True)

    # Delegate to the unified surface to keep one code path
    cmd = [
        "pipeline-run",
        "--pdf",
        str(pdf),
        "--results",
        str(results),
        "--mode",
        "fast",
    ]

    if verbose:
        typer.echo("Running:\n" + " \\\n+\n  ".join(cmd))

    proc = subprocess.run(cmd, env=env)
    # Build a simple run summary from validation artifacts
    try:
        import json
        import time

        summary = {
            "ok": proc.returncode == 0,
            "results": str(results),
            "arango_db": arango_db,
            "stages": {},
            "score": None,
        }
        art_dir = Path("scripts/artifacts")
        stage_ids = ["01","02","03","04","05","06","07","09","10","11","14"]
        for sid in stage_ids:
            p = art_dir / f"validate_stage_{sid}.json"
            if p.exists():
                try:
                    data = json.loads(p.read_text())
                    summary["stages"][sid] = {"pass": bool(data.get("pass", True))}
                    # hoist useful metrics for scoring
                    if sid == "07":
                        for c in data.get("checks", []):
                            if c.get("name", "").startswith("token_similarity:"):
                                summary["stages"][sid]["token_similarity"] = c.get("similarity")
                    if sid == "11":
                        for c in data.get("checks", []):
                            if c.get("name") == "has_edges_or_confirmation":
                                summary["stages"][sid]["edges_ok"] = bool(c.get("pass"))
                except Exception:
                    summary["stages"][sid] = {"pass": False}
        # Optional: read Stage 09 report for coverage stats
        p9 = art_dir / "validate_stage_09.json"
        if p9.exists():
            try:
                rep9 = json.loads(p9.read_text())
                for c in rep9.get("checks", []):
                    if c.get("name", "").startswith("list_similarity_coverage:"):
                        n = c.get("n") or 0
                        h = c.get("hits") or 0
                        summary.setdefault("stages", {}).setdefault("09", {})
                        summary["stages"]["09"]["coverage"] = (h / max(1, n)) if n else None
                        break
            except Exception:
                pass

        # Compute a simple score (0–100)
        s07 = summary.get("stages", {}).get("07", {})
        s09 = summary.get("stages", {}).get("09", {})
        s10 = summary.get("stages", {}).get("10", {}).get("pass")
        s11 = summary.get("stages", {}).get("11", {}).get("pass")
        ts = s07.get("token_similarity") or 0.0
        cov = s09.get("coverage") if s09 else None
        score = 0.0
        score += 50.0 * float(max(0.0, min(1.0, ts)))
        if cov is not None:
            score += 30.0 * float(max(0.0, min(1.0, cov)))
        if s10:
            score += 10.0
        if s11:
            score += 10.0
        summary["score"] = round(score, 1)

        art_dir.mkdir(parents=True, exist_ok=True)
        out = art_dir / "run_summary_happy.json"
        out.write_text(json.dumps(summary, indent=2))
        if verbose:
            typer.echo(f"Wrote run summary → {out}")
    except Exception:
        pass

    raise typer.Exit(proc.returncode)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
