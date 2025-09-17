#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "python-dotenv",
#   "typer>=0.12",
# ]
# ///
import json
from pathlib import Path
import importlib.util
import typer
from dotenv import load_dotenv, find_dotenv


app = typer.Typer(add_completion=False, help="Smoke: Stage 14 report stats from synthetic pipeline dir")


def _load_stage14():
    spec = importlib.util.spec_from_file_location(
        "stage14", "src/extractor/pipeline/steps/14_report_generator.py"
    )
    if not spec or not spec.loader:
        raise RuntimeError("Failed to load Stage 14 module")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


@app.command()
def main():
    load_dotenv(find_dotenv())
    mod = _load_stage14()
    base = Path("data/results/pipeline/smokes/report_synth")
    # Create minimal canonical tree
    def d(p: Path):
        p.mkdir(parents=True, exist_ok=True)
        return p
    d(base / "01_annotation_processor" / "json_output").joinpath("01_annotations.json").write_text(
        json.dumps({"annotation_count": 1, "annotations": [{"interpretation": {}}], "clean_pdf_path": "x"})
    )
    d(base / "02_marker_extractor" / "json_output").joinpath("02_marker_blocks.json").write_text(
        json.dumps({"block_count": 5})
    )
    d(base / "04_section_builder" / "json_output").joinpath("04_sections.json").write_text(
        json.dumps({"section_count": 1, "hierarchy_depth": 1, "suspicious_header_analysis": {"categories": {"false_positives": []}}})
    )
    d(base / "05_table_extractor" / "json_output").joinpath("05_tables.json").write_text(
        json.dumps({"table_count": 0})
    )
    d(base / "06_figure_extractor" / "json_output").joinpath("06_figures.json").write_text(
        json.dumps({"figure_count": 0, "figures": []})
    )
    d(base / "07_reflow_section" / "json_output").joinpath("07_reflowed.json").write_text(
        json.dumps({"reflowed_sections": []})
    )
    d(base / "10_arangodb_exporter" / "json_output").joinpath("10_export_confirmation.json").write_text(
        json.dumps({"ok": True})
    )

    results = mod.load_results(base)
    stats = mod.calculate_pipeline_statistics(results)
    if "overall_quality_score" not in stats:
        raise SystemExit(1)
    typer.echo("OK: Stage 14 report stats computed")


if __name__ == "__main__":
    app()
