#!/usr/bin/env python3
"""
Pipeline Stage 09: Section Summarizer (Modernized)

Consolidates logic and adheres to the SCILLM Paved Path.
Uses SciLLM v1.78.1 parallel_acompletions_iter for standardized execution.
"""

import os
import json
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

# Move SCILLM_JSON_STRICT=1 to top to ensure all imports honor it
os.environ["SCILLM_JSON_STRICT"] = "1"

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(usecwd=True), override=False)

from loguru import logger
from extractor.pipeline.utils.db.connection import get_connection

# Default model and API settings
DEFAULT_MODEL = os.getenv("CHUTES_TEXT_MODEL", "moonshotai/Kimi-K2-Instruct-0905")
DEFAULT_API_BASE = os.getenv("SCILLM_API_BASE", "https://llm.chutes.ai/v1")
DEFAULT_CONCURRENCY = int(os.getenv("SCILLM_CONCURRENCY", "4"))

def extract_message_content(r: Any) -> Optional[str]:
    """Normalize SciLLM response content extraction."""
    try:
        if isinstance(r, dict):
            # Try to get from 'parsed' first if schema/JSON was used
            if r.get("parsed"):
                # If parsed is a dict, we might want it as JSON string or keep it?
                # For consistency with parallel_acompletions_iter usage elsewhere,
                # we return the content as string if we need to parse it later,
                # but better to return the dict if available.
                return r["parsed"]
            return r.get("content")
        
        # Fallback for raw objects
        choices = getattr(r, "choices", None)
        if choices:
            msg = getattr(choices[0], "message", None)
            if msg:
                return getattr(msg, "content", None)
        return None
    except Exception as e:
        logger.debug(f"extraction_normalization_failed: {e}")
        return None

def fetch_ordered_section_content(con: Any, section_id: str) -> str:
    """
    Fetches all artifacts for a section and joins them in reading order.
    Merges contiguous text blocks.
    """
    # 1. Fetch all assets
    # Use v_clean_blocks to avoid text that is actually part of tables/figures
    blocks = con.execute("SELECT page, y0, text, type FROM v_clean_blocks WHERE section_id = ? ORDER BY page, y0", (section_id,)).fetchall()
    tables = con.execute("SELECT page, y0, llm_title, llm_description FROM tables WHERE section_id = ? ORDER BY page, y0", (section_id,)).fetchall()
    figures = con.execute("SELECT page, y0, llm_title, llm_description FROM figures WHERE section_id = ? ORDER BY page, y0", (section_id,)).fetchall()
    
    # 2. Interleave
    all_items = []
    for b in blocks:
        all_items.append({"page": b[0], "y0": b[1], "type": "text", "content": b[2], "sub_type": b[3]})
    for t in tables:
        title = t[2] or "Untitled Table"
        desc = t[3] or ""
        all_items.append({"page": t[0], "y0": t[1], "type": "table", "content": f"[TABLE: {title}] {desc}".strip()})
    for f in figures:
        title = f[2] or "Untitled Figure"
        desc = f[3] or ""
        all_items.append({"page": f[0], "y0": f[1], "type": "figure", "content": f"[FIGURE: {title}] {desc}".strip()})
        
    all_items.sort(key=lambda x: (x["page"], x["y0"]))
    
    # 3. Merge contiguous text and format
    final_lines = []
    current_text = []
    
    for item in all_items:
        if item["type"] == "text":
            # For headers, we might want to emphasize them
            line = item["content"].strip()
            if not line:
                continue
            if item["sub_type"] == "SectionHeader":
                if current_text:
                    final_lines.append(" ".join(current_text))
                    current_text = []
                final_lines.append(f"### {line}")
            else:
                current_text.append(line)
        else:
            # Table or Figure
            if current_text:
                final_lines.append(" ".join(current_text))
                current_text = []
            final_lines.append(item["content"])
            
    if current_text:
        final_lines.append(" ".join(current_text))
        
    return "\n\n".join(final_lines)

async def run_summarizer(
    con: Any,
    model: str = DEFAULT_MODEL,
    api_base: str = DEFAULT_API_BASE,
    concurrency: int = DEFAULT_CONCURRENCY,
) -> Dict[str, int]:
    """Batch summarize sections with rolling context via parallel_acompletions_iter."""
    from scillm import parallel_acompletions_iter
    
    # 1. Fetch sections
    sections_query = "SELECT id, title FROM sections ORDER BY page_start, id"
    section_rows = con.execute(sections_query).fetchall()
    if not section_rows:
        logger.warning("No sections found for summarization.")
        return {"summaries": 0}

    # Load prompts
    from extractor.pipeline.utils.prompt_loader import load_prompt
    prompts = load_prompt("09_section_summarizer")
    system_prompt = prompts["system"]
    user_prompt_tmpl = prompts["user"]

    # Columns llm_summary, llm_key_concepts, llm_metadata are now defined in schema.py
    # No runtime ALTER TABLE needed - schema handles this at DB creation time

    # Schema for validation
    summary_schema = {
        "type": "object",
        "properties": {
            "summary": {"type": "string", "minLength": 20},
            "key_concepts": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 2
            }
        },
        "required": ["summary", "key_concepts"]
    }

    # We process in batches to maintain semi-rolling context.
    # Within a batch, items use context from the PREVIOUS batch.
    batch_size = concurrency if concurrency > 0 else 4
    all_results = []
    previous_summaries = []
    
    api_key = os.getenv("CHUTES_API_KEY")

    logger.info(f"Summarizing {len(section_rows)} sections in batches of {batch_size}...")

    for i in range(0, len(section_rows), batch_size):
        batch_rows = section_rows[i : i + batch_size]
        
        # Build context from the last 3 successful summaries
        context_str = "\n".join([
            f"- {s['title']}: {s['summary']}"
            for s in previous_summaries[-3:]
        ])
        if not context_str:
            context_str = "(none)"

        payloads = []
        for s_id, title in batch_rows:
            section_text = fetch_ordered_section_content(con, s_id)
            prompt = user_prompt_tmpl.format(
                previous_summaries=context_str,
                section_title=title,
                section_level=0, # Could fetch from DB if needed
                section_text=section_text[:15000]
            )
            payloads.append({
                "model": model,
                "id": s_id,
                "title": title,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.0
            })

        # Run this batch
        async for r in parallel_acompletions_iter(
            payloads,
            api_base=api_base,
            api_key=api_key,
            concurrency=batch_size,
            repair_invalid_json=True,
            retry_invalid_json=2,
            schema=summary_schema,
            timeout=120
        ):
            # SciLLM v1.78.x returns dict with 'request' key
            req = r.get("request", {})
            s_id = req.get("id")
            title = req.get("title")
            
            # Use extract_message_content for consistency
            content_val = extract_message_content(r)
            
            if isinstance(content_val, dict):
                data = content_val
            elif isinstance(content_val, str):
                try:
                    data = json.loads(content_val)
                except:
                    data = {}
            else:
                data = {}

            summary = data.get("summary", "")
            key_concepts = data.get("key_concepts", [])
            
            if summary:
                logger.info(f"Successfully summarized section {s_id}: {title}")
                res = {"id": s_id, "title": title, "summary": summary, "success": True}
                previous_summaries.append(res)
                all_results.append(res)
                
                # Metadata capture
                meta = {
                    "usage": r.get("usage"),
                    "model": r.get("model", model),
                    "latency_ms": r.get("metrics", {}).get("total_time_ms"), 
                    "timings": r.get("timings"), # scillm internal timings if available
                    "generated_at": datetime.utcnow().isoformat()
                }

                # Update DB
                con.execute(
                    "UPDATE sections SET llm_summary = ?, llm_key_concepts = ?, llm_metadata = ? WHERE id = ?",
                    (summary, json.dumps(key_concepts), json.dumps(meta), s_id)
                )
            else:
                err_msg = r.get("error", "Unknown error")
                logger.warning(f"Failed to summarize section {s_id}: {title} | Error: {err_msg}")

    return {"summaries": len([r for r in all_results if r["success"]])}

def run_stage_09_summarizer(
    pipeline_dir: Path,
    model: str = DEFAULT_MODEL,
    api_base: str = DEFAULT_API_BASE,
    concurrency: int = DEFAULT_CONCURRENCY,
):
    """Entry point for the pipeline driver."""
    from scillm.paved import list_models_openai_like
    
    db_path = pipeline_dir / "pipeline.duckdb"
    if not db_path.exists():
        logger.error(f"Database not found at {db_path}")
        return

    # Check model availability first
    api_key = os.getenv("CHUTES_API_KEY")
    try:
        models = list_models_openai_like(api_base=api_base, api_key=api_key)
        if not models or model not in models:
            logger.warning(f"Model {model} not listed at {api_base}, but attempting anyway.")
    except Exception as e:
        logger.warning(f"Could not list models: {e}")

    con = get_connection(db_path)
    try:
        asyncio.run(run_summarizer(con, model, api_base, concurrency))
        logger.info("Stage 09 Section Summarizer complete.")
    finally:
        con.close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Stage 09: Section Summarizer")
    parser.add_argument("--pipeline-dir", type=str, required=True)
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--api-base", type=str, default=DEFAULT_API_BASE)
    parser.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    
    args = parser.parse_args()
    
    run_stage_09_summarizer(
        Path(args.pipeline_dir),
        args.model,
        args.api_base,
        args.concurrency
    )
