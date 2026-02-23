#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "python-arango>=8.2.0",
#   "typer>=0.12",
# ]
# ///

from __future__ import annotations
import time
import typer
from scripts.lessons.arango_client import get_db

app = typer.Typer(add_completion=False)


def resolve_key(col, title: str | None, scope: str | None) -> str | None:
    if not title:
        return None
    cur = col.find({"title": title, "scope": scope or "tabbed"})
    docs = list(cur) if cur else []
    return docs[0]["_key"] if docs else None


@app.command()
def link(
    from_key: str = typer.Option(
        "", help="_key of source lesson (alternative: --from-title + --from-scope)"
    ),
    to_key: str = typer.Option(
        "", help="_key of target lesson (alternative: --to-title + --to-scope)"
    ),
    from_title: str = typer.Option("", help="Resolve source by title"),
    from_scope: str = typer.Option("tabbed", help="Resolve source scope"),
    to_title: str = typer.Option("", help="Resolve target by title"),
    to_scope: str = typer.Option("tabbed", help="Resolve target scope"),
    rationale: str = typer.Option("", help="Why these are related"),
    weight: float = typer.Option(0.5, help="Edge weight [0..1]"),
    date: int = typer.Option(0, help="Unix epoch (default: now)"),
):
    db = get_db()
    lessons = db.collection("lessons")
    edges = db.collection("lesson_edges")
    fk = from_key or resolve_key(lessons, from_title, from_scope)
    tk = to_key or resolve_key(lessons, to_title, to_scope)
    if not fk or not tk:
        print("from/to not resolved — provide keys or valid title+scope")
        raise typer.Exit(2)
    doc = {
        "_from": f"lessons/{fk}",
        "_to": f"lessons/{tk}",
        "rationale": rationale or "",
        "weight": float(max(0.0, min(1.0, weight))),
        "date": int(date or time.time()),
    }
    ins = edges.insert(doc)
    print(f"Linked lessons: {ins.get('_key')}  {_fmt_node(fk)} -> {_fmt_node(tk)}")


def _fmt_node(k: str) -> str:
    return f"lessons/{k}"


if __name__ == "__main__":
    app()
