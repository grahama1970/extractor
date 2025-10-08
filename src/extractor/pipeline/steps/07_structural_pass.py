"""
Structural Pass (Stage 07 Core)
===============================

Deterministic, offline transformation:
  - Load Stage 04 sections, Stage 05 tables, Stage 06 figures, optional annotations.
  - Merge raw text blocks into paragraph blocks (hard-wrap to a max char budget).
  - Normalize table shapes (ensure pandas_df list[dict] when rows/columns present).
  - (Optional) Score & merge obvious multi-page / fragmented tables (configurable modes).
  - Attach figures pass-through.
  - Provide stable reflowed_text + section/table hashes & merge diagnostics.

Env Flags:
  STAGE07_MAX_PARAGRAPH_CHARS          (int, default 800)
  STAGE07_TABLE_MERGE_MODE             off|strict|assist|llm (default strict)
  STAGE07_TABLE_MERGE_HARD             float (default 0.75)
  STAGE07_TABLE_MERGE_SOFT             float (default 0.45)
  STAGE07_TABLE_MERGE_MAX_ROWS         int (default 10000)

Outputs: dict consumed by orchestrator.
"""

from __future__ import annotations
import os, json, hashlib, math
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _split_preserving_words(text: str, max_chars: int) -> List[str]:
    if len(text) <= max_chars:
        return [text]
    words = text.split()
    out: List[str] = []
    cur: List[str] = []
    cur_len = 0
    for w in words:
        wl = len(w) + (1 if cur else 0)
        if cur_len + wl > max_chars and cur:
            out.append(" ".join(cur))
            cur = [w]
            cur_len = len(w)
        else:
            cur.append(w)
            cur_len += wl
    if cur:
        out.append(" ".join(cur))
    return out


def _merge_text_blocks(blocks: List[Dict[str, Any]], max_para_chars: int) -> List[Dict[str, Any]]:
    paras: List[Dict[str, Any]] = []
    buf: List[str] = []
    pages: List[int] = []
    ids: List[str] = []

    def flush():
        if not buf:
            return
        text = " ".join(buf).strip()
        if text:
            paras.append({
                "type": "paragraph",
                "text": text,
                "source": {
                    "pages": sorted({p for p in pages if isinstance(p, int)}),
                    "block_ids": ids,
                },
            })
        buf.clear()
        pages.clear()
        ids.clear()

    for b in blocks or []:
        btype = b.get("block_type") or b.get("type")
        text = (b.get("text") or "").strip()
        if btype in {"Text", "text", "Paragraph", "paragraph", "ListItem", "listitem"} and text:
            for chunk in _split_preserving_words(text, max_para_chars):
                if len(" ".join(buf + [chunk])) > max_para_chars:
                    flush()
                buf.append(chunk)
                try:
                    pages.append(int(b.get("page", b.get("page_idx", -1))))
                except Exception:
                    pass
                bid = b.get("id") or b.get("block_id")
                if bid:
                    ids.append(str(bid))
        else:
            flush()
    flush()
    return paras


def _canonicalize_table(table: Dict[str, Any]) -> Dict[str, Any]:
    pdf = table.get("pandas_df")
    if isinstance(pdf, list):
        return table
    if table.get("rows") and table.get("columns"):
        rows = table.get("rows")
        cols = table.get("columns")
        if isinstance(rows, list) and isinstance(cols, list):
            pd_rows: List[Dict[str, Any]] = []
            for r in rows:
                if isinstance(r, list):
                    pd_rows.append({str(c): (r[i] if i < len(r) else "") for i, c in enumerate(cols)})
            table["pandas_df"] = pd_rows
    return table

# ---------------- Table Merge Scoring ----------------

def _table_header_similarity(t1: Dict[str, Any], t2: Dict[str, Any]) -> float:
    import re
    cols1 = (t1.get("pandas_metrics") or {}).get("columns") or t1.get("columns") or []
    cols2 = (t2.get("pandas_metrics") or {}).get("columns") or t2.get("columns") or []
    if not cols1 or not cols2:
        return 0.0
    n1 = {re.sub(r"\s+", " ", str(c)).lower() for c in cols1 if c}
    n2 = {re.sub(r"\s+", " ", str(c)).lower() for c in cols2 if c}
    inter = len(n1 & n2)
    union = len(n1 | n2)
    return float(inter / union) if union else 0.0

def _table_iou_x(t1: Dict[str, Any], t2: Dict[str, Any]) -> float:
    try:
        ax0, _, ax1, _ = t1.get("bbox", [0,0,0,0])
        bx0, _, bx1, _ = t2.get("bbox", [0,0,0,0])
        inter = max(0.0, min(ax1, bx1) - max(ax0, bx0))
        uni = max(ax1, bx1) - min(ax0, bx0)
        return inter / uni if uni > 0 else 0.0
    except Exception:
        return 0.0

def _rows_cols(t: Dict[str, Any]) -> tuple[int,int]:
    pm = t.get("pandas_metrics") or {}
    shape = pm.get("shape") or [0,0]
    try:
        return int(shape[0] or 0), int(shape[1] or 0)
    except Exception:
        return 0,0

def _page_index(t: Dict[str, Any]) -> int:
    try:
        return int(t.get("page_index", t.get("page", 0)) or 0)
    except Exception:
        return 0

def _score_pair(t1: Dict[str, Any], t2: Dict[str, Any]) -> tuple[float, Dict[str, Any]]:
    p1, p2 = _page_index(t1), _page_index(t2)
    page_delta = p2 - p1
    r1, c1 = _rows_cols(t1)
    r2, c2 = _rows_cols(t2)
    header_sim = _table_header_similarity(t1, t2)
    iou_x = _table_iou_x(t1, t2)
    role_score = 0.0
    if (r1 <= 2 and r2 >= 2) or (r2 <= 2 and r1 >= 2):
        role_score = 1.0
    elif r1 >= 2 and r2 >= 2:
        role_score = 0.6
    page_prox = 1.0 if p1 == p2 else (0.5 if page_delta == 1 else 0.0)
    score = (
        0.40 * header_sim +
        0.25 * iou_x +
        0.20 * page_prox +
        0.15 * role_score
    )
    features = {
        "page_delta": page_delta,
        "header_similarity": round(header_sim,4),
        "iou_x": round(iou_x,4),
        "row_pattern_score": role_score,
        "r1": r1, "r2": r2, "c1": c1, "c2": c2
    }
    return round(score,4), features

def _merge_tables_scored(section_id: str,
                         tables: List[Dict[str, Any]],
                         mode: str,
                         hard: float,
                         soft: float,
                         max_rows_cap: int) -> tuple[List[Dict[str, Any]], List[Dict[str,Any]], List[Dict[str,Any]]]:
    """
    Returns (final_tables, auto_merged_records, candidate_records)
      auto_merged_records: scored pairs actually merged (strict mode)
      candidate_records  : ambiguous pairs (score in [soft, hard)) or auto merges (for auditing)
    Modes:
      off    : no scoring / merging
      strict : merge if score>=hard, mark ambiguous for soft<=score<hard
      assist : never merge, collect ambiguous (soft<=score)
      llm    : same as assist; later plugin adjudicates
    """
    if len(tables) <= 1 or mode == "off":
        return tables, [], []
    # Sort by page, then table_index
    def _key(t): return (_page_index(t), int(t.get("table_index",0) or 0))
    working = sorted(tables, key=_key)
    auto_merged: List[Dict[str, Any]] = []
    candidates: List[Dict[str, Any]] = []
    i = 0
    while i < len(working) - 1:
        t1, t2 = working[i], working[i+1]
        score, feats = _score_pair(t1, t2)
        decision = "reject"
        if score >= hard:
            decision = "auto_merge" if mode == "strict" else "ambiguous"
        elif score >= soft:
            decision = "ambiguous"
        record = {
            "section_id": section_id,
            "t1_index": i,
            "t2_index": i+1,
            "score": score,
            "decision": decision,
            "features": feats,
            "orig_table_index_t1": t1.get("table_index"),
            "orig_table_index_t2": t2.get("table_index"),
        }
        if decision in {"auto_merge","ambiguous"}:
            candidates.append(record)
        if decision == "auto_merge":
            # Attempt merge
            r1, c1 = _rows_cols(t1)
            r2, c2 = _rows_cols(t2)
            df1 = t1.get("pandas_df") or []
            df2 = t2.get("pandas_df") or []
            if c1 == c2 and c1 > 0:
                if (r1 <= 2 and r2 >= 2) and df1 and df2:
                    # header adoption case
                    if isinstance(df1[0], dict) and isinstance(df2[0], dict):
                        hdr_vals = list(df1[0].values())
                        body_keys = list(df2[0].keys())
                        if len(body_keys) == len(hdr_vals):
                            new_cols = [str(v).strip() or f"col_{j}" for j,v in enumerate(hdr_vals)]
                            new_body = []
                            for row in df2:
                                new_body.append({new_cols[idx]: row.get(body_keys[idx], "") for idx in range(len(new_cols))})
                            t2["pandas_df"] = new_body
                            t2.setdefault("pandas_metrics", {})["columns"] = new_cols
                            auto_merged.append(record | {"merge_type":"header_body"})
                            working.pop(i)  # drop header fragment, stay at same index
                            continue
                # body/body concat
                if r1 >= 2 and r2 >= 2 and df1 and df2 and isinstance(df1[0], dict) and isinstance(df2[0], dict):
                    keys1 = list(df1[0].keys()); keys2 = list(df2[0].keys())
                    if keys1 == keys2:
                        merged_rows = df1 + df2
                        if len(merged_rows) <= max_rows_cap:
                            t1["pandas_df"] = merged_rows
                            t1.setdefault("pandas_metrics", {})["shape"] = [len(merged_rows), len(keys1)]
                            auto_merged.append(record | {"merge_type":"body_body"})
                            working.pop(i+1)
                            continue
        i += 1
    return working, auto_merged, candidates


def build_structural_reflow(
    *,
    sections_path: Path,
    tables_path: Path,
    figures_path: Path,
    annotations_path: Optional[Path],
    summary_only: bool,
) -> Dict[str, Any]:
    s04 = _read_json(sections_path)
    s05 = _read_json(tables_path)
    s06 = _read_json(figures_path)
    sections_raw = s04.get("sections") or []
    tables_raw = s05.get("tables") or []
    figures_raw = s06.get("figures") or []

    tables_by_sec: Dict[str, List[Dict[str, Any]]] = {}
    for t in tables_raw:
        sid = t.get("section_id")
        if sid:
            tables_by_sec.setdefault(str(sid), []).append(_canonicalize_table(t))

    figures_by_sec: Dict[str, List[Dict[str, Any]]] = {}
    for f in figures_raw:
        sid = f.get("section_id")
        if sid:
            figures_by_sec.setdefault(str(sid), []).append(f)

    max_para_chars = int(os.getenv("STAGE07_MAX_PARAGRAPH_CHARS", "800"))

    processed: List[Dict[str, Any]] = []
    total_chars_raw = 0
    total_chars_reflow = 0

    for sec in sections_raw:
        if not isinstance(sec, dict):
            continue
        sid = sec.get("id") or sec.get("section_id") or f"sec_{len(processed)}"
        blocks = sec.get("blocks", [])
        paras = _merge_text_blocks(blocks, max_para_chars)
        raw_text = " ".join((b.get("text") or "").strip() for b in blocks if (b.get("text") or "").strip())
        reflow_text = " ".join(p.get("text") for p in paras)
        total_chars_raw += len(raw_text)
        total_chars_reflow += len(reflow_text)
        raw_tables = tables_by_sec.get(str(sid), [])
        merge_mode = os.getenv("STAGE07_TABLE_MERGE_MODE", "strict").lower()
        hard = float(os.getenv("STAGE07_TABLE_MERGE_HARD", "0.75"))
        soft = float(os.getenv("STAGE07_TABLE_MERGE_SOFT", "0.45"))
        max_rows_cap = int(os.getenv("STAGE07_TABLE_MERGE_MAX_ROWS", "10000"))
        merged_tables, auto_records, cand_records = _merge_tables_scored(
            str(sid), raw_tables, merge_mode, hard, soft, max_rows_cap
        )
        # Hash tables & enrich metadata
        finalized_tables: List[Dict[str, Any]] = []
        for t in merged_tables:
            cols = (t.get("pandas_metrics") or {}).get("columns") or t.get("columns") or []
            # preview hash (first 3 rows)
            preview = []
            for r in (t.get("pandas_df") or [])[:3]:
                if isinstance(r, dict):
                    preview.append([str(r.get(c,"")) for c in cols])
            th = hashlib.sha256(json.dumps({"c": cols, "p": preview}, ensure_ascii=False).encode("utf-8")).hexdigest()
            page_idx = _page_index(t)
            t["page_span"] = [page_idx]
            t["row_count"], t["col_count"] = len(t.get("pandas_df") or []), len(cols)
            t["table_id"] = f"table/{page_idx}-{page_idx}-{th[:8]}"
            t["table_hash"] = th
            finalized_tables.append(t)
        out_sec = {
            "id": sid,
            "title": sec.get("title") or sec.get("display_title") or "Untitled",
            "blocks": paras,
            "tables": finalized_tables,
            "figures": figures_by_sec.get(str(sid), []),
            "reflowed_text": reflow_text,
            "reflow_status": "structural_only" if summary_only else "structural_base",
            "table_merge": {
                "mode": merge_mode,
                "auto_merged": auto_records,
                "candidates": cand_records,
                "thresholds": {"hard": hard, "soft": soft},
            }
        }
        # Section hash
        try:
            sh = hashlib.sha256()
            for p in paras:
                sh.update((p.get("text") or "").encode("utf-8","ignore"))
            for t in finalized_tables:
                sh.update((t.get("table_id") or "").encode("utf-8"))
            out_sec["section_hash"] = sh.hexdigest()
        except Exception:
            out_sec["section_hash"] = None
        processed.append(out_sec)

    h = hashlib.sha256()
    for s in processed:
        h.update((str(s.get("id", "")) + ":" + (s.get("reflowed_text") or "")[:64]).encode("utf-8", "ignore"))

    metrics = {
        "sections": len(processed),
        "raw_chars": total_chars_raw,
        "reflow_chars": total_chars_reflow,
        "char_retention_ratio": round(total_chars_reflow / total_chars_raw, 4) if total_chars_raw else None,
    }
    return {
        "sections": processed,
        "metrics": metrics,
        "diagnostics": [],
        "run_id": datetime.now().strftime("%Y%m%d%H%M%S"),
        "hash": h.hexdigest(),
    }
