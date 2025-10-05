import json
from pathlib import Path

# Existing tests import using underscored alias; match that convention
from extractor.pipeline.steps._07a_section_canonicalizer import run as run_07a  # type: ignore


def test_no_false_merge(tmp_path: Path):
    sections = {
        "sections": [
            {
                "id": "A",
                "title": "Sec A",
                "level": 1,
                "page_start": 0,
                "page_end": 0,
                "blocks": [{"text": "Intro", "bbox": [0, 0, 100, 40], "page_idx": 0}],
                "metadata": {"section_content_hash": "ha"},
            },
            {
                "id": "B",
                "title": "Sec B",
                "level": 1,
                "page_start": 1,
                "page_end": 1,
                "blocks": [{"text": "Body", "bbox": [0, 0, 100, 40], "page_idx": 1}],
                "metadata": {"section_content_hash": "hb"},
            },
        ]
    }
    tables = {
        "tables": [
            {
                "section_id": "A",
                "page_index": 0,
                "table_index": 0,
                "raw_table_id": "rawA",
                "bbox": [50, 500, 400, 560],
                "pandas_metrics": {"shape": [1, 3], "columns": ["alpha", "beta", "gamma"], "data_density": 0.95},
                "pandas_df": [{"0": "alpha", "1": "beta", "2": "gamma"}],
            },
            {
                "section_id": "B",
                "page_index": 1,
                "table_index": 0,
                "raw_table_id": "rawB",
                "bbox": [50, 120, 400, 300],
                "pandas_metrics": {"shape": [4, 3], "columns": ["delta", "epsilon", "theta"], "data_density": 0.80},
                "pandas_df": [{"0": "d1", "1": "e1", "2": "t1"}],
            },
        ]
    }
    figures = {"figures": []}

    p_sec = tmp_path / "sec.json"
    p_sec.write_text(json.dumps(sections))
    p_tab = tmp_path / "tab.json"
    p_tab.write_text(json.dumps(tables))
    p_fig = tmp_path / "fig.json"
    p_fig.write_text(json.dumps(figures))
    out_dir = tmp_path

    # Run
    run_07a(
        sections_json=p_sec,
        tables_json=p_tab,
        figures_json=p_fig,
        verified03_json=None,
        output_dir=out_dir,
    )
    result = json.loads((out_dir / "07a_section_canonicalizer" / "json_output" / "07a_canonical.json").read_text())
    a = [s for s in result["sections"] if s["id"] == "A"][0]
    b = [s for s in result["sections"] if s["id"] == "B"][0]
    assert len(a["tables"]) == 1
    assert len(b["tables"]) == 1
    assert not b["tables"][0].get("provenance", {}).get("continuation_reason")

