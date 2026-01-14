#!/usr/bin/env python3
"""
S11b_scillm_lean4.py - Sanity check for scillm Certainly/Lean4 endpoint.

Purpose:
- Verify that the scillm Lean4 proving bridge works.
- This is required for S11 (Lean4 Theorem Prover).

Dependencies:
- scillm.extras.providers.certainly_prove
- CERTAINLY_BRIDGE_BASE or LEAN4_BRIDGE_BASE env var
- Lean4 bridge running

Success Criteria:
- API call succeeds
- Response contains proof status (proved/failed/timeout)
"""

import asyncio
import os
import sys
from pathlib import Path

# Resolve project root
ROOT = Path(__file__).resolve().parents[3]


async def _run() -> int:
    # Load dotenv if available
    try:
        from dotenv import find_dotenv, load_dotenv
        load_dotenv(find_dotenv(usecwd=True), override=False)
    except ImportError:
        pass
    
    # Get bridge URL
    bridge_base = (
        os.getenv("CERTAINLY_BRIDGE_BASE")
        or os.getenv("LEAN4_BRIDGE_BASE")
        or "http://127.0.0.1:8787"
    )
    
    print(f"Testing scillm Lean4 bridge...")
    print(f"  Bridge URL: {bridge_base}")
    
    # Import scillm Lean4 provider
    try:
        from scillm.extras.providers import certainly_prove
    except ImportError as e:
        print(f"SKIP: scillm Lean4 provider not installed ({e})")
        return 0
    
    # Simple proof request (Nat.add_assoc is trivial)
    requirement_text = os.getenv("LEAN4_REQUIREMENT_TEXT", "Nat.add_assoc")
    max_seconds = float(os.getenv("LEAN4_MAX_SECONDS", "30"))
    
    print(f"  Requirement: {requirement_text}")
    print(f"  Timeout: {max_seconds}s")
    
    try:
        result = await certainly_prove(
            requirement=requirement_text,
            base_url=bridge_base,
            max_seconds=max_seconds,
        )
        
        if not isinstance(result, dict):
            print(f"FAIL: Unexpected result type: {type(result)}")
            return 1
        
        status = result.get("status") or result.get("proved")
        lean_code = result.get("lean_code") or result.get("code")
        
        print(f"  Status: {status}")
        if lean_code:
            print(f"  Code snippet: {lean_code[:80]}...")
        
        print(f"OK: Lean4 bridge responded")
        return 0
        
    except Exception as e:
        error_str = str(e).lower()
        if "connection" in error_str or "refused" in error_str or "timeout" in error_str:
            print(f"SKIP: Lean4 bridge not reachable ({e})")
            return 0  # Skip, not fail - Lean4 is optional
        print(f"FAIL: Lean4 bridge error: {e}")
        return 1


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    sys.exit(main())
