#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///

"""
Verify live pipeline outputs for CI (LLM-inclusive run).

Checks:
- timings_summary.json exists and total_ms > 0
- 07_reflow_section/json_output/07_reflowed.json exists and has reflowed_sections or sections
- 09a_pdf_annotator/annotated.pdf exists
- 09a_pdf_annotator/json_output/annotations.json exists and total_overlays >= by_kind.section + by_kind.table
  (not strict, but sanity checks presence)
Exits non-zero on failure.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True, help="Pipeline output directory")
    args = ap.parse_args()
    out = args.out

    # timings summary
    ts = out / "timings_summary.json"
    assert ts.exists(), f"Missing timings_summary.json at {ts}"
    tdata = json.loads(ts.read_text())
    assert int(tdata.get("total_ms", 0)) > 0, "Expected total_ms > 0 in timings_summary.json"

    # reflowed json (Stage 07)
    rj = out / "07_reflow_section" / "json_output" / "07_reflowed.json"
    assert rj.exists(), f"Missing reflowed.json at {rj} (Stage 07)"
    rdata = json.loads(rj.read_text())
    rs = rdata.get("reflowed_sections") or rdata.get("sections") or []
    assert isinstance(rs, list) and len(rs) >= 1, "Expected at least one reflowed section"

    # Stage 05 and 06 raw counts (deterministic expectations per CONTRACT.md)
    t05 = out / "05_table_extractor" / "json_output" / "05_tables.json"
    f06 = out / "06_figure_extractor" / "json_output" / "06_figures.json"
    assert t05.exists(), f"Missing 05_tables.json at {t05}"
    assert f06.exists(), f"Missing 06_figures.json at {f06}"
    d05 = json.loads(t05.read_text())
    d06 = json.loads(f06.read_text())
    raw_tables = len((d05 or {}).get("tables", []))
    raw_figs = len((d06 or {}).get("figures", [])) if isinstance(d06, dict) else 0

    # Live fixture acceptance (BHT_* expectations)
    # Sections: exactly 3
    assert len(rs) == 3, f"Expected exactly 3 reflowed sections, got {len(rs)}"

    # Tables: merged logical count == 5; best-effort grouping by logical_table_id or header_norm
    def iter_table_blocks():
        for s in rs:
            for b in (s.get("reflowed_json", {}) or {}).get("blocks", []):
                if (b.get("type") or b.get("kind")) == "table":
                    yield b

    table_blocks = list(iter_table_blocks())
    # If table_blocks are embedded per-section, total logical tables should be 5
    # Try grouping via logical_table_id if present, else header_norm/title as fallback
    keys = []
    for tb in table_blocks:
        lid = tb.get("logical_table_id")
        hdr = (tb.get("header_norm") or tb.get("title") or "").strip().lower()
        key = lid or hdr or str(tb.get("id") or tb.get("table_id") or "t")
        keys.append(key)
    unique_keys = set(keys)
    unique_tables = len(unique_keys) if keys else 0
    assert unique_tables == 5, f"Expected 5 logical tables after merge; got {unique_tables} (raw={raw_tables})"
    # Count merged groups (appear on >1 page)
    def table_pages_for_key(k: str) -> set[int]:
        pages: set[int] = set()
        for s in rs:
            for b in (s.get("reflowed_json", {}) or {}).get("blocks", []):
                if (b.get("type") or b.get("kind")) != "table":
                    continue
                lid = b.get("logical_table_id")
                hdr = (b.get("header_norm") or b.get("title") or "").strip().lower()
                key = str(lid or hdr or b.get("id") or b.get("table_id") or "t")
                if key != k:
                    continue
                bids = ((b.get("source") or {}).get("block_ids") or [])
                for bid in bids:
                    t = (out / "02_marker_extractor" / "json_output" / "02_marker_blocks.json")
                    # We already validated 02 exists; load once outside loop would be nicer, but keep simple here
        # Load stage 02 once
    s02 = json.loads((out / "02_marker_extractor" / "json_output" / "02_marker_blocks.json").read_text())
    block_lookup = {str(b.get("id") or b.get("block_id")): b for b in s02.get("blocks", [])}
    def pages_for_block_ids(ids):
        p = set()
        for bid in ids:
            blk = block_lookup.get(str(bid))
            if not blk:
                continue
            pg = blk.get("page") if blk.get("page") is not None else blk.get("page_idx")
            try:
                pg = int(pg)
            except Exception:
                continue
            p.add(pg)
        return p
    merged_count = 0
    for k in unique_keys:
        pages = set()
        for s in rs:
            for b in (s.get("reflowed_json", {}) or {}).get("blocks", []):
                if (b.get("type") or b.get("kind")) != "table":
                    continue
                lid = b.get("logical_table_id")
                hdr = (b.get("header_norm") or b.get("title") or "").strip().lower()
                key = str(lid or hdr or b.get("id") or b.get("table_id") or "t")
                if key != k:
                    continue
                pages |= pages_for_block_ids(((b.get("source") or {}).get("block_ids") or []))
        if len(pages) > 1:
            merged_count += 1
    assert merged_count == 1, f"Expected exactly 1 merged logical table group (spanning >1 page), got {merged_count}"
    assert unique_tables - merged_count == 4, f"Expected 4 unmerged logical tables, got {unique_tables - merged_count}"

    # Requirements: ≥ 12 total, ≥ 2 conditional
    r07 = out / "07_requirements_miner" / "json_output" / "07_requirements.json"
    assert r07.exists(), f"Missing 07_requirements.json at {r07}"
    d07 = json.loads(r07.read_text())
    reqs = d07.get("requirements", [])
    conds = [r for r in reqs if (r.get("is_conditional") or "conditional" in str(r.get("category", "")).lower())]
    assert len(reqs) >= 12, f"Expected ≥12 requirements, got {len(reqs)}"
    assert len(conds) >= 2, f"Expected ≥2 conditional requirements, got {len(conds)}"

    # annotator
    annotated = out / "09a_pdf_annotator" / "annotated.pdf"
    assert annotated.exists(), f"Missing annotated.pdf at {annotated}"
    ann_json = out / "09a_pdf_annotator" / "json_output" / "annotations.json"
    assert ann_json.exists(), f"Missing annotations.json at {ann_json}"
    aj = json.loads(ann_json.read_text())
    summ = aj.get("summary", {})
    total = int(summ.get("total_overlays", 0))
    byk = {str(k): int(v) for k, v in (summ.get("by_kind", {}) or {}).items()}
    assert total >= (byk.get("section", 0) + byk.get("table", 0)), "Overlay total sanity check failed"
    # Figure overlay present (fixture says 1 figure exists)
    assert raw_figs >= 1, "Fixture expects ≥1 figure in Stage 06"
    assert byk.get("figure", 0) >= 1, "Expected at least 1 figure overlay in 09a"

    print("live verify: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
