#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.16.0",
# ]
# ///

"""
Batch helper: run the pipeline on multiple PDFs and produce viewable PDFs with
overlaid annotations (from Stage 02 blocks and Stage 01 annotations).

Example:
  uv run scripts/pipeline/run_and_annotate.py \
    --glob "data/pdfs/*.pdf" \
    --limit 3

Outputs per PDF under: data/results/pipeline_multi/<slug>/{...}
"""

from __future__ import annotations

import glob
import json
import os
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import typer


app = typer.Typer(help="Run pipeline (strict) on multiple PDFs and render annotated outputs")


@dataclass
class RunResult:
    stem: str
    base: Path
    clean_pdf: Optional[Path]
    blocks_json: Optional[Path]
    stage01_json: Optional[Path]
    ann_blocks_out: Optional[Path]
    ann_stage01_out: Optional[Path]


def _slug(stem: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in stem).strip("_")


def _run(cmd: List[str], env: Optional[dict] = None) -> int:
    print("+", " ".join(shlex.quote(c) for c in cmd))
    proc = subprocess.run(cmd, env=env)
    return int(proc.returncode)


@app.command()
def main(
    glob_pattern: str = typer.Option("data/pdfs/*.pdf", "--glob", help="Glob for input PDFs"),
    limit: int = typer.Option(3, help="Max PDFs to process (0=all)"),
    driver: str = typer.Option("stages", help="Driver: 'stages' (01→02) or 'run_all'", case_sensitive=False),
    # Stage 02 is strict-only by policy; env is forced accordingly
    verify_tables: bool = typer.Option(True, help="Generate table verification bundles when tables exist"),
):
    pdfs = sorted(Path(p) for p in glob.glob(glob_pattern))
    if limit and len(pdfs) > limit:
        pdfs = pdfs[:limit]
    if not pdfs:
        raise SystemExit("No PDFs matched. Adjust --glob or add files to data/pdfs/")

    results: List[RunResult] = []
    for pdf in pdfs:
        stem = pdf.stem
        slug = _slug(stem)
        out_base = Path("data/results/pipeline_multi") / slug
        out_base.mkdir(parents=True, exist_ok=True)

        # Configure env
        env = os.environ.copy()
        env.setdefault("PYTHONPATH", str(Path("src").resolve()))
        env.setdefault("RUN_ALL_DEBUG", "1")
        # Enforce strict predictor mode for Stage 02 (no fallbacks allowed)
        env["OFFLINE_PDF_PREDICTORS"] = "0"

        if driver.lower() == "run_all":
            # End-to-end (may fail at later stages). Kept for parity, but strict tests prefer stages-only.
            _run(
                [
                    "uv", "run", "python", "-m", "extractor.pipeline.run_all",
                    "--pdf", str(pdf), "--results", str(out_base), "--no-resume",
                    "--summary-only07", "--skip-proving08", "--skip-export10",
                    "--skip-embeddings10", "--skip-graph11",
                ],
                env=env,
            )
        else:
            # Strict Stage‑01 → Stage‑02
            rc = _run(
                [
                    "uv", "run", "--active", "python", "-m",
                    "extractor.pipeline.steps.01_annotation_processor", "run",
                    str(pdf), "-o", str(out_base),
                ],
                env=env,
            )
            if rc != 0:
                print(f"Stage 01 failed for {pdf} (rc={rc}); continuing...")
                # Continue to next PDF
                results.append(RunResult(stem=stem, base=out_base, clean_pdf=None, blocks_json=None, stage01_json=None, ann_blocks_out=None, ann_stage01_out=None))
                continue
            clean_candidates = sorted((out_base / "01_annotation_processor").glob("*_clean.pdf"))
            if not clean_candidates:
                raise SystemExit(f"No clean PDF from Stage 01 for {pdf}")
            clean_pdf = clean_candidates[0]
            rc = _run(
                [
                    "uv", "run", "--active", "python", "-m",
                    "extractor.pipeline.steps.02_marker_extractor", "run",
                    str(clean_pdf), "-o", str(out_base),
                ],
                env=env,
            )
            if rc != 0:
                print(f"Stage 02 failed for {pdf} (rc={rc}); continuing to artifacts where possible…")

        # Locate artifacts
        stage01_dir = out_base / "01_annotation_processor"
        stage02_dir = out_base / "02_marker_extractor"
        clean_pdf = None
        try:
            cands = sorted(stage01_dir.glob("*_clean.pdf"))
            clean_pdf = cands[0] if cands else None
        except Exception:
            pass
        blocks_json = stage02_dir / "json_output" / "02_marker_blocks.json"
        if not blocks_json.exists():
            blocks_json = None
        stage01_json = stage01_dir / "json_output" / "01_annotations.json"
        if not stage01_json.exists():
            stage01_json = None
        tables_json = out_base / "05_table_extractor" / "json_output" / "05_tables.json"
        if not tables_json.exists():
            tables_json = None

        # Render annotated PDFs where possible
        ann_dir = out_base / "annotated"
        ann_blocks_out = None
        ann_stage01_out = None
        if clean_pdf and blocks_json:
            ann_blocks_out = ann_dir / f"{slug}__blocks_annotated.pdf"
            ann_dir.mkdir(parents=True, exist_ok=True)
            # If a verify_dir exists, pass it so Table overlays link to view.html
            verify_dir = out_base / "05_table_extractor" / "verify"
            args = [
                [
                    "uv", "run", "--active",
                    "python",
                    "-m",
                    "extractor.pipeline.tools.render_annotated_pdf",
                    "from-blocks",
                    "--pdf",
                    str(clean_pdf),
                    "--blocks-json",
                    str(blocks_json),
                    "--out",
                    str(ann_blocks_out),
                    "--label-style", "tab",
                ]
            ]
            if verify_dir.exists():
                args[0] += ["--verify-dir", str(verify_dir)]
            _run(args[0],
                env=env,
            )
        if clean_pdf and stage01_json:
            ann_stage01_out = ann_dir / f"{slug}__stage01_annotated.pdf"
            ann_dir.mkdir(parents=True, exist_ok=True)
            _run(
                [
                    "uv", "run", "--active",
                    "python",
                    "-m",
                    "extractor.pipeline.tools.render_annotated_pdf",
                    "from-stage01",
                    "--pdf",
                    str(clean_pdf),
                    "--stage01-json",
                    str(stage01_json),
                    "--out",
                    str(ann_stage01_out),
                    "--label-style", "tab",
                ],
                env=env,
            )

        # Table verification bundle
        if verify_tables and clean_pdf and tables_json:
            verify_dir = out_base / "05_table_extractor" / "verify"
            _run(
                [
                    "uv", "run", "--active",
                    "python", "-m", "extractor.pipeline.tools.table_verify",
                    str(clean_pdf), str(tables_json), "-o", str(verify_dir),
                ],
                env=env,
            )

        # Self-assessment (best-effort)
        try:
            _run([
                "uv", "run", "--active", "python", "-m",
                "extractor.pipeline.tools.self_assess", str(out_base)
            ], env=env)
        except Exception:
            pass

        results.append(
            RunResult(
                stem=stem,
                base=out_base,
                clean_pdf=clean_pdf,
                blocks_json=blocks_json,
                stage01_json=stage01_json,
                ann_blocks_out=ann_blocks_out,
                ann_stage01_out=ann_stage01_out,
            )
        )

    # Summary
    print("\n=== Summary ===")
    for r in results:
        print(f"- {r.stem}")
        print(f"  base: {r.base}")
        print(f"  clean_pdf: {r.clean_pdf}")
        print(f"  blocks_json: {r.blocks_json}")
        print(f"  stage01_json: {r.stage01_json}")
        print(f"  ann_blocks_out: {r.ann_blocks_out}")
        print(f"  ann_stage01_out: {r.ann_stage01_out}")


if __name__ == "__main__":  # pragma: no cover
    app()
