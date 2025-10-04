"""
Chutes warmup utility (verified working model slugs via .env)

- Reads CHUTES_API_BASE/CHUTES_API_KEY and LITELLM_*_MODEL variables from .env
- Sends a tiny warmup request to each unique model to prime provider backends
- Optional single test completion for a specific model via CLI arg

Usage:
  python debug/chutes_call.py                # warmup all from .env
  python debug/chutes_call.py --test LARGE   # also run a short test completion on LARGE
  python debug/chutes_call.py --dry-run      # print plan, do not call
"""

import asyncio
import os
import time
from typing import Dict, List, Tuple

import litellm
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())


def _env_models() -> Dict[str, str]:
    keys = [
        "LITELLM_DEFAULT_MODEL",
        "LITELLM_SMALL_VLM_MODEL",
        "LITELLM_MED_VLM_MODEL",
        "LITELLM_LARGE_VLLM_MODEL",
        "LITELLM_SMALL_TEXT_MODEL",
        "LITELLM_MED_TEXT_MODEL",
        "LITELLM_LARGE_TEXT_MODEL",
        "LITELLM_CHUTES_KIMI_K2",
    ]
    out: Dict[str, str] = {}
    for k in keys:
        v = os.getenv(k)
        if v:
            out[k] = v.strip().strip('"')
    return out


async def warmup_model(model: str, api_key: str, api_base: str, timeout_s: float = 30.0) -> Tuple[str, bool, float, str]:
    t0 = time.time()
    try:
        resp = await litellm.acompletion(
            model=model,
            api_key=api_key,
            api_base=api_base,
            messages=[{"role": "system", "content": "ping"}],
            request_timeout=timeout_s,
            max_tokens=8,
        )
        dt = time.time() - t0
        ok = bool(getattr(resp, "choices", None))
        return model, ok, dt, "ok"
    except Exception as e:
        dt = time.time() - t0
        return model, False, dt, f"error: {type(e).__name__}: {e}"


async def test_completion(model: str, api_key: str, api_base: str, timeout_s: float = 30.0) -> str:
    resp = await litellm.acompletion(
        model=model,
        api_key=api_key,
        api_base=api_base,
        messages=[{"role": "user", "content": "Reply 'pong' and nothing else."}],
        request_timeout=timeout_s,
        max_tokens=16,
        temperature=0,
    )
    return resp.choices[0].message.content if resp.choices else ""


async def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--test", choices=["DEFAULT","SMALL_VLM","MED_VLM","LARGE","SMALL","MED","LARGE_TEXT"], help="Run a short test completion after warmup for the chosen slot")
    args = parser.parse_args()

    api_key = os.getenv("CHUTES_API_KEY")
    api_base = os.getenv("CHUTES_API_BASE") or "https://api.chutes.ai/v1"
    if not api_key:
        print("CHUTES_API_KEY not set; aborting.")
        return

    models = _env_models()
    unique = list(dict.fromkeys(models.values()))  # preserve order, dedupe

    print("Warmup plan:")
    for k, v in models.items():
        print(f"  {k}: {v}")
    if args.dry_run:
        return

    # Warm up all unique models concurrently
    coros = [warmup_model(m, api_key, api_base) for m in unique]
    results = await asyncio.gather(*coros)
    print("\nWarmup results:")
    for m, ok, dt, msg in results:
        status = "OK" if ok else "FAIL"
        print(f"  {m:60s}  {status:4s}  {dt*1000:6.1f} ms  {msg}")

    # Optional short test completion for a chosen slot
    slot_alias = args.test
    if slot_alias:
        slot_map = {
            "DEFAULT": "LITELLM_DEFAULT_MODEL",
            "SMALL_VLM": "LITELLM_SMALL_VLM_MODEL",
            "MED_VLM": "LITELLM_MED_VLM_MODEL",
            "LARGE": "LITELLM_LARGE_VLLM_MODEL",
            "SMALL": "LITELLM_SMALL_TEXT_MODEL",
            "MED": "LITELLM_MED_TEXT_MODEL",
            "LARGE_TEXT": "LITELLM_LARGE_TEXT_MODEL",
        }
        mdl = models.get(slot_map[slot_alias])
        if mdl:
            print(f"\nTest completion on {slot_alias} → {mdl}")
            out = await test_completion(mdl, api_key, api_base)
            print("Test output:", out)
        else:
            print(f"Slot {slot_alias} not set in environment")


if __name__ == "__main__":
    asyncio.run(main())
