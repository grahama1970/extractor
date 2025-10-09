#!/usr/bin/env python3
from __future__ import annotations

import os, sys

def ensure_env() -> None:
    exe = sys.executable
    if "/.venv/bin/python" not in exe:
        raise SystemExit(
            f"Not using project venv (sys.executable={exe}).\n"
            "Run: source .venv/bin/activate && set -a && [ -f .env ] && source .env && set +a\n"
        )
    if not os.getenv("CHUTES_API_BASE") or not os.getenv("CHUTES_API_KEY"):
        raise SystemExit(
            "Missing CHUTES_API_BASE/CHUTES_API_KEY in environment.\n"
            "Run: source .venv/bin/activate && set -a && [ -f .env ] && source .env && set +a\n"
        )

