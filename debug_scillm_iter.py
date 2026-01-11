
import asyncio
import sys
import os

# Ensure we pick up the editable scillm if possible (though path is handled by venv usually)
try:
    from scillm.extras.providers import certainly_prove_iter
    print("SUCCESS: certainly_prove_iter imported.")
except ImportError:
    print("FAILURE: certainly_prove_iter not found in scillm.extras.providers")
    sys.exit(1)

async def probe():
    items = [{"requirement_text": "axiom test : True", "id": "test_id_123"}]
    print("Running probe with items:", items)
    
    try:
        async for res in certainly_prove_iter(
            items=items,
            response_format={"type": "json_object"},
            concurrency=1
        ):
            print("RESULT KEYS:", list(res.keys()))
            print("RESULT RAW:", res)
            
            # Check for ID echo
            if "id" in res:
                print("ID FOUND in root:", res["id"])
            if "request" in res and "id" in res["request"]:
                 print("ID FOUND in request:", res["request"]["id"])
            if "item" in res and "id" in res["item"]:
                print("ID FOUND in item:", res["item"]["id"])
                
    except Exception as e:
        print(f"PROBE ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(probe())
