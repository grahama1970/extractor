#!/usr/bin/env python3
"""Scenario: Backend health surfaces without starting servers.

Prereqs:
- BACKEND_BASE (default http://127.0.0.1:8000)

Behavior:
- GET {BACKEND_BASE}/api/health/llm and print minimal JSON if reachable
- If connection refused or 404, SKIP with exit 0 (isolation-friendly)
"""
from __future__ import annotations

import json
import os
import sys
from urllib.request import urlopen
from urllib.error import URLError, HTTPError

BASE = os.getenv("BACKEND_BASE", "http://127.0.0.1:8000").rstrip("/")
URL = os.getenv("API_HEALTH_URL") or f"{BASE}/api/health/llm"


def main() -> None:
    try:
        with urlopen(URL, timeout=10) as resp:
            data = resp.read().decode("utf-8", errors="replace")
            print(json.dumps({"url": URL, "status": resp.status, "body": data[:500]}, indent=2))
            if resp.status == 200:
                print("Scenario pipeline/api_health: OK")
                sys.exit(0)
            else:
                print("Scenario pipeline/api_health: FAIL (non-200)")
                sys.exit(1)
    except HTTPError as e:
        if e.code == 404:
            print("SKIP: /api/health/llm not found (404) at", URL)
            sys.exit(0)
        print("Scenario pipeline/api_health: FAIL (HTTPError)", e)
        sys.exit(1)
    except URLError as e:
        if "Connection refused" in str(e.reason):
            print("SKIP: backend not reachable at", URL)
            sys.exit(0)
        print("Scenario pipeline/api_health: FAIL (URLError)", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
