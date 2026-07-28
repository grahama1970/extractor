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
def delete(
    key: str = typer.Option("", help="_key of the lesson to delete"),
    title: str = typer.Option("", help="Alternatively specify title + scope"),
    scope: str = typer.Option("", help="Scope for title-based delete"),
):
    """Delete a lesson by key or title and scope."""
    db = get_db()
    col = db.collection("lessons")
    if key:
        try:
            db.aql.execute("REMOVE {_key: @key} IN lessons", bind_vars={"key": key})
            print(f"Deleted lesson key={key}")
            return
        except Exception as e:
            print(f"Failed to delete key={key}: {e}")
            raise typer.Exit(1)
    if not title or not scope:
        print("Provide --key or both --title and --scope")
        raise typer.Exit(2)
    cur = col.find({"title": title, "scope": scope})
    items = list(cur) if cur else []
    if not items:
        print("No matching lesson.")
        raise typer.Exit(0)
    for d in items:
        try:
            db.aql.execute("REMOVE {_key: @key} IN lessons", bind_vars={"key": d["_key"]})
            print(f"Deleted lesson key={d['_key']}")
        except Exception as e:
            print(f"Failed to delete key={d['_key']}: {e}")
            raise typer.Exit(1)


if __name__ == "__main__":
    app()
