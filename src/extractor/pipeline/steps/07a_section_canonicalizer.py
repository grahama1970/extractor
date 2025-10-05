#!/usr/bin/env python3
from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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


def _likely_continuation(prev_t: Dict[str, Any], next_t: Dict[str, Any]) -> bool:
    # Rule: same normalized_label OR ≥70% header token overlap
    lbl1 = prev_t.get("normalized_label")
    lbl2 = next_t.get("normalized_label")
    if lbl1 and lbl2 and lbl1 == lbl2:
        return True
    # Fallback on columns similarity
    _, c1 = _columns_signature(prev_t)
    _, c2 = _columns_signature(next_t)
    if not c1 or not c2:
        return False
    inter = len(set(c1) & set(c2))
    denom = max(len(c1), len(c2)) or 1
    return (inter / denom) >= 0.7


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
            can_sections[s["id"]]["paragraphs"].append({"pid": f"p{len(can_sections[s['id']]['paragraphs'])+1}", "text": txt, "bbox": b.get("bbox"), "page": b.get("page", b.get("page_idx", 0))})

    # Attach tables/figures
    for t in tables:
        sid = t.get("section_id")
        if sid in can_sections:
            can_sections[sid]["tables"].append(t)
    for f in figures:
        sid = f.get("section_id")
        if sid in can_sections:
            can_sections[sid]["figures"].append(f)

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
        if _likely_continuation(ta, tb):
            # move ta into b and record provenance
            moved = a["tables"].pop()
            b["tables"] = [moved] + b["tables"]
            prov = tb.setdefault("provenance", {})
            prov.setdefault("merged_from_sections", []).append(a["id"])
            prov.setdefault("merged_from_raw", []).append(moved.get("raw_table_id"))

    # Compute 03 annotations hash and fold into content_hash if available
    for sid, sec in can_sections.items():
        h03 = _03_annotations_hash(verified03_json, sec_by_id.get(sid, {}))
        if h03:
            base = sec.get("content_hash") or ""
            sec["content_hash"] = hashlib.sha256((base + "|03:" + h03).encode("utf-8")).hexdigest()

    payload = {
        "timestamp": __import__("datetime").datetime.now().isoformat(),
        "status": "Completed",
        "sections": list(can_sections.values()),
    }
    outp = json_dir / "07a_canonical.json"
    outp.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    logger.success(f"07a: wrote {outp}")


if __name__ == "__main__":
    app()

