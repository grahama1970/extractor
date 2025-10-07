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
from typing import Optional, Dict, Any, List
import shutil

import typer
from rich.console import Console

from extractor.pipeline.utils.metrics_logger import log_metric
from extractor.pipeline.tools.reqif_export import export_reqif
from extractor.pipeline.utils.mode import deterministic_mode, init_deterministic_seeds

console = Console()


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
        artifacts = Path("scripts/artifacts")
        artifacts.mkdir(parents=True, exist_ok=True)
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
    *,
    deterministic_lean4: bool = False,
    no_llm_lean4: bool = False,
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
    # Lean4 CLI (full proving) or stub (offline)
    use_stub = e.get("LEAN4_STUB", "").lower() in {"1", "true", "yes", "y"}
    cli_exists = False
    if lean4_cli:
        try:
            cli_exists = Path(str(lean4_cli).split()[0]).exists()
        except Exception:
            cli_exists = False
    if use_stub or not cli_exists:
        cli_cmd = f"{sys.executable} -m extractor.pipeline.tools.lean4_stub_cli batch --input-file {{input_json}} --output-file {{output_json}}"
    else:
        cli_cmd = f"{lean4_cli} batch --input-file {{input_json}} --output-file {{output_json}}"
    if deterministic_lean4 and "--deterministic" not in cli_cmd:
        cli_cmd = f"{cli_cmd} --deterministic"
    if no_llm_lean4 and "--no-llm" not in cli_cmd:
        cli_cmd = f"{cli_cmd} --no-llm"
    e["LEAN4_CLI_CMD"] = cli_cmd
    # Default rationale model to default LLM when not set
    if not e.get("GRAPH_RATIONALE_MODEL"):
        e["GRAPH_RATIONALE_MODEL"] = (
            e.get("LITELLM_DEFAULT_MODEL")
            or e.get("DEFAULT_LITELLM_MODEL")
            or e.get("LITELLM_MODEL", "")
        )
    return e


def build_cli() -> typer.Typer:
    app = typer.Typer(help="Run all pipeline stages end-to-end")

    def _preflight_strict() -> None:
        strict = os.getenv("OFFLINE_PDF_PREDICTORS", "1").lower() in {"0", "false"}
        if not strict:
            return
        try:
            from extractor.core.models import create_model_dict
            m = create_model_dict()
            required = [
                "detection_model",
                "layout_model",
                "ocr_error_model",
                "recognition_model",
                "table_rec_model",
            ]
            missing = [k for k in required if k not in m or m.get(k) is None]
            if missing:
                console.print("[red]Strict mode: missing predictors -> " + ", ".join(missing) + "[/red]")
                console.print("[yellow]Hint: activate venv and run: `uv sync --extra accurate`[/yellow]")
                raise typer.Exit(1)
        except Exception as e:
            console.print(f"[red]Strict mode preflight failed: {e}[/red]")
            console.print("[yellow]Hint: `uv sync --extra accurate`[/yellow]")
            raise typer.Exit(1)

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
        resume: bool = typer.Option(
            False,
            "--resume/--no-resume",
            help="Skip stages that already have outputs recorded in pipeline_manifest.json",
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
        skip_tables05: bool = typer.Option(
            False, "--skip-tables05/--no-skip-tables05", help="Stage 05: skip table extraction"
        ),
        skip_figures06: bool = typer.Option(
            False, "--skip-figures06/--no-skip-figures06", help="Stage 06: skip figure extraction"
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
        _preflight_strict()
        # Log and seed deterministic mode early (informational; stages are separate procs)
        if deterministic_mode():
            init_deterministic_seeds("run_all")
            console.print("[cyan]Deterministic mode active (PIPELINE_DETERMINISTIC=1).[/cyan]")
        if os.getenv("OFFLINE_PDF_PREDICTORS", "1").lower() not in {"0","false"}:
            console.print("[cyan]INFO:[/cyan] Running in predictor lenient mode (OFFLINE_PDF_PREDICTORS=1). Set OFFLINE_PDF_PREDICTORS=0 for strict checks.")
        # Deprecation notice: prefer the unified surface
        try:
            import typer as _ty
            _ty.secho(
                "[deprecated] Prefer 'pipeline-run --mode accurate' for the Happy Path.",
                fg=_ty.colors.YELLOW,
            )
        except Exception:
            pass
        results.mkdir(parents=True, exist_ok=True)
        pipeline_start = time.monotonic()
        sid = session or os.getenv("LITELLM_SESSION_ID") or datetime.now().strftime("%Y%m%d-%H%M%S")
        ci_mode = os.getenv("CI", "").lower() in {"1", "true", "yes", "on"}
        env = _ensure_env(
            {},
            results,
            arango_db,
            sid,
            lean4_cli,
            deterministic_lean4=offline or ci_mode,
            no_llm_lean4=offline,
        )
        return _run_pipeline_core(
            pdf=pdf,
            results=results,
            arango_db=arango_db,
            sid=sid,
            env=env,
            resume=resume,
            offline=offline,
            skip_llm03=skip_llm03,
            skip_descriptions06=skip_descriptions06,
            summary_only07=summary_only07,
            skip_tables05=skip_tables05,
            skip_figures06=skip_figures06,
            skip_proving08=skip_proving08,
            skip_export10=skip_export10,
            skip_embeddings10=skip_embeddings10,
            fast_embeddings10=fast_embeddings10,
            skip_graph11=skip_graph11,
            validate=validate,
            annotations_json=annotations_json,
            clean_pdf=clean_pdf,
            pipeline_start=pipeline_start,
        )

    def _run_pipeline_core(
        *,
        pdf: Path,
        results: Path,
        arango_db: str,
        sid: str,
        env: dict[str, str],
        resume: bool,
        offline: bool,
        skip_llm03: bool,
        skip_descriptions06: bool,
        summary_only07: bool,
        skip_tables05: bool,
        skip_figures06: bool,
        skip_proving08: bool,
        skip_export10: bool,
        skip_embeddings10: bool,
        fast_embeddings10: bool,
        skip_graph11: bool,
        validate: bool,
        annotations_json: Optional[Path],
        clean_pdf: Optional[Path],
        pipeline_start: float,
        ) -> None:
        manifest_path = results / "pipeline_manifest.json"
        manifest: Dict[str, Any] = {}
        if resume and manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text())
            except Exception:
                manifest = {}

        def stage_completed(stage_name: str, outputs: list[Path]) -> bool:
            entry = manifest.get(stage_name)
            if not entry:
                return False
            for p in outputs:
                if not p.exists():
                    return False
            return True

        def record_stage(stage_name: str, outputs: list[Path]) -> None:
            manifest[stage_name] = {
                "completed_at": datetime.now().isoformat(),
                "outputs": [str(p) for p in outputs],
            }
            try:
                manifest_path.write_text(
                    json.dumps(manifest, indent=2, ensure_ascii=False)
                )
            except Exception:
                pass

    # End of internal helpers; return CLI app now.
    
    return app


if __name__ == "__main__":
    # Enable direct execution: python -m extractor.pipeline.run_all --pdf ...
    build_cli()()

    # Stage 02
    stage02_name = "02_marker_extractor"
    blocks_json = results / stage02_name / "json_output" / "02_marker_blocks.json"
    if resume and stage_completed(stage02_name, [blocks_json]):
        console.print(f"[yellow]Skipping {stage02_name} (resume)\[/yellow]")
    else:
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
            stage_name=stage02_name,
        )
        if validate:
            _validate_output("02", blocks_json)
        record_stage(stage02_name, [blocks_json])

    # Stage 03
    stage03_name = "03_suspicious_headers"
    verified_json = results / stage03_name / "json_output" / "03_verified_blocks.json"
    if resume and stage_completed(stage03_name, [verified_json]):
        console.print(f"[yellow]Skipping {stage03_name} (resume)\[/yellow]")
    else:
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
            stage_name=stage03_name,
        )
        if validate:
            _validate_output("03", verified_json)
        record_stage(stage03_name, [verified_json])

    # Stage 04
    stage04_name = "04_section_builder"
    sections_json = results / stage04_name / "json_output" / "04_sections.json"
    if resume and stage_completed(stage04_name, [sections_json]):
        console.print(f"[yellow]Skipping {stage04_name} (resume)\[/yellow]")
    else:
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
            stage_name=stage04_name,
        )
        if validate:
            _validate_output("04", sections_json)
        record_stage(stage04_name, [sections_json])

    # Stage 05
    stage05_name = "05_table_extractor"
    tj_dir = results / stage05_name / "json_output"
    tables_json = tj_dir / "05_tables.json"
    if resume and stage_completed(stage05_name, [tables_json]):
        console.print(f"[yellow]Skipping {stage05_name} (resume)\[/yellow]")
    elif skip_tables05:
        tj_dir.mkdir(parents=True, exist_ok=True)
        tables_json.write_text(json.dumps({"tables": []}, indent=2))
        record_stage(stage05_name, [tables_json])
    else:
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
            stage_name=stage05_name,
        )
        if validate:
            _validate_output("05", tables_json)
        record_stage(stage05_name, [tables_json])

    # Stage 06
    stage06_name = "06_figure_extractor"
    fj_dir = results / stage06_name / "json_output"
    figures_json = fj_dir / "06_figures.json"
    if resume and stage_completed(stage06_name, [figures_json]):
        console.print(f"[yellow]Skipping {stage06_name} (resume)\[/yellow]")
    elif skip_figures06:
        fj_dir.mkdir(parents=True, exist_ok=True)
        figures_json.write_text(json.dumps({"figures": []}, indent=2))
        record_stage(stage06_name, [figures_json])
    else:
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
            stage_name=stage06_name,
        )
        if validate:
            _validate_output("06", figures_json)
        record_stage(stage06_name, [figures_json])

    # Stage 07 (full VLM mode; images included)
    stage07_name = "07_reflow_section"
    reflow_json = results / stage07_name / "json_output" / "07_reflowed.json"
    if resume and stage_completed(stage07_name, [reflow_json]):
        console.print(f"[yellow]Skipping {stage07_name} (resume)\[/yellow]")
    else:
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
            stage_name=stage07_name,
        )
        if validate:
            _validate_output("07", reflow_json)
        record_stage(stage07_name, [reflow_json])

    # Stage 07½ — Requirements Miner (deterministic, offline-friendly)
    stage07r_name = "07_requirements_miner"
    req_dir = results / stage07r_name / "json_output"
    req_json = req_dir / "07_requirements.json"
    if resume and stage_completed(stage07r_name, [req_json]):
        console.print(f"[yellow]Skipping {stage07r_name} (resume)\[/yellow]")
    elif os.getenv("STAGE07_REQUIREMENTS_MINER", "1").lower() in {"1","true","yes","y"}:
        _run(
            [
                sys.executable,
                "src/extractor/pipeline/steps/07_requirements_miner.py",
                str(reflow_json),
                "-o",
                str(results),
            ],
            env,
            stage_name=stage07r_name,
        )
        record_stage(stage07r_name, [req_json])

    # Stage 08 (full proving via Lean4 CLI)
    # Allow explicit --prove08 to override offline skipping
    force_prove = (not skip_proving08) or os.getenv("FORCE_PROVE08", "").lower() in {"1", "true", "yes", "y"}
    skip_proving_effective = (skip_proving08 or offline) and not force_prove
    stage08_name = "08_lean4_theorem_prover"
    _theorems_json = results / stage08_name / "json_output" / "08_theorems.json"
    if resume and stage_completed(stage08_name, [_theorems_json]):
        console.print(f"[yellow]Skipping {stage08_name} (resume)\[/yellow]")
    else:
        _run(
            [
                sys.executable,
                "src/extractor/pipeline/steps/08_lean4_theorem_prover.py",
                "run",
                str(reflow_json),
                "-o",
                str(results),
                *( ["--skip-proving"] if skip_proving_effective else [] ),
            ],
            env,
            stage_name=stage08_name,
        )
        record_stage(stage08_name, [_theorems_json])
    # Ensure enriched requirements JSON exists for UX and Stage 14 summaries
    try:
        enr_dir = results / stage08_name / "json_output"
        enr_json = enr_dir / "08_requirements_enriched.json"
        if not enr_json.exists() and req_json.exists():
            req = json.loads(req_json.read_text())
            enriched = {
                "requirements": [
                    {
                        **r,
                        "status": "unproved" if not skip_proving_effective else "new",
                        "compile_log": "",
                        "formalization": None,
                        "diagnostics": [],
                    }
                    for r in (req.get("requirements") or [])
                ]
            }
            enr_dir.mkdir(parents=True, exist_ok=True)
            enr_json.write_text(json.dumps(enriched, indent=2))
            current_outputs = manifest.get(stage08_name, {}).get("outputs", [])
            if str(enr_json) not in current_outputs:
                record_stage(stage08_name, [p for p in [_theorems_json, enr_json] if p.exists()])
    except Exception as e:
        console.print(f"[yellow]Stage 08 enrichment synthesis warning: {e}\[/yellow]")

    # Stage 09
    stage09_name = "09_section_summarizer"
    summaries_json = results / stage09_name / "json_output" / "09_summaries.json"
    if resume and stage_completed(stage09_name, [summaries_json]):
        console.print(f"[yellow]Skipping {stage09_name} (resume)\[/yellow]")
    else:
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
            stage_name=stage09_name,
        )
        record_stage(stage09_name, [summaries_json])
    summaries_json = results / "09_section_summarizer" / "json_output" / "09_summaries.json"
    if validate:
        _validate_output("09", summaries_json)

    # Stage 10 (Arango export)
    stage10_name = "10_arangodb_exporter"
    flat_json = results / stage10_name / "json_output" / "10_flattened_data.json"
    confirm_json = results / stage10_name / "json_output" / "10_export_confirmation.json"
    stage10_outputs: List[Path] = [flat_json, confirm_json]
    if resume and stage_completed(stage10_name, stage10_outputs):
        console.print(f"[yellow]Skipping {stage10_name} (resume)\[/yellow]")
    else:
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
                *( ["--skip-export"] if (skip_export10 or (offline and not (os.getenv("ARANGO_PASS") or os.getenv("ARANGO_PASSWORD")))) else [] ),
                *( ["--skip-embeddings"] if (skip_embeddings10 or offline) else [] ),
                *( ["--fast-embeddings"] if fast_embeddings10 else [] ),
            ],
            env,
            stage_name=stage10_name,
        )
        if validate and confirm_json.exists():
            _validate_output("10", confirm_json)
        record_stage(stage10_name, [p for p in stage10_outputs if p.exists()])

    # ReqIF export (v0)
    reqif_path = results / stage10_name / "artifacts" / "10_requirements.reqif"
    if flat_json.exists() and not (skip_export10 or offline):
        try:
            export_reqif(flat_json, reqif_path)
            current_outputs = manifest.get(stage10_name, {}).get("outputs", [])
            if str(reqif_path) not in current_outputs:
                outputs = [flat_json, confirm_json, reqif_path]
                record_stage(stage10_name, [p for p in outputs if isinstance(p, Path) and p.exists()])
        except Exception as e:
            console.print(f"[red]ReqIF export failed:[/red] {e}")

    # Stage 11 (Graph)
    stage11_name = "11_arango_create_graph"
    graph_confirm = results / stage11_name / "json_output" / "11_graph_confirmation.json"
    if resume and stage_completed(stage11_name, [graph_confirm]):
        console.print(f"[yellow]Skipping {stage11_name} (resume)\[/yellow]")
    else:
        _run(
            [
                sys.executable,
                "src/extractor/pipeline/steps/11_arango_create_graph.py",
                "run",
                str(flat_json),
                "-o",
                str(results),
                *( ["--skip-graph-creation"] if (skip_graph11 or (offline and not (os.getenv("ARANGO_PASS") or os.getenv("ARANGO_PASSWORD")))) else [] ),
            ],
            env,
            stage_name=stage11_name,
        )
        if validate and graph_confirm.exists():
            _validate_output("11", graph_confirm)
        record_stage(stage11_name, [graph_confirm] if graph_confirm.exists() else [])

    # Stage 12 (Annotations → Arango)
    annotations_json = results / "01_annotation_processor" / "json_output" / "01_annotations.json"
    stage12_name = "12_insert_annotations"
    if resume and stage_completed(stage12_name, []):
        console.print(f"[yellow]Skipping {stage12_name} (resume)\[/yellow]")
    else:
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
            stage_name=stage12_name,
        )
        record_stage(stage12_name, [])
    # Stage 12: DB action only (no gold)

    # Stage 14 (Report)
    stage14_name = "14_report_generator"
    final_json = results / "final_report.json"
    final_md = results / "final_report.md"
    if resume and stage_completed(stage14_name, [final_json, final_md]):
        console.print(f"[yellow]Skipping {stage14_name} (resume)\[/yellow]")
    else:
        _run(
            [
                sys.executable,
                "src/extractor/pipeline/steps/14_report_generator.py",
                "run",
                str(results),
            ],
            env,
            stage_name=stage14_name,
        )
        if validate and final_json.exists():
            _validate_output("14", final_json)
        record_stage(stage14_name, [p for p in [final_json, final_md] if p.exists()])

    print("\nAll stages completed. Final report:", results / "final_report.md")
    # Surface Stage 02 fallback predictor mode if present
    try:
        s02_path = results / "02_marker_extractor" / "json_output" / "02_marker_blocks.json"
        if s02_path.exists():
            data = json.loads(s02_path.read_text())
            if data.get("fallback_mode"):
                missing = [k for k,v in (data.get("predictors_present") or {}).items() if not v]
                console.print(f"[yellow]Stage 02 ran in fallback mode; missing predictors: {', '.join(missing)}[/yellow]")
    except Exception:
        pass
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

    # end run()
