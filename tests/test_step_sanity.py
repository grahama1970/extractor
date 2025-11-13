import json
from pathlib import Path

from extractor.pipeline.utils.step_sanity import run_step_sanity


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_layout_sketcher_accepts_section_mapping(tmp_path, monkeypatch, capsys):
    root = tmp_path / "results"
    monkeypatch.setenv("EXTRACTOR_RESULTS_ROOT", str(root))
    sections_path = root / "06b_layout_sketcher" / "json_output" / "06b_layout_sketch.json"
    _write_json(sections_path, {"sections": {"a": {"x": 1}, "b": {"x": 2}}})

    exit_code = run_step_sanity("06b_layout_sketcher")
    captured = capsys.readouterr()
    summary = json.loads(captured.out)

    assert exit_code == 0
    assert summary["outputs"][0]["sections_count"] == 2


def test_section_summarizer_skipped_when_summary_only(tmp_path, monkeypatch, capsys):
    root = tmp_path / "results"
    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("EXTRACTOR_RESULTS_ROOT", str(root))
    monkeypatch.setenv("SUMMARY_ONLY", "1")

    exit_code = run_step_sanity("09_section_summarizer")
    captured = capsys.readouterr()
    summary = json.loads(captured.out)

    assert exit_code == 0
    assert summary["skipped"] == "summary_only"
    assert summary["outputs"][0]["skip_reason"] == "summary_only"
