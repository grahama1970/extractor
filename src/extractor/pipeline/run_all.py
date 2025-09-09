#!/usr/bin/env python3
"""
Run All Pipeline Stages (01 → 14) end-to-end with a single CLI.

Features
- Respects .env and per-run session id (LITELLM_SESSION_ID or generated)
- Uses a dedicated ArangoDB test database unless overridden
- Supports full Lean4 proving by wiring LEAN4_CLI_CMD to the Lean project CLI

Usage
  python -m extractor.pipeline.run_all run \
    --pdf data/input/pipeline/BHT_CV32A65X_marked.pdf \
    --results data/results/pipeline \
    --arango-db pdf_knowledge_base_test \
    --lean4-cli "python /home/graham/workspace/experiments/lean4/src/lean4_prover/cli_mini.py"

Notes
- LITELLM_VLM_MODEL is the single source for VLM (e.g., openai/gpt-5-mini)
- LITELLM_ATTACH_SESSION defaults to true; cache is namespaced by session id
"""
from __future__ import annotations

import os
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional

import typer

app = typer.Typer(help="Run all pipeline stages end-to-end")


def _run(cmd: list[str], env: dict[str, str]) -> None:
    proc = subprocess.run(cmd, env=env)
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed ({proc.returncode}): {' '.join(cmd)}")


def _ensure_env(base_env: dict[str, str], results_dir: Path, arango_db: str, session_id: Optional[str], lean4_cli: Optional[str]) -> dict[str, str]:
    e = os.environ.copy()
    e.update(base_env)
    e.setdefault("PYTHONPATH", str(Path.cwd() / "src"))
    # Session + provider attachment
    if session_id:
        e["LITELLM_SESSION_ID"] = session_id
        e.setdefault("LITELLM_CACHE_NAMESPACE", session_id)
    e.setdefault("LITELLM_ATTACH_SESSION", "true")
    # Arango test DB
    if arango_db:
        e["ARANGO_DATABASE"] = arango_db
    # Lean4 CLI (full proving)
    if lean4_cli:
        # Prefer batch file JSON mode for cli_mini.py
        e["LEAN4_CLI_CMD"] = f"{lean4_cli} batch --input-file {{input_json}} --output-file {{output_json}}"
    return e


@app.command()
def run(
    pdf: Path = typer.Option(..., exists=True, file_okay=True, dir_okay=False, readable=True, help="Input PDF"),
    results: Path = typer.Option(Path("data/results/pipeline"), exists=False, file_okay=False, dir_okay=True, help="Results directory"),
    arango_db: str = typer.Option("pdf_knowledge_base_test", help="Dedicated ArangoDB database for this run"),
    session: Optional[str] = typer.Option(None, help="Optional fixed session id (defaults to timestamp)"),
    lean4_cli: Optional[str] = typer.Option("python /home/graham/workspace/experiments/lean4/src/lean4_prover/cli_mini.py", help="Path to Lean4 CLI (cli_mini.py)")
):
    """Run all stages 01→14 on the provided PDF."""
    results.mkdir(parents=True, exist_ok=True)
    sid = session or os.getenv("LITELLM_SESSION_ID") or datetime.now().strftime("%Y%m%d-%H%M%S")
    env = _ensure_env({}, results, arango_db, sid, lean4_cli)

    # Stage 01
    _run([sys.executable, "src/extractor/pipeline/steps/01_annotation_processor.py", "run", str(pdf), "-o", str(results)], env)
    # Discover clean PDF
    anno_dir = results / "01_annotation_processor"
    clean_candidates = sorted(anno_dir.glob("*_clean.pdf"))
    if not clean_candidates:
        raise FileNotFoundError("No *_clean.pdf produced by Stage 01")
    clean_pdf = clean_candidates[0]

    # Stage 02
    _run([sys.executable, "src/extractor/pipeline/steps/02_marker_extractor.py", "run", str(clean_pdf), "-o", str(results)], env)
    blocks_json = results / "02_marker_extractor" / "json_output" / "02_marker_blocks.json"

    # Stage 03
    _run([sys.executable, "src/extractor/pipeline/steps/03_suspicious_headers.py", "run", str(blocks_json), "--pdf-dir", str(anno_dir), "-o", str(results)], env)

    # Stage 04
    verified_json = results / "03_suspicious_headers" / "json_output" / "03_verified_blocks.json"
    _run([sys.executable, "src/extractor/pipeline/steps/04_section_builder.py", "run", str(verified_json), "--pdf-dir", str(anno_dir), "-o", str(results)], env)
    sections_json = results / "04_section_builder" / "json_output" / "04_sections.json"

    # Stage 05
    _run([sys.executable, "src/extractor/pipeline/steps/05_table_extractor.py", "run", str(sections_json), "--pdf-dir", str(anno_dir), "-o", str(results)], env)
    tables_json = results / "05_table_extractor" / "json_output" / "05_tables.json"

    # Stage 06
    _run([sys.executable, "src/extractor/pipeline/steps/06_figure_extractor.py", "run", str(blocks_json), "--sections", str(sections_json), "--pdf-dir", str(anno_dir), "-o", str(results)], env)
    figures_json = results / "06_figure_extractor" / "json_output" / "06_figures.json"

    # Stage 07 (full VLM mode; images included)
    _run([sys.executable, "src/extractor/pipeline/steps/07_reflow_section.py", "run", "--sections", str(sections_json), "--tables", str(tables_json), "--figures", str(figures_json), "-o", str(results)], env)
    reflow_json = results / "07_reflow_section" / "json_output" / "07_reflowed.json"

    # Stage 08 (full proving via Lean4 CLI)
    _run([sys.executable, "src/extractor/pipeline/steps/08_lean4_theorem_prover.py", "run", str(reflow_json), "-o", str(results)], env)
    theorems_json = results / "08_lean4_theorem_prover" / "json_output" / "08_theorems.json"

    # Stage 09
    _run([sys.executable, "src/extractor/pipeline/steps/09_section_summarizer.py", "run", str(reflow_json), "-o", str(results), "--max-concurrent", "2", "--window-size", "2", "--strict-json"], env)
    summaries_json = results / "09_section_summarizer" / "json_output" / "09_summaries.json"

    # Stage 10 (Arango export)
    _run([sys.executable, "src/extractor/pipeline/steps/10_arangodb_exporter.py", "run", "--reflowed", str(reflow_json), "--summaries", str(summaries_json), "-o", str(results)], env)
    flat_json = results / "10_arangodb_exporter" / "json_output" / "10_flattened_data.json"

    # Stage 11 (Graph)
    _run([sys.executable, "src/extractor/pipeline/steps/11_arango_create_graph.py", "run", str(flat_json), "-o", str(results)], env)

    # Stage 12 (Annotations → Arango)
    annotations_json = results / "01_annotation_processor" / "json_output" / "01_annotations.json"
    _run([sys.executable, "src/extractor/pipeline/steps/12_insert_annotations.py", "run", "--annotations", str(annotations_json), "-o", str(results)], env)

    # Stage 14 (Report)
    _run([sys.executable, "src/extractor/pipeline/steps/14_report_generator.py", "run", str(results)], env)

    print("\nAll stages completed. Final report:", results / "final_report.md")


if __name__ == "__main__":
    app()
