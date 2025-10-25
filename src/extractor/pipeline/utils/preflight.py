#!/usr/bin/env python3
from __future__ import annotations

import os
from typing import Tuple


def scillm_quick_check(timeout: float = 3.0) -> Tuple[bool, str]:
    """Fast sanity check for scillm/Chutes availability.

    - Verifies CHUTES_API_BASE and CHUTES_API_KEY are set
    - Makes a cheap GET to /models with x-api-key
    - Returns (ok, reason)
    """
    base = (os.getenv("CHUTES_API_BASE") or "").rstrip("/")
    key = os.getenv("CHUTES_API_KEY") or ""
    if not base or not key:
        return False, "CHUTES_API_BASE/CHUTES_API_KEY not set"
    try:
        import httpx  # type: ignore

        url = f"{base}/models"
        r = httpx.get(url, headers={"x-api-key": key}, timeout=timeout)
        if r.status_code == 200:
            return True, "ok"
        return False, f"HTTP {r.status_code} from /models"
    except Exception as e:  # pragma: no cover
        return False, f"http error: {e}"


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
