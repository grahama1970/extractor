#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "python-arango>=8.2.0",
#   "typer>=0.12",
# ]
# ///

from __future__ import annotations
import os
import time
import typer
from scripts.lessons.arango_client import get_db

SYNONYMS = {
    "cdp": ["chrome", "chromium", "devtools", "browserless", "puppeteer", "playwright"],
    "proxy": ["vite", "backend", "target", "api", "port", "8000", "8001"],
    "json": ["response_format", "schema", "structured", "wrap_json"],
    "smokes": ["smoke", "ci", "tests", "playwright", "puppeteer"],
    "timeout": ["hang", "stall", "latency"],
}


def build_keywords(tags: list[str], scope: str) -> str:
    bag: list[str] = []
    for t in tags:
        bag.append(t)
        bag.extend(SYNONYMS.get(t.lower(), []))
    if scope:
        bag.append(scope)
    # de-dupe while preserving order
    seen = set()
    out: list[str] = []
    for w in bag:
        if w and w not in seen:
            seen.add(w)
            out.append(w)
    return " ".join(out)


app = typer.Typer(add_completion=False)


@app.command()
def add(
    title: str = typer.Option(..., help="Lesson title"),
    problem: str = typer.Option(..., help="Problem summary"),
    playbook: str = typer.Option(..., help="Playbook / steps"),
    tags: str = typer.Option("", help="Comma-separated tags e.g. cdp,proxy"),
    scope: str = typer.Option("tabbed", help="Repo/component scope"),
    status: str = typer.Option("active", help="active|draft|deprecated"),
):
    db = get_db()
    col = db.collection("lessons")
    doc = {
        "title": title,
        "problem": problem,
        "playbook": playbook,
        "tags": [t.strip() for t in tags.split(",") if t.strip()] if tags else [],
        "scope": scope,
        "status": status,
        "added_by": os.getenv("USER", "unknown"),
        "updated_at": int(time.time()),
    }
    # Add a flat keywords field to improve BM25 recall (tags + synonyms + scope)
    doc["keywords"] = build_keywords(doc.get("tags", []), scope)
    # Upsert by title+scope
    existing_cur = col.find({"title": title, "scope": scope})
    existing_list = list(existing_cur) if existing_cur else []
    if existing_list:
        key = existing_list[0]["_key"]
        col.update_match({"_key": key}, doc)
        print(f"Updated lesson {_safe(existing_list[0])}")
    else:
        col.insert(doc)
        print("Inserted lesson")


def _safe(d):
    return {k: d[k] for k in ("_key", "title", "scope") if k in d}


if __name__ == "__main__":
    app()
