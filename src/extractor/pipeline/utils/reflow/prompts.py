#!/usr/bin/env python3
"""Prompt building utilities for Stage 07 Section Reflow.

Functions for constructing LLM prompts from section data.
"""

from __future__ import annotations

import json
from textwrap import dedent
from typing import Any, Dict, List

from extractor.pipeline.utils.text_utils import sanitize_text


def build_reflow_prompt(section_data: dict[str, Any]) -> str:
    """Build a simplified prompt focused on the core reflow task."""
    table_count = len(section_data.get("tables", []))
    figure_count = len(section_data.get("figures", []))

    return dedent(
        f"""
        Clean up and reflow this PDF section into proper Markdown.

        Section: "{section_data.get('title', 'Untitled')}"
        Tables: {table_count}
        Figures: {figure_count}

        Raw text to clean up:
        ---
        {section_data.get('raw_text', '')}
        ---

        Fix common PDF extraction issues like words split across lines, OCR errors, and broken table formatting.

        Return ONLY a JSON object with the following keys:
        {{
            "reflowed_text": "The cleaned Markdown text.",
            "ocr_corrections": {{'erroneous text': 'corrected text'}},
            "improvements_made": "A brief summary of what was fixed."
        }}
    """
    ).strip()


def build_compact_prompt(
    *,
    results_base_dir: Any,
    section_data: Dict[str, Any],
    tables: List[Dict[str, Any]],
    figures: List[Dict[str, Any]],
    sketch_v2_by_sec: Dict[str, Any],
) -> str:
    """Construct a compact, string-only prompt using 06b's sketch_v2 + 06a enrichments."""
    sid = str(section_data.get("id"))
    sketch = (sketch_v2_by_sec or {}).get(sid) or {}
    tabs_for_sec = [t for t in (tables or []) if str(t.get("section_id")) == sid]
    figs_for_sec = [f for f in (figures or []) if str(f.get("section_id")) == sid]

    # Identify merge candidates by (logical_table_id, header_norm)
    merges: List[str] = []
    by_key: Dict[str, List[str]] = {}
    for t in tabs_for_sec:
        key = f"{t.get('logical_table_id') or ''}|{t.get('header_norm') or ''}"
        if key.strip("|"):
            by_key.setdefault(key, []).append(str(t.get("id") or t.get("table_id") or "tbl"))
    for k, ids in by_key.items():
        if len(ids) >= 2:
            merges.append(f"logical={k} parts={','.join(ids[:6])}")

    lines: List[str] = []
    lines.append(
        "You output ONLY a compact JSON object with keys: reflowed_json, ocr_corrections, improvements_made, summary. No markdown, no code fences."
    )
    lines.append("")
    lines.append(f"Section id: {sid}")
    lines.append(f"Tables: {len(tabs_for_sec)} | Figures: {len(figs_for_sec)}")
    for m in merges[:4]:
        lines.append(f"Merge candidate: {m}")

    # Minimal sketch slice
    objs = (sketch.get("objects") or []) if isinstance(sketch, dict) else []
    if objs:
        mini = []
        for o in objs[:20]:
            mini.append(
                {
                    "id": o.get("id"),
                    "type": o.get("type"),
                    "page": o.get("page"),
                    "grid_bbox": o.get("grid_bbox"),
                    "header_norm": o.get("header_norm"),
                    "logical_table_id": o.get("logical_table_id"),
                    "summary": o.get("summary"),
                }
            )
        try:
            lines.append("")
            lines.append("Sketch (minimal):")
            lines.append(json.dumps(mini, ensure_ascii=False))
        except Exception:
            pass

    # Heads/titles summary
    if tabs_for_sec:
        lines.append("")
        lines.append("Tables heads/titles:")
        for t in tabs_for_sec[:8]:
            hid = t.get("id") or t.get("table_id")
            lines.append(f"- {hid}: header_norm={t.get('header_norm')} title={t.get('title')}")
    if figs_for_sec:
        lines.append("")
        lines.append("Figures titles:")
        for f in figs_for_sec[:6]:
            fid = f.get("id") or f.get("figure_id")
            lines.append(f"- {fid}: title={f.get('title')} caption={f.get('caption')}")

    lines.append("")
    lines.append("Return ONLY the JSON; keep it compact.")
    return "\n".join(lines)


def build_compact_prompt_simple(
    section: dict[str, Any],
    *,
    text_char_cap: int = 1200,
) -> str:
    """Build a compact, string-only prompt with minimal context.

    Includes:
    - Top Summary: counts and per-table metrics
    - Layout Sketch DSL (from 06b)
    - Minimal inputs: trimmed text, tables (headers + first row), figures
    - Strict JSON contract reminder
    """
    lines: list[str] = []
    title = sanitize_text(section.get("title", "Untitled"))
    pg0 = section.get("page_start")
    pg1 = section.get("page_end")
    blocks_count = len(section.get("blocks", []) or [])

    tables = section.get("tables") or []
    figures = section.get("figures") or []

    # Top Summary
    lines.append(f"Top Summary\n- title: {title}\n- pages: {pg0}–{pg1}\n- blocks: {blocks_count}")
    lines.append(f"- tables: {len(tables)}\n- figures: {len(figures)}")

    # Table metrics
    used_idx = set()
    next_idx = 0
    for tb in tables:
        pm = tb.get("pandas_metrics") or {}
        shape = pm.get("shape") or [0, 0]
        rows, cols = (
            (int(shape[0] or 0), int(shape[1] or 0)) if isinstance(shape, (list, tuple)) else (0, 0)
        )
        density = pm.get("data_density")
        camel = tb.get("camelot_metrics") or {}
        acc = camel.get("accuracy")
        strat = tb.get("strategy") or tb.get("strategy_history") or None
        qf = tb.get("quality_fallback") or None

        try:
            tbi = int(tb.get("table_index"))
        except Exception:
            tbi = None
        if tbi in used_idx or tbi is None:
            while next_idx in used_idx:
                next_idx += 1
            disp_idx = next_idx
            used_idx.add(disp_idx)
            next_idx += 1
        else:
            disp_idx = tbi
            used_idx.add(disp_idx)

        def _r2(x):
            try:
                return round(float(x), 2)
            except Exception:
                return x

        lines.append(
            f"  • table idx {disp_idx}: rows×cols={rows}×{cols}, density={_r2(density)}, camelot_acc={_r2(acc)}, strategy={strat}, quality_fallback={qf}"
        )

    # Layout Sketch DSL (compact)
    lsk = section.get("layout_sketch") or {}
    if isinstance(lsk, dict) and lsk:
        grid = lsk.get("grid", 12)
        cols = lsk.get("columns") or []
        dsl = (lsk.get("flow_stream") or "").strip()
        dsl_compact = dsl if len(dsl) <= 900 else (dsl[:900] + " …")
        lines.append("\nLayout Sketch")
        lines.append(f"- grid: {grid}")
        if cols:
            try:
                lines.append(f"- columns: {json.dumps(cols, ensure_ascii=False)[:300]}")
            except Exception:
                lines.append("- columns: (unavailable)")
        if dsl_compact:
            lines.append("- dsl:")
            lines.append(dsl_compact)

    # Minimal Inputs
    src_text = sanitize_text(
        section.get("source_text") or section.get("merged_text") or section.get("raw_text") or ""
    )
    lines.append("\nInputs")
    lines.append("Text (trimmed):")
    if src_text:
        lines.append(src_text[:text_char_cap])

    # Tables: headers + first row
    if tables:
        lines.append("Tables (headers + first row):")
        used_idx2 = set()
        next_idx2 = 0
        for tb in tables[:4]:
            pm = tb.get("pandas_metrics") or {}
            headers = pm.get("columns") or []
            sample_rows = tb.get("pandas_df") or tb.get("pandas_df_dict") or tb.get("rows") or []
            first = sample_rows[0] if sample_rows else []
            try:
                first_row_list = (
                    first if isinstance(first, list) else [first.get(h, "") for h in headers]
                )
            except Exception:
                first_row_list = first if isinstance(first, list) else []

            try:
                tbi2 = int(tb.get("table_index"))
            except Exception:
                tbi2 = None
            if tbi2 in used_idx2 or tbi2 is None:
                while next_idx2 in used_idx2:
                    next_idx2 += 1
                disp_idx2 = next_idx2
                used_idx2.add(disp_idx2)
                next_idx2 += 1
            else:
                disp_idx2 = tbi2
                used_idx2.add(disp_idx2)
            lines.append(
                f"- table idx {disp_idx2} headers={headers} first_row={first_row_list} page={tb.get('page_index')}"
            )

    # Figures: title/caption + bbox/page
    if figures:
        lines.append("Figures (title/caption + bbox/page):")
        for fg in figures[:6]:
            title_f = (fg.get("title") or "").strip()
            cap = (fg.get("caption") or fg.get("ai_description") or "").strip()
            bbox = fg.get("bbox") or fg.get("bbox0") or []
            page = (
                fg.get("page")
                if fg.get("page") is not None
                else (fg.get("page_idx") if fg.get("page_idx") is not None else None)
            )
            if page is None:
                lines.append(
                    f"- figure id={fg.get('figure_id')} title={title_f or None} caption={cap[:160] if cap else None} bbox={bbox}"
                )
            else:
                lines.append(
                    f"- figure id={fg.get('figure_id')} title={title_f or None} caption={cap[:160] if cap else None} bbox={bbox} page={page}"
                )

    # Strict JSON schema reminder
    lines.append(
        dedent(
            """
            Instruction
            Return ONLY one JSON object with keys:
              - reflowed_json { title: string, blocks: [ {paragraph|list|table|figure} … ] }
              - ocr_corrections: {"erroneous": "corrected", …}
              - improvements_made: string
              - summary: string
            No code fences. No extra keys. No explanations outside JSON.
            """
        ).strip()
    )

    return "\n".join(lines).strip()


__all__ = [
    "build_reflow_prompt",
    "build_compact_prompt",
    "build_compact_prompt_simple",
]
