#!/usr/bin/env python3
"""Data loading utilities for Stage 07 Section Reflow.

Handles loading and consolidating data from previous pipeline stages.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
from loguru import logger

from extractor.pipeline.utils.reflow.tables import sanitize_table_cell, df_map
from extractor.pipeline.utils.reflow.layout import horizontal_iou


def merge_text_blocks(blocks: list[dict[str, Any]]) -> str:
    """Minimal normalization: join non-empty lines into paragraphs.

    LLM handles full reflow; this is only for pass-through when needed.
    """
    parts: list[str] = []
    for b in blocks or []:
        txt = (b.get("text") or "").strip()
        if not txt:
            continue
        lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
        if lines:
            parts.append(" ".join(lines))
    return "\n\n".join(parts)


def get_rows_cols(t: dict[str, Any]) -> tuple[int, int]:
    """Extract (rows, cols) from table pandas_metrics."""
    m = t.get("pandas_metrics") or {}
    shape = m.get("shape") or [0, 0]
    try:
        return int(shape[0] or 0), int(shape[1] or 0)
    except Exception:
        return 0, 0


def compute_metrics_for_df(df: pd.DataFrame) -> dict[str, Any]:
    """Compute pandas metrics dict for a DataFrame."""
    try:
        if df is None or df.empty:
            return {"shape": [0, 0], "data_density": 0.0, "columns": []}
        total_cells = int(df.size)
        non_empty = int(df.astype(str).ne("").sum().sum())
        return {
            "shape": [int(df.shape[0]), int(df.shape[1])],
            "columns": [str(c) for c in df.columns],
            "dtypes": {str(k): str(v) for k, v in df.dtypes.to_dict().items()},
            "null_counts": {str(k): int(v) for k, v in df.isnull().sum().to_dict().items()},
            "total_cells": total_cells,
            "non_empty_cells": non_empty,
            "data_density": float(non_empty / total_cells) if total_cells > 0 else 0.0,
        }
    except Exception:
        return {"shape": [0, 0], "data_density": 0.0, "columns": []}


def merge_section_tables(section: dict[str, Any]) -> None:
    """Merge tables within a section when they represent continued parts across pages.

    Modifies section in place.
    """
    tabs = list(section.get("tables") or [])
    if len(tabs) <= 1:
        return

    # Sort by page then by table_index
    try:
        tabs.sort(
            key=lambda t: (
                int(t.get("page_index", 0) or 0),
                int(t.get("table_index", 0) or 0),
            )
        )
    except Exception:
        pass

    merged: list[dict[str, Any]] = tabs[:]
    i = 0
    while i < len(merged) - 1:
        t1, t2 = merged[i], merged[i + 1]
        r1, c1 = get_rows_cols(t1)
        r2, c2 = get_rows_cols(t2)

        if c1 > 0 and c1 == c2 and (t2.get("page_index", 0) <= (t1.get("page_index", 0) or 0) + 1):
            iou = horizontal_iou(
                t1.get("bbox", []) or [0, 0, 0, 0], t2.get("bbox", []) or [0, 0, 0, 0]
            )
            if iou >= 0.2:
                # Case A: header (1 row) + body (>=2 rows)
                if r1 == 1 and r2 >= 2:
                    try:
                        hdr = pd.DataFrame(t1.get("pandas_df") or [])
                        body = pd.DataFrame(t2.get("pandas_df") or [])

                        def _collapse_ws(df: pd.DataFrame) -> pd.DataFrame:
                            """Sanitize DataFrame cells and replace nulls with empty strings."""
                            return df_map(
                                df,
                                lambda v: sanitize_table_cell(v) if not pd.isna(v) else "",
                            )

                        if len(body.columns) == len(hdr.columns):
                            _hdr_clean = _collapse_ws(hdr)
                            body = _collapse_ws(body)
                            new_cols = [
                                (sanitize_table_cell(x) or str(j))
                                for j, x in enumerate(hdr.iloc[0].tolist())
                            ]
                            body.columns = new_cols
                        else:
                            body = _collapse_ws(body)

                        t2["pandas_df"] = body.to_dict("records")
                        t2["pandas_metrics"] = compute_metrics_for_df(body)
                        merged.pop(i)
                        continue
                    except Exception:
                        pass

                # Case B: both bodies with same columns -> concatenate
                if r1 >= 2 and r2 >= 2:
                    try:
                        df1 = pd.DataFrame(t1.get("pandas_df") or [])
                        df2 = pd.DataFrame(t2.get("pandas_df") or [])

                        def _collapse(df: pd.DataFrame) -> pd.DataFrame:
                            """Sanitize DataFrame cells, filling NaNs with empty strings."""
                            return df_map(
                                df,
                                lambda v: sanitize_table_cell(v) if not pd.isna(v) else "",
                            )

                        if len(df1.columns) == len(df2.columns):
                            out = pd.concat([_collapse(df1), _collapse(df2)], ignore_index=True)
                            t1["pandas_df"] = out.to_dict("records")
                            t1["pandas_metrics"] = compute_metrics_for_df(out)
                            merged.pop(i + 1)
                            continue
                    except Exception:
                        pass
        i += 1

    # If multiple remain, keep the densest
    if len(merged) > 1:

        def _density(t: dict[str, Any]) -> float:
            """Return data density as a float from the given dictionary."""
            m = t.get("pandas_metrics") or {}
            try:
                return float(m.get("data_density") or 0.0)
            except Exception:
                return 0.0

        keep = max(merged, key=_density)
        section["tables"] = [keep]
    else:
        section["tables"] = merged


def consolidate_data(
    sections_path: Path,
    tables_path: Path,
    figures_path: Path,
    annotations_path: Optional[Path] = None,
    *,
    embedder: Any = None,
    debug: bool = False,
) -> list[dict[str, Any]]:
    """Reads and merges data from previous stages (sections, tables, figures, annotations).

    Args:
        sections_path: Path to sections JSON from Stage 04
        tables_path: Path to tables JSON from Stage 05
        figures_path: Path to figures JSON from Stage 06
        annotations_path: Optional path to annotations JSON
        embedder: Optional sentence embedder for semantic ranking
        debug: Enable debug output

    Returns:
        List of section dicts with tables, figures, and annotations attached.
    """
    with open(sections_path) as f:
        sections_data = json.load(f).get("sections", [])

    with open(tables_path) as f:
        tables_list = json.load(f).get("tables", [])

    with open(figures_path) as f:
        figures_list = json.load(f).get("figures", [])

    # Index by section id for quick join
    tables_by_section: dict[str, list[dict[str, Any]]] = {}
    for t in tables_list:
        sid = t.get("section_id")
        if sid is None:
            continue
        tables_by_section.setdefault(sid, []).append(t)

    figures_by_section: dict[str, list[dict[str, Any]]] = {}
    for g in figures_list:
        sid = g.get("section_id")
        if sid is None:
            continue
        figures_by_section.setdefault(sid, []).append(g)

    # Load annotations by page (optional)
    annotations_by_page: dict[int, list[dict[str, Any]]] = {}
    source_pdf: Optional[str] = None
    if annotations_path and annotations_path.exists():
        try:
            with open(annotations_path) as f:
                annot_payload = json.load(f)
            source_pdf = annot_payload.get("source_pdf")
            for a in annot_payload.get("annotations", []):
                p = int(a.get("page", -1))
                if p >= 0:
                    annotations_by_page.setdefault(p, []).append(a)
        except Exception as e:
            logger.warning(f"Failed to load annotations from {annotations_path}: {e}")

    for section in sections_data:
        # Source text and merged fallback from blocks
        blocks = section.get("blocks", [])
        section["source_text"] = "\n".join(
            [(b.get("text") or "").strip() for b in blocks if (b.get("text") or "").strip()]
        )
        section["merged_text"] = merge_text_blocks(blocks)
        sid = section.get("id")
        if source_pdf:
            section["source_pdf"] = source_pdf

        # Attach tables and figures
        section["tables"] = tables_by_section.get(sid, [])
        section["figures"] = figures_by_section.get(sid, [])

        # Merge tables within section
        merge_section_tables(section)

        # Attach relevant annotations by page range
        page_start = int(section.get("page_start", 0) or 0)
        page_end = int(section.get("page_end", page_start) or page_start)
        candidates: list[dict[str, Any]] = []
        for p in range(page_start, page_end + 1):
            candidates.extend(annotations_by_page.get(p, []))

        selected: list[dict[str, Any]] = list(candidates)

        # Optionally rank by semantic similarity
        if candidates and embedder is not None:
            try:
                title = section.get("title", "") or ""
                raw_text = section.get("raw_text", "") or ""
                query_text = f"{title}\n{raw_text}".strip()
                q_vec = embedder.encode(query_text, normalize_embeddings=True)

                def _blocks_to_text(block_list: list[dict[str, Any]]) -> str:
                    """Convert a list of blocks to a single text string."""
                    lines: list[str] = []
                    for blk in block_list or []:
                        for ln in blk.get("lines", []):
                            for sp in ln.get("spans", []):
                                t = (sp.get("text") or "").strip()
                                if t:
                                    lines.append(t)
                    return " ".join(lines)

                annot_texts: list[str] = []
                for a in candidates:
                    inside = _blocks_to_text(a.get("inside_blocks", []))
                    above = _blocks_to_text(a.get("above_blocks", []))
                    below = _blocks_to_text(a.get("below_blocks", []))
                    combined = " ".join([inside, above, below]).strip()
                    annot_texts.append(combined if combined else a.get("type", ""))

                a_vecs = embedder.encode(annot_texts, normalize_embeddings=True)
                sims = np.dot(a_vecs, q_vec)
                for i in range(len(candidates)):
                    candidates[i]["similarity"] = float(sims[i])
            except Exception as e:
                logger.warning(f"Annotation semantic ranking failed: {e}")

        section["annotations"] = selected

        if debug:
            section["hybrid_status"] = {
                "page": page_start,
                "on_page_candidates": len(candidates),
                "selected": len(selected),
            }

    return sections_data


__all__ = [
    "merge_text_blocks",
    "get_rows_cols",
    "compute_metrics_for_df",
    "merge_section_tables",
    "consolidate_data",
]
