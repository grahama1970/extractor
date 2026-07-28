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


def resolve_id(db, title: str, scope: str) -> str | None:
    """Retrieve document ID from database matching title and scope."""
    cur = db.aql.execute(
        "FOR d IN lessons FILTER d.title==@t AND d.scope==@s LIMIT 1 RETURN d._id",
        bind_vars={"t": title, "s": scope},
    )
    arr = list(cur)
    return arr[0] if arr else None


@app.command()
def approve(
    edge_id: str = typer.Option("", help="Edge _id to approve (alternative: provide from/to)"),
    from_title: str = typer.Option("", help="From title"),
    from_scope: str = typer.Option("", help="From scope"),
    to_title: str = typer.Option("", help="To title"),
    to_scope: str = typer.Option("", help="To scope"),
    human_rationale: str = typer.Option("Looks good", help="Human override rationale"),
):
    """Approve an edge by ID or from/to titles and scopes."""
    db = get_db()
    ts = int(time.time())
    if not edge_id:
        f = resolve_id(db, from_title, from_scope)
        t = resolve_id(db, to_title, to_scope)
        if not f or not t:
            print("edge_id or from/to titles required")
            raise typer.Exit(2)
        cur = db.aql.execute(
            'FOR e IN lesson_edges FILTER e._from==@f AND e._to==@t AND e.type=="related" LIMIT 1 RETURN e._id',
            bind_vars={"f": f, "t": t},
        )
        arr = list(cur)
        if not arr:
            print("edge not found")
            raise typer.Exit(3)
        edge_id = arr[0]
    aql = 'LET e = DOCUMENT(@eid) UPDATE e WITH { approved: true, status: "active", rationale: @hr, rationales: APPEND(e.rationales ? e.rationales : [], { by: "human", text: @hr, at: @ts }), last_verified_at: @ts, updated_at: @ts } IN lesson_edges RETURN NEW._id'
    out = list(db.aql.execute(aql, bind_vars={"eid": edge_id, "hr": human_rationale, "ts": ts}))
    print("approved:", out[0])


if __name__ == "__main__":
    app()
