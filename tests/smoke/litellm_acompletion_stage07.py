#!/usr/bin/env python3
"""
Stage 07 – simplified Router.acompletion smoke for Gemini.

Purpose: Build a minimal Stage-07-like prompt (strict JSON guard + optional image)
and send it directly through LiteLLM Router.acompletion, so we can see exactly
what Gemini returns without the rest of the pipeline involved.

This mirrors tests/smoke/litellm_acompletion_gemini.py style, but shapes the
messages similarly to our Stage 07 shaping (guard in user content).
"""
import os
import asyncio
from dotenv import load_dotenv, find_dotenv
from litellm import Router


def build_router() -> Router:
    model_list = [
        {
            "model_name": "gemini-2.5-flash",
            "litellm_params": {
                "model": "gemini/gemini-2.5-flash",
                "api_key": os.getenv("GEMINI_API_KEY"),
            },
        }
    ]
    os.environ.setdefault("LITELLM_LOG", "DEBUG")
    return Router(model_list=model_list)


def stage07_guard(compact: bool = False) -> str:
    if compact:
        return (
            "Return ONLY a JSON object (no code fences). Prefer this shape: "
            '{"reflowed_json":{"section_id":string,"title":string,"blocks":[{"type":"paragraph","text":string}]},'
            '"ocr_corrections":{},"improvements_made":string,"summary":string}. '
            'If you cannot build reflowed_json, return {"reflowed_text":string} instead.'
        )
    # Full guard (trimmed from step for brevity)
    return (
        "You are a strict JSON reflow engine. Return ONLY a JSON object with keys: "
        "reflowed_json, ocr_corrections, improvements_made, summary. No code fences. "
        "Requirements: reflowed_json.blocks must preserve reading order; include one merged table block when needed; "
        "figure blocks with caption & image_ref; keep table cell text intact."
    )


def text_only_messages(prompt_guard: str, context: str):
    # Stage-07 style for Gemini: put guard at start of user input (use standard 'text' part)
    return [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": f"{prompt_guard}\n\n{context}"},
            ],
        }
    ]


def with_image_messages(prompt_guard: str, context: str, image_url: str):
    # Use standard 'image_url' part for broad LiteLLM compatibility
    return [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": f"{prompt_guard}\n\n{context}"},
                {"type": "image_url", "image_url": {"url": image_url}},
            ],
        }
    ]


def print_resp(label: str, resp):
    print(f"\n=== {label} ===")
    try:
        usage = getattr(resp, "usage", None)
        hidden = getattr(resp, "_hidden_params", None)
        print("usage:", usage)
        print("hidden:", hidden)
        ch = getattr(resp, "choices", None)
        if ch:
            msg = getattr(ch[0], "message", None)
            if msg is not None and getattr(msg, "content", None) is not None:
                print("content:", msg.content)
            else:
                txt = getattr(ch[0], "text", None)
                print("text:", txt)
        else:
            print("raw:", str(resp)[:500])
    except Exception as e:
        print("error printing resp:", e)


async def main():
    load_dotenv(find_dotenv())
    router = build_router()

    # Minimal context (Stage 07 would build from sections/tables/figures)
    context = (
        "Section: Example Submodule (level 2) pages 1–2\n"
        "Paragraphs: describe the system. Tables: optional. Figures: optional."
    )
    panda = (
        "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0f/"
        "Grosser_Panda.JPG/2560px-Grosser_Panda.JPG"
    )

    # 1) Text-only with compact guard
    try:
        resp = await router.acompletion(
            model="gemini-2.5-flash",
            messages=text_only_messages(stage07_guard(compact=True), context),
            timeout=45,
        )
        print_resp("gemini text-only compact", resp)
    except Exception as e:
        print("gemini text-only compact (exception):", repr(e))

    # 2) With input_image
    try:
        resp = await router.acompletion(
            model="gemini-2.5-flash",
            messages=with_image_messages(stage07_guard(compact=True), context, panda),
            timeout=45,
        )
        print_resp("gemini with input_image compact", resp)
    except Exception as e:
        print("gemini with input_image compact (exception):", repr(e))


if __name__ == "__main__":
    asyncio.run(main())
