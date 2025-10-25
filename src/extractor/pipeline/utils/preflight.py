#!/usr/bin/env python3
from __future__ import annotations

import os
from typing import Tuple
import urllib.request
import urllib.error


def scillm_quick_check(timeout: float = 3.0) -> Tuple[bool, str]:
    """Fast sanity check for scillm/Chutes availability.

    - Verifies CHUTES_API_BASE and CHUTES_API_KEY are set
    - Makes a cheap GET to /v1/models (or /models if base already endswith /v1) with x-api-key
    - Returns (ok, reason)
    """
    base = (os.getenv("CHUTES_API_BASE") or "").rstrip("/")
    key = os.getenv("CHUTES_API_KEY") or ""
    if not base or not key:
        return False, "CHUTES_API_BASE/CHUTES_API_KEY not set"
    try:
        # Normalize to .../v1/models
        if base.endswith("/v1"):
            url = f"{base}/models"
        else:
            url = f"{base}/v1/models"
        req = urllib.request.Request(url, headers={"x-api-key": key})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code = getattr(resp, "status", None) or resp.getcode()
            if code == 200:
                return True, "ok"
            return False, f"HTTP {code} from /models"
    except urllib.error.HTTPError as e:  # pragma: no cover
        return False, f"http error: {e.code}"
    except Exception as e:  # pragma: no cover
        return False, f"http error: {e}"


def require_scillm_env() -> Tuple[bool, str]:
    """Ensure SciLLM/Chutes env is set and sanitize conflicting OPENAI_*.

    Returns (ok, reason). When ok is False, reason explains the missing variable.
    Side‑effect: unsets OPENAI_API_KEY/OPENAI_BASE_URL to avoid Bearer path misrouting.
    """
    base = (os.getenv("CHUTES_API_BASE") or "").strip()
    key = (os.getenv("CHUTES_API_KEY") or "").strip()
    text_model = (os.getenv("CHUTES_TEXT_MODEL") or "").strip()
    if not base:
        return False, "CHUTES_API_BASE not set"
    if not key:
        return False, "CHUTES_API_KEY not set"
    if not text_model:
        return False, "CHUTES_TEXT_MODEL not set"
    # Ignore OPENAI_* to prevent accidental Bearer path usage
    for var in ("OPENAI_API_KEY", "OPENAI_BASE_URL"):
        if os.getenv(var):
            try:
                os.environ.pop(var, None)
            except Exception:
                pass
    return True, "ok"


def forbid_input_writes(path_str: str) -> Tuple[bool, str]:
    """Reject writes under data/input/ tree. Return (ok, reason)."""
    try:
        p = os.path.abspath(path_str)
        root = os.path.abspath("data/input")
        if os.path.commonpath([p, root]) == root:
            return False, f"Refusing to write under data/input/: {p}"
    except Exception:
        pass
    return True, "ok"


def camelot_quick_check() -> Tuple[bool, str]:
    try:
        import camelot  # type: ignore

        _ = camelot.__version__
        return True, "ok"
    except Exception as e:  # pragma: no cover
        return False, f"camelot import error: {e}"


def litellm_quick_check() -> Tuple[bool, str]:
    try:
        try:
            import litellm  # type: ignore
        except Exception:
            return True

        _ = getattr(litellm, "completion", None)
        return True, "ok"
    except Exception as e:  # pragma: no cover
        return False, f"litellm import error: {e}"
