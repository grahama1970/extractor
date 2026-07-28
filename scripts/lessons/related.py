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


def resolve_key(col, title: str | None, scope: str | None) -> str | None:
    """Resolve document key from collection based on title and scope."""
    if not title:
        return None
    cur = col.find({"title": title, "scope": scope or "tabbed"})
    docs = list(cur) if cur else []
    return docs[0]["_key"] if docs else None


@app.command()
def related(
    key: str = typer.Option("", help="_key of seed lesson (or use --title + --scope)"),
    title: str = typer.Option("", help="Resolve by title"),
    scope: str = typer.Option("tabbed", help="Scope for title resolution"),
    direction: str = typer.Option("both", help="out|in|both"),
    k: int = typer.Option(10, help="Limit"),
    json_out: bool = typer.Option(False, "--json", help="JSON output"),
):
    """Retrieve related lessons based on a specified key or title."""
    db = get_db()
    lessons = db.collection("lessons")
    edges = db.collection("lesson_edges")
    seed = key or resolve_key(lessons, title, scope)
    if not seed:
        print("Provide --key or --title + --scope")
        raise typer.Exit(2)
    seed_id = f"lessons/{seed}"
    # Collect neighbor edges
    out_docs = []
    rels = []
    if direction in ("out", "both"):
        for e in edges.find({"_from": seed_id}) or []:
            out_docs.append(e)
    if direction in ("in", "both"):
        for e in edges.find({"_to": seed_id}) or []:
            out_docs.append(e)
    # Deduplicate by neighbor id, keep max weight
    acc: dict[str, dict] = {}
    for e in out_docs:
        nid = e["_to"] if e.get("_from") == seed_id else e.get("_from")
        if not nid:
            continue
        if nid not in acc or float(e.get("weight", 0)) > float(acc[nid].get("weight", 0)):
            acc[nid] = e
    # Fetch neighbor lessons and format
    for nid, e in acc.items():
        try:
            ldoc = lessons.get(nid.split("/", 1)[1])
        except Exception:
            ldoc = None
        if ldoc:
            rels.append(
                {
                    "neighbor": {
                        "_key": ldoc.get("_key"),
                        "title": ldoc.get("title"),
                        "scope": ldoc.get("scope"),
                        "tags": ldoc.get("tags", []),
                    },
                    "edge": {
                        "weight": float(e.get("weight", 0)),
                        "rationale": e.get("rationale"),
                        "date": e.get("date"),
                    },
                }
            )
    rels.sort(key=lambda x: x["edge"]["weight"], reverse=True)
    rels = rels[:k]
    if json_out:
        import json as _json

        print(_json.dumps(rels, ensure_ascii=False))
    else:
        for i, r in enumerate(rels, 1):
            print(
                f"{i}. {r['neighbor']['title']}  [w={r['edge']['weight']:.2f}]  ({r['neighbor']['scope']})"
            )
            if r["edge"].get("rationale"):
                print(f"   {r['edge']['rationale']}")


if __name__ == "__main__":
    app()
