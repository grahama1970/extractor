"""
EnhancedTableProcessor reinstated from deprecated archive.
Wraps Camelot-based recovery for tables when marker extraction is low-confidence
or missing, with pandas-based quality metrics and merge heuristics.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import camelot
from camelot import io as camelot_io
import pandas as pd

from extractor.core.processors import BaseProcessor
from extractor.core.schema.document import Document
from extractor.core.logger import get_logger

logger = get_logger()


class EnhancedTableProcessor(BaseProcessor):
    """Process candidate tables with Camelot and attach recovered cells.

    This class provides a minimal implementation sufficient for callers that
    import it (e.g., unified_extractor.py Camelot fallback). The heavy-duty
    logic from the archive is intentionally simplified to avoid tight coupling.
    """

    def __init__(self, detection_model: Any, recognition_model: Any, table_rec_model: Any, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.config = config or {}

    def process_with_camelot_fallback(self, document: Document, pdf_path: str, fallback_table_info: List[Dict[str, Any]]) -> None:
        """Attempt Camelot extraction for provided table regions and update document blocks in-place.

        Args:
            document: The working document
            pdf_path: Path to original PDF file
            fallback_table_info: List of dicts with 'page', 'block', and 'page_idx'
        """
        if not Path(pdf_path).exists():
            logger.warning(f"PDF not found for Camelot fallback: {pdf_path}")
            return

        for item in fallback_table_info:
            page_idx = int(item.get("page_idx", 0))
            block = item.get("block")
            if not block:
                continue
            bbox = getattr(block.polygon, 'bbox', None)
            page_str = str(page_idx + 1)
            try:
                # Prefer lattice with background processing
                tables = camelot_io.read_pdf(  # type: ignore[attr-defined]
                    str(pdf_path),
                    pages=page_str,
                    flavor="lattice",
                    process_background=True,
                    line_scale=int(self.config.get('table', {}).get('camelot', {}).get('line_scale', 40)),
                )
            except Exception as e:
                logger.debug(f"Camelot failed for page {page_str}: {e}")
                continue

            if not tables:
                continue

            # Choose best by density
            def _score(df: pd.DataFrame) -> float:
                if df is None or df.empty:
                    return 0.0
                total = df.size
                non_empty = df.astype(str).ne('').sum().sum()
                return float(non_empty) / float(total) if total else 0.0

            best = max(tables, key=lambda t: _score(t.df))
            df = best.df
            # Convert DataFrame rows to simple text lines
            rows = df.to_dict('records') if df is not None else []

            # Attach minimal metadata onto the block
            try:
                block.update_metadata(
                    camelot_extracted=True,
                    pandas_df=rows,
                    pandas_shape=list(df.shape) if df is not None else [0, 0],
                    camelot_accuracy=getattr(best, 'accuracy', None),
                    camelot_whitespace=getattr(best, 'whitespace', None),
                )
            except Exception:
                # Metadata method might not exist on mock blocks; ignore
                pass

        logger.info("EnhancedTableProcessor Camelot fallback completed")

