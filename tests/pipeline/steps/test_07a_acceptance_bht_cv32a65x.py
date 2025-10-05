import json
from pathlib import Path
from extractor.pipeline.steps._07a_section_canonicalizer import run as run_07a  # type: ignore


def _write(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2))


def test_bht_cv32a65x_merge(tmp_path: Path):
    sections = {
        "sections": [
            {"id":"sec0","title":"Intro","level":1,"page_start":0,"page_end":0,
             "blocks":[{"text":"Intro para","bbox":[0,0,100,40],"page_idx":0}],
             "metadata": {"section_content_hash":"h0","needs_layout_image":False}},
            {"id":"sec1","title":"Branch Predictor","level":1,"page_start":1,"page_end":1,
             "blocks":[{"text":"Body para","bbox":[0,0,100,40],"page_idx":1}],
             "metadata": {"section_content_hash":"h1","needs_layout_image":False}},
        ]
    }
    tables = {
        "tables": [
            {"section_id":"sec0","page_index":0,"table_index":0,"raw_table_id":"rawtbl_p0_i0",
             "pandas_metrics":{"columns":["bht_update_i","bht_prediction_o","unused"],"data_density":0.95},
             "pandas_df":[{"0":"bht_update_i","1":"bht_prediction_o","2":"unused"}]},
            {"section_id":"sec1","page_index":1,"table_index":0,"raw_table_id":"rawtbl_p1_i0",
             "pandas_metrics":{"columns":["0","1","2"],"data_density":0.85},
             "pandas_df":[{"0":"row1a","1":"row1b","2":"row1c"}]}
        ]
    }
    figures = {"figures": []}
    stage03 = {"blocks":[{"object_id":"hdr_p1_b0","page_idx":1,"bbox":[10,50,400,90],"text":"bht_update_i bht_prediction_o unused","llm_verification":{"result":{"is_header":False}}}]}

    p04 = tmp_path/"04.json"; _write(p04, sections)
    p05 = tmp_path/"05.json"; _write(p05, tables)
    p06 = tmp_path/"06.json"; _write(p06, figures)
    p03 = tmp_path/"03.json"; _write(p03, stage03)

    out_dir = tmp_path/"out"
    # Typer wrapper
    run_07a.callback(
        sections_json=p04, tables_json=p05, figures_json=p06, verified03_json=p03, output_dir=out_dir
    ) if hasattr(run_07a, 'callback') else run_07a(
        sections_json=p04, tables_json=p05, figures_json=p06, verified03_json=p03, output_dir=out_dir
    )

    data = json.loads((out_dir/"07a_section_canonicalizer"/"json_output"/"07a_canonical.json").read_text())
    sec0 = [s for s in data["sections"] if s["id"]=="sec0"][0]
    sec1 = [s for s in data["sections"] if s["id"]=="sec1"][0]
    assert len(sec0["tables"]) == 0
    assert len(sec1["tables"]) >= 1
    cols = sec1["tables"][0].get("pandas_metrics", {}).get("columns") or []
    assert [c.lower() for c in cols] == ["bht_update_i","bht_prediction_o","unused"]

