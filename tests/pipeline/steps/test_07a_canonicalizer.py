import json
from pathlib import Path

from extractor.pipeline.steps._07a_section_canonicalizer import run as run_07a  # type: ignore


def _write(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2))


def test_07a_continuity_and_hash(tmp_path: Path):
    # Minimal 04
    s04 = {
        "sections": [
            {"id": "section_0", "title": "A", "level": 1, "page_start": 0, "page_end": 0, "bbox": [0,0,100,100],
             "blocks": [{"text":"Intro","bbox":[0,0,10,10],"page":0}], "metadata": {}},
            {"id": "section_1", "title": "B", "level": 1, "page_start": 1, "page_end": 1, "bbox": [0,0,100,100],
             "blocks": [{"text":"Body","bbox":[0,0,10,10],"page":1}], "metadata": {}},
        ]
    }
    # Minimal 05: table at end of section_0 and start of section_1 with same normalized_label
    s05 = {
        "tables": [
            {"page_index":0, "table_index":1, "raw_table_id":"rawtbl_p0_i1", "normalized_label":"table/4-1",
             "pandas_metrics": {"columns":["a","b"], "data_density": 0.95}, "pandas_df":[["1","2"]]},
            {"page_index":1, "table_index":1, "raw_table_id":"rawtbl_p1_i1", "normalized_label":"table/4-1",
             "pandas_metrics": {"columns":["a","b"], "data_density": 0.95}, "pandas_df":[["3","4"]]},
        ]
    }
    # Minimal 06
    s06 = {"figures": []}
    # 03 verified blocks
    s03 = {
        "blocks": [
            {"page_idx": 0, "bbox":[10,10,20,20], "block_type":"SectionHeader", "llm_verification":{"result":{"is_header":True}}, "normalized_header_text":"intro"}
        ]
    }

    out_dir = tmp_path / "out"
    p04 = tmp_path/"04.json"; _write(p04, s04)
    p05 = tmp_path/"05.json"; _write(p05, s05)
    p06 = tmp_path/"06.json"; _write(p06, s06)
    p03 = tmp_path/"03.json"; _write(p03, s03)

    # Execute 07a
    run_07a.callback(
        sections_json=p04,
        tables_json=p05,
        figures_json=p06,
        verified03_json=p03,
        output_dir=out_dir,
    ) if hasattr(run_07a, 'callback') else run_07a(
        sections_json=p04,
        tables_json=p05,
        figures_json=p06,
        verified03_json=p03,
        output_dir=out_dir,
    )

    payload = json.loads((out_dir/"07a_section_canonicalizer"/"json_output"/"07a_canonical.json").read_text())
    sections = {s["id"]: s for s in payload.get("sections", [])}
    # Continuity move: later section should have two tables; earlier zero
    assert len(sections["section_1"]["tables"]) == 2
    assert len(sections["section_0"]["tables"]) == 0
    # Content hash present
    assert isinstance(sections["section_1"].get("content_hash"), str)

