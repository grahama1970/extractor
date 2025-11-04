#!/usr/bin/env python3
"""
Analyze a live pipeline run directory and emit a concise report.
Inputs via env/args:
  OUT: path to the run dir (default: data/results/pipeline_live_ci)
Outputs:
  - Prints human-readable summary to stdout
  - Writes JSON + Markdown reports into scripts/artifacts/
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List


def _load_json(p: Path) -> Any:
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def analyze(out: Path) -> Dict[str, Any]:
    report: Dict[str, Any] = {"run_dir": str(out)}

    # 04 sections
    sec_p = out / "04_section_builder" / "json_output" / "04_sections.json"
    sec = _load_json(sec_p) or {}
    sections = sec.get("sections") or []
    base = min([s.get("level", 1) for s in sections], default=1)
    top = [s for s in sections if int(s.get("level", base)) == base]
    report["sections"] = {
        "top_level_count": len(top),
        "top_level_titles": [str(s.get("title") or "") for s in top],
    }

    # 05 tables
    t05_p = out / "05_table_extractor" / "json_output" / "05_tables.json"
    t05 = _load_json(t05_p) or {}
    tables = t05.get("tables") or []
    header_1x5 = None
    body_4x5 = None
    for t in tables:
        pm = t.get("pandas_metrics") or {}
        shp = pm.get("shape") or [0, 0]
        try:
            r, c = int(shp[0] or 0), int(shp[1] or 0)
        except Exception:
            r, c = 0, 0
        if r == 1 and c == 5 and int(t.get("page_index", -1)) in {0, 1}:
            header_1x5 = {
                "page_index": int(t.get("page_index", -1)),
                "bbox": t.get("bbox"),
            }
        if r == 4 and c == 5 and int(t.get("page_index", -1)) in {0, 1}:
            body_4x5 = {
                "page_index": int(t.get("page_index", -1)),
                "bbox": t.get("bbox"),
            }
    report["tables05"] = {"header_1x5": header_1x5, "body_4x5": body_4x5, "total": len(tables)}

    # 06b layout v2: merged logical groups
    v2_p = out / "06b_layout_sketcher" / "json_output" / "06b_layout_sketch_v2.json"
    v2 = _load_json(v2_p) or {"sections": {}}
    merged_groups: List[Dict[str, Any]] = []
    expected_hn = "signal|io|description|connection|type"
    spanning_p0p1 = False
    for s in (v2.get("sections") or {}).values():
        for o in (s.get("objects") or []):
            if o.get("type") != "table":
                continue
    # Build lid → pages mapping
    by_lid: Dict[str, set] = {}
    by_lid_hn: Dict[str, str] = {}
    for s in (v2.get("sections") or {}).values():
        for o in (s.get("objects") or []):
            if o.get("type") != "table":
                continue
            lid = o.get("logical_table_id")
            if not lid:
                continue
            p = o.get("page_index", o.get("page"))
            try:
                p = int(p if p is not None else -1)
            except Exception:
                p = -1
            if p < 0:
                continue
            by_lid.setdefault(lid, set()).add(p)
            if o.get("header_norm"):
                by_lid_hn[lid] = o.get("header_norm")
    for lid, pages in by_lid.items():
        if len(pages) > 1:
            merged_groups.append({"lid": lid, "pages": sorted(pages), "header_norm": by_lid_hn.get(lid)})
        if {0, 1}.issubset(pages):
            spanning_p0p1 = True
    report["sketch06b"] = {
        "merged_groups": merged_groups,
        "spans_p0_p1": spanning_p0p1,
    }

    # 09a annotations
    ann_p = out / "09a_pdf_annotator" / "json_output" / "annotations.json"
    ann = _load_json(ann_p) or {}
    merged = int((ann.get("summary") or {}).get("merged_table_groups", 0))
    pdf_path = out / "09a_pdf_annotator" / "annotated.pdf"
    report["annot09a"] = {
        "merged_table_groups": merged,
        "annotated_pdf_exists": pdf_path.exists(),
        "annotated_pdf_size": pdf_path.stat().st_size if pdf_path.exists() else 0,
    }

    # 07 requirements summary
    req_p = out / "07_requirements_miner" / "json_output" / "07_requirements_summary.json"
    req = _load_json(req_p) or {}
    report["requirements07"] = {
        "total": int(req.get("total_requirements", req.get("total", 0)) or 0),
        "conditional": int(
            req.get("conditional_requirements")
            or req.get("conditional")
            or req.get("with_condition", 0)
            or 0
        ),
    }

    return report


def write_reports(rep: Dict[str, Any]) -> None:
    out_dir = Path("scripts/artifacts")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "live_run_report.json").write_text(json.dumps(rep, indent=2), encoding="utf-8")
    # Minimal markdown summary
    md = [
        f"Run dir: {rep.get('run_dir')}",
        "",
        f"Sections (top-level): {rep.get('sections',{}).get('top_level_count')} — "
        + ", ".join(rep.get("sections", {}).get("top_level_titles", []) or []),
        f"06b merged groups: {len(rep.get('sketch06b',{}).get('merged_groups', []))} (p0→p1={rep.get('sketch06b',{}).get('spans_p0_p1')})",
        f"09a merged_table_groups: {rep.get('annot09a',{}).get('merged_table_groups')} (pdf={rep.get('annot09a',{}).get('annotated_pdf_exists')})",
        f"Requirements: total={rep.get('requirements07',{}).get('total')} conditional={rep.get('requirements07',{}).get('conditional')}",
    ]
    (out_dir / "live_run_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")


if __name__ == "__main__":
    out = Path(os.environ.get("OUT", "data/results/pipeline_live_ci"))
    rep = analyze(out)
    write_reports(rep)
    # Print to stdout for quick inspection
    print(json.dumps(rep, indent=2))
