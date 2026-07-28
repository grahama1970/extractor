#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import base64
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from litellm import aresponses
except Exception as e:
    raise SystemExit(f"litellm not available: {e}")

# Optional: use our wrapper (auto-adapt + extraction)
USE_LITELLM_CALL = os.getenv("MODEL_PROBE_USE_LITELLM_CALL", "0").lower() in (
    "1",
    "true",
    "yes",
    "y",
)
AUTO_ADAPT = os.getenv("LITELLM_AUTO_ADAPT_RESPONSES", "1").lower() in ("1", "true", "yes", "y")
RESP_KWARGS_ENV = os.getenv("MODEL_PROBE_RESPONSES_KWARGS", "").strip()
try:
    from extractor.pipeline.utils.litellm_call import litellm_call
except Exception:
    litellm_call = None  # type: ignore


@dataclass
class ModelSpec:
    """Define a model specification with name and provider attributes."""
    name: str
    provider: str  # 'openai' | 'gemini' | 'moonshot' | 'other'


def b64_image(path: Path) -> str:
    """Return base64 image data URI from path."""
    raw = path.read_bytes()
    return f"data:image/png;base64,{base64.b64encode(raw).decode('utf-8')}"


def clean_fences(s: str) -> str:
    """Remove markdown code fences and language specifier."""
    s2 = s.strip()
    if s2.startswith("```"):
        s2 = s2.split("\n", 1)[1] if "\n" in s2 else s2
        if s2.endswith("```"):
            s2 = s2[:-3]
    return s2.strip()


def extract_text_from_responses(resp: Any) -> str:
    # Works for OpenAI Responses object or dict form
    out = getattr(resp, "output", None)
    if out is None and isinstance(resp, dict):
        out = resp.get("output")
    if isinstance(out, list) and out:
        parts = []
        first = out[0]
        content = (
            getattr(first, "content", None) if not isinstance(first, dict) else first.get("content")
        )
        if isinstance(content, list):
            for item in content:
                txt = (
                    getattr(item, "text", None) if not isinstance(item, dict) else item.get("text")
                )
                if isinstance(txt, str) and txt.strip():
                    parts.append(txt)
        return "\n".join(parts)
    return ""


async def call_responses(
    model: str, system: str, items: List[Dict[str, Any]], *, provider: str, variant: str
) -> Tuple[str, Dict[str, Any]]:
    """Call LiteLLM Responses API with provider-aware kwargs; try multiple OpenAI JSON modes."""
    call_meta: Dict[str, Any] = {"variant": variant}

    # Per-provider candidate kwargs
    candidates: List[Dict[str, Any]] = []
    base = {"model": model, "input": [{"role": "user", "content": items}], "max_output_tokens": 800}
    if provider == "openai":
        # 1) json_object
        candidates.append(
            {**base, "response_format": {"type": "json_object"}, "instructions": system}
        )
        # 2) json_schema (simple schema to prove JSON)
        schema = {
            "type": "object",
            "properties": {
                "reflowed_json": {"type": "object"},
                "ocr_corrections": {"type": "object"},
                "improvements_made": {"type": "string"},
                "summary": {"type": "string"},
            },
            "required": ["reflowed_json"],
            "additionalProperties": True,
        }
        candidates.append(
            {
                **base,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {"name": "reflow", "schema": schema, "strict": True},
                },
                "instructions": system,
            }
        )
    elif provider == "gemini":
        candidates.append(
            {**base, "response_mime_type": "application/json", "system_instruction": system}
        )
    else:
        candidates.append({**base, "instructions": system})

    # If requested, route via our wrapper (no auto-adapt by default)
    if USE_LITELLM_CALL and litellm_call is not None:
        for kw in candidates:
            prompts = [
                {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": items},
                    ],
                    "responses_kwargs": json.loads(RESP_KWARGS_ENV) if RESP_KWARGS_ENV else {},
                    "max_tokens": 800,
                }
            ]
            try:
                out = await litellm_call(
                    prompts, wrap_json=True, concurrency=1, desc=f"probe:{model}"
                )
                return (out[0] or ""), {**call_meta, "via": "litellm_call"}
            except Exception as e:
                last_err = f"{type(e).__name__}: {e}"
        return "", {**call_meta, "via": "litellm_call", "error": last_err}

    # Direct Responses attempts
    last_err = None
    for kw in candidates:
        try:
            resp = await aresponses(**kw)
            text = extract_text_from_responses(resp)
            if text and text.strip():
                return text, {**call_meta, "raw": str(resp)[:400], "via": "aresponses"}
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
    return "", {**call_meta, "via": "aresponses", "error": last_err or "empty"}


async def probe_model(
    spec: ModelSpec, outdir: Path, text: str, section_img_b64: str
) -> Dict[str, Any]:
    """Query a model with text and image, returning structured results."""
    model = spec.name
    mslug = model.replace("/", "__")
    mdir = outdir / mslug
    mdir.mkdir(parents=True, exist_ok=True)
    results: Dict[str, Any] = {"model": model, "provider": spec.provider, "attempts": []}

    system = (
        "Return ONLY a JSON object with keys: reflowed_json, ocr_corrections, improvements_made, summary. "
        'reflowed_json must contain {"section_id","title","blocks":[]}. No code fences.'
    )

    # Prepare content items
    # Prefer a tiny remote png to sidestep provider data-URL quirks; also attach section image
    remote_png = {"type": "input_image", "image_url": "https://httpbin.org/image/png"}
    section_img = {"type": "input_image", "image_url": section_img_b64}
    text_item = {"type": "input_text", "text": text}

    # Strategy 1: remote tiny + text (minimal)
    items1 = [text_item, remote_png]
    # Strategy 2: section image + text
    items2 = [text_item, section_img]
    # Strategy 3: both images
    items3 = [text_item, remote_png, section_img]

    strategies = [
        ("remote+text", items1),
        ("section+text", items2),
        ("both+text", items3),
    ]

    worked = False
    for variant, items in strategies:
        try:
            content, meta = await call_responses(
                model, system, items, provider=spec.provider, variant=variant
            )
            meta["len"] = len(content)
            (mdir / f"raw_{variant}.txt").write_text(content or "", encoding="utf-8")
            ok = False
            parsed: Optional[Dict[str, Any]] = None
            if content:
                try:
                    cleaned = clean_fences(content)
                    parsed = json.loads(cleaned)
                    ok = isinstance(parsed, dict) and bool(parsed.get("reflowed_json"))
                except Exception:
                    ok = False
            results["attempts"].append({"variant": variant, "ok": ok, "meta": meta})
            if ok and not worked:
                # Persist parsed JSON for inspection
                (mdir / f"parsed_{variant}.json").write_text(
                    json.dumps(parsed, indent=2, ensure_ascii=False), encoding="utf-8"
                )
                worked = True
        except Exception as e:
            results["attempts"].append({"variant": variant, "error": f"{type(e).__name__}: {e}"})

    results["worked"] = worked
    (mdir / "summary.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return results


async def main() -> None:
    """Create output directory and load context text and image data."""
    base = Path("tests/stage07_manual")
    outdir = base / "model_runs"
    outdir.mkdir(parents=True, exist_ok=True)

    context_text = (base / "context_text.txt").read_text(encoding="utf-8")[:2400]
    section_img_b64 = b64_image(base / "images" / "section.png")

    models = [
        ModelSpec("openai/gpt-5-mini", "openai"),
        ModelSpec("openai/gpt-5", "openai"),
        ModelSpec("gemini/gemini-2.5-flash", "gemini"),
        ModelSpec("moonshot/kimi-k2-turbo-preview", "moonshot"),
    ]

    results: List[Dict[str, Any]] = []
    for spec in models:
        r = await probe_model(spec, outdir, context_text, section_img_b64)
        results.append(r)

    # Print compact summary
    print("\nModel Probe Summary:\n")
    for r in results:
        attempts = r.get("attempts", [])
        status = "✅" if r.get("worked") else "❌"
        variants = ", ".join(
            f"{a.get('variant')}: {'ok' if a.get('ok') else 'fail'}" for a in attempts
        )
        print(f"- {r['model']} [{r['provider']}] {status} → {variants}")
    print(f"\nDetails written to: {outdir}")


if __name__ == "__main__":
    asyncio.run(main())
