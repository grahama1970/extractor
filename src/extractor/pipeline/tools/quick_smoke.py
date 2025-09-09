#!/usr/bin/env python3
"""Quick pipeline smoke: 01→09 and 14 with gold checks, 10–11 in skip modes.

Usage:
  pipeline-quick-smoke --pdf data/input/pipeline/BHT_CV32A65X_marked.pdf
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
import sys
import typer

app = typer.Typer(help="Run 01→09 & 14 with gold checks; 10–11 in skip modes")

ROOT = Path.cwd()
SRC = ROOT / "src"
DATA_RESULTS = ROOT / "data" / "results" / "pipeline"
DATA_GOLD = ROOT / "data" / "gold_standards" / "pipeline"


def _run(cmd: list[str]) -> None:
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", str(SRC))
    proc = subprocess.run(cmd, env=env)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


@app.command()
def run(
    pdf: Path = typer.Option(..., "--pdf", exists=True, file_okay=True, dir_okay=False, readable=True),
) -> None:
    DATA_RESULTS.mkdir(parents=True, exist_ok=True)

    # 1→4
    _run([sys.executable, "-m", "extractor.pipeline.tools.run_and_validate", "--pdf", str(pdf), "--until", "4"])

    # 5
    _run([sys.executable, str(SRC/"extractor/pipeline/steps/05_table_extractor.py"), "run",
          str(DATA_RESULTS/"04_section_builder/json_output/04_sections.json"),
          "--pdf-dir", str(DATA_RESULTS/"01_annotation_processor"), "-o", str(DATA_RESULTS)])
    _run([sys.executable, "-m", "extractor.pipeline.tools.compare_to_gold", "--output",
          str(DATA_RESULTS/"05_table_extractor/json_output/05_tables.json"), "--gold",
          str(DATA_GOLD/"005_table_extractor_gs.json")])

    # 6
    _run([sys.executable, str(SRC/"extractor/pipeline/steps/06_figure_extractor.py"), "run",
          str(DATA_RESULTS/"02_marker_extractor/json_output/02_marker_blocks.json"),
          "--sections", str(DATA_RESULTS/"04_section_builder/json_output/04_sections.json"),
          "--pdf-dir", str(DATA_RESULTS/"01_annotation_processor"), "-o", str(DATA_RESULTS)])
    _run([sys.executable, "-m", "extractor.pipeline.tools.compare_to_gold", "--output",
          str(DATA_RESULTS/"06_figure_extractor/json_output/06_figures.json"), "--gold",
          str(DATA_GOLD/"006_figure_extractor_gs.json")])

    # 7 (summary-only)
    _run([sys.executable, str(SRC/"extractor/pipeline/steps/07_reflow_section.py"), "run",
          "--sections", str(DATA_RESULTS/"04_section_builder/json_output/04_sections.json"),
          "--tables", str(DATA_RESULTS/"05_table_extractor/json_output/05_tables.json"),
          "--figures", str(DATA_RESULTS/"06_figure_extractor/json_output/06_figures.json"),
          "--annotations", str(DATA_RESULTS/"01_annotation_processor/json_output/01_annotations.json"),
          "-o", str(DATA_RESULTS), "--summary-only"])
    _run([sys.executable, "-m", "extractor.pipeline.tools.compare_to_gold", "--output",
          str(DATA_RESULTS/"07_reflow_section/json_output/07_reflowed.json"), "--gold",
          str(DATA_GOLD/"007_reflow_section_gs.json")])

    # 8 (skip proving)
    _run([sys.executable, str(SRC/"extractor/pipeline/steps/08_lean4_theorem_prover.py"), "run",
          str(DATA_RESULTS/"07_reflow_section/json_output/07_reflowed.json"), "-o", str(DATA_RESULTS), "--skip-proving"])
    _run([sys.executable, "-m", "extractor.pipeline.tools.compare_to_gold", "--output",
          str(DATA_RESULTS/"08_lean4_theorem_prover/json_output/08_theorems.json"), "--gold",
          str(DATA_GOLD/"008_lean4_theorem_prover_gs.json")])

    # 9
    _run([sys.executable, str(SRC/"extractor/pipeline/steps/09_section_summarizer.py"), "run",
          str(DATA_RESULTS/"07_reflow_section/json_output/07_reflowed.json"), "-o", str(DATA_RESULTS), "--strict-json", "--max-concurrent", "3"])
    _run([sys.executable, "-m", "extractor.pipeline.tools.compare_to_gold", "--output",
          str(DATA_RESULTS/"09_section_summarizer/json_output/09_summaries.json"), "--gold",
          str(DATA_GOLD/"009_section_summarizer_gs.json")])

    # 14
    _run([sys.executable, str(SRC/"extractor/pipeline/steps/14_report_generator.py"), "run", str(DATA_RESULTS)])
    _run([sys.executable, "-m", "extractor.pipeline.tools.compare_to_gold", "--output",
          str(DATA_RESULTS/"final_report.json"), "--gold",
          str(DATA_GOLD/"014_report_generator_gs.json")])

    # 10 (skip export) + 11 (skip graph creation)
    _run([sys.executable, str(SRC/"extractor/pipeline/steps/10_arangodb_exporter.py"), "run",
          "--reflowed", str(DATA_RESULTS/"07_reflow_section/json_output/07_reflowed.json"),
          "--summaries", str(DATA_RESULTS/"09_section_summarizer/json_output/09_summaries.json"),
          "-o", str(DATA_RESULTS), "--skip-export"])
    _run([sys.executable, str(SRC/"extractor/pipeline/steps/11_arango_create_graph.py"), "run",
          str(DATA_RESULTS/"10_arangodb_exporter/json_output/10_flattened_data.json"),
          "-o", str(DATA_RESULTS), "--skip-graph-creation"])

    print("\n✅ Quick smoke completed.")


if __name__ == "__main__":
    app()

