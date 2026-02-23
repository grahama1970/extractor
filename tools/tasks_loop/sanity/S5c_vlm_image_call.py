#!/usr/bin/env python3
"""
S5c_vlm_image_call.py - Sanity check for VLM (Vision-Language Model) multimodal call.

Purpose:
- Verify that we can send a base64 image to the VLM and get a response.
- This is the core functionality for S05b (Table Describer) and S06b (Figure Describer).

Pattern:
1. First test with curl (raw HTTP) to verify API connectivity
2. Then test with scillm parallel_acompletions_iter

Dependencies:
- CHUTES_API_KEY or CHUTES_API_TOKEN
- CHUTES_VLM_MODEL (default: Qwen/Qwen3-VL-235B-A22B-Instruct)
- PyMuPDF (to generate test image)

Success Criteria:
- VLM returns a description of the image
"""

import asyncio
import base64
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# Resolve project root
ROOT = Path(__file__).resolve().parents[3]
FIXTURE_PDF = ROOT / "data" / "input" / "pipeline" / "BHT_CV32A65X_test.pdf"


def _get_api_key() -> str:
    key = os.getenv("CHUTES_API_KEY") or os.getenv("CHUTES_API_TOKEN")
    if not key:
        raise RuntimeError("CHUTES_API_KEY or CHUTES_API_TOKEN not set")
    return key


def _create_test_image() -> str:
    """Create a test image from the fixture PDF and return base64."""
    try:
        import fitz
    except ImportError:
        raise RuntimeError("PyMuPDF (fitz) not installed")

    if not FIXTURE_PDF.exists():
        raise RuntimeError(f"Fixture PDF not found: {FIXTURE_PDF}")

    doc = fitz.open(str(FIXTURE_PDF))
    if len(doc) == 0:
        raise RuntimeError("PDF has no pages")

    # Render first page to image
    page = doc[0]
    pix = page.get_pixmap(matrix=fitz.Matrix(1, 1))

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        pix.save(f.name)
        img_path = Path(f.name)

    doc.close()

    # Read and base64 encode
    b64 = base64.b64encode(img_path.read_bytes()).decode("utf-8")
    img_path.unlink()  # Cleanup
    return b64


def test_curl() -> bool:
    """Test VLM call using curl (raw HTTP)."""
    print("=== Step 1: Testing VLM via curl ===")

    api_key = _get_api_key()
    model = os.getenv("CHUTES_VLM_MODEL", "Qwen/Qwen3-VL-235B-A22B-Instruct")
    api_base = os.getenv("SCILLM_API_BASE", "https://llm.chutes.ai/v1")

    print(f"  Model: {model}")
    print(f"  API Base: {api_base}")

    # Create test image
    try:
        b64_image = _create_test_image()
        print(f"  Image: base64 ({len(b64_image)} chars)")
    except Exception as e:
        print(f"FAIL: Could not create test image: {e}")
        return False

    # Build payload
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Describe this image in one sentence. Reply with only the description.",
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64_image}"},
                    },
                ],
            }
        ],
        "max_tokens": 100,
        "temperature": 0.0,
    }

    # Run curl
    cmd = [
        "curl",
        "-s",
        "-X",
        "POST",
        f"{api_base}/chat/completions",
        "-H",
        "Content-Type: application/json",
        "-H",
        f"Authorization: Bearer {api_key}",
        "-d",
        json.dumps(payload),
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            print(f"FAIL: curl returned {result.returncode}")
            print(f"  stderr: {result.stderr[:200]}")
            return False

        response = json.loads(result.stdout)

        # Check for error
        if "error" in response:
            print(f"FAIL: API error: {response['error']}")
            return False

        # Extract content
        choices = response.get("choices", [])
        if not choices:
            print("FAIL: No choices in response")
            return False

        content = choices[0].get("message", {}).get("content", "")
        if not content:
            print("FAIL: No content in response")
            return False

        print(f"  Response: {content[:80]}...")
        print("✅ curl VLM call succeeded")
        return True

    except subprocess.TimeoutExpired:
        print("FAIL: curl timed out")
        return False
    except json.JSONDecodeError as e:
        print(f"FAIL: Invalid JSON response: {e}")
        return False
    except Exception as e:
        print(f"FAIL: {e}")
        return False


async def test_scillm() -> bool:
    """Test VLM call using scillm parallel_acompletions_iter."""
    print("\n=== Step 2: Testing VLM via scillm ===")

    try:
        from dotenv import find_dotenv, load_dotenv

        load_dotenv(find_dotenv(usecwd=True), override=False)
    except ImportError:
        pass

    try:
        from scillm.batch import parallel_acompletions_iter
    except ImportError as e:
        print(f"SKIP: scillm not installed ({e})")
        return True  # Skip, not fail

    api_key = _get_api_key()
    model = os.getenv("CHUTES_VLM_MODEL", "Qwen/Qwen3-VL-235B-A22B-Instruct")
    api_base = os.getenv("SCILLM_API_BASE", "https://llm.chutes.ai/v1")

    # Create test image
    try:
        b64_image = _create_test_image()
    except Exception as e:
        print(f"FAIL: Could not create test image: {e}")
        return False

    # Build payload (OpenAI multimodal format)
    payloads = [
        {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "What type of document is this? Reply in 5 words or less.",
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64_image}"},
                        },
                    ],
                }
            ],
            "max_tokens": 50,
            "temperature": 0.0,
            "id": "vlm-sanity",
        }
    ]

    results = []
    try:
        async for result in parallel_acompletions_iter(
            payloads,
            api_base=api_base,
            api_key=api_key,
            custom_llm_provider="openai_like",
            concurrency=1,
            timeout=60,
            tenacious=True,  # Retry on transient failures (429, etc.)
        ):
            results.append(result)
    except Exception as e:
        print(f"FAIL: parallel_acompletions_iter raised: {e}")
        return False

    if not results:
        print("FAIL: No results returned")
        return False

    first = results[0]
    if first.get("ok") is False:
        print(f"FAIL: LLM error: {first.get('error')}")
        return False

    content = first.get("content") or ""
    if not content:
        print("FAIL: No content in response")
        return False

    print(f"  Response: {content[:80]}...")
    print("✅ scillm VLM call succeeded")
    return True


def main() -> int:
    print("Testing VLM multimodal (image) calls...")

    # Step 1: curl
    if not test_curl():
        return 1

    # Step 2: scillm
    if not asyncio.run(test_scillm()):
        return 1

    print("\n✅ VLM sanity check passed (both curl and scillm)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
