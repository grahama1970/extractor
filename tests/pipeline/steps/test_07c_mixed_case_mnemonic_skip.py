import json
from pathlib import Path

from extractor.pipeline.steps._07c_table_title_infer import run as run07c  # type: ignore


def test_mixed_case_mnemonic_skip(tmp_path: Path):
    canonical = {
        "sections": [
            {
                "id": "s1",
                "title": "Signals",
                "level": 1,
                "page_start": 0,
                "page_end": 0,
                "paragraphs": [],
                "tables": [
                    {
                        "tid": "t1",
                        "pandas_metrics": {"columns": ["Clk", "Rst_n", "Addr", "Data", "En"], "data_density": 0.92},
                        "pandas_df": [["1", "0", "FF", "AA", "1"]],
                    }
                ],
                "figures": [],
                "content_hash": "h1",
            }
        ]
    }
    cpath = tmp_path / "canonical.json"
    cpath.write_text(json.dumps(canonical))

    out_dir = tmp_path
    run07c(
        canonical_json=cpath,
        output_dir=out_dir,
        verified03_json=None,
    )

    data = json.loads((out_dir / "07c_table_title_infer" / "07c_table_title_infer.json").read_text())
    # Ensure mnemonic header resulted in no title for t1 (under section s1)
    sec_map = data.get("table_titles", {})
    assert not any((sid_map or {}).get("t1") for sid_map in sec_map.values())

