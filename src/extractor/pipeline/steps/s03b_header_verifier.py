#!/usr/bin/env python3
"""
Stage 03b — Header Verifier (Batch LLM).

Purpose:
- Consumes `03_markup.json` (candidates from Stage 03).
- Uses `scillm.parallel_acompletions_iter` to verify suspicious headers in batch.
- Outputs `03_verified_blocks.json` (final state).
"""

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List

from dotenv import find_dotenv, load_dotenv
from loguru import logger
from scillm import parallel_acompletions_iter

from extractor.pipeline.utils.reliability import log_stage_error, write_json_strict
from extractor.pipeline.utils.step_sanity import run_step_sanity
from extractor.pipeline.steps.scillm_preflight_validator import require_scillm_preflight

load_dotenv(find_dotenv())

STEP_NAME = "03b_header_verifier"

# Tunables
CONCURRENCY = int(os.getenv("STAGE03_CONCURRENCY", "4"))
VLM_TIMEOUT_SEC = float(os.getenv("STAGE03_VLM_TIMEOUT_SEC", "30"))
# Use CHUTES_VLM_MODEL for vision capabilities
MODEL = os.getenv("CHUTES_VLM_MODEL", "chutes/vlm") 

def sanity() -> int:
    return run_step_sanity(STEP_NAME)

def run(input_dir: Path, output_dir: Path) -> Path:
    """
    Run the header verification stage.
    Args:
        input_dir: Path containing 03_markup.json (usually 03 output dir)
        output_dir: Pipeline output root
    """
    require_scillm_preflight()

    # Input resolution
    input_json = input_dir / "json_output" / "03_markup.json"
    if not input_json.exists():
        # Fallback for legacy name if generator wasn't updated yet?
        # Or if we chained from previous run.
        logger.warning(f"Input {input_json} not found. Checking alternate...")
        input_json = input_dir / "json_output" / "03_verified_blocks.json" 
        
    if not input_json.exists():
        logger.error(f"No input found in {input_dir}")
        return input_dir # Fail safe

    data = json.loads(input_json.read_text())
    
    # Identify candidates
    # In the new 03 generator, "candidates" might be explicit, or we scan for "is_suspicious" flag?
    # Let's assume the generator marks them.
    # However, for flat list:
    blocks = data.get("blocks", [])
    
    candidates = []
    # Identify blocks needing verification (suspicious_header=True OR marked for review)
    # We rely on Stage 03 to have set "requires_verification": True or similar.
    # Or determining from 'suspicious_header' flag.
    
    candidate_indices = []
    
    for i, b in enumerate(blocks):
        if b.get("suspicious_header") or b.get("requires_verification"):
             # Must have context_image_path for VLM
             if b.get("context_image_path"):
                 candidates.append(b)
                 candidate_indices.append(i)
    
    if not candidates:
        logger.info("No suspicious headers to verify.")
        # Just write pass-through
        out_dir = output_dir / STEP_NAME
        out_dir.mkdir(exist_ok=True)
        (out_dir / "json_output").mkdir(exist_ok=True)
        out_file = out_dir / "json_output" / "03_verified_blocks.json"
        write_json_strict(out_file, data)
        return out_file

    logger.info(f"Verifying {len(candidates)} suspicious headers with {MODEL}...")

    # Prepare requests
    requests = []
    system_prompt = (
        "You are an expert at analyzing PDF section headers. "
        "Reply with strict JSON matching this schema:\n"
        "{\n"
        "  \"is_header\": boolean,\n"
        "  \"confidence\": float, // 0.0 to 1.0\n"
        "  \"reason\": string,\n"
        "  \"alternate_type\": string // e.g. \"list_item\", \"caption\", \"table_row\", \"text\"\n"
        "}"
    )
    
    for i, b in enumerate(candidates):
        # Image must be absolute path? 
        # Stage 03 writes absolute path to 'context_image_path'.
        img_path = Path(b["context_image_path"])
        if not img_path.exists():
            logger.warning(f"Missing context image: {img_path}")
            continue
            
        try:
            import base64
            b64 = base64.b64encode(img_path.read_bytes()).decode("utf-8")
        except Exception as e:
            logger.error(f"Failed to read image {img_path}: {e}")
            continue

        prompt_text = (
            "Analyze the image and text.\n"
            f"Text: {b.get('text', '')}\n"
            "Text: {b.get('text', '')}\n"
            "Is this a true section header? Or is it a list item, table row, or caption?\n"
            "Return strict JSON."
        )
        # Add context from prompt builder? 
        # Ideally Stage 03 generator prepared the "prompt_context" string in the block.
        if b.get("prompt_context"):
            prompt_text = b["prompt_context"]

        req = {
            "model": MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user", 
                    "content": [
                        {"type": "text", "text": prompt_text},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
                    ]
                }
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.0,
            "metadata": {"task_kind": "header_verify", "stage": "03b"},
            "index": candidate_indices[i] # Track back to original block index
        }
        requests.append(req)

    # Batch Process
    api_key = os.getenv("CHUTES_API_KEY")
    api_base = os.getenv("CHUTES_API_BASE", "https://llm.chutes.ai/v1")
    
    async def _process():
        async for r in parallel_acompletions_iter(
            requests,
            api_base=api_base,
            api_key=api_key,
            concurrency=CONCURRENCY,
            timeout=VLM_TIMEOUT_SEC,
            response_format={"type": "json_object"}
        ):
            idx = r.get("index")
            if idx is None: continue
            
            block = blocks[idx]
            
            if not r.get("ok"):
                logger.warning(f"Failed verify block {idx}: {r.get('error')}")
                # Default to keeping it as header? Or demoting?
                # Fail open (keep header) is safer for containment, fail closed (demote) safer for reading flow.
                # Let's keep strict: if error, keep original state but note it.
                continue

            content = r.get("parsed") or {}
            is_header = content.get("is_header")
            
            # Apply decision
            block["suspicious_header"] = False # Decision made
            block["llm_verification"] = {
                "verified_at": time.time(),
                "model": MODEL,
                "confidence": content.get("confidence", 1.0),
                "reason": content.get("reason"),
                "result": content
            }
            
            if is_header is False:
                # DEMOTE
                block["block_type"] = "Text"
                # If they gave an alternate type like "Caption", maybe use it?
                # For now, just demote to Text to be safe.
                if content.get("alternate_type") == "caption":
                    block["block_type"] = "Caption"
                
                block["is_suspicious"] = True
                block["suspicious_reasons"] = ["llm_verification_reject"]
            else:
                 # CONFIRM
                 block["is_suspicious"] = False
                 block["suspicious_confidence"] = 0.0

    asyncio.run(_process())

    # Write Output
    out_dir = output_dir / STEP_NAME
    out_dir.mkdir(exist_ok=True)
    (out_dir / "json_output").mkdir(exist_ok=True)
    
    out_file = out_dir / "json_output" / "03_verified_blocks.json"
    write_json_strict(out_file, data)
    
    logger.info(f"Verified {len(requests)} headers.")
    return out_file

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("data/results/pipeline"))
    args = parser.parse_args()
    
    run(args.input_dir, args.output_dir)
