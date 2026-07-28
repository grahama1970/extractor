#!/usr/bin/env python3
"""
Deprecated: litellm parallel helper smoke.

Extractor is SciLLM-only now. This smoke is kept to avoid breaking
external references, but it exits with SKIP and code 0.
"""

from __future__ import annotations

import argparse
import json
from typing import Any, Dict


def run(mode: str) -> Dict[str, Any]:
    """Return a dictionary containing the mode and status flags."""
    return {"mode": mode, "ok": True, "skip": "SciLLM-only; litellm parallel smoke deprecated"}


def main() -> None:
    """Parse command-line arguments and print JSON output."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", required=False, default="helper", choices=["helper", "legacy"])
    args = ap.parse_args()
    print(json.dumps(run(args.mode), ensure_ascii=False))


if __name__ == "__main__":
    main()
