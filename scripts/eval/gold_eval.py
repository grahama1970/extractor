#!/usr/bin/env python3
"""
Gold Set Evaluation (scaffold)

Inputs:
  --reflow   path to 07e_reflowed.json
  --gold     path to gold JSON (see schema below)

Gold schema (minimal):
{
  "sections": [{"id":"s1","title":"..","pages":[..]}],
  "tables": [{"section_id":"s2","header_tokens":["bht_update_i","bht_prediction_o"]}],
  "continuity_expectations": [{"from_section":"sec0","to_section":"sec1","label":"table/4-1"}]
}

Outputs:
  Prints simple precision/recall for sections and continuity checks; returns non‑zero on failure.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List


def main(reflow_path: Path, gold_path: Path) -> int:
    reflow = json.loads(reflow_path.read_text())
    gold = json.loads(gold_path.read_text())

    # Sections
    ref_ids = {s.get("id") or s.get("section_id") for s in reflow.get("reflowed_sections", [])}
    gold_ids = {s.get("id") for s in gold.get("sections", [])}
    tp = len(ref_ids & gold_ids); fp = len(ref_ids - gold_ids); fn = len(gold_ids - ref_ids)
    prec = tp / max(1, tp + fp); rec = tp / max(1, tp + fn)

    # Continuity expectations
    cont_ok = True
    cont_reqs = gold.get("continuity_expectations", [])
    sec_map: Dict[str, Dict[str, Any]] = {s.get("id") or s.get("section_id"): s for s in reflow.get("reflowed_sections", [])}
    for c in cont_reqs:
        to_section = sec_map.get(c.get("to_section"))
        if not to_section:
            cont_ok = False; continue
        label = c.get("label")
        tables = [b for b in to_section.get("reflowed_json", {}).get("blocks", []) if b.get("type") == "table"]
        if label and not any(t.get("normalized_label") == label for t in tables):
            cont_ok = False

    print(json.dumps({"sections":{"precision":prec,"recall":rec},"continuity_ok":cont_ok}, indent=2))
    return 0 if cont_ok else 1


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: gold_eval.py RELOW_JSON GOLD_JSON", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(Path(sys.argv[1]), Path(sys.argv[2])))

