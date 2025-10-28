from __future__ import annotations

import os
from typing import Any, Dict, List

from scillm import Router
import json
import os
from subprocess import run, PIPE

_TEXT_ROUTER: Router | None = None
_VLM_ROUTER: Router | None = None


def _model_entry(model: str) -> Dict[str, Any]:
    return {
        "model_name": "chutes/text",
        "litellm_params": {
            "custom_llm_provider": "openai_like",
            "model": model,
            "api_base": os.environ.get("CHUTES_API_BASE", ""),
            "api_key": os.environ.get("CHUTES_API_KEY", ""),
        },
    }


def _model_entry_vlm(model: str) -> Dict[str, Any]:
    return {
        "model_name": "chutes/vlm",
        "litellm_params": {
            "custom_llm_provider": "openai_like",
            "model": model,
            "api_base": os.environ.get("CHUTES_API_BASE", ""),
            "api_key": os.environ.get("CHUTES_API_KEY", ""),
        },
    }


def get_text_router() -> Router:
    global _TEXT_ROUTER
    if _TEXT_ROUTER is not None:
        return _TEXT_ROUTER
    # Optional auto-discovery from /v1/models when SCILLM_AUTO_ROUTER=1
    auto = os.getenv("SCILLM_AUTO_ROUTER", "").lower() in {"1","true","yes","y"}
    primary = os.environ.get("CHUTES_TEXT_MODEL", "")
    alts: List[str] = [
        os.environ.get("CHUTES_TEXT_MODEL_ALT1", ""),
        os.environ.get("CHUTES_TEXT_MODEL_ALT2", ""),
    ]
    if auto and not (primary and any(alts)):
        base = os.getenv("CHUTES_API_BASE", "").rstrip("/")
        key = os.getenv("CHUTES_API_KEY", "")
        if base and key:
            r = run([
                "curl","-sS","-H",f"Authorization: Bearer {key}",f"{base}/models"
            ], check=False, stdout=PIPE, text=True)
            try:
                data = json.loads(r.stdout)
                ids = [d.get("id","") for d in (data.get("data") or [])]
                # crude filter: exclude obvious VLMs
                text_ids = [i for i in ids if i and not any(tok in i.lower() for tok in ["-vl","/vl","vision"])]
                pref = [
                    "Qwen/Qwen3-235B-A22B-Instruct-2507",
                    "deepseek-ai/DeepSeek-V3.1",
                    "zai-org/GLM-4.6-FP8",
                ]
                ordered = [i for i in pref if i in text_ids] + [i for i in text_ids if i not in pref]
                if not primary and ordered:
                    primary = ordered[0]
                fill = [i for i in ordered if i != primary][:2]
                if not alts[0:1] and fill:
                    alts[0:1] = [fill[0]]
                if len(fill) > 1 and len(alts) < 2:
                    alts = (alts + [fill[1]])[:2]
            except Exception:
                pass
    model_list: List[Dict[str, Any]] = []
    if primary:
        model_list.append(_model_entry(primary))
    for m in alts:
        if m:
            model_list.append(_model_entry(m))
    _TEXT_ROUTER = Router(model_list=model_list or [{}])
    return _TEXT_ROUTER


def get_vlm_router() -> Router:
    global _VLM_ROUTER
    if _VLM_ROUTER is not None:
        return _VLM_ROUTER
    auto = os.getenv("SCILLM_AUTO_ROUTER", "").lower() in {"1","true","yes","y"}
    primary = os.environ.get("CHUTES_VLM_MODEL", "")
    alts: List[str] = [
        os.environ.get("CHUTES_VLM_MODEL_ALT1", ""),
        os.environ.get("CHUTES_VLM_MODEL_ALT2", ""),
    ]
    if auto and not (primary and any(alts)):
        base = os.getenv("CHUTES_API_BASE", "").rstrip("/")
        key = os.getenv("CHUTES_API_KEY", "")
        if base and key:
            r = run([
                "curl","-sS","-H",f"Authorization: Bearer {key}",f"{base}/models"
            ], check=False, stdout=PIPE, text=True)
            try:
                data = json.loads(r.stdout)
                ids = [d.get("id","") for d in (data.get("data") or [])]
                vlm_ids = [i for i in ids if i and any(tok in i.lower() for tok in ["-vl","/vl","vision"])]
                pref = [
                    "Qwen/Qwen3-VL-235B-A22B-Instruct",
                    "Qwen/Qwen2.5-VL-32B-Instruct",
                    "OpenGVLab/InternVL3-78B",
                ]
                ordered = [i for i in pref if i in vlm_ids] + [i for i in vlm_ids if i not in pref]
                if not primary and ordered:
                    primary = ordered[0]
                fill = [i for i in ordered if i != primary][:2]
                if not alts[0:1] and fill:
                    alts[0:1] = [fill[0]]
                if len(fill) > 1 and len(alts) < 2:
                    alts = (alts + [fill[1]])[:2]
            except Exception:
                pass
    model_list: List[Dict[str, Any]] = []
    if primary:
        model_list.append(_model_entry_vlm(primary))
    for m in alts:
        if m:
            model_list.append(_model_entry_vlm(m))
    _VLM_ROUTER = Router(model_list=model_list or [{}])
    return _VLM_ROUTER
