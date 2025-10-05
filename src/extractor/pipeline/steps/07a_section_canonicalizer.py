#!/usr/bin/env python3
from __future__ import annotations

import json
import hashlib
import os
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Iterable

import typer
from loguru import logger


app = typer.Typer(help="07a: Canonicalize sections, attach tables/figures, continuity merges, compute hashes.")


def _load_json(p: Path) -> Dict[str, Any]:
    return json.loads(p.read_text())


def _sec_key(sec: Dict[str, Any]) -> Tuple[int, float, float]:
    bx = sec.get("bbox") or [0, 0, 0, 0]
    return (
        int(sec.get("page_start", 0)),
        float(bx[1]) if len(bx) >= 2 else 0.0,
        float(bx[0]) if len(bx) >= 1 else 0.0,
    )


def _03_annotations_hash(verified03: Optional[Path], section: Dict[str, Any]) -> Optional[str]:
    if not verified03 or not verified03.exists():
        return None
    try:
        payload = _load_json(verified03)
        blocks = payload.get("blocks", []) or []
        ps = int(section.get("page_start", 0))
        pe = int(section.get("page_end", ps))
        # Collect only those on same pages; sort by (page_idx, y0, x0)
        items = []
        for b in blocks:
            p = b.get("page_idx")
            if p is None or not (ps <= int(p) <= pe):
                continue
            bb = b.get("bbox") or [0, 0, 0, 0]
            try:
                y0 = round(float(bb[1]), 2)
                x0 = round(float(bb[0]), 2)
            except Exception:
                y0 = 0.0
                x0 = 0.0
            fbt = (b.get("llm_verification") or {}).get("result", {}).get("is_header")
            items.append(
                (
                    int(p),
                    y0,
                    x0,
                    b.get("block_type"),
                    bool(fbt) if fbt is not None else None,
                    b.get("normalized_header_text"),
                )
            )
        items.sort()
        h = hashlib.sha256()
        for it in items:
            h.update(repr(it).encode("utf-8", "ignore"))
        return h.hexdigest()
    except Exception:
        return None


def _cols(df_like: Any) -> List[str]:
    # df_like can be a list of dicts; infer keys order from pandas_metrics.columns if present
    return []


def _columns_signature(t: Dict[str, Any]) -> Tuple[int, Tuple[str, ...]]:
    pm = t.get("pandas_metrics") or {}
    cols = pm.get("columns") or []
    cols_norm = tuple(str(c).strip().lower() for c in cols)
    return (len(cols_norm), cols_norm)


def _tokenize(seq: Iterable[str]) -> List[str]:
    out: List[str] = []
    for s in seq or []:
        if not s:
            continue
        for tok in str(s).strip().lower().split():
            tok = tok.strip(".,:;()[]{}\"'`")
            if len(tok) >= 2:
                out.append(tok)
    return out


def _dice(a: List[str], b: List[str]) -> float:
    if not a or not b:
        return 0.0
    A = set(a)
    B = set(b)
    inter = len(A & B)
    return (2 * inter) / (len(A) + len(B))


def _likely_continuation(
    prev_t: Dict[str, Any],
    next_t: Dict[str, Any],
    headers_index: Dict[int, List[Dict[str, Any]]],
) -> Tuple[bool, str]:
    """Returns (is_continuation, reason)."""
    # Thresholds (env tunable)
    dice_threshold = float(os.getenv("CONTINUITY_DICE_THRESHOLD", "0.75"))
    jaccard_threshold = float(os.getenv("CONTINUITY_JACCARD_THRESHOLD", "0.75"))
    top_page_y_cutoff = float(os.getenv("CONTINUITY_TOP_PAGE_Y_CUTOFF", "220"))
    min_cols = int(os.getenv("CONTINUITY_MIN_COLS_JACCARD", "3"))
    max_vertical_gap = float(os.getenv("CONTINUITY_MAX_VERTICAL_GAP", "360"))  # px tightened default
    min_next_rows = int(os.getenv("CONTINUITY_MIN_NEXT_ROWS", "2"))
    lbl1 = prev_t.get("normalized_label")
    lbl2 = next_t.get("normalized_label")
    if lbl1 and lbl2 and lbl1 == lbl2:
        return True, "label_match"

    # Column set Jaccard overlap
    _, c1 = _columns_signature(prev_t)
    _, c2 = _columns_signature(next_t)
    if c1 and c2 and len(c1) >= min_cols and len(c2) >= min_cols:
        # Asymmetry guard: skip if column counts diverge widely
        if abs(len(c1) - len(c2)) <= 2:
            inter = len(set(c1) & set(c2))
            denom = max(len(c1), len(c2)) or 1
            if (inter / denom) >= jaccard_threshold:
                if _vertical_gap_ok(prev_t, next_t, max_vertical_gap):
                    return True, "columns_jaccard"

    # Header row token similarity (Dice)
    prev_cols = list(c1)
    next_cols = list(c2)
    # Guard: require minimum rows in the next table to avoid merging into tiny boilerplate headers
    nxt_shape = (next_t.get("pandas_metrics") or {}).get("shape") or [0, 0]
    try:
        if int(nxt_shape[0]) < min_next_rows:
            return False, "next_too_small"
    except Exception:
        pass
    if prev_cols and next_cols:
        d = _dice(_tokenize(prev_cols), _tokenize(next_cols))
        if d >= dice_threshold and _vertical_gap_ok(prev_t, next_t, max_vertical_gap):
            return True, "header_dice"

    # Stage 03 rejected header candidate at top of next table's page matching columns
    page_idx = next_t.get("page_index")
    if isinstance(page_idx, int) and page_idx in headers_index:
        for hdr in headers_index.get(page_idx, []):
            if hdr.get("is_header") is True:
                continue
            bb = hdr.get("bbox") or [0, 0, 0, 0]
            try:
                y0 = float(bb[1])
            except Exception:
                y0 = 9999.0
            if y0 > top_page_y_cutoff:
                continue
            hdr_tokens = _tokenize([hdr.get("text") or ""])
            col_tokens = _tokenize(prev_cols)
            if hdr_tokens and col_tokens:
                d2 = _dice(hdr_tokens, col_tokens)
                if d2 >= dice_threshold and _vertical_gap_ok(prev_t, next_t, max_vertical_gap):
                    return True, "03_rejected_header_repeat"

    return False, "no_match"


def _vertical_gap_ok(prev_t: Dict[str, Any], next_t: Dict[str, Any], limit: float) -> bool:
    """
    Estimate vertical gap using bottom of prev table bbox and top of next table bbox.
    Fallback: if bbox missing, allow.
    """
    try:
        pb = prev_t.get("bbox") or prev_t.get("table_bbox") or []
        nb = next_t.get("bbox") or next_t.get("table_bbox") or []
        if len(pb) < 4 or len(nb) < 4:
            return True
        prev_bottom = float(pb[3])
        next_top = float(nb[1])
        return (next_top - prev_bottom) <= limit
    except Exception:
        return True


@app.command("run")
def run(
    sections_json: Path = typer.Option(..., "--sections", exists=True),
    tables_json: Path = typer.Option(..., "--tables", exists=True),
    figures_json: Path = typer.Option(..., "--figures", exists=True),
    verified03_json: Optional[Path] = typer.Option(None, "--verified03", help="03_verified_blocks.json if available"),
    output_dir: Path = typer.Option(Path("data/results/pipeline"), "-o"),
):
    base = output_dir
    out_dir = base / "07a_section_canonicalizer"
    json_dir = out_dir / "json_output"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_dir.mkdir(parents=True, exist_ok=True)

    s04 = _load_json(sections_json)
    s05 = _load_json(tables_json)
    s06 = _load_json(figures_json)

    sections: List[Dict[str, Any]] = list(s04.get("sections", []))
    sections.sort(key=_sec_key)
    tables = list(s05.get("tables", []))
    figures = list(s06.get("figures", []))

    # Index tables/figures by section via page range when section_id missing
    for t in tables:
        if t.get("section_id") is None:
            p = int(t.get("page_index", 0))
            for sec in sections:
                if int(sec.get("page_start", 0)) <= p <= int(sec.get("page_end", 0)):
                    t["section_id"] = sec.get("id")
                    break
    for f in figures:
        if f.get("section_id") is None:
            p = int(f.get("page", 0))
            for sec in sections:
                if int(sec.get("page_start", 0)) <= p <= int(sec.get("page_end", 0)):
                    f["section_id"] = sec.get("id")
                    break

    # Build per-section canonical structure
    sec_by_id = {s.get("id"): s for s in sections}
    can_sections: Dict[str, Dict[str, Any]] = {}
    for s in sections:
        can_sections[s["id"]] = {
            "id": s["id"],
            "title": s.get("title"),
            "level": s.get("level"),
            "page_start": s.get("page_start"),
            "page_end": s.get("page_end"),
            "paragraphs": [],
            "tables": [],
            "figures": [],
            "section_image_ref": (s.get("visual_path") or s.get("visual_page_paths", [None])[0]),
            "needs_layout_image": bool((s.get("metadata") or {}).get("needs_layout_image")),
            "content_hash": (s.get("metadata") or {}).get("section_content_hash"),
        }
        # Extract paragraphs from blocks
        for b in s.get("blocks", []) or []:
            txt = (b.get("text") or "").strip()
            if not txt:
                continue
            btype = b.get("block_type") or b.get("type")
            if btype and str(btype) == "SectionHeader":
                continue
            pid = f"p{len(can_sections[s['id']]['paragraphs'])+1}"
            para = {
                "pid": pid,
                "text": txt,
                "bbox": b.get("bbox"),
                "page": b.get("page", b.get("page_idx", 0)),
            }
            # Stable paragraph anchor id
            sid_local = s.get("id")
            sig = f"{sid_local}|{pid}|{txt[:120]}"
            para["anchor_id"] = "par::" + hashlib.sha256(sig.encode("utf-8", "ignore")).hexdigest()[:16]
            can_sections[s["id"]]["paragraphs"].append(para)

    # Attach tables/figures
    for t in tables:
        sid = t.get("section_id")
        if sid in can_sections:
            can_sections[sid]["tables"].append(t)
    for f in figures:
        sid = f.get("section_id")
        if sid in can_sections:
            can_sections[sid]["figures"].append(f)

    # Build Stage 03 headers index if provided (accepted & rejected)
    headers_index: Dict[int, List[Dict[str, Any]]] = {}
    if verified03_json and verified03_json.exists():
        try:
            v3 = _load_json(verified03_json)
            for b in v3.get("blocks", []):
                p = b.get("page_idx")
                if p is None:
                    continue
                lv = (b.get("llm_verification") or {}).get("result", {}) or {}
                is_header = bool(lv.get("is_header", True))
                headers_index.setdefault(int(p), []).append({
                    "object_id": b.get("object_id"),
                    "text": b.get("text"),
                    "is_header": is_header,
                    "bbox": b.get("bbox"),
                    "page_idx": p,
                })
        except Exception as e:
            logger.warning(f"07a: failed to build headers_index: {e}")

    # Continuity merge across adjacent sections: attach to later section when likely continuation
    ids = list(can_sections.keys())
    for i in range(len(ids) - 1):
        a = can_sections[ids[i]]
        b = can_sections[ids[i + 1]]
        if not a["tables"] or not b["tables"]:
            continue
        # naive: compare last of a with first of b
        ta = a["tables"][-1]
        tb = b["tables"][0]
        cont, reason = _likely_continuation(ta, tb, headers_index)
        if cont:
            # move ta into b and record provenance
            moved = a["tables"].pop()
            b["tables"] = [moved] + b["tables"]
            prov = tb.setdefault("provenance", {})
            prov.setdefault("merged_from_sections", []).append(a["id"])
            prov.setdefault("merged_from_raw", []).append(moved.get("raw_table_id"))
            prov["continuation_reason"] = reason

    # Compute 03 annotations hash and fold into content_hash if available
    for sid, sec in can_sections.items():
        h03 = _03_annotations_hash(verified03_json, sec_by_id.get(sid, {}))
        if h03:
            base = sec.get("content_hash") or ""
            sec["content_hash"] = hashlib.sha256((base + "|03:" + h03).encode("utf-8")).hexdigest()
        # Add anchor ids and table block hash
        for t in sec.get("tables", []):
            raw_id = t.get("raw_table_id") or t.get("tid") or str(id(t))
            cols = (t.get("pandas_metrics") or {}).get("columns") or []
            sig = f"{sid}|{raw_id}|{','.join(map(str, cols))}"
            t["anchor_id"] = "tab::" + hashlib.sha256(sig.encode("utf-8", "ignore")).hexdigest()[:16]
            try:
                block_core = {
                    "cols": cols,
                    "rows": t.get("pandas_df") or t.get("rows") or [],
                }
                t["block_hash"] = hashlib.sha256(json.dumps(block_core, sort_keys=True, default=str).encode("utf-8", "ignore")).hexdigest()
            except Exception:
                pass
        for f in sec.get("figures", []):
            capcand = f.get("caption") or f.get("ai_description") or f.get("caption_candidate") or ""
            sig = f"{sid}|{f.get('image_ref') or f.get('image_path')}|{capcand[:80]}"
            f["anchor_id"] = "fig::" + hashlib.sha256(sig.encode("utf-8", "ignore")).hexdigest()[:16]
        # Capture prompt_source_objects: first accepted header object_id on the section's first page
        try:
            ps = int(sec_by_id[sid].get("page_start", 0))
            objs = []
            for h in headers_index.get(ps, []):
                if h.get("is_header") and h.get("object_id"):
                    objs.append(h.get("object_id"))
            if objs:
                sec["prompt_source_objects"] = objs[:1]
        except Exception:
            pass

    payload = {
        "timestamp": __import__("datetime").datetime.now().isoformat(),
        "status": "Completed",
        "sections": list(can_sections.values()),
        "deterministic": True,
        "hash_component": "07a",
    }
    outp = json_dir / "07a_canonical.json"
    outp.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    logger.success(f"07a: wrote {outp}")


if __name__ == "__main__":
    app()
