#!/usr/bin/env python3
"""Scenario: Validate Arango graph basic health if configured.

SKIP when ARANGO_* env vars are not present. Minimal checks:
- Connect and fetch a small count from a known collection or graph.
"""
from __future__ import annotations

import os
import sys

try:
    from arango import ArangoClient  # type: ignore
except Exception:
    ArangoClient = None  # type: ignore


def env(name: str) -> str | None:
    v = os.getenv(name)
    return v if v and not v.strip().startswith("${") else None


def main() -> None:
    host = env("ARANGO_HOST") or "http://127.0.0.1"
    port = env("ARANGO_PORT") or "8529"
    user = env("ARANGO_USER") or env("ARANGO_USERNAME")
    password = env("ARANGO_PASSWORD")
    dbname = env("ARANGO_DB") or env("ARANGO_DATABASE")
    if not dbname or not user or not password:
        print("SKIP: missing ARANGO_* credentials; not probing graph DB")
        sys.exit(0)
    if ArangoClient is None:
        print("SKIP: python-arango not installed in this env")
        sys.exit(0)

    client = ArangoClient(hosts=f"{host}:{port}")
    sys_db = client.db("_system", username=user, password=password)
    if not sys_db.has_database(dbname):
        print(f"SKIP: database '{dbname}' not found")
        sys.exit(0)
    db = client.db(dbname, username=user, password=password)
    # Try light checks
    collections = db.collections()
    names = [c["name"] for c in collections if not c.get("system")]
    has_nodes = any(n.lower().startswith("nodes") for n in names) or any(n.lower().startswith("v_") for n in names)
    print("Scenario pipeline/step_11_graph_db: collections=", names[:10])
    sys.exit(0 if has_nodes else 1)


if __name__ == "__main__":
    main()

