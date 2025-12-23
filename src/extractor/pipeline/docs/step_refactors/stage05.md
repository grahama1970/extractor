This script contains a mix of **Computer Vision (Camelot/PyMuPDF)**, **Data Science (Pandas)**, **LLM Logic**, and **Heuristic Processing**.

I recommend refactoring this into a sub-package `extractor/pipeline/utils/tables/`.

### Recommended Directory Structure

```text
extractor/pipeline/
├── steps/
│   └── 05_table_extractor.py      <-- Orchestration & Configuration only
└── utils/
    └── tables/
        ├── __init__.py
        ├── extraction.py          <-- Camelot wrappers & Strategy Config
        ├── visuals.py             <-- Image generation & Padding logic
        ├── metrics.py             <-- Pandas scoring & analysis
        ├── heuristics.py          <-- Stitching, Caption detection, Demotion logic
        └── assist.py              <-- LLM-based repairs (split columns, confirm tables)
```

---

### 1\. `extraction.py` (The Camelot Wrapper)

Isolate the external library calls to Camelot.

- **Move:** `try_camelot_strategy`
- **Move:** `CAMELOT_STRATEGIES` (Constant)
- **Move:** `_bbox_tuple_for` (Helper used to normalize Camelot bboxes)

### 2\. `visuals.py` (Image Processing)

Isolate PyMuPDF image extraction and padding math.

- **Move:** `extract_table_image`
- **Configuration:** Move `VERTICAL_PADDING_RATIO`, `HORIZONTAL_PADDING_RATIO`, `PYMUPDF_DPI` constants here.

### 3\. `metrics.py` (Data Analysis)

- **Move:** `generate_pandas_metrics`
- **Move:** `score_table`

### 4\. `heuristics.py` (Logic & Cleanup)

This file handles the messy rules for what counts as a table and how to merge them.

- **Move:** `stitch_headers` (and its helper `horizontal_iou`)
- **Move:** `detect_table_caption` (The PyMuPDF text scanning logic)
- **Move:** `_reconstruct_single_col_header` (The complex text analysis logic)
- **Move:** `_demote_table_headers_to_text`
- **Move:** `_demote_sentence_like_single_row_tables`
- **Move:** `is_header_row_table`
- **Move:** `_iou` (The generic Intersection over Union function)

### 5\. `assist.py` (LLM Operations)

Isolate all code that touches `scillm` or the Router. This is the largest block of code to move.

- **Move:** `_attach_llm_assist_headers` (Very long function)
- **Move:** `_llm_split_single_col_header`
- **Move:** `_llm_confirm_is_table`
- **Move:** `_infer_title_with_scillm`

---

### The New `05_table_extractor.py`

The main file becomes a readable checklist of the pipeline stages:

```python
# ... imports ...
import extractor.pipeline.utils.tables.extraction as ext
import extractor.pipeline.utils.tables.heuristics as heur
import extractor.pipeline.utils.tables.visuals as vis
import extractor.pipeline.utils.tables.assist as assist

def extract_tables_from_page(...):
    # 1. Extract
    tables = ext.try_camelot_strategy(...)

    # 2. Score & Register
    # ... (Keep the local history/score tracking logic here as it manages state) ...

def extract_all_tables(...):
    # ... loop pages ...

    # 3. Stitch Headers
    if TABLE_HEADER_STITCHING_ENABLED:
        all_tables = heur.stitch_headers(all_tables)

    # 4. Filter & Deduplicate
    # ...

    # 5. Extract Visuals
    vis.extract_table_image(...)

    # 6. LLM Assist
    assist.attach_llm_assist_headers(...)
```

### Next Step

The most complex logic to move is **`heuristics.py`** because it contains the delicate "Stitching" and "Reconstruction" logic which relies on both geometry and text analysis. Would you like me to generate that file first?

Here is the code for **`extractor/pipeline/utils/tables/heuristics.py`**.

This module isolates the logic for:

1.  **Stitching**: Merging header-only tables with body tables across pages.
2.  **Detection**: Finding captions/titles using spatial scanning.
3.  **Repair**: reconstructing collapsed single-column headers.
4.  **Demotion**: Converting "fake" tables (sentence fragments, single text lines) back into text blocks for the pipeline.

<!-- end list -->

```python
import os
import re
import fitz  # PyMuPDF
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple, Set

from extractor.pipeline.utils.reliability import log_stage_error
# Import existing text extraction helper if it exists in your project structure
# If not, you can inline the logic for extracting text from a dictionary row.
from extractor.pipeline.utils.table_extractor_utils import _extract_table_text_for_heuristics

# --- Configuration Constants (Env vars moved here) ---
TABLE_STITCH_MIN_HORIZONTAL_IOU = float(os.getenv("TABLE_STITCH_MIN_HORIZONTAL_IOU", 0.2))
TABLE_STITCH_ALLOW_NEXT_PAGE = os.getenv("TABLE_STITCH_ALLOW_NEXT_PAGE", "true").lower() in ("1", "true", "yes", "y")
STAGE05_DEMOTE_MAX_ROWS = int(os.getenv("STAGE05_DEMOTE_MAX_ROWS", "4"))


def iou(a: List[float], b: List[float]) -> float:
    """Calculate Intersection over Union for two [x0, y0, x1, y1] boxes."""
    try:
        ax0, ay0, ax1, ay1 = a
        bx0, by0, bx1, by1 = b
        inter_w = max(0.0, min(ax1, bx1) - max(ax0, bx0))
        inter_h = max(0.0, min(ay1, by1) - max(ay0, by0))
        inter = inter_w * inter_h
        area_a = max(0.0, (ax1 - ax0)) * max(0.0, (ay1 - ay0))
        area_b = max(0.0, (bx1 - bx0)) * max(0.0, (by1 - by0))
        union = area_a + area_b - inter
        return float(inter / union) if union > 0 else 0.0
    except Exception:
        return 0.0


def horizontal_iou(a: List[float], b: List[float]) -> float:
    """Calculate 1D Intersection over Union on the X-axis only."""
    try:
        ax0, _, ax1, _ = a
        bx0, _, bx1, _ = b
        inter = max(0.0, min(ax1, bx1) - max(ax0, bx0))
        uni = max(ax1, bx1) - min(ax0, bx0)
        return float(inter / uni) if uni > 0 else 0.0
    except Exception:
        return 0.0


def is_header_row_table(t: Dict[str, Any]) -> bool:
    """
    Keyword-agnostic heuristic for header-only tables.

    Criteria:
    - Exactly 1 row and at least 2 columns.
    - Average cell length <= 32 chars.
    - Combined digit ratio < 0.5.
    """
    metrics = t.get("pandas_metrics", {}) or {}
    shape = metrics.get("shape", [0, 0])
    rows = int(shape[0]) if isinstance(shape, (list, tuple)) and shape else 0
    cols = int(shape[1]) if isinstance(shape, (list, tuple)) and shape else 0

    if rows != 1 or cols < 2:
        return False

    try:
        first = (t.get("pandas_df") or [{}])[0]
        # Preserving order by numeric key, else arbitrary
        keys = sorted(first.keys(), key=lambda k: int(str(k)) if str(k).isdigit() else 9999)
        values = [str(first[k]).strip() for k in keys]

        if not values:
            return False

        avg_len = sum(len(v) for v in values) / max(1, len(values))
        digits = sum(sum(ch.isdigit() for ch in v) for v in values)
        total = sum(len(v) for v in values) or 1
        digit_ratio = digits / total

        return (avg_len <= 32) and (digit_ratio < 0.5)
    except Exception:
        return False


def stitch_headers(tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Merge header-only tables (e.g. from page breaks) into the body table below them.
    Checks horizontal overlap and page adjacency.
    """
    if not tables:
        return tables

    # Index candidates by page
    by_page: Dict[int, List[Dict[str, Any]]] = {}
    for t in tables:
        by_page.setdefault(int(t.get("page_index", 0)), []).append(t)

    used_headers: Set[int] = set()
    stitched: List[Dict[str, Any]] = []

    for t in tables:
        # Check if this table looks like a detached header row
        if is_header_row_table(t):
            page = int(t.get("page_index", 0))
            bbox = t.get("bbox", [])
            cols = int((t.get("pandas_metrics", {}) or {}).get("shape", [0, 0])[1] or 0)

            # Search body on same or next page
            candidate_pages = [page]
            if TABLE_STITCH_ALLOW_NEXT_PAGE:
                candidate_pages.append(page + 1)

            candidates = []
            for p in candidate_pages:
                candidates.extend(by_page.get(p, []) or [])

            best = None
            best_score = -1.0

            for c in candidates:
                if c is t:
                    continue

                # Candidate must be a valid body (>=2 rows) and match column count
                m = c.get("pandas_metrics", {}) or {}
                shape = m.get("shape", [0, 0])
                rows_c = int(shape[0]) if isinstance(shape, (list, tuple)) and shape else 0
                cols_c = int(shape[1]) if isinstance(shape, (list, tuple)) and shape else 0

                if rows_c < 2 or cols_c != cols:
                    continue

                # Check horizontal alignment
                align_iou = horizontal_iou(bbox, c.get("bbox", []))
                if align_iou < TABLE_STITCH_MIN_HORIZONTAL_IOU:
                    continue

                # Prefer tables with high alignment + high Camelot confidence score
                score = float(c.get("score", 0.0)) + align_iou
                if score > best_score:
                    best_score = score
                    best = c

            if best is not None:
                # Apply header row from 't' as column names for 'best'
                try:
                    header_row = (t.get("pandas_df") or [{}])[0]
                    keys = sorted(
                        header_row.keys(),
                        key=lambda k: int(str(k)) if str(k).isdigit() else 9999,
                    )
                    new_cols = [
                        str(header_row[k]).strip() or str(i) for i, k in enumerate(keys)
                    ]

                    body_df = pd.DataFrame(best.get("pandas_df") or [])
                    if len(body_df.columns) == len(new_cols):
                        body_df.columns = new_cols
                        # Update best table payload and metrics
                        best["pandas_df"] = body_df.to_dict("records")
                        # Re-import generation func locally or passed in?
                        # Ideally metrics.py handles this, but for now we assume simple update
                        # or caller regenerates metrics. We can do a quick calc here:
                        total_cells = body_df.size
                        non_empty = body_df.astype(str).ne("").sum().sum()
                        best["pandas_metrics"] = {
                            "shape": list(body_df.shape),
                            "columns": [str(c) for c in body_df.columns],
                            "data_density": float(non_empty / total_cells) if total_cells > 0 else 0.0,
                        }
                        used_headers.add(id(t))
                except Exception as exc:
                    log_stage_error('05_tables_heuristics', exc, {'context': 'stitch_headers'})
                    pass

            # Don't append header-only table; it will be dropped or merged
            continue

        stitched.append(t)

    return stitched


def detect_table_caption(pdf_path: str, page_index: int, bbox: List[float]) -> Optional[str]:
    """
    Find a nearby caption/title for a table by scanning the PDF text just above it.
    """
    try:
        doc = fitz.open(str(pdf_path))
        page = doc[page_index]
        rect = fitz.Rect(*bbox)

        def _scan_band(top: float) -> Optional[str]:
            band = fitz.Rect(rect.x0, max(0, top), rect.x1, rect.y0)
            blocks = page.get_text('blocks', clip=band)
            blocks = sorted(blocks, key=lambda b: -b[1])  # y desc (bottom-up scan)
            for b in blocks:
                txt = (b[4] or '').strip()
                if not txt:
                    continue
                # Look for "Table X-Y" pattern
                if re.match(r"^\s*Table\s+\d+(?:[-–]\d+)?[.:]", txt, re.IGNORECASE):
                    return txt
            return None

        # Scan narrow (80pt) then wider (200pt)
        cap = _scan_band(max(0, rect.y0 - 80))
        if cap:
            doc.close()
            return cap

        cap = _scan_band(max(0, rect.y0 - 200))
        if cap:
            doc.close()
            return cap

        # Fallback: any block above y0 on the page
        blocks = page.get_text('blocks')
        above = [b for b in blocks if b[3] <= rect.y0]
        above = sorted(above, key=lambda b: -b[1])

        for b in above:
            txt = (b[4] or '').strip()
            if not txt:
                continue
            if re.match(r"^\s*Table\s+\d+(?:[-–]\d+)?[.:]", txt, re.IGNORECASE):
                doc.close()
                return txt

        doc.close()
        return None
    except Exception as exc:
        log_stage_error('05_tables_heuristics', exc, {'context': 'detect_caption'})
        return None


def reconstruct_single_col_header(table: Dict[str, Any], pdf_path: str) -> bool:
    """
    Attempt to reconstruct a table that Camelot collapsed into a single column
    by looking at the word spacing in the original PDF.

    Returns True if the table was successfully modified.
    """
    try:
        pm = table.get("pandas_metrics") or {}
        shape = pm.get("shape") or [0, 0]
        rows = int(shape[0] or 0)
        cols = int(shape[1] or 0)

        # Only targets 1x1 collapsed tables
        if rows != 1 or cols != 1:
            return False

        bbox = table.get("bbox") or []
        if not bbox:
            return False

        page_idx = int(table.get("page_index", 0) or 0)

        with fitz.open(str(pdf_path)) as doc:
            page = doc[page_idx]
            x0, y0, x1, y1 = bbox
            # Convert Camelot (bottom-left origin) to PyMuPDF (top-left origin)
            h = page.rect.height
            rect = fitz.Rect(x0, h - y1, x1, h - y0)

            # Get individual words
            words = page.get_text("words", clip=rect) or []
            words = [w for w in words if (w[4] or "").strip()]

            if not words:
                return False

            # Method 1: Robust whitespace split on the Pandas string
            # (Sometimes Camelot extracts the text correctly but puts it in one cell)
            try:
                src_df = pd.DataFrame(table.get("pandas_df") or [])
                raw_txt = ""
                if not src_df.empty:
                    raw_txt = str(list(src_df.iloc[0].values)[0])
                # Split on double space, pipe, or tabs
                tokens_ws = [t.strip() for t in re.split(r"\s{2,}|\s\|\s|\t+", raw_txt) if t.strip()]
            except Exception:
                tokens_ws = []

            # Method 2: Spatial Clustering of PDF words (X-axis gaps)
            words_sorted = sorted(words, key=lambda w: (float(w[0]), float(w[1])))
            cols_spans: List[List[Tuple[float, float, str]]] = []
            gap_min = 10.0  # points
            cur: List[Tuple[float, float, str]] = []
            prev_x1 = None

            for (wx0, wy0, wx1, wy1, wtxt, *_) in words_sorted:
                if prev_x1 is None:
                    cur = [(wx0, wx1, wtxt)]
                    prev_x1 = wx1
                    continue

                if (wx0 - prev_x1) >= gap_min:
                    if cur:
                        cols_spans.append(cur)
                    cur = [(wx0, wx1, wtxt)]
                else:
                    cur.append((wx0, wx1, wtxt))
                prev_x1 = max(prev_x1, wx1)

            if cur:
                cols_spans.append(cur)

            # Normalize column text from spatial clusters
            col_texts = [" ".join([t[2] for t in col]).strip() for col in cols_spans]

            # Choose the method that yields more columns
            candidates = [tokens_ws, col_texts]
            best = max(candidates, key=lambda L: len(L or []))

            # Simple sanitization
            best = [t.strip() for t in (best or []) if t.strip()]

            # Guardrail: Only accept if we actually found distinct columns (>=3)
            if len(best) < 3:
                return False

            # Rebuild dataframe as 1 row, N columns
            # Handle duplicate headers by appending _1, _2
            uniq: List[str] = []
            seen: Set[str] = set()
            for h in best:
                hh = h
                k = 1
                while hh in seen:
                    k += 1
                    hh = f"{h}_{k}"
                uniq.append(hh)
                seen.add(hh)

            # Create empty DF with these headers (to match structure of header-only table)
            df = pd.DataFrame([uniq], columns=uniq)

            # Update table metadata
            # We record inferred headers rather than mutating the original raw data too heavily,
            # though here we do update header_inferred for downstream use.
            table["header_inferred"] = best
            table["header_provenance"] = "spatial_reconstruction"
            return True

    except Exception as exc:
        log_stage_error('05_tables_heuristics', exc, {'context': 'reconstruct_single_col_header'})
        return False


def demote_table_headers_to_text(result: Dict[str, Any]) -> None:
    """
    Detect one-line numbered headings captured as small tables and emit
    demoted text blocks for Stage 04 to pick up.

    Populates result["demoted_text_blocks"].
    """
    pat = re.compile(r"^(?:\d+\.){1,6}\s+\S.*")
    demoted: List[Dict[str, Any]] = []

    for t in result.get("tables") or []:
        try:
            pm = t.get("pandas_metrics") or {}
            shape = pm.get("shape") or [0, 0]
            rows = int(shape[0] or 0)
            cols = int(shape[1] or 0)
        except Exception:
            rows, cols = 0, 0

        # Filter: must be small (<=2 cols, <=4 rows)
        if cols > 2 or rows > STAGE05_DEMOTE_MAX_ROWS:
            continue

        # Get first cell content
        src = t.get("pandas_df_raw") or t.get("pandas_df") or []
        cells: List[str] = []

        if isinstance(src, list):
            for r in src[:8]:
                if isinstance(r, dict):
                    cells.extend([str(v).strip() for v in r.values()])
                elif isinstance(r, list):
                    cells.extend([str(v).strip() for v in r])

        head = next((c for c in cells if c), None)

        # Must match numbering pattern (e.g. "1.2 Title")
        if not head or not pat.match(head):
            continue

        # Must not end in sentence punctuation (likely just a sentence)
        if head.endswith('.') or head.endswith(';'):
            continue

        try:
            if t.get("page_index") is not None:
                p = int(t.get("page_index"))
            else:
                p = int(t.get("page_number", 1)) - 1
        except Exception:
            p = 0

        bbox = t.get("bbox") or []
        demoted.append({"page_idx": p, "bbox": bbox, "text": head})

    if demoted:
        result["demoted_text_blocks"] = demoted


def demote_sentence_like_single_row_tables(result: Dict[str, Any]) -> None:
    """
    Demote single-row tables that look like simple sentences back to text blocks.

    Criteria: rows==1 and text has >= 6 words and ends with punctuation.
    """
    tables = list(result.get("tables") or [])
    keep: List[Dict[str, Any]] = []
    demoted: List[Dict[str, Any]] = result.get("demoted_text_blocks", []) or []

    for t in tables:
        pm = (t.get("pandas_metrics") or {}).get("shape") or []
        rows = int(pm[0]) if len(pm) > 0 and str(pm[0]).isdigit() else None

        if rows != 1:
            keep.append(t)
            continue

        txt = _extract_table_text_for_heuristics(t)
        words = len(txt.split())
        looks_sentence = words >= 6 and bool(re.search(r"[\.!?]\s*$", txt))

        if looks_sentence:
            try:
                p = int(t.get("page_index") if t.get("page_index") is not None else int(t.get("page_number", 1)) - 1)
            except Exception:
                p = 0
            demoted.append({
                "page_idx": p,
                "bbox": t.get("bbox") or [],
                "text": txt,
                "reason": "sentence_like_single_row"
            })
        else:
            keep.append(t)

    result["tables"] = keep
    if demoted:
        result["demoted_text_blocks"] = demoted
```
