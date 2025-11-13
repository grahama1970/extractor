from __future__ import annotations

import os
from typing import Any, Dict, List

import asyncio

_TEXT_ROUTER: Router | None = None
_VLM_ROUTER: Router | None = None


def _auth_params() -> Dict[str, Any]:
    """Return litellm auth params for Chutes chat/completions.

    Use api_key only and let SciLLM canonicalize headers for Chutes.
    """
    base = os.environ.get("CHUTES_API_BASE", "")
    key = os.environ.get("CHUTES_API_KEY", "")
    return {"api_base": base, "api_key": key}


def _model_entry(model: str) -> Dict[str, Any]:
    lp = {"custom_llm_provider": "openai_like", "model": model}
    lp.update(_auth_params())
    return {"model_name": "chutes/text", "litellm_params": lp}


def _model_entry_vlm(model: str) -> Dict[str, Any]:
    lp = {"custom_llm_provider": "openai_like", "model": model}
    lp.update(_auth_params())
    return {"model_name": "chutes/vlm", "litellm_params": lp}


def _import_router_cls():
    """Import and return the SciLLM Router class lazily.

    Avoids hard import-time dependency on an external scillm install, which can
    break deterministic/offline tests that never exercise LLM calls.
    """
    try:
        from scillm import Router as _Router  # type: ignore

        return _Router
    except Exception as e:  # pragma: no cover - only used in constrained CI envs
        raise ImportError(
            "SciLLM Router unavailable; ensure sibling 'litellm/scillm' is present or install scillm."
        ) from e


def get_text_router():
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
    # Router now handles transient retries natively; avoid layering retries here
    # to prevent duplicate backoffs. Use Router defaults.
    Router = _import_router_cls()
    _TEXT_ROUTER = Router(
        model_list=model_list or [{}],
    )
    return _TEXT_ROUTER


def get_vlm_router():
    global _VLM_ROUTER
    if _VLM_ROUTER is not None:
        return _VLM_ROUTER
    auto = os.getenv("SCILLM_AUTO_ROUTER", "0").lower() in {"1","true","yes","y"}
    primary = os.environ.get("CHUTES_VLM_MODEL", "")
    alt1 = os.environ.get("CHUTES_VLM_MODEL_ALT1", "").strip()
    alt2 = os.environ.get("CHUTES_VLM_MODEL_ALT2", "").strip()
    if auto:
        raise RuntimeError("SCILLM_AUTO_ROUTER is disabled by default. Provide CHUTES_VLM_MODEL (and optional ALT1/ALT2).")
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
    Router = _import_router_cls()
    _VLM_ROUTER = Router(
        model_list=model_list or [{}],
    )
    return _VLM_ROUTER



def _safe_async_close(obj) -> None:
    try:
        aclose = getattr(obj, "aclose", None)
        if aclose is not None:
            res = aclose()
            if asyncio.iscoroutine(res):
                try:
                    asyncio.run(res)
                except RuntimeError:
                    # Already in a loop; best effort fallback
                    try:
                        loop = asyncio.get_event_loop()
                        loop.create_task(res)  # fire and forget
                    except Exception:
                        pass
    except Exception:
        pass


def close_text_router() -> None:
    global _TEXT_ROUTER
    try:
        if _TEXT_ROUTER is not None:
            # Prefer async close when available to ensure aiohttp connector shuts down
            _safe_async_close(_TEXT_ROUTER)
            try:
                _TEXT_ROUTER.close()
            except Exception:
                pass
    finally:
        _TEXT_ROUTER = None


def close_vlm_router() -> None:
    global _VLM_ROUTER
    try:
        if _VLM_ROUTER is not None:
            _safe_async_close(_VLM_ROUTER)
            try:
                _VLM_ROUTER.close()
            except Exception:
                pass
    finally:
        _VLM_ROUTER = None


def close_all_routers() -> None:
    close_text_router()
    close_vlm_router()
