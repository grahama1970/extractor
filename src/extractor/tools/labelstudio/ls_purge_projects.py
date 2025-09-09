#!/usr/bin/env python3
from __future__ import annotations

import os
import requests
from .util_env import load_ls_env
from .util_auth import get_access_token


def main():
    load_ls_env()
    host = os.environ.get("LS_HOST", "http://localhost:8080").rstrip("/")
    access = get_access_token(host)
    headers = {"Authorization": f"Bearer {access}", "Content-Type": "application/json"}

    r = requests.get(f"{host}/api/projects/", headers=headers, timeout=30)
    r.raise_for_status()
    items = r.json().get("results") or r.json()
    deleted = 0
    for p in items:
        pid = p.get("id")
        if not pid:
            continue
        d = requests.delete(f"{host}/api/projects/{pid}/", headers=headers, timeout=30)
        if d.status_code in (200, 204):
            deleted += 1
        else:
            print(f"Delete failed {pid}: HTTP {d.status_code} {d.text}")
    print(f"deleted projects: {deleted}")


if __name__ == "__main__":
    main()

