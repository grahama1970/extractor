"""Bridge between /extract-tables dual_extract and S05 pipeline output schema.

Runs Camelot + pdf_oxide in parallel threads, compares results by bbox IoU,
and returns tables in S05's expected dict format. Disagreements are quarantined
to a JSONL file for /interview review before ArangoDB storage.

Standalone entry point (replaces S05 when EXTRACTOR_ENGINE=dual):
    from extractor.pipeline.utils.tables.dual_bridge import run_dual_s05
    out_path = run_dual_s05(pdf_path, output_dir, sections_data=sections)

Library usage:
    from extractor.pipeline.utils.tables.dual_bridge import extract_dual
    tables, quarantine_path, summary = extract_dual(pdf_path, pages="all")
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

# Ensure /extract-tables skill is importable
_SKILL_DIR = Path.home() / ".claude" / "skills" / "extract-tables"
_SKILL_SRC = _SKILL_DIR / "src"
if str(_SKILL_SRC) not in sys.path:
    sys.path.insert(0, str(_SKILL_SRC))


def _ensure_dual_extract():
    """Import dual_extract, registering the package if needed."""
    try:
        from python.dual_extract import dual_extract, quarantine_to_jsonl
        return dual_extract, quarantine_to_jsonl
    except ImportError as e:
        logger.warning(f"dual_extract not available: {e}")
        return None, None


def _comparison_to_s05_table(comp, extraction_method: str) -> Optional[Dict[str, Any]]:
    """Convert a TableComparison to S05 pipeline table dict format.

    Picks the best table based on comp.best_source and converts to S05 schema.
    """
    table_obj = None
    metrics = {}

    if comp.best_source == "native" and comp.native_table:
        table_obj = comp.native_table
        extraction_method = "pdf_oxide"
        metrics = {
            "accuracy": comp.native_accuracy,
            "whitespace": getattr(table_obj, "whitespace", 0),
        }
    elif comp.best_source == "camelot" and comp.camelot_table:
        table_obj = comp.camelot_table
        extraction_method = "camelot"
        metrics = {
            "accuracy": comp.camelot_accuracy,
            "whitespace": getattr(table_obj, "whitespace", None),
        }
    elif comp.native_table:
        table_obj = comp.native_table
        extraction_method = "pdf_oxide"
        metrics = {"accuracy": comp.native_accuracy, "whitespace": 0}
    elif comp.camelot_table:
        table_obj = comp.camelot_table
        extraction_method = "camelot"
        metrics = {"accuracy": comp.camelot_accuracy, "whitespace": None}
    else:
        return None

    # Build S05 table dict
    if extraction_method == "pdf_oxide":
        # pdf_oxide table object
        try:
            df = table_obj.df  # polars DataFrame
            df_records = df.to_dicts() if hasattr(df, "to_dicts") else []
            shape = [table_obj.rows, table_obj.cols]
        except Exception:
            df_records = []
            shape = list(comp.native_shape)
    else:
        # Camelot table object
        try:
            df = table_obj.df  # pandas DataFrame
            df_records = df.to_dict("records") if not df.empty else []
            shape = list(df.shape)
        except Exception:
            df_records = []
            shape = list(comp.camelot_shape)

    return {
        "page_number": comp.page,
        "page_index": comp.page - 1 if comp.page > 0 else 0,
        "table_index": 0,  # reassigned by caller
        "bbox": list(comp.bbox),
        "extraction_method": extraction_method,
        "strategy": f"dual_{extraction_method}",
        "fragmentation_score": 0,
        "pandas_df": df_records,
        "pandas_metrics": {"shape": shape},
        "camelot_metrics": metrics,
        "score": metrics.get("accuracy", 0),
        "quality_fallback": False,
        "strategy_history": [
            {
                "strategy": "dual",
                "agreement": comp.agreement,
                "native_shape": list(comp.native_shape),
                "camelot_shape": list(comp.camelot_shape),
                "cell_diffs": comp.cell_diffs,
                "best_source": comp.best_source,
            }
        ],
        "table_image_path": None,
        "dual_comparison": comp.to_dict(),
        "section_id": comp.section_id,
    }


def extract_dual(
    pdf_path: Path,
    pages: str = "all",
    flavor: str = "lattice",
    iou_threshold: float = 0.3,
    quarantine_dir: Optional[Path] = None,
) -> Tuple[List[Dict[str, Any]], Optional[Path], Dict[str, Any]]:
    """Run dual extraction (Camelot + pdf_oxide) and return S05-compatible tables.

    Args:
        pdf_path: Path to PDF file
        pages: Page spec (e.g. "1", "1,2,3", "all")
        flavor: Extraction flavor ("lattice", "stream", "auto")
        iou_threshold: Minimum bbox IoU for table matching
        quarantine_dir: Directory for quarantine JSONL (default: alongside PDF)

    Returns:
        (tables, quarantine_path, summary) where:
        - tables: list of S05-compatible table dicts (agreed tables only)
        - quarantine_path: path to quarantine JSONL if disagreements exist, else None
        - summary: dict with extraction stats
    """
    dual_extract_fn, quarantine_fn = _ensure_dual_extract()
    if dual_extract_fn is None:
        logger.error("dual_extract not available — falling back to Camelot-only")
        return [], None, {"error": "dual_extract_unavailable"}

    t0 = time.monotonic()
    result = dual_extract_fn(
        str(pdf_path),
        pages=pages,
        flavor=flavor,
        iou_threshold=iou_threshold,
    )
    elapsed = time.monotonic() - t0

    # Convert agreed tables to S05 format
    tables = []
    idx = 1
    for comp in result.comparisons:
        if comp.agreement in ("match", "shape_match", "native_only", "camelot_only"):
            table_dict = _comparison_to_s05_table(comp, "dual")
            if table_dict:
                table_dict["table_index"] = idx
                tables.append(table_dict)
                idx += 1

    # Quarantine disagreements
    quarantine_path = None
    if result.quarantined:
        if quarantine_dir is None:
            quarantine_dir = Path(pdf_path).parent
        quarantine_dir = Path(quarantine_dir)
        quarantine_dir.mkdir(parents=True, exist_ok=True)
        quarantine_path = quarantine_dir / "quarantine.jsonl"
        quarantine_fn(result, str(quarantine_path))
        logger.warning(
            f"Quarantined {len(result.quarantined)} tables to {quarantine_path}"
        )

    summary = {
        "mode": "dual",
        "native_elapsed": result.native_elapsed,
        "camelot_elapsed": result.camelot_elapsed,
        "total_elapsed": elapsed,
        "agreed": len(result.agreed),
        "quarantined": len(result.quarantined),
        "native_only": len(result.native_only),
        "camelot_only": len(result.camelot_only),
        "native_error": result.native_error,
        "camelot_error": result.camelot_error,
        "tables_returned": len(tables),
    }

    logger.info(
        "Dual extraction {}: {} tables ({} agreed, {} quarantined) in {:.1f}s",
        Path(pdf_path).name,
        len(tables),
        summary["agreed"],
        summary["quarantined"],
        elapsed,
    )

    return tables, quarantine_path, summary


def _rects_intersect(a: list, b: list) -> bool:
    """Check if two bboxes [x0,y0,x1,y1] overlap."""
    return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]


def run_dual_s05(
    pdf_path: Path,
    output_dir: Path,
    sections_data: Optional[Dict[str, Any]] = None,
    input_json: Optional[Path] = None,
) -> Path:
    """Standalone S05 replacement: dual extraction producing 05_tables.json.

    Writes the same output format as s05_table_extractor.run() so downstream
    pipeline stages (S11 json_exporter, S12 framework_mapper) work unchanged.

    Args:
        pdf_path: Path to the PDF
        output_dir: Pipeline output_dir (parent of 05_table_extractor/)
        sections_data: Parsed sections JSON (from S01-S04). If None, reads input_json.
        input_json: Path to sections JSON file (fallback if sections_data not provided)

    Returns:
        Path to the written 05_tables.json
    """
    from datetime import datetime

    stage_dir = Path(output_dir) / "05_table_extractor"
    json_dir = stage_dir / "json_output"
    stage_dir.mkdir(parents=True, exist_ok=True)
    json_dir.mkdir(exist_ok=True)

    # Load sections for section association
    sections = []
    if sections_data is None and input_json and Path(input_json).exists():
        sections_data = json.loads(Path(input_json).read_text())
    if sections_data:
        sections = sections_data.get("sections", [])

    t0 = time.monotonic()

    all_tables, quarantine_path, summary = extract_dual(
        pdf_path,
        pages="all",
        flavor="lattice",
        quarantine_dir=stage_dir,
    )

    # Associate tables with sections (same logic as S05)
    for t in all_tables:
        t_bbox = t["bbox"]
        for s in sections:
            s_bbox = s.get("bbox")
            if not s_bbox:
                continue
            if (
                s.get("page_start", 0) <= t["page_index"] <= s.get("page_end", 9999)
                and _rects_intersect(t_bbox, s_bbox)
            ):
                t["section_id"] = s.get("id")
                break

    elapsed_ms = int((time.monotonic() - t0) * 1000)

    res = {
        "timestamp": datetime.now().isoformat(),
        "source_pdf": str(pdf_path),
        "status": "Completed",
        "table_count": len(all_tables),
        "tables": all_tables,
        "metrics": {
            "quality": {
                "pages_processed": 0,
                "param_source": "dual",
                "dual_summary": summary,
            },
            "strategies": {"dual": {"attempts": 1, "successes": 1}},
        },
        "timings": {"duration": elapsed_ms},
        "quality_summary": summary,
        "quality_warnings": [],
    }

    if quarantine_path:
        res["quarantine_path"] = str(quarantine_path)
        res["quarantine_count"] = summary.get("quarantined", 0)

    out_path = json_dir / "05_tables.json"
    out_path.write_text(json.dumps(res, indent=2, ensure_ascii=False))
    logger.info("Dual S05 wrote {} tables to {}", len(all_tables), out_path)

    return out_path


def run(
    input_json: Path,
    pdf_dir: Path = Path("data/results/pipeline/01_annotation_processor"),
    output_dir: Path = Path("data/results/pipeline"),
) -> Path:
    """Drop-in replacement for s05_table_extractor.run() with dual extraction.

    Same signature as S05's run() so it can be swapped in run_pipeline.py:
        _step("05_table_extractor", dual_bridge.run, a04_path, pdf_dir, out, ...)
    """
    input_json = Path(input_json)
    if not input_json.exists():
        raise FileNotFoundError(f"Input JSON missing: {input_json}")

    sections_data = json.loads(input_json.read_text())

    # Find the PDF (same logic as S05)
    pdf_path = None
    clean_key = sections_data.get("clean_pdf")
    if clean_key and Path(clean_key).exists():
        pdf_path = Path(clean_key)
    if not pdf_path:
        src_key = sections_data.get("source_pdf")
        if src_key:
            candidate = Path(pdf_dir) / f"{Path(src_key).stem}_clean.pdf"
            if candidate.exists():
                pdf_path = candidate
    if not pdf_path:
        try:
            pdf_path = next(Path(pdf_dir).glob("*_clean.pdf"))
        except StopIteration:
            raise FileNotFoundError(f"No *_clean.pdf found in {pdf_dir}")

    return run_dual_s05(pdf_path, output_dir, sections_data=sections_data)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Dual extraction (Camelot + pdf_oxide)")
    parser.add_argument("input_json", type=Path, help="Sections JSON from S04")
    parser.add_argument("--pdf-dir", type=Path, default=Path("."), help="Directory with clean PDFs")
    parser.add_argument("--output-dir", type=Path, default=Path("."), help="Pipeline output directory")
    args = parser.parse_args()

    out = run(args.input_json, args.pdf_dir, args.output_dir)
    print(f"Output: {out}")
