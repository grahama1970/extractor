#!/usr/bin/env python3
"""
Stage 06a: Title/Caption Enricher (text-only)

Purpose
- Add titles to tables and figures using explicit nearby text when present.
- If no explicit title exists, infer a short title via the Chutes text model (scillm, x-api-key),
  and prefix with "INFER: ". Falls back to deterministic heuristics if the model is unavailable.

Inputs
- 05_tables.json (Stage 05)
- 06_figures.json (Stage 06)
- (Optional) 04_sections.json for context (not required)

Outputs (under 06a_title_caption_enricher/json_output)
- 05_tables.enriched.json
- 06_figures.enriched.json

Profile
- Text-first. No images. Network calls are short (<=6s) and fail-soft.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import json as _json
import urllib.request

import typer
from loguru import logger
from scillm import acompletion as sc_acompletion
from typing import Iterable


app = typer.Typer(add_completion=False)


def _load_json(p: Path) -> Dict[str, Any]:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error(f"Failed to read JSON {p}: {e}")
        return {}


def _save_json(p: Path, obj: Dict[str, Any]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _explicit_table_title(t: Dict[str, Any]) -> Optional[str]:
    # Prefer existing title/caption from Stage 05 detection
    txt = (t.get("title") or t.get("caption") or "").strip()
    if not txt:
        return None
    return txt


def _explicit_figure_title(f: Dict[str, Any]) -> Optional[str]:
    # Prefer existing title, else use explicit caption below/above if Stage 06 found one
    txt = (f.get("title") or f.get("caption") or "").strip()
    if not txt:
        return None
    return txt


def _chutes_title_infer(prompt_ctx: str, timeout: float = 6.0) -> Optional[str]:
    """Infer a short title via SciLLM directly (Chutes x‑api‑key, OpenAI‑compatible path)."""
    try:
        prompt = (
            "Return ONLY a short, precise technical title (<= 10 words). "
            "Do not include numbering or the words 'Table'/'Figure'. "
            "If nearby text appears generic (e.g., just 'Figure 3' or boilerplate) "
            "ignore it and rely on the table headers/sample or the figure content/description.\n\n"
            f"Context:\n{prompt_ctx[:1200]}\n"
        )
        # QUICKSTART helper: wrapper handles x-api-key vs Bearer, /v1 base, and backoff
        # Allow env override for slow chutes via CHUTES_INFER_TIMEOUT (seconds)
        try:
            _t_env = float(os.getenv("CHUTES_INFER_TIMEOUT", "0").strip() or 0)
            if _t_env > 0:
                timeout = _t_env
        except Exception:
            pass
        model = os.getenv("CHUTES_TEXT_MODEL", "").strip()
        base = os.getenv("CHUTES_API_BASE", "").strip()
        key = os.getenv("CHUTES_API_KEY", "").strip()
        if not (model and base and key):
            return None
        resp = asyncio.run(sc_acompletion(
            model=model,
            custom_llm_provider="openai_like",
            api_base=base,
            api_key=None,
            extra_headers={"x-api-key": key},
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.2,
            timeout=timeout,
        ))
        content = (resp.get("choices") or [{}])[0].get("message", {}).get("content", "").strip()
        return content.strip().strip('"') or None
    except Exception as e:
        logger.debug(f"Title inference skipped: {e}")
        return None


# -----------------------------
# Nearby block utilities (Stage 04)
# -----------------------------

Block = Dict[str, Any]


def _flatten_section_blocks(sections_json: Path | None) -> Dict[int, List[Block]]:
    """Return a map: page_idx -> list of text-like blocks with bbox and text.

    Accepts Stage 04 `04_sections.json` and gathers blocks that can serve as
    captions/titles: Text, SectionHeader, ListItem, Paragraph (when present).
    """
    out: Dict[int, List[Block]] = {}
    if not sections_json:
        return out
    try:
        data = json.loads(Path(sections_json).read_text(encoding="utf-8"))
        sections = data.get("sections") or []
        for sec in sections:
            for b in sec.get("blocks", []) or []:
                btype = (b.get("block_type") or "").strip()
                if btype not in {"Text", "SectionHeader", "ListItem", "Paragraph"}:
                    continue
                txt = (b.get("text") or b.get("content") or "").strip()
                bbox = b.get("bbox") or []
                pidx = b.get("page_idx")
                if not txt or not isinstance(bbox, list) or len(bbox) != 4:
                    continue
                if pidx is None:
                    pidx = b.get("page")
                if pidx is None:
                    continue
                out.setdefault(int(pidx), []).append(b)
        # stable order: by top y (bbox[1]) then left x
        for k in list(out.keys()):
            out[k].sort(key=lambda bb: (float((bb.get("bbox") or [0, 0, 0, 0])[1]), float((bb.get("bbox") or [0, 0, 0, 0])[0])))
    except Exception as e:
        logger.debug(f"sections flatten failed: {e}")
    return out


def _h_overlap(a: Iterable[float], b: Iterable[float]) -> float:
    ax0, _, ax1, _ = a
    bx0, _, bx1, _ = b
    inter = max(0.0, min(ax1, bx1) - max(ax0, bx0))
    w = max(1e-6, max(ax1 - ax0, bx1 - bx0))
    return float(inter / w)


def _nearest_above_below(
    page_blocks: Dict[int, List[Block]],
    page_idx: int,
    bbox: List[float],
    *,
    min_h_overlap: float = 0.3,
    max_v_dist: float | None = 160.0,
) -> Tuple[Optional[Block], Optional[Block]]:
    """Find nearest text-like blocks directly above and below a bbox on a page.

    - Requires some horizontal overlap (min_h_overlap)
    - Optionally caps vertical search distance (max_v_dist points)
    """
    blocks = page_blocks.get(int(page_idx)) or []
    if not blocks or not bbox or len(bbox) != 4:
        return None, None
    x0, y0, x1, y1 = [float(v) for v in bbox]
    above_cands: List[Tuple[float, Block]] = []
    below_cands: List[Tuple[float, Block]] = []
    for b in blocks:
        bb = b.get("bbox") or []
        if not isinstance(bb, list) or len(bb) != 4:
            continue
        ov = _h_overlap(bbox, bb)
        if ov < float(min_h_overlap):
            continue
        bx0, by0, bx1, by1 = [float(v) for v in bb]
        # Above: candidate bottom <= target top
        if by1 <= y0:
            dy = y0 - by1
            if max_v_dist is None or dy <= max_v_dist:
                above_cands.append((dy, b))
        # Below: candidate top >= target bottom
        elif by0 >= y1:
            dy = by0 - y1
            if max_v_dist is None or dy <= max_v_dist:
                below_cands.append((dy, b))
        else:
            # Overlapping vertically — not strictly above/below; skip
            continue
    above = min(above_cands, key=lambda t: t[0])[1] if above_cands else None
    below = min(below_cands, key=lambda t: t[0])[1] if below_cands else None
    return above, below


def _useful_text(s: str) -> bool:
    s = (s or "").strip()
    if len(s) < 6:
        return False
    # generic labels like "Figure 2" or "Table 1:"
    if re.match(r"^(?:Fig(?:\.|ure)?|Table)\s*\d+[\.:]?\s*$", s, re.IGNORECASE):
        return False
    # largely punctuation/noise
    if re.match(r"^[\W_]+$", s):
        return False
    return True


def _collect_nearby_text(
    page_blocks: Dict[int, List[Block]],
    page_idx: int,
    bbox: List[float],
    *,
    max_above: int = 2,
    max_below: int = 2,
    min_h_overlap: float = 0.3,
    max_v_dist: float | None = 200.0,
) -> Tuple[List[str], List[str]]:
    """Return up to N 'useful' lines above and below the bbox, by nearest distance first."""
    blocks = page_blocks.get(int(page_idx)) or []
    if not blocks or not bbox or len(bbox) != 4:
        return [], []
    x0, y0, x1, y1 = [float(v) for v in bbox]
    above_cands: List[Tuple[float, str]] = []
    below_cands: List[Tuple[float, str]] = []
    for b in blocks:
        bb = b.get("bbox") or []
        if not isinstance(bb, list) or len(bb) != 4:
            continue
        ov = _h_overlap(bbox, bb)
        if ov < float(min_h_overlap):
            continue
        bx0, by0, bx1, by1 = [float(v) for v in bb]
        text = (b.get("text") or b.get("content") or "").strip()
        if not _useful_text(text):
            continue
        if by1 <= y0:
            dy = y0 - by1
            if max_v_dist is None or dy <= max_v_dist:
                above_cands.append((dy, text))
        elif by0 >= y1:
            dy = by0 - y1
            if max_v_dist is None or dy <= max_v_dist:
                below_cands.append((dy, text))
        else:
            continue
    above_cands.sort(key=lambda t: t[0])
    below_cands.sort(key=lambda t: t[0])
    return [t for _, t in above_cands[:max_above]], [t for _, t in below_cands[:max_below]]


def _normalize_id(prefix: str, number: Optional[str], base_title: Optional[str]) -> Optional[str]:
    if number:
        return f"{prefix}-{number}"
    if base_title:
        slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in base_title).strip("-")
        if slug:
            return f"{prefix}-{slug}"
    return None


def enrich_tables(tables: List[Dict[str, Any]], *, page_blocks: Optional[Dict[int, List[Block]]] = None) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for t in tables or []:
        tt = (t or {}).copy()
        title = _explicit_table_title(tt)
        title_source = None
        if not title:
            # Nearby context from Stage 04 blocks if available
            ctx_parts: List[str] = []
            try:
                page_idx = int(tt.get("page_index") if tt.get("page_index") is not None else int(tt.get("page_number", 1)) - 1)
            except Exception:
                page_idx = None  # type: ignore
            bbox = tt.get("bbox") or []
            if page_blocks and page_idx is not None and isinstance(bbox, list) and len(bbox) == 4:
                ab_lines, bel_lines = _collect_nearby_text(page_blocks, page_idx, bbox)
                if ab_lines:
                    ctx_parts.append("Above: " + " | ".join(ab_lines))
                if bel_lines:
                    ctx_parts.append("Below: " + " | ".join(bel_lines))
            # Build simple context from header row and a few body rows
            try:
                import pandas as pd
                df = pd.DataFrame(tt.get("pandas_df") or [])
                header = " | ".join(str(c) for c in df.columns) if not df.empty else ""
                samples: List[str] = []
                if not df.empty:
                    for i in range(min(2, len(df))):
                        try:
                            samples.append(" | ".join(str(x) for x in df.iloc[i].tolist()))
                        except Exception:
                            break
                sample_str = "\n".join(samples)
                basic = f"Header: {header}\nSamples:\n{sample_str}" if header or sample_str else ""
            except Exception:
                basic = ""
            ctx_all = "\n".join([p for p in ctx_parts + ([basic] if basic else []) if p]).strip()
            inferred = _chutes_title_infer(ctx_all or basic)
            if inferred:
                title = f"INFER: {inferred}"
                title_source = "infer"
            else:
                # deterministic fallback: header or first body row
                fallback_line = (ctx_all.splitlines()[0] if ctx_all else (basic.splitlines()[0] if basic else "")).strip()
                title = f"INFER: {fallback_line}" if fallback_line else "INFER: Untitled Table"
                title_source = "infer"
        # Parse number + base_title for merging
        m = re.match(r"\s*(?:Table|Tbl\.)\s*([A-Za-z0-9\-\.]+)?[\.:]?\s*(.*)$", title or "", re.IGNORECASE)
        number = (m.group(1).strip() if (m and m.group(1)) else None) or None
        base_title = (m.group(2).strip() if (m and m.group(2)) else title or None) or None
        cont = bool(title and "Continued" in title)
        norm_id = _normalize_id("table", number, base_title)
        tt.update(
            {
                "title": title,
                "title_source": title_source or tt.get("title_source") or "detected",
                "number": number,
                "base_title": base_title,
                "continued": cont,
                "normalized_id": norm_id or tt.get("normalized_id"),
            }
        )
        out.append(tt)
    return out


def enrich_figures(figs: List[Dict[str, Any]], *, page_blocks: Optional[Dict[int, List[Block]]] = None) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for f in figs or []:
        ff = (f or {}).copy()
        title = _explicit_figure_title(ff)
        title_source = None
        if not title:
            ctx_parts: List[str] = []
            # Nearby text above/below as primary context
            try:
                page_idx = int(ff.get("page_index") if ff.get("page_index") is not None else int(ff.get("page_number", 1)) - 1)
            except Exception:
                page_idx = None  # type: ignore
            bbox = ff.get("bbox") or []
            if page_blocks and page_idx is not None and isinstance(bbox, list) and len(bbox) == 4:
                ab_lines, bel_lines = _collect_nearby_text(page_blocks, page_idx, bbox)
                if ab_lines:
                    ctx_parts.append("Above: " + " | ".join(ab_lines))
                if bel_lines:
                    ctx_parts.append("Below: " + " | ".join(bel_lines))
            # Include any AI description from Stage 06
            ai_desc = (ff.get("ai_description") or "").strip()
            if ai_desc:
                ctx_parts.append(f"AI: {ai_desc}")
            ctx = "\n".join(ctx_parts)[:1200]
            inferred = _chutes_title_infer(ctx)
            if inferred:
                title = f"INFER: {inferred}"
                title_source = "infer"
            else:
                # deterministic fallback: first sentence of description
                base = ai_desc or ctx
                first = base.split(".", 1)[0].strip()
                title = f"INFER: {first}" if first else "INFER: Untitled Figure"
                title_source = "infer"
        m = re.match(r"\s*(?:Figure|Fig\.)\s*([A-Za-z0-9\-\.]+)?[\.:]?\s*(.*)$", title or "", re.IGNORECASE)
        number = (m.group(1).strip() if (m and m.group(1)) else None) or None
        base_title = (m.group(2).strip() if (m and m.group(2)) else title or None) or None
        cont = bool(title and "Continued" in title)
        norm_id = _normalize_id("figure", number, base_title)
        ff.update(
            {
                "title": title,
                "title_source": title_source or ff.get("title_source") or "detected",
                "number": number,
                "base_title": base_title,
                "continued": cont,
                "normalized_id": norm_id or ff.get("normalized_id"),
            }
        )
        out.append(ff)
    return out


@app.command()
def run(
    tables_json: Path = typer.Option(
        ..., "--tables", exists=True, help="Path to Stage 05 tables JSON"
    ),
    figures_json: Path = typer.Option(
        ..., "--figures", exists=True, help="Path to Stage 06 figures JSON"
    ),
    sections_json: Path | None = typer.Option(
        None, "--sections", exists=True, help="Optional Stage 04 sections JSON"
    ),
    output_dir: Path = typer.Option(
        "data/results/pipeline", "-o", help="Results base directory"
    ),
) -> None:
    console = typer.echo
    t = _load_json(tables_json)
    f = _load_json(figures_json)
    page_blocks = _flatten_section_blocks(sections_json) if sections_json else {}
    tables = t.get("tables") or []
    figs = f.get("figures") or []
    tables_e = enrich_tables(tables, page_blocks=page_blocks)
    figs_e = enrich_figures(figs, page_blocks=page_blocks)
    enriched_root = output_dir / "06a_title_caption_enricher" / "json_output"
    _save_json(enriched_root / "05_tables.enriched.json", {"tables": tables_e, "timestamp": datetime.now().isoformat()})
    _save_json(enriched_root / "06_figures.enriched.json", {"figures": figs_e, "timestamp": datetime.now().isoformat()})
    console(
        f"Enriched titles written to: {enriched_root / '05_tables.enriched.json'} and {enriched_root / '06_figures.enriched.json'}"
    )


if __name__ == "__main__":
    app()
