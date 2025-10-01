from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional


def load_json(p: Path) -> Any:
    return json.loads(p.read_text(encoding="utf-8"))


def find_first_table_block(reflowed_json: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    blocks = reflowed_json.get("blocks") or []
    for b in blocks:
        if isinstance(b, dict) and b.get("type") == "table":
            return b
    return None


def compare_reflow_to_gold(reflow_path: Path, gold_path: Path) -> Dict[str, Any]:
    _out: Dict[str, Any] = {}
    data = load_json(reflow_path)
    gold = load_json(gold_path)
    sections = data.get("reflowed_sections") or []
    if not sections:
        return {"ok": False, "error": "no_sections"}
    rj = sections[0].get("reflowed_json") or {}
    tbl = find_first_table_block(rj)
    if not tbl:
        return {"ok": False, "error": "no_table_block"}
    ex_cols = [str(c) for c in (tbl.get("columns") or [])]
    gold_cols = [str(c) for c in (gold.get("columns") or [])]
    cols_ok = (ex_cols == gold_cols) if gold_cols else True
    title = str(tbl.get("title") or "")
    title_ok = ("inferred" in title.lower()) if gold.get("title_inferred", True) else True
    return {
        "ok": bool(cols_ok and title_ok),
        "columns_ok": cols_ok,
        "title_ok": title_ok,
        "extracted_columns": ex_cols,
        "gold_columns": gold_cols,
        "extracted_title": title,
    }


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--reflow", required=True)
    ap.add_argument("--gold", required=True)
    args = ap.parse_args()
    res = compare_reflow_to_gold(Path(args.reflow), Path(args.gold))
    print(json.dumps(res, indent=2, ensure_ascii=False))
