from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path
from typing import Optional

import requests

from .util_env import load_ls_env


CACHE_FILE = Path("data/labelstudio/.ls_access.json")


def _decode_jwt_exp(token: str) -> Optional[int]:
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return None
        payload = parts[1]
        # add padding
        pad = '=' * (-len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload + pad).decode("utf-8"))
        return int(data.get("exp")) if "exp" in data else None
    except Exception:
        return None


def _save_cache(token: str) -> None:
    exp = _decode_jwt_exp(token) or int(time.time()) + 900
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps({"access": token, "exp": exp}), encoding="utf-8")


def _load_cache() -> Optional[str]:
    if not CACHE_FILE.exists():
        return None
    try:
        data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        if int(data.get("exp", 0)) > int(time.time()) + 30:
            return data.get("access")
    except Exception:
        return None
    return None


def get_access_token(host: str) -> str:
    """Return a valid access token using cached value if possible.

    Order of operations:
      1) Try cached access token from data/labelstudio/.ls_access.json if not expired
      2) Try LS_ACCESS env var, cache it if it looks valid
      3) Use LS_REFRESH env var to refresh (POST /api/token/refresh), then cache
    """
    load_ls_env()
    # cache first
    cached = _load_cache()
    if cached:
        return cached
    # env LS_ACCESS
    env_access = os.environ.get("LS_ACCESS")
    if env_access:
        _save_cache(env_access)
        return env_access
    # refresh using LS_REFRESH
    refresh = os.environ.get("LS_REFRESH")
    if not refresh:
        raise SystemExit("LS_REFRESH not set. Put it in .env.labelstudio to avoid prompts.")
    url = host.rstrip("/") + "/api/token/refresh"
    headers = {"Authorization": f"Token {refresh}", "Content-Type": "application/json"}
    resp = requests.post(url, headers=headers, json={"refresh": refresh}, timeout=30)
    if resp.status_code != 200:
        raise SystemExit(f"Failed to refresh access token: HTTP {resp.status_code} {resp.text}")
    access = resp.json().get("access")
    if not access:
        raise SystemExit("No 'access' in refresh response")
    _save_cache(access)
    return access

