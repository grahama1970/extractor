#!/usr/bin/env python3
import os
import sys
import json
import argparse
import urllib.request
from urllib.error import HTTPError, URLError


def normalize_base(b: str) -> str:
    b = (b or "").strip().rstrip("/")
    if not b:
        b = "https://llm.chutes.ai"
    if b.endswith("/v1"):
        return b
    return b + "/v1"


def get_models(base: str, api_key: str):
    url = normalize_base(base) + "/models"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))


def main():
    ap = argparse.ArgumentParser(description="List models from Chutes OpenAI-compatible aggregator")
    ap.add_argument("--json", action="store_true", help="Output raw JSON")
    ap.add_argument("--filter", type=str, default="", help="Substring filter for model id")
    args = ap.parse_args()

    base = os.getenv("CHUTES_API_BASE", "https://llm.chutes.ai")
    key = os.getenv("CHUTES_API_KEY", "")
    if not key:
        print("CHUTES_API_KEY is not set", file=sys.stderr)
        sys.exit(2)

    try:
        data = get_models(base, key)
        if args.json:
            print(json.dumps(data, indent=2))
            return
        models = []
        # Try to support both OpenAI /v1/models shape and potential custom shapes
        if isinstance(data, dict) and isinstance(data.get("data"), list):
            for m in data["data"]:
                mid = m.get("id") or m.get("model") or m.get("name")
                if not mid:
                    continue
                if args.filter and args.filter.lower() not in str(mid).lower():
                    continue
                models.append(str(mid))
        elif isinstance(data, list):
            for m in data:
                mid = None
                if isinstance(m, dict):
                    mid = m.get("id") or m.get("model") or m.get("name")
                else:
                    mid = str(m)
                if not mid:
                    continue
                if args.filter and args.filter.lower() not in str(mid).lower():
                    continue
                models.append(str(mid))
        else:
            print("Unexpected /models response shape", file=sys.stderr)
            print(json.dumps(data, indent=2))
            sys.exit(1)

        for mid in models:
            print(mid)
    except HTTPError as e:
        body = None
        try:
            body = e.read().decode("utf-8", "ignore")
        except Exception:
            body = None
        print(json.dumps({"ok": False, "error": f"HTTP {e.code}", "body": body}, indent=2))
        sys.exit(1)
    except URLError as e:
        print(json.dumps({"ok": False, "error": f"URL error {e}"}, indent=2))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
