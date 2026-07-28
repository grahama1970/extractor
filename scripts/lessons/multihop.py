#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "python-arango>=8.2.0",
#   "typer>=0.12",
# ]
# ///

from __future__ import annotations
import json
import typer
from scripts.lessons.arango_client import get_db

app = typer.Typer(add_completion=False)


def resolve_key(col, title: str | None, scope: str | None) -> str | None:
    """Resolve document key by title and scope."""
    if not title:
        return None
    cur = col.find({"title": title, "scope": scope or "tabbed"})
    docs = list(cur) if cur else []
    return docs[0]["_key"] if docs else None


@app.command()
def multihop(
    key: str = typer.Option("", help="Seed _key (or use --title + --scope)"),
    title: str = typer.Option("", help="Resolve seed by title"),
    scope: str = typer.Option("tabbed", help="Scope used with --title"),
    depth: int = typer.Option(2, help="Max hop depth (1..4)"),
    direction: str = typer.Option("ANY", help="OUTBOUND|INBOUND|ANY"),
    limit: int = typer.Option(10, help="Top K neighbors to return"),
    json_out: bool = typer.Option(False, "--json", help="Output JSON"),
):
    """Perform multihop operation."""
    db = get_db()
    lessons = db.collection("lessons")
    seed_key = key or resolve_key(lessons, title, scope)
    if not seed_key:
        typer.echo("Provide --key or --title + --scope")
        raise typer.Exit(2)
    seed_id = f"lessons/{seed_key}"
    depth = max(1, min(4, int(depth)))
    dir_kw = direction.upper()
    if dir_kw not in ("OUTBOUND", "INBOUND", "ANY"):
        dir_kw = "ANY"

    aql = f"""
    FOR v, e, p IN 1..@depth {dir_kw} @seed lesson_edges
      OPTIONS {{ bfs: true, uniqueVertices: 'path' }}
      FILTER v._id != @seed
      RETURN {{
        target: v,
        edges: p.edges
      }}
    """
    cur = db.aql.execute(aql, bind_vars={"seed": seed_id, "depth": depth})

    # Aggregate best score per neighbor using product of weights (or exp of sum of log weights)
    best: dict[str, dict] = {}
    for row in cur:
        tgt = row.get("target") or {}
        tid = tgt.get("_id")
        if not tid:
            continue
        wprod = 1.0
        for ed in row.get("edges") or []:
            w = ed.get("weight")
            try:
                w = float(w)
            except Exception:
                w = 0.5
            w = max(0.0, min(1.0, w))
            wprod *= max(1e-6, w)
        prev = best.get(tid)
        if (not prev) or (wprod > prev["score"]):
            best[tid] = {
                "score": wprod,
                "neighbor": {
                    "_key": tgt.get("_key"),
                    "title": tgt.get("title"),
                    "scope": tgt.get("scope"),
                    "tags": tgt.get("tags", []),
                },
            }

    ranked = sorted(best.values(), key=lambda x: x["score"], reverse=True)[:limit]
    if json_out:
        print(json.dumps(ranked, ensure_ascii=False))
        return
    for i, r in enumerate(ranked, 1):
        print(
            f"{i}. {r['neighbor']['title']}  [score={r['score']:.4f}]  ({r['neighbor']['scope']})"
        )


if __name__ == "__main__":
    app()
