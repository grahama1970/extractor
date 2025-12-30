#!/usr/bin/env python3
"""
Stage 09: LLM Enrichment for Tables and Figures

Purpose:
- Generate descriptive titles for tables and figures using LLM
- Add descriptions/summaries for each asset
- Store enriched data back in DuckDB

Uses scillm.parallel_acompletions_iter for efficient batch processing.
"""

import os
import asyncio
from pathlib import Path
from typing import Dict, Any

# Set SCILLM_JSON_STRICT before any SciLLM imports to ensure it takes effect
os.environ["SCILLM_JSON_STRICT"] = "1"

from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(usecwd=True), override=False)

from loguru import logger
from extractor.pipeline.utils.db.connection import get_connection

# Default model and API settings
DEFAULT_MODEL = os.getenv("CHUTES_TEXT_MODEL", "moonshotai/Kimi-K2-Instruct-0905")
DEFAULT_API_BASE = os.getenv("SCILLM_API_BASE", "https://llm.chutes.ai/v1")
DEFAULT_CONCURRENCY = int(os.getenv("SCILLM_CONCURRENCY", "4"))

DEFAULT_SYSTEM_PROMPT = os.getenv(
    "SCILLM_SYSTEM_PROMPT",
    "You are a technical document analyzer. You MUST provide technical metadata in valid JSON "
    "with exactly 'title' and 'description' keys. Infer the subject matter from the provided context. "
    "If a specific title/caption is not found in the text, infer a descriptive one and prepend it with 'INFERRED: '."
)

def extract_message_content(resp_item: Dict[str, Any]) -> str:
    """Decouple from provider-specific response shapes (OpenAI vs others)."""
    resp = resp_item.get("response")
    if not resp:
        return ""
    
    # Check for direct content (some SciLLM versions/providers)
    if "content" in resp:
        return resp["content"]
        
    # Check for OpenAI-like choice structure
    try:
        choices = resp.get("choices", [])
        if choices:
            msg = choices[0].get("message", {})
            return msg.get("content", "")
    except Exception as e:
        logger.debug(f"Failed to extract content from unknown shape: {e}")
        logger.trace(f"Full payload: {resp}")
    
    return ""

async def enrich_assets(
    con: Any, # duckdb.DuckDBPyConnection
    model: str = DEFAULT_MODEL,
    api_base: str = DEFAULT_API_BASE,
    concurrency: int = DEFAULT_CONCURRENCY,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
) -> Dict[str, int]:
    """Enrich tables and figures with LLM-generated metadata."""
    from scillm import parallel_acompletions_iter
    
    api_key = os.getenv("CHUTES_API_KEY")
    
    # 2. Fetch assets with context using LATERAL JOINs (Robust Coverage)
    # We drive from primary tables/figures to ensure 100% coverage even if assembler missed them in merged_content.
    # We look up "text" or "section" context from merged_content nearby in sort_order.
    
    asset_query = """
    WITH combined_assets AS (
        SELECT 'table' as asset_type, id as asset_id, section_id, sort_order, csv_data as content, NULL as page FROM tables
        UNION ALL
        SELECT 'figure' as asset_type, id as asset_id, section_id, sort_order, NULL as content, page FROM figures
    )
    SELECT 
        a.asset_type,
        a.asset_id,
        s.title as section_title,
        CASE WHEN a.asset_type = 'table' THEN a.content ELSE NULL END as csv_data,
        CASE WHEN a.asset_type = 'figure' THEN a.page ELSE NULL END as page,
        
        -- Context Before (Nearest 2 text/section blocks)
        COALESCE(cb.ctx, '(none)') as context_before,
        
        -- Context After (Nearest 2 text/section blocks)
        COALESCE(ca.ctx, '(none)') as context_after
        
    FROM combined_assets a
    LEFT JOIN sections s ON a.section_id = s.id
    
    -- LATERAL JOIN for Context Before
    LEFT JOIN LATERAL (
        SELECT string_agg(content, '\n\n') as ctx
        FROM (
            SELECT content 
            FROM merged_content 
            WHERE section_id = a.section_id 
              AND sort_order < a.sort_order 
              AND type IN ('text', 'section')
            ORDER BY sort_order DESC 
            LIMIT 2
        ) sub_b
    ) cb ON true
    
    -- LATERAL JOIN for Context After
    LEFT JOIN LATERAL (
        SELECT string_agg(content, '\n\n') as ctx
        FROM (
            SELECT content 
            FROM merged_content 
            WHERE section_id = a.section_id 
              AND sort_order > a.sort_order 
              AND type IN ('text', 'section')
            ORDER BY sort_order ASC 
            LIMIT 2
        ) sub_a
    ) ca ON true
    """
    
    assets = con.execute(asset_query).fetchall()
    
    # Asset count sanity check
    db_tables = con.execute("SELECT COUNT(*) FROM tables").fetchone()[0]
    db_figures = con.execute("SELECT COUNT(*) FROM figures").fetchone()[0]
    joined_tables = sum(1 for a in assets if a[0] == 'table')
    joined_figures = sum(1 for a in assets if a[0] == 'figure')
    
    if joined_tables != db_tables or joined_figures != db_figures:
        logger.warning(
            f"Asset count mismatch even with primary query! DB: {db_tables}T/{db_figures}F, Joined: {joined_tables}T/{joined_figures}F."
        )

    if not assets:
        logger.info("No assets to enrich")
        return {"tables": 0, "figures": 0}

    # 3. Build Batch Requests
    requests = []
    asset_map = {}  # index -> (type, id, context_strings)
    
    for idx, (a_type, a_id, section_title, csv_data, page, before, after) in enumerate(assets):
        if a_type == 'table':
            user_prompt = f"""Analyze this table.
Section: {section_title}
Context Before: {before}
Table CSV (first 2000 chars):
{csv_data[:2000] if csv_data else ""}
Context After: {after}"""
        else:
            user_prompt = f"""Suggest metadata for this figure.
Section: {section_title} | Page: {(page + 1) if page is not None else "Unknown"}
Context Before: {before}
[FIGURE]
Context After: {after}"""
        
        requests.append({
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1
        })
        asset_map[len(requests) - 1] = (a_type, a_id, before + "\n" + after)

    # 4. Execute Batch with Progress (parallel_acompletions_iter)
    logger.info(f"Enriching {len(requests)} assets via parallel_acompletions_iter...")
    
    # Columns llm_title and llm_description are now defined in schema.py
    # No runtime ALTER TABLE needed - schema handles this at DB creation time

    table_count = 0
    figure_count = 0
    total = len(requests)
    completed = 0

    # Define schema for enforcement
    asset_schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string", "minLength": 5},
            "description": {"type": "string", "minLength": 10}
        },
        "required": ["title", "description"]
    }

    async for r in parallel_acompletions_iter(
        requests,
        api_base=api_base,
        api_key=api_key,
        concurrency=concurrency,
        tenacious=True,
        timeout=60,
        response_format={"type": "json_object"},
        repair_invalid_json=True,
        retry_invalid_json=2,
        schema=asset_schema
    ):
        completed += 1
        idx = r["index"]
        asset_type, asset_id, combined_ctx = asset_map[idx]
        
        if not r["ok"] or r.get("error") == "invalid_json":
            # Improved error logging with payload visibility
            err_msg = r.get("error") or r.get("status")
            logger.warning(f"[{completed}/{total}] Error enriching {asset_type} {asset_id}: {err_msg}")
            if "response" in r:
                logger.debug(f"Truncated payload for {asset_id}: {str(r['response'])[:500]}")
            continue
        
        # v1.78.0 features: 'parsed' contains the dict if schema/JSON was successful
        # 'content' contains the raw string if repair failed but it's still "ok"
        # In current scillm v1.78.1, 'content' might already be the parsed dict.
        data = r.get("parsed") or {}
        
        if not data and r.get("content"):
            content = r.get("content")
            if isinstance(content, dict):
                data = content
            else:
                import json_repair
                try:
                    data = json_repair.loads(content)
                except Exception as e:
                    logger.debug(f"Fallback parse failed for {asset_id}: {e}")
                    data = {}

        if r.get("repaired"):
            logger.debug(f"SciLLM auto-repaired JSON for {asset_id}")

        title = str(data.get("title", "")).strip()
        desc = str(data.get("description", "")).strip()
        
        # Robustness: Fallback if title/desc empty
        if not title:
            title = desc[:50] if desc else f"Untitled {asset_type}"
        if not desc:
            desc = "(No description provided by LLM)"

        # --- Deterministic INFERRED Enforcement (Business Rule) ---
        # 1. Clean previous prefix if LLM provided it
        clean_title = title.replace("INFERRED:", "").strip()
        
        # 2. Heuristic: Is a caption present in context?
        # Captions usually contain 'Table X' or 'Figure Y' or 'Fig. Z'
        found_verbatim = False
        import re
        patterns = [r"Table\s+\d+", r"Figure\s+\d+", r"Fig\.\s+\d+"]
        for p in patterns:
            # We check if the clean title (verbatim extraction) exists in the context
            # or if the context contains a typical caption pattern that matches the title
            if re.search(p, combined_ctx, re.IGNORECASE) and clean_title.lower() in combined_ctx.lower():
                found_verbatim = True
                break
        
        # 3. Enforce prefix
        if not found_verbatim and not title.startswith("INFERRED:"):
            title = f"INFERRED: {clean_title}"
        elif found_verbatim and title.startswith("INFERRED:"):
            # If it found it verbatim but still prefixed it, remove prefix to respect verbatim rule
            title = clean_title

        # Truncate for storage
        title = title[:120]
        desc = desc[:1000]
        
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
    
    # Standardized connection via utility
    con = get_connection(db_path)
    
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
    # Default to data/results/pipeline_test_final if not specified
    parser.add_argument("--pipeline-dir", type=str, default="data/results/pipeline_test_final")
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
