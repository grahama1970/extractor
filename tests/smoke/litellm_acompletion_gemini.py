import os
from litellm import Router
import base64
from pathlib import Path
from extractor.pipeline.utils.litellm_image_utils import (
    compress_image_cached,
    fetch_remote_image_cached,
)
import asyncio
from dotenv import load_dotenv, find_dotenv
from extractor.pipeline.utils.litellm_cache import initialize_litellm_cache

initialize_litellm_cache()
load_dotenv(find_dotenv())

model_list = [
    {
        "model_name": "gemini-2.5-flash",
        "litellm_params": {
            "model": "gemini/gemini-2.5-flash",
            "api_key": os.getenv("GEMINI_API_KEY"),
        },
    },
    {
        "model_name": "kimi-k2-turbo-preview",
        "litellm_params": {
            "model": "moonshot/kimi-k2-turbo-preview",
            "api_key": os.getenv("MOONSHOT_API_KEY"),
        },
    },
    {
        "model_name": "kimi-latest",
        "litellm_params": {
            "model": "moonshot/kimi-k2-turbo-preview",
            "api_key": os.getenv("MOONSHOT_API_KEY"),
        },
    },
]

os.environ.setdefault("LITELLM_LOG", "DEBUG")
router = Router(model_list=model_list)


def _print_resp(label: str, resp):
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


async def try_case(model: str, messages, label: str):
    try:
        resp = await router.acompletion(model=model, messages=messages, timeout=45)
        _print_resp(label, resp)
    except Exception as e:
        print(f"\n=== {label} (exception) ===\n", repr(e))


def text_only(prompt: str):
    return [{"role": "user", "content": [{"type": "text", "text": prompt}]}]


def image_url(prompt: str, url: str):
    return [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": url}},
            ],
        }
    ]


def input_image(prompt: str, url: str):
    # Prefer standard 'text' + 'image_url' parts to satisfy LiteLLM validation
    return [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": url}},
            ],
        }
    ]


def data_url_for_path(p: str) -> str:
    path = Path(p)
    if not path.exists():
        return ""
    # Use the same cached compressor the pipeline uses (PNG output, good for diagrams)
    try:
        return compress_image_cached(str(path), max_kb=1000)
    except Exception:
        # Fallback to raw base64 if compressor not available
        ext = path.suffix.lower().lstrip(".") or "png"
        mime = {
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "webp": "image/webp",
            "gif": "image/gif",
            "bmp": "image/bmp",
            "tiff": "image/tiff",
        }.get(ext, "image/png")
        b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{b64}"


def data_url_for_remote(url: str) -> str:
    try:
        out = fetch_remote_image_cached(url, timeout=10)
        return out or ""
    except Exception:
        return ""


async def main():
    panda = "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0f/Grosser_Panda.JPG/2560px-Grosser_Panda.JPG"
    # Optional: use images from env (comma-separated). Each item may be a local path or a URL.
    # Build data URLs using the same helpers as the pipeline.
    local_list = []
    env_items = os.getenv("S07_IMAGES", "").strip()
    if env_items:
        for item in env_items.split(","):
            item = item.strip()
            if not item:
                continue
            d = data_url_for_path(item) if Path(item).exists() else data_url_for_remote(item)
            if d:
                local_list.append(d)

    # 1) Gemini text-only sanity
    await try_case(
        model="gemini-2.5-flash",
        messages=text_only('Return only {"ok":true} as JSON'),
        label="gemini text-only JSON sanity",
    )

    # 2) Gemini image via image_url (litellm translates often)
    await try_case(
        model="gemini-2.5-flash",
        messages=image_url("Describe this image.", panda),
        label="gemini image_url",
    )

    # 3) Gemini image via input_image/input_text
    await try_case(
        model="gemini-2.5-flash",
        messages=input_image("Describe this image.", panda),
        label="gemini input_image",
    )

    # 3c) Gemini image with Stage‑07 compact JSON guard
    s07_guard = (
        "Return ONLY a JSON object (no code fences). Prefer this shape: "
        '{"reflowed_json":{"section_id":"string","title":"string",'
        '"blocks":[{"type":"paragraph","text":"string"}]},'
        '"ocr_corrections":{},"improvements_made":"string","summary":"string"}. '
        'If you cannot build reflowed_json, return { "reflowed_text": "string" } instead.'
    )
    await try_case(
        model="gemini-2.5-flash",
        messages=input_image(s07_guard, panda),
        label="gemini image_url + s07 guard",
    )

    # 3b) Gemini multi-image input (data URLs if provided via S07_IMAGE_PATHS)
    if local_list:
        msgs = [
            {
                "role": "user",
                "content": (
                    [{"type": "input_text", "text": "Describe these images."}]
                    + [{"type": "input_image", "image_url": {"url": d}} for d in local_list]
                ),
            }
        ]
        await try_case(
            model="gemini-2.5-flash",
            messages=msgs,
            label="gemini multi input_image (data-url)",
        )

    # Keep this smoke minimal and focused on your original three Gemini cases.

    # 4) Kimi (text only — not multimodal)
    await try_case(
        model="kimi-k2-turbo-preview",
        messages=text_only('Return only {"ok":true} as JSON'),
        label="kimi text-only JSON sanity",
    )


if __name__ == "__main__":
    asyncio.run(main())
