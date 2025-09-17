from __future__ import annotations
import typer
from ..arango_client import get_db

app = typer.Typer(add_completion=False)

@app.command()
def related(title: str = typer.Option(...), scope: str = typer.Option("tabbed"), k: int = typer.Option(10)):
    db = get_db()
    seed = list(db.aql.execute('FOR d IN lessons FILTER d.title==@t AND d.scope==@s LIMIT 1 RETURN d._id', bind_vars={'t':title,'s':scope}))
    if not seed:
        print('seed not found')
        raise typer.Exit(2)
    sid = seed[0]
    aql = '''
    FOR e IN lesson_edges
      FILTER e.type=='related' AND (e._from==@sid OR e._to==@sid)
      LET nid = e._from==@sid ? e._to : e._from
      LET key = SPLIT(nid,'/')[1]
      LET l = DOCUMENT('lessons', key)
      SORT e.weight DESC
      LIMIT @k
      RETURN { neighbor: KEEP(l,['_key','title','scope','tags']), edge: KEEP(e,['weight','approved','status','raw_sim','rationale']) }
    '''
    items = list(db.aql.execute(aql, bind_vars={'sid':sid,'k':max(1,k)}))
    for it in items:
        n=it['neighbor']; e=it['edge']
        print(f"{n['title']} ({n['scope']})  w={e.get('weight',0):.2f}  appr={e.get('approved')}  tags={','.join(n.get('tags',[]))}")
