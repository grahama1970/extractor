#!/usr/bin/env python3
from __future__ import annotations
import json, sys
from pathlib import Path
from typing import Any, Dict

def _load(p: Path) -> Any:
    try:
        return json.loads(p.read_text())
    except Exception:
        return None

def main(out_dir: str) -> int:
    base = Path(out_dir)
    sec = _load(base/"04_section_builder/json_output/04_sections.json") or {}
    tab = _load(base/"05_table_extractor/json_output/05_tables.json") or {}
    fig = _load(base/"06_figure_extractor/json_output/06_figures.json") or {}
    r07 = _load(base/"07_reflow_section/json_output/07_reflowed.json") or {}
    h03 = _load(base/"03_suspicious_headers/json_output/03_verified_blocks.json") or {}
    ann = _load(base/"09a_pdf_annotator/json_output/annotations.json") or {}

    sections = sec.get("sections") or []
    tables = tab.get("tables") or []
    figures = fig.get("figures") or []
    reflow = r07.get("reflowed_sections") or r07.get("sections") or []
    headers = h03.get("blocks") or []
    overlays = ann.get("overlays") or []

    # Metrics
    m: Dict[str, Any] = {}
    m["sections.count"] = len(sections)
    m["tables.count"] = len(tables)
    m["figures.count"] = len(figures)
    m["figures.described.count"] = sum(1 for f in figures if (f.get("ai_description") or f.get("description")))
    m["headers.suspicious.count"] = sum(1 for b in headers if b.get("suspicious_header") or b.get("is_suspicious"))
    m["reflow.sections.count"] = len(reflow)
    m["overlay.boxes.count"] = len(overlays)

    # LLM success proxy: scan 07 sections for reflow_status
    m["reflow.success.count"] = sum(1 for s in reflow if s.get("reflow_status") == "success")

    # Compose brief assessment
    m["assessment"] = {
        "figures_described_ratio": (m["figures.described.count"] / m["figures.count"]) if m["figures.count"] else 0.0,
        "reflow_success_ratio": (m["reflow.success.count"] / m["reflow.sections.count"]) if m["reflow.sections.count"] else 0.0,
    }

    out = base/"artifacts"/"pipeline_eval_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(m, indent=2))
    print(out)
    return 0

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: pipeline_eval_report.py <results_dir>")
        sys.exit(2)
    sys.exit(main(sys.argv[1]))

