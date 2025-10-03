import os
import time
import uuid
import pytest


def _set_env():
    os.environ.setdefault("ARANGO_URL", "http://127.0.0.1:8529")
    os.environ.setdefault("ARANGO_DB", os.getenv("ARANGO_DATABASE", "lessons"))
    os.environ.setdefault("ARANGO_USER", "root")
    os.environ.setdefault("ARANGO_PASS", os.getenv("ARANGO_PASSWORD", "openSesame"))


@pytest.fixture(scope="module")
def db():
    _set_env()
    try:
        from graph_memory.setup_schema import ensure_collections_and_view
        from graph_memory.arango_client import get_db

        ensure_collections_and_view()
        return get_db()
    except Exception as e:
        pytest.skip(f"ArangoDB not reachable: {e}")


def test_seed_and_bm25(db):
    from graph_memory.lessons.seed import seed

    batch = "gmtest_" + uuid.uuid4().hex[:6]
    seed(count=6, scope="tabbed", batch=batch)
    n = db.aql.execute(
        "RETURN LENGTH(FOR d IN lessons FILTER d.demo==true AND d.demo_batch==@b RETURN 1)",
        bind_vars={"b": batch},
    ).next()
    assert n == 6

    res = list(
        db.aql.execute(
            """
            FOR d IN lessons_search
              SEARCH ANALYZER(
                d.title IN TOKENS(@q, 'text_en') OR
                d.problem IN TOKENS(@q, 'text_en') OR
                d.playbook IN TOKENS(@q, 'text_en') OR
                d.tags IN TOKENS(@q, 'text_en')
              , 'text_en')
              FILTER d.scope=='tabbed'
              SORT BM25(d) DESC
              LIMIT 3
              RETURN KEEP(d, '_key','title','scope','tags')
            """,
            bind_vars={"q": "thumbnails rail filmstrip"},
        )
    )
    assert len(res) >= 1


def test_approve_edge(db):
    from graph_memory.lessons.edges import approve as approve_fn

    ts = int(time.time())
    a = f"DEMO[gm-approve] A {ts}"
    b = f"DEMO[gm-approve] B {ts}"
    for t in (a, b):
        db.aql.execute(
            "UPSERT { title:@t, scope:'tabbed' } INSERT { title:@t, scope:'tabbed', tags:['gm'], updated_at:@ts, demo:true, demo_batch:'gm-approve' } UPDATE { updated_at:@ts, demo:true, demo_batch:'gm-approve' } IN lessons",
            bind_vars={"t": t, "ts": ts},
        )
    f_id = db.aql.execute("FOR d IN lessons FILTER d.title==@t AND d.scope=='tabbed' LIMIT 1 RETURN d._id", bind_vars={"t": a}).next()
    t_id = db.aql.execute("FOR d IN lessons FILTER d.title==@t AND d.scope=='tabbed' LIMIT 1 RETURN d._id", bind_vars={"t": b}).next()
    db.aql.execute(
        """
        UPSERT { _from:@f, _to:@t, type:'related' }
        INSERT { _from:@f, _to:@t, type:'related', weight:0.6, approved:false, status:'pending', created_at:@ts }
        UPDATE { weight:0.6, approved:false, status:'pending', created_at:@ts }
        IN lesson_edges
        """,
        bind_vars={"f": f_id, "t": t_id, "ts": ts},
    )

    approve_fn(edge_id="", from_title=a, from_scope="tabbed", to_title=b, to_scope="tabbed", human_rationale="ok")
    e = list(
        db.aql.execute(
            "FOR e IN lesson_edges FILTER e._from==@f AND e._to==@t AND e.type=='related' LIMIT 1 RETURN e",
            bind_vars={"f": f_id, "t": t_id},
        )
    )[0]
    assert e.get("approved") is True and e.get("status") == "active"


@pytest.mark.skipif(os.getenv("RUN_FAISS_TESTS") not in ("1", "true", "TRUE"), reason="FAISS/transformers opt-in")
def test_faiss_proposer(db):
    from graph_memory.lessons.seed import seed
    from graph_memory.lessons.proposer import propose

    batch = "gmfaiss_" + uuid.uuid4().hex[:6]
    seed(count=15, scope="pipeline", batch=batch)
    propose(k=8, sim_thresh=0.0, min_top=3, scope="pipeline", dry_run=False)
    n_edges = db.aql.execute(
        """
        RETURN LENGTH(
          FOR e IN lesson_edges
            LET k = SPLIT(e._from, '/')[1]
            LET l = DOCUMENT('lessons', k)
            FILTER l.scope=='pipeline' AND e.type=='related'
            RETURN 1)
        """
    ).next()
    assert n_edges >= 5
