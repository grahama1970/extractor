from __future__ import annotations

import os
from typing import Any, Dict, List

from scillm import Router
import json
from subprocess import run, PIPE

_TEXT_ROUTER: Router | None = None
_VLM_ROUTER: Router | None = None


def _auth_params() -> Dict[str, Any]:
    """Return litellm auth params for Chutes chat/completions.

    Enforce Bearer-only for chat on this tenant, regardless of CHUTES_AUTH_STYLE.
    If CHUTES_AUTH_STYLE is set and not 'bearer', print a one-line warning and
    proceed with Bearer headers.
    """
    style = (os.environ.get("CHUTES_AUTH_STYLE") or "bearer").strip().lower()
    base = os.environ.get("CHUTES_API_BASE", "")
    key = os.environ.get("CHUTES_API_KEY", "")
    if style and style != "bearer":
        try:
            print(f"[scillm_router] WARNING: CHUTES_AUTH_STYLE='{style}' ignored for chat; using Bearer.")
        except Exception:
            pass
    return {"api_base": base, "api_key": None, "extra_headers": {"Authorization": f"Bearer {key}"}}


def _model_entry(model: str) -> Dict[str, Any]:
    lp = {"custom_llm_provider": "openai_like", "model": model}
    lp.update(_auth_params())
    return {"model_name": "chutes/text", "litellm_params": lp}


def _model_entry_vlm(model: str) -> Dict[str, Any]:
    lp = {"custom_llm_provider": "openai_like", "model": model}
    lp.update(_auth_params())
    return {"model_name": "chutes/vlm", "litellm_params": lp}


def get_text_router() -> Router:
    global _TEXT_ROUTER
    if _TEXT_ROUTER is not None:
        return _TEXT_ROUTER
    # Optional auto-discovery from /v1/models when SCILLM_AUTO_ROUTER=1
    auto = os.getenv("SCILLM_AUTO_ROUTER", "0").lower() in {"1","true","yes","y"}
    primary = os.environ.get("CHUTES_TEXT_MODEL", "")
    # Alternates supported: ALT1/ALT2 if provided; discovery remains disabled by default
    alt1 = os.environ.get("CHUTES_TEXT_MODEL_ALT1", "").strip()
    alt2 = os.environ.get("CHUTES_TEXT_MODEL_ALT2", "").strip()
    if auto:
        raise RuntimeError("SCILLM_AUTO_ROUTER is disabled by default. Provide CHUTES_TEXT_MODEL (and optional ALT1/ALT2).")
    if False:  # discovery branch intentionally disabled
        base = os.getenv("CHUTES_API_BASE", "").rstrip("/")
        key = os.getenv("CHUTES_API_KEY", "")
        if base and key:
            r = run([
                "curl","-sS","--max-time","3","-H",f"Authorization: Bearer {key}",f"{base}/models"
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
        if alt1:
            model_list.append(_model_entry(alt1))
        if alt2:
            model_list.append(_model_entry(alt2))
    else:
        raise RuntimeError("CHUTES_TEXT_MODEL is required (alternates optional).")
    if not model_list and not auto:
        raise RuntimeError("No CHUTES_TEXT_MODEL pins provided and SCILLM_AUTO_ROUTER is disabled. Set CHUTES_TEXT_MODEL or enable SCILLM_AUTO_ROUTER=1 for dev triage.")
    _TEXT_ROUTER = Router(
        model_list=model_list or [{}],
        num_retries=0,
        default_litellm_params={"timeout": 20},
    )
    return _TEXT_ROUTER


def get_vlm_router() -> Router:
    global _VLM_ROUTER
    if _VLM_ROUTER is not None:
        return _VLM_ROUTER
    auto = os.getenv("SCILLM_AUTO_ROUTER", "0").lower() in {"1","true","yes","y"}
    primary = os.environ.get("CHUTES_VLM_MODEL", "")
    alt1 = os.environ.get("CHUTES_VLM_MODEL_ALT1", "").strip()
    alt2 = os.environ.get("CHUTES_VLM_MODEL_ALT2", "").strip()
    if auto:
        raise RuntimeError("SCILLM_AUTO_ROUTER is disabled by default. Provide CHUTES_VLM_MODEL (and optional ALT1/ALT2).")
    if False:
        base = os.getenv("CHUTES_API_BASE", "").rstrip("/")
        key = os.getenv("CHUTES_API_KEY", "")
        if base and key:
            r = run([
                "curl","-sS","--max-time","3","-H",f"Authorization: Bearer {key}",f"{base}/models"
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
        if alt1:
            model_list.append(_model_entry_vlm(alt1))
        if alt2:
            model_list.append(_model_entry_vlm(alt2))
    else:
        raise RuntimeError("CHUTES_VLM_MODEL is required (alternates optional).")
    if not model_list and not auto:
        raise RuntimeError("No CHUTES_VLM_MODEL pins provided and SCILLM_AUTO_ROUTER is disabled. Set CHUTES_VLM_MODEL or enable SCILLM_AUTO_ROUTER=1 for dev triage.")
    _VLM_ROUTER = Router(
        model_list=model_list or [{}],
        num_retries=0,
        default_litellm_params={"timeout": 20},
    )
    return _VLM_ROUTER


def close_text_router() -> None:
    global _TEXT_ROUTER
    try:
        if _TEXT_ROUTER is not None:
            _TEXT_ROUTER.close()
    finally:
        _TEXT_ROUTER = None


def close_vlm_router() -> None:
    global _VLM_ROUTER
    try:
        if _VLM_ROUTER is not None:
            _VLM_ROUTER.close()
    finally:
        _VLM_ROUTER = None


def close_all_routers() -> None:
    close_text_router()
    close_vlm_router()
