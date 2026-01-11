
import asyncio
import os
import sys
from dotenv import load_dotenv, find_dotenv

# Minimal sanity check for Stage 09 (Summarizer)
# Verifies LLM connectivity for the specific model used in S09.
# This separates "Bridge" issues (S08) from "Remote API" issues (S09).

load_dotenv(find_dotenv(usecwd=True), override=False)

try:
    from scillm.batch import parallel_acompletions_iter
    HAS_SCILLM = True
except ImportError:
    HAS_SCILLM = False

async def main():
    if not HAS_SCILLM:
        print("❌ SciLLM not installed/importable. S09 cannot run.")
        return

    # S09 Defaults
    model = os.getenv("CHUTES_TEXT_MODEL", "moonshotai/Kimi-K2-Instruct-0905")
    api_base = os.getenv("SCILLM_API_BASE", "https://llm.chutes.ai/v1")
    api_key = os.getenv("CHUTES_API_KEY", "")
    
    print(f"Testing S09 Summarizer LLM Connection...")
    print(f"API: {api_base}")
    print(f"Model: {model}")
    
    if not api_key:
        print("❌ CHUTES_API_KEY not set.")
        return

    payloads = [{
        "model": model,
        "id": "sanity_test",
        "messages": [{"role": "user", "content": "Summarize this: Hello World."}],
        "temperature": 0.0,
        "response_format": {"type": "json_object"} 
    }]
    
    print("Sending request...")
    results = []
    try:
        async for r in parallel_acompletions_iter(
            payloads,
            api_base=api_base,
            api_key=api_key,
            concurrency=1,
            timeout=30
        ):
            results.append(r)
            
        if not results:
            print("❌ No results yielded from iterator.")
            return
            
        res = results[0]
        if res.get("ok") is False: # SciLLM v1.78 error structure
             print(f"❌ LLM Error: {res.get('error')}")
             return
             
        # Check content
        content = res.get("content") or res.get("parsed") or (res.get("choices")[0].message.content if res.get("choices") else None)
        
        if content:
             print(f"✅ S09 Sanity Passed. Response received: {str(content)[:50]}...")
        else:
             print(f"⚠️ Response received but content empty: {res}")
            
    except Exception as e:
        print(f"❌ S09 Exception: {e}")

if __name__ == "__main__":
    asyncio.run(main())
