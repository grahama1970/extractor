from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

try:
    from arango import ArangoClient  # type: ignore
    from arango.database import StandardDatabase  # type: ignore
except Exception:  # pragma: no cover
    ArangoClient = None  # type: ignore
    StandardDatabase = None  # type: ignore


EVENTS_COL = "proto_events"
EPISODES_COL = "proto_episodes"
STATUS_COL = "proto_status"
LOGS_COL = "proto_logs"

app = FastAPI()
app_data: Dict[str, Any] = {}


def _get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.environ.get(name)
    return v if v is not None and v != "" else default


def _connect_arango() -> Optional[StandardDatabase]:  # type: ignore[valid-type]
    if app_data.get("arango_db") is not None:
        return app_data["arango_db"]
    if ArangoClient is None:
        return None
    host = _get_env("ARANGO_HOST", "127.0.0.1")
    port = int(_get_env("ARANGO_PORT", "8529") or "8529")
    user = _get_env("ARANGO_USERNAME") or _get_env("ARANGO_USER") or "root"
    password = _get_env("ARANGO_PASS", "")
    db_name = _get_env("ARANGO_DB") or _get_env("ARANGO_DATABASE") or "marker"
    client = ArangoClient(hosts=f"http://{host}:{port}")
    db = client.db("_system", username=user, password=password)
    _ = db.version()
    if not db.has_database(db_name):
        db.create_database(db_name, users=[{"username": user, "password": password, "active": True}])
    db2 = client.db(db_name, username=user, password=password)
    for col in (EVENTS_COL, EPISODES_COL, STATUS_COL, LOGS_COL):
        if not db2.has_collection(col):
            db2.create_collection(col)
    app_data["arango_db"] = db2
    return db2



def _safe_path(rel: str) -> Path | None:
    try:
        base = Path.cwd().resolve()
        p = (base / rel).resolve()
        return p if str(p).startswith(str(base)) else None
    except Exception:
        return None


@app.get("/")
async def root():
    return {"ok": True, "service": "gamified-logger"}


@app.get("/stream")
async def stream():
    async def event_generator():
        q: asyncio.Queue = asyncio.Queue()
        subs: List[asyncio.Queue] = app_data.setdefault("subs", [])
        subs.append(q)
        try:
            while True:
                data = await q.get()
                yield f"data: {data}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            try:
                subs.remove(q)
            except ValueError:
                pass

    return StreamingResponse(event_generator(), media_type="text/event-stream")


async def _broadcast(message: Dict[str, Any]):
    data = json.dumps(message)
    for q in list(app_data.get("subs", [])):
        try:
            q.put_nowait(data)
        except Exception:
            pass


@app.post("/ingest/log")
async def ingest_log(payload: Dict[str, Any]):
    db = _connect_arango()
    if db is None:
        return JSONResponse({"ok": False, "error": "ArangoDB unavailable"}, status_code=503)
    try:
        db.collection(LOGS_COL).insert(payload)
    except Exception:
        pass
    await _broadcast({"type": "log", "data": payload})
    # Best-effort: on stderr lines, call Graph Memory for quick recall and append to run notes
    try:
        if str(payload.get("stream","")) == "stderr":
            run_id = str(payload.get("run_id") or "gamified")
            msg = str(payload.get("message") or "")[:256]
            q = " ".join([w for w in msg.split() if w and len(w) <= 64])[:200]
            if q:
                # Import lazily to avoid hard dep
                try:
                    from graph_memory.api import MemoryClient  # type: ignore
                    client = MemoryClient(scope="gamified", k=3)
                    res = client.search(q)
                    items = res.get("items") or []
                    if items:
                        lines = ["[memory] Suggestions:"]
                        for it in items[:3]:
                            title = it.get("title") or ""
                            why = it.get("why") or ""
                            lines.append(f"- {title} ({why})")
                        # Append to notes.txt
                        from pathlib import Path
                        notes_path = Path('workspace/runs') / run_id / 'notes.txt'
                        notes_path.parent.mkdir(parents=True, exist_ok=True)
                        prev = notes_path.read_text(encoding='utf-8') if notes_path.exists() else ""
                        notes_path.write_text((prev + ("\n" if prev else "") + "\n".join(lines)).strip() + "\n", encoding='utf-8')
                except Exception:
                    pass
    except Exception:
        pass
    return {"ok": True}


@app.post("/ingest/episode")
async def ingest_episode(payload: Dict[str, Any]):
    db = _connect_arango()
    if db is None:
        return JSONResponse({"ok": False, "error": "ArangoDB unavailable"}, status_code=503)
    try:
        db.collection(EPISODES_COL).insert(payload)
        aql = f"""
        UPSERT {{ run_id: @run_id, variant: @variant }}
        INSERT {{ run_id: @run_id, variant: @variant, last_ts: @ts, last_score: @score, error_count: @error_count }}
        UPDATE {{ last_ts: @ts, last_score: @score, error_count: @error_count }} IN {STATUS_COL}
        RETURN NEW
        """
        db.aql.execute(
            aql,
            bind_vars={
                "run_id": payload.get("run_id"),
                "variant": payload.get("variant"),
                "ts": payload.get("ts"),
                "score": payload.get("score"),
                "error_count": payload.get("error_count", 0),
            },
        )
    except Exception:
        pass
    await _broadcast({"type": "episode", "data": payload})
    # Best-effort: also log to Graph Memory episodes for timeline/recency
    try:
        run_id = str(payload.get("run_id") or "gamified")
        variant = str(payload.get("variant") or "")
        score = payload.get("score")
        errc = int(payload.get("error_count", 0) or 0)
        status = 'success' if errc == 0 else 'failure'
        title = f"{run_id}/{variant} score={score}"
        details = json.dumps({k: payload.get(k) for k in ("score","error_count","ts")}, ensure_ascii=False)
        from graph_memory.api import log_episode as memory_log_episode  # type: ignore
        memory_log_episode(status=status, title=title, scope="gamified", details=details, promote_if_novel=True)
    except Exception:
        pass
    return {"ok": True}


@app.get("/scoreboard")
async def scoreboard(run_id: Optional[str] = None):
    db = _connect_arango()
    if db is None:
        return JSONResponse({"ok": False, "error": "ArangoDB unavailable"}, status_code=503)
    where = "FILTER s.run_id == @run_id" if run_id else ""
    aql = f"""
    FOR s IN {STATUS_COL}
      {where}
      RETURN s
    """
    rows = list(db.aql.execute(aql, bind_vars={"run_id": run_id} if run_id else None))
    return {"ok": True, "items": rows}


@app.get("/episodes")
async def list_episodes(run_id: Optional[str] = None, variant: Optional[str] = None, limit: int = 50):
    db = _connect_arango()
    if db is None:
        return JSONResponse({"ok": False, "error": "ArangoDB unavailable"}, status_code=503)
    filters = []
    if run_id:
        filters.append("e.run_id == @run_id")
    if variant:
        filters.append("e.variant == @variant")
    where = ("FILTER " + " AND ".join(filters)) if filters else ""
    aql = f"""
    FOR e IN {EPISODES_COL}
      {where}
      SORT e.ts DESC
      LIMIT @limit
      RETURN e
    """
    rows = list(db.aql.execute(aql, bind_vars={"run_id": run_id, "variant": variant, "limit": limit}))
    return {"ok": True, "items": rows}


@app.get("/logs")
async def list_logs(run_id: Optional[str] = None, variant: Optional[str] = None, source: Optional[str] = None, stream: Optional[str] = None, limit: int = 100):
    db = _connect_arango()
    if db is None:
        return JSONResponse({"ok": False, "error": "ArangoDB unavailable"}, status_code=503)
    filters = []
    if run_id:
        filters.append("l.run_id == @run_id")
    if variant:
        filters.append("l.variant == @variant")
    if source:
        filters.append("l.source == @source")
    if stream:
        filters.append("l.stream == @stream")
    where = ("FILTER " + " AND ".join(filters)) if filters else ""
    aql = f"""
    FOR l IN {LOGS_COL}
      {where}
      SORT l.ts DESC
      LIMIT @limit
      RETURN l
    """
    rows = list(db.aql.execute(aql, bind_vars={"run_id": run_id, "variant": variant, "source": source, "stream": stream, "limit": limit}))
    return {"ok": True, "items": rows}


# ------------------ Memory (operator endpoints) ------------------

@app.get("/memory/research")
async def memory_research(scope: str = "research", limit: int = 5):
    """List latest research lessons (arXiv-tagged) for a scope.

    This is a thin convenience around Graph Memory so the dashboard can render
    a "New Research Ideas" panel without extra setup.
    """
    try:
        from graph_memory.arango_client import get_db as _gm_db  # type: ignore
        from graph_memory.setup_schema import ensure_collections_and_view as _gm_ensure  # type: ignore
    except Exception:
        return JSONResponse({"ok": False, "error": "graph_memory unavailable"}, status_code=503)
    try:
        _gm_ensure()
        db = _gm_db()
        rows = list(db.aql.execute(
            """
            FOR d IN lessons
              FILTER d.scope==@s AND @tag IN d.tags
              SORT d.updated_at DESC
              LIMIT @n
              RETURN KEEP(d,['_key','title','chunks','pdf_url','updated_at'])
            """,
            bind_vars={"s": scope, "tag": "arxiv", "n": max(1,int(limit))}
        ))
        return {"ok": True, "items": rows}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/memory/feedback")
async def memory_feedback(payload: Dict[str, Any]):
    """Submit helpful/not helpful feedback for a memory lesson (operator action)."""
    try:
        from graph_memory.api import feedback as _gm_feedback  # type: ignore
    except Exception:
        return JSONResponse({"ok": False, "error": "graph_memory unavailable"}, status_code=503)
    try:
        title = str(payload.get('lesson_title') or '')
        scope = str(payload.get('lesson_scope') or '')
        helpful = bool(payload.get('helpful', True))
        note = str(payload.get('note') or '')
        if not title:
            return JSONResponse({"ok": False, "error": "lesson_title required"}, status_code=400)
        out = _gm_feedback(lesson_title=title, lesson_scope=scope, helpful=helpful, note=note)
        return {"ok": True, "result": out}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.get("/memory/explain")
async def memory_explain(key: str, q: Optional[str] = None, scope: str = ""):
    """Explain a memory lesson (operator). Thin wrapper for graph_memory.api.explain."""
    try:
        from graph_memory.api import explain as _gm_explain  # type: ignore
    except Exception:
        return JSONResponse({"ok": False, "error": "graph_memory unavailable"}, status_code=503)
    try:
        out = _gm_explain(key=key, q=q, scope=scope)
        return {"ok": True, "result": out}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.get('/memory/suggestions')
async def memory_suggestions(run_id: Optional[str] = None, k: int = 3):
    """Compute fresh memory suggestions from the last stderr log of a run.

    Falls back to empty list when unavailable. Operator-only, low cost.
    """
    db = _connect_arango()
    if db is None:
        return JSONResponse({"ok": False, "error": "ArangoDB unavailable"}, status_code=503)
    try:
        filters = ["l.stream=='stderr'"]
        bind = {"limit": max(1, int(k))}
        if run_id:
            filters.append("l.run_id==@run_id")
            bind["run_id"] = run_id
        where = "FILTER " + " AND ".join(filters)
        aql = f"""
        FOR l IN {LOGS_COL}
          {where}
          SORT l.ts DESC
          LIMIT 1
          RETURN l
        """
        rows = list(db.aql.execute(aql, bind_vars=bind))
        if not rows:
            return {"ok": True, "items": []}
        msg = str(rows[0].get('message') or '')[:256]
        toks = " ".join([w for w in msg.split() if w and len(w) <= 64])[:200]
        if not toks:
            return {"ok": True, "items": []}
        from graph_memory.api import MemoryClient  # type: ignore
        client = MemoryClient(scope="gamified", k=max(1, int(k)))
        res = client.search(toks)
        items = res.get('items') or []
        # shrink payload for UI
        out = []
        for it in items[: max(1, int(k))]:
            out.append({
                'title': it.get('title'),
                'why': it.get('why'),
                'scores': it.get('scores'),
                'key': it.get('_key'),
            })
        return {"ok": True, "items": out}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.get("/memory/help")
async def memory_help():
    html = """
<!doctype html>
<html><head><meta charset='utf-8'/><title>Memory Docs</title>
<style>body{font-family:system-ui;line-height:1.4;padding:16px} code{background:#eee;padding:2px 4px;border-radius:3px}</style>
</head><body>
  <h2>Graph Memory — Quick Operator Guide</h2>
  <p>Memory is shared across projects (via ArangoDB) and stays under the hood so the Happy Path remains unchanged.</p>
  <h3>Basics</h3>
  <ul>
    <li>On failures, suggestions are appended to Run Notes automatically.</li>
    <li>Mark items Helpful/Not helpful to improve ranking over time.</li>
  </ul>
  <h3>Make Targets (Gamified)</h3>
  <ul>
    <li><code>make -C prototypes/gamified memory-timeline</code> — update recency from episodes.</li>
    <li><code>make -C prototypes/gamified research-update</code> — small arXiv refresh for scope=research.</li>
  </ul>
  <h3>CLIs (run via uv)</h3>
  <ul>
    <li><code>uv run lessons-search --q "&lt;topic&gt;" --scope gamified --k 5 --json</code></li>
    <li><code>uv run lessons-explain explain --key lessons/&lt;key&gt; --q "..." --scope gamified --json</code></li>
    <li><code>uv run lessons-timeline build --scope gamified --json</code></li>
  </ul>
  <h3>Docs</h3>
  <ul>
    <li>See repository README for full details (install options, smokes, flags).</li>
  </ul>
</body></html>
"""
    return HTMLResponse(html)


@app.get("/proto/dashboard")
async def proto_dashboard():
    return HTMLResponse(
        """
<!doctype html>
<html><head><meta charset='utf-8'/><title>Gamified Logger</title></head>
<body style="font-family: system-ui; padding: 12px;">
  <h2>Gamified Logger (Arango-backed)</h2>
  <p>Use the React dashboard for the modern UI. Quick links:</p>
  <ul>
    <li><a href="/scoreboard">/scoreboard</a></li>
    <li><a href="/episodes">/episodes</a></li>
    <li><a href="/logs">/logs</a></li>
    <li><a href="/stream">/stream (SSE)</a></li>
  </ul>
</body></html>
"""
    )


# ---- Minimal collaboration endpoints (Happy Path) ----

@app.get("/spec")
async def get_spec(path: str | None = None):
    target = _safe_path(path) if path else _safe_path('gamified.yaml')
    if not target or not target.exists():
        return JSONResponse({"ok": False, "error": "spec not found"}, status_code=404)
    try:
        return {"ok": True, "path": str(target), "content": target.read_text(encoding='utf-8')}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@app.put("/spec")
async def put_spec(payload: dict):
    path = payload.get('path') or 'gamified.yaml'
    content = payload.get('content')
    target = _safe_path(path)
    if not target:
        return JSONResponse({"ok": False, "error": "invalid path"}, status_code=400)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(content or ''), encoding='utf-8')
        return {"ok": True, "path": str(target)}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@app.get('/runs/{run_id}/notes')
async def get_run_notes(run_id: str):
    from pathlib import Path
    notes_path = Path('workspace/runs') / run_id / 'notes.txt'
    if not notes_path.exists():
        return {"ok": True, "notes": ''}
    try:
        return {"ok": True, "notes": notes_path.read_text(encoding='utf-8')}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@app.post('/runs/{run_id}/notes')
async def set_run_notes(run_id: str, payload: dict):
    from pathlib import Path
    notes = str(payload.get('notes') or '')
    notes_path = Path('workspace/runs') / run_id / 'notes.txt'
    try:
        notes_path.parent.mkdir(parents=True, exist_ok=True)
        notes_path.write_text(notes, encoding='utf-8')
        return {"ok": True}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@app.post('/runs')
async def spawn_run(payload: dict):
    import subprocess, sys, time, os
    from pathlib import Path
    spec_path = payload.get('spec_path')
    spec_content = payload.get('spec_content')
    run_id = payload.get('run_id') or time.strftime('%Y%m%d-%H%M%S')
    fast = bool(payload.get('fast', False))
    if not spec_path and not spec_content:
        return JSONResponse({"ok": False, "error": "spec_path or spec_content is required"}, status_code=400)
    try:
        if spec_content and not spec_path:
            spec_target = Path('workspace/specs') / f'{run_id}.yaml'
            spec_target.parent.mkdir(parents=True, exist_ok=True)
            spec_target.write_text(str(spec_content), encoding='utf-8')
            spec_path = str(spec_target)
        target = _safe_path(spec_path)
        if not target or not target.exists():
            return JSONResponse({"ok": False, "error": "spec not found"}, status_code=404)
        env = os.environ.copy()
        if fast:
            env['GAMIFIED_FAST_BENCH'] = '1'
        cmd = [sys.executable, '-m', 'prototypes.gamified.cli', 'run', '--spec', str(target), '--run-id', run_id]
        subprocess.Popen(cmd, env=env)
        return {"ok": True, "run_id": run_id}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.get('/optimize_from_spec')
async def optimize_from_spec(path: str | None = None):
    try:
        from prototypes.gamified.spec.v1 import load_spec, render_prompt  # type: ignore
        from prototypes.gamified.tools.prompt_opt import PromptOptimizer  # type: ignore
        import yaml, difflib  # type: ignore
    except Exception as e:
        return JSONResponse({"ok": False, "error": f"optimizer unavailable: {e}"}, status_code=500)
    target = _safe_path(path) if path else _safe_path('gamified.yaml')
    if not target or not target.exists():
        return JSONResponse({"ok": False, "error": "spec not found"}, status_code=404)
    try:
        spec_obj = load_spec(str(target))
        raw_prompt = render_prompt(spec_obj)
        # Load POP rules
        rules_path = Path('prototypes/gamified/rules/prompt_optimization.yaml')
        rules_obj = yaml.safe_load(rules_path.read_text(encoding='utf-8')) if rules_path.exists() else {}
        opt = PromptOptimizer(rules_obj)
        optimized_prompt, rep = opt.validate_and_optimize(raw_prompt)
        diff = '
'.join(difflib.unified_diff(raw_prompt.splitlines(), optimized_prompt.splitlines(), fromfile='raw', tofile='optimized', lineterm=''))
        return {"ok": True, "raw": raw_prompt, "optimized": optimized_prompt, "diff": diff, "errors": [e.__dict__ for e in rep.errors]}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
