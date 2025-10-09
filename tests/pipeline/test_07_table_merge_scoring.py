import json, os, sys, subprocess
from pathlib import Path


def write_json(p: Path, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2))


def build_header_body_pair():
    header = {
        "section_id": "S1",
        "table_index": 0,
        "page_index": 1,
        "bbox": [50, 100, 550, 300],
        "pandas_metrics": {"shape": [1, 2], "columns": ["ColA", "ColB"], "data_density": 1.0},
        "pandas_df": [{"ColA": "H1", "ColB": "H2"}],
    }
    body = {
        "section_id": "S1",
        "table_index": 1,
        "page_index": 2,
        "bbox": [50, 120, 550, 780],
        "pandas_metrics": {"shape": [2, 2], "columns": ["ColA", "ColB"], "data_density": 0.9},
        "pandas_df": [{"ColA": "a", "ColB": "b"}, {"ColA": "c", "ColB": "d"}],
    }
    return header, body


def prepare_min_inputs(root: Path, tables_payload):
    sections = {"sections": [{"id": "S1", "title": "Intro", "blocks": [{"block_type": "Text", "text": "Para"}]}]}
    figures = {"figures": []}
    write_json(root / "04_section_builder/json_output/04_sections.json", sections)
    write_json(root / "05_table_extractor/json_output/05_tables.json", tables_payload)
    write_json(root / "06_figure_extractor/json_output/06_figures.json", figures)


def run_orchestrator(root: Path, env: dict):
    cmd = [
        sys.executable,
        "src/extractor/pipeline/steps/07_orchestrator.py",
        "--sections",
        str(root / "04_section_builder/json_output/04_sections.json"),
        "--tables",
        str(root / "05_table_extractor/json_output/05_tables.json"),
        "--figures",
        str(root / "06_figure_extractor/json_output/06_figures.json"),
        "-o",
        str(root),
    ]
    subprocess.check_call(cmd, env=env)


def test_strict_auto_merge(tmp_path: Path):
    h, b = build_header_body_pair()
    prepare_min_inputs(tmp_path, {"tables": [h, b]})
    env = os.environ.copy()
    env["STAGE07_TABLE_MERGE_MODE"] = "strict"
    run_orchestrator(tmp_path, env)
    data = json.loads((tmp_path / "07_reflow_section/json_output/07_reflowed.json").read_text())
    sec = data["reflowed_sections"][0]
    assert len(sec["tables"]) == 1, "Strict mode should auto-merge header+body pair"


def test_assist_mode_no_merge(tmp_path: Path):
    h, b = build_header_body_pair()
    prepare_min_inputs(tmp_path, {"tables": [h, b]})
    env = os.environ.copy()
    env["STAGE07_TABLE_MERGE_MODE"] = "assist"
    run_orchestrator(tmp_path, env)
    data = json.loads((tmp_path / "07_reflow_section/json_output/07_reflowed.json").read_text())
    sec = data["reflowed_sections"][0]
    assert len(sec["tables"]) == 2, "Assist mode must not auto-merge"
    cand = sec["table_merge"]["candidates"]
    assert cand, "Candidates should be recorded in assist mode"


def test_llm_mode_with_decisions(tmp_path: Path):
    h, b = build_header_body_pair()
    prepare_min_inputs(tmp_path, {"tables": [h, b]})
    decisions = {"pairs": [{"section_id": "S1", "t1_index": 0, "t2_index": 1, "decision": "merge"}]}
    dec_path = tmp_path / "decisions.json"
    write_json(dec_path, decisions)
    env = os.environ.copy()
    env["STAGE07_TABLE_MERGE_MODE"] = "llm"
    env["STAGE07_LLM_TABLE_MERGE_DECISIONS"] = str(dec_path)
    env["STAGE07_PLUGINS"] = "table_titles,llm_table_merge_adjudicator,requirements"
    run_orchestrator(tmp_path, env)
    data = json.loads((tmp_path / "07_reflow_section/json_output/07_reflowed.json").read_text())
    sec = data["reflowed_sections"][0]
    assert len(sec["tables"]) == 1, "LLM adjudicator (decisions file) should merge pair"

