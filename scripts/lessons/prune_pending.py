#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "python-arango>=8.2.0",
# ]
# ///

from __future__ import annotations
from scripts.lessons.arango_client import get_db


def main():
    """Remove pending related lesson edges from the database."""
    db = get_db()
    aql = """
    FOR e IN lesson_edges
      FILTER e.type=='related' AND e.approved==false AND e.status=='pending'
        AND e.weight < 0.30
        AND (DATE_NOW()/1000 - e.created_at) > 365*86400
        AND (e.usage_count == null OR e.usage_count == 0)
      REMOVE e IN lesson_edges RETURN OLD._id
    """
    cur = db.aql.execute(aql)
    removed = list(cur)
    print("pruned:", removed)


if __name__ == "__main__":
    main()
