#!/usr/bin/env python3
"""
extract_table_features.py

Given a Stage 05 tables JSON file, produce a mapping from table object_id -> feature vector.
This decouples runtime feature computation from annotation time (supports recomputation after code changes).
"""

from __future__ import annotations
import json, argparse, hashlib
from pathlib import Path
from typing import Dict, Any

FEATURE_ORDER = [
    "fragmentation",
    "header_jaccard_max",
    "numeric_stability",
    "row_count",
    "col_count",
    "strategy_diversity",
    "merge_type_header_body",
    "foreign_numeric_ratio",
]


def features_from_table(t: Dict[str, Any]) -> Dict[str, float]:
    c = t.get("confidence", {}) or {}
    fusion = t.get("fusion", {}) or {}
    rank = fusion.get("rank_features", {}) or {}
    merge_type = (c.get("merge_type") or "").strip()
    foreign_numeric_ratio = float(rank.get("foreign_numeric_ratio", 0.0) or 0.0)
    return {
        "fragmentation": int(c.get("fragmentation", 0) or 0),
        "header_jaccard_max": float(c.get("header_jaccard", 0.0) or 0.0),
        "numeric_stability": float(c.get("numeric_stability", 1.0) or 1.0),
        "row_count": int(t.get("row_count", 0) or 0),
        "col_count": int(t.get("col_count", 0) or 0),
        "strategy_diversity": int(len(list(set(c.get("source_strategies", []) or [])))),
        "merge_type_header_body": 1 if merge_type == "header_body_merge" else 0,
        "foreign_numeric_ratio": foreign_numeric_ratio,
    }


def hash_features(feat: Dict[str, float]) -> str:
    raw = json.dumps(feat, sort_keys=True).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def main(args):
    data = json.loads(Path(args.tables_json).read_text())
    out = {}
    for t in data.get("tables", []):
        page_index = int(t.get("page_index", 0) or 0)
        index = int(t.get("table_index", 1) or 1)
        object_id = f"table:p{page_index:03d}:t{index:02d}"
        feat = features_from_table(t)
        out[object_id] = {
            "features": feat,
            "features_hash": hash_features(feat),
        }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(
        json.dumps({"feature_order": FEATURE_ORDER, "tables": out}, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote features for {len(out)} tables to {args.out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tables-json", required=True)
    ap.add_argument("--out", default="training/derived/table_features.json")
    main(ap.parse_args())

