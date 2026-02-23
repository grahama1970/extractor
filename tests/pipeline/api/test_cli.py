import json
from pathlib import Path
from typing import List

import pytest
from typer.testing import CliRunner

import extractor.pipeline.api as api


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


def _simulate_stage_outputs(cmd: List[str], out_dir: Path) -> None:
    """Create minimal expected files for each stage command the API would run.

    This mirrors the directory structure used by `extract_sections` without invoking
    heavyweight processing.
    """
    # Ensure parent structure exists for all stages
    (out_dir / "01_annotation_processor").mkdir(parents=True, exist_ok=True)
    (out_dir / "02_marker_extractor" / "json_output").mkdir(parents=True, exist_ok=True)
    (out_dir / "03_suspicious_headers" / "json_output").mkdir(parents=True, exist_ok=True)
    (out_dir / "04_section_builder" / "json_output").mkdir(parents=True, exist_ok=True)

    # Stage identification by script path contained in the command list
    joined = " ".join(cmd)
    if "01_annotation_processor.py" in joined:
        # Create a dummy cleaned PDF so _find_clean_pdf succeeds
        (out_dir / "01_annotation_processor" / "dummy_clean.pdf").write_bytes(b"%PDF-1.4\n%")
    elif "02_marker_extractor.py" in joined:
        # Minimal block output
        (out_dir / "02_marker_extractor" / "json_output" / "02_marker_blocks.json").write_text(
            json.dumps({"block_count": 0, "blocks": []})
        )
    elif "03_suspicious_headers.py" in joined:
        (out_dir / "03_suspicious_headers" / "json_output" / "03_verified_blocks.json").write_text(
            json.dumps({"verified_blocks": []})
        )
    elif "04_section_builder.py" in joined:
        (out_dir / "04_section_builder" / "json_output" / "04_sections.json").write_text(
            json.dumps({"sections": [{"title": "Intro"}]})
        )


def test_cli_run_json(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, runner: CliRunner) -> None:
    # Create a tiny input PDF
    pdf = tmp_path / "input.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%")

    # Monkeypatch _run to simulate side effects instead of executing real scripts
    def fake_run(cmd: List[str], cwd=None, env=None) -> None:
        _simulate_stage_outputs(cmd, tmp_path)

    # Monkeypatch _find_clean_pdf to return our dummy
    def fake_find(anno_dir: Path) -> Path:
        return next(anno_dir.glob("*_clean.pdf"))

    monkeypatch.setattr(api, "_run", fake_run)
    monkeypatch.setattr(api, "_find_clean_pdf", fake_find)

    app = api.build_cli()
    # The app has a single command; Typer flattens it, so omit 'run'
    result = runner.invoke(app, [str(pdf), "--json", "-o", str(tmp_path)], catch_exceptions=False)
    print("STDOUT:\n", result.stdout)
    print("EXC:", repr(result.exception))
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert isinstance(data.get("sections"), list)
    assert data["sections"][0]["title"] == "Intro"


def test_cli_run_text_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, runner: CliRunner
) -> None:
    pdf = tmp_path / "input.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%")

    def fake_run(cmd: List[str], cwd=None, env=None) -> None:
        _simulate_stage_outputs(cmd, tmp_path)

    def fake_find(anno_dir: Path) -> Path:
        return next(anno_dir.glob("*_clean.pdf"))

    monkeypatch.setattr(api, "_run", fake_run)
    monkeypatch.setattr(api, "_find_clean_pdf", fake_find)

    app = api.build_cli()
    result = runner.invoke(app, [str(pdf), "-o", str(tmp_path)], catch_exceptions=False)
    print("STDOUT:\n", result.stdout)
    print("EXC:", repr(result.exception))
    assert result.exit_code == 0
    assert "Sections JSON:" in result.stdout
    assert "Sections count: 1" in result.stdout
