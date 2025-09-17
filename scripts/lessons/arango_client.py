#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "python-arango>=8.2.0",
# ]
# ///

from __future__ import annotations
import os
from typing import Optional

from arango import ArangoClient  # type: ignore


def get_db():
    """
    Connect to ArangoDB using environment variables.

    Required env:
      - ARANGO_URL (e.g., http://127.0.0.1:8529)
      - ARANGO_DB (e.g., lessons)
      - ARANGO_USER / ARANGO_PASS
    """
    url = os.getenv("ARANGO_URL", "http://127.0.0.1:8529")
    db_name = os.getenv("ARANGO_DB", "lessons")
    user = os.getenv("ARANGO_USER", "root")
    password = os.getenv("ARANGO_PASS", "")

    client = ArangoClient(hosts=url)
    sys_db = client.db("_system", username=user, password=password)
    if not sys_db.has_database(db_name):
        sys_db.create_database(db_name)
    db = client.db(db_name, username=user, password=password)
    return db
