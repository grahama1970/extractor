#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "python-dotenv",
# ]
# ///
"""
Quick sanity: prove a single requirement via SciLLM certainly_prove.
Usage:
  PYTHONPATH=src CHUTES_API_KEY=... CHUTES_API_BASE=... CHUTES_TEXT_MODEL=... \
  python scripts/single_prove_sanity.py
"""
from __future__ import annotations

import asyncio
import json
import os

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(), override=True)

try:
    from scillm.extras.providers import certainly_prove  # type: ignore
except Exception as exc:  # pragma: no cover
    raise RuntimeError(f"certainly_prove not available: {exc}")

# Simple BHT requirement sample
REQ = {
    "requirement_id": "REQ-BHT-1",
    "requirement_text": "The BHT shall implement BHTDepth entries and index them using the lower bits of VPC_i.",
    "modality": "shall",
}


async def main():
    print("Running single prove sanity via certainly_prove ...")
    try:
        res = await asyncio.wait_for(
            asyncio.to_thread(
                certainly_prove,
                items=[
                    {
                        "requirement_id": REQ["requirement_id"],
                        "requirement_text": REQ["requirement_text"],
                    }
                ],
                require_proved=False,
                request_timeout=120.0,
                max_seconds=float(os.getenv("SINGLE_PROVE_TIMEOUT", "180")),
            ),
            timeout=int(os.getenv("SINGLE_PROVE_TIMEOUT", "180")),
        )
    except asyncio.TimeoutError:
        print("Timed out waiting for proof.")
        return
    except Exception as exc:
        print(f"certainly_prove raised: {exc}")
        return

    # Normalize result to JSON for display
    def _to_jsonable(obj):
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        return obj

    try:
        out = json.loads(json.dumps(res, default=_to_jsonable))
    except Exception:
        out = str(res)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
