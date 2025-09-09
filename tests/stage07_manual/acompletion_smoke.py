#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv, find_dotenv
from extractor.pipeline.utils.litellm_cache import initialize_litellm_cache

try:
    from litellm import acompletion
except Exception as e:
    raise SystemExit(f"litellm not available: {e}")

load_dotenv(find_dotenv(), override=False)
try:
    initialize_litellm_cache()
except Exception:
    pass


@dataclass
class Probe:
    model: str
    provider: str  # 'openai' | 'gemini' | 'moonshot'


def strip_fences_and_crop(s: str) -> str:
    if not s:
        return s
    s2 = s.strip()
    if s2.startswith("```"):
        s2 = s2.split("\n", 1)[1] if "\n" in s2 else s2
        if s2.endswith("```"):
            s2 = s2[:-3]
    s2 = s2.strip()
    if s2 and (s2[0] != '{' or s2[-1] != '}'):
        a = s2.find('{'); b = s2.rfind('}')
        if a != -1 and b != -1 and b > a:
            s2 = s2[a:b+1]
    return s2


def parse_json(s: str) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(strip_fences_and_crop(s))
    except Exception:
        return None


async def try_chat(model: str, messages: List[Dict[str, Any]], **extra) -> str:
    resp = await acompletion(model=model, messages=messages, **extra)
    # 1) Standard path
    try:
        choices = getattr(resp, 'choices', [])
        if choices:
            msg = getattr(choices[0], 'message', None)
            if msg is not None:
                content = getattr(msg, 'content', None)
                if isinstance(content, str) and content.strip():
                    return content
    except Exception:
        pass
    # 2) Some providers expose .text
    try:
        txt = getattr(resp, 'text', None)
        if isinstance(txt, str) and txt.strip():
            return txt
    except Exception:
        pass
    # 3) Dict-like fallback
    if isinstance(resp, dict):
        try:
            ch = resp.get('choices') or []
            if ch:
                msg = ch[0].get('message') or {}
                content = msg.get('content')
                if isinstance(content, str) and content.strip():
                    return content
        except Exception:
            pass
        # last resort: dump and try to crop JSON from string form
        try:
            s = json.dumps(resp)
            return s
        except Exception:
            pass
    # 4) Stringify object
    try:
        s = str(resp)
        return s
    except Exception:
        return ""


async def run_openai(model: str, outdir: Path) -> Tuple[bool, str]:
    # Use the working pattern from gpt5_acompletion.py
    def _guess_mime(path: Path) -> str:
        ext = path.suffix.lower().lstrip('.')
        return {
            'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'webp': 'image/webp',
            'gif': 'image/gif', 'bmp': 'image/bmp', 'tiff': 'image/tiff'
        }.get(ext, 'application/octet-stream')
    def _file_to_data_uri_tail(path: Path) -> str:
        import base64
        data = path.read_bytes()
        b64 = base64.b64encode(data).decode('ascii')
        return f"{_guess_mime(path)};base64,{b64}"
    def images_to_mm_content(prompt_text: str, images: List[str]) -> List[Dict[str, Any]]:
        parts: List[Dict[str, Any]] = [{"type": "text", "text": prompt_text}]
        for p in images:
            path = Path(p).expanduser().resolve()
            if not path.is_file():
                continue
            tail = _file_to_data_uri_tail(path)
            parts.append({"type": "image_url", "image_url": {"url": f"data:{tail}"}})
        return parts

    images = [
        "tests/stage07_manual/images/smoke/panda.png",
        "tests/stage07_manual/images/smoke/parrot.png",
    ]
    messages = [
        {
            "role": "system",
            "content": (
                "You are a vision captioning assistant. "
                "Only output JSON with this schema: [{description: string}, ...]. "
                "No extra text."
            ),
        },
        {
            "role": "user",
            "content": images_to_mm_content("Describe the content of each image.", images),
        },
    ]
    try:
        resp = await acompletion(
            model=model,
            messages=messages,
            max_tokens=400,
            response_format={"type": "json_object"},
        )
        # Try both message.content and text
        content = getattr(resp.choices[0].message, 'content', None) or getattr(resp, 'text', None) or ''
        if isinstance(content, str) and content.strip():
            (outdir/"openai_image_raw.txt").write_text(content, encoding="utf-8")
            parsed = parse_json(content)
            if isinstance(parsed, (dict, list)):
                (outdir/"openai_image_parsed.json").write_text(json.dumps(parsed, indent=2, ensure_ascii=False), encoding="utf-8")
                return True, content
    except Exception:
        pass
    return False, ""


async def run_gemini(model: str, outdir: Path) -> Tuple[bool, str]:
    # Use the same standardized chat settings as OpenAI, BUT do NOT send response_format for Gemini Chat.
    def _guess_mime(path: Path) -> str:
        ext = path.suffix.lower().lstrip('.')
        return {
            'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'webp': 'image/webp',
            'gif': 'image/gif', 'bmp': 'image/bmp', 'tiff': 'image/tiff'
        }.get(ext, 'application/octet-stream')
    def _file_to_data_uri_tail(path: Path) -> str:
        import base64
        data = path.read_bytes()
        b64 = base64.b64encode(data).decode('ascii')
        return f"{_guess_mime(path)};base64,{b64}"
    def images_to_mm_content(prompt_text: str, images: List[str]) -> List[Dict[str, Any]]:
        parts: List[Dict[str, Any]] = [{"type": "text", "text": prompt_text}]
        for p in images:
            path = Path(p).expanduser().resolve()
            if not path.is_file():
                continue
            tail = _file_to_data_uri_tail(path)
            parts.append({"type": "image_url", "image_url": {"url": f"data:{tail}"}})
        return parts
    images = [
        "tests/stage07_manual/images/smoke/panda.png",
        "tests/stage07_manual/images/smoke/parrot.png",
    ]
    # 1) Minimal text-only JSON first (prove JSON-only path)
    messages_min = [
        {"role": "system", "content": "Return ONLY a JSON object. No code fences."},
        {"role": "user", "content": "Return ONLY {\"ok\": true, \"model\": \"%s\"}." % model},
    ]
    try:
        resp = await acompletion(model=model, messages=messages_min)
        content = getattr(resp.choices[0].message, 'content', None) or getattr(resp, 'text', None) or ''
        parsed = parse_json(content)
        if isinstance(parsed, dict) and ("ok" in parsed or "reflowed_json" in parsed):
            (outdir/"gemini_min_raw.txt").write_text(content, encoding="utf-8")
            (outdir/"gemini_min_parsed.json").write_text(json.dumps(parsed, indent=2, ensure_ascii=False), encoding="utf-8")
            # continue to image JSON
        else:
            # If minimal fails, stop here
            return False, content
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"

    # 2) Image + JSON (no response_format)
    messages_img = [
        {"role": "system", "content": "Return ONLY a JSON object: {descriptions:[{description:string},...]}. No code fences."},
        {"role": "user", "content": images_to_mm_content("Describe the content of each image.", images)},
    ]
    try:
        resp = await acompletion(model=model, messages=messages_img)
        content = getattr(resp.choices[0].message, 'content', None) or getattr(resp, 'text', None) or ''
        if isinstance(content, str) and content.strip():
            (outdir/"gemini_image_raw.txt").write_text(content, encoding="utf-8")
            parsed = parse_json(content)
            if isinstance(parsed, (dict, list)):
                (outdir/"gemini_image_parsed.json").write_text(json.dumps(parsed, indent=2, ensure_ascii=False), encoding="utf-8")
                return True, content
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
    return False, content


async def run_moonshot(model: str, outdir: Path) -> Tuple[bool, str]:
    # Same standardized chat settings as others
    def _guess_mime(path: Path) -> str:
        ext = path.suffix.lower().lstrip('.')
        return {
            'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'webp': 'image/webp',
            'gif': 'image/gif', 'bmp': 'image/bmp', 'tiff': 'image/tiff'
        }.get(ext, 'application/octet-stream')
    def _file_to_data_uri_tail(path: Path) -> str:
        import base64
        data = path.read_bytes()
        b64 = base64.b64encode(data).decode('ascii')
        return f"{_guess_mime(path)};base64,{b64}"
    def images_to_mm_content(prompt_text: str, images: List[str]) -> List[Dict[str, Any]]:
        parts: List[Dict[str, Any]] = [{"type": "text", "text": prompt_text}]
        for p in images:
            path = Path(p).expanduser().resolve()
            if not path.is_file():
                continue
            tail = _file_to_data_uri_tail(path)
            parts.append({"type": "image_url", "image_url": {"url": f"data:{tail}"}})
        return parts
    images = [
        "tests/stage07_manual/images/smoke/panda.png",
        "tests/stage07_manual/images/smoke/parrot.png",
    ]
    messages = [
        {"role": "system", "content": "Return ONLY a JSON object. No code fences."},
        {"role": "user", "content": images_to_mm_content("Describe the content of each image.", images)},
    ]
    try:
        resp = await acompletion(model=model, messages=messages, response_format={"type": "json_object"})
        content = getattr(resp.choices[0].message, 'content', None) or getattr(resp, 'text', None) or ''
        if isinstance(content, str) and content.strip():
            (outdir/"moonshot_image_raw.txt").write_text(content, encoding="utf-8")
            parsed = parse_json(content)
            if isinstance(parsed, (dict, list)):
                (outdir/"moonshot_image_parsed.json").write_text(json.dumps(parsed, indent=2, ensure_ascii=False), encoding="utf-8")
                return True, content
    except Exception:
        pass
    return False, ""


async def main() -> None:
    base = Path(__file__).parent
    outdir = base / "chat_runs"
    outdir.mkdir(parents=True, exist_ok=True)

    models = [
        Probe("openai/gpt-5-mini", "openai"),
        Probe("openai/gpt-5", "openai"),
        Probe("gemini/gemini-2.5-flash", "gemini"),
        Probe("moonshot/kimi-k2-turbo-preview", "moonshot"),
    ]

    for p in models:
        print(f"\n=== {p.model} ({p.provider}) ===")
        mdir = outdir / p.model.replace("/", "__")
        mdir.mkdir(parents=True, exist_ok=True)
        try:
            if p.provider == "openai":
                ok, text = await run_openai(p.model, mdir)
            elif p.provider == "gemini":
                ok, text = await run_gemini(p.model, mdir)
            else:
                ok, text = await run_moonshot(p.model, mdir)
            print("ok=", ok, "len=", len(text))
            if ok:
                parsed = parse_json(text)
                (mdir/"parsed.json").write_text(json.dumps(parsed, indent=2, ensure_ascii=False), encoding="utf-8")
            else:
                (mdir/"raw.txt").write_text(text or "", encoding="utf-8")
        except Exception as e:
            print("error:", type(e).__name__, e)


if __name__ == "__main__":
    asyncio.run(main())
