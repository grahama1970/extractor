from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv, find_dotenv
import litellm as _litellm
from extractor.pipeline.utils.litellm_call import litellm_call

from scillm.extras.json_utils import clean_json_string
from extractor.pipeline.utils.model_params import (
    build_chat_messages,
    build_chat_extras,
)


load_dotenv(find_dotenv(), override=False)
_litellm.drop_params = True  # tolerate provider-specific unsupported params
# Bridge env var naming: accept OPEN_ROUTER_API_KEY as alias for OPENROUTER_API_KEY
if os.getenv("OPEN_ROUTER_API_KEY") and not os.getenv("OPENROUTER_API_KEY"):
    os.environ["OPENROUTER_API_KEY"] = os.getenv("OPEN_ROUTER_API_KEY")  # type: ignore


@dataclass
class CallResult:
    content: str
    parsed: Optional[Dict[str, Any]]
    usage: Dict[str, Any]
    provider_cost_reported: Optional[float]
    raw_object: Any


async def chat_call(
    model: str, system_text: str, user_text: str, image_url: Optional[str], *, timeout: int = 60
) -> CallResult:
    """Use the project's litellm_call for consistency. It injects token/cost metadata into JSON when possible.
    Falls back to retrying without image once if provider rejects image inputs."""

    def _build_params(with_image: bool) -> Dict[str, Any]:
        messages = build_chat_messages(system_text, user_text, image_url if with_image else None)
        extras = build_chat_extras(model)
        params = {
            "model": model,
            "messages": messages,
            "timeout": timeout,
            "temperature": 0,
            "top_p": 1,
            **extras,
        }
        # OpenRouter support
        mlow = (model or "").lower()
        if mlow.startswith("openrouter/"):
            api_key = os.getenv("OPENROUTER_API_KEY")
            if api_key:
                params["api_key"] = api_key
            params["api_base"] = os.getenv("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1")
        return params

    # First attempt: with image if provided
    params = _build_params(with_image=bool(image_url))
    results = await litellm_call([params], wrap_json=False, concurrency=1, desc="LLM Eval")
    content = results[0] if results else ""

    # If empty and we tried image, retry without image
    if not (isinstance(content, str) and content.strip()) and image_url:
        params2 = _build_params(with_image=False)
        results2 = await litellm_call(
            [params2], wrap_json=False, concurrency=1, desc="LLM Eval (no image)"
        )
        content = results2[0] if results2 else ""

    # Parse and extract metadata if present
    parsed: Optional[Dict[str, Any]] = None
    usage: Dict[str, Any] = {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None}
    provider_cost = None
    if isinstance(content, str) and content.strip():
        try:
            parsed_any = clean_json_string(content, return_dict=True)
            if isinstance(parsed_any, dict):
                parsed = parsed_any
                md = parsed.get("metadata") or parsed.get("_metadata")
                if isinstance(md, dict):
                    tu = md.get("token_usage") or {}
                    if isinstance(tu, dict):
                        usage = {
                            "prompt_tokens": tu.get("prompt_tokens"),
                            "completion_tokens": tu.get("completion_tokens"),
                            "total_tokens": tu.get("total_tokens"),
                        }
                    if "response_cost" in md:
                        provider_cost = md.get("response_cost")
        except Exception:
            parsed = None

    return CallResult(
        content=content or "",
        parsed=parsed,
        usage=usage,
        provider_cost_reported=provider_cost,
        raw_object=None,
    )


def calc_cost(
    model: str,
    usage: Dict[str, Any],
    provider_cost_reported: Optional[float],
    pricing: Dict[str, Dict[str, float]],
) -> Optional[float]:
    if isinstance(provider_cost_reported, (int, float)):
        return float(provider_cost_reported)
    rates = pricing.get(model) or {}
    in_rate = float(rates.get("input_per_1k_usd") or 0)
    out_rate = float(rates.get("output_per_1k_usd") or 0)
    pt = float(usage.get("prompt_tokens") or 0)
    ct = float(usage.get("completion_tokens") or 0)
    if not (in_rate or out_rate):
        return None
    return (pt / 1000.0) * in_rate + (ct / 1000.0) * out_rate


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False))


def load_yaml(path: Path) -> Any:
    import yaml  # type: ignore

    return yaml.safe_load(path.read_text())


def now_ts() -> str:
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def build_manifest(dataset_registry: Path, models_file: Path) -> Dict[str, Any]:
    # Best-effort git SHA
    sha = None
    try:
        import subprocess

        sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        sha = None
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "git_sha": sha,
        "dataset_registry": str(dataset_registry),
        "models_file": str(models_file),
        "env": {
            k: os.environ.get(k)
            for k in ["OPENAI_API_KEY", "GOOGLE_API_KEY", "MOONSHOT_API_KEY"]
            if os.environ.get(k)
        },
    }
