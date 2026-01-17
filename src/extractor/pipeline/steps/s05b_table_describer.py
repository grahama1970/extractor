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
from typing import Any, Dict, List, Optional

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
        custom_llm_provider="openai_like",  # Required per SCILLM_PAVED_PATH_CONTRACT
        concurrency=CONCURRENCY,
        timeout=VLM_TIMEOUT_SEC,
        wall_time_s=300,  # 5 min max for whole batch
        tenacious=False,  # Fail fast
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
    skip_descriptions: bool = False,
    preset_config: Optional[Dict[str, Any]] = None,
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
    data["enriched_timestamp"] = time.time()
    
    write_json_strict(out_file, data)
    
    logger.info(f"Stage 05b complete. Enriched {len(enriched_tables)} tables in {int(time.monotonic()-t0)}s.")
    return out_file

if __name__ == "__main__":
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description="Stage 05b: Table Describer")
    parser.add_argument("--pipeline-dir", type=Path, required=True, help="Path to pipeline results root")
    args = parser.parse_args()
    
    pipeline_dir = args.pipeline_dir
    stage_dir = pipeline_dir / "05_table_extractor"
    
    try:
        logger.info("Running Stage 05b...")
        if not stage_dir.exists():
            logger.error("Missing input dependencies (Stage 05)")
            sys.exit(1)
        
        run(stage_05_dir=stage_dir, output_dir=pipeline_dir)
        
    except Exception as e:
        logger.error(f"Execution failed: {e}")
        sys.exit(1)
