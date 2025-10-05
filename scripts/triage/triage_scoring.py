#!/usr/bin/env python3
"""
Compute triage queues (ELS = error-likelihood score) for machine-first, human-selective review.

Reads Stage 05 tables and writes a ranked queue JSON for UI/API consumption.

Inputs (defaults):
  data/results/pipeline/05_table_extractor/json_output/05_tables.json

Outputs:
  data/results/pipeline/triage_queue/tables.json

ELS heuristic for tables (numeric_recall currently omitted unless present in rank_features):
  uncertainty     = 1 - |structure_prob - 0.5| * 2
  frag_norm       = min(fragmentation/8, 1)
  numeric_penalty = max(0, (0.95 - numeric_recall)/0.95) if available else 0
  foreign_penalty = clamp((foreign_numeric_ratio - 0.02)/0.08, 0, 1)
  header_penalty  = 1 if (merge_type == header_body_merge and header_jaccard < 0.5) else 0

  ELS = 0.40*uncertainty + 0.20*frag_norm + 0.20*numeric_penalty 
        + 0.10*foreign_penalty + 0.10*header_penalty
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple


def _clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def compute_table_els(t: Dict[str, Any]) -> Tuple[float, Dict[str, float]]:
    c = t.get("confidence", {}) or {}
    fusion_feats = (t.get("fusion") or {}).get("rank_features", {}) or {}
    structure_prob = c.get("structure_prob")
    if structure_prob is None:
        structure_prob = 0.5
    uncertainty = 1 - abs(float(structure_prob) - 0.5) * 2
    fragmentation = min(float(c.get("fragmentation", 0) or 0) / 8.0, 1.0)
    # optional numeric_recall (set by section audit wiring if later propagated into tables)
    numeric_recall = fusion_feats.get("numeric_recall")
    if numeric_recall is None:
        numeric_penalty = 0.0
    else:
        numeric_penalty = max(0.0, (0.95 - float(numeric_recall)) / 0.95)
    foreign_ratio = float(fusion_feats.get("foreign_numeric_ratio", 0.0) or 0.0)
    foreign_penalty = _clamp((foreign_ratio - 0.02) / 0.08, 0.0, 1.0)
    header_jaccard = float(c.get("header_jaccard", 1.0) or 1.0)
    merge_type = (c.get("merge_type") or "").strip()
    header_penalty = 1.0 if (merge_type == "header_body_merge" and header_jaccard < 0.5) else 0.0

    els = (
        0.40 * uncertainty
        + 0.20 * fragmentation
        + 0.20 * numeric_penalty
        + 0.10 * foreign_penalty
        + 0.10 * header_penalty
    )
    els = round(_clamp(els, 0.0, 1.0), 4)
    reasons = {
        "uncertainty": round(uncertainty, 3),
        "fragmentation": round(fragmentation, 3),
        "numeric_penalty": round(numeric_penalty, 3),
        "foreign_penalty": round(foreign_penalty, 3),
        "header_penalty": header_penalty,
    }
    return els, reasons


def _band(els: float) -> str:
    if els >= 0.65:
        return "high"
    if els >= 0.40:
        return "medium"
    if els >= 0.20:
        return "low"
    return "very_low"


def main() -> int:
    tables_path = Path("data/results/pipeline/05_table_extractor/json_output/05_tables.json")
    if not tables_path.exists():
        print(f"No tables file: {tables_path}")
        return 1
    data = json.loads(tables_path.read_text())
    out_items: List[Dict[str, Any]] = []
    for t in data.get("tables", []):
        page_index = int(t.get("page_index", 0) or 0)
        index = int(t.get("table_index", 1) or 1)
        object_id = f"table:p{page_index:03d}:t{index:02d}"
        els, reasons = compute_table_els(t)
        out_items.append(
            {
                "object_id": object_id,
                "els": els,
                "band": _band(els),
                "reasons": reasons,
                "page_index": page_index,
            }
        )
    out_items.sort(key=lambda x: (x["els"], x["page_index"]), reverse=True)
    out_dir = Path("data/results/pipeline/triage_queue")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "tables.json"
    payload = {"generated_at": os.environ.get("RUN_TIMESTAMP"), "items": out_items}
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote triage queue: {out_path} (items={len(out_items)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
