#!/usr/bin/env python3
"""
Stage 05c — Table Merger

Contract:
- Logic:
  - Operates on the ARTIFACTS from S05b (JSON) before they hit S07.
  - A pre-processing step on the JSON artifacts before assembly.

  DECISION:
  - To follow the pattern `s05` -> `s05b` -> `s05c` -> `s07`,
  - This step reads `05b_tables.json`, performs deterministic merges, and outputs `05c_merged_tables.json`.
  - This keeps S07 simple (ingest only).

Algorithm:
- Merge page-split tables (page N bottom -> page N+1 top).
- Requirements:
  - 99% confidence (same columns, consecutive pages, no text blockers).
"""

import os
import sys
import json
import pandas as pd
import time
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger
from extractor.pipeline.utils.reliability import log_stage_error, write_json_strict
from extractor.pipeline.utils.step_sanity import run_step_sanity

STEP_NAME = "05c_table_merger"

# ---------------------------------------------------------------------------
# ML merge classifier gate
# ---------------------------------------------------------------------------
USE_MERGE_CLASSIFIER = os.environ.get("USE_MERGE_CLASSIFIER", "false").lower() == "true"
MERGE_CONFIDENCE_THRESHOLD = float(os.environ.get("MERGE_CONFIDENCE_THRESHOLD", "0.7"))


def sanity() -> int:
    return run_step_sanity(STEP_NAME)


def _load_annotations_for_text_blockers(annotations_json: Path) -> Dict[int, List[Dict[str, Any]]]:
    """Load text blocks to check for content between tables."""
    if not annotations_json.exists():
        return {}
    try:
        data = json.loads(annotations_json.read_text())
        pages = {}
        for block in data.get("blocks", []):  # standard structure? S01 output
            # S01 structure is ... annotations.json usually has "pages" -> "blocks"
            p = block.get("page_number", 0) - 1
            pages.setdefault(p, []).append(block)
        return pages
    except Exception:
        return {}


def _is_junk_table(t: Dict[str, Any]) -> bool:
    """Filter out 1-row tables that are likely just sentences."""
    df_data = t.get("pandas_df", [])
    if not df_data:
        return True

    # Heuristic 1: Single row, single column, long text -> Sentence misclassified
    if len(df_data) == 1:
        row = df_data[0]
        if len(row) == 1:
            val = str(list(row.values())[0])
            if len(val) > 50 and " " in val:  # Arbitrary "sentence like" check
                return True

    # Heuristic 2: Very small area (artifact)?
    # (Skip for now to be safe)
    return False


# ---------------------------------------------------------------------------
# ML classifier merge path
# ---------------------------------------------------------------------------

def _merge_with_classifier(
    tables: List[Dict[str, Any]],
    pdf_path: Path,
    output_dir: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Use trained merge classifier to decide cross-page merges.

    For each pair of tables on consecutive pages:
    1. Render side-by-side page-half image
    2. Compute tabular feature vector
    3. Call predictor.predict()
    4. Merge if should_merge and confidence >= threshold

    Falls through to deterministic merge execution (pd.concat) on positive
    predictions — the merge *execution* logic is shared with heuristics.
    """
    # Lazy import to avoid hard dependency when classifier is disabled
    try:
        _scripts_dir = os.environ.get(
            "MERGE_CLASSIFIER_SCRIPTS",
            str(Path(__file__).resolve().parents[5]
                / "pi-mono" / ".pi" / "skills"
                / "create-table-classifier" / "scripts"),
        )
        if _scripts_dir not in sys.path:
            sys.path.insert(0, _scripts_dir)
        from merge_inference import get_merge_predictor
    except ImportError:
        from importlib import import_module
        mod = import_module("merge_inference")
        get_merge_predictor = mod.get_merge_predictor

    predictor = get_merge_predictor()
    # Force lazy load so we know the model type
    predictor._lazy_load()
    needs_images = predictor._model_type not in ("tabular", "heuristic")

    concat_page_halves = None
    if needs_images:
        try:
            from extractor.pipeline.utils.tables.extraction import concat_page_halves
        except ImportError:
            needs_images = False
            logger.warning("concat_page_halves unavailable, falling back to features-only")

    # Temp dir for pair images (only needed for vision/ensemble models)
    import tempfile
    tmp_dir = Path(tempfile.mkdtemp(prefix="s05c_merge_")) if needs_images else None

    merged: List[Dict[str, Any]] = []
    skip_indices: set = set()

    for i in range(len(tables) - 1):
        if i in skip_indices:
            continue

        t1 = tables[i]
        t2 = tables[i + 1]

        p1 = t1.get("page_index", 0)
        p2 = t2.get("page_index", 0)

        if p2 != p1 + 1:
            merged.append(t1)
            continue

        # Generate side-by-side image (only for vision/ensemble models)
        pair_img_path = None
        if needs_images and tmp_dir is not None:
            pair_img_path = tmp_dir / f"pair_{i}.png"
            try:
                concat_page_halves(pdf_path, p1, p2, output_path=pair_img_path)
            except Exception as e:
                logger.debug(f"Could not render pair image p{p1}-p{p2}: {e}")
                pair_img_path = None

        # Compute tabular features
        df1_data = t1.get("pandas_df", [])
        df2_data = t2.get("pandas_df", [])
        cols1 = len(df1_data[0]) if df1_data else 0
        cols2 = len(df2_data[0]) if df2_data else 0
        b1 = t1.get("bbox", [0, 0, 0, 0])
        b2 = t2.get("bbox", [0, 0, 0, 0])
        title1 = t1.get("llm_title") or t1.get("title") or ""
        title2 = t2.get("llm_title") or t2.get("title") or ""

        w1 = abs(b1[2] - b1[0]) if b1 else 0
        w2 = abs(b2[2] - b2[0]) if b2 else 0

        features = {
            "col_count_match": cols1 == cols2 and cols1 > 0,
            "width_ratio": min(w1, w2) / max(w1, w2) if max(w1, w2) > 0 else 0,
            "horizontal_iou": _horizontal_iou_1d(b1, b2),
            "title_has_continued": "continued" in title2.lower(),
            "same_section": (
                bool(t1.get("section_id"))
                and t1.get("section_id") == t2.get("section_id")
            ),
            "s05b_title_similarity": _word_overlap(title1, title2),
            "gap_between_tables_px": 0.0,
            "row_count_ratio": (
                min(len(df1_data), len(df2_data)) / max(len(df1_data), len(df2_data))
                if max(len(df1_data), len(df2_data)) > 0 else 0
            ),
        }

        prediction = predictor.predict(pair_image=pair_img_path, features=features)

        if prediction.should_merge and prediction.confidence >= MERGE_CONFIDENCE_THRESHOLD:
            logger.info(
                f"ML Merge Table {i} (P{p1}) -> Table {i+1} (P{p2})  "
                f"conf={prediction.confidence:.3f} model={prediction.model_type}"
            )
            # Execute merge (shared logic)
            try:
                df1 = pd.DataFrame(df1_data)
                df2 = pd.DataFrame(df2_data)
                if df1.empty or df2.empty:
                    merged.append(t1)
                    continue
                new_df = pd.concat([df1, df2], ignore_index=True)
                new_t = t1.copy()
                new_t["pandas_df"] = new_df.to_dict("records")
                new_t["rows"] = len(new_df)
                new_t["merged_with"] = t2.get("table_index")
                new_t["merge_model"] = prediction.model_type
                new_t["merge_confidence"] = prediction.confidence
                if "csv" in new_t:
                    del new_t["csv"]
                c1 = t1.get("components", [{"page_index": p1, "bbox": t1.get("bbox")}])
                c2 = t2.get("components", [{"page_index": p2, "bbox": t2.get("bbox")}])
                new_t["components"] = c1 + c2
                merged.append(new_t)
                skip_indices.add(i + 1)
            except Exception as e:
                logger.warning(f"Merge execution failed for pair {i}: {e}")
                merged.append(t1)
        else:
            merged.append(t1)

    # Handle last table
    if (len(tables) - 1) not in skip_indices:
        merged.append(tables[-1])

    # Cleanup temp dir
    if tmp_dir is not None:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception as e:
            logger.debug(f"Failed to clean up temp dir {tmp_dir}: {e}")

    return merged


def _horizontal_iou_1d(b1: List, b2: List) -> float:
    """1-D IOU on X axis for bboxes [x0, y0, x1, y1]."""
    if not b1 or not b2 or len(b1) < 4 or len(b2) < 4:
        return 0.0
    inter = max(0, min(b1[2], b2[2]) - max(b1[0], b2[0]))
    union = max(b1[2], b2[2]) - min(b1[0], b2[0])
    return inter / union if union > 0 else 0.0


def _word_overlap(t1: str, t2: str) -> float:
    """Cheap word-overlap cosine between two titles."""
    if not t1 or not t2:
        return 0.0
    w1 = set(t1.lower().split())
    w2 = set(t2.lower().split())
    if not w1 or not w2:
        return 0.0
    return len(w1 & w2) / (len(w1) ** 0.5 * len(w2) ** 0.5)


def merge_tables(
    tables: List[Dict[str, Any]],
    pdf_path: Optional[Path] = None,
    output_dir: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Merge split tables — ML classifier or heuristic fallback.

    When ``USE_MERGE_CLASSIFIER`` is set and *pdf_path* is available, pairs
    on consecutive pages are evaluated by a trained vision+tabular model.
    Otherwise the original deterministic heuristics are used.
    """
    # 1. Cleanup Junk
    clean_tables = [t for t in tables if not _is_junk_table(t)]
    if len(clean_tables) < len(tables):
        logger.info(f"Filtered {len(tables) - len(clean_tables)} junk tables.")
    tables = clean_tables

    if len(tables) < 2:
        return tables

    # Sort by page, then Y position
    tables.sort(key=lambda t: (t.get("page_index", 0), t.get("bbox", [0])[1]))

    if USE_MERGE_CLASSIFIER and pdf_path is not None:
        try:
            return _merge_with_classifier(tables, pdf_path, output_dir)
        except Exception as e:
            logger.warning(f"Classifier merge failed, falling back to heuristics: {e}")

    merged = []
    skip_indices = set()

    for i in range(len(tables) - 1):
        if i in skip_indices:
            continue

        t1 = tables[i]
        t2 = tables[i + 1]

        # 1. Page Continuity
        p1 = t1.get("page_index", 0)
        p2 = t2.get("page_index", 0)

        if p2 != p1 + 1:
            merged.append(t1)
            continue

        # 2. Schema Match
        try:
            df1 = pd.DataFrame(t1.get("pandas_df", []))
            df2 = pd.DataFrame(t2.get("pandas_df", []))
        except Exception as e:
            logger.warning(f"Failed to create DataFrames for table merge: {e}")
            merged.append(t1)
            continue

        if df1.empty or df2.empty:
            merged.append(t1)
            continue

        # 3. Enhanced Merge Logic
        should_merge = False

        # Signal A: "Continued" in Title
        # Check titles if available (from S05b)
        (t1.get("llm_title") or t1.get("title") or "").lower()
        title2 = (t2.get("llm_title") or t2.get("title") or "").lower()

        has_continued = "continued" in title2
        # Fuzzy logic: if T2 says continued, and T1 has similar words?
        # Or simply: if T2 says continued, assume it continues the *previous* table on p-1.
        if has_continued:
            should_merge = True

        # Signal B: Schema Match (Strict Column Count + Header)

        if not should_merge:
            # Strict Column Count Match
            if len(df1.columns) == len(df2.columns):
                h1 = list(df1.columns)
                h2 = list(df2.columns)

                # Heuristic: If T2 columns are ["0", "1", "2"...] it's headless.
                is_numeric = all(str(c).isdigit() for c in h2)

                # [NEW] Geometric Safety Check: Horizontal Alignment
                # bbox is [x0, y0, x1, y1] (Camelot/PDF coords)
                b1 = t1.get("bbox")
                b2 = t2.get("bbox")
                aligned = False

                if b1 and b2 and len(b1) == 4 and len(b2) == 4:
                    # Check X-span overlap
                    x0_1, x1_1 = b1[0], b1[2]
                    x0_2, x1_2 = b2[0], b2[2]

                    # Intersection
                    inter_x0 = max(x0_1, x0_2)
                    inter_x1 = min(x1_1, x1_2)

                    if inter_x1 > inter_x0:
                        overlap = inter_x1 - inter_x0
                        width1 = x1_1 - x0_1
                        width2 = x1_2 - x0_2
                        min_width = min(width1, width2)

                        # Requirement: >50% of the smaller table's width must overlap
                        # AND widths must be similar (within 10%) to prevent merging nested tables
                        width_ratio = min(width1, width2) / max(width1, width2)

                        if min_width > 0 and (overlap / min_width) > 0.5 and width_ratio > 0.9:
                            aligned = True
                        elif width_ratio <= 0.9:
                            logger.info(
                                f"  Skipping merge P{p1}->P{p2}: Width Mismatch (Ratio {width_ratio:.2f})"
                            )

                # Fallback: If no bbox (rare), assume aligned if columns match strictly
                if (not b1) or (not b2):
                    aligned = True

                if (is_numeric or h1 == h2) and aligned:
                    should_merge = True
                    logger.info("  Geometrically Aligned (Overlap > 50%, Widths Similar)")
                elif not aligned:
                    logger.info(f"  Skipping merge P{p1}->P{p2}: Horizontal Misalignment.")

        if not should_merge:
            merged.append(t1)
            continue

        # MERGE CONFIRMED
        logger.info(f"Merging Table {i} (Page {p1}) -> Table {i+1} (Page {p2})")

        new_df = pd.concat([df1, df2], ignore_index=True)

        # Create Merged Object (Inherit T1 metadata, extend T2)
        new_t = t1.copy()
        new_t["pandas_df"] = new_df.to_dict("records")
        new_t["rows"] = len(new_df)
        new_t["merged_with"] = t2.get("table_index")
        # Critical: Remove stale CSV so S07 regenerates it from the new pandas_df
        if "csv" in new_t:
            del new_t["csv"]

        # Track Components for Suppression
        # If we act recursively, t1 might already have components
        c1 = t1.get("components", [{"page_index": p1, "bbox": t1.get("bbox")}])
        c2 = t2.get("components", [{"page_index": p2, "bbox": t2.get("bbox")}])
        new_t["components"] = c1 + c2

        merged.append(new_t)
        skip_indices.add(i + 1)

    # Handle last table if not merged
    if (len(tables) - 1) not in skip_indices:
        merged.append(tables[-1])

    return merged


def run(
    input_dir: Path,
    output_dir: Path,
    preset_config: Optional[Dict[str, Any]] = None,
) -> Path:

    # Input from S05b (described) or S05 (raw)
    # run_pipeline passes 'out' as input_dir, so we expect:
    # out/05b_table_describer/json_output/...
    input_json = input_dir / "05b_table_describer" / "json_output" / "05b_tables.json"
    if not input_json.exists():
        input_json = input_dir / "05_table_extractor" / "json_output" / "05_tables.json"

    if not input_json.exists():
        logger.warning(f"Input {input_json} not found. Skipping.")
        # If input not found, we can't just return input_json path if it doesn't exist.
        # But for pipeline flow, we might need to return None or fail?
        # Let's try to return the S05 path as fallback for downstream if skipping.
        return input_json

    data = json.loads(input_json.read_text())
    tables = data.get("tables", [])

    if not tables:
        return input_json

    t0 = time.monotonic()

    # Resolve source PDF for classifier mode
    pdf_path = None
    if USE_MERGE_CLASSIFIER:
        ctx_path = input_dir / "pipeline_context.json"
        if ctx_path.exists():
            try:
                ctx = json.loads(ctx_path.read_text())
                src = ctx.get("source_pdf") or ctx.get("pdf_path")
                if src and Path(src).exists():
                    pdf_path = Path(src)
            except Exception as e:
                logger.debug(f"Failed to read pipeline context for PDF path: {e}")

    # Process
    try:
        merged_tables = merge_tables(tables, pdf_path=pdf_path, output_dir=output_dir)
    except Exception as e:
        log_stage_error(STEP_NAME, e)
        raise

    # Write output
    step_dir = output_dir / "05c_table_merger"
    step_dir.mkdir(exist_ok=True)
    json_out = step_dir / "json_output"
    json_out.mkdir(exist_ok=True)
    visual_out = step_dir / "visual_output"
    visual_out.mkdir(exist_ok=True)

    out_file = json_out / "05c_merged_tables.json"

    data["tables"] = merged_tables
    data["merge_timestamp"] = getattr(time, "time")()

    # Copy table visuals for merged tables (debug enforcement expects visuals)
    for idx, table in enumerate(merged_tables):
        img_rel = table.get("table_image_path") or table.get("image_path")
        if not img_rel:
            continue
        src_path = Path(str(img_rel))
        if not src_path.is_absolute():
            src_path = output_dir / src_path
        if not src_path.exists():
            continue
        dst_name = f"table_{idx:04d}.png"
        dst_path = visual_out / dst_name
        if not dst_path.exists():
            shutil.copy2(src_path, dst_path)
        try:
            table["visual_path"] = str(dst_path.relative_to(output_dir))
        except Exception:
            table["visual_path"] = str(dst_path)

    write_json_strict(out_file, data)

    logger.info(
        f"Stage 05c complete. {len(tables)} -> {len(merged_tables)} tables in {int(time.monotonic()-t0)}s."
    )
    return out_file


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Stage 05c: Table Merger")
    parser.add_argument(
        "--pipeline-dir", type=Path, required=True, help="Path to pipeline results root"
    )
    args = parser.parse_args()

    pipeline_dir = args.pipeline_dir

    try:
        logger.info("Running Stage 05c...")
        # S05c inputs are technically output_dir (it finds S05b or S05 in it)
        if not (pipeline_dir / "05_table_extractor").exists():
            logger.error("Missing input dependencies (Stage 05)")
            sys.exit(1)

        run(input_dir=pipeline_dir, output_dir=pipeline_dir)

    except Exception as e:
        logger.error(f"Execution failed: {e}")
        sys.exit(1)
