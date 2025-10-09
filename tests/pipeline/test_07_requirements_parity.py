import json, os, sys, subprocess
from pathlib import Path


def write_json(p: Path, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2))


def run_cmd(cmd, env):
    subprocess.check_call(cmd, env=env)


def test_requirements_parity_plugin_vs_standalone(tmp_path: Path):
    # Minimal doc with one SHALL sentence in paragraph and one in table
    sections = {"sections": [{"id": "S1", "title": "Reqs", "blocks": [{"block_type": "Text", "text": "The system SHALL initialize."}]}]}
    tables = {"tables": [{"section_id": "S1", "table_index": 0, "page_index": 1, "bbox": [0, 0, 100, 50],
                           "pandas_metrics": {"shape": [1, 2], "columns": ["Col1", "Col2"], "data_density": 0.9},
                           "pandas_df": [{"Col1": "Module shall respond", "Col2": "OK"}]}]}
    figures = {"figures": []}
    root = tmp_path / "results"
    write_json(root / "04_section_builder/json_output/04_sections.json", sections)
    write_json(root / "05_table_extractor/json_output/05_tables.json", tables)
    write_json(root / "06_figure_extractor/json_output/06_figures.json", figures)
    env = os.environ.copy()
    env["STAGE07_PLUGINS"] = "table_titles,requirements"
    run_cmd([
        sys.executable,
        "src/extractor/pipeline/steps/07_orchestrator.py",
        "--sections", str(root / "04_section_builder/json_output/04_sections.json"),
        "--tables", str(root / "05_table_extractor/json_output/05_tables.json"),
        "--figures", str(root / "06_figure_extractor/json_output/06_figures.json"),
        "-o", str(root)
    ], env)
    plugin_req = json.loads((root / "07_requirements_miner/json_output/07_requirements.json").read_text())["requirements"]
    # Now run standalone miner
    run_cmd([
        sys.executable,
        "src/extractor/pipeline/steps/07_requirements_miner.py",
        str(root / "07_reflow_section/json_output/07_reflowed.json"),
        "-o", str(root)
    ], env)
    standalone_req = json.loads((root / "07_requirements_miner/json_output/07_requirements.json").read_text())["requirements"]
    assert len(plugin_req) == len(standalone_req), "Requirement counts differ plugin vs standalone"
    # Spot check one 'shall'
    assert any("shall" in r["text_raw"].lower() for r in plugin_req), "Missing SHALL modality"

