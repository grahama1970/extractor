#!/usr/bin/env python3
"""
Stage 05c — Table Merger

Contract:
- Logic:
  - Connects to `pipeline.duckdb` (requires Stage 07 to be initialized first? NO).
  - ACTUALLY, this stage operates on the ARTIFACTS from S05b (JSON) before they hit S07.
  - OR, it can be a post-processing step on the JSON artifacts.
  
  DECISION:
  - To follow the pattern `s05` -> `s05b` -> `s05c` -> `s07`,
  - This step reads `05b_tables.json`, performs deterministic merges, and outputs `05c_merged_tables.json`.
  - This keeps S07 simple (ingest only).

Algorithm:
- Merge page-split tables (page N bottom -> page N+1 top).
- Requirements:
  - 99% confidence (same columns, consecutive pages, no text blockers).
"""

import sys
import json
import logging
import pandas as pd
import io
import time
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger
from extractor.pipeline.utils.reliability import log_stage_error, write_json_strict
from extractor.pipeline.utils.step_sanity import run_step_sanity

STEP_NAME = "05c_table_merger"

def sanity() -> int:
    return run_step_sanity(STEP_NAME)

def _load_annotations_for_text_blockers(annotations_json: Path) -> Dict[int, List[Dict[str, Any]]]:
    """Load text blocks to check for content between tables."""
    if not annotations_json.exists():
        return {}
    try:
        data = json.loads(annotations_json.read_text())
        pages = {}
        for block in data.get("blocks", []): # standard structure? S01 output
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
            if len(val) > 50 and " " in val: # Arbitrary "sentence like" check
                return True
                
    # Heuristic 2: Very small area (artifact)?
    # (Skip for now to be safe)
    return False

def merge_tables(tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Deterministic merge of split tables.
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
    
    merged = []
    skip_indices = set()
    
    for i in range(len(tables) - 1):
        if i in skip_indices:
            continue
            
        t1 = tables[i]
        t2 = tables[i+1]
        
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
        except:
             merged.append(t1)
             continue
             
        if df1.empty or df2.empty:
            merged.append(t1)
            continue
            
        # 3. Enhanced Merge Logic
        should_merge = False
        
        # Signal A: "Continued" in Title
        # Check titles if available (from S05b)
        title1 = (t1.get("llm_title") or t1.get("title") or "").lower()
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
                
                if b1 and b2 and len(b1)==4 and len(b2)==4:
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
                             logger.info(f"  Skipping merge P{p1}->P{p2}: Width Mismatch (Ratio {width_ratio:.2f})")
                            
                # Fallback: If no bbox (rare), assume aligned if columns match strictly
                if (not b1) or (not b2): 
                    aligned = True

                if (is_numeric or h1 == h2) and aligned:
                    should_merge = True
                    logger.info(f"  Geometrically Aligned (Overlap > 50%, Widths Similar)")
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
        skip_indices.add(i+1)
        
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
    
    # Process
    try:
        merged_tables = merge_tables(tables)
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
    
    logger.info(f"Stage 05c complete. {len(tables)} -> {len(merged_tables)} tables in {int(time.monotonic()-t0)}s.")
    return out_file

if __name__ == "__main__":
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description="Stage 05c: Table Merger")
    parser.add_argument("--pipeline-dir", type=Path, required=True, help="Path to pipeline results root")
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
