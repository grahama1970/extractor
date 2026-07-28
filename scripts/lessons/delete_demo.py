#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "python-arango>=8.2.0",
#   "typer>=0.12",
# ]
# ///

from __future__ import annotations
import typer
from scripts.lessons.arango_client import get_db

app = typer.Typer(add_completion=False)


@app.command()
def delete(demo_batch: str = typer.Option("", help="Optional demo batch id to narrow deletion")):
    """Delete demo lessons, optionally by batch ID."""
    db = get_db()
    if demo_batch:
        aql = "FOR d IN lessons FILTER d.demo==true AND d.demo_batch==@b REMOVE d IN lessons RETURN OLD._key"
        cur = db.aql.execute(aql, bind_vars={"b": demo_batch})
    else:
        aql = "FOR d IN lessons FILTER d.demo==true REMOVE d IN lessons RETURN OLD._key"
        cur = db.aql.execute(aql)
    removed = list(cur)
    print(f"Deleted {len(removed)} demo lessons" + (f" (batch={demo_batch})" if demo_batch else ""))


if __name__ == "__main__":
    app()
