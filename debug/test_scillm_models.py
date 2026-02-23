#!/usr/bin/env python3
"""
List models from a Chutes (OpenAI-compatible) gateway and write artifacts.
Outputs:
  - .artifacts/chutes/models_raw_openai.json
  - .artifacts/chutes/models_ids.txt (overwrites/merges with zsh output)
Prints a one-line JSON: {"ok": true, "count": N, "out": ".../models_ids.txt"}
"""
import json
import os
import sys
import urllib.request
from pathlib import Path

ART = Path(".artifacts/chutes")
RAW = ART / "models_raw_openai.json"
IDS = ART / "models_ids.txt"


def map_env():
    base = os.getenv("CHUTES_API_BASE")
    key = os.getenv("CHUTES_API_KEY")
    if base and not os.getenv("OPENAI_BASE_URL"):
        os.environ["OPENAI_BASE_URL"] = base
        os.environ["OPENAI_API_BASE"] = base
    if key and not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = key


def fetch_models(timeout=20):
    base = (os.getenv("OPENAI_BASE_URL") or os.getenv("OPENAI_API_BASE") or "").rstrip("/")
    key = os.getenv("OPENAI_API_KEY")
    if not base or not key:
        return {"error": "OPENAI_* (or CHUTES_*) env not set"}
    req = urllib.request.Request(
        base + "/models",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    map_env()
    ART.mkdir(parents=True, exist_ok=True)
    try:
        data = fetch_models()
        if "error" in data and not data.get("data"):
            print(json.dumps({"ok": False, **data}))
            return 1
        RAW.write_text(json.dumps(data, indent=2), encoding="utf-8")
        ids = [x.get("id") for x in (data.get("data") or []) if x.get("id")]
        IDS.write_text("\n".join(ids), encoding="utf-8")
        print(json.dumps({"ok": True, "count": len(ids), "out": str(IDS)}))
        return 0
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
