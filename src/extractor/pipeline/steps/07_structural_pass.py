"""
Structural Pass (Stage 07 Core)
==============================

Deterministic, offline transformation:
  - Load Stage 04 sections, Stage 05 tables, Stage 06 figures, optional annotations.
  - Merge raw text blocks into paragraph blocks (hard-wrap to a max char budget).
  - Normalize table shapes (ensure pandas_df list[dict] when rows/columns present).
  - Attach figures pass-through.
  - Provide a stable reflowed_text per section and basic metrics.

Outputs a dict consumed by the Stage 07 orchestrator.
"""

from __future__ import annotations
import os
import json
import hashlib
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
        out_sec = {
            "id": sid,
            "title": sec.get("title") or sec.get("display_title") or "Untitled",
            "blocks": paras,
            "tables": tables_by_sec.get(str(sid), []),
            "figures": figures_by_sec.get(str(sid), []),
            "reflowed_text": reflow_text,
            "reflow_status": "structural_only" if summary_only else "structural_base",
        }
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

