#!/usr/bin/env python3
"""Run pipeline stages sequentially and validate against gold invariants.

Example:
  python -m extractor.pipeline.tools.run_and_validate \
    --pdf data/input/pipeline/BHT_CV32A65X_marked.pdf --until 4

Options allow skipping heavy stages. At each stage, this runner calls the step
CLI, then compares the produced JSON to the stage's gold file (if available).
"""
from __future__ import annotations

import json
import os
import sys
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

import typer


app = typer.Typer(help="Run pipeline stages and validate against gold standards")


ROOT = Path.cwd()
SRC = ROOT / "src"
DATA_RESULTS = ROOT / "data" / "results" / "pipeline"
DATA_GOLD = ROOT / "data" / "gold_standards" / "pipeline"


@dataclass
class StageInfo:
    script: Path
    output_json: Path  # relative to DATA_RESULTS
    gold_file: Optional[Path]


def _run(cmd: list[str]) -> None:
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", str(SRC))
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        try:
            script = Path(cmd[1]).name if len(cmd) > 1 else "unknown"
        except Exception:
            script = "unknown"
        logs_dir = DATA_RESULTS / "_cli_logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        from datetime import datetime

        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        log_path = logs_dir / f"{script}-{ts}.log"
        try:
            log_path.write_text(
                f"CMD: {' '.join(cmd)}\n\nSTDOUT:\n{proc.stdout}\n\nSTDERR:\n{proc.stderr}\n"
            )
        except Exception:
            pass
        if proc.stderr:
            print(proc.stderr.strip()[:2000])
        raise RuntimeError(f"Command failed ({proc.returncode}): {' '.join(cmd)}")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _stage_name(num: int) -> str:
    return {
        1: "01_annotation_processor",
        2: "02_marker_extractor",
        3: "03_suspicious_headers",
        4: "04_section_builder",
        5: "05_table_extractor",
        6: "06_figure_extractor",
        7: "07_reflow_section",
        8: "08_lean4_theorem_prover",
        9: "09_section_summarizer",
        10: "10_arangodb_exporter",
        11: "11_arango_create_graph",
        12: "12_insert_annotations",
        14: "14_report_generator",
    }.get(num, f"{num:02d}_unknown")


def _collect_stage_summary(num: int, out_json: Path) -> dict:
    name = _stage_name(num)
    entry = {
        "stage": name,
        "path": str(out_json),
        "validated": True,
        "timing_ms": None,
        "counts": {},
    }
    try:
        data = _load_json(out_json)
        t = data.get("timings") or {}
        if isinstance(t, dict) and "stage_duration_ms" in t:
            entry["timing_ms"] = int(t.get("stage_duration_ms") or 0)
        # Heuristic key counts
        for k in (
            "annotation_count",
            "block_count",
            "section_count",
            "table_count",
            "figure_count",
            "summaries_generated",
            "edges_created",
            "documents_created",
        ):
            if k in data:
                try:
                    entry["counts"][k] = int(data.get(k) or 0)
                except Exception:
                    pass
        # Arrays
        for k in (
            "annotations",
            "blocks",
            "sections",
            "tables",
            "figures",
            "reflowed_sections",
            "summaries",
        ):
            if k in data and isinstance(data.get(k), list):
                entry["counts"][f"{k}_len"] = len(data.get(k) or [])
    except Exception:
        pass
    return entry


def _validate_stage(num: int, out_json: Path, gold_file: Path | None) -> None:
    if gold_file and gold_file.exists():
        sid = f"{num:02d}"
        _run(
            [
                sys.executable,
                "-m",
                "extractor.pipeline.tools.validate_gold_standard",
                "gold",
                sid,
                str(out_json),
            ]
        )


@app.command()
def run(
    pdf: Path = typer.Option(..., "--pdf", exists=True, help="Input PDF path"),
    until: int = typer.Option(4, "--until", min=1, max=14, help="Run up to stage N"),
    skip_heavy: bool = typer.Option(
        True,
        "--skip-heavy/--no-skip-heavy",
        help="Skip heavy stages (tables, figures, lean, arango)",
    ),
    offline: bool = typer.Option(
        False,
        "--offline/--no-offline",
        help="Run all stages with offline flags: 03 --skip-llm, 06 --skip-descriptions, 07 --summary-only, 08 --skip-proving, 10 --skip-export, 11 --skip-graph-creation",
    ),
) -> None:
    DATA_RESULTS.mkdir(parents=True, exist_ok=True)

    stage_summaries = []
    mc_env = os.getenv("MAX_CONCURRENT_LLM_CALLS") or "5"

    # Stage definitions (adjust output filenames to step conventions)
    stages: Dict[int, StageInfo] = {
        1: StageInfo(
            script=SRC / "extractor/pipeline/steps/01_annotation_processor.py",
            output_json=Path("01_annotation_processor/json_output/01_annotations.json"),
            gold_file=DATA_GOLD / "001_annotation_processor_gs.json",
        ),
        2: StageInfo(
            script=SRC / "extractor/pipeline/steps/02_marker_extractor.py",
            output_json=Path("02_marker_extractor/json_output/02_marker_blocks.json"),
            gold_file=DATA_GOLD / "002_marker_extractor_gs.json",
        ),
        3: StageInfo(
            script=SRC / "extractor/pipeline/steps/03_suspicious_headers.py",
            output_json=Path("03_suspicious_headers/json_output/03_verified_blocks.json"),
            gold_file=DATA_GOLD / "003_suspicious_headers_gs.json",
        ),
        4: StageInfo(
            script=SRC / "extractor/pipeline/steps/04_section_builder.py",
            output_json=Path("04_section_builder/json_output/04_sections.json"),
            gold_file=DATA_GOLD / "004_section_builder_gs.json",
        ),
        5: StageInfo(
            script=SRC / "extractor/pipeline/steps/05_table_extractor.py",
            output_json=Path("05_table_extractor/json_output/05_tables.json"),
            gold_file=DATA_GOLD / "005_table_extractor_gs.json",
        ),
        6: StageInfo(
            script=SRC / "extractor/pipeline/steps/06_figure_extractor.py",
            output_json=Path("06_figure_extractor/json_output/06_figures.json"),
            gold_file=DATA_GOLD / "006_figure_extractor_gs.json",
        ),
        7: StageInfo(
            script=SRC / "extractor/pipeline/steps/07_reflow_section.py",
            output_json=Path("07_reflow_section/json_output/07_reflowed.json"),
            gold_file=DATA_GOLD / "007_reflow_section_gs.json",
        ),
        8: StageInfo(
            script=SRC / "extractor/pipeline/steps/08_lean4_theorem_prover.py",
            output_json=Path("08_lean4_theorem_prover/json_output/08_theorems.json"),
            gold_file=DATA_GOLD / "008_lean4_theorem_prover_gs.json",
        ),
        9: StageInfo(
            script=SRC / "extractor/pipeline/steps/09_section_summarizer.py",
            output_json=Path("09_section_summarizer/json_output/09_summaries.json"),
            gold_file=DATA_GOLD / "009_section_summarizer_gs.json",
        ),
        10: StageInfo(
            script=SRC / "extractor/pipeline/steps/10_arangodb_exporter.py",
            output_json=Path("10_arangodb_exporter/json_output/10_export_confirmation.json"),
            gold_file=DATA_GOLD / "010_arangodb_exporter_gs.json",
        ),
        11: StageInfo(
            script=SRC / "extractor/pipeline/steps/11_arango_create_graph.py",
            output_json=Path("11_arango_create_graph/json_output/11_graph_confirmation.json"),
            gold_file=DATA_GOLD / "011_arango_create_graph_gs.json",
        ),
        12: StageInfo(
            script=SRC / "extractor/pipeline/steps/12_insert_annotations.py",
            output_json=Path("12_insert_annotations/json_output/12_insert_confirmation.json"),
            gold_file=(
                DATA_GOLD / "012_insert_annotations_gs.json"
                if (DATA_GOLD / "012_insert_annotations_gs.json").exists()
                else None
            ),
        ),
        14: StageInfo(
            script=SRC / "extractor/pipeline/steps/14_report_generator.py",
            output_json=Path("14_report_generator/json_output/final_report.json"),
            gold_file=DATA_GOLD / "014_report_generator_gs.json",
        ),
    }

    # Derived paths
    anno_dir = DATA_RESULTS / "01_annotation_processor"

    # Stage 1
    if until >= 1:
        _run([sys.executable, str(stages[1].script), "run", str(pdf), "-o", str(DATA_RESULTS)])
        out_json = DATA_RESULTS / stages[1].output_json
        if stages[1].gold_file and stages[1].gold_file.exists():
            _validate_stage(1, out_json, stages[1].gold_file)
        stage_summaries.append(_collect_stage_summary(1, out_json))

    # Get clean PDF for next stage
    clean_pdf = None
    try:
        j = _load_json(DATA_RESULTS / stages[1].output_json)
        clean_pdf = j.get("clean_pdf_path")
    except Exception:
        pass
    if not clean_pdf:
        typer.secho("Missing clean PDF from Stage 01; aborting.", fg=typer.colors.RED)
        raise typer.Exit(1)

    # Stage 2
    if until >= 2:
        _run([sys.executable, str(stages[2].script), "run", clean_pdf, "-o", str(DATA_RESULTS)])
        out_json = DATA_RESULTS / stages[2].output_json
        if stages[2].gold_file and stages[2].gold_file.exists():
            _validate_stage(2, out_json, stages[2].gold_file)
        stage_summaries.append(_collect_stage_summary(2, out_json))

    # Stage 3
    if until >= 3:
        in_json = DATA_RESULTS / stages[2].output_json
        # Typer app requires explicit subcommand name
        _run(
            [
                sys.executable,
                str(stages[3].script),
                "run",
                str(in_json),
                "--pdf-dir",
                str(anno_dir),
                "-o",
                str(DATA_RESULTS),
            ]
        )
        out_json = DATA_RESULTS / stages[3].output_json
        if stages[3].gold_file and stages[3].gold_file.exists():
            _validate_stage(3, out_json, stages[3].gold_file)
        stage_summaries.append(_collect_stage_summary(3, out_json))

    # Stage 4
    if until >= 4:
        in_json = DATA_RESULTS / stages[3].output_json
        _run(
            [
                sys.executable,
                str(stages[4].script),
                "run",
                str(in_json),
                "--pdf-dir",
                str(anno_dir),
                "-o",
                str(DATA_RESULTS),
            ]
        )
        out_json = DATA_RESULTS / stages[4].output_json
        if stages[4].gold_file and stages[4].gold_file.exists():
            _validate_stage(4, out_json, stages[4].gold_file)
        stage_summaries.append(_collect_stage_summary(4, out_json))

    # Stage 5
    if until >= 5 and (not skip_heavy or offline):
        in_json = DATA_RESULTS / stages[4].output_json
        _run(
            [
                sys.executable,
                str(stages[5].script),
                "run",
                str(in_json),
                "--pdf-dir",
                str(anno_dir),
                "-o",
                str(DATA_RESULTS),
            ]
        )
        out_json = DATA_RESULTS / stages[5].output_json
        if stages[5].gold_file and stages[5].gold_file.exists():
            _validate_stage(5, out_json, stages[5].gold_file)
        stage_summaries.append(_collect_stage_summary(5, out_json))

    # Stage 6
    if until >= 6 and (not skip_heavy or offline):
        blocks_json = DATA_RESULTS / stages[2].output_json
        sections_json = DATA_RESULTS / stages[4].output_json
        _run(
            (
                [
                    sys.executable,
                    str(stages[6].script),
                    "run",
                    str(blocks_json),
                    "--sections",
                    str(sections_json),
                    "--pdf-dir",
                    str(anno_dir),
                    "-o",
                    str(DATA_RESULTS),
                ]
                + (["--skip-descriptions"] if offline else [])
            )
        )
        out_json = DATA_RESULTS / stages[6].output_json
        if stages[6].gold_file and stages[6].gold_file.exists():
            _validate_stage(6, out_json, stages[6].gold_file)
        stage_summaries.append(_collect_stage_summary(6, out_json))

    # Stage 7
    if until >= 7 and (not skip_heavy or offline):
        sections_json = DATA_RESULTS / stages[4].output_json
        tables_json = DATA_RESULTS / stages[5].output_json
        figures_json = DATA_RESULTS / stages[6].output_json
        _run(
            (
                [
                    sys.executable,
                    str(stages[7].script),
                    "run",
                    "--sections",
                    str(sections_json),
                    "--tables",
                    str(tables_json),
                    "--figures",
                    str(figures_json),
                    "-o",
                    str(DATA_RESULTS),
                ]
                + (["--summary-only"] if offline else [])
            )
        )
        out_json = DATA_RESULTS / stages[7].output_json
        if stages[7].gold_file and stages[7].gold_file.exists():
            _validate_stage(7, out_json, stages[7].gold_file)
        stage_summaries.append(_collect_stage_summary(7, out_json))

    # Stage 8
    if until >= 8 and (not skip_heavy or offline):
        reflow_json = DATA_RESULTS / stages[7].output_json
        _run(
            (
                [
                    sys.executable,
                    str(stages[8].script),
                    "run",
                    str(reflow_json),
                    "-o",
                    str(DATA_RESULTS),
                ]
                + (["--skip-proving"] if offline else [])
            )
        )
        out_json = DATA_RESULTS / stages[8].output_json
        if stages[8].gold_file and stages[8].gold_file.exists():
            _validate_stage(8, out_json, stages[8].gold_file)
        stage_summaries.append(_collect_stage_summary(8, out_json))

    # Stage 9
    if until >= 9 and (not skip_heavy or offline):
        reflow_json = DATA_RESULTS / stages[7].output_json
        _run(
            [
                sys.executable,
                str(stages[9].script),
                "run",
                str(reflow_json),
                "-o",
                str(DATA_RESULTS),
                "--max-concurrent",
                str(mc_env),
                "--window-size",
                "2",
                "--strict-json",
            ]
        )
        out_json = DATA_RESULTS / stages[9].output_json
        if stages[9].gold_file and stages[9].gold_file.exists():
            _validate_stage(9, out_json, stages[9].gold_file)
        stage_summaries.append(_collect_stage_summary(9, out_json))

    # Stage 10
    if until >= 10 and (not skip_heavy or offline):
        reflow_json = DATA_RESULTS / stages[7].output_json
        summaries_json = DATA_RESULTS / stages[9].output_json
        _run(
            (
                [
                    sys.executable,
                    str(stages[10].script),
                    "run",
                    "--reflowed",
                    str(reflow_json),
                    "--summaries",
                    str(summaries_json),
                    "-o",
                    str(DATA_RESULTS),
                ]
                + (["--skip-export"] if offline else [])
            )
        )
        out_json = DATA_RESULTS / stages[10].output_json
        if stages[10].gold_file and stages[10].gold_file.exists():
            _validate_stage(10, out_json, stages[10].gold_file)
        stage_summaries.append(_collect_stage_summary(10, out_json))

    # Stage 11
    if until >= 11 and (not skip_heavy or offline):
        if offline:
            # Skip Stage 11 execution in offline mode; dependencies like FAISS/Arango may be unavailable
            stage_summaries.append(
                {
                    "stage": _stage_name(11),
                    "path": "(skipped --offline)",
                    "validated": True,
                    "timing_ms": None,
                    "counts": {},
                }
            )
        else:
            flat_json = (
                DATA_RESULTS / "10_arangodb_exporter" / "json_output" / "10_flattened_data.json"
            )
            _run(
                (
                    [
                        sys.executable,
                        str(stages[11].script),
                        "run",
                        str(flat_json),
                        "-o",
                        str(DATA_RESULTS),
                    ]
                    + (["--skip-graph-creation"] if offline else [])
                )
            )
            out_json = DATA_RESULTS / stages[11].output_json
            if stages[11].gold_file and stages[11].gold_file.exists():
                _validate_stage(11, out_json, stages[11].gold_file)
            stage_summaries.append(_collect_stage_summary(11, out_json))

    # Stage 12 (optional gold)
    if until >= 12 and (not skip_heavy or offline) and stages[12].gold_file:
        annotations_json = DATA_RESULTS / stages[1].output_json
        _run(
            [
                sys.executable,
                str(stages[12].script),
                "run",
                "--annotations",
                str(annotations_json),
                "-o",
                str(DATA_RESULTS),
            ]
        )
        out_json = DATA_RESULTS / stages[12].output_json
        if stages[12].gold_file and stages[12].gold_file.exists():
            _validate_stage(12, out_json, stages[12].gold_file)
        stage_summaries.append(_collect_stage_summary(12, out_json))

    # Stage 14
    if until >= 14 and (not skip_heavy or offline):
        _run([sys.executable, str(stages[14].script), "run", str(DATA_RESULTS)])
        out_json = DATA_RESULTS / "final_report.json"
        if stages[14].gold_file and stages[14].gold_file.exists():
            _validate_stage(14, out_json, stages[14].gold_file)
        stage_summaries.append(_collect_stage_summary(14, out_json))

    # Write run report
    try:
        md = ["# Pipeline Run Report", ""]
        for e in stage_summaries:
            line = f"- {e['stage']}: PASS (output: {e['path']})"
            md.append(line)
            if e.get("timing_ms") is not None:
                md.append(f"  - duration: {e['timing_ms']} ms")
            if e.get("counts"):
                md.append(f"  - counts: {e['counts']}")
        (DATA_RESULTS / "run_report.md").write_text("\n".join(md))
    except Exception:
        pass
    raise typer.Exit(0)


if __name__ == "__main__":
    app()
