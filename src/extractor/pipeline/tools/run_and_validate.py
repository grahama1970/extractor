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

from .compare_to_gold import run as compare_cli  # for reference; we invoke via subprocess for isolation

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
    proc = subprocess.run(cmd, env=env)
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed ({proc.returncode}): {' '.join(cmd)}")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


@app.command()
def run(
    pdf: Path = typer.Option(..., "--pdf", exists=True, help="Input PDF path"),
    until: int = typer.Option(4, "--until", min=1, max=14, help="Run up to stage N"),
    skip_heavy: bool = typer.Option(True, "--skip-heavy/--no-skip-heavy", help="Skip heavy stages (tables, figures, lean, arango)"),
) -> None:
    DATA_RESULTS.mkdir(parents=True, exist_ok=True)

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
            gold_file=DATA_GOLD / "012_insert_annotations_gs.json" if (DATA_GOLD / "012_insert_annotations_gs.json").exists() else None,
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
            _run([sys.executable, "-m", "extractor.pipeline.tools.compare_to_gold", "--output", str(out_json), "--gold", str(stages[1].gold_file)])

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
            _run([sys.executable, "-m", "extractor.pipeline.tools.compare_to_gold", "--output", str(out_json), "--gold", str(stages[2].gold_file)])

    # Stage 3
    if until >= 3:
        in_json = DATA_RESULTS / stages[2].output_json
        # Typer app requires explicit subcommand name
        _run([
            sys.executable,
            str(stages[3].script),
            "run",
            str(in_json),
            "--pdf-dir",
            str(anno_dir),
            "-o",
            str(DATA_RESULTS),
        ])
        out_json = DATA_RESULTS / stages[3].output_json
        if stages[3].gold_file and stages[3].gold_file.exists():
            _run([sys.executable, "-m", "extractor.pipeline.tools.compare_to_gold", "--output", str(out_json), "--gold", str(stages[3].gold_file)])

    # Stage 4
    if until >= 4:
        in_json = DATA_RESULTS / stages[3].output_json
        _run([sys.executable, str(stages[4].script), "run", str(in_json), "--pdf-dir", str(anno_dir), "-o", str(DATA_RESULTS)])
        out_json = DATA_RESULTS / stages[4].output_json
        if stages[4].gold_file and stages[4].gold_file.exists():
            _run([sys.executable, "-m", "extractor.pipeline.tools.compare_to_gold", "--output", str(out_json), "--gold", str(stages[4].gold_file)])

    # Continue with heavy stages if requested
    if skip_heavy or until <= 4:
        print("Stopped before heavy stages. Use --no-skip-heavy and --until N to continue.")
        raise typer.Exit(0)

    # Stage 5
    if until >= 5:
        in_json = DATA_RESULTS / stages[4].output_json
        _run([sys.executable, str(stages[5].script), "run", str(in_json), "--pdf-dir", str(anno_dir), "-o", str(DATA_RESULTS)])
        out_json = DATA_RESULTS / stages[5].output_json
        if stages[5].gold_file and stages[5].gold_file.exists():
            _run([sys.executable, "-m", "extractor.pipeline.tools.compare_to_gold", "--output", str(out_json), "--gold", str(stages[5].gold_file)])

    # Stage 6
    if until >= 6:
        blocks_json = DATA_RESULTS / stages[2].output_json
        sections_json = DATA_RESULTS / stages[4].output_json
        _run([sys.executable, str(stages[6].script), "run", str(blocks_json), "--sections", str(sections_json), "--pdf-dir", str(anno_dir), "-o", str(DATA_RESULTS)])
        out_json = DATA_RESULTS / stages[6].output_json
        if stages[6].gold_file and stages[6].gold_file.exists():
            _run([sys.executable, "-m", "extractor.pipeline.tools.compare_to_gold", "--output", str(out_json), "--gold", str(stages[6].gold_file)])

    # Stage 7
    if until >= 7:
        sections_json = DATA_RESULTS / stages[4].output_json
        tables_json = DATA_RESULTS / stages[5].output_json
        figures_json = DATA_RESULTS / stages[6].output_json
        _run([sys.executable, str(stages[7].script), "run", "--sections", str(sections_json), "--tables", str(tables_json), "--figures", str(figures_json), "-o", str(DATA_RESULTS)])
        out_json = DATA_RESULTS / stages[7].output_json
        if stages[7].gold_file and stages[7].gold_file.exists():
            _run([sys.executable, "-m", "extractor.pipeline.tools.compare_to_gold", "--output", str(out_json), "--gold", str(stages[7].gold_file)])

    # Stage 8
    if until >= 8:
        reflow_json = DATA_RESULTS / stages[7].output_json
        _run([sys.executable, str(stages[8].script), "run", str(reflow_json), "-o", str(DATA_RESULTS)])
        out_json = DATA_RESULTS / stages[8].output_json
        if stages[8].gold_file and stages[8].gold_file.exists():
            _run([sys.executable, "-m", "extractor.pipeline.tools.compare_to_gold", "--output", str(out_json), "--gold", str(stages[8].gold_file)])

    # Stage 9
    if until >= 9:
        reflow_json = DATA_RESULTS / stages[7].output_json
        _run([sys.executable, str(stages[9].script), "run", str(reflow_json), "-o", str(DATA_RESULTS), "--max-concurrent", "2", "--window-size", "2", "--strict-json"])
        out_json = DATA_RESULTS / stages[9].output_json
        if stages[9].gold_file and stages[9].gold_file.exists():
            _run([sys.executable, "-m", "extractor.pipeline.tools.compare_to_gold", "--output", str(out_json), "--gold", str(stages[9].gold_file)])

    # Stage 10
    if until >= 10:
        reflow_json = DATA_RESULTS / stages[7].output_json
        summaries_json = DATA_RESULTS / stages[9].output_json
        _run([sys.executable, str(stages[10].script), "run", "--reflowed", str(reflow_json), "--summaries", str(summaries_json), "-o", str(DATA_RESULTS)])
        out_json = DATA_RESULTS / stages[10].output_json
        if stages[10].gold_file and stages[10].gold_file.exists():
            _run([sys.executable, "-m", "extractor.pipeline.tools.compare_to_gold", "--output", str(out_json), "--gold", str(stages[10].gold_file)])

    # Stage 11
    if until >= 11:
        flat_json = DATA_RESULTS / stages[10].output_json
        _run([sys.executable, str(stages[11].script), "run", str(flat_json), "-o", str(DATA_RESULTS)])
        out_json = DATA_RESULTS / stages[11].output_json
        if stages[11].gold_file and stages[11].gold_file.exists():
            _run([sys.executable, "-m", "extractor.pipeline.tools.compare_to_gold", "--output", str(out_json), "--gold", str(stages[11].gold_file)])

    # Stage 12 (optional gold)
    if until >= 12 and stages[12].gold_file:
        annotations_json = DATA_RESULTS / stages[1].output_json
        _run([sys.executable, str(stages[12].script), "run", "--annotations", str(annotations_json), "-o", str(DATA_RESULTS)])
        out_json = DATA_RESULTS / stages[12].output_json
        if stages[12].gold_file and stages[12].gold_file.exists():
            _run([sys.executable, "-m", "extractor.pipeline.tools.compare_to_gold", "--output", str(out_json), "--gold", str(stages[12].gold_file)])

    # Stage 14
    if until >= 14:
        _run([sys.executable, str(stages[14].script), "run", str(DATA_RESULTS)])
        out_json = DATA_RESULTS / stages[14].output_json
        if stages[14].gold_file and stages[14].gold_file.exists():
            _run([sys.executable, "-m", "extractor.pipeline.tools.compare_to_gold", "--output", str(out_json), "--gold", str(stages[14].gold_file)])

    raise typer.Exit(0)


if __name__ == "__main__":
    app()
