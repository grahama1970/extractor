#!/usr/bin/env python3
"""
SciLLM Chutes smoke checks (replaces litellm_call smokes)

Goals
- Confirm SciLLM env model resolution and basic text JSON sanity
- Optionally run an image URL and local image case via helper/compression

Artifacts
- Writes a log file under scripts/artifacts/ with timestamp
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import typer
from dotenv import load_dotenv, find_dotenv


app = typer.Typer(add_completion=False, help="Smoke: SciLLM Chutes helper")


def _resolve_default_model() -> str:
    # Prefer explicit SMOKE_MODEL; then CHUTES_TEXT_MODEL
    sm = os.getenv("SMOKE_MODEL", "").strip()
    if sm:
        return sm
    return os.getenv("CHUTES_TEXT_MODEL", "")


def _ensure_src_path():
    # Allow importing our project module directly
    root = Path(__file__).resolve().parents[2]
    src = root / "src"
    sys.path.insert(0, str(src))


def _write_artifact(lines: list[str]) -> Path:
    root = Path(__file__).resolve().parents[2]
    outdir = root / "scripts" / "artifacts"
    outdir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    outfile = outdir / f"litellm_call_smoke_{ts}.log"
    outfile.write_text("\n".join(lines), encoding="utf-8")
    return outfile


@app.command()
def sanity(
    model: str = typer.Option(_resolve_default_model(), help="Model (defaults to env)"),
    timeout: int = typer.Option(20, help="Request timeout seconds"),
    wrap_json: bool = typer.Option(True, help="Wrap non-JSON; include usage metadata"),
):
    """Run a minimal {\"ok\":true} JSON sanity via SciLLM helper."""
    try:
        try:
            load_dotenv(find_dotenv(usecwd=True))
        except Exception:
            load_dotenv()
        _ensure_src_path()
        from scillm import completion  # type: ignore

        prompt = 'Return only {"ok":true} as JSON.'
        prompts = [prompt]
        kwargs = {
            "wrap_json": wrap_json,
            "response_format": "json_object",
            "request_timeout": timeout,
            "num_retries": 0,
            "show_progress": False,
            "concurrency": 1,
        }

        if not model:
            model = os.getenv("CHUTES_TEXT_MODEL", "")

        # Run and record (SciLLM helper returns OpenAI-like response)
        res = completion(
            model=model,
            custom_llm_provider="openai_like",
            api_base=os.environ.get("CHUTES_API_BASE",""),
            api_key=None,
            extra_headers={"x-api-key": os.environ.get("CHUTES_API_KEY","")},
            messages=[{"role": "user", "content": prompt}],
            response_format={"type":"json_object"},
            timeout=timeout,
        )
        content = res.get("choices", [{}])[0].get("message", {}).get("content", "")
        text = content if isinstance(content, str) else json.dumps(content)
        lines = [f"MODEL={model}", f"PROMPT={prompt}", f"OUTPUT={text[:300]}..."]
        ok = False
        try:
            data = json.loads(text)
            ok = (isinstance(data, dict) and (data.get("ok") is True or (isinstance(data.get("content"), dict) and data["content"].get("ok") is True)))
        except Exception:
            ok = False
        lines.append(f"OK={ok}")
        path = _write_artifact(lines)
        if ok:
            typer.echo(f"OK: sanity passed; artifact: {path}")
        else:
            typer.echo(f"Smoke failed (sanity not ok); artifact: {path}", err=True)
            raise SystemExit(1)
    except Exception as e:
        typer.echo(f"Smoke error: {e}", err=True)
        raise SystemExit(1)


@app.command()
def image_url(
    url: str = typer.Argument("https://httpbin.org/image/png"),
    model: str = typer.Option(_resolve_default_model(), help="Model (defaults to env)"),
    timeout: int = typer.Option(45, help="Request timeout seconds"),
):
    """Describe a public image URL via SciLLM helper (vision-capable model required)."""
    try:
        try:
            load_dotenv(find_dotenv(usecwd=True))
        except Exception:
            load_dotenv()
        _ensure_src_path()
        from scillm import completion  # type: ignore

        if not model:
            model = os.getenv("CHUTES_VLM_MODEL", os.getenv("CHUTES_TEXT_MODEL", ""))

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe this image."},
                    {"type": "image_url", "image_url": {"url": url}},
                ],
            }
        ]
        res = completion(
            model=model,
            custom_llm_provider="openai_like",
            api_base=os.environ.get("CHUTES_API_BASE",""),
            api_key=None,
            extra_headers={"x-api-key": os.environ.get("CHUTES_API_KEY","")},
            messages=messages,
            timeout=timeout,
        )
        content = res.get("choices", [{}])[0].get("message", {}).get("content", "")
        text = content if isinstance(content, str) else json.dumps(content)
        ok = bool(text.strip())
        lines = [
            f"MODEL={model}",
            f"PROMPT=Describe this image.",
            f"OUTPUT={text[:300]}...",
            f"OK={ok}",
        ]
        path = _write_artifact(lines)
        if ok:
            typer.echo(f"OK: image_url returned text; artifact: {path}")
        else:
            typer.echo(f"Smoke failed: empty output; artifact: {path}", err=True)
            raise SystemExit(1)
    except Exception as e:
        typer.echo(f"Smoke error: {e}", err=True)
        raise SystemExit(1)


@app.command()
def local_image(
    path: str = typer.Option("tests/stage07_manual/images/smoke/panda.png", help="Local image path"),
    model: str = typer.Option(_resolve_default_model(), help="Model (defaults to env)"),
    timeout: int = typer.Option(60, help="Request timeout seconds (raised for local images)"),
    max_kb: int = typer.Option(200, help="Max KB for local image compression"),
):
    """Describe a local image (file path) via SciLLM helper (vision)."""
    try:
        try:
            load_dotenv(find_dotenv(usecwd=True))
        except Exception:
            load_dotenv()
        _ensure_src_path()
        from extractor.pipeline.utils.image_helpers import compress_image_cached
        from scillm import completion  # type: ignore
        from pathlib import Path as _Path
        p = _Path(path)
        if not p.exists():
            raise SystemExit(f"Local image not found: {path}")
        data_url = compress_image_cached(str(p), max_kb=max_kb)
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe this image."},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ]
        if not model:
            model = os.getenv("CHUTES_VLM_MODEL", os.getenv("CHUTES_TEXT_MODEL", ""))
        res = completion(
            model=model,
            custom_llm_provider="openai_like",
            api_base=os.environ.get("CHUTES_API_BASE",""),
            api_key=None,
            extra_headers={"x-api-key": os.environ.get("CHUTES_API_KEY","")},
            messages=messages,
            timeout=timeout,
        )
        content = res.get("choices", [{}])[0].get("message", {}).get("content", "")
        text = content if isinstance(content, str) else json.dumps(content)
        ok = bool(text.strip())
        lines = [
            f"MODEL={model}",
            f"PROMPT=Describe this image.",
            f"OUTPUT={text[:300]}...",
            f"OK={ok}",
        ]
        path_out = _write_artifact(lines)
        if ok:
            typer.echo(f"OK: local_image returned text; artifact: {path_out}")
        else:
            typer.echo(f"Smoke failed: empty output; artifact: {path_out}", err=True)
            raise SystemExit(1)
    except Exception as e:
        typer.echo(f"Smoke error: {e}", err=True)
        raise SystemExit(1)


@app.command()
def stream(
    prompt: str = typer.Option("Write one short line.", help="Prompt to stream"),
    model: str = typer.Option(_resolve_default_model(), help="Model (defaults to env)"),
    timeout: int = typer.Option(20, help="Request timeout seconds"),
):
    """Stream is not supported via the simple helper; run a non-stream JSON check instead."""
    try:
        try:
            load_dotenv(find_dotenv(usecwd=True))
        except Exception:
            load_dotenv()
        _ensure_src_path()
        from scillm import completion  # type: ignore
        if not model:
            model = os.getenv("CHUTES_TEXT_MODEL", "")
        res = completion(
            model=model,
            custom_llm_provider="openai_like",
            api_base=os.environ.get("CHUTES_API_BASE",""),
            api_key=None,
            extra_headers={"x-api-key": os.environ.get("CHUTES_API_KEY","")},
            messages=[{"role":"user","content":prompt}],
            timeout=timeout,
        )
        content = res.get("choices", [{}])[0].get("message", {}).get("content", "")
        text = content if isinstance(content, str) else json.dumps(content)
        ok = bool(text.strip())
        lines = [f"MODEL={model}", f"PROMPT={prompt}", f"STREAM_OUTPUT={text[:200]}...", f"OK={ok}"]
        path_out = _write_artifact(lines)
        if ok:
            typer.echo(f"OK: stream returned text; artifact: {path_out}")
        else:
            typer.echo(f"Smoke failed: empty stream output; artifact: {path_out}", err=True)
            raise SystemExit(1)
    except Exception as e:
        typer.echo(f"Smoke error: {e}", err=True)
        raise SystemExit(1)


@app.command()
def batch(
    model: str = typer.Option(_resolve_default_model(), help="Model (defaults to env)"),
    timeout: int = typer.Option(20, help="Request timeout seconds"),
):
    """Run two prompts (batch) via SciLLM helper (sequential) and save artifact."""
    try:
        try:
            load_dotenv(find_dotenv(usecwd=True))
        except Exception:
            load_dotenv()
        _ensure_src_path()
        from scillm import completion  # type: ignore

        prompts = ["What is 2+2?", "Capital of France?"]
        if not model:
            model = os.getenv("CHUTES_TEXT_MODEL", "")
        outs: list[str] = []
        for p in prompts:
            r = completion(
                model=model,
                custom_llm_provider="openai_like",
                api_base=os.environ.get("CHUTES_API_BASE",""),
                api_key=None,
                extra_headers={"x-api-key": os.environ.get("CHUTES_API_KEY","")},
                messages=[{"role":"user","content":p}],
                timeout=timeout,
            )
            c = r.get("choices", [{}])[0].get("message", {}).get("content", "")
            outs.append(c if isinstance(c, str) else json.dumps(c))
        lines = [f"MODEL={model}", f"P0={prompts[0]}", f"R0={outs[0][:120] if outs else ''}", f"P1={prompts[1]}", f"R1={outs[1][:120] if len(outs)>1 else ''}"]
        path_out = _write_artifact(lines)
        ok = len(outs) == 2 and all(isinstance(x, str) and x.strip() for x in outs)
        if ok:
            typer.echo(f"OK: batch returned two results; artifact: {path_out}")
        else:
            typer.echo(f"Smoke failed: batch results invalid; artifact: {path_out}", err=True)
            raise SystemExit(1)
    except Exception as e:
        typer.echo(f"Smoke error: {e}", err=True)
        raise SystemExit(1)


if __name__ == "__main__":
    app()
