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
import time
from pathlib import Path
from datetime import datetime
from typing import Optional
import shutil

import typer

from extractor.pipeline.utils.metrics_logger import log_metric
from typing import Any as _Any

app = typer.Typer(help="Run all pipeline stages end-to-end")


def _run(cmd: list[str], env: dict[str, str], stage_name: str) -> None:
    start = time.monotonic()
    try:
        proc = subprocess.run(cmd, env=env)
        duration_ms = int((time.monotonic() - start) * 1000)
        if proc.returncode != 0:
            log_metric(
                stage_name,
                {
                    "success": False,
                    "return_code": proc.returncode,
                    "duration_ms": duration_ms,
                    "command": cmd,
                },
            )
            raise RuntimeError(f"Command failed ({proc.returncode}): {' '.join(cmd)}")
        log_metric(
            stage_name,
            {
                "success": True,
                "duration_ms": duration_ms,
                "command": cmd,
            },
        )
    except Exception as exc:
        if "duration_ms" not in locals():
            duration_ms = int((time.monotonic() - start) * 1000)
            log_metric(
                stage_name,
                {
                    "success": False,
                    "duration_ms": duration_ms,
                    "error": str(exc),
                    "command": cmd,
                },
            )
        raise


def _validate_output(stage_id: str, path: Path) -> None:
    try:
        from extractor.pipeline.tools import validate_gold_standard as vgs

        data = json.loads(Path(path).read_text())
        gs_dir = vgs._gs_dir()
        gs_file = vgs.STAGE_TO_GS.get(stage_id)
        if not gs_file:
            typer.secho(f"[validate] No GS mapping for stage {stage_id}", fg=typer.colors.YELLOW)
            return
        gold = json.loads((gs_dir / gs_file).read_text())
        ok, report = vgs.compare_against_gs_invariants(stage_id, data, gold)
        artifacts = Path("scripts/artifacts"); artifacts.mkdir(parents=True, exist_ok=True)
        (artifacts / f"validate_stage_{stage_id}.json").write_text(json.dumps(report, indent=2))
        if not ok:
            raise RuntimeError(f"gold invariants failed for stage {stage_id}")
        typer.secho(f"[validate] Stage {stage_id} passed gold invariants.", fg=typer.colors.GREEN)
    except Exception as e:
        typer.secho(f"[validate] Stage {stage_id} failed: {e}", fg=typer.colors.RED)
        raise


def _ensure_env(
    base_env: dict[str, str],
    results_dir: Path,
    arango_db: str,
    session_id: Optional[str],
    lean4_cli: Optional[str],
) -> dict[str, str]:
    e = os.environ.copy()
    e.update(base_env)
    # Ensure PYTHONPATH points to the repo's src directory regardless of cwd
    try:
        src_dir = Path(__file__).resolve().parents[2]
    except Exception:
        src_dir = Path.cwd() / "src"
    e["PYTHONPATH"] = str(src_dir)
    # Session + provider attachment
    if session_id:
        e["LITELLM_SESSION_ID"] = session_id
        e.setdefault("LITELLM_CACHE_NAMESPACE", session_id)
    e.setdefault("LITELLM_ATTACH_SESSION", "true")
    e.setdefault("STAGE07_TRIM_CHARS", os.getenv("STAGE07_TRIM_CHARS", "6000"))
    # Arango test DB
    if arango_db:
        e["ARANGO_DATABASE"] = arango_db
    # Lean4 CLI (full proving)
    if lean4_cli:
        # Prefer batch file JSON mode for cli_mini.py
        e["LEAN4_CLI_CMD"] = (
            f"{lean4_cli} batch --input-file {{input_json}} --output-file {{output_json}}"
        )
    # Default rationale model to default LLM when not set
    if not e.get("GRAPH_RATIONALE_MODEL"):
        e["GRAPH_RATIONALE_MODEL"] = (
            e.get("LITELLM_DEFAULT_MODEL")
            or e.get("DEFAULT_LITELLM_MODEL")
            or e.get("LITELLM_MODEL", "")
        )
    return e


@app.command()
def run(
    pdf: Path = typer.Option(
        ..., exists=True, file_okay=True, dir_okay=False, readable=True, help="Input PDF"
    ),
    results: Path = typer.Option(
        Path("data/results/pipeline"),
        exists=False,
        file_okay=False,
        dir_okay=True,
        help="Results directory",
    ),
    arango_db: str = typer.Option(
        "pdf_knowledge_base_test", help="Dedicated ArangoDB database for this run"
    ),
    session: Optional[str] = typer.Option(
        None, help="Optional fixed session id (defaults to timestamp)"
    ),
    lean4_cli: Optional[str] = typer.Option(
        "python /home/graham/workspace/experiments/lean4/src/lean4_prover/cli_mini.py",
        help="Path to Lean4 CLI (cli_mini.py)",
    ),
    # Offline/skip toggles per stage
    offline: bool = typer.Option(
        False,
        "--offline/--no-offline",
        help="Run with offline-friendly flags across stages (skips LLM/DB/heavy ops)",
    ),
    skip_llm03: bool = typer.Option(
        False, "--skip-llm03/--no-skip-llm03", help="Stage 03: skip vision LLM verification"
    ),
    skip_descriptions06: bool = typer.Option(
        False,
        "--skip-descriptions06/--no-skip-descriptions06",
        help="Stage 06: skip LLM descriptions for figures",
    ),
    summary_only07: bool = typer.Option(
        False, "--summary-only07/--full07", help="Stage 07: summary-only (no VLM merge)"
    ),
    skip_proving08: bool = typer.Option(
        False, "--skip-proving08/--prove08", help="Stage 08: skip proving"
    ),
    skip_export10: bool = typer.Option(
        False, "--skip-export10/--no-skip-export10", help="Stage 10: skip Arango export"
    ),
    skip_embeddings10: bool = typer.Option(
        False,
        "--skip-embeddings10/--no-skip-embeddings10",
        help="Stage 10: skip embedding computation",
    ),
    fast_embeddings10: bool = typer.Option(
        False,
        "--fast-embeddings10/--no-fast-embeddings10",
        help="Stage 10: use deterministic 8D hash embeddings",
    ),
    skip_graph11: bool = typer.Option(
        False, "--skip-graph11/--no-skip-graph11", help="Stage 11: write edges JSON only"
    ),
    validate: bool = typer.Option(
        False, "--validate/--no-validate", help="Validate stages against gold invariants"
    ),
    annotations_json: Optional[Path] = typer.Option(
        None,
        "--annotations-json",
        help="External annotations JSON (skip Stage 01 and use this file)",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    clean_pdf: Optional[Path] = typer.Option(
        None,
        "--clean-pdf",
        help="External clean PDF path to use with --annotations-json",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
):
    """Run all stages 01→14 on the provided PDF."""
    results.mkdir(parents=True, exist_ok=True)
    pipeline_start = time.monotonic()
    sid = session or os.getenv("LITELLM_SESSION_ID") or datetime.now().strftime("%Y%m%d-%H%M%S")
    env = _ensure_env({}, results, arango_db, sid, lean4_cli)

    # Stage 01 (or external annotations path)
    anno_dir = results / "01_annotation_processor"
    json_dir = anno_dir / "json_output"
    if annotations_json is not None:
        anno_dir.mkdir(parents=True, exist_ok=True)
        json_dir.mkdir(exist_ok=True)
        # Write annotations JSON into canonical location
        dest_anno = json_dir / "01_annotations.json"
        try:
            shutil.copyfile(str(annotations_json), str(dest_anno))
        except Exception as e:
            raise RuntimeError(f"Failed to stage annotations JSON: {e}")
        # Prepare clean PDF
        if clean_pdf is not None:
            staged_clean = anno_dir / f"{pdf.stem}_clean.pdf"
            try:
                shutil.copyfile(str(clean_pdf), str(staged_clean))
            except Exception as e:
                raise RuntimeError(f"Failed to stage clean PDF: {e}")
            effective_clean_pdf = staged_clean
        else:
            # Phase-1 cleaner: copy original to *_clean.pdf
            staged_clean = anno_dir / f"{pdf.stem}_clean.pdf"
            try:
                shutil.copyfile(str(pdf), str(staged_clean))
            except Exception as e:
                raise RuntimeError(f"Failed to copy original PDF as clean: {e}")
            effective_clean_pdf = staged_clean
        if validate:
            _validate_output("01", dest_anno)
    else:
        _run(
            [
                sys.executable,
                "src/extractor/pipeline/steps/01_annotation_processor.py",
                "run",
                str(pdf),
                "-o",
                str(results),
            ],
            env,
            stage_name="01_annotation_processor",
        )
        if validate:
            _validate_output("01", json_dir / "01_annotations.json")
        clean_candidates = sorted(anno_dir.glob("*_clean.pdf"))
        if not clean_candidates:
            raise FileNotFoundError("No *_clean.pdf produced by Stage 01")
        effective_clean_pdf = clean_candidates[0]

    # Stage 02
    _run(
        [
            sys.executable,
            "src/extractor/pipeline/steps/02_marker_extractor.py",
            "run",
            str(effective_clean_pdf),
            "--no-spawn",
            "-o",
            str(results),
        ],
        env,
        stage_name="02_marker_extractor",
    )
    if validate:
        _validate_output("02", results / "02_marker_extractor" / "json_output" / "02_marker_blocks.json")
    blocks_json = results / "02_marker_extractor" / "json_output" / "02_marker_blocks.json"

    # Stage 03
    _run(
        [
            sys.executable,
            "src/extractor/pipeline/steps/03_suspicious_headers.py",
            "run",
            str(blocks_json),
            "--pdf-dir",
            str(anno_dir),
            "-o",
            str(results),
            *( ["--skip-llm"] if (skip_llm03 or offline) else [] ),
        ],
        env,
        stage_name="03_suspicious_headers",
    )
    if validate:
        _validate_output("03", results / "03_suspicious_headers" / "json_output" / "03_verified_blocks.json")

    # Stage 04
    verified_json = results / "03_suspicious_headers" / "json_output" / "03_verified_blocks.json"
    _run(
        [
            sys.executable,
            "src/extractor/pipeline/steps/04_section_builder.py",
            "run",
            str(verified_json),
            "--pdf-dir",
            str(anno_dir),
            "-o",
            str(results),
        ],
        env,
        stage_name="04_section_builder",
    )
    sections_json = results / "04_section_builder" / "json_output" / "04_sections.json"
    if validate:
        _validate_output("04", sections_json)

    # Stage 05
    _run(
        [
            sys.executable,
            "src/extractor/pipeline/steps/05_table_extractor.py",
            "run",
            str(sections_json),
            "--pdf-dir",
            str(anno_dir),
            "-o",
            str(results),
        ],
        env,
        stage_name="05_table_extractor",
    )
    if validate:
        _validate_output("05", results / "05_table_extractor" / "json_output" / "05_tables.json")
    tables_json = results / "05_table_extractor" / "json_output" / "05_tables.json"

    # Stage 06
    _run(
        [
            sys.executable,
            "src/extractor/pipeline/steps/06_figure_extractor.py",
            "run",
            str(blocks_json),
            "--sections",
            str(sections_json),
            "--pdf-dir",
            str(anno_dir),
            "-o",
            str(results),
            *( ["--skip-descriptions"] if (skip_descriptions06 or offline) else [] ),
        ],
        env,
        stage_name="06_figure_extractor",
    )
    figures_json = results / "06_figure_extractor" / "json_output" / "06_figures.json"
    if validate:
        _validate_output("06", figures_json)

    # Stage 07 (full VLM mode; images included)
    _run(
        [
            sys.executable,
            "src/extractor/pipeline/steps/07_reflow_section.py",
            "run",
            "--sections",
            str(sections_json),
            "--tables",
            str(tables_json),
            "--figures",
            str(figures_json),
            "--timeout",
            os.getenv("STAGE07_TIMEOUT", "120"),
            "--allow-fallback",
            "-o",
            str(results),
            *( ["--summary-only"] if (summary_only07 or offline) else [] ),
        ],
        env,
        stage_name="07_reflow_section",
    )
    reflow_json = results / "07_reflow_section" / "json_output" / "07_reflowed.json"
    if validate:
        _validate_output("07", reflow_json)

    # Stage 08 (full proving via Lean4 CLI)
    _run(
        [
            sys.executable,
            "src/extractor/pipeline/steps/08_lean4_theorem_prover.py",
            "run",
            str(reflow_json),
            "-o",
            str(results),
            *( ["--skip-proving"] if (skip_proving08 or offline) else [] ),
        ],
        env,
        stage_name="08_lean4_theorem_prover",
    )
    theorems_json = results / "08_lean4_theorem_prover" / "json_output" / "08_theorems.json"
    # Stage 08 has no invariant file; skip

    # Stage 09
    _run(
        [
            sys.executable,
            "src/extractor/pipeline/steps/09_section_summarizer.py",
            "run",
            str(reflow_json),
            "-o",
            str(results),
            "--max-concurrent",
            "2",
            "--window-size",
            "2",
            "--strict-json",
        ],
        env,
        stage_name="09_section_summarizer",
    )
    summaries_json = results / "09_section_summarizer" / "json_output" / "09_summaries.json"
    if validate:
        _validate_output("09", summaries_json)

    # Stage 10 (Arango export)
    _run(
        [
            sys.executable,
            "src/extractor/pipeline/steps/10_arangodb_exporter.py",
            "run",
            "--reflowed",
            str(reflow_json),
            "--summaries",
            str(summaries_json),
            "-o",
            str(results),
            *( ["--skip-export"] if (skip_export10 or offline) else [] ),
            *( ["--skip-embeddings"] if (skip_embeddings10 or offline) else [] ),
            *( ["--fast-embeddings"] if fast_embeddings10 else [] ),
        ],
        env,
        stage_name="10_arangodb_exporter",
    )
    flat_json = results / "10_arangodb_exporter" / "json_output" / "10_flattened_data.json"
    if validate:
        # Confirm export confirmation structure rather than flattened data
        _validate_output("10", results / "10_arangodb_exporter" / "json_output" / "10_export_confirmation.json")

    # Stage 11 (Graph)
    _run(
        [
            sys.executable,
            "src/extractor/pipeline/steps/11_arango_create_graph.py",
            "run",
            str(flat_json),
            "-o",
            str(results),
            *( ["--skip-graph-creation"] if (skip_graph11 or offline) else [] ),
        ],
        env,
        stage_name="11_arango_create_graph",
    )
    if validate:
        _validate_output("11", results / "11_arango_create_graph" / "json_output" / "11_graph_confirmation.json")

    # Stage 12 (Annotations → Arango)
    annotations_json = results / "01_annotation_processor" / "json_output" / "01_annotations.json"
    _run(
        [
            sys.executable,
            "src/extractor/pipeline/steps/12_insert_annotations.py",
            "run",
            "--annotations",
            str(annotations_json),
            "-o",
            str(results),
        ],
        env,
        stage_name="12_insert_annotations",
    )
    # Stage 12: DB action only (no gold)

    # Stage 14 (Report)
    _run(
        [
            sys.executable,
            "src/extractor/pipeline/steps/14_report_generator.py",
            "run",
            str(results),
        ],
        env,
        stage_name="14_report_generator",
    )
    if validate:
        _validate_output("14", results / "final_report.json")

    print("\nAll stages completed. Final report:", results / "final_report.md")
    log_metric(
        "pipeline_run",
        {
            "success": True,
            "duration_ms": int((time.monotonic() - pipeline_start) * 1000),
            "session_id": sid,
            "pdf": str(pdf),
            "results_dir": str(results),
        },
    )


if __name__ == "__main__":
    app()
