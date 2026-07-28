"""Test that scanned PDF metadata is captured in assembled_content.json."""
import json
from pathlib import Path

from extractor.pipeline.steps.s07_json_assembler import run_assemble_corpus


def test_scanned_metadata_ingested(tmp_path: Path):
    """Prepare test files for scanned metadata ingestion."""
    scanned_path = tmp_path / "scanned_pdf.json"
    scanned_path.write_text(json.dumps({"is_scanned": True, "confidence": 0.8}))

    sections_json = tmp_path / "04_sections.json"
    sections_json.write_text(json.dumps({"sections": []}))

    tables_json = tmp_path / "05_tables.json"
    tables_json.write_text(json.dumps({"tables": []}))

    figures_json = tmp_path / "06_figures.json"
    figures_json.write_text(json.dumps({"figures": []}))

    annotations_json = tmp_path / "01_annotations.json"
    annotations_json.write_text(json.dumps({"annotations": []}))

    marker_json = tmp_path / "02_marker_blocks.json"
    marker_json.write_text(json.dumps({"toc_entries": []}))

    out_path = tmp_path / "07_assembled" / "assembled_content.json"

    run_assemble_corpus(
        output_json_path=out_path,
        sections_json=sections_json,
        tables_json=tables_json,
        figures_json=figures_json,
        annotations_json=annotations_json,
        marker_json=marker_json,
        scanned_info_json=scanned_path,
    )

    assert out_path.exists()
    data = json.loads(out_path.read_text())

    assert data["metadata"]["is_scanned"] is True
