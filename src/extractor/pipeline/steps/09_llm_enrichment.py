#!/usr/bin/env python3
"""
Stage 09: LLM Enrichment for Tables and Figures

Purpose:
- Generate descriptive titles for tables and figures using LLM
- Add descriptions/summaries for each asset
- Store enriched data back in DuckDB

Uses scillm.parallel_acompletions_iter for efficient batch processing.
"""

import sys
import os
import json
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
import duckdb

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(usecwd=True), override=False)

from loguru import logger

# Default model and API settings
DEFAULT_MODEL = os.getenv("SCILLM_MODEL", "deepseek-ai/DeepSeek-V3")
DEFAULT_API_BASE = os.getenv("SCILLM_API_BASE", "https://llm.chutes.ai/v1")
DEFAULT_CONCURRENCY = int(os.getenv("SCILLM_CONCURRENCY", "4"))

DEFAULT_SYSTEM_PROMPT = os.getenv(
    "SCILLM_SYSTEM_PROMPT",
    "You are a technical document analyzer. You MUST provide technical metadata in valid JSON "
    "with exactly 'title' and 'description' keys. Infer the subject matter from the provided context. "
    "If a specific title/caption is not found in the text, infer a descriptive one and prepend it with 'INFERRED: '."
)


async def enrich_assets(
    con: duckdb.DuckDBPyConnection,
    model: str = DEFAULT_MODEL,
    api_base: str = DEFAULT_API_BASE,
    concurrency: int = DEFAULT_CONCURRENCY,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
) -> Dict[str, int]:
    """Enrich tables and figures with LLM-generated metadata."""
    from scillm import parallel_acompletions_iter
    import json_repair
    
    api_key = os.getenv("CHUTES_API_KEY")
    os.environ["SCILLM_JSON_STRICT"] = "1"  # Opt-in to strict JSON via env
    
    # 2. Fetch assets with context
    tables = con.execute("""
        WITH asset_pos AS (
            SELECT section_id, asset_id, sort_order FROM merged_content WHERE type = 'table'
        )
        SELECT 
            t.id, t.csv_data, s.title as section_title,
            (SELECT content FROM merged_content m2 
             WHERE m2.section_id = ap.section_id AND m2.sort_order < ap.sort_order AND m2.type = 'text'
             ORDER BY m2.sort_order DESC LIMIT 1) as context_before,
            (SELECT content FROM merged_content m3 
             WHERE m3.section_id = ap.section_id AND m3.sort_order > ap.sort_order AND m3.type = 'text'
             ORDER BY m3.sort_order ASC LIMIT 1) as context_after
        FROM tables t
        JOIN asset_pos ap ON t.id = ap.asset_id
        LEFT JOIN sections s ON t.section_id = s.id
    """).fetchall()
    
    figures = con.execute("""
        WITH asset_pos AS (
            SELECT section_id, asset_id, sort_order FROM merged_content WHERE type = 'figure'
        )
        SELECT 
            f.id, f.page, s.title as section_title,
            (SELECT content FROM merged_content m2 
             WHERE m2.section_id = ap.section_id AND m2.sort_order < ap.sort_order AND m2.type = 'text'
             ORDER BY m2.sort_order DESC LIMIT 1) as context_before,
            (SELECT content FROM merged_content m3 
             WHERE m3.section_id = ap.section_id AND m3.sort_order > ap.sort_order AND m3.type = 'text'
             ORDER BY m3.sort_order ASC LIMIT 1) as context_after
        FROM figures f
        JOIN asset_pos ap ON f.id = ap.asset_id
        LEFT JOIN sections s ON f.section_id = s.id
    """).fetchall()
    
    if not tables and not figures:
        logger.info("No assets to enrich")
        return {"tables": 0, "figures": 0}

    # 3. Build Batch Requests
    requests = []
    asset_map = {}  # index -> (type, id)
    
    for idx, (t_id, csv_data, section_title, before, after) in enumerate(tables):
        user_prompt = f"""Analyze this table.
Section: {section_title}
Context Before: {before or "(none)"}
Table CSV (first 2000 chars):
{csv_data[:2000]}
Context After: {after or "(none)"}"""
        
        requests.append({
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            # Note: response_format is handled inside acompletion in the iterator
            "response_format": {"type": "json_object"},
            "temperature": 0.1
        })
        asset_map[len(requests) - 1] = ("table", t_id)

    for idx, (f_id, page, section_title, before, after) in enumerate(figures):
        user_prompt = f"""Suggest metadata for this figure.
Section: {section_title} | Page: {page + 1}
Context Before: {before or "(none)"}
[FIGURE]
Context After: {after or "(none)"}"""

        requests.append({
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1
        })
        asset_map[len(requests) - 1] = ("figure", f_id)

    # 4. Execute Batch with Progress (parallel_acompletions_iter)
    logger.info(f"Enriching {len(requests)} assets via parallel_acompletions_iter...")
    
    # Ensure columns exist before processing
    for tbl in ["tables", "figures"]:
        try:
            con.execute(f"ALTER TABLE {tbl} ADD COLUMN llm_title VARCHAR")
            con.execute(f"ALTER TABLE {tbl} ADD COLUMN llm_description VARCHAR")
        except Exception: pass

    table_count = 0
    figure_count = 0
    total = len(requests)
    completed = 0

    async for r in parallel_acompletions_iter(
        requests,
        api_base=api_base,
        api_key=api_key,
        concurrency=concurrency,
        tenacious=True,
        timeout=60
    ):
        completed += 1
        idx = r["index"]
        asset_type, asset_id = asset_map[idx]
        
        if not r["ok"] or r.get("error"):
            logger.warning(f"[{completed}/{total}] Error enriching {asset_type} {asset_id}: {r.get('error') or r.get('status')}")
            continue
        
        # In parallel_acompletions_iter, response is the direct object
        # We need to extract the content. Given strict_json=True (env),
        # scillm might already provide a parsed dict or we parse response.content
        raw_msg = r["response"]["choices"][0]["message"]["content"]
        try:
            data = json_repair.loads(raw_msg)
        except Exception as e:
            logger.warning(f"Failed to parse JSON for {asset_id}: {e}")
            data = {"title": raw_msg[:80], "description": raw_msg}

        if not isinstance(data, dict):
            data = {"title": str(data)[:80], "description": str(data)}
            
        title = data.get("title", "")[:80]
        desc = data.get("description", "")[:500]
        
        table_name = "tables" if asset_type == "table" else "figures"
        con.execute(
            f"UPDATE {table_name} SET llm_title = ?, llm_description = ? WHERE id = ?",
            [title, desc, asset_id]
        )
        if asset_type == "table": table_count += 1
        else: figure_count += 1
        
        logger.info(f"[{completed}/{total}] Enriched {asset_type} {asset_id}: {title[:40]}")

    logger.info(f"Enrichment complete. Tables: {table_count}, Figures: {figure_count}")
    return {"tables": table_count, "figures": figure_count}


def run_enrich_assets(
    pipeline_dir: Path,
    model: str = DEFAULT_MODEL,
    api_base: str = DEFAULT_API_BASE,
    concurrency: int = DEFAULT_CONCURRENCY,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
) -> Dict[str, int]:
    """Main entry point for Stage 09."""
    logger.info("Starting Stage 09: LLM Enrichment")
    
    db_path = pipeline_dir / "pipeline.duckdb"
    if not db_path.exists():
        logger.error(f"Database not found: {db_path}")
        return {"tables": 0, "figures": 0}
    
    con = duckdb.connect(str(db_path))
    
    # 1. Paved Path: Preflight (Discovery)
    from scillm.paved import list_models_openai_like
    api_key = os.getenv("CHUTES_API_KEY")
    logger.info(f"Checking model availability for {model}...")
    models = list_models_openai_like(api_base=api_base, api_key=api_key)
    
    if not models or model not in models:
        logger.error(f"Model {model} not found in listed models.")
        con.close()
        return {"tables": 0, "figures": 0}

    try:
        result = asyncio.run(enrich_assets(con, model, api_base, concurrency, system_prompt))
        logger.info("Stage 09 Completed Successfully")
        return result
    finally:
        con.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Stage 09: LLM Enrichment")
    parser.add_argument("--pipeline-dir", type=str, required=True)
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--api-base", type=str, default=DEFAULT_API_BASE)
    parser.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    parser.add_argument("--system-prompt", type=str, default=DEFAULT_SYSTEM_PROMPT)
    
    args = parser.parse_args()
    
    run_enrich_assets(
        Path(args.pipeline_dir),
        args.model,
        args.api_base,
        args.concurrency,
        args.system_prompt,
    )
