#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12.3",
#   "rich>=13.7.1",
#   "Pillow>=10.0.0",
# ]
# ///
from __future__ import annotations

import os
import io
import json
import base64
import asyncio
from dataclasses import dataclass
from typing import Optional, List

import typer
from rich.console import Console
from rich.table import Table
from PIL import Image
from pathlib import Path


app = typer.Typer(add_completion=False)
console = Console()
ART_DIR = Path("scripts/artifacts")
ART_DIR.mkdir(parents=True, exist_ok=True)


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    return os.getenv(name, default)


def _make_png_b64(size: int = 256) -> str:
    buf = io.BytesIO()
    Image.new("RGB", (size, size), color=(180, 180, 180)).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


@dataclass
class ProbeResult:
    alias: str
    path: str  # router|litellm
    ok: bool
    err: Optional[str]
    content_snip: str


def _get_router_meta(resp: object) -> dict:
    try:
        ak = getattr(resp, "additional_kwargs", None)
        if isinstance(ak, dict):
            return ak.get("router", {}) or ak.get("scillm_router", {}) or {}
    except Exception:
        pass
    if isinstance(resp, dict):
        return resp.get("scillm_router", {}) or resp.get("router", {}) or {}
    return {}


async def _probe_router(alias: str, b64: str, timeout: int = 30) -> ProbeResult:
    # Prefer SciLLM Router; fallback to litellm.Router if needed
    router = None
    try:
        import scillm  # type: ignore
        router = scillm.Router(deterministic=True)  # type: ignore
    except Exception:
        try:
            from litellm import Router  # type: ignore
            router = Router(deterministic=True)  # type: ignore
        except Exception as e:  # pragma: no cover
            return ProbeResult(alias, "router", False, f"Router import failed: {e}", "")

    png_url = _env("PNG_DATA_URL") or f"data:image/png;base64,{b64}"
    req = {
        "model": alias,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": 'Return only {"ok": true} as JSON.'},
                    {"type": "image_url", "image_url": {"url": png_url}},
                ],
            }
        ],
        "kwargs": {
            "custom_llm_provider": _env("CHUTES_PROVIDER", "openai"),
            "api_base": _env("CHUTES_API_BASE", "https://llm.chutes.ai/v1"),
            "api_key": _env("CHUTES_API_KEY"),
            "response_mode": "schema_first",
            "json_schema": {
                "name": "ok",
                "schema": {
                    "type": "object",
                    "properties": {"ok": {"type": "boolean"}},
                    "required": ["ok"],
                },
            },
            "retry_enabled": True,
            "honor_retry_after": True,
            "timeout": timeout,
        },
    }

    try:
        out = await router.parallel_acompletions([req], max_concurrency=8)  # type: ignore[attr-defined]
        resp = out[0] if out else {}
        meta = resp.get("scillm_router", {}) if isinstance(resp, dict) else {}
        if meta:
            console.print(f"[dim]meta({alias} router): {json.dumps(meta)[:240]}[/dim]")
        content = ((resp.get("choices") or [{}])[0].get("message") or {}).get("content") if isinstance(resp, dict) else None
        # Save raw for debugging
        try:
            raw_path = ART_DIR / f"vision_probe_raw__{alias.replace('/','_')}__router.json"
            raw_path.write_text(json.dumps({"resp": resp, "meta": meta}, indent=2, ensure_ascii=False))
        except Exception:
            pass
        ok = False
        if content:
            try:
                ok = json.loads(content).get("ok") is True
            except Exception:
                ok = False
        return ProbeResult(alias, "router", ok, None, (content or "")[:120])
    except Exception as e:
        return ProbeResult(alias, "router", False, str(e), "")


def _probe_litellm(alias: str, b64: str, timeout: int = 30) -> ProbeResult:
    try:
        import litellm  # type: ignore
    except Exception as e:  # pragma: no cover
        return ProbeResult(alias, "litellm", False, f"litellm import failed: {e}", "")

    req = {
        "model": alias.split("/", 1)[1] if "/" in alias else alias,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Return only {\"ok\":true} as JSON."},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                ],
            }
        ],
        "response_format": {"type": "json_object"},
        "timeout": timeout,
        "api_key": _env("CHUTES_API_KEY"),
        "base_url": _env("CHUTES_API_BASE", "https://llm.chutes.ai/v1"),
        "custom_llm_provider": _env("CHUTES_PROVIDER", "openai"),
    }
    try:
        resp = litellm.completion(**req)  # type: ignore
        content = resp["choices"][0]["message"]["content"] if isinstance(resp, dict) else str(resp)
        # Save raw
        try:
            raw_path = ART_DIR / f"vision_probe_raw__{alias.replace('/','_')}__litellm.json"
            raw_path.write_text(json.dumps(resp if isinstance(resp, dict) else {"raw": str(resp)}, indent=2, ensure_ascii=False))
        except Exception:
            pass
        ok = False
        if content:
            try:
                ok = json.loads(content).get("ok") is True
            except Exception:
                ok = False
        return ProbeResult(alias, "litellm", ok, None, (content or "")[:80])
    except Exception as e:
        return ProbeResult(alias, "litellm", False, str(e), "")


@app.command()
def run(
    timeout: int = typer.Option(30, help="Per-request timeout (s)"),
):
    """Probe vision (image+JSON) via SciLLM Router vs direct litellm on .env VLM aliases."""
    models = [
        _env("LITELLM_SMALL_VLM_MODEL"),
        _env("LITELLM_MED_VLM_MODEL"),
        _env("LITELLM_LARGE_VLM_MODEL") or _env("LITELLM_LARGE_VLLM_MODEL"),
    ]
    models = [m for m in models if m]
    if not models:
        console.print("[yellow]No VLM models set in environment.[/yellow]")
        raise typer.Exit(0)

    b64 = _make_png_b64()
    results: List[ProbeResult] = []

    async def _main():
        for alias in models:
            results.append(await _probe_router(alias, b64, timeout))
            results.append(_probe_litellm(alias, b64, timeout))

    asyncio.run(_main())

    # Render table
    table = Table(title="Vision Probe (image+JSON)")
    for c in ("alias", "path", "ok", "snippet", "err"):
        table.add_column(c)
    for r in results:
        table.add_row(r.alias, r.path, str(r.ok), r.content_snip, (r.err or "")[:120])
    console.print(table)

    # Exit non-zero if both paths failed for any alias
    failures = [r for r in results if not r.ok]
    exit_code = 0 if any(r.ok for r in results) else 1
    raise typer.Exit(exit_code)


if __name__ == "__main__":
    app()
