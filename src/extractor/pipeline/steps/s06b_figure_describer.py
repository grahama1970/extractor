#!/usr/bin/env python3
"""
Stage 06b — Figure Describer (VLM Batch)

Contract:
- Inputs: Stage 06 figures JSON (deterministic extraction).
- Logic:
  - Reads `06_figures.json`.
  - Builds batch requests for Chutes VLM (Image + Context).
  - Uses `scillm.parallel_acompletions_iter` (simulated batch via concurrency) or custom iterator.
  - Updates figures with `ai_description` and `ai_title`.
- Outputs: Overwrites or creates new `06_figures.json` with encrichment.

Note: Since scillm's `parallel_acompletions_iter` is text-optimized (standard OpenAI messages), 
it works for Multimodal IF the provider supports `image_url` blocks in the `user` message. 
Chutes/VLM supports this standard OpenAI format.
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

STEP_NAME = "06b_figure_describer"

# Tunables
CONCURRENCY = int(os.getenv("STAGE06_CONCURRENCY", "6"))
VLM_TIMEOUT_SEC = float(os.getenv("STAGE06_VLM_TIMEOUT_SEC", "45"))
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


async def process_figures(figures: List[Dict[str, Any]], output_dir: Path) -> List[Dict[str, Any]]:
    """Batch process figures using VLM."""
    
    requests = []
    # Map index to figure object to update later
    fig_map = {}
    
    system_prompt = (
        "You assist PDF figure extraction. Return strict JSON only with keys: "
        "description (2–3 sentences), title (<=10 words, no 'Figure' prefix), "
        "source ('above'|'below'|'context'|'unknown'), number (optional)."
    )

    valid_req_count = 0
    for idx, fig in enumerate(figures):
        # Fix: Step 06 produces "image_path", but code was using "img_path". Support both.
        img_rel = fig.get("image_path") or fig.get("img_path")
        if not img_rel:
            continue
            
        # Resolve image path relative to pipeline root (assuming output_dir is pipeline/results)
        # fig["img_path"] is usually relative to results root.
        # We need absolute path. output_dir passed to run() is usually valid.
        # If output_dir is ".../06_figure_extractor", we need to look there.
        # Actually, fig["img_path"] is like "06_figure_extractor/visual_output/fig_001.png"
        # and output_dir is ".../pipeline".
        
        full_img_path = output_dir / img_rel
        if not full_img_path.exists():
            full_img_path = output_dir.parent / img_rel # fallback hack if nesting varies
            
        if not full_img_path.exists():
            logger.warning(f"Image not found: {full_img_path}")
            continue

        b64 = _encode_image(full_img_path)
        if not b64:
            continue

        text_above = fig.get("context_above", "")
        text_below = fig.get("context_below", "")
        nearby = fig.get("context_nearby", "")
        
        user_parts = [
            {
                "type": "text",
                "text": (
                    f"Text above:\n{text_above[:600]}\n\n"
                    f"Text below:\n{text_below[:600]}\n\n"
                    f"Nearby text:\n{nearby[:800]}"
                ),
            },
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
            "index": idx # Pass index to correlate
        })
        fig_map[idx] = fig
        valid_req_count += 1

    if not requests:
        logger.info("No figures to describe.")
        return figures

    logger.info(f"Describing {len(requests)} figures with {MODEL} (concurrency={CONCURRENCY})...")
    
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
        idx = result.get("index") # scillm usually passes through extra fields or we rely on order? 
        # Wait, scillm parallel_acompletions_iter yields result dicts. 
        # Does "index" passthrough? Usually yes if it's in the request dict. 
        # If not, we have to match by order IF atomic... but parallel implies out-of-order.
        # Actually parallel_acompletions_iter yields {index: int, ...} by design.
        
        if idx is None:
            # Fallback if scillm version doesn't support passthrough, verify source code usage
            # Stage 09 uses r["index"]. It exists.
            continue
            
        fig = fig_map.get(idx)
        if not fig: continue

        if not result.get("ok"):
            logger.warning(f"Failed to describe figure {fig.get('figure_id')}: {result.get('error')}")
            continue

        # Parse JSON
        content = result.get("parsed") or result.get("content") or {}
        if isinstance(content, str) and content:
             # lazy parse
             try:
                 import json_repair
                 content = json_repair.loads(content)
             except:
                 content = {}

        if content:
             fig["ai_description"] = content.get("description")
             fig["ai_title"] = content.get("title")
             fig["ai_source"] = content.get("source")
             fig["ai_number"] = content.get("number")
             # Clean up context fields to save space?
             # fig.pop("context_above", None) 
             # ... maybe keep them for debugging

    return figures


def run(
    stage_06_dir: Path,
    output_dir: Path,
    skip_descriptions: bool = False,
    preset_config: Optional[Dict[str, Any]] = None,
) -> Path:
    
    if skip_descriptions:
        logger.info("Skipping VLM descriptions (requested).")
        return stage_06_dir / "json_output" / "06_figures.json"

    require_scillm_preflight()

    input_json = stage_06_dir / "json_output" / "06_figures.json"
    if not input_json.exists():
        logger.warning(f"Input {input_json} not found. Skipping.")
        return input_json

    data = json.loads(input_json.read_text())
    figures = data.get("figures", [])
    
    if not figures:
        logger.info("No figures found in Step 06 output.")
        return input_json
        
    t0 = time.monotonic()
    
    # Process
    try:
        enriched_figures = asyncio.run(process_figures(figures, output_dir))
    except Exception as e:
        log_stage_error(STEP_NAME, e)
        raise

    # Write output (overwrite 06_figures.json to serve as drop-in replacement or shadow?)
    # Ideally we write to 06b directory to be pure.
    step_dir = output_dir / "06b_figure_describer"
    step_dir.mkdir(exist_ok=True)
    json_out = step_dir / "json_output"
    json_out.mkdir(exist_ok=True)
    
    out_file = json_out / "06b_figures.json"
    
    data["figures"] = enriched_figures
    data["enriched_timestamp"] = time.time()
    
    write_json_strict(out_file, data)
    
    logger.info(f"Stage 06b complete. Enriched {len(enriched_figures)} figures in {int(time.monotonic()-t0)}s.")
    return out_file

if __name__ == "__main__":
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description="Stage 06b: Figure Describer")
    parser.add_argument("--pipeline-dir", type=Path, required=True, help="Path to pipeline results root")
    args = parser.parse_args()
    
    pipeline_dir = args.pipeline_dir
    stage_dir = pipeline_dir / "06_figure_extractor"
    
    try:
        logger.info("Running Stage 06b...")
        if not stage_dir.exists():
            logger.error("Missing input dependencies (Stage 06)")
            sys.exit(1)
        
        run(stage_06_dir=stage_dir, output_dir=pipeline_dir)
        
    except Exception as e:
        logger.error(f"Execution failed: {e}")
        sys.exit(1)
