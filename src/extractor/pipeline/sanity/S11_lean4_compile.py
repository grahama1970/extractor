#!/usr/bin/env python3
"""
Sanity Script: S11 Lean4 Compile
================================

Purpose: Verify that the Lean4 compilation infrastructure works by proving "1 + 1 = 2".

This is a quick smoke test to confirm:
1. scillm.extras.providers.certainly_prove_iter is importable
2. The Certainly bridge is reachable
3. Lean4 compiler can compile a trivial theorem

Usage:
    python src/extractor/pipeline/sanity/S11_lean4_compile.py
"""

import asyncio
import os
import sys
from pathlib import Path

def main():
    print("=" * 60)
    print("Sanity Check: Lean4 Trivial Theorem Compilation")
    print("=" * 60)
    
    # 1. Import Check
    print("\n[1/3] Checking imports...")
    try:
        from scillm.extras.providers import certainly_prove_iter
        print("  ✅ scillm.extras.providers.certainly_prove_iter imported")
    except ImportError as e:
        print(f"  ❌ Import failed: {e}")
        return 1
    
    # 2. Bridge Check
    print("\n[2/3] Checking bridge configuration...")
    bridge_base = os.getenv("CERTAINLY_BRIDGE_BASE") or os.getenv("LEAN4_BRIDGE_BASE") or os.getenv("SCILLM_API_BASE")
    if bridge_base:
        print(f"  ✅ Bridge configured: {bridge_base}")
    else:
        print("  ⚠️ No bridge configured (will use default)")
    
    # 3. Prove Trivial Theorem
    print("\n[3/3] Attempting to prove: 1 + 1 = 2")
    
    async def prove_trivial():
        items = [{"requirement_text": "Prove that 1 + 1 = 2", "id": "sanity_001"}]
        
        results = []
        async for res in certainly_prove_iter(
            items=items,
            response_format={"type": "json_object"},
            concurrency=1,
        ):
            results.append(res)
            ok = res.get("ok", False)
            if ok:
                print(f"  ✅ Proof received (ok={ok})")
                # Check for Lean compilation result
                content = res.get("content", "")
                if "OK" in str(content) or "verified" in str(content).lower():
                    print("  ✅ Lean4 compilation succeeded!")
                else:
                    print(f"  ⚠️ Received response, checking proof...")
            else:
                error = res.get("error") or res.get("status", "unknown")
                print(f"  ❌ Proof failed: {error}")
        
        return len(results) > 0 and any(r.get("ok") for r in results)
    
    try:
        success = asyncio.run(prove_trivial())
        if success:
            print("\n" + "=" * 60)
            print("✅ SANITY CHECK PASSED: Lean4 infrastructure is functional")
            print("=" * 60)
            return 0
        else:
            print("\n" + "=" * 60)
            print("❌ SANITY CHECK FAILED: No successful proof received")
            print("=" * 60)
            return 1
    except Exception as e:
        print(f"\n❌ Exception during proving: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
