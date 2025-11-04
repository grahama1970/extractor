import json
import os
import shutil
import subprocess
from pathlib import Path

RUN_DIR = Path("data/results/ci_det_test")
PDF = Path("data/input/pipeline/BHT_CV32A65X_with_requirements_noannots.pdf")


def run_pipeline_det(out_dir: Path) -> None:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    # Ensure propagation is ON (safety flag default is on, but set explicitly)
    env["STAGE06B_HEADER_PROPAGATION"] = "1"
    cmd = [
        "python",
        "-m",
        "extractor.pipeline.run_pipeline",
        "--pdf",
        str(PDF),
        "--out",
        str(out_dir),
        "--summary-only",
        "--skip-fig-descriptions",
        "--annotate-pdf",
        "--stop-on-fail",
    ]
    subprocess.run(cmd, check=True, env=env)


def _load_json(p: Path):
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def test_bht_tables_merged_and_overlays_present():
    run_pipeline_det(RUN_DIR)

    # 06b sketch v2: ensure p0→p1 share lid with expected header_norm
    v2 = _load_json(RUN_DIR / "06b_layout_sketcher" / "json_output" / "06b_layout_sketch_v2.json")
    assert "sections" in v2 and isinstance(v2["sections"], dict)

    tables = []
    for sec in v2["sections"].values():
        for obj in (sec.get("objects") or []):
            if obj.get("type") == "table":
                tables.append(obj)
    assert tables, "no tables found in 06b v2"

    # There must be at least one logical_table_id that spans pages 0 and 1
    by_lid = {}
    for t in tables:
        lid = t.get("logical_table_id")
        if not lid:
            continue
        pval = t.get("page_index")
        if pval is None:
            pval = t.get("page", -1)
        p = int(pval if pval is not None else -1)
        if p < 0:
            continue
        by_lid.setdefault(lid, set()).add(p)
    spanning = {lid for lid, pages in by_lid.items() if {0, 1}.issubset(pages)}
    assert spanning, "no logical_table_id spans pages 0 and 1"

    # And at least one table carries the expected header_norm
    expected_hn = "signal|io|description|connection|type"
    assert any(t.get("header_norm") == expected_hn for t in tables), "expected header_norm not present"

    # 09a annotations: merged groups present
    ann = _load_json(RUN_DIR / "09a_pdf_annotator" / "json_output" / "annotations.json")
    summary = ann.get("summary") or {}
    assert int(summary.get("merged_table_groups", 0)) >= 1, "expected at least one merged table group"

    # Requirements miner: counts and conditional presence
    req_sum = _load_json(RUN_DIR / "07_requirements_miner" / "json_output" / "07_requirements_summary.json")
    total = int(req_sum.get("total_requirements", req_sum.get("total", 0)))
    assert total >= 12, "expected >=12 requirements"
    # Conditional requirement detection is stricter in live mode; in deterministic runs,
    # we only assert a healthy total count and leave conditional checks to live CI.
