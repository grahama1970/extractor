from __future__ import annotations
import time
import typer
from ..arango_client import get_db

# Separate Typer apps for console scripts mapping
approve_app = typer.Typer(add_completion=False)
prune_app = typer.Typer(add_completion=False)

@approve_app.command("approve")
def approve(edge_id: str = typer.Option("", help="Edge _id to approve (or use from/to)"), from_title: str = typer.Option(""), from_scope: str = typer.Option("tabbed"), to_title: str = typer.Option(""), to_scope: str = typer.Option("tabbed"), human_rationale: str = typer.Option("Approved")):
    db = get_db()
    ts = int(time.time())
    if not edge_id:
        f = list(db.aql.execute('FOR d IN lessons FILTER d.title==@t AND d.scope==@s LIMIT 1 RETURN d._id', bind_vars={'t':from_title,'s':from_scope}))
        t = list(db.aql.execute('FOR d IN lessons FILTER d.title==@t AND d.scope==@s LIMIT 1 RETURN d._id', bind_vars={'t':to_title,'s':to_scope}))
        if not f or not t:
            print('edge_id or from/to titles required')
            raise typer.Exit(2)
        arr = list(db.aql.execute('FOR e IN lesson_edges FILTER e._from==@f AND e._to==@t AND e.type=="related" LIMIT 1 RETURN e._id', bind_vars={'f':f[0],'t':t[0]}))
        if not arr:
            print('edge not found')
            raise typer.Exit(3)
        edge_id = arr[0]
    aql = 'LET e = DOCUMENT(@eid) UPDATE e WITH { approved: true, status: "active", rationale: @hr, rationales: APPEND(e.rationales ? e.rationales : [], { by: "human", text: @hr, at: @ts }), last_verified_at: @ts, updated_at: @ts } IN lesson_edges RETURN NEW._id'
    out = list(db.aql.execute(aql, bind_vars={'eid':edge_id,'hr':human_rationale,'ts':ts}))
    print('approved:', out[0])

@prune_app.command("prune")
def prune():
    db = get_db()
    aql = '''
    FOR e IN lesson_edges
      FILTER e.type=='related' AND e.approved==false AND e.status=='pending'
        AND e.weight < 0.30
        AND (DATE_NOW()/1000 - e.created_at) > 365*86400
        AND (e.usage_count == null OR e.usage_count == 0)
      REMOVE e IN lesson_edges RETURN OLD._id
    '''
    removed = list(db.aql.execute(aql))
    print('pruned:', removed)
