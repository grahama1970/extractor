import os
import json
import base64
import uuid
import asyncio

from litellm import Router
from dotenv import load_dotenv, find_dotenv
from extractor.pipeline.utils.litellm_cache import initialize_litellm_cache
from extractor.pipeline.utils.litellm_response_utils import extract_content


async def main():
    load_dotenv(find_dotenv())
    initialize_litellm_cache()

    router = Router(
        model_list=[
            {
                "model_name": "gemini-flash",
                "litellm_params": {
                    "model": "gemini/gemini-2.5-flash",
                    "timeout": 30,
                    "num_retries": 2,
                },
            }
        ]
    )

    # Inline image -> base64
    with open("tests/stage07_manual/images/smoke/panda.png", "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode("utf-8")

    # Requests: omit ids; they will be auto-assigned
    requests = [
        {
            "model": "gemini-flash",
            "messages": [{"role": "user", "content": "Say hello from smoke batch test."}],
        },
        {
            "model": "gemini-flash",
            "messages": [{"role": "user", "content": "What is 2+2? Answer with a number only."}],
        },
        {
            "model": "gemini-flash",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "What’s in this image?"},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}" }},
                    ],
                }
            ],
        },
    ]

    # Minimal auto-id assignment; bump to 12–16 chars if you run very large batches
    for r in requests:
        r.setdefault("id", uuid.uuid4().hex[:8])

    id_to_req = {r["id"]: r for r in requests}
    # Redact base64 data URLs in printed requests by default; override with SMOKE_STRIP_BASE64=0
    strip_b64 = (os.getenv("SMOKE_STRIP_BASE64", "1").lower() in ("1", "true", "yes", "y"))

    def _sanitize_messages(msgs):
        import copy
        import re
        mm = copy.deepcopy(msgs)
        for m in mm:
            content = m.get("content")
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and "image_url" in part:
                        url = part["image_url"].get("url")
                        if isinstance(url, str) and url.startswith("data:image"):
                            mtype = "image"
                            try:
                                m = re.match(r"^data:image/([^;]+);base64,", url)
                                if m:
                                    mtype = f"image/{m.group(1)}"
                            except Exception:
                                pass
                            part["image_url"]["url"] = f"data:{mtype};base64,<redacted>"
        return mm

    sem = asyncio.Semaphore(8)

    async def _runner(r):
        rid = r["id"]
        async with sem:
            try:
                resp = await router.acompletion(
                    model=r["model"],
                    messages=r["messages"],
                    metadata={"request_id": rid},
                )
                return rid, resp, None
            except Exception as e:
                return rid, None, str(e)

    tasks = [asyncio.create_task(_runner(r)) for r in requests]

    results_by_id = {}
    for t in asyncio.as_completed(tasks):
        rid, resp, err = await t
        req = id_to_req[rid]
        safe_msgs = _sanitize_messages(req["messages"]) if strip_b64 else req["messages"]
        results_by_id[rid] = {
            "id": rid,
            "request": {"model": req["model"], "messages": safe_msgs},
            "response": extract_content(resp) if resp is not None else "",
            "error": err,
        }
    # Preserve original order
    results = [results_by_id[r["id"]] for r in requests]
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
