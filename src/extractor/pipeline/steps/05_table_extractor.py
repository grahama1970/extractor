#!/usr/bin/env python3
"""
Pipeline Stage 5: Table Extraction using Camelot
==============================================

This stage extracts tables from PDFs using Camelot's lattice detection,
which provides more accurate table extraction than pdfplumber.

Key Features:
- Multi-strategy approach (lattice with different settings)
- Intelligent padding for table visualization
- Rich pandas metrics for downstream analysis
- Handles multi-page tables
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

# Direct imports - fail fast
try:
    import fitz  # PyMuPDF
except ImportError:
    print("PyMuPDF (fitz) not installed. Stage 05 requires it.", file=sys.stderr)
    raise
import pandas as pd
try:
    import camelot
    from camelot import io as camelot_io
except ImportError:
    print("Camelot is required for Stage 05 (table extraction). Please install camelot-py.", file=sys.stderr)
    raise
try:
    try:
        import typer
        _HAS_TYPER = True
    except Exception:
        _HAS_TYPER = False
        class _TyperShim:
            def __init__(self,*a,**k): pass
            def command(self,*a,**k): return lambda f: f
            def __call__(self,*a,**k): print("Typer not installed; CLI disabled")
        def _opt(*a,**k): return None
        def _arg(*a,**k): return None
        typer = _TyperShim()  # type: ignore
        typer.Typer = _TyperShim  # type: ignore
        typer.Option = _opt  # type: ignore
        typer.Argument = _arg  # type: ignore
        typer.secho = print  # type: ignore

    _HAS_TYPER = True
except Exception:
    _HAS_TYPER = False
    class _TyperShim:
        def __init__(self,*a,**k): pass
        def command(self,*a,**k): return lambda f: f
        def __call__(self,*a,**k): print("Typer not installed; CLI disabled")
    def _opt(*a,**k): return None
    def _arg(*a,**k): return None
    typer = _TyperShim()  # type: ignore
    typer.Typer = _TyperShim  # type: ignore
    typer.Option = _opt  # type: ignore
    typer.Argument = _arg  # type: ignore
    typer.secho = print  # type: ignore

from dotenv import load_dotenv, find_dotenv
from loguru import logger
from rich.console import Console
from rich.table import Table as RichTable
from io import BytesIO  # kept if needed elsewhere; will avoid PIL roundtrip when saving
from extractor.pipeline.utils.diagnostics import start_resource_sampler, stop_resource_sampler, get_run_id, iso_now, make_event, snapshot_resources, build_stage_timings

# --- Initialization ---
if not load_dotenv(find_dotenv()):
    print("Warning: .env not found; continuing with process environment.", file=sys.stderr)

logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{function}:{line}</cyan> - <level>{message}</level>")

app = typer.Typer(help="Extract tables from PDFs using Camelot")
console = Console()

# Camelot extraction strategies
CAMELOT_STRATEGIES = {
    "lattice_strong": {
        "flavor": "lattice", 
        "params": {"process_background": True, "line_scale": 40}
    },
    "lattice_default": {
        "flavor": "lattice", 
        "params": {"process_background": True, "line_scale": 15}
    },
    "lattice_sensitive": {
        "flavor": "lattice",
        "params": {"process_background": True, "line_scale": 5}
    }
}

# Padding ratios for table image extraction
VERTICAL_PADDING_RATIO = float(os.getenv("TABLE_VERTICAL_PADDING_RATIO", 0.30))
HORIZONTAL_PADDING_RATIO = float(os.getenv("TABLE_HORIZONTAL_PADDING_RATIO", 0.07))
PYMUPDF_DPI = int(os.getenv("TABLE_EXTRACTION_DPI", 200))

# Stitching/overlap and filtering thresholds (env-configurable)
TABLE_STITCH_MIN_HORIZONTAL_IOU = float(os.getenv("TABLE_STITCH_MIN_HORIZONTAL_IOU", 0.2))
TABLE_STITCH_ALLOW_NEXT_PAGE = os.getenv("TABLE_STITCH_ALLOW_NEXT_PAGE", "true").lower() in ("1", "true", "yes", "y")
TABLE_FILTER_MIN_DENSITY = float(os.getenv("TABLE_FILTER_MIN_DENSITY", 0.15))
TABLE_FILTER_MIN_ROWS = int(os.getenv("TABLE_FILTER_MIN_ROWS", 3))
TABLE_HEADER_DUP_MIN_MATCH = float(os.getenv("TABLE_HEADER_DUP_MIN_MATCH", 0.5))

# Multi-page behavior
TABLE_MULTI_PAGE_MERGE_ENABLED = os.getenv("TABLE_MULTI_PAGE_MERGE_ENABLED", "true").lower() in ("1", "true", "yes", "y")
TABLE_MULTI_PAGE_MERGE_MIN_IOU = float(os.getenv("TABLE_MULTI_PAGE_MERGE_MIN_IOU", 0.3))

# Feature toggles (env-configurable)
TABLE_HEADER_STITCHING_ENABLED = os.getenv("TABLE_HEADER_STITCHING_ENABLED", "true").lower() in ("1", "true", "yes", "y")
TABLE_HEADER_DEDUP_ENABLED = os.getenv("TABLE_HEADER_DEDUP_ENABLED", "true").lower() in ("1", "true", "yes", "y")
TABLE_HEADER_COALESCE_ENABLED = os.getenv("TABLE_HEADER_COALESCE_ENABLED", "true").lower() in ("1", "true", "yes", "y")
TABLE_HEADER_REPEAT_MIN_MATCH = float(os.getenv("TABLE_HEADER_REPEAT_MIN_MATCH", 0.6))

# --- Core Functions ---

def generate_pandas_metrics(df: pd.DataFrame) -> Dict[str, Any]:
    """Generate comprehensive metrics from a DataFrame for analysis."""
    if df.empty:
        return {"shape": [0, 0], "error": "Empty DataFrame"}

    total_cells = df.size
    non_empty_cells = df.astype(str).ne('').sum().sum()
    
    metrics = {
        "shape": list(df.shape),
        "columns": [str(c) for c in df.columns],
        "dtypes": {str(k): str(v) for k, v in df.dtypes.to_dict().items()},
        "null_counts": {str(k): int(v) for k, v in df.isnull().sum().to_dict().items()},
        "total_cells": int(total_cells),
        "non_empty_cells": int(non_empty_cells),
        "data_density": float(non_empty_cells / total_cells) if total_cells > 0 else 0.0,
    }
    return metrics

def score_table(df: pd.DataFrame) -> float:
    """Score a table based on non-empty cell count."""
    if df.empty: 
        return 0.0
    return float(df.astype(str).ne('').sum().sum())

def try_camelot_strategy(pdf_path: Path, page_num: int, strategy: Dict[str, Any], diagnostics: Optional[List[Dict[str, Any]]] = None) -> List[Any]:
    """Try a specific Camelot extraction strategy and record diagnostics on failure."""
    page_str = str(page_num + 1)  # Camelot uses 1-based page numbers
    try:
        tables = camelot_io.read_pdf(  # type: ignore[attr-defined]
            str(pdf_path),
            pages=page_str,
            flavor=strategy["flavor"],
            **strategy["params"],
        )
        return list(tables)  # type: ignore[call-arg, return-value]
    except Exception as e:
        logger.warning(f"Strategy '{strategy.get('name', 'unknown')}' failed on page {page_str}: {e}")
        try:
            if diagnostics is not None:
                diagnostics.append(make_event(
                    "05_table_extractor",
                    "warning",
                    "camelot_strategy_failed",
                    str(e),
                    {"page": page_num, "strategy": strategy.get("name")}
                ))
        except Exception:
            pass
        return []
def extract_table_image(pdf_doc: Any, page_num: int, bbox: Tuple[float, float, float, float], output_dir: Path, table_idx: int, diagnostics: Optional[list] = None) -> Optional[str]:
    """Extract table as image with padding."""
    try:
        page = pdf_doc[page_num]
        x1, y1, x2, y2 = bbox
        page_height = page.rect.height
        page_width = page.rect.width

        # Add vertical padding
        table_height = y2 - y1
        vpad = table_height * VERTICAL_PADDING_RATIO
        y1_padded = max(0, y1 - vpad)
        y2_padded = min(page_height, y2 + vpad)

        # Add horizontal padding
        table_width = x2 - x1
        hpad = table_width * HORIZONTAL_PADDING_RATIO
        x1_padded = max(0, x1 - hpad)
        x2_padded = min(page_width, x2 + hpad)

        # Convert to PyMuPDF coordinates (origin top-left)
        # Camelot's y2 is the 'top' (higher value), y1 is 'bottom' (lower value)
        # PyMuPDF's y0 is 'top' (lower value), y1 is 'bottom' (higher value)
        rect_y0 = page_height - y2_padded
        rect_y1 = page_height - y1_padded
        bbox_rect = fitz.Rect(x1_padded, rect_y0, x2_padded, rect_y1)

        # Render the cropped table and save without PIL roundtrip (faster, less memory)
        pix = page.get_pixmap(clip=bbox_rect, dpi=PYMUPDF_DPI)
        img_path = output_dir / f"page_{page_num+1}_table_{table_idx+1}.png"
        try:
            # Let PyMuPDF determine format from extension (PNG)
            pix.save(str(img_path))
        except Exception:
            # Fallback to explicit PNG bytes
            with open(img_path, 'wb') as f:
                f.write(pix.tobytes("png"))
        
        return str(img_path)
    except Exception as e:
        logger.error(f"Failed to extract table image: {e}")
        try:
            if diagnostics is not None:
                diagnostics.append(make_event("05_table_extractor","error","image_extract_failed", str(e), {"page": page_num, "table_idx": table_idx}))
        except Exception:
            pass
        return None

def extract_tables_from_page(
    pdf_path: Path, 
    page_num: int, 
    pdf_doc: Any,
    output_dir: Path,
    last_good_strategy: Optional[str] = None,
    diagnostics: Optional[list] = None
) -> Tuple[List[Dict[str, Any]], Optional[str], Dict[str, Any]]:
    """Extract all tables from a single page using multiple strategies."""
    page_tables = {}
    best_strategy = None
    
    # Order strategies with last successful one first
    strategies_to_try = []
    if last_good_strategy and last_good_strategy in CAMELOT_STRATEGIES:
        strategies_to_try.append({
            "name": last_good_strategy, 
            **CAMELOT_STRATEGIES[last_good_strategy]
        })
    
    for name, config in CAMELOT_STRATEGIES.items():
        if name != last_good_strategy:
            strategies_to_try.append({"name": name, **config})

    # Track per-strategy durations
    strategy_durations = {}
    found_by_strategy = {}
    # Try each strategy
    for strategy in strategies_to_try:
        import time as _t
        _t0=_t.monotonic()
        tables = try_camelot_strategy(pdf_path, page_num, strategy, diagnostics)
        _dt = int((_t.monotonic()-_t0)*1000)
        nm=strategy.get("name")
        strategy_durations.setdefault(nm, {"count":0,"total_ms":0})
        strategy_durations[nm]["count"] += 1
        strategy_durations[nm]["total_ms"] += _dt

        found_count = 0
        for table in tables:
            bbox_tuple = getattr(table, "_bbox", None)
            if not bbox_tuple and hasattr(table, "cells") and getattr(table, "cells"):
                try:
                    xs = [c.x1 for c in table.cells] + [c.x2 for c in table.cells]
                    ys = [c.y1 for c in table.cells] + [c.y2 for c in table.cells]
                    bbox_tuple = (min(xs), min(ys), max(xs), max(ys))
                except Exception:
                    bbox_tuple = None
            score = score_table(table.df)
            if score == 0:
                continue
            if not bbox_tuple:
                # if we cannot determine bbox, skip this table instance
                continue
            bbox_key = tuple(map(int, bbox_tuple))
            
            # Keep the best scoring version of each table
            if bbox_key not in page_tables or score > page_tables[bbox_key]['score']:
                page_tables[bbox_key] = {
                    'table': table,
                    'score': score,
                    'strategy': strategy['name']
                }
                if not best_strategy:
                    best_strategy = strategy['name']
                found_count += 1

        # record per-page count for this strategy after processing
        strategy_durations[nm].setdefault("found", {})[page_num] = int(found_count)

    # Convert to output format
    extracted_tables = []
    table_idx = 0
    
    for bbox_key, table_info in page_tables.items():
        table = table_info['table']
        
        # Extract table image
        bbox_tuple = getattr(table, "_bbox", None)
        if not bbox_tuple and hasattr(table, "cells") and getattr(table, "cells"):
            try:
                xs = [c.x1 for c in table.cells] + [c.x2 for c in table.cells]
                ys = [c.y1 for c in table.cells] + [c.y2 for c in table.cells]
                bbox_tuple = (min(xs), min(ys), max(xs), max(ys))
            except Exception:
                bbox_tuple = None
        img_path = extract_table_image(
            pdf_doc, page_num, bbox_tuple, output_dir, table_idx, diagnostics
        ) if bbox_tuple else None
        
        # Optionally coalesce repeated header rows mid-body before metrics
        df = table.df
        if TABLE_HEADER_COALESCE_ENABLED:
            try:
                df = coalesce_repeated_header_rows(df, TABLE_HEADER_REPEAT_MIN_MATCH)
            except Exception as e:
                logger.debug("Header coalesce failed; continuing")
                try:
                    diagnostics.append(make_event("05_table_extractor","warning","header_coalesce_failed", str(e), {"page_index": page_num, "table_idx": table_idx}))
                except Exception:
                    pass

        # Build table data
        table_data = {
            "page_number": page_num + 1,
            "page_index": page_num,
            "table_index": table_idx + 1,
            "bbox": list(bbox_tuple) if bbox_tuple else [],
            "extraction_method": "camelot",
            "strategy": table_info['strategy'],
            "pandas_df": df.to_dict('records'),
            "pandas_metrics": generate_pandas_metrics(df),
            "camelot_metrics": {
                "accuracy": table.accuracy,
                "whitespace": table.whitespace,
                "order": table.order
            },
            "score": table_info['score']
        }
        
        if img_path:
            # store path relative to results root (../.. from image_output)
            try:
                table_data["table_image_path"] = str(Path(img_path).resolve().relative_to(output_dir.parent.parent.resolve()))
            except Exception:
                table_data["table_image_path"] = img_path
            
        extracted_tables.append(table_data)
        table_idx += 1

    return extracted_tables, best_strategy, strategy_durations

def _normalize_cell(val: Any) -> str:
    s = str(val or '').strip()
    s = s.replace('\u00a0', ' ')  # NBSP -> space
    s = ' '.join(s.split())
    return s.lower()

def coalesce_repeated_header_rows(df: pd.DataFrame, min_match: float = TABLE_HEADER_REPEAT_MIN_MATCH) -> pd.DataFrame:
    """Remove repeated header rows that appear mid-body (common in multi-page Camelot outputs).

    Strategy:
    - Treat the first non-empty row as the header prototype (or use columns if already meaningful).
    - For each subsequent row, compute fraction of columns equal (normalized) to header prototype; if >= min_match, drop row.
    - Preserve original index order.
    """
    if df is None or df.empty:
        return df

    # Determine header prototype
    # Prefer column labels if they are all non-empty strings and not default numeric labels
    header_proto = None
    try:
        cols = list(df.columns)
        if cols and not all(isinstance(c, int) for c in cols):
            header_proto = [_normalize_cell(c) for c in cols]
    except Exception:
        header_proto = None
    if header_proto is None:
        # Use first non-empty row
        for _, row in df.iterrows():
            vals = [_normalize_cell(v) for v in row.tolist()]
            if any(vals):
                header_proto = vals
                break
    if not header_proto:
        return df

    keep_mask = []
    for i, row in df.iterrows():
        vals = [_normalize_cell(v) for v in row.tolist()]
        if not any(vals):
            keep_mask.append(True)
            continue
        # Compute match ratio
        n = max(1, min(len(vals), len(header_proto)))
        matches = sum(1 for a, b in zip(vals[:n], header_proto[:n]) if a == b and a != '')
        ratio = matches / float(n)
        if ratio >= min_match and i != df.index[0]:
            # Drop this repeated header row
            keep_mask.append(False)
        else:
            keep_mask.append(True)
    try:
        df2 = df.loc[df.index[keep_mask]].copy()
        df2.reset_index(drop=True, inplace=True)
        return df2
    except Exception:
        return df

def extract_all_tables(pdf_path: Path, output_dir: Path, diagnostics: Optional[list] = None) -> List[Dict[str, Any]]:
    """Extract all tables from a PDF."""
    all_tables = []
    last_good_strategy = None
    strategy_summary = {}
    
    # Open PDF with PyMuPDF for image extraction
    try:
        pdf_doc = fitz.open(str(pdf_path))
    except Exception as e:
        logger.error(f"Failed to open PDF {pdf_path}: {e}")
        return []
    
    try:
        total_pages = len(pdf_doc)
        console.print(f"[cyan]Processing {total_pages} pages...[/cyan]")
        
        for page_num in range(total_pages):
            logger.info(f"Processing page {page_num + 1}/{total_pages}")
            
            tables, best_strategy, sdurs = extract_tables_from_page(
                pdf_path, page_num, pdf_doc, output_dir, last_good_strategy, diagnostics
            )
            
            if tables:
                all_tables.extend(tables)
            try:
                for k,v in sdurs.items():
                    entry = strategy_summary.setdefault(k, {"attempts": 0, "successes": 0, "failures": 0, "total_duration_ms": 0, "per_page_ms": {}})
                    cnt = int(v.get("count",0) or 0)
                    entry["attempts"] += cnt
                    # Mark success if found>0 for this page
                    found_map = v.get("found") or {}
                    if isinstance(found_map, dict) and int(found_map.get(page_num, 0) or 0) > 0:
                        entry["successes"] += 1
                    else:
                        entry["failures"] += 1
                    dur = int(v.get("total_ms",0) or 0)
                    entry["total_duration_ms"] += dur
                    # Approximate per_page_ms as average duration per attempt for this page
                    per_attempt = int(dur / max(1, cnt)) if cnt else dur
                    entry["per_page_ms"][str(page_num)] = per_attempt
            except Exception:
                pass
                if best_strategy:
                    last_good_strategy = best_strategy
                    
            console.print(f"  Page {page_num + 1}: Found {len(tables)} tables")
            
    finally:
        pdf_doc.close()
        
    return all_tables

@app.command()
def run(
    input_json: Path = typer.Argument(..., help="Path to Stage 04 sections JSON."),
    pdf_dir: Path = typer.Option("data/results/pipeline/01_annotation_processor", "--pdf-dir", help="Directory with the clean PDF from Stage 01."),
    output_dir: Path = typer.Option("data/results/pipeline", "-o", help="Parent directory for pipeline results."),
):
    """Extracts tables from the PDF and associates them with sections."""
    console.print(f"[green]Extracting tables based on sections in: {input_json.name}[/green]")
    run_id = get_run_id()
    diagnostics = []
    errors_count = 0
    warnings_count = 0
    import time
    t0 = time.monotonic()
    stage_start_ts = iso_now()
    resources = snapshot_resources("start")
    import os
    sampler = start_resource_sampler(float(os.getenv("SAMPLE_INTERVAL_SEC", "2"))) if os.getenv("ENABLE_RESOURCE_SAMPLING", "0").lower() in ("1","true","yes","y") else None
    try:
        if sampler and not gpu_metrics_available():
            diagnostics.append(make_event("05_table_extractor","info","gpu_metrics_unavailable","NVML not available; GPU metrics disabled",{}))
    except Exception:
        pass

    # --- Input Validation ---
    if not input_json.exists():
        console.print(f"[red]Input JSON not found: {input_json}[/red]")
        raise typer.Exit(1)
        
    try:
        pdf_path = next(pdf_dir.glob("*_clean.pdf"))
    except StopIteration:
        console.print(f"[red]No '*_clean.pdf' found in --pdf-dir: {pdf_dir}[/red]")
        raise typer.Exit(1)

    with open(input_json, 'r') as f:
        sections_data = json.load(f)
    sections = sections_data.get("sections", [])

    # --- Directory Setup ---
    stage_output_dir = output_dir / "05_table_extractor"
    json_output_dir = stage_output_dir / "json_output"
    image_output_dir = stage_output_dir / "image_output"
    stage_output_dir.mkdir(parents=True, exist_ok=True)
    json_output_dir.mkdir(exist_ok=True)
    image_output_dir.mkdir(exist_ok=True)
    run_id = get_run_id()
    diagnostics = []
    errors_count = 0
    warnings_count = 0
    import time
    t0 = time.monotonic()
    stage_start_ts = iso_now()
    resources = snapshot_resources("start")
    import os
    sampler = start_resource_sampler(float(os.getenv("SAMPLE_INTERVAL_SEC", "2"))) if os.getenv("ENABLE_RESOURCE_SAMPLING", "0").lower() in ("1","true","yes","y") else None
    try:
        if sampler and not gpu_metrics_available():
            diagnostics.append(make_event("05_table_extractor","info","gpu_metrics_unavailable","NVML not available; GPU metrics disabled",{}))
    except Exception:
        pass

    # --- Table Extraction ---
    all_tables = extract_all_tables(pdf_path, image_output_dir, diagnostics)

    # --- Heuristic merge: stitch header-only tables with body tables across pages
    def is_header_row_table(t: Dict[str, Any]) -> bool:
        """Keyword-agnostic heuristic for header-only tables.

        Criteria:
        - Exactly 1 row and at least 2 columns.
        - Average cell length not too large (<= 32 chars).
        - Combined digit ratio across cells < 0.5 (header cells tend to be mostly alphabetic).
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

    def horizontal_iou(a: List[float], b: List[float]) -> float:
        try:
            ax0, _, ax1, _ = a
            bx0, _, bx1, _ = b
            inter = max(0.0, min(ax1, bx1) - max(ax0, bx0))
            uni = max(ax1, bx1) - min(ax0, bx0)
            return float(inter / uni) if uni > 0 else 0.0
        except Exception:
            return 0.0

    def stitch_headers(tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not tables:
            return tables
        # Index candidates by page
        by_page: Dict[int, List[Dict[str, Any]]] = {}
        for t in tables:
            by_page.setdefault(int(t.get("page_index", 0)), []).append(t)

        used_headers: set[int] = set()
        stitched: List[Dict[str, Any]] = []
        for t in tables:
            # Skip header-only tables that will be stitched
            if is_header_row_table(t):
                page = int(t.get("page_index", 0))
                bbox = t.get("bbox", [])
                cols = int((t.get("pandas_metrics", {}) or {}).get("shape", [0, 0])[1] or 0)
                header_idx = id(t)
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
                    m = c.get("pandas_metrics", {}) or {}
                    shape = m.get("shape", [0, 0])
                    rows_c = int(shape[0]) if isinstance(shape, (list, tuple)) and shape else 0
                    cols_c = int(shape[1]) if isinstance(shape, (list, tuple)) and shape else 0
                    if rows_c < 2 or cols_c != cols:
                        continue
                    iou = horizontal_iou(bbox, c.get("bbox", []))
                    if iou < TABLE_STITCH_MIN_HORIZONTAL_IOU:
                        continue
                    score = float(c.get("score", 0.0)) + iou
                    if score > best_score:
                        best_score = score
                        best = c
                if best is not None:
                    # Apply header row as column names for 'best'
                    try:
                        import pandas as pd
                        header_row = (t.get("pandas_df") or [{}])[0]
                        keys = sorted(header_row.keys(), key=lambda k: int(str(k)) if str(k).isdigit() else 9999)
                        new_cols = [str(header_row[k]).strip() or str(i) for i, k in enumerate(keys)]
                        body_df = pd.DataFrame(best.get("pandas_df") or [])
                        if len(body_df.columns) == len(new_cols):
                            body_df.columns = new_cols
                            # Update best table payload and metrics
                            best["pandas_df"] = body_df.to_dict("records")
                            best["pandas_metrics"] = generate_pandas_metrics(body_df)
                            used_headers.add(header_idx)
                    except Exception:
                        pass
                # Don't append header-only table; it will be dropped by filters anyway
                continue
            stitched.append(t)
        return stitched

    if TABLE_HEADER_STITCHING_ENABLED:
        all_tables = stitch_headers(all_tables)
    
    # --- Associate Tables with Sections ---
    for table in all_tables:
        table_bbox = fitz.Rect(table["bbox"])
        for section in sections:
            section_bbox = fitz.Rect(section["bbox"])
            if section["page_start"] <= table["page_index"] <= section["page_end"]:
                if section_bbox.intersects(table_bbox):
                    table["section_id"] = section.get("id", "unknown")
                    break

    # Heuristic filtering: density- and header-aware, with robust fallback
    filtered_tables = []
    for t in all_tables:
        metrics = t.get("pandas_metrics", {}) or {}
        shape = metrics.get("shape", [0, 0])
        rows = int(shape[0]) if isinstance(shape, (list, tuple)) and shape else 0
        cols = int(shape[1]) if isinstance(shape, (list, tuple)) and shape else 0
        density = float(metrics.get("data_density", 0.0) or 0.0)
        # Accept dense multi-row tables; drop header-only or sparse artifacts
        if (rows >= TABLE_FILTER_MIN_ROWS) or (rows >= 2 and density >= TABLE_FILTER_MIN_DENSITY):
            filtered_tables.append(t)
        else:
            try:
                diagnostics.append(make_event("05_table_extractor","warning","table_low_confidence", "Filtered out low-confidence table", {"rows": rows, "cols": cols, "density": density, "page": t.get("page_index"), "strategy": t.get("strategy")}))
            except Exception:
                pass

    # Fallback: if nothing passed filters, keep the highest-scoring table
    if not filtered_tables and all_tables:
        try:
            best = max(all_tables, key=lambda t: float(t.get("score", 0.0)))
            filtered_tables = [best]
        except Exception:
            filtered_tables = all_tables[:1]

    # --- De-duplicate header rows accidentally included in body ---
    try:
        import pandas as pd
    except Exception:
        pd = None  # type: ignore
    if pd is not None and TABLE_HEADER_DEDUP_ENABLED:
        for t in filtered_tables:
            try:
                df = pd.DataFrame(t.get("pandas_df") or [])
                if df.empty:
                    continue
                # Normalize headers and drop any repeated header rows found mid-body (multi-page repeats)
                cols_norm = [str(c).strip().lower() for c in df.columns]
                to_drop = []
                for idx, row in df.iterrows():
                    row_vals = [str(v).strip().lower() for v in row.tolist()]
                    pos_matches = sum(1 for a, b in zip(cols_norm, row_vals) if a == b)
                    match_ratio = pos_matches / max(1, len(cols_norm))
                    if match_ratio >= TABLE_HEADER_DUP_MIN_MATCH:
                        to_drop.append(idx)
                if to_drop:
                    df = df.drop(index=to_drop).reset_index(drop=True)
                    t["pandas_df"] = df.to_dict("records")
                    t["pandas_metrics"] = generate_pandas_metrics(df)
            except Exception:
                continue

    # --- Final Payload and Output ---
    try:
        samples = stop_resource_sampler(sampler) if sampler else []
        if samples:
            resources.setdefault("resource_samples", samples)
    except Exception:
        pass
    timings = build_stage_timings(stage_start_ts, t0)
    try:
        for _k,_v in strategy_summary.items():
            att = int(_v.get("attempts",0) or 0)
            if att > 0:
                _v["avg_duration_ms"] = int(_v.get("total_duration_ms",0) / att)
        timings["strategy_durations"] = strategy_summary
    except Exception:
        pass
    try:
        samples = stop_resource_sampler(sampler) if sampler else []
        if samples:
            resources.setdefault("resource_samples", samples)
    except Exception:
        pass
    timings = build_stage_timings(stage_start_ts, t0)
    try:
        for _k,_v in strategy_summary.items():
            att = int(_v.get("attempts",0) or 0)
            if att > 0:
                _v["avg_duration_ms"] = int(_v.get("total_duration_ms",0) / att)
        timings["strategy_durations"] = strategy_summary
    except Exception:
        pass
    result = {
        "timestamp": datetime.now().isoformat(),
        "source_json": str(input_json),
        "source_pdf": str(pdf_path),
        "status": "Completed",
        "table_count": len(filtered_tables),
        "tables": filtered_tables,
        "run_id": run_id,
        "errors_count": errors_count,
        "warnings_count": warnings_count,
        "diagnostics": diagnostics,
        "timings": timings,
        "resources": resources,
    }

    output_path = json_output_dir / "05_tables.json"
    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    console.print(f"✅ Table extraction complete. Saved {len(filtered_tables)} tables to: {output_path}")

@app.command("debug-bundle")
def debug_bundle(
    bundle: Path = typer.Argument(..., exists=True, file_okay=True, dir_okay=False, readable=True, help="Bundle with keys: sections (Stage 04 object), clean_pdf (path)"),
    output_dir: Path = typer.Option("data/results/pipeline", "-o", help="Parent directory for pipeline results."),
):
    """Run Stage 05 with a consolidated bundle (sections + clean PDF)."""
    stage_output_dir = output_dir / "05_table_extractor"
    json_output_dir = stage_output_dir / "json_output"
    image_output_dir = stage_output_dir / "image_output"
    stage_output_dir.mkdir(parents=True, exist_ok=True)
    json_output_dir.mkdir(exist_ok=True)
    image_output_dir.mkdir(exist_ok=True)
    run_id = get_run_id()
    diagnostics = []
    errors_count = 0
    warnings_count = 0
    import time
    t0 = time.monotonic()
    stage_start_ts = iso_now()
    resources = snapshot_resources("start")
    import os
    sampler = start_resource_sampler(float(os.getenv("SAMPLE_INTERVAL_SEC", "2"))) if os.getenv("ENABLE_RESOURCE_SAMPLING", "0").lower() in ("1","true","yes","y") else None
    try:
        if sampler and not gpu_metrics_available():
            diagnostics.append(make_event("05_table_extractor","info","gpu_metrics_unavailable","NVML not available; GPU metrics disabled",{}))
    except Exception:
        pass

    try:
        data = json.loads(bundle.read_text())
        sections_obj = data.get('sections')
        clean_pdf = data.get('clean_pdf')
        if not sections_obj or not clean_pdf:
            raise ValueError("Bundle must include 'sections' and 'clean_pdf'")
        tmp_sections = stage_output_dir / "_bundle_sections.json"
        tmp_sections.write_text(json.dumps({"sections": sections_obj}))
        pdf_path = Path(clean_pdf)
    except Exception as e:
        typer.secho(f"Failed to load bundle: {e}", fg=typer.colors.RED); raise typer.Exit(1)

    # Extract tables and associate
    all_tables = extract_all_tables(pdf_path, image_output_dir, diagnostics)
    strategy_summary = {}
    with open(tmp_sections, 'r') as f:
        sections_data = json.load(f)
    sections = sections_data.get("sections", [])
    # associate
    for table in all_tables:
        try:
            table_bbox = fitz.Rect(table["bbox"])
            for section in sections:
                section_bbox = fitz.Rect(section["bbox"])
                if section["page_start"] <= table["page_index"] <= section["page_end"] and section_bbox.intersects(table_bbox):
                    table["section_id"] = section.get("id", "unknown"); break
        except Exception:
            continue
    # Basic filter (reuse criteria)
    filtered_tables = []
    for t in all_tables:
        metrics = t.get("pandas_metrics", {}) or {}
        shape = metrics.get("shape", [0, 0])
        rows = int(shape[0]) if isinstance(shape, (list, tuple)) and shape else 0
        density = float(metrics.get("data_density", 0.0) or 0.0)
        if (rows >= TABLE_FILTER_MIN_ROWS) or (rows >= 2 and density >= TABLE_FILTER_MIN_DENSITY):
            filtered_tables.append(t)
    if not filtered_tables and all_tables:
        try:
            best = max(all_tables, key=lambda t: float(t.get("score", 0.0)))
            filtered_tables = [best]
        except Exception:
            filtered_tables = all_tables[:1]

    try:
        samples = stop_resource_sampler(sampler) if sampler else []
        if samples:
            resources.setdefault("resource_samples", samples)
    except Exception:
        pass
    timings = build_stage_timings(stage_start_ts, t0)
    try:
        for _k,_v in strategy_summary.items():
            att = int(_v.get("attempts",0) or 0)
            if att > 0:
                _v["avg_duration_ms"] = int(_v.get("total_duration_ms",0) / att)
        timings["strategy_durations"] = strategy_summary
    except Exception:
        pass
    try:
        samples = stop_resource_sampler(sampler) if sampler else []
        if samples:
            resources.setdefault("resource_samples", samples)
    except Exception:
        pass
    timings = build_stage_timings(stage_start_ts, t0)
    try:
        for _k,_v in strategy_summary.items():
            att = int(_v.get("attempts",0) or 0)
            if att > 0:
                _v["avg_duration_ms"] = int(_v.get("total_duration_ms",0) / att)
        timings["strategy_durations"] = strategy_summary
    except Exception:
        pass
    result = {
        "timestamp": datetime.now().isoformat(),
        "source_pdf": str(pdf_path),
        "status": "Completed",
        "table_count": len(filtered_tables),
        "tables": filtered_tables,
        "run_id": run_id,
        "errors_count": errors_count,
        "warnings_count": warnings_count,
        "diagnostics": diagnostics,
        "timings": timings,
        "resources": resources,
    }
    output_path = json_output_dir / "05_tables.json"
    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    console.print(f"[green]Debug bundle: saved {len(filtered_tables)} tables to {output_path}")


if __name__ == "__main__":
    app()