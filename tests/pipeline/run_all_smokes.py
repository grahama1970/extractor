import json
from pathlib import Path

import pytest
from typer.testing import CliRunner


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


def _touch_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj))


def _simulate_run_all(cmd: list[str], env: dict[str, str], results_dir: Path) -> None:
    joined = " ".join(cmd)
    # Stage 01
    if "01_annotation_processor.py" in joined:
        (results_dir / "01_annotation_processor").mkdir(parents=True, exist_ok=True)
        (results_dir / "01_annotation_processor" / "dummy_clean.pdf").write_bytes(b"%PDF-1.4\n%")
        _touch_json(
            results_dir / "01_annotation_processor" / "json_output" / "01_annotations.json",
            {"annotation_count": 1, "annotations": [], "clean_pdf_path": "dummy_clean.pdf"},
        )
    # Stage 02
    elif "02_marker_extractor.py" in joined:
        _touch_json(results_dir / "02_marker_extractor" / "json_output" / "02_marker_blocks.json", {"block_count": 0})
    # Stage 03
    elif "03_suspicious_headers.py" in joined:
        _touch_json(results_dir / "03_suspicious_headers" / "json_output" / "03_verified_blocks.json", {"verified_blocks": []})
    # Stage 04
    elif "04_section_builder.py" in joined:
        _touch_json(
            results_dir / "04_section_builder" / "json_output" / "04_sections.json",
            {"section_count": 1, "hierarchy_depth": 1, "sections": [{"title": "Intro", "level": 1}]},
        )
    # Stage 05
    elif "05_table_extractor.py" in joined:
        _touch_json(results_dir / "05_table_extractor" / "json_output" / "05_tables.json", {"table_count": 0})
    # Stage 06
    elif "06_figure_extractor.py" in joined:
        _touch_json(results_dir / "06_figure_extractor" / "json_output" / "06_figures.json", {"figure_count": 0, "figures": []})
    # Stage 07
    elif "07_reflow_section.py" in joined:
        _touch_json(results_dir / "07_reflow_section" / "json_output" / "07_reflowed.json", {"reflowed_sections": []})
    # Stage 08
    elif "08_lean4_theorem_prover.py" in joined:
        _touch_json(results_dir / "08_lean4_theorem_prover" / "json_output" / "08_theorems.json", {"theorems": []})
    # Stage 09
    elif "09_section_summarizer.py" in joined:
        _touch_json(
            results_dir / "09_section_summarizer" / "json_output" / "09_summaries.json",
            {"summaries_generated": 0, "summaries": []},
        )
    # Stage 10
    elif "10_arangodb_exporter.py" in joined:
        _touch_json(
            results_dir / "10_arangodb_exporter" / "json_output" / "10_flattened_data.json",
            {"objects": []},
        )
        _touch_json(
            results_dir / "10_arangodb_exporter" / "json_output" / "10_export_confirmation.json",
            {"ok": True},
        )
    # Stage 11
    elif "11_arango_create_graph.py" in joined:
        _touch_json(
            results_dir / "11_arango_create_graph" / "json_output" / "11_graph_confirmation.json",
            {"ok": True},
        )
    # Stage 12
    elif "12_insert_annotations.py" in joined:
        # No-op side effect confirmation
        pass
    # Stage 14
    elif "14_report_generator.py" in joined:
        (results_dir / "14_report_generator" / "json_output").mkdir(parents=True, exist_ok=True)
        (results_dir / "final_report.md").write_text("# Report\nOK")
        (results_dir / "final_report.json").write_text(json.dumps({"success": True}))


def test_run_all_smoke(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, runner: CliRunner) -> None:
    from extractor.pipeline import run_all

    # Create input PDF
    pdf = tmp_path / "input.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%")
    results_dir = tmp_path / "results"

    def fake_run(cmd: list[str], env: dict[str, str]):
        _simulate_run_all(cmd, env, results_dir)

    monkeypatch.setattr(run_all, "_run", fake_run)

    res = runner.invoke(
        run_all.app,
        [
            "--pdf",
            str(pdf),
            "--results",
            str(results_dir),
            "--arango-db",
            "test_db",
            "--session",
            "sess-123",
        ],
        catch_exceptions=False,
    )

    assert res.exit_code == 0
    assert (results_dir / "final_report.md").exists()
    assert "All stages completed" in res.stdout
