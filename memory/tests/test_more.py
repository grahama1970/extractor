import os
import time
import uuid
import pytest

from graph_memory.arango_client import get_db
from graph_memory.setup_schema import ensure_collections_and_view
from graph_memory.lessons.recall import bm25_rank, fuse_bm25_graph


def _env():
    os.environ.setdefault("ARANGO_URL", "http://127.0.0.1:8529")
    os.environ.setdefault("ARANGO_DB", os.getenv("ARANGO_DATABASE", "lessons"))
    os.environ.setdefault("ARANGO_USER", "root")
    os.environ.setdefault("ARANGO_PASS", os.getenv("ARANGO_PASS", "openSesame"))


@pytest.fixture(scope="module")
def db():
    _env()
    try:
        ensure_collections_and_view()
        return get_db()
    except Exception as e:
        pytest.skip(f"Arango not reachable: {e}")


def test_related_neighbor_shape(db):
    ts = int(time.time())
    a = f"DEMO[gm-related] A {ts}"
    b = f"DEMO[gm-related] B {ts}"
    for t in (a, b):
        db.aql.execute(
            "UPSERT { title:@t, scope:'tabbed' } INSERT { title:@t, scope:'tabbed', tags:['gm'], updated_at:@ts, demo:true, demo_batch:'gm-related' } UPDATE { updated_at:@ts, demo:true, demo_batch:'gm-related' } IN lessons",
            bind_vars={"t": t, "ts": ts},
        )
    f_id = db.aql.execute("FOR d IN lessons FILTER d.title==@t AND d.scope=='tabbed' LIMIT 1 RETURN d._id", bind_vars={"t": a}).next()
    t_id = db.aql.execute("FOR d IN lessons FILTER d.title==@t AND d.scope=='tabbed' LIMIT 1 RETURN d._id", bind_vars={"t": b}).next()
    db.aql.execute(
        "UPSERT { _from:@f, _to:@t, type:'related' } INSERT { _from:@f, _to:@t, type:'related', weight:0.7, approved:true, status:'active' } UPDATE { weight:0.7, approved:true, status:'active' } IN lesson_edges",
        bind_vars={"f": f_id, "t": t_id},
    )
    # Aggregate neighbor via AQL
    aql = """
    FOR e IN lesson_edges
      FILTER e.type=='related' AND (e._from==@sid OR e._to==@sid)
      LET nid = e._from==@sid ? e._to : e._from
      LET key = SPLIT(nid,'/')[1]
      LET l = DOCUMENT('lessons', key)
      LIMIT 1
      RETURN { neighbor: KEEP(l,['_key','title','scope','tags']), edge: KEEP(e,['weight','approved','status']) }
    """
    out = list(db.aql.execute(aql, bind_vars={"sid": f_id}))
    assert out and 'neighbor' in out[0] and 'edge' in out[0]


def test_multihop_paths_exist(db):
    # Create a small chain A->B->C
    ts = int(time.time())
    ids = []
    for name in ('MHA', 'MHB', 'MHC'):
        title = f"DEMO[gm-mh] {name} {ts}"
        db.aql.execute(
            "UPSERT { title:@t, scope:'tabbed' } INSERT { title:@t, scope:'tabbed', tags:['gm'], updated_at:@ts, demo:true, demo_batch:'gm-mh' } UPDATE { updated_at:@ts, demo:true, demo_batch:'gm-mh' } IN lessons",
            bind_vars={"t": title, "ts": ts},
        )
        ids.append(db.aql.execute("FOR d IN lessons FILTER d.title==@t AND d.scope=='tabbed' LIMIT 1 RETURN d._id", bind_vars={"t": title}).next())
    f_id, mid_id, t_id = ids
    for pair in ((f_id, mid_id), (mid_id, t_id)):
        db.aql.execute(
            "UPSERT { _from:@f, _to:@t, type:'related' } INSERT { _from:@f, _to:@t, type:'related', weight:0.6, approved:true, status:'active' } UPDATE { weight:0.6, approved:true, status:'active' } IN lesson_edges",
            bind_vars={"f": pair[0], "t": pair[1]},
        )
    # Multihop BFS
    rows = list(db.aql.execute(
        """
        FOR v, e, p IN 1..2 ANY @seed lesson_edges
          OPTIONS { bfs: true, uniqueVertices: 'path' }
          FILTER v._id != @seed
          LIMIT 10
          RETURN p.edges
        """,
        bind_vars={"seed": f_id},
    ))
    assert isinstance(rows, list) and len(rows) >= 1


def test_recall_diff_api(db):
    # Seed a small set to ensure BM25 returns something
    batch = "gmrd_" + uuid.uuid4().hex[:6]
    for i in range(3):
        t = f"DEMO[{batch}] thumbnails rail filmstrip {i}"
        db.aql.execute(
            "UPSERT { title:@t, scope:'tabbed' } INSERT { title:@t, scope:'tabbed', tags:['thumbnails','rail','filmstrip'], updated_at:0, demo:true, demo_batch:@b } UPDATE { demo:true, demo_batch:@b } IN lessons",
            bind_vars={"t": t, "b": batch},
        )
    bm25 = bm25_rank(db, q="thumbnails rail filmstrip", scope="tabbed", tags=[], k=5)
    fused = fuse_bm25_graph(db, bm25=bm25, depth=2, k=5)
    assert isinstance(bm25, list) and isinstance(fused, list)
