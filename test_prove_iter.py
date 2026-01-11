#!/usr/bin/env python3
"""Quick test of certainly_prove_iter with Lean code extraction."""

import asyncio
import os
from dotenv import load_dotenv
from scillm.extras.providers import certainly_prove_iter

load_dotenv()

async def main():
    items = [{"requirement_text": "Nat.add_assoc", "id": "test-1"}]
    
    print("Testing certainly_prove_iter...")
    async for res in certainly_prove_iter(
        items=items,
        api_base=os.getenv("CERTAINLY_BRIDGE_BASE", "http://127.0.0.1:8787"),
        max_seconds=120,
        flags=["--strategies", "direct,structured"],
    ):
        print(f"\n=== Result for {res.get('item', {}).get('id')} ===")
        print(f"ok: {res.get('ok')}")
        print(f"content (summary): {res.get('content', '')[:100]}")
        
        resp = res.get("response")
        if resp is None:
            print(f"ERROR: {res.get('error')}")
            continue
        
        # Extract using the pattern from scillm agent
        payload = resp.get("additional_kwargs", {}) if isinstance(resp, dict) else getattr(resp, "additional_kwargs", {})
        results = (payload.get("certainly", {}) or {}).get("results", [])
        
        if not results:
            print("❌ No results in payload")
            continue
        
        lean_code = results[0].get("lean_code", "")
        success = results[0].get("success", False)
        
        print(f"✅ Success: {success}")
        print(f"Lean code length: {len(lean_code)}")
        if lean_code:
            print(f"Lean code preview: {lean_code[:200]}")
        else:
            print("⚠️ No Lean code captured!")

if __name__ == "__main__":
    asyncio.run(main())
