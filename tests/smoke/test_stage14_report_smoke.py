import json
import importlib.util


def _load_mod():
    """Load a module from a hardcoded file path."""
    spec = importlib.util.spec_from_file_location(
        "stage14", "src/extractor/pipeline/steps/14_report_generator.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


def test_report_load_and_stats(tmp_path):
    """Load test report data and generate statistics from pipeline structure."""
    mod = _load_mod()
    # Create minimal pipeline dir layout with canonical json_output files
    base = tmp_path / "pipeline"
    (base / "01_annotation_processor" / "json_output").mkdir(parents=True)
    (base / "02_marker_extractor" / "json_output").mkdir(parents=True)
    (base / "04_section_builder" / "json_output").mkdir(parents=True)
    (base / "05_table_extractor" / "json_output").mkdir(parents=True)
    (base / "06_figure_extractor" / "json_output").mkdir(parents=True)
    (base / "07_reflow_section" / "json_output").mkdir(parents=True)
    (base / "10_arangodb_exporter" / "json_output").mkdir(parents=True)

    def dump(p, data):
        """Dump data as JSON to a path."""
        p.write_text(json.dumps(data))

    dump(
        base / "01_annotation_processor" / "json_output" / "01_annotations.json",
        {"annotation_count": 1, "annotations": [{"interpretation": {}}], "clean_pdf_path": "x"},
    )
    dump(
        base / "02_marker_extractor" / "json_output" / "02_marker_blocks.json",
        {"block_count": 5},
    )
    dump(
        base / "04_section_builder" / "json_output" / "04_sections.json",
        {
            "section_count": 1,
            "hierarchy_depth": 1,
            "suspicious_header_analysis": {"categories": {"false_positives": []}},
        },
    )
    dump(
        base / "05_table_extractor" / "json_output" / "05_tables.json",
        {"table_count": 0},
    )
    dump(
        base / "06_figure_extractor" / "json_output" / "06_figures.json",
        {"figure_count": 0, "figures": []},
    )
    dump(
        base / "07_reflow_section" / "json_output" / "07_reflowed.json",
        {"reflowed_sections": []},
    )
    dump(
        base / "10_arangodb_exporter" / "json_output" / "10_export_confirmation.json",
        {"ok": True},
    )

    results = mod.load_results(base)
    stats = mod.calculate_pipeline_statistics(results)
    assert stats["total_stages_run"] >= 5
    assert "overall_quality_score" in stats
