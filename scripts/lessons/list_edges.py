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


@app.command()
def list_edges(
    title: str = typer.Option("", help="Seed by title (optional)"),
    scope: str = typer.Option("", help="Scope for title seed (optional)"),
    approved: str = typer.Option("", help="'true'|'false' to filter"),
    status: str = typer.Option("", help="Filter by status (e.g., pending|active)"),
    etype: str = typer.Option("related", help="Edge type"),
    limit: int = typer.Option(25, help="Limit results"),
    json_out: bool = typer.Option(False, "--json", help="Output JSON"),
):
    """List edges based on optional filters for title, scope, and status."""
    db = get_db()
    bind = {"type": etype, "limit": max(1, limit)}
    filters = ["e.type==@type"]
    if approved.strip():
        if approved.lower() in ("true", "1", "yes"):
            bind["approved"] = True
            filters.append("e.approved==@approved")
        if approved.lower() in ("false", "0", "no"):
            bind["approved"] = False
            filters.append("e.approved==@approved")
    if status.strip():
        bind["status"] = status
        filters.append("e.status==@status")
    seed_filter = ""
    if title:
        q = "FOR d IN lessons FILTER d.title==@t AND (@s=='' OR d.scope==@s) LIMIT 1 RETURN d._id"
        sid = list(db.aql.execute(q, bind_vars={"t": title, "s": scope or ""}))
        if not sid:
            print("seed not found")
            raise typer.Exit(2)
        bind["sid"] = sid[0]
        seed_filter = " AND (e._from==@sid OR e._to==@sid)"
    where = " AND ".join(filters)
    aql = f"""
    FOR e IN lesson_edges
      FILTER {where}{seed_filter}
      LET nid = e._to
      LET key = SPLIT(nid,'/')[1]
      LET l = DOCUMENT('lessons', key)
      SORT e.updated_at DESC, e.weight DESC
      LIMIT @limit
      RETURN {{ edge: KEEP(e, ['_id','_from','_to','type','approved','status','weight','raw_sim','rationale']), neighbor: KEEP(l,['title','scope','tags']) }}
    """
    res = list(db.aql.execute(aql, bind_vars=bind))
    if json_out:
        print(json.dumps(res, ensure_ascii=False))
    else:
        for r in res:
            e = r["edge"]
            n = r["neighbor"]
            print(
                f"{e['_id']}  {e['type']}  w={e.get('weight',0):.2f}  appr={e.get('approved')}  {n.get('title')} ({n.get('scope')})"
            )


if __name__ == "__main__":
    app()
