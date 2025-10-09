#!/usr/bin/env python3
"""
Summarize per-section numeric recall/precision from Stage 07 output.

Reads: data/results/pipeline/07_reflow_section/json_output/07_reflowed.json
Writes: data/results/pipeline/07_reflow_section/json_output/numeric_recall_summary.json
Prints a brief text summary to stdout.
"""
from __future__ import annotations
import json
from pathlib import Path

def main() -> int:
    base = Path("data/results/pipeline/07_reflow_section/json_output")
    src = base / "07_reflowed.json"
    if not src.exists():
        print(f"No file: {src}")
        return 1
    data = json.loads(src.read_text())
    sections = data.get("reflowed_sections", [])
    rows = []
    recalls = []
    for s in sections:
        md = s.get("metadata") or {}
        na = md.get("numeric_audit") or {}
        rec = na.get("recall")
        prec = na.get("precision")
        rows.append({
            "id": s.get("id"),
            "title": (s.get("title") or "").strip(),
            "recall": rec,
            "precision": prec,
            "orig_nums": na.get("original_numeric_count"),
            "reflow_nums": na.get("reflow_numeric_count"),
            "missing_samples": na.get("missing_samples") or [],
            "extra_samples": na.get("extra_samples") or [],
        })
        if isinstance(rec, (int, float)):
            recalls.append(float(rec))
    summary = {
        "sections": rows,
        "count": len(rows),
        "recall_avg": round(sum(recalls)/len(recalls), 4) if recalls else None,
        "recall_min": round(min(recalls), 4) if recalls else None,
        "recall_max": round(max(recalls), 4) if recalls else None,
    }
    out = base / "numeric_recall_summary.json"
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"numeric_recall_summary: count={summary['count']} avg={summary['recall_avg']} min={summary['recall_min']} max={summary['recall_max']}")
    print(f"saved: {out}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

