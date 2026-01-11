
import asyncio
import os
import json
from scillm import parallel_acompletions_iter

# Config (mimicking s08)
model = os.getenv("LEAN4_PROVER_MODEL", "certainly/lean4")
api_base = os.getenv("CERTAINLY_BRIDGE_BASE") # Start with env
if not api_base:
    # Try finding it from scillm defaults or assume chutes
    api_base = os.getenv("SCILLM_API_BASE", "http://localhost:8791/v1")

print(f"Targeting Model: {model} at {api_base}")

async def probe():
    items = [
        {"id": "test_1", "text": "axiom test : True"},
        {"id": "test_2", "text": "theorem foo : 1 = 1 := by rfl"}
    ]
    
    payloads = []
    for item in items:
        # Construct payload compatible with OpenAI ChatCompletion
        # The bridge likely expects the requirement/code in user content
        payloads.append({
            "model": model,
            "id": item["id"], # Pass ID for tracking
            "messages": [
                {"role": "user", "content": item["text"]}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.0
        })
        
    print("Payloads prepared. Running iter...")
    try:
        async for res in parallel_acompletions_iter(
            payloads,
            api_base=api_base,
            api_key=os.getenv("CHUTES_API_KEY"),
            concurrency=2,
            timeout=60
        ):
            print(f"-- Result for {res.get('request', {}).get('id')} --")
            if "error" in res:
                print("ERROR:", res["error"])
            else:
                # Content should be the JSON string from the tool
                content = res.get("choices", [{}])[0].get("message", {}).get("content", "")
                print("CONTENT:", content)
                try:
                    parsed = json.loads(content)
                    print("PARSED OK:", parsed.keys())
                except:
                    print("PARSE FAIL")

    except Exception as e:
        print(f"ITER ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(probe())
