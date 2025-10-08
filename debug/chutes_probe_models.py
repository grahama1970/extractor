#!/usr/bin/env python3
import os
import sys
import json
import argparse
import urllib.request
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin


def normalize_base(b: str) -> str:
    b = (b or "").strip().rstrip("/")
    if not b:
        b = "https://llm.chutes.ai"
    # Avoid double /v1 if already provided in env
    if b.endswith("/v1"):
        return b
    return b + "/v1"


def post_chat(base: str, api_key: str, model: str):
    # Accept openai/<vendor>/<id> or raw "<vendor>/<id>"
    raw = model.split("/", 2)[2] if model.startswith("openai/") else model
    url = urljoin(normalize_base(base) + "/", "chat/completions")
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    body = json.dumps(
        {
            "model": raw,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1,
            "stream": False,
        }
    ).encode("utf-8")
    with urllib.request.urlopen(req, data=body, timeout=20) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))


def main():
    ap = argparse.ArgumentParser(description="Probe a single Chutes model via OpenAI-compatible /chat/completions")
    ap.add_argument(
        "--model",
        "-m",
        required=True,
        help=(
            "Model id (e.g., deepseek-ai/DeepSeek-V3-0324-turbo or openai/deepseek-ai/DeepSeek-V3-0324-turbo)"
        ),
    )
    args = ap.parse_args()

    base = os.getenv("CHUTES_API_BASE", "https://llm.chutes.ai")
    key = os.getenv("CHUTES_API_KEY", "")
    if not key:
        print("CHUTES_API_KEY is not set", file=sys.stderr)
        sys.exit(2)

    try:
        data = post_chat(base, key, args.model)
        # If the aggregator returned a completion, consider it OK
        ok = bool(data.get("choices"))
        out = {
            "ok": ok,
            "endpoint": normalize_base(base),
            "model_sent": args.model,
            "raw_model": args.model.split("/", 2)[2] if args.model.startswith("openai/") else args.model,
            "response_keys": list(data.keys())[:5],
        }
        print(json.dumps(out, indent=2))
        sys.exit(0 if ok else 1)
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
