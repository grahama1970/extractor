import json
from pathlib import Path

from extractor.pipeline.steps._07a_section_canonicalizer import run as run07a  # type: ignore


def test_no_merge_column_asymmetry(tmp_path: Path):
    sections = {
        "sections": [
            {"id": "S1", "title": "A", "level": 1, "page_start": 0, "page_end": 0,
             "blocks": [{"text": "Intro", "bbox": [0, 0, 100, 40], "page_idx": 0}],
             "metadata": {"section_content_hash": "ha"}},
            {"id": "S2", "title": "B", "level": 1, "page_start": 1, "page_end": 1,
             "blocks": [{"text": "Body", "bbox": [0, 0, 100, 40], "page_idx": 1}],
             "metadata": {"section_content_hash": "hb"}},
        ]
    }
    tables = {
        "tables": [
            {"section_id": "S1", "page_index": 0, "table_index": 0, "raw_table_id": "raw1",
             "bbox": [50, 300, 500, 360],
             "pandas_metrics": {"shape": [1, 3], "columns": ["col_a", "col_b", "col_c"], "data_density": 0.9},
             "pandas_df": [{"0": "col_a", "1": "col_b", "2": "col_c"}]},
            {"section_id": "S2", "page_index": 1, "table_index": 0, "raw_table_id": "raw2",
             "bbox": [50, 120, 500, 420],
             "pandas_metrics": {"shape": [5, 7], "columns": ["col_a", "col_b", "col_c", "x1", "x2", "x3", "x4"], "data_density": 0.85},
             "pandas_df": [{"0": "v", "1": "v", "2": "v", "3": "v", "4": "v", "5": "v", "6": "v"}]}
        ]
    }
    figures = {"figures": []}

    p_sec = tmp_path / "sec.json"; p_sec.write_text(json.dumps(sections))
    p_tab = tmp_path / "tab.json"; p_tab.write_text(json.dumps(tables))
    p_fig = tmp_path / "fig.json"; p_fig.write_text(json.dumps(figures))

    run07a(
        sections_json=p_sec,
        tables_json=p_tab,
        figures_json=p_fig,
        verified03_json=None,
        output_dir=tmp_path,
    )

    data = json.loads((tmp_path / "07a_section_canonicalizer" / "json_output" / "07a_canonical.json").read_text())
    s1 = [s for s in data["sections"] if s["id"] == "S1"][0]
    s2 = [s for s in data["sections"] if s["id"] == "S2"][0]
    assert len(s1["tables"]) == 1
    assert len(s2["tables"]) == 1
    assert not s2["tables"][0].get("provenance", {}).get("continuation_reason")

