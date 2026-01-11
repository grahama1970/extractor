#!/usr/bin/env python3
"""
Stage 05b — Table Describer (VLM Batch)

Contract:
- Inputs: Stage 05 tables JSON (Camelot extraction with images).
- Logic:
  - Reads `05_tables.json`.
  - Builds batch requests for Chutes VLM (Table Image).
  - Uses `scillm.parallel_acompletions_iter` for batch processing.
  - Updates tables with `ai_description` and `ai_title`.
- Outputs: Creates `05b_tables.json` with enrichment.
"""

import asyncio
import base64
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List

from dotenv import find_dotenv, load_dotenv
from loguru import logger
from scillm.batch import parallel_acompletions_iter

from extractor.pipeline.utils.reliability import log_stage_error, write_json_strict
from extractor.pipeline.utils.step_sanity import run_step_sanity
from extractor.pipeline.steps.scillm_preflight_validator import require_scillm_preflight

load_dotenv(find_dotenv())

STEP_NAME = "05b_table_describer"

# Tunables
CONCURRENCY = int(os.getenv("STAGE05B_CONCURRENCY", "6"))
VLM_TIMEOUT_SEC = float(os.getenv("STAGE05B_VLM_TIMEOUT_SEC", "45"))
MODEL = os.getenv("CHUTES_VLM_MODEL", "chutes/vlm")


def sanity() -> int:
    return run_step_sanity(STEP_NAME)


def _encode_image(path: Path) -> str:
    """Read image file and return base64 string."""
    try:
        return base64.b64encode(path.read_bytes()).decode("utf-8")
    except Exception as e:
        logger.warning(f"Failed to read image {path}: {e}")
        return ""


async def process_tables(tables: List[Dict[str, Any]], output_dir: Path) -> List[Dict[str, Any]]:
    """Batch process tables using VLM."""
    
    requests = []
    # Map index to table object to update later
    tbl_map = {}
    
    system_prompt = (
        "You are a table extraction assistant. Analyze the table image. "
        "Return strict JSON with keys: "
        "title (short descriptive title), "
        "description (summary of the table structure and content), "
        "headers (list of inferred column headers if visible)."
    )

    valid_req_count = 0
    for idx, tbl in enumerate(tables):
        # Skip if already described (idempotency)
        if tbl.get("ai_description"):
            pass
            
        img_rel = tbl.get("table_image_path")
        if not img_rel:
            continue
            
        # Resolve image path relative to pipeline root
        full_img_path = output_dir / img_rel
        if not full_img_path.exists():
            full_img_path = output_dir.parent / img_rel # fallback hack
            
        if not full_img_path.exists():
            logger.warning(f"Table image not found: {full_img_path}")
            continue

        b64 = _encode_image(full_img_path)
        if not b64:
            continue
            
        # We can also pass partial CSV context if we trust Camelot, but VLM purely visual is requested
        # context = tbl.get("csv", "")[:500] 
        
        user_parts = [
            {"type": "text", "text": "Describe this table."},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        ]
        
        requests.append({
            "model": MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_parts}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
            "index": idx
        })
        tbl_map[idx] = tbl
        valid_req_count += 1

    if not requests:
        logger.info("No table images to describe.")
        return tables

    logger.info(f"Describing {len(requests)} tables with {MODEL} (concurrency={CONCURRENCY})...")
    
    api_key = os.getenv("CHUTES_API_KEY")
    api_base = os.getenv("CHUTES_API_BASE", "https://llm.chutes.ai/v1")

    async for result in parallel_acompletions_iter(
        requests,
        api_base=api_base,
        api_key=api_key,
        concurrency=CONCURRENCY,
        timeout=VLM_TIMEOUT_SEC,
        response_format={"type": "json_object"},
        retry_invalid_json=2,
    ):
        idx = result.get("index")
        if idx is None: continue
            
        tbl = tbl_map.get(idx)
        if not tbl: continue

        if not result.get("ok"):
            logger.warning(f"Failed to describe table {idx}: {result.get('error')}")
            continue

        # Parse JSON
        content = result.get("parsed") or result.get("content") or {}
        if isinstance(content, str) and content:
             try:
                 import json_repair
                 content = json_repair.loads(content)
             except:
                 content = {}

        if content:
             tbl["ai_description"] = content.get("description")
             tbl["ai_title"] = content.get("title")
             tbl["ai_headers"] = content.get("headers")

    return tables


def run(
    stage_05_dir: Path,
    output_dir: Path, 
    skip_descriptions: bool = False
) -> Path:
    
    if skip_descriptions:
        logger.info("Skipping VLM table descriptions (requested).")
        # Just return input, or copy to new spot?
        # Better to copy to maintain S05b output contract
        input_json = stage_05_dir / "json_output" / "05_tables.json"
        step_dir = output_dir / "05b_table_describer"
        step_dir.mkdir(exist_ok=True)
        json_out = step_dir / "json_output"
        json_out.mkdir(exist_ok=True)
        out_file = json_out / "05b_tables.json"
        if input_json.exists():
            out_file.write_bytes(input_json.read_bytes())
        return out_file

    require_scillm_preflight()

    input_json = stage_05_dir / "json_output" / "05_tables.json"
    if not input_json.exists():
        logger.warning(f"Input {input_json} not found. Skipping.")
        return input_json

    data = json.loads(input_json.read_text())
    tables = data.get("tables", [])
    
    if not tables:
        logger.info("No tables found in Step 05 output.")
        return input_json
        
    t0 = time.monotonic()
    
    # Process
    try:
        enriched_tables = asyncio.run(process_tables(tables, output_dir))
    except Exception as e:
        log_stage_error(STEP_NAME, e)
        raise

    # Write output
    step_dir = output_dir / "05b_table_describer"
    step_dir.mkdir(exist_ok=True)
    json_out = step_dir / "json_output"
    json_out.mkdir(exist_ok=True)
    
    out_file = json_out / "05b_tables.json"
    
    data["tables"] = enriched_tables
    data["enriched_timestamp"] = getattr(time, "time")()
    
    write_json_strict(out_file, data)
    
    logger.info(f"Stage 05b complete. Enriched {len(enriched_tables)} tables in {int(time.monotonic()-t0)}s.")
    return out_file

if __name__ == "__main__":
    import argparse
    import sys
    from extractor.pipeline.utils import ralph
    
    parser = argparse.ArgumentParser(description="Stage 05b: Table Describer (Ralph Enabled)")
    parser.add_argument("--pipeline-dir", type=Path, required=True, help="Path to pipeline results root")
    parser.add_argument("--verify-only", action="store_true", help="Only verify existing results without running")
    args = parser.parse_args()
    
    pipeline_dir = args.pipeline_dir
    stage_dir = pipeline_dir / "05_table_extractor"
    
    # Run Generation
    if not args.verify_only:
        try:
            logger.info("Ralph: Running Stage 05b...")
            if not stage_dir.exists():
                logger.error("Missing input dependencies (Stage 05)")
                sys.exit(1)
            
            run(stage_05_dir=stage_dir, output_dir=pipeline_dir)
            
        except Exception as e:
            logger.error(f"Ralph: Execution failed: {e}")
            sys.exit(1)

    # Verification
    try:
        out_file = pipeline_dir / "05b_table_describer/json_output/05b_tables.json"
        
        ralph.assert_helping(out_file.exists(), "05b_tables.json output exists")
        data = ralph.check_json_file_valid(out_file, key_check=["tables"])
        tables = data.get("tables", [])
        
        # If no tables extracted in S05, S05b is trivially successful (0 in, 0 out)
        if len(tables) == 0:
             logger.info("Ralph: No tables to describe. Trivial success.")
             print("✅ Ralph is happy! Stage 05b is active (but no input data).")
             sys.exit(0)
        
        ralph.assert_helping(len(tables) > 0, f"Found {len(tables)} tables")
        
        # Check Enrichment
        # We check if `ai_description` is populated for substantial tables
        described_count = 0
        substantial_count = 0
        for t in tables:
             # Heuristic for substantial table: has image path
             if t.get("table_image_path"):
                 substantial_count += 1
                 if t.get("ai_description"):
                     described_count += 1
                     
        if substantial_count == 0:
             logger.warning("Ralph: Tables present but no images? Might be text-only tables.")
        else:
             logger.info(f"Ralph: Found {described_count} described tables out of {substantial_count} substantial tables.")
             # We expect at least some to be described if substantial
             if described_count == 0:
                  logger.warning("Ralph: No tables were described. VLM might be failing or config disabled?")
                  # This should probably fail if budget/config allows
                  # For now, if we have substantial tables, we expect VLM
                  if os.getenv("TABLE_LLM_ASSIST", "0") == "1": # Or check logic
                       pass # Logic is always enabled unless skip_descriptions=True
                  
                  # Let's enforce it if we found images
                  ralph.assert_helping(described_count > 0, "VLM Description generated for at least one table")
        
        if described_count > 0:
             sample = next(t for t in tables if t.get("ai_description"))
             logger.info(f"Ralph: Sample description: {sample['ai_description'][:50]}...")
        
        print("✅ Ralph is happy! Stage 05b is helping.")
        sys.exit(0)
        
    except ralph.RalphError as e:
        logger.error(f"Ralph is sad: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Verification crashed: {e}")
        sys.exit(1)
