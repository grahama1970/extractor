import os
import uuid
import pytest


ARANGO_URL = os.getenv("ARANGO_URL", "http://127.0.0.1:8529")
ARANGO_DB = os.getenv("ARANGO_DB", os.getenv("ARANGO_DATABASE", "lessons"))
ARANGO_USER = os.getenv("ARANGO_USER", "root")
ARANGO_PASS = os.getenv("ARANGO_PASS", os.getenv("ARANGO_PASS", "openSesame"))


def _get_db():
    # Import lazily to avoid coupling test collection to runtime
    from scripts.lessons.arango_client import get_db

    os.environ["ARANGO_URL"] = ARANGO_URL
    os.environ["ARANGO_DB"] = ARANGO_DB
    os.environ["ARANGO_USER"] = ARANGO_USER
    os.environ["ARANGO_PASS"] = ARANGO_PASS
    return get_db()


def _ensure_setup():
    from scripts.lessons.setup import ensure_collections_and_view

    ensure_collections_and_view()


@pytest.fixture(scope="module")
def db():
    try:
        _ensure_setup()
        return _get_db()
    except Exception as e:
        pytest.skip(f"ArangoDB not reachable or not authorized: {e}")


def test_seed_and_search_bm25(db):
    from scripts.lessons.seed_demo import seed as seed_demo

    batch = "testbatch_" + uuid.uuid4().hex[:8]
    # Seed a small set
    seed_demo(count=8, scope="tabbed", batch=batch)

    # Verify lessons inserted with demo flags
    count = db.aql.execute(
        "RETURN LENGTH(FOR d IN lessons FILTER d.demo==true AND d.demo_batch==@b RETURN 1)",
        bind_vars={"b": batch},
    ).next()
    assert count == 8

    # BM25 query via view: ensure at least one result
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
              LIMIT 5
              RETURN KEEP(d, '_key','title','scope','tags')
            """,
            bind_vars={"q": "thumbnails rail filmstrip"},
        )
    )
    assert isinstance(res, list) and len(res) >= 1


@pytest.mark.skipif(
    os.getenv("RUN_FAISS_TESTS") not in ("1", "true", "TRUE"),
    reason="FAISS/transformers are heavy or require network; enable with RUN_FAISS_TESTS=1",
)
def test_faiss_proposer_creates_edges(db):
    from scripts.lessons.seed_demo import seed as seed_demo
    from scripts.lessons.propose_faiss import propose as propose_faiss

    batch = "faiss_" + uuid.uuid4().hex[:6]
    seed_demo(count=20, scope="pipeline", batch=batch)
    # Propose edges (scope-restricted) — allow zero-rejection by lowering thresholds
    propose_faiss(k=8, sim_thresh=0.0, min_top=3, scope="pipeline", dry_run=False)

    # Ensure at least some edges exist in that scope
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
