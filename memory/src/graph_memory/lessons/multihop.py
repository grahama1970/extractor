from __future__ import annotations
import typer
from ..arango_client import get_db

app = typer.Typer(add_completion=False)

@app.command()
def multihop(title: str = typer.Option(...), scope: str = typer.Option("tabbed"), depth: int = typer.Option(2), limit: int = typer.Option(10)):
    db = get_db()
    seed = list(db.aql.execute('FOR d IN lessons FILTER d.title==@t AND d.scope==@s LIMIT 1 RETURN d._id', bind_vars={'t':title,'s':scope}))
    if not seed:
        print('seed not found')
        raise typer.Exit(2)
    sid = seed[0]
    depth = max(1, min(4, int(depth)))
    aql = '''
    FOR v, e, p IN 1..@depth ANY @seed lesson_edges
      OPTIONS { bfs: true, uniqueVertices: 'path' }
      FILTER v._id != @seed
      LIMIT @limit
      RETURN { target: v, edges: p.edges }
    '''
    rows = list(db.aql.execute(aql, bind_vars={'seed':sid,'depth':depth,'limit':max(1,limit)}))
    print(f"Paths: {len(rows)}")
    for i, r in enumerate(rows[:limit], 1):
        tgt = r['target']
        print(f"{i}. -> {tgt.get('title')} ({tgt.get('scope')})  edges={len(r.get('edges') or [])}")
