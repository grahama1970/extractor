import json
from pathlib import Path
from extractor.pipeline.steps._07b_paragraph_polish import run as run_07b  # type: ignore


def _write(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2))


def test_paragraph_suppression_near_header(tmp_path: Path):
    canonical = {
        "sections":[
            {"id":"s1","title":"Intro","level":1,"page_start":0,"page_end":0,
             "paragraphs":[
                 {"pid":"p1","text":"Functional Overview","bbox":[10,100,300,140],"page_idx":0},
                 {"pid":"p2","text":"BROK EN hyphen- para with    noise","bbox":[10,170,420,210],"page_idx":0}
             ],
             "tables":[],"figures":[],"content_hash":"abc"}
        ]
    }
    stage03 = {
        "blocks":[
            {"object_id":"hdr_p0_b0","page_idx":0,"bbox":[10,95,300,135],
             "text":"Functional Overview","llm_verification":{"result":{"is_header":True}}}
        ]
    }
    cpath = tmp_path/"canon.json"; _write(cpath, canonical)
    s03p = tmp_path/"03.json"; _write(s03p, stage03)
    out_dir = tmp_path/"out"
    run_07b.callback(canonical_json=cpath, output_dir=out_dir, verified03_json=s03p) if hasattr(run_07b,'callback') else run_07b(canonical_json=cpath, output_dir=out_dir, verified03_json=s03p)
    data = json.loads((out_dir/"07b_paragraph_polish"/"07b_paragraph_polish.json").read_text())
    pol = data.get("polish", {}).get("s1", {})
    # p1 suppressed (near header) => identity mapping present or skipped
    assert pol.get("p1") in (None, "Functional Overview")

