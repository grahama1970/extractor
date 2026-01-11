#!/usr/bin/env python3
"""Debug: inspect the full certainly_prove_iter response structure."""

import asyncio
import os
import json
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
        print("\n=== FULL RESPONSE DEBUG ===")
        print("Keys in res:", list(res.keys()))
        
        resp = res.get("response")
        print(f"\nType of response: {type(resp)}")
        
        if isinstance(resp, dict):
            print("Response is dict")
            print("Keys:", list(resp.keys()))
            payload = resp.get("additional_kwargs", {})
        else:
            print("Response is object")
            payload = getattr(resp, "additional_kwargs", {})
        
        print(f"\nPayload type: {type(payload)}")
        if isinstance(payload, dict):
            print("Payload keys:", list(payload.keys()))
            print("\nFull payload:")
            print(json.dumps(payload, indent=2, default=str))

if __name__ == "__main__":
    asyncio.run(main())
