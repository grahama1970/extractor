import json
from pathlib import Path
import subprocess
import sys


def write_json(p: Path, payload: dict):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2))


def test_stage07_summary_only(tmp_path: Path):
    results = tmp_path / "results"

    # Minimal Stage 04 sections
    sections = {
        "sections": [
            {
                "id": "S1",
                "title": "Introduction",
                "blocks": [
                    {"block_type": "Text", "text": "System shall initialize safely.", "page_idx": 0}
                ],
                "page_start": 0,
                "page_end": 0,
            }
        ]
    }
    tables = {"table_count": 0, "tables": []}
    figures = {"figure_count": 0, "figures": []}

    write_json(results / "04_section_builder" / "json_output" / "04_sections.json", sections)
    write_json(results / "05_table_extractor" / "json_output" / "05_tables.json", tables)
    write_json(results / "06_figure_extractor" / "json_output" / "06_figures.json", figures)

    # Run Stage 07 summary-only
    cmd = [
        sys.executable,
        "src/extractor/pipeline/steps/07_reflow_section.py",
        "run",
        "--sections",
        str(results / "04_section_builder" / "json_output" / "04_sections.json"),
        "--tables",
        str(results / "05_table_extractor" / "json_output" / "05_tables.json"),
        "--figures",
        str(results / "06_figure_extractor" / "json_output" / "06_figures.json"),
        "--summary-only",
        "-o",
        str(results),
    ]
    subprocess.check_call(cmd)
    reflow_path = results / "07_reflow_section" / "json_output" / "07_reflowed.json"
    assert reflow_path.exists(), "07_reflowed.json not created"
    data = json.loads(reflow_path.read_text())
    assert data.get("reflowed_sections"), "No sections in reflow output"
    assert data["reflowed_sections"][0].get("reflowed_text") is not None

    # Run requirements miner
    cmd2 = [
        sys.executable,
        "src/extractor/pipeline/steps/07_requirements_miner.py",
        "run",
        str(reflow_path),
        "-o",
        str(results),
    ]
    subprocess.check_call(cmd2)
    req_path = results / "07_requirements_miner" / "json_output" / "07_requirements.json"
    assert req_path.exists(), "07_requirements.json not created"
    req_data = json.loads(req_path.read_text())
    assert "requirements" in req_data

