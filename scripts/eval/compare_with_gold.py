#!/usr/bin/env python3
from __future__ import annotations
import json, argparse
from pathlib import Path

def load_index_by_id(path: str):
    items = {}
    if not path:
        return items
    data = json.loads(Path(path).read_text())
    if isinstance(data, list):
        for rec in data:
            items[rec["object_id"]] = rec
    else:
        for rec in data.get("items", []):
            items[rec["object_id"]] = rec
    return items

def norm(s):
    return " ".join(str(s).split()).strip().lower()

def table_text_exact(pred_cells, gold_cells):
    gold_map = {(c["r"],c["c"]): norm(c["text"]) for c in gold_cells if "text" in c}
    pred_map = {(c["r"],c["c"]): norm(c["text"]) for c in pred_cells if "text" in c}
    shared = 0
    total = len(gold_map)
    for k,v in gold_map.items():
        if k in pred_map and pred_map[k] == v:
            shared += 1
    return (shared / total) if total else None

def main(a):
    gold_tables = load_index_by_id(a.gold_tables)
    pred_tables_path = Path(a.pred_tables)
    tables_obj = json.loads(pred_tables_path.read_text())
    pred_tables = tables_obj.get("tables", [])
    out = {"tables": []}
    for t in pred_tables:
        oid = f"table:p{int(t.get('page_index',0)):03d}:t{int(t.get('table_index',0)):02d}"
        if oid not in gold_tables:
            continue
        gold = gold_tables[oid]
        g_rows, g_cols = gold.get("rows"), gold.get("cols")
        p_rows, p_cols = t.get("row_count"), t.get("col_count")
        row_ok = (g_rows is None or p_rows is None) or abs(int(p_rows) - int(g_rows)) <= 1
        col_ok = (g_cols is None or p_cols is None) or abs(int(p_cols) - int(g_cols)) <= 1
        cell_exact = None
        if gold.get("cells") and t.get("pandas_df"):
            pcells = []
            for r_i, row in enumerate(t.get("pandas_df", [])):
                for c_i, (_, text) in enumerate(row.items()):
                    pcells.append({"r": r_i, "c": c_i, "text": text})
            cell_exact = table_text_exact(pcells, gold["cells"])
        out["tables"].append({
            "object_id": oid,
            "row_count_match": bool(row_ok),
            "col_count_match": bool(col_ok),
            "cell_text_exact": cell_exact
        })
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, indent=2))
    print(f"Wrote metrics to {a.out}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold-tables", required=True)
    ap.add_argument("--pred-tables", required=True)
    ap.add_argument("--out", default="evaluation/reports/tables_metrics.json")
    main(ap.parse_args())

