"""LLM-assisted header detection for Stage 05.

Contains:
- Table hash and header helpers
- LLM assist header attachment (batch async via scillm)
"""

import asyncio
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List

from loguru import logger

from extractor.pipeline.utils.tables.metrics import sanitize_cell


def _stable_table_hash(t: Dict[str, Any]) -> str:
    """Hash based on content to be stable across runs."""
    df_recs = t.get("pandas_df", [])
    s = json.dumps(df_recs, sort_keys=True)
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def _headers_from_table(t: Dict[str, Any]) -> List[str]:
    """Try to get headers from pandas metric or infer row 0."""
    df_recs = t.get("pandas_df", [])
    if not df_recs:
        return []
    return list(df_recs[0].keys())


def _should_assist(t: Dict[str, Any]) -> bool:
    """Assist if simple headers like 0, 1, 2 or empty strings."""
    hdrs = _headers_from_table(t)
    if not hdrs:
        return False
    # Check for integer-like headers (Pandas defaults)
    if all(str(h).isdigit() for h in hdrs):
        return True
    # Check for empty headers
    if any(not str(h).strip() for h in hdrs):
        return True
    return False


def _attach_llm_assist_headers(result: Dict[str, Any], stage_dir: Path) -> None:
    """Attach LLM assist headers from sidecar to result."""
    logger.info("Starting TABLE_LLM_ASSIST check...")
    sidecar = stage_dir / "05_tables_llm_assist.json"
    side_data = json.loads(sidecar.read_text()) if sidecar.exists() else {}

    model = (
        os.getenv("TABLE_LLM_ASSIST_MODEL")
        or os.getenv("CHUTES_TEXT_MODEL")
        or "deepseek-ai/DeepSeek-V3"
    ).strip()
    if not model:
        return

    tables = result.get("tables") or []
    # Headers are stored in pandas_metrics.columns, not in a top-level 'headers' field
    candidates = [t for t in tables if any(str(h).isdigit() for h in t.get("pandas_metrics", {}).get("columns", []))]

    if not candidates:
        logger.info(f"TABLE_LLM_ASSIST: No generic headers found in {len(tables)} tables.")
        return

    logger.info(
        f"TABLE_LLM_ASSIST: Found {len(candidates)} tables with generic headers. Proceeding."
    )
    requests = []
    table_map = {}

    tokens_used = 0
    tokens_budget = int(os.getenv("STAGE05_TOKENS_BUDGET", "120000"))
    budget_enforce = os.getenv("STAGE05_BUDGET_ENFORCE", "true").lower() in (
        "1",
        "true",
        "yes",
        "y",
    )

    system_prompt = (
        "You are a strict normalizer for table column headers.\n"
        "Rules: Do not invent, add, or reorder columns.\n"
        'Return JSON: {"headers": [..]} with the same length as input.\n'
    )

    for idx, t in enumerate(tables):
        if budget_enforce and tokens_used >= tokens_budget:
            logger.warning("TABLE_LLM_ASSIST: Tokens budget exceeded")
            continue

        if not _should_assist(t):
            logger.debug(
                f"TABLE_LLM_ASSIST: Skipping Table {t.get('table_index')} - does not satisfy assist criteria"
            )
            continue

        headers_in = _headers_from_table(t)
        if not headers_in:
            logger.warning(
                f"TABLE_LLM_ASSIST: Table {t.get('table_index')} has no headers to assist"
            )
            continue

        table_hash = _stable_table_hash(t)
        cache_key = f"assist:{table_hash}:{model}"
        cached = side_data.get(cache_key)

        if (
            cached
            and isinstance(cached.get("headers"), list)
            and len(cached["headers"]) == len(headers_in)
        ):
            logger.info(f"TABLE_LLM_ASSIST: Using cached headers for Table {t.get('table_index')}")
            t["llm_assist"] = {"model": model, "patch": cached}
            t["header_inferred"] = [sanitize_cell(h) for h in cached["headers"]]
            continue

        logger.info(
            f"TABLE_LLM_ASSIST: Queuing assist request for Table {t.get('table_index')} using model {model}"
        )
        user_content = json.dumps({"headers_input": headers_in}, ensure_ascii=False)
        requests.append(
            {
                "model": model,  # Use the model variable
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0,
                "index": idx,
                "metadata": {"headers_in": headers_in, "table_hash": table_hash},
            }
        )
        table_map[idx] = t

    if not requests:
        return

    from scillm.batch import parallel_acompletions_iter

    async def process_batch():
        """Process a batch of requests using asynchronous completions."""
        nonlocal tokens_used
        api_base = os.getenv("SCILLM_API_BASE", "http://localhost:4010")
        api_key = os.getenv("SCILLM_PROXY_KEY", "sk-dev-proxy-123")

        async for r in parallel_acompletions_iter(
            requests,
            api_base=api_base,
            api_key=api_key,
            custom_llm_provider="openai_like",
            concurrency=5,
            timeout=20,
            wall_time_s=120,
            tenacious=True,
            response_format={"type": "json_object"},
        ):
            idx = r.get("index")
            t = table_map.get(idx)
            if not t:
                continue

            if not r["ok"]:
                continue
            tokens_used += r.get("usage", {}).get("total_tokens") or 0

            try:
                data = r.get("parsed") or r.get("content") or {}
                if isinstance(data, str) and data:
                    import json_repair

                    data = json_repair.loads(data)

                new_headers = data.get("headers")
                if isinstance(new_headers, list) and len(new_headers) == len(
                    t.get("header_inferred", []) or requests[idx]["metadata"]["headers_in"]
                ):
                    new_headers = [" ".join(str(h).split()) for h in new_headers]
                    t["llm_assist"] = {"model": model, "patch": {"headers": new_headers}}
                    t["header_inferred"] = [sanitize_cell(h) for h in new_headers]
                    side_data[f"assist:{requests[idx]['metadata']['table_hash']}:{model}"] = {
                        "headers": new_headers
                    }
            except Exception as e:
                logger.debug(f"Failed to process LLM assist result at index {idx}: {e}")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(process_batch())
    finally:
        loop.close()

    try:
        sidecar.write_text(json.dumps(side_data, ensure_ascii=False, indent=2))
    except Exception as e:
        logger.warning(f"Failed to write LLM assist sidecar file: {e}")
