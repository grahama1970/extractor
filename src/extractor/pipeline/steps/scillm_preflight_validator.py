#!/usr/bin/env python3
"""
SciLLM Preflight Validator - AGENTS.md Compliance

Per paved-path requirements:
- Use scillm Router/helpers; do not re-implement routing.
- Preflight via `scillm.paved.list_models_openai_like` + `scillm.paved.sanity_preflight`.
- Fail fast on non-200 responses (short wall, parallel strict JSON probe).
"""

import os
import sys
import asyncio
import aiohttp
import logging
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

# Ensure the local SciLLM / litellm repo is on sys.path first so that
# `scillm.paved` is importable even when an older PyPI scillm is also
# installed. This keeps the extractor pinned to the paved-path contract.
try:
    _litellm_repo = Path.home() / "workspace" / "experiments" / "litellm"
    if _litellm_repo.exists():
        _litellm_str = str(_litellm_repo)
        if _litellm_str not in sys.path:
            sys.path.insert(0, _litellm_str)
except Exception:
    # Best-effort bootstrap; never block preflight on this convenience hook.
    pass


async def probe_models_endpoint(base_url: str, api_key: str) -> Tuple[bool, str]:
    from scillm.paved import list_models_openai_like  # type: ignore
    try:
        ids = list_models_openai_like(api_base=base_url, api_key=api_key, timeout=10.0) or []
        if not ids:
            return False, "No models returned"
        text_model = os.getenv("CHUTES_TEXT_MODEL")
        vlm_model = os.getenv("CHUTES_VLM_MODEL")
        if text_model and text_model not in ids:
            return False, f"Text model '{text_model}' not in model list"
        if vlm_model and vlm_model not in ids:
            logger.warning("Requested VLM model not in list; continuing")
        logger.info(f"SciLLM preflight: Found {len(ids)} total models")
        return True, "Models endpoint accessible"
    except Exception as e:
        return False, f"Models endpoint probe failed: {e}"

async def probe_chat_completions_endpoint(base_url: str, api_key: str) -> Tuple[bool, str]:
    from scillm.paved import sanity_preflight  # type: ignore
    text_model = os.getenv("CHUTES_TEXT_MODEL") or "deepseek-ai/DeepSeek-R1"
    try:
        # sanity_preflight is synchronous and internally uses asyncio.run;
        # run it in a thread so we do not nest event loops inside our async preflight.
        loop = asyncio.get_running_loop()
        ok, _, details = await loop.run_in_executor(
            None,
            lambda: sanity_preflight(
                api_base=base_url,
                api_key=api_key,
                model=text_model,
                wall_time_s=20,
                timeout=10,
                parallel=3,
            ),
        )
        return (True, "Chat completions accessible") if ok else (False, f"Chat preflight failed: {details}")
    except Exception as e:
        return False, f"Chat preflight exception: {e}"


async def validate_scillm_preflight() -> Tuple[bool, str]:
    """
    Full SciLLM preflight validation per AGENTS.md requirements.
    Uses paved timeouts; no external wait_for wrapping required.
    Returns (success, reason).
    """
    base_url = os.getenv("CHUTES_API_BASE", "").rstrip("/")
    api_key = os.getenv("CHUTES_API_KEY", "")

    if not base_url:
        return False, "CHUTES_API_BASE not set"
    if not api_key:
        return False, "CHUTES_API_KEY not set"

    # Prefer paved healthcheck from scillm if available (Router-only policy)
    try:
        from scillm.paved import chutes_healthcheck  # type: ignore

        hc = chutes_healthcheck(timeout=15.0)
        if asyncio.iscoroutine(hc):
            hc = await hc
        ok = bool(hc.get("ok")) if isinstance(hc, dict) else False
        if ok:
            logger.info("SciLLM preflight (paved): ok — served_model=%s", hc.get("served_model"))
            return True, "Healthcheck passed"
        # fall through to explicit probes if paved check reports not ok
    except Exception as e:
        logger.warning(f"SciLLM paved healthcheck failed: {e}")

    # Fallback explicit probes (rarely needed)
    models_ok, models_reason = await probe_models_endpoint(base_url, api_key)
    if not models_ok:
        return False, f"Models probe failed: {models_reason}"

    chat_ok, chat_reason = await probe_chat_completions_endpoint(base_url, api_key)
    if not chat_ok:
        return False, f"Chat completions probe failed: {chat_reason}"

    logger.info("SciLLM preflight validation passed")
    return True, "All endpoints accessible and responsive"


def validate_scillm_env_sync() -> Tuple[bool, str]:
    """Synchronous wrapper for validate_scillm_preflight(). Relies on paved timeouts."""
    try:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        if loop.is_running():
            # Already running loop: schedule task and wait
            fut = asyncio.run_coroutine_threadsafe(validate_scillm_preflight(), loop)
            return fut.result()
        else:
            return asyncio.run(validate_scillm_preflight())
    except Exception as e:
        return False, f"Preflight validation error: {e}"


def require_scillm_preflight() -> None:
    """
    Require SciLLM preflight validation, raise RuntimeError if failed.
    Per AGENTS.md: "Fail fast on non-200"
    """
    ok, reason = validate_scillm_env_sync()
    if not ok:
        raise RuntimeError(f"SciLLM preflight failed: {reason}")


# Quick validation function for use in stages
def quick_scillm_check() -> bool:
    """Quick check if SciLLM environment is properly configured."""
    text_model = os.getenv("CHUTES_TEXT_MODEL")
    vlm_model = os.getenv("CHUTES_VLM_MODEL")
    base_url = os.getenv("CHUTES_API_BASE")
    api_key = os.getenv("CHUTES_API_KEY")
    
    if not base_url or not api_key:
        return False
    
    # At least one model should be configured for the pipeline to work
    if not text_model and not vlm_model:
        return False
    
    return True


if __name__ == "__main__":
    # Quick test
    logging.basicConfig(level=logging.INFO)
    ok, reason = validate_scillm_env_sync()
    print(f"SciLLM preflight: {'✅ PASS' if ok else '❌ FAIL'} - {reason}")
