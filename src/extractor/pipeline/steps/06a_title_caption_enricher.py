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
import asyncio

from loguru import logger
from extractor.pipeline.utils.scillm_router import get_text_router
from extractor.pipeline.utils.response_utils import normalize_json_content
from extractor.pipeline.utils.debug_utils import ensure_logs_dir, time_block, log_timing
from extractor.pipeline.utils.preflight import scillm_quick_check
from typing import Iterable


## CLI removed: import and call run(...), or use a debug harness.


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


def _chutes_title_infer_struct(prompt_ctx: str, timeout: float = 45.0) -> Optional[Dict[str, Any]]:
    """Infer title metadata using SciLLM and return a structured dict.

    Returns a dict subset of: {title, number, base_title, continued}
    or None on failure/empty content.
    """
    prompt = (
        "You are naming elements in scientific/engineering documents. Return ONLY strict JSON with keys: "
        "{\"title\": string|null, \"number\": string|null, \"base_title\": string|null, \"continued\": boolean|null}. "
        "title: concise (<=10 words), no numbering and without the words 'Table'/'Figure'. If unsure, set title=null. "
        "number: the element's explicit number if present (e.g., '4-1', 'IV', '1'), else null. "
        "base_title: the semantic title without numbering or prefixes, else null. continued: true if the text implies a continued table/figure.\n\n"
        f"Context (ignore boilerplate labels):\n{prompt_ctx[:1500]}\n"
    )
    # Router-only JSON call (Bearer auth only for this tenant)
    try:
        # Enforce Bearer for chat on this tenant
        os.environ.setdefault("CHUTES_AUTH_STYLE", "bearer")
        # Preflight once per call site (fast, 3s)
        ok, reason = scillm_quick_check(timeout=3.0)
        if not ok:
            raise RuntimeError(f"06a preflight failed: {reason}")
        router = get_text_router()
        # Write per-call timing under the stage logs directory if env RUN_RESULTS_DIR is set
        results_dir = os.getenv("RUN_RESULTS_DIR")
        if results_dir:
            logs_dir = ensure_logs_dir(Path(results_dir), "06a_title_caption_enricher")
            with time_block(logs_dir, "title_infer", kind="text", ctx_chars=len(prompt_ctx or "")):
                try:
                    (logs_dir / "last_request.json").write_text(
                        json.dumps({
                            "model": "chutes/text",
                            "messages": [
                                {"role": "system", "content": "Return ONLY strict JSON for scientific/engineering docs."},
                                {"role": "user", "content": prompt},
                            ],
                            "response_format": {"type": "json_object"},
                            "temperature": 0,
                            "timeout": timeout,
                        }, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                except Exception:
                    pass
                resp = asyncio.run(
                    router.acompletion(
                        model="chutes/text",
                        messages=[
                            {"role": "system", "content": "Return ONLY strict JSON for scientific/engineering docs."},
                            {"role": "user", "content": prompt},
                        ],
                        response_format={"type": "json_object"},
                        temperature=0,
                        timeout=timeout,
                    )
                )
                try:
                    usage = getattr(resp, "usage", None) or {}
                    served = getattr(resp, "model", None)
                    log_timing(
                        "06a_title_caption_enricher",
                        {
                            "attempt": "title_infer",
                            "outcome": "ok",
                            "model": served,
                            "tokens_in": usage.get("prompt_tokens"),
                            "tokens_out": usage.get("completion_tokens"),
                        },
                        stage_dir=logs_dir,
                    )
                    (logs_dir / "last_response.json").write_text(
                        json.dumps(getattr(resp, "choices", [{}])[0].get("message", {}).get("content", ""), ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                except Exception:
                    pass
        else:
            resp = asyncio.run(
                router.acompletion(
                    model="chutes/text",
                    messages=[
                        {"role": "system", "content": "Return ONLY strict JSON for scientific/engineering docs."},
                        {"role": "user", "content": prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0,
                    timeout=timeout,
                )
            )
        _, json_obj = normalize_json_content(resp)
        if isinstance(json_obj, dict):
            out: Dict[str, Any] = {}
            title = json_obj.get("title")
            out["title"] = title.strip() if isinstance(title, str) and title.strip() else None
            for k in ("number", "base_title"):
                v = json_obj.get(k)
                out[k] = v.strip() if isinstance(v, str) and v.strip() else None
            cont = json_obj.get("continued")
            out["continued"] = bool(cont) if isinstance(cont, bool) else None
            return out
    except Exception as e:
        logger.debug(f"SciLLM Router infer failed: {e}")
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
            inferred = _chutes_title_infer_struct(ctx_all or basic)
            if isinstance(inferred, dict):
                title = inferred.get("title")
                title_source = "infer" if title else "missing"
                number = inferred.get("number")
                base_title = inferred.get("base_title") or title
                cont = bool(inferred.get("continued"))
            else:
                title = None
                title_source = "missing"
                number = None
                base_title = None
                cont = False
        else:
            # If an explicit title exists, prefer it; derive base fields without regex assumptions
            number = None
            base_title = title
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
            # Use structured SciLLM inference directly (no legacy helper)
            inferred = _chutes_title_infer_struct(ctx)
            if isinstance(inferred, dict):
                title = inferred.get("title")
                title_source = "infer" if title else "missing"
                number = inferred.get("number")
                base_title = inferred.get("base_title") or title
                cont = bool(inferred.get("continued"))
            else:
                title = None
                title_source = "missing"
                number = None
                base_title = None
                cont = False
        # if title still missing after structured infer, leave as missing (no deterministic fabrication)
        else:
            number = None
            base_title = title
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


def run(
    tables_json: Path,
    figures_json: Path,
    sections_json: Path | None = None,
    output_dir: Path = Path("data/results/pipeline"),
) -> Path:
    def _console(msg: str) -> None:
        logger.info(msg)
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
    _console(
        f"Enriched titles written to: {enriched_root / '05_tables.enriched.json'} and {enriched_root / '06_figures.enriched.json'}"
    )
    return enriched_root


if __name__ == "__main__":
    print("Import and call run(...), or use scripts/debug/stage06_debug.py")
