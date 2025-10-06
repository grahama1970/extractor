#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.12.3",
#   "rich>=13.7.1",
#   "litellm>=1.51.0",
#   "scillm @ file:///home/graham/workspace/experiments/litellm",
# ]
# ///
"""
Chutes.ai SOTA model evaluation (text-first, optional VLM).

Uses OpenAI-compatible providers via litellm with your CHUTES_* env vars.
Reads model aliases from LITELLM_* envs and normalizes to remote model ids.

Outputs metrics JSON and a compact table under scripts/artifacts/evals/.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import argparse
import asyncio
from rich.console import Console
from rich.table import Table
from urllib import request as urlrequest
from urllib.error import URLError, HTTPError

from extractor.pipeline.utils.model_env import (
    resolve_text_small,
    resolve_text_med,
    resolve_text_large,
    resolve_default,
)
import sys
from types import ModuleType

def _import_scillm_client() -> ModuleType:
    """Import the SciLLM client (module name: litellm), honoring SCILLM_DEV_PATH.
    If SCILLM_DEV_PATH or the default local path exists, prepend it to sys.path
    so the local SciLLM checkout wins over any PyPI litellm.
    """
    dev_path = os.getenv("SCILLM_DEV_PATH") or \
        "/home/graham/workspace/experiments/litellm"
    try:
        if dev_path and os.path.isdir(dev_path) and dev_path not in sys.path:
            sys.path.insert(0, dev_path)
    except Exception:
        pass
    import importlib
    try:
        return importlib.import_module("litellm")
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"SciLLM client import failed: {exc}")


console = Console()


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    return os.getenv(name, default)


def _remote_from_alias(alias: str) -> str:
    """Keep alias as-is for SciLLM; providers are resolved by env.
    Maintained for display only.
    """
    return alias


def _collect_default_models() -> Dict[str, str]:
    """Return label->alias using project resolvers (SCILLM_* preferred)."""
    envs = {
        "default_text": resolve_default(None),
        "small_text": resolve_text_small(None),
        "med_text": resolve_text_med(None),
        "large_text": resolve_text_large(None),
    }
    return {k: v for k, v in envs.items() if v and str(v).strip()}


def _discover_ollama_models(api_base: Optional[str]) -> List[str]:
    """Return a list of 'ollama/<tag>' aliases discovered on a local Ollama server.
    Gracefully returns [] if server is not reachable.
    """
    base = (api_base or os.getenv("OLLAMA_API_BASE") or "http://127.0.0.1:11434").rstrip("/")
    url = f"{base}/api/tags"
    try:
        with urlrequest.urlopen(url, timeout=1.5) as resp:  # type: ignore[arg-type]
            data = json.loads(resp.read().decode("utf-8"))
        models = data.get("models") or []
        tags = []
        for m in models:
            tag = m.get("name") or m.get("model")
            if tag:
                tags.append(str(tag))
        return [f"ollama/{t}" for t in tags]
    except (URLError, HTTPError, TimeoutError, json.JSONDecodeError, Exception):
        return []


def _filter_student_candidates(aliases: List[str]) -> List[str]:
    """Prefer small/medium 'student' sizes if present; otherwise pass through.
    Keeps common candidates: qwen2.5 3B/7B, llama3.2 3B, mistral 7B, phi4 14b, granite3.3 8b, glm4 9b.
    """
    keep_substrings = [
        "qwen2.5:3b",
        "qwen2.5:7b",
        "llama3.2:3b",
        "mistral:7b",
        "phi4:14b",
        "granite3.3:8b",
        "glm4:9b",
        "glm4:latest",
    ]
    out: List[str] = []
    for a in aliases:
        low = a.lower()
        if any(s in low for s in keep_substrings):
            out.append(a)
    # Fallback to original if nothing matched
    return out or aliases


@dataclass
class EvalItem:
    label: str
    alias: str
    remote: str
    ok: bool
    status: str
    latency_ms: int
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None


async def _call_json_batch_via_router(
    aliases: List[str],
    prompt: str,
    *,
    timeout: int = 45,
    max_concurrency: int = 8,
) -> List[Dict[str, Any]]:
    """Use SciLLM Router.parallel_acompletions for a batch of model aliases.
    Returns entries aligned with aliases: {ok, data?, usage?, error?}.
    """
    litellm = _import_scillm_client()
    Router = getattr(litellm, "Router", None)
    if Router is None:
        raise RuntimeError("SciLLM Router not exported; please update SciLLM client")
    reqs = []
    for model_alias in aliases:
        is_ollama = model_alias.startswith("ollama/")
        provider = "ollama" if is_ollama else (os.getenv("CHUTES_PROVIDER") or "openai").strip() or "openai"
        api_base = (
            os.getenv("OLLAMA_API_BASE", "http://127.0.0.1:11434") if is_ollama
            else os.getenv("CHUTES_API_BASE", "https://llm.chutes.ai/v1")
        )
        api_key = None if is_ollama else os.getenv("CHUTES_API_KEY")
        reqs.append({
            "model": model_alias,
            "messages": [
                {"role": "system", "content": "You are a concise assistant."},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "api_key": api_key,
            "api_base": api_base,
            "custom_llm_provider": provider,
            "timeout": timeout,
        })
    router = Router()
    resps = await router.parallel_acompletions(reqs, max_concurrency=max_concurrency)
    out: List[Dict[str, Any]] = []
    for r in resps:
        try:
            content = r["choices"][0]["message"]["content"]
            data = json.loads(content)
            usage = r.get("usage", {}) if isinstance(r, dict) else {}
            out.append({"ok": bool(data.get("ok") is True), "data": data, "usage": usage})
        except Exception as exc:
            out.append({"ok": False, "error": str(exc), "usage": {}})
    return out

async def _call_json_scillm_direct(model_alias: str, prompt: str, timeout: int = 45) -> Dict[str, Any]:
    """Call SciLLM (litellm module) directly and return parsed JSON."""
    litellm = _import_scillm_client()
    is_ollama = model_alias.startswith("ollama/")
    # For Chutes/OpenAI-compatible routes, SciLLM accepts the full alias
    # (e.g., openai/zai-org/GLM-4.5-Air). For Ollama, use the tag only.
    model_remote = (
        model_alias.split("/", 1)[1] if "/" in model_alias else model_alias
    ) if not is_ollama else (model_alias.split("/", 1)[1] if "/" in model_alias else model_alias)
    provider = "ollama" if is_ollama else (os.getenv("CHUTES_PROVIDER") or "openai").strip() or "openai"
    api_base = (
        os.getenv("OLLAMA_API_BASE", "http://127.0.0.1:11434") if is_ollama
        else os.getenv("CHUTES_API_BASE", "https://llm.chutes.ai/v1")
    )
    api_key = None if is_ollama else os.getenv("CHUTES_API_KEY")
    # Note: SciLLM expects api_key via keyword api_key
    # Some clients still read OPENAI_API_KEY from env; ensure it's present when using provider 'openai'
    if provider == "openai" and api_key:
        os.environ.setdefault("OPENAI_API_KEY", api_key)
    # Use sync completion path — minimal surface, widely compatible
    loop = asyncio.get_event_loop()
    resp = await loop.run_in_executor(
        None,
        lambda: litellm.completion(
            model=model_remote,
            messages=[
                {"role": "system", "content": "You are a concise assistant."},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            timeout=timeout,
            api_key=api_key,
            base_url=api_base,
            custom_llm_provider=provider,
        ),
    )
    try:
        content = resp["choices"][0]["message"]["content"]
    except Exception:
        content = str(resp)
    data = json.loads(content)
    usage = resp.get("usage", {}) if isinstance(resp, dict) else {}
    return {"data": data, "usage": usage}


async def _acompletion_once(litellm_mod, model_remote: str, prompt: str, provider: str, api_base: str | None, api_key: str | None, timeout: int):
    if provider == "openai" and api_key:
        os.environ.setdefault("OPENAI_API_KEY", api_key)
    return await litellm_mod.acompletion(
        model=model_remote,
        messages=[
            {"role": "system", "content": "You are a concise assistant."},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        timeout=timeout,
        api_key=api_key,
        base_url=api_base,
        custom_llm_provider=provider,
    )



def _call_json_litellm(model_alias: str, prompt: str, timeout: int = 45) -> Dict[str, Any]:
    if litellm is None:
        raise RuntimeError("litellm not available for fallback")
    is_ollama = model_alias.startswith("ollama/")
    model_remote = model_alias.split("/", 1)[1] if "/" in model_alias else model_alias
    provider = "ollama" if is_ollama else (os.getenv("CHUTES_PROVIDER") or "openai").strip() or "openai"
    api_base = (
        os.getenv("OLLAMA_API_BASE", "http://127.0.0.1:11434") if is_ollama
        else os.getenv("CHUTES_API_BASE", "https://llm.chutes.ai/v1")
    )
    api_key = None if is_ollama else os.getenv("CHUTES_API_KEY")
    resp = litellm.completion(
        model=model_remote,
        messages=[
            {"role": "system", "content": "You are a concise assistant."},
            {"role": "user", "content": prompt},
        ],
        api_key=api_key,
        api_base=api_base,
        custom_llm_provider=provider,
        timeout=timeout,
        response_format={"type": "json_object"},
    )
    try:
        content = resp["choices"][0]["message"]["content"]
    except Exception:
        content = str(resp)
    data = json.loads(content)
    usage = resp.get("usage", {}) if isinstance(resp, dict) else {}
    return {"data": data, "usage": usage}


def _ensure_artifacts_dir() -> Path:
    out_dir = Path("scripts/artifacts/evals")
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Chutes model quick eval")
    parser.add_argument(
        "--model",
        dest="models",
        action="append",
        help=(
            "Explicit model alias (e.g., openai/deepseek-ai/DeepSeek-R1). "
            "Repeat for multiple models. If omitted, uses LITELLM_* env defaults."
        ),
    )
    parser.add_argument(
        "--full",
        dest="full",
        action="store_true",
        help="Run a tiny extra reasoning probe after sanity JSON (slower)",
    )
    parser.add_argument(
        "--no-record",
        dest="record",
        action="store_false",
        help="Do not write artifacts (JSON/TSV)",
    )
    parser.add_argument(
        "--include-ollama",
        action="store_true",
        help="Also evaluate local Ollama models (via /api/tags).",
    )
    parser.add_argument(
        "--ollama-base",
        default=os.getenv("OLLAMA_API_BASE", "http://127.0.0.1:11434"),
        help="Ollama API base URL (default: http://127.0.0.1:11434)",
    )
    parser.add_argument(
        "--all-ollama",
        action="store_true",
        help="Include all discovered Ollama models instead of a curated student subset.",
    )
    args = parser.parse_args(argv)
    """Evaluate a small set of Chutes models for quick health/latency."""
    # Build model list
    model_map = _collect_default_models()
    if args.models:
        model_map = {f"m{i+1}": m for i, m in enumerate(args.models)}

    # Optionally include local Ollama tags
    if args.include_ollama:
        ollama_aliases = _discover_ollama_models(args.ollama_base)
        if ollama_aliases:
            if not args.all_ollama:
                ollama_aliases = _filter_student_candidates(ollama_aliases)
            # Append to the model_map with stable labels
            start_index = len(model_map)
            for i, alias in enumerate(ollama_aliases, start=1):
                model_map[f"ollama_{start_index+i}"] = alias

    if not model_map:
        console.print("No models provided and no LITELLM_* defaults found.")
        return 2

    console.print(f"Evaluating {len(model_map)} model(s) via SciLLM Router…")
    evals: List[EvalItem] = []
    labels = list(model_map.keys())
    aliases = [model_map[k] for k in labels]
    t0 = time.monotonic()
    results = asyncio.run(
        _call_json_batch_via_router(
            aliases,
            prompt='Return only {"ok": true} as JSON.',
        )
    )
    elapsed = int((time.monotonic() - t0) * 1000)
    for i, label in enumerate(labels):
        alias = aliases[i]
        remote = _remote_from_alias(alias)
        item = results[i] if i < len(results) else {"ok": False, "error": "missing"}
        ok = bool(item.get("ok"))
        status = "ok" if ok else (f"error: {item.get('error','bad_json')}"[:160])
        usage = item.get("usage") or {}
        evals.append(
            EvalItem(
                label=label,
                alias=alias,
                remote=remote,
                ok=ok,
                status=status,
                latency_ms=elapsed,
                tokens_in=usage.get("prompt_tokens"),
                tokens_out=usage.get("completion_tokens"),
            )
        )

        if args.full and evals[-1].ok:
            # Optional: add one short reasoning probe as JSON
            try:
                _ = asyncio.run(
                    _call_json_batch_via_router(
                        [alias],
                        prompt=(
                            "Solve: If a train leaves at 3pm and travels 60km/h for 90 minutes,"
                            " return JSON {\"distance_km\": <number>} only."
                        ),
                    )
                )
            except Exception:
                pass

    # Present table
    table = Table(title="Chutes Model Eval (quick)")
    for col in ("label", "alias", "remote", "ok", "latency_ms", "status"):
        table.add_column(col)
    for e in evals:
        table.add_row(e.label, e.alias, e.remote, str(e.ok), str(e.latency_ms), e.status)
    console.print(table)

    if args.record:
        out_dir = _ensure_artifacts_dir()
        ts = time.strftime("%Y%m%d_%H%M%S")
        json_path = out_dir / f"chutes_eval_{ts}.json"
        json_path.write_text(json.dumps([asdict(e) for e in evals], indent=2))
        # Lightweight CSV-like table
        tsv_path = out_dir / f"chutes_eval_{ts}.tsv"
        lines = [
            "label	alias	remote	ok	latency_ms	status\n",
        ]
        for e in evals:
            lines.append(
                f"{e.label}\t{e.alias}\t{e.remote}\t{int(e.ok)}\t{e.latency_ms}\t{e.status}\n"
            )
        tsv_path.write_text("".join(lines))
        console.print(f"Saved: {json_path}")
        console.print(f"Saved: {tsv_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
