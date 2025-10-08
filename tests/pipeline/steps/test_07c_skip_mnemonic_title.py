import json
from pathlib import Path

from extractor.pipeline.steps._07c_table_title_infer import run as run07c  # type: ignore


def test_skip_mnemonic_title(tmp_path: Path, monkeypatch):
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
                        "pandas_metrics": {"columns": ["VDD", "CLK", "RST", "EN"], "data_density": 0.9},
                        "pandas_df": [["1", "2", "3", "4"]],
                    }
                ],
                "figures": [],
                "content_hash": "abc",
            }
        ]
    }
    cpath = tmp_path / "canon.json"; cpath.write_text(json.dumps(canonical))

    out_dir = tmp_path
    run07c(
        canonical_json=cpath,
        output_dir=out_dir,
        verified03_json=None,
    )
    data = json.loads((out_dir / "07c_table_title_infer" / "07c_table_title_infer.json").read_text())
    # Find any section entry mapping
    # Since we store by section id, ensure the mnemonic header resulted in no title for t1
    sec_map = data.get("table_titles", {})
    # titles keyed by raw table key from code path; here using t1 when present
    # Fallback: ensure no non-empty titles present in any section for tid t1
    assert not any((sid_map or {}).get("t1") for sid_map in sec_map.values())

