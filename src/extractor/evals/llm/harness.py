from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv, find_dotenv
from scillm import acompletion as sc_acompletion  # type: ignore

from scillm.extras.json_utils import clean_json_string
from extractor.pipeline.utils.model_params import (
    build_chat_messages,
)


load_dotenv(find_dotenv(), override=False)


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
    """SciLLM-only eval call via acompletion. Falls back once without image if needed."""

    def _build_messages(with_image: bool) -> Dict[str, Any]:
        return build_chat_messages(system_text, user_text, image_url if with_image else None)

    # First attempt: with image if provided
    messages = _build_messages(with_image=bool(image_url))
    resp = await sc_acompletion(
        model=model,
        api_base=os.getenv("CHUTES_API_BASE"),
        api_key=os.getenv("CHUTES_API_KEY"),
        custom_llm_provider="openai",
        messages=messages,
        timeout=timeout,
        temperature=0,
        top_p=1,
    )
    content = (resp.get("choices") or [{}])[0].get("message", {}).get("content") or ""

    # If empty and we tried image, retry without image
    if not (isinstance(content, str) and content.strip()) and image_url:
        messages2 = _build_messages(with_image=False)
        resp2 = await sc_acompletion(
            model=model,
            api_base=os.getenv("CHUTES_API_BASE"),
            api_key=os.getenv("CHUTES_API_KEY"),
            custom_llm_provider="openai",
            messages=messages2,
            timeout=timeout,
            temperature=0,
            top_p=1,
        )
        content = (resp2.get("choices") or [{}])[0].get("message", {}).get("content") or ""

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
