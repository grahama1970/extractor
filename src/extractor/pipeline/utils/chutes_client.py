#!/usr/bin/env python3
"""
Minimal OpenAI-compatible HTTP client for Chutes-style gateways that require
either `x-api-key: <key>` or `Authorization: <key>` (no 'Bearer ').

Use this when OpenAI SDK / litellm paths fail due to 'Authorization: Bearer' 401s.
"""
from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional
import time
import random
from .metrics_logger import log_metric


class ChutesAuthError(RuntimeError):
    pass


def _headers(api_key: str, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    h = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        # Current gateway behavior: Chat Completions accepts Authorization (Bearer optional).
        "Authorization": api_key,
    }
    if extra:
        h.update(extra)
    return h


def chat_completion(
    *,
    api_base: str,
    api_key: str,
    model: str,
    messages: List[Dict[str, Any]],
    response_format: Optional[Dict[str, Any]] = None,
    stop: Optional[List[str]] = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    timeout: float = 30.0,
) -> Dict[str, Any]:
    """POST /v1/chat/completions to an OpenAI-compatible gateway with x-api-key auth."""
    base = api_base.rstrip("/")
    if not base.endswith("/v1"):
        # Accept both .../v1 and raw base; append /v1 for canonical endpoints
        base = base + "/v1"
    url = f"{base}/chat/completions"
    # Normalize model id (e.g., strip 'openai/' vendor prefix when gateway expects raw id)
    mid = (model or "").strip()
    if mid.lower().startswith("openai/"):
        mid = mid.split("/", 1)[1]
    body: Dict[str, Any] = {"model": mid, "messages": messages}
    if response_format is not None:
        body["response_format"] = response_format
    if stop is not None:
        body["stop"] = stop
    if max_tokens is not None:
        body["max_tokens"] = max_tokens
    if temperature is not None:
        body["temperature"] = temperature

    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=_headers(api_key))
    tries = 0
    # Up to 3 attempts total (initial + 2 retries)
    backoffs = [1.0, 2.0]  # default fallbacks if Retry-After is missing
    while True:
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read().decode("utf-8")
                if tries > 0:
                    # Successful after retry(s)
                    log_metric(
                        "scillm_chutes",
                        {
                            "event": "rate_limit_recovered",
                            "retries": tries,
                            "wait_strategy": "retry-after+jitter",
                        },
                    )
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            payload = e.read().decode("utf-8", errors="ignore") if hasattr(e, "read") else ""
            if e.code == 401:
                raise ChutesAuthError(f"401 Unauthorized from {url}: {payload}")
            if e.code == 429:
                # Honor Retry-After when present; otherwise use expanding fallback with jitter
                ra = None
                try:
                    ra = float(e.headers.get("Retry-After", "").strip()) if getattr(e, "headers", None) else None
                except Exception:
                    ra = None
                if tries < len(backoffs) + 1:  # allow up to 2 retries after the first attempt
                    wait = ra if ra and ra > 0 else backoffs[min(tries, len(backoffs)-1)]
                    # Jitter to avoid thundering herds
                    jitter = random.uniform(0, wait * 0.25)
                    wait = wait + jitter
                    log_metric(
                        "scillm_chutes",
                        {
                            "event": "rate_limit_backoff",
                            "retry_after_s": ra if ra else None,
                            "planned_wait_s": round(wait, 3),
                            "attempt": tries + 1,
                        },
                    )
                    time.sleep(wait)
                    tries += 1
                    continue
            # Out of retries or non-429 error
            if e.code == 429:
                log_metric("scillm_chutes", {"event": "rate_limit_exhausted"})
            raise RuntimeError(f"HTTP {e.code} from {url}: {payload}")
