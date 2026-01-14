#!/usr/bin/env python3
"""
S5b_scillm_chutes.py - Sanity check for scillm parallel_acompletions_iter with Chutes.

Purpose:
- Verify that scillm's batch LLM processing works with Chutes API.
- This is the core functionality used by S03, S05b, S06b, S08, S09.

Dependencies:
- scillm.batch.parallel_acompletions_iter
- CHUTES_API_KEY or CHUTES_API_TOKEN env var
- Network access to Chutes API

Success Criteria:
- At least one completion returned
- Response contains valid content
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

# Resolve project root
ROOT = Path(__file__).resolve().parents[3]


def _get_api_key() -> str:
    """Get Chutes API key from environment."""
    key = os.getenv("CHUTES_API_KEY") or os.getenv("CHUTES_API_TOKEN")
    if not key:
        raise RuntimeError("CHUTES_API_KEY or CHUTES_API_TOKEN not set")
    return key


async def _run() -> int:
    # Load dotenv if available
    try:
        from dotenv import find_dotenv, load_dotenv
        load_dotenv(find_dotenv(usecwd=True), override=False)
    except ImportError:
        pass
    
    # Import scillm
    try:
        from scillm.batch import parallel_acompletions_iter
    except ImportError as e:
        print(f"SKIP: scillm not installed ({e})")
        return 0  # Skip, not fail
    
    api_key = _get_api_key()
    model = os.getenv("CHUTES_TEXT_MODEL", "moonshotai/Kimi-K2-Instruct-0905")
    api_base = os.getenv("SCILLM_API_BASE", "https://llm.chutes.ai/v1")
    
    print(f"Testing scillm parallel_acompletions_iter...")
    print(f"  Model: {model}")
    print(f"  API Base: {api_base}")
    
    # Minimal payload
    payloads: List[Dict[str, Any]] = [
        {
            "model": model,
            "messages": [
                {"role": "user", "content": "Reply with exactly: SANITY_OK"}
            ],
            "temperature": 0.0,
            "max_tokens": 20,
            "id": "sanity-check",
        }
    ]
    
    results: List[Dict[str, Any]] = []
    try:
        async for result in parallel_acompletions_iter(
            payloads,
            api_base=api_base,
            api_key=api_key,
            concurrency=1,
            timeout=30,
        ):
            results.append(result)
    except Exception as e:
        print(f"FAIL: parallel_acompletions_iter raised: {e}")
        return 1
    
    if not results:
        print("FAIL: No results returned")
        return 1
    
    first = results[0]
    
    # Check for error
    if first.get("ok") is False:
        print(f"FAIL: LLM error: {first.get('error')}")
        return 1
    
    # Extract content
    content = first.get("content") or ""
    if not content:
        # Try parsed
        parsed = first.get("parsed")
        if parsed:
            content = str(parsed)
    
    if not content:
        print(f"FAIL: No content in response: {first}")
        return 1
    
    print(f"OK: Got response: {content[:50]}...")
    return 0


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    sys.exit(main())
