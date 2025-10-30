#!/usr/bin/env python3
"""Debug the SciLLM preflight issue."""

import os
import asyncio
import aiohttp
import json
from urllib.parse import urljoin

async def debug_models_probe():
    """Debug the models endpoint probe."""
    base_url = os.getenv("CHUTES_API_BASE", "").rstrip("/")
    api_key = os.getenv("CHUTES_API_KEY", "")
    
    print(f"Base URL: {base_url}")
    print(f"API Key: {'*' * 10 if api_key else 'NOT SET'}")
    
    headers = {"Authorization": f"Bearer {api_key}"}
    
    try:
        async with aiohttp.ClientSession() as session:
            models_url = f"{base_url}/models"
            print(f"Requesting: {models_url}")
            
            async with session.get(
                models_url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                print(f"Response status: {resp.status}")
                print(f"Response headers: {dict(resp.headers)}")
                
                text = await resp.text()
                print(f"Response body (first 500 chars): {text[:500]}")
                
                if resp.status == 200:
                    try:
                        data = json.loads(text)
                        models = data.get("data", [])
                        print(f"Found {len(models)} models")
                        
                        # Check for our specific models
                        text_model = os.getenv("CHUTES_TEXT_MODEL")
                        vlm_model = os.getenv("CHUTES_VLM_MODEL")
                        
                        model_ids = [m.get("id", "") for m in models]
                        print(f"Text model '{text_model}': {'FOUND' if text_model in model_ids else 'NOT FOUND'}")
                        print(f"VLM model '{vlm_model}': {'FOUND' if vlm_model in model_ids else 'NOT FOUND'}")
                        
                        if text_model and text_model not in model_ids:
                            print(f"Available models containing text model name parts:")
                            name_parts = text_model.split("/")
                            for part in name_parts:
                                matches = [m for m in model_ids if part in m]
                                if matches:
                                    print(f"  '{part}' matches: {matches[:3]}")
                                    
                    except Exception as e:
                        print(f"Error parsing JSON: {e}")
                else:
                    print(f"Error response: {text}")
                    
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    asyncio.run(debug_models_probe())