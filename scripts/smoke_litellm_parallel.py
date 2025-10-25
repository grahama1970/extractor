#!/usr/bin/env python3
"""
Deprecated: litellm parallel helper smoke.

Extractor is SciLLM-only now. This smoke is kept to avoid breaking
external references, but it exits with SKIP and code 0.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
from typing import Any, Dict


def run(mode: str) -> Dict[str, Any]:
    return {"mode": mode, "ok": True, "skip": "SciLLM-only; litellm parallel smoke deprecated"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", required=False, default="helper", choices=["helper", "legacy"]) 
    args = ap.parse_args()
    print(json.dumps(run(args.mode), ensure_ascii=False))


if __name__ == "__main__":
    main()
