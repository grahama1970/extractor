#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import base64
import json
from dataclasses import dataclass
from dotenv import load_dotenv, find_dotenv
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from litellm import aresponses
except Exception as e:
    raise SystemExit(f"litellm not available: {e}")

# Load API keys from .env
load_dotenv(find_dotenv(), override=False)


@dataclass
class Probe:
    """Define an AI model and its associated provider."""
    model: str
    provider: str  # 'openai' | 'gemini' | 'moonshot'


def load_section_image_b64() -> str:
    """Load section image as a base64 data URI string."""
    img = (Path(__file__).parent / "images" / "section.png").read_bytes()
    return f"data:image/png;base64,{base64.b64encode(img).decode('utf-8')}"


def extract_text(resp: Any) -> str:
    """Extract text content from a response object."""
    out = getattr(resp, "output", None)
    if out is None and isinstance(resp, dict):
        out = resp.get("output")
    buf: List[str] = []
    if isinstance(out, list) and out:
        content = getattr(out[0], "content", None) or (
            out[0].get("content") if isinstance(out[0], dict) else None
        )
        if isinstance(content, list):
            for item in content:
                txt = (
                    getattr(item, "text", None) if not isinstance(item, dict) else item.get("text")
                )
                if isinstance(txt, str) and txt.strip():
                    buf.append(txt)
    return "\n".join(buf)


def try_parse_json(text: str) -> Optional[Dict[str, Any]]:
    """Try to parse a JSON string and return a dictionary or None."""
    s = (text or "").strip()
    # strip common code fences
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s
        if s.endswith("```"):
            s = s[:-3]
    s = s.strip()
    # naive brace crop
    if s and (s[0] != "{" or s[-1] != "}"):
        a = s.find("{")
        b = s.rfind("}")
        if a != -1 and b != -1 and b > a:
            s = s[a : b + 1]
    try:
        return json.loads(s)
    except Exception:
        return None


async def try_openai(model: str, items: List[Dict[str, Any]], sys_text: str) -> Tuple[str, str]:
    # 1) json_object (with image)
    kwargs = {
        "model": model,
        "input": [{"role": "user", "content": items}],
        "response_format": {"type": "json_object"},
        "max_output_tokens": 400,
        "instructions": sys_text,
    }
    try:
        r = await aresponses(**kwargs)
        t = extract_text(r)
        if t.strip():
            return t, "json_object"
    except Exception:
        pass
    # 2) json_schema minimal (with image)
    schema = {
        "type": "object",
        "properties": {"reflowed_json": {"type": "object"}, "summary": {"type": "string"}},
        "required": ["reflowed_json"],
        "additionalProperties": True,
    }
    kwargs2 = {
        "model": model,
        "input": [{"role": "user", "content": items}],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "reflow", "schema": schema, "strict": True},
        },
        "max_output_tokens": 400,
        "instructions": sys_text,
    }
    r = await aresponses(**kwargs2)
    return extract_text(r), "json_schema"


async def try_gemini(model: str, items: List[Dict[str, Any]], sys_text: str) -> Tuple[str, str]:
    """Query Gemini model and extract text from its response."""
    kwargs = {
        "model": model,
        "input": [{"role": "user", "content": items}],
        "response_mime_type": "application/json",
        "system_instruction": sys_text,
        "max_output_tokens": 400,
    }
    r = await aresponses(**kwargs)
    return extract_text(r), "response_mime_type"


async def try_moonshot(model: str, items: List[Dict[str, Any]], sys_text: str) -> Tuple[str, str]:
    """Return extracted text and instructions from a model response."""
    kwargs = {
        "model": model,
        "input": [{"role": "user", "content": items}],
        "instructions": sys_text,
        "max_output_tokens": 400,
    }
    r = await aresponses(**kwargs)
    return extract_text(r), "instructions"


async def main() -> None:
    """Return a JSON object with specified keys from the processed image."""
    section_img = load_section_image_b64()
    # Stage-07 style minimal system instruction
    sys_text = (
        "Return ONLY a JSON object with keys: reflowed_json, ocr_corrections, improvements_made, summary. "
        'reflowed_json must contain {"section_id","title","blocks":[]}. No code fences.'
    )
    # One image + short text
    context = "Stage07 minimal probe"
    items = [
        {"type": "input_text", "text": context},
        {"type": "input_image", "image_url": section_img},
    ]

    models = [
        Probe("openai/gpt-5-mini", "openai"),
        Probe("openai/gpt-5", "openai"),
        Probe("gemini/gemini-2.5-flash", "gemini"),
        Probe("moonshot/kimi-k2-turbo-preview", "moonshot"),
    ]

    outdir = Path(__file__).parent / "aresponses_runs"
    outdir.mkdir(parents=True, exist_ok=True)

    for p in models:
        print(f"\n=== {p.model} ({p.provider}) ===")
        try:
            if p.provider == "openai":
                text, mode = await try_openai(p.model, items, sys_text)
                # fallback: text-only
                if not text.strip():
                    items_text_only = [{"type": "input_text", "text": context}]
                    text, mode = await try_openai(
                        p.model, items_text_only, sys_text + " Return only minimal JSON if needed."
                    )
            elif p.provider == "gemini":
                text, mode = await try_gemini(p.model, items, sys_text)
                # fallback: text-only
                if not text.strip():
                    items_text_only = [{"type": "input_text", "text": context}]
                    text, mode = await try_gemini(p.model, items_text_only, sys_text)
            else:
                text, mode = await try_moonshot(p.model, items, sys_text)
                if not text.strip():
                    items_text_only = [{"type": "input_text", "text": context}]
                    text, mode = await try_moonshot(p.model, items_text_only, sys_text)
            # Save outputs
            mslug = p.model.replace("/", "__")
            (outdir / f"{mslug}__raw.txt").write_text(text, encoding="utf-8")
            ok = False
            parsed = try_parse_json(text)
            if isinstance(parsed, dict):
                ok = bool(parsed.get("reflowed_json")) or (
                    "ok" in parsed
                )  # accept trivial JSON in smoke
                if ok:
                    (outdir / f"{mslug}__parsed.json").write_text(
                        json.dumps(parsed, indent=2, ensure_ascii=False), encoding="utf-8"
                    )
            print(f"mode={mode} len={len(text)} ok={ok}")
        except Exception as e:
            print(f"error: {type(e).__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(main())
