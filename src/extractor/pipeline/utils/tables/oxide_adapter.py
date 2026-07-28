"""Adapter: make pdf_oxide table dicts quack like Camelot table objects.

S05's extract_tables_from_page calls try_camelot_strategy() which returns
Camelot table objects with .df, ._bbox, .accuracy, .whitespace, .parsing_report.

This module provides:
  - OxideTableProxy: wraps a pdf_oxide dict to match that interface
  - try_oxide_strategy: drop-in replacement for try_camelot_strategy

Usage in extraction.py:
    from .oxide_adapter import try_oxide_strategy
    tables = try_oxide_strategy(pdf_path, page_num, strategy)
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from loguru import logger


class OxideTableProxy:
    """Wraps a pdf_oxide read_pdf() dict to look like a Camelot table object.

    Attributes accessed by S05:
        .df            -> pandas DataFrame
        ._bbox         -> (x0, y0, x1, y1)
        .accuracy      -> float
        .whitespace    -> float
        .parsing_report -> dict with "accuracy" key
    """

    def __init__(self, table_dict: dict):
        self._raw = table_dict
        self._bbox = tuple(table_dict["bbox"]) if "bbox" in table_dict else None
        self.accuracy = table_dict.get("accuracy", 0.0)
        self.whitespace = table_dict.get("whitespace", 0.0)
        self.parsing_report = {
            "accuracy": self.accuracy,
            "whitespace": self.whitespace,
            "page": table_dict.get("page", 0) + 1,
            "order": table_dict.get("order", 0) + 1,
        }

        # Build pandas DataFrame from df_data (list of dicts with string keys)
        df_data = table_dict.get("df_data", [])
        if df_data:
            self.df = pd.DataFrame(df_data)
        else:
            # Fallback: build from raw data (2D list)
            data = table_dict.get("data", [])
            if data:
                ncols = len(data[0]) if data else 0
                self.df = pd.DataFrame(data, columns=[str(i) for i in range(ncols)])
            else:
                self.df = pd.DataFrame()


def try_oxide_strategy(
    pdf_path: Path,
    page_num: int,
    strategy: Dict[str, Any],
    diagnostics: Optional[List[Dict[str, Any]]] = None,
) -> List[OxideTableProxy]:
    """Drop-in replacement for try_camelot_strategy using pdf_oxide.

    Returns list of OxideTableProxy objects that S05 can use identically
    to Camelot table objects.
    """
    try:
        import pdf_oxide
    except ImportError:
        logger.error("pdf_oxide not installed")
        return []

    page_str = str(page_num + 1)
    flavor = strategy.get("flavor", "lattice")
    params = strategy.get("params", {})

    try:
        doc = pdf_oxide.PdfDocument(str(pdf_path))
        raw_tables = doc.read_pdf(
            pages=page_str,
            flavor=flavor,
            line_scale=params.get("line_scale"),
            edge_tol=params.get("edge_tol"),
        )
        return [OxideTableProxy(t) for t in raw_tables]
    except Exception as e:
        logger.warning(
            "pdf_oxide strategy '{}' failed on page {}: {}",
            strategy.get("name", "unknown"),
            page_str,
            e,
        )
        return []
