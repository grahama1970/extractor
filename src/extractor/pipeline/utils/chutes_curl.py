#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _artifacts_dir() -> Path:
    p = Path("scripts/artifacts")
    p.mkdir(parents=True, exist_ok=True)
    return p


def _write(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(obj, (dict, list)):
        path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        path.write_text(str(obj), encoding="utf-8")


def chutes_curl_chat_json(
    *,
    messages: List[Dict[str, Any]],
    model: Optional[str] = None,
    response_format: Optional[Dict[str, Any]] = None,
    temperature: float = 0,
    max_tokens: int = 512,
    tag: str = "curl_chat",
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """Post an OpenAI-compatible /chat/completions via curl (Bearer only).

    Returns (parsed_response, meta). parsed_response is the parsed JSON response
    (dict) or None on failure. meta contains artifact paths and status.
    """
    base = os.environ.get("CHUTES_API_BASE", "").rstrip("/")
    api_key = os.environ.get("CHUTES_API_KEY", "")
    if not base or not api_key:
        return None, {"error": "missing_env", "CHUTES_API_BASE": bool(base), "CHUTES_API_KEY": bool(api_key)}

    model = model or os.environ.get("CHUTES_TEXT_MODEL") or ""
    ts = time.strftime("%Y%m%d_%H%M%S")
    art = _artifacts_dir()
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format:
        payload["response_format"] = response_format

    payload_path = art / f"{tag}.{ts}.payload.json"
    resp_path = art / f"{tag}.{ts}.response.json"
    hdr_path = art / f"{tag}.{ts}.headers.txt"
    _write(payload_path, payload)

    cmd = [
        "curl",
        "-sS",
        "-D",
        str(hdr_path),
        "-H",
        "Content-Type: application/json",
        "-H",
        f"Authorization: Bearer {api_key}",
        "-o",
        str(resp_path),
        f"{base}/chat/completions",
        "--data",
        f"@{payload_path}",
    ]
    try:
        r = subprocess.run(cmd, check=False, capture_output=True, text=True)
    except Exception as e:
        return None, {"error": "subprocess", "exc": str(e)}

    meta = {
        "returncode": r.returncode,
        "stdout": r.stdout.strip(),
        "stderr": r.stderr.strip(),
        "payload": str(payload_path),
        "response": str(resp_path),
        "headers": str(hdr_path),
    }
    try:
        data = json.loads(resp_path.read_text(encoding="utf-8"))
    except Exception:
        return None, {**meta, "error": "json_load_failed"}
    return data, meta

