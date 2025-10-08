"""
Self-contained FastAPI backend for the Tabbed prototype.

Endpoints:
- GET / → basic index
- GET /api/build → { git, started_at }
- GET /api/list → list PDFs from SERVER_PDFS_ROOT (defaults to prototypes/tabbed/pdfs)
- GET /api/pdf?rel=... → stream a PDF from the root
- POST /api/ux/generate → optional LLM call via LiteLLM; falls back to mock when not configured
- POST /api/ux/mock/generate → canned table JSON (for demos)

Notes:
- Adds no-store headers to all responses (dev convenience)
- CORS permissive for local dev
- Optional caching: attempts Redis; otherwise uses in-memory caching
"""

from __future__ import annotations

import os
import subprocess
import shutil
import datetime
import base64
from typing import List, Dict, Any
import sys

from fastapi import FastAPI, BackgroundTasks, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse, Response
from fastapi.middleware.cors import CORSMiddleware
import json
import time
import tempfile
import zipfile
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field
from typing import Dict, List
try:
    from extractor.pipeline.utils.embeddings import ensure_embedder  # type: ignore
except Exception:
    ensure_embedder = lambda: None  # fallback


def _ensure_pdf_objects_view(db) -> str:
    """Ensure an ArangoSearch view exists for pdf_objects with English analyzer.

    Returns the view name if available/created; otherwise returns an empty string.
    """
    try:
        view_name = os.getenv("PDF_OBJECTS_VIEW", "v_pdf_objects")
        if hasattr(db, "has_view") and db.has_view(view_name):  # type: ignore[attr-defined]
            return view_name
        # Create ArangoSearch view
        props = {
            "links": {
                "pdf_objects": {
                    "analyzers": ["identity"],
                    "fields": {
                        "text_content": {"analyzers": ["text_en"]},
                        "source_pdf": {"analyzers": ["identity"]},
                    },
                }
            }
        }
        if hasattr(db, "create_arangosearch_view"):
            db.create_arangosearch_view(view_name, properties=props)  # type: ignore[attr-defined]
            return view_name
        return ""
    except Exception:
        return ""

# Optional ArangoDB (lessons/incidents + search)
try:
    from arango import ArangoClient  # type: ignore
except Exception:  # pragma: no cover - optional runtime dep
    ArangoClient = None  # type: ignore

try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None


def _default_pdfs_root() -> str:
    here = os.path.abspath(os.path.dirname(__file__))
    # repo_root/prototypes/tabbed/pdfs
    root = os.path.abspath(os.path.join(here, "..", "pdfs"))
    if os.path.isdir(root):
        return root
    # fallback to repo_root/data/pdfs
    alt = os.path.abspath(os.path.join(here, "..", "..", "..", "data", "pdfs"))
    return alt


SERVER_PDFS_ROOT = os.getenv("SERVER_PDFS_ROOT", _default_pdfs_root())
HERE = Path(__file__).resolve()
REPO_ROOT = HERE.parents[3]
try:
    if str(REPO_ROOT / 'src') not in sys.path:
        sys.path.insert(0, str(REPO_ROOT / 'src'))
except Exception:
    pass

# Artifacts root for listing/downloading server-generated files (e.g., COCO exports)
def _default_artifacts_root() -> str:
    here = os.path.abspath(os.path.dirname(__file__))
    # repo_root/scripts/artifacts
    return os.path.abspath(os.path.join(here, '..', '..', '..', 'scripts', 'artifacts'))

ARTIFACTS_ROOT = os.getenv('ARTIFACTS_ROOT', _default_artifacts_root())

app = FastAPI()


def _latest_results_dir() -> Optional[Path]:
    try:
        p = Path(ARTIFACTS_ROOT) / "latest_results.json"
        if not p.exists():
            return None
        j = json.loads(p.read_text())
        rd = j.get("results_dir")
        if not rd:
            return None
        rp = Path(rd).resolve()
        return rp if rp.exists() else None
    except Exception:
        return None


def _chat_fallback_from_latest(q: str, top_k: int = 8) -> Dict[str, Any]:
    """Best-effort chat fallback when Arango is unavailable.

    Loads Stage 10 flattened JSON from the latest results pointer and returns
    a trivial top match by substring/score. This is intentionally simple and offline-friendly.
    """
    rd = _latest_results_dir()
    if not rd:
        return {"ok": True, "answer": "No relevant content found.", "citations": [], "count": 0}
    flat = rd / "10_arangodb_exporter" / "json_output" / "10_flattened_data.json"
    if not flat.exists():
        return {"ok": True, "answer": "No relevant content found.", "citations": [], "count": 0}
    try:
        data = json.loads(flat.read_text())
        items = data if isinstance(data, list) else data.get("items") or []
        ql = q.lower()
        scored = []
        for it in items:
            txt = str(it.get("text_content", ""))
            score = 0.0
            if ql and txt:
                tl = txt.lower()
                score += 1.0 if ql in tl else 0.0
                qs = set(ql.split())
                ts = set(tl.split())
                if qs and ts:
                    score += len(qs & ts) / max(1.0, len(qs))
            if score > 0:
                scored.append((score, it))
        scored.sort(key=lambda x: x[0], reverse=True)
        top = [it for _, it in scored[: max(1, int(top_k))]]
        answer = (top[0].get("text_content") or "").strip() if top else "No relevant content found."
        cits = [{"page": it.get("page_num"), "type": it.get("object_type") } for it in top[:3]]
        return {"ok": True, "answer": answer, "citations": cits, "count": len(scored)}
    except Exception:
        return {"ok": True, "answer": "No relevant content found.", "citations": [], "count": 0}


# CORS: wildcard requires allow_credentials=False. If credentials are needed, set explicit origins via env.
_cors_origins = os.getenv("CORS_ALLOW_ORIGINS", "*")
if _cors_origins.strip() == "*":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    origins = [o.strip() for o in _cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.middleware("http")
async def no_store_headers(request, call_next):
    resp = await call_next(request)
    try:
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, proxy-revalidate"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        resp.headers["Surrogate-Control"] = "no-store"
    except Exception:
        pass
    return resp


@app.get("/")
async def root():
    return HTMLResponse("<h3>Tabbed Prototype API</h3><ul><li>/api/list</li><li>/api/pdf?rel=...</li><li>/api/ux/generate</li></ul>")


def _git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"]).decode().strip()
    except Exception:
        return "unknown"

_BUILD_INFO = {
    "git": _git_sha(),
    "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
}


@app.get("/api/build")
async def api_build():
    # Return precomputed build metadata to avoid blocking the event loop per request.
    return _BUILD_INFO


# -----------------------------
# Arango (Lessons & Incidents)
# -----------------------------
_ARANGO_DB = None  # cached handle
_ARANGO_READY = False


def _get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name, default if default is not None else None)
    return v


def _arango_connect():
    """Best-effort connect to ArangoDB using either ARANGO_URL or ARANGO_HOST/PORT envs.

    Env (supported):
      - ARANGO_URL (preferred), e.g. http://127.0.0.1:8529
      - ARANGO_HOST, ARANGO_PORT (fallback)
      - ARANGO_DB or ARANGO_DATABASE (db name)
      - ARANGO_USER, ARANGO_PASS or ARANGO_PASS
    """
    global _ARANGO_DB
    if _ARANGO_DB is not None:
        return _ARANGO_DB
    if ArangoClient is None:
        return None
    # Gather env
    url = _get_env("ARANGO_URL")
    host = _get_env("ARANGO_HOST", "127.0.0.1")
    port = _get_env("ARANGO_PORT", "8529")
    db_name = _get_env("ARANGO_DB") or _get_env("ARANGO_DATABASE") or "lessons"
    user = _get_env("ARANGO_USER", "root") or "root"
    password = _get_env("ARANGO_PASS") or _get_env("ARANGO_PASS") or ""

    try:
        client = ArangoClient(hosts=(url or f"http://{host}:{port}"))  # type: ignore
        # Try connect to db, create if missing (requires root perms)
        sys_db = client.db("_system", username=user, password=password)
        if not sys_db.has_database(db_name):
            try:
                sys_db.create_database(db_name)
            except Exception:
                # may lack perms; proceed anyway (will 404 later)
                pass
        _ARANGO_DB = client.db(db_name, username=user, password=password)
        # sanity: try version() to confirm connect
        _ = _ARANGO_DB.version()  # noqa: F841
        return _ARANGO_DB
    except Exception:
        return None


def _ensure_lessons_schema(db):
    """Ensure lessons + incidents collections and lessons_search view exist.
    Mirrors scripts/lessons/setup.py and tolerates partial availability.
    """
    global _ARANGO_READY
    if _ARANGO_READY:
        return True
    try:
        if not db:
            return False
        # Collections
        if not db.has_collection("lessons"):
            db.create_collection("lessons")
        if not db.has_collection("incidents"):
            db.create_collection("incidents")
        # View
        view_name = "lessons_search"
        # Detect view by name; arango-py may not expose has_view directly across versions
        try:
            existing = [v.get("name") for v in db.views()]
        except Exception:
            existing = []
        if view_name not in existing:
            db.create_arangosearch_view(
                view_name,
                properties={
                    "links": {
                        "lessons": {
                            "includeAllFields": False,
                            "analyzers": ["text_en"],
                            "fields": {
                                "title": {"analyzers": ["text_en"]},
                                "problem": {"analyzers": ["text_en"]},
                                "playbook": {"analyzers": ["text_en"]},
                                "tags": {"analyzers": ["text_en", "identity"]},
                                "keywords": {"analyzers": ["text_en", "identity"]},
                                "scope": {"analyzers": ["identity"]},
                            },
                        }
                    }
                },
            )
        _ARANGO_READY = True
        return True
    except Exception:
        return False


@app.get("/api/lessons/search")
async def api_lessons_search(q: str, tags: str | None = None, k: int = 10):
    """
    Search lessons using ArangoSearch BM25/TF-IDF.

    Query params:
      - q: search text
      - tags: optional comma-separated tag list
      - k: top K (default 10)

    Returns: { ok, items: [ {title, problem, playbook, tags, scope, status, updated_at, _key} ] }
    """
    db = _arango_connect()
    if not db:
        return JSONResponse({"ok": False, "error": "arango_unavailable"}, status_code=503)
    _ensure_lessons_schema(db)
    try:
        tag_list = [t.strip() for t in (tags or "").split(",") if t.strip()]
        bind = {"q": q, "k": int(max(1, min(50, k))), "tags": tag_list}
        aql = (
            "FOR d IN lessons_search "
            "SEARCH ANALYZER("
            " d.title IN TOKENS(@q, 'text_en') OR"
            " d.problem IN TOKENS(@q, 'text_en') OR"
            " d.playbook IN TOKENS(@q, 'text_en') OR"
            " d.tags IN TOKENS(@q, 'text_en') OR"
            " d.keywords IN TOKENS(@q, 'text_en')"
            ", 'text_en') "
            "FILTER LENGTH(@tags)==0 OR d.tags ANY IN @tags "
            "SORT BM25(d) DESC, TFIDF(d) DESC "
            "LIMIT @k "
            "RETURN KEEP(d, '_key','title','problem','playbook','tags','scope','status','updated_at')"
        )
        cursor = db.aql.execute(aql, bind_vars=bind)
        items = list(cursor)
        return {"ok": True, "items": items}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/api/lessons/add")
async def api_lessons_add(payload: Dict[str, Any]):
    """
    Upsert a lesson by (title, scope).
    Body: { title, problem, playbook, tags: [..], scope: 'tabbed', status: 'active' }
    """
    db = _arango_connect()
    if not db:
        return JSONResponse({"ok": False, "error": "arango_unavailable"}, status_code=503)
    _ensure_lessons_schema(db)
    try:
        title = (payload.get("title") or "").strip()
        problem = (payload.get("problem") or "").strip()
        playbook = (payload.get("playbook") or "").strip()
        scope = (payload.get("scope") or "tabbed").strip() or "tabbed"
        status = (payload.get("status") or "active").strip() or "active"
        tags = payload.get("tags") or []
        if not isinstance(tags, list):
            tags = []
        if not title:
            return JSONResponse({"ok": False, "error": "missing_title"}, status_code=400)
        ts = int(time.time())
        user = os.getenv("USER", "unknown")
        # Add keywords field for improved BM25 recall: tags + synonyms + scope
        def build_keywords(tags_list: list[str], scope_val: str) -> str:
            syn = {
                "cdp": ["chrome", "chromium", "devtools", "browserless", "puppeteer", "playwright"],
                "proxy": ["vite", "backend", "target", "api", "port", "8000", "8001"],
                "json": ["response_format", "schema", "structured", "wrap_json"],
                "smokes": ["smoke", "ci", "tests", "playwright", "puppeteer"],
                "timeout": ["hang", "stall", "latency"],
            }
            bag: list[str] = []
            for t in tags_list or []:
                bag.append(t)
                bag.extend(syn.get(str(t).lower(), []))
            if scope_val:
                bag.append(scope_val)
            out: list[str] = []
            seen: set[str] = set()
            for w in bag:
                if w and w not in seen:
                    seen.add(w)
                    out.append(w)
            return " ".join(out)

        keywords = build_keywords(tags, scope)
        aql = (
            "UPSERT { title: @title, scope: @scope } "
            "INSERT { title: @title, problem: @problem, playbook: @playbook, tags: @tags, keywords: @keywords, scope: @scope, status: @status, added_by: @user, updated_at: @ts } "
            "UPDATE { problem: @problem, playbook: @playbook, tags: @tags, keywords: @keywords, status: @status, added_by: @user, updated_at: @ts } "
            "IN lessons RETURN NEW"
        )
        bind = {
            "title": title,
            "problem": problem,
            "playbook": playbook,
            "tags": tags,
            "keywords": keywords,
            "scope": scope,
            "status": status,
            "user": user,
            "ts": ts,
        }
        cursor = db.aql.execute(aql, bind_vars=bind)
        doc = list(cursor)[0]
        return {"ok": True, "item": doc}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/api/incident/log")
async def api_incident_log(payload: Dict[str, Any]):
    """
    Record an incident in the 'incidents' collection.
    Body: { message: str, level?: str, meta?: dict }
    """
    db = _arango_connect()
    if not db:
        return JSONResponse({"ok": False, "error": "arango_unavailable"}, status_code=503)
    _ensure_lessons_schema(db)
    try:
        msg = (payload.get("message") or "").strip()
        if not msg:
            return JSONResponse({"ok": False, "error": "missing_message"}, status_code=400)
        level = (payload.get("level") or "ERROR").strip() or "ERROR"
        meta = payload.get("meta") or {}
        if not isinstance(meta, dict):
            meta = {"meta": str(meta)}
        doc = {
            "message": msg,
            "level": level,
            "meta": meta,
            "ts": int(time.time()),
            "user": os.getenv("USER", "unknown"),
        }
        col = db.collection("incidents")
        ins = col.insert(doc)
        return {"ok": True, "_key": ins.get("_key")}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


def _is_within_root(path: str, root: str) -> bool:
    try:
        rp = os.path.realpath(path)
        rr = os.path.realpath(root)
        return os.path.commonpath([rp, rr]) == rr
    except Exception:
        return False


def _list_pdfs(root: str) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    if not os.path.isdir(root):
        return items
    for name in sorted(os.listdir(root)):
        if not name.lower().endswith(".pdf"):
            continue
        fp = os.path.join(root, name)
        try:
            st = os.stat(fp)
        except Exception:
            continue
        items.append({"name": name, "rel": name, "size": st.st_size, "mtime": st.st_mtime})
    return items


@app.get("/api/list")
async def api_list(dir: str | None = None):
    base = SERVER_PDFS_ROOT if not dir else os.path.join(SERVER_PDFS_ROOT, dir)
    if not _is_within_root(base, SERVER_PDFS_ROOT):
        return JSONResponse({"ok": False, "error": "invalid_dir"}, status_code=400)
    return {"ok": True, "root": SERVER_PDFS_ROOT, "items": _list_pdfs(base)}


@app.get("/api/pdf")
async def api_pdf(rel: str):
    fp = os.path.join(SERVER_PDFS_ROOT, rel)
    if not _is_within_root(fp, SERVER_PDFS_ROOT) or not os.path.isfile(fp):
        return JSONResponse({"ok": False, "error": "not_found"}, status_code=404)
    return FileResponse(fp, media_type="application/pdf", filename=os.path.basename(fp))


def _abs_pdf_path(rel: str) -> str:
    fp = os.path.join(SERVER_PDFS_ROOT, rel)
    if not _is_within_root(fp, SERVER_PDFS_ROOT) or not os.path.isfile(fp):
        raise FileNotFoundError("not_found")
    return fp

# -----------------------------
# ArangoDB: documents/pages/chunks/annotations schema
# -----------------------------

def _ensure_docs_schema(db):
    try:
        if not db:
            return False
        cols = [c['name'] for c in db.collections()]
        def ensure_col(name):
            if name not in cols:
                db.create_collection(name)
        for c in ("docs","pages","chunks","annotations","answers","feedback"):
            ensure_col(c)
        # ArangoSearch view for chunks (BM25/TFIDF on text)
        view_name = "chunks_search"
        try:
            existing = [v.get("name") for v in db.views()]
        except Exception:
            existing = []
        if view_name not in existing:
            db.create_arangosearch_view(
                view_name,
                properties={
                    "links": {
                        "chunks": {
                            "includeAllFields": False,
                            "analyzers": ["text_en"],
                            "fields": {
                                "text": {"analyzers": ["text_en"]},
                                "type": {"analyzers": ["identity"]},
                            },
                        }
                    }
                },
            )
        return True
    except Exception:
        return False


# -----------------------------
# Artifacts: simple browse/download helpers
# -----------------------------

def _is_within_artifacts(path: str) -> bool:
    try:
        rp = os.path.realpath(path)
        rr = os.path.realpath(ARTIFACTS_ROOT)
        return os.path.commonpath([rp, rr]) == rr
    except Exception:
        return False


@app.get("/api/artifacts/browse")
async def api_artifacts_browse(dir: str):
    base = dir if os.path.isabs(dir) else os.path.join(ARTIFACTS_ROOT, dir)
    if not _is_within_artifacts(base) or not os.path.isdir(base):
        return JSONResponse({"ok": False, "error": "invalid_dir"}, status_code=400)
    try:
        names = sorted(os.listdir(base))
        rows = []
        for name in names:
            p = os.path.join(base, name)
            if os.path.isdir(p):
                rows.append(f'<li>📁 <a href="/api/artifacts/browse?dir={p}">{name}</a></li>')
            else:
                rows.append(f'<li>📄 <a href="/api/artifacts/download?path={p}">{name}</a></li>')
        html = f"<h3>Artifacts</h3><p>Root: {ARTIFACTS_ROOT}</p><ul>{''.join(rows)}</ul>"
        return HTMLResponse(html)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.get("/api/artifacts/download")
async def api_artifacts_download(path: str):
    fp = path if os.path.isabs(path) else os.path.join(ARTIFACTS_ROOT, path)
    if not _is_within_artifacts(fp) or not os.path.isfile(fp):
        return JSONResponse({"ok": False, "error": "not_found"}, status_code=404)
    return FileResponse(fp, filename=os.path.basename(fp))



@app.post("/api/export/json")
async def api_export_json(payload: Dict[str, Any]):
    """
    Accepts annotations and returns a downloadable JSON file.
    Payload example: { rel: "file.pdf", boxes_by_page: { "1": [ { type, instance_id, bounding_box:[x,y,w,h] } ] } }
    """
    rel = payload.get("rel") or "document"
    boxes = payload.get("boxes_by_page") or {}
    out = {"rel": rel, "boxes_by_page": boxes}
    data = json.dumps(out, indent=2).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Content-Disposition": f"attachment; filename=\"{Path(rel).stem or 'annotations'}.json\"",
    }
    return Response(content=data, headers=headers, media_type="application/json")


@app.post("/api/export/pdf")
async def api_export_pdf(payload: Dict[str, Any], tasks: BackgroundTasks):
    """
    Render simple annotation overlays into a PDF using PyMuPDF and return it.
    Payload: { rel: str, boxes_by_page: { page_num(str|int): [ { type, instance_id, bounding_box:[x,y,w,h] } ] } }
    """
    if fitz is None:
        return JSONResponse({"ok": False, "error": "pymupdf_not_available"}, status_code=500)
    try:
        rel = payload.get("rel")
        boxes = payload.get("boxes_by_page") or {}
        src = _abs_pdf_path(rel)
        with fitz.open(src) as doc:
            # Draw annotations as semi-transparent boxes with label text
            for k, arr in boxes.items():
                try:
                    pnum = int(k)
                except Exception:
                    continue
                if pnum < 1 or pnum > doc.page_count:
                    continue
                page = doc.load_page(pnum - 1)
                pw, ph = page.rect.width, page.rect.height
                for b in arr or []:
                    bb = b.get("bounding_box") or b.get("bbox") or []
                    if not (isinstance(bb, (list, tuple)) and len(bb) == 4):
                        continue
                    x, y, w, h = bb
                    rect = fitz.Rect(x * pw, y * ph, (x + w) * pw, (y + h) * ph)
                    # Choose color by type
                    t = (b.get("type") or "Section").lower()
                    if t == "table":
                        color = (0.2, 0.4, 0.9)
                    elif t == "figure":
                        color = (0.5, 0.3, 0.9)
                    else:
                        color = (0.1, 0.7, 0.5)
                    page.draw_rect(rect, color=color, fill=(color[0], color[1], color[2], 0.08), width=1.2)
                    label = f"{b.get('type') or ''} · {b.get('instance_id') or ''}"
                    page.insert_text((rect.x0 + 4, rect.y0 - 8), label, fontsize=8, color=color)
            # Write to temp file
            fd, tmp_path = tempfile.mkstemp(suffix=".pdf")
            os.close(fd)
            doc.save(tmp_path)
        filename = f"annotated_{Path(rel).stem}.pdf"
        # Clean up temp file after response is sent
        tasks.add_task(lambda p: (os.path.exists(p) and os.remove(p)), tmp_path)
        return FileResponse(tmp_path, media_type="application/pdf", filename=filename)
    except FileNotFoundError:
        return JSONResponse({"ok": False, "error": "not_found"}, status_code=404)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/api/export/zip")
async def api_export_zip(payload: Dict[str, Any], tasks: BackgroundTasks):
    """
    Build a ZIP containing annotations.json and annotated_<name>.pdf (if PyMuPDF available).
    Payload: { rel: str, boxes_by_page: {...} }
    """
    try:
        rel = payload.get("rel")
        boxes = payload.get("boxes_by_page") or {}
        stem = Path(rel or "document").stem or "document"
        fd, zip_path = tempfile.mkstemp(suffix=".zip")
        os.close(fd)
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            # annotations.json
            zf.writestr("annotations.json", json.dumps({"rel": rel, "boxes_by_page": boxes}, indent=2))
            # annotated pdf (optional)
            if fitz is not None and rel:
                try:
                    src = _abs_pdf_path(rel)
                    with fitz.open(src) as doc:
                        for k, arr in boxes.items():
                            try:
                                pnum = int(k)
                            except Exception:
                                continue
                            if pnum < 1 or pnum > doc.page_count:
                                continue
                            page = doc.load_page(pnum - 1)
                            pw, ph = page.rect.width, page.rect.height
                            for b in arr or []:
                                bb = b.get("bounding_box") or b.get("bbox") or []
                                if not (isinstance(bb, (list, tuple)) and len(bb) == 4):
                                    continue
                                x, y, w, h = bb
                                rect = fitz.Rect(x * pw, y * ph, (x + w) * pw, (y + h) * ph)
                                t = (b.get("type") or "Section").lower()
                                if t == "table":
                                    color = (0.2, 0.4, 0.9)
                                elif t == "figure":
                                    color = (0.5, 0.3, 0.9)
                                else:
                                    color = (0.1, 0.7, 0.5)
                                page.draw_rect(rect, color=color, fill=(color[0], color[1], color[2], 0.08), width=1.2)
                                label = f"{b.get('type') or ''} · {b.get('instance_id') or ''}"
                                page.insert_text((rect.x0 + 4, rect.y0 - 8), label, fontsize=8, color=color)
                        # write annotated to temp and add to zip
                        fd2, tmp_pdf = tempfile.mkstemp(suffix=".pdf")
                        os.close(fd2)
                        doc.save(tmp_pdf)
                    zf.write(tmp_pdf, arcname=f"annotated_{stem}.pdf")
                    try:
                        os.remove(tmp_pdf)
                    except Exception:
                        pass
                except Exception:
                    # If annotated generation fails, still return annotations.json in the ZIP
                    pass
        filename = f"export_{stem}.zip"
        tasks.add_task(lambda p: (os.path.exists(p) and os.remove(p)), zip_path)
        return FileResponse(zip_path, media_type="application/zip", filename=filename)
    except FileNotFoundError:
        return JSONResponse({"ok": False, "error": "not_found"}, status_code=404)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


# Shared LiteLLM integration (project-standard)
try:
    from extractor.pipeline.utils.litellm_call import litellm_call  # type: ignore
    from extractor.pipeline.utils.litellm_cache import initialize_litellm_cache  # type: ignore
except Exception:  # pragma: no cover
    litellm_call = None  # type: ignore
    def initialize_litellm_cache():  # type: ignore
        return None

# Initialize cache best-effort
try:
    initialize_litellm_cache()
except Exception:
    pass


@app.post("/api/ux/generate")
async def http_generate(payload: Dict[str, Any]):
    # Mock path enabled?
    if os.getenv("UX_MOCK_GENERATE", "0") in ("1", "true", "TRUE", "yes"):
        sample = {
            "title": "INFERRED_Table_Example",
            "columns": ["Col A", "Col B", "Col C"],
            "data": [["A1", "B1", "C1"], ["A2", "B2", "C2"]],
        }
        return JSONResponse({"ok": True, "data": sample})

    model = (
        payload.get("model")
        or os.getenv("LITELLM_DEFAULT_MODEL")
        or os.getenv("DEFAULT_LITELLM_MODEL")
        or os.getenv("LITELLM_VLM_MODEL", "gemini/gemini-2.5-flash")
    )
    prompt = payload.get("prompt") or ""
    image = payload.get("image")

    temp_path: str | None = None
    try:
        params: Dict[str, Any] = {"model": model, "text": prompt}
        if image:
            # Support data URLs by writing to a temporary file
            if isinstance(image, str) and image.startswith("data:image/") and "," in image:
                import base64, tempfile
                header, b64 = image.split(",", 1)
                ext = "png"
                try:
                    kind = header.split(";")[0].split("/")[-1]
                    if kind in ("png", "jpeg", "jpg", "webp"):
                        ext = "jpg" if kind == "jpeg" else kind
                except Exception:
                    pass
                fd, temp_path = tempfile.mkstemp(suffix=f".{ext}")
                with os.fdopen(fd, "wb") as f:
                    f.write(base64.b64decode(b64))
                params["image"] = temp_path
            else:
                params["image"] = image
        # Enforce JSON object outputs for downstream parsing
        if litellm_call is None:
            return JSONResponse({"ok": False, "error": "litellm_unavailable"}, status_code=503)
        results = await litellm_call(
            [params],
            wrap_json=True,
            concurrency=1,
            desc="Tabbed UX Generate",
            response_format="json_object",
        )
        raw = results[0] if isinstance(results, list) and results else results
        # Coerce into a JSON object and include the model used
        content_obj: Dict[str, Any] | None = None
        try:
            if isinstance(raw, str):
                content_obj = json.loads(raw)
            elif isinstance(raw, dict):
                # Some adapters return {content:{...}}; prefer nested content if present
                if isinstance(raw.get("content"), dict):
                    content_obj = raw.get("content")  # type: ignore
                else:
                    content_obj = raw  # type: ignore
        except Exception:
            content_obj = None

        if content_obj is not None and isinstance(content_obj, dict):
            try:
                # Do not overwrite if provider already returned a model field
                content_obj.setdefault("model", model)
            except Exception:
                pass
            # Return a normalized shape with a json field for the UI
            return JSONResponse({"ok": True, "data": {"json": content_obj, "raw": raw}})

        # Fallback: still provide a minimal JSON with the model, plus raw
        minimal = {"ok": True, "model": model}
        return JSONResponse({"ok": True, "data": {"json": minimal, "raw": raw}})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
    finally:
        try:
            if temp_path and os.path.isfile(temp_path):
                os.remove(temp_path)
        except Exception:
            pass


@app.post("/api/ux/mock/generate")
async def http_generate_mock():
    sample = {
        "title": "INFERRED_Table_Example",
        "columns": ["Col A", "Col B", "Col C"],
        "data": [["A1", "B1", "C1"], ["A2", "B2", "C2"]],
    }
    return JSONResponse({"ok": True, "data": sample})


# LLM health: trivial JSON round-trip via litellm_call
@app.get("/api/health/llm")
async def api_health_llm(model: str | None = None, timeout: float = 20.0):
    prompt = 'Return only {"ok":true} as JSON.'
    eff_model = (
        model
        or os.getenv("LITELLM_DEFAULT_MODEL")
        or os.getenv("DEFAULT_LITELLM_MODEL")
        or os.getenv("LITELLM_VLM_MODEL", "gemini/gemini-2.5-flash")
    )
    t0 = time.perf_counter()
    # If no provider credentials are configured, return a 200 with a skipped marker
    # to avoid hard client errors during local dev/preview.
    provider_keys = [
        os.getenv("OPENAI_API_KEY"),
        os.getenv("ANTHROPIC_API_KEY"),
        os.getenv("GEMINI_API_KEY"),
        os.getenv("GOOGLE_API_KEY"),
        os.getenv("AZURE_OPENAI_API_KEY"),
        os.getenv("OLLAMA_BASE_URL"),
    ]
    if not any(k for k in provider_keys if (k or "").strip()):
        return {
            "ok": False,
            "skipped": True,
            "reason": "no_provider_credentials",
            "model": eff_model,
            "elapsed_ms": int((time.perf_counter() - t0) * 1000),
        }
    try:
        results = await litellm_call(
            [{"text": prompt, "model": eff_model}],
            wrap_json=False,
            response_format="json_object",
            request_timeout=timeout,
            concurrency=1,
            desc="LLM Health (Tabbed)",
        )
        out = results[0] if results else ""
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        ok = False
        data = None
        try:
            data = json.loads((out or "").strip())
            if isinstance(data, dict):
                ok = bool(data.get("ok") is True)
                if not ok:
                    content = data.get("content")
                    if isinstance(content, dict):
                        ok = bool(content.get("ok") is True)
        except Exception:
            ok = False

        payload = {
            "ok": ok,
            "model": eff_model,
            "elapsed_ms": elapsed_ms,
            "content": data,
        }
        if ok:
            return payload
        # Non-OK response from provider: surface as 200 with ok:false to avoid
        # failing browser-side health checks while still conveying status.
        return payload
    except Exception as e:
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        return JSONResponse(
            {"ok": False, "error": str(e), "model": eff_model, "elapsed_ms": elapsed_ms},
            status_code=500,
        )

# ---- Lessons Graph Helpers & Endpoints (appended) ----

def _ensure_graph_bits(db):
    try:
        if not db.has_collection('lesson_edges'):
            db.create_collection('lesson_edges', edge=True)
    except Exception:
        pass
    try:
        if not db.has_collection('rejected_pairs'):
            db.create_collection('rejected_pairs')
    except Exception:
        pass


def _pair_id(a_id: str, b_id: str) -> str:
    a, b = (a_id, b_id) if a_id <= b_id else (b_id, a_id)
    import hashlib as _hl
    m = _hl.sha1()
    m.update((a + '|' + b).encode('utf-8'))
    return m.hexdigest()


def _resolve_lesson_id(db, key: Optional[str], title: Optional[str], scope: Optional[str]) -> Optional[str]:
    if key:
        return f"lessons/{key}"
    if title:
        try:
            cur = db.collection('lessons').find({ 'title': title, 'scope': scope or 'tabbed' })
            arr = list(cur) if cur else []
            if arr:
                return f"lessons/{arr[0]['_key']}"
        except Exception:
            return None
    return None


@app.post("/api/lessons/edge/related")
async def api_edge_related(payload: Dict[str, Any]):
    db = _arango_connect()
    if not db:
        return JSONResponse({"ok": False, "error": "arango_unavailable"}, status_code=503)
    _ensure_lessons_schema(db)
    _ensure_graph_bits(db)
    try:
        fk = _resolve_lesson_id(db, payload.get('from_key'), payload.get('from_title'), payload.get('from_scope'))
        tk = _resolve_lesson_id(db, payload.get('to_key'), payload.get('to_title'), payload.get('to_scope'))
        if not fk or not tk or fk == tk:
            return JSONResponse({"ok": False, "error": "invalid_from_to"}, status_code=400)
        ts = int(time.time())
        pair = _pair_id(fk, tk)
        weight = float(payload.get('weight') or 0.0)
        raw_sim = payload.get('raw_sim'); raw_sim = float(raw_sim) if raw_sim is not None else None
        confidence = payload.get('confidence'); confidence = float(confidence) if confidence is not None else None
        approved = bool(payload.get('approved') or False)
        rationale = (payload.get('rationale') or '').strip()
        evidence_refs = payload.get('evidence_refs') if isinstance(payload.get('evidence_refs'), list) else []
        src = (payload.get('source') or 'faiss').strip() or 'faiss'
        status = 'active' if approved else 'pending'
        doc_base = {
            'type': 'related',
            'source': src,
            'weight': max(0.0, min(1.0, weight)),
            'raw_sim': raw_sim,
            'confidence': confidence,
            'approved': approved,
            'rationale': rationale,
            'rationales': [{ 'by': 'agent', 'text': rationale, 'at': ts }] if rationale else [],
            'evidence_refs': evidence_refs,
            'status': status,
            'created_at': ts,
            'updated_at': ts,
            'last_verified_at': ts,
            'pair_id': pair,
            'decay_policy': 'standard',
        }
        out = []
        for frm, to in ((fk, tk), (tk, fk)):
            aql = (
                "UPSERT { _from: @from, _to: @to, type: 'related' } "
                "INSERT MERGE({ _from: @from, _to: @to }, @doc) "
                "UPDATE MERGE(OLD, @doc, { created_at: OLD.created_at }) IN lesson_edges RETURN NEW"
            )
            cur = db.aql.execute(aql, bind_vars={ 'from': frm, 'to': to, 'doc': doc_base })
            out.append(list(cur)[0])
        return { 'ok': True, 'edges': out }
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/api/lessons/edge/reject")
async def api_edge_reject(payload: Dict[str, Any]):
    db = _arango_connect()
    if not db:
        return JSONResponse({"ok": False, "error": "arango_unavailable"}, status_code=503)
    _ensure_lessons_schema(db)
    _ensure_graph_bits(db)
    try:
        fk = _resolve_lesson_id(db, payload.get('from_key'), payload.get('from_title'), payload.get('from_scope'))
        tk = _resolve_lesson_id(db, payload.get('to_key'), payload.get('to_title'), payload.get('to_scope'))
        if not fk or not tk or fk == tk:
            return JSONResponse({"ok": False, "error": "invalid_from_to"}, status_code=400)
        pid = _pair_id(fk, tk)
        reason = (payload.get('reason') or '').strip() or 'rejected_by_agent'
        ts = int(time.time())
        aql = (
            "UPSERT { _key: @pid } "
            "INSERT { _key: @pid, pair_id: @pid, reason: @reason, last_checked_at: @ts, attempts: 1 } "
            "UPDATE { reason: @reason, last_checked_at: @ts, attempts: OLD.attempts + 1 } IN rejected_pairs RETURN NEW"
        )
        cur = db.aql.execute(aql, bind_vars={ 'pid': pid, 'reason': reason, 'ts': ts })
        return { 'ok': True, 'rejected': list(cur)[0] }
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/api/lessons/edge/approve")
async def api_edge_approve(payload: Dict[str, Any]):
    db = _arango_connect()
    if not db:
        return JSONResponse({"ok": False, "error": "arango_unavailable"}, status_code=503)
    _ensure_lessons_schema(db)
    _ensure_graph_bits(db)
    try:
        edge_id = payload.get('edge_id')
        human_rationale = (payload.get('rationale') or '').strip()
        ts = int(time.time())
        if not edge_id:
            fk = _resolve_lesson_id(db, payload.get('from_key'), payload.get('from_title'), payload.get('from_scope'))
            tk = _resolve_lesson_id(db, payload.get('to_key'), payload.get('to_title'), payload.get('to_scope'))
            if not fk or not tk or fk == tk:
                return JSONResponse({"ok": False, "error": "edge_id_or_from_to_required"}, status_code=400)
            q = "FOR e IN lesson_edges FILTER e._from==@from AND e._to==@to AND e.type=='related' LIMIT 1 RETURN e"
            cur = db.aql.execute(q, bind_vars={ 'from': fk, 'to': tk })
            arr = list(cur)
            if not arr:
                return JSONResponse({"ok": False, "error": "edge_not_found"}, status_code=404)
            edge_id = arr[0]['_id']
        aql = (
            "LET e = DOCUMENT(@eid) "
            "UPDATE e WITH { approved: true, status: 'active', rationale: @hr, "
            "  rationales: APPEND(e.rationales ? e.rationales : [], { by: 'human', text: @hr, at: @ts }), "
            "  last_verified_at: @ts, updated_at: @ts } IN lesson_edges RETURN NEW"
        )
        cur2 = db.aql.execute(aql, bind_vars={ 'eid': edge_id, 'hr': human_rationale, 'ts': ts })
        return { 'ok': True, 'edge': list(cur2)[0] }
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.get("/api/lessons/related")
async def api_lessons_related(key: Optional[str] = None, title: Optional[str] = None, scope: Optional[str] = None, direction: str = 'both', k: int = 10):
    db = _arango_connect()
    if not db:
        return JSONResponse({"ok": False, "error": "arango_unavailable"}, status_code=503)
    _ensure_lessons_schema(db)
    _ensure_graph_bits(db)
    try:
        seed = _resolve_lesson_id(db, key, title, scope)
        if not seed:
            return JSONResponse({"ok": False, "error": "seed_not_found"}, status_code=404)
        edges = db.collection('lesson_edges')
        res = []
        if direction in ('out','both'):
            for e in edges.find({ '_from': seed, 'type': 'related' }) or []:
                res.append(e)
        if direction in ('in','both'):
            for e in edges.find({ '_to': seed, 'type': 'related' }) or []:
                res.append(e)
        acc = {}
        for e in res:
            nid = e['_to'] if e.get('_from') == seed else e.get('_from')
            if not nid:
                continue
            if (nid not in acc) or float(e.get('weight', 0)) > float(acc[nid].get('weight', 0)):
                acc[nid] = e
        items = []
        for nid, e in acc.items():
            key2 = nid.split('/',1)[1]
            ldoc = db.collection('lessons').get(key2)
            if not ldoc: continue
            items.append({ 'neighbor': { '_key': key2, 'title': ldoc.get('title'), 'scope': ldoc.get('scope'), 'tags': ldoc.get('tags', []) }, 'edge': { k: e.get(k) for k in ('weight','rationale','approved','status','confidence','raw_sim','created_at','updated_at','last_verified_at') } })
        items.sort(key=lambda x: float(x['edge'].get('weight',0)), reverse=True)
        return { 'ok': True, 'items': items[: max(1,int(k))] }
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.get("/api/lessons/multihop")
async def api_lessons_multihop(key: Optional[str] = None, title: Optional[str] = None, scope: Optional[str] = None, depth: int = 2, direction: str = 'ANY', limit: int = 10):
    db = _arango_connect()
    if not db:
        return JSONResponse({"ok": False, "error": "arango_unavailable"}, status_code=503)
    _ensure_lessons_schema(db)
    _ensure_graph_bits(db)
    try:
        seed = _resolve_lesson_id(db, key, title, scope)
        if not seed:
            return JSONResponse({"ok": False, "error": "seed_not_found"}, status_code=404)
        depth = max(1, min(4, int(depth)))
        dir_kw = direction.upper()
        if dir_kw not in ('OUTBOUND','INBOUND','ANY'):
            dir_kw = 'ANY'
        aql = f"""
        FOR v, e, p IN 1..@depth {dir_kw} @seed lesson_edges
          OPTIONS {{ bfs: true, uniqueVertices: 'path' }}
          FILTER v._id != @seed
          LIMIT @limit
          RETURN {{ target: v, edges: p.edges }}
        """
        cur = db.aql.execute(aql, bind_vars={ 'seed': seed, 'depth': depth, 'limit': max(1,int(limit)) })
        return { 'ok': True, 'items': list(cur) }
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

# -----------------------------
# COCO Export (images + annotations)
# -----------------------------
@app.post("/api/coco/export")
async def api_coco_export(payload: Dict[str, Any]):
    """
    Build a COCO dataset from normalized boxes and rendered page images.
    Body: { rel: str, boxes_by_page: { page_num: [ {x,y,w,h,type} ] } }
    Returns: { ok, dir, json }
    """
    rel = payload.get("rel")
    boxes_by_page = payload.get("boxes_by_page") or {}
    if not isinstance(rel, str) or not boxes_by_page:
        return JSONResponse({"ok": False, "error": "missing_rel_or_boxes"}, status_code=400)
    try:
        src = _abs_pdf_path(rel)
    except FileNotFoundError:
        return JSONResponse({"ok": False, "error": "not_found"}, status_code=404)
    if fitz is None:
        return JSONResponse({"ok": False, "error": "pymupdf_missing"}, status_code=500)
    ts = time.strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.abspath(os.path.join("scripts", "artifacts", f"coco_export_{ts}"))
    os.makedirs(out_dir, exist_ok=True)
    images_out = os.path.join(out_dir, "images")
    os.makedirs(images_out, exist_ok=True)

    coco: Dict[str, Any] = {"images": [], "annotations": [], "categories": []}
    seen_types: Dict[str, int] = {}
    ann_id = 1
    img_id = 1
    try:
        with fitz.open(src) as doc:
            for p_str, boxes in (boxes_by_page or {}).items():
                try:
                    page_num = int(p_str)
                except Exception:
                    continue
                if page_num < 1 or page_num > doc.page_count:
                    continue
                page = doc.load_page(page_num - 1)
                mat = fitz.Matrix(2, 2)
                pix = page.get_pixmap(matrix=mat)
                img_name = f"{Path(rel).stem}_p{page_num:04d}.png"
                img_path = os.path.join(images_out, img_name)
                pix.save(img_path)
                width, height = pix.width, pix.height
                coco["images"].append({"id": img_id, "file_name": img_name, "width": width, "height": height})
                for b in (boxes or []):
                    # Accept either {x,y,w,h,type} or {bounding_box:[x,y,w,h], type}
                    if all(k in b for k in ("x","y","w","h")):
                        bx = float(b.get("x", 0))
                        by = float(b.get("y", 0))
                        bw = float(b.get("w", 0))
                        bh = float(b.get("h", 0))
                    else:
                        bb = b.get("bounding_box") or b.get("bbox") or [0,0,0,0]
                        bx, by, bw, bh = [float(v) for v in bb]
                    typ = str(b.get("type", "Box"))
                    if typ not in seen_types:
                        seen_types[typ] = len(seen_types) + 1
                    cat_id = seen_types[typ]
                    x_px = max(0, min(width, int(bx * width)))
                    y_px = max(0, min(height, int(by * height)))
                    w_px = max(1, min(width - x_px, int(bw * width)))
                    h_px = max(1, min(height - y_px, int(bh * height)))
                    coco["annotations"].append({
                        "id": ann_id,
                        "image_id": img_id,
                        "category_id": cat_id,
                        "bbox": [x_px, y_px, w_px, h_px],
                        "iscrowd": 0,
                        "area": w_px * h_px,
                    })
                    ann_id += 1
                img_id += 1
        for name, cid in seen_types.items():
            coco["categories"].append({"id": cid, "name": name})
        out_json = os.path.join(out_dir, "annotations.json")
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(coco, f, indent=2)
        return {"ok": True, "dir": out_dir, "json": out_json}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


# -----------------------------
# Suggestions: Camelot tables
# -----------------------------
@app.get("/api/suggest/tables")
async def api_suggest_tables(rel: str, page: int):
    try:
        src = _abs_pdf_path(rel)
    except FileNotFoundError:
        return JSONResponse({"ok": False, "error": "not_found"}, status_code=404)
    # Import Camelot lazily and tolerate missing optional deps
    try:
        import camelot as _camelot  # type: ignore
    except Exception:
        return JSONResponse({"ok": False, "error": "camelot_missing"}, status_code=500)
    if fitz is None:
        return JSONResponse({"ok": False, "error": "pymupdf_missing"}, status_code=500)
    try:
        tables = None
        try:
            tables = _camelot.read_pdf(str(src), pages=str(page), flavor="lattice")
        except Exception:
            tables = None
        if (not tables) or getattr(tables, "n", 0) == 0:
            try:
                tables = _camelot.read_pdf(str(src), pages=str(page), flavor="stream")
            except Exception:
                tables = None
        if (not tables) or getattr(tables, "n", 0) == 0:
            return {"ok": True, "suggestions": []}
        with fitz.open(src) as doc:
            pg = doc[page - 1]
            pw, ph = pg.rect.width, pg.rect.height
        out = []
        for t in tables:
            bb = getattr(t, "_bbox", None) or getattr(t, "bbox", None)
            if not bb:
                continue
            x1, y1, x2, y2 = bb
            # Camelot bbox uses PDF coords; normalize to 0..1 in our top-left origin
            nx = max(0.0, min(1.0, x1 / pw))
            ny = max(0.0, min(1.0, (ph - y2) / ph))
            nw = max(0.001, min(1.0, (x2 - x1) / pw))
            nh = max(0.001, min(1.0, (y2 - y1) / ph))
            out.append({"x": nx, "y": ny, "w": nw, "h": nh, "type": "Table"})
        return {"ok": True, "suggestions": out}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


# -----------------------------
# Simple pipeline job scaffolding
# -----------------------------
JOBS: Dict[str, Dict[str, Any]] = {}

@app.post("/api/pipeline/run")
async def api_pipeline_run(payload: Dict[str, Any]):
    rel = payload.get("rel")
    if not isinstance(rel, str):
        return JSONResponse({"ok": False, "error": "missing_rel"}, status_code=400)
    job_id = f"job_{int(time.time()*1000)}"
    JOBS[job_id] = {"id": job_id, "rel": rel, "status": "queued", "started": time.time()}

    async def _runner(jid: str, rel_path: str):
        JOBS[jid]["status"] = "running"
        try:
            # Placeholder for real pipeline integration
            import asyncio as _asyncio
            await _asyncio.sleep(2.5)
            JOBS[jid]["result"] = {"out_dir": os.path.abspath(os.path.join("scripts", "artifacts", f"pipeline_{jid}"))}
            JOBS[jid]["status"] = "done"
        except Exception as e:
            JOBS[jid]["status"] = "error"
            JOBS[jid]["error"] = str(e)

    try:
        import asyncio as _asyncio
        _asyncio.create_task(_runner(job_id, rel))
    except Exception:
        pass
    return {"ok": True, "job_id": job_id}

@app.get("/api/pipeline/status")
async def api_pipeline_status(job_id: str):
    j = JOBS.get(job_id)
    if not j:
        return JSONResponse({"ok": False, "error": "unknown_job"}, status_code=404)
    return {"ok": True, "job": j}

@app.get("/api/pipeline/result")
async def api_pipeline_result(job_id: str):
    j = JOBS.get(job_id)
    if not j:
        return JSONResponse({"ok": False, "error": "unknown_job"}, status_code=404)
    if j.get("status") != "done":
        return JSONResponse({"ok": False, "error": "not_done"}, status_code=400)
    return {"ok": True, "result": j.get("result")}


# -----------------------------
# Persist extracted content into ArangoDB
# -----------------------------
@app.post("/api/arangodb/insert")
async def api_arango_insert(payload: dict):
    db = _arango_connect()
    if not db:
        return JSONResponse({"ok": False, "error": "arango_unavailable"}, status_code=503)
    _ensure_docs_schema(db)
    try:
        doc = (payload.get("doc") or {})
        chunks = payload.get("chunks") or []
        if not isinstance(chunks, list):
            return JSONResponse({"ok": False, "error": "invalid_chunks"}, status_code=400)
        dcol = db.collection("docs")
        rel = (doc.get("rel") or doc.get("name") or "document").strip()
        existing = list(dcol.find({"rel": rel})) or []
        if existing:
            dkey = existing[0].get("_key")
        else:
            ins = dcol.insert({"rel": rel, "name": doc.get("name") or rel, "added_at": int(time.time())})
            dkey = ins.get("_key")
        ccol = db.collection("chunks")
        inserted = 0
        for c in chunks:
            text = (c.get("text") or "").strip()
            if not text:
                continue
            rec = {
                "doc_key": dkey,
                "page": int(c.get("page") or 1),
                "type": c.get("type") or "text",
                "text": text,
                "bbox": c.get("bbox") or {"x": c.get("x"), "y": c.get("y"), "w": c.get("w"), "h": c.get("h")},
                "ts": int(time.time()),
            }
            ccol.insert(rec)
            inserted += 1
        return {"ok": True, "doc_key": dkey, "inserted": inserted}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

# -----------------------------
# Search and Chat (minimal scaffolds)
# -----------------------------
@app.post("/api/search")
async def api_search(payload: dict):
    q = (payload.get("q") or "").strip()
    if not q:
        return JSONResponse({"ok": False, "error": "missing_q"}, status_code=400)
    db = _arango_connect()
    if not db:
        return JSONResponse({"ok": False, "error": "arango_unavailable"}, status_code=503)
    _ensure_docs_schema(db)
    try:
        aql = (
            "FOR d IN chunks_search "
            "SEARCH ANALYZER(d.text IN TOKENS(@q,'text_en'),'text_en') "
            "SORT BM25(d) DESC, TFIDF(d) DESC LIMIT 10 RETURN d"
        )
        cur = db.aql.execute(aql, bind_vars={"q": q})
        items = []
        for d in list(cur):
            items.append({
                "doc_key": d.get("doc_key"),
                "page": d.get("page"),
                "type": d.get("type"),
                "text": d.get("text"),
                "bbox": d.get("bbox"),
            })
        return {"ok": True, "items": items}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@app.post("/api/chat/query")
async def api_chat_query(payload: dict):
    session_id = payload.get("session_id") or f"s-{int(time.time())}"
    q = (payload.get("q") or "").strip()
    pdf_hint = (payload.get("pdf") or payload.get("pdf_rel") or payload.get("pdf_name") or "").strip()
    doc_ids = payload.get("doc_ids") or []
    top_k = int(payload.get("top_k") or 8)
    alpha = float(payload.get("alpha") or 0.5)
    alpha = max(0.0, min(1.0, alpha))
    if not q:
        return JSONResponse({"ok": False, "error": "missing_q"}, status_code=400)
    try:
        db = _arango_connect()
        if db and db.has_collection("pdf_objects"):
            view = _ensure_pdf_objects_view(db) or ""
            bind: Dict[str, Any] = {"q": q, "doc_ids": []}
            if doc_ids and isinstance(doc_ids, list):
                bind["doc_ids"] = [str(x) for x in doc_ids if isinstance(x, (str, int))]
            bind["pdf"] = pdf_hint.lower()
            aql = None
            if view and hasattr(db, "aql"):
                # Use ArangoSearch BM25 scoring
                aql = (
                    f"FOR d IN {view} "
                    "SEARCH ANALYZER(d.text_content IN TOKENS(@q,'text_en'),'text_en') "
                    "FILTER LENGTH(@doc_ids) == 0 OR d.doc_id IN @doc_ids "
                    "FILTER @pdf == '' OR CONTAINS(LOWER(d.source_pdf), @pdf) "
                    "LET bm = BM25(d) "
                    "SORT bm DESC LIMIT 50 "
                    "RETURN { text: d.text_content, page: d.page_num, type: d.object_type, embedding: d.embedding, bm25: bm }"
                )
            else:
                # Fallback to simple filter on collection (no BM25)
                aql = (
                    "FOR d IN pdf_objects "
                    "FILTER CONTAINS(LOWER(d.text_content), LOWER(@q)) "
                    "FILTER LENGTH(@doc_ids) == 0 OR d.doc_id IN @doc_ids "
                    "FILTER @pdf == '' OR CONTAINS(LOWER(d.source_pdf), @pdf) "
                    "LIMIT 50 RETURN { text: d.text_content, page: d.page_num, type: d.object_type, embedding: d.embedding, bm25: 0 }"
                )
            cur = db.aql.execute(aql, bind_vars=bind)
            rows = list(cur)
            # Hybrid re-ranking: normalize BM25, add cosine(sim)
            try:
                import numpy as _np
                embed = ensure_embedder()
                if rows and embed is not None:
                    qv = embed.encode(q, normalize_embeddings=True)
                    bm_max = max((float(r.get("bm25") or 0.0) for r in rows), default=1.0) or 1.0
                    for r in rows:
                        bm = float(r.get("bm25") or 0.0) / bm_max
                        sim = 0.0
                        ev = r.get("embedding")
                        try:
                            if isinstance(ev, list) and ev:
                                dv = _np.array(ev, dtype="float32")
                                nv = dv / max(1e-8, _np.linalg.norm(dv))
                                sim = float(_np.dot(nv, qv))
                        except Exception:
                            sim = 0.0
                        r["_score"] = alpha * bm + (1.0 - alpha) * sim
                    rows.sort(key=lambda x: x.get("_score", 0.0), reverse=True)
            except Exception:
                pass
            items = rows[: max(1, top_k)]
            answer = (items[0].get("text") or "").strip() if items else "No relevant content found."
            cits = [{"page": it.get("page"), "type": it.get("type") } for it in items[:3]]
            return {"ok": True, "session_id": session_id, "answer": answer, "citations": cits, "count": len(rows)}
        # Fallback: read latest Stage 10 flattened JSON when DB is unavailable
        fb = _chat_fallback_from_latest(q, top_k=top_k)
        return {"ok": True, "session_id": session_id, "answer": fb.get("answer", "No relevant content found."), "citations": fb.get("citations", []), "count": fb.get("count", 0)}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/api/admin/ensure-pdf-objects-view")
def api_admin_ensure_pdf_objects_view():
    db = _arango_connect()
    if not db:
        return JSONResponse({"ok": False, "error": "arango_unavailable"}, status_code=503)
    name = _ensure_pdf_objects_view(db)
    return {"ok": bool(name), "view": name or None}


# -----------------------------
# PDF upsert status (for UI indicator)
# -----------------------------
@app.get("/api/pipeline/pdf-status")
def api_pipeline_pdf_status(pdf_rel: Optional[str] = None, pdf_path: Optional[str] = None):
    try:
        db = _arango_connect()
        if not db:
            return {"ok": False, "error": "arango_unavailable"}
        coll = "pdf_objects" if db.has_collection("pdf_objects") else None
        if not coll:
            return {"ok": True, "upserted": False, "count": 0}
        hint = (pdf_rel or pdf_path or "").strip()
        bind = {"pdf": hint.lower()}
        aql = (
            f"FOR d IN {coll} "
            "FILTER @pdf == '' OR CONTAINS(LOWER(d.source_pdf), @pdf) "
            "COLLECT WITH COUNT INTO c RETURN c"
        )
        cur = db.aql.execute(aql, bind_vars=bind)
        cnt = 0
        for n in cur:
            try:
                cnt = int(n)
            except Exception:
                cnt = 0
        return {"ok": True, "upserted": cnt > 0, "count": cnt}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.get("/api/pipeline/doc-id")
def api_pipeline_doc_id(pdf_rel: Optional[str] = None, pdf_path: Optional[str] = None):
    """Return a stable per-document identifier based on file bytes.

    Rationale: hashing the file path can collide for duplicate content in
    different locations. Hashing bytes (SHA-256) avoids this and matches the
    project’s requirement to prevent working on duplicates.
    """
    try:
        pdf = _resolve_pdf_for_ui(pdf_path, pdf_rel)
        import hashlib
        h = hashlib.sha256()
        try:
            with open(pdf, "rb") as f:
                # Stream in chunks to avoid large memory spikes
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    h.update(chunk)
            doc_id = h.hexdigest()
        except Exception:
            # Fallback to hashing the absolute path string if file is unreadable
            doc_id = hashlib.md5(str(pdf).encode()).hexdigest()
        return {"ok": True, "doc_id": doc_id}
    except HTTPException as e:
        return JSONResponse({"ok": False, "error": e.detail}, status_code=e.status_code)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
# -----------------------------
# Pipeline bridge (run-external) — integrates happy-path pipeline
# -----------------------------

class _Box(BaseModel):
    id: Optional[str] = None
    type: str
    instanceId: Optional[str] = None
    x: float
    y: float
    w: float
    h: float


class _RunExternalReq(BaseModel):
    pdf_path: Optional[str] = None
    pdf_rel: Optional[str] = None
    boxes_by_page: Dict[int, List[_Box]] = Field(default_factory=dict)
    results_dir: Optional[str] = None
    session: Optional[str] = None


class _SaveAnnotationsReq(BaseModel):
    pdf_path: Optional[str] = None
    pdf_rel: Optional[str] = None
    boxes_by_page: Dict[int, List[_Box]] = Field(default_factory=dict)
    results_dir: Optional[str] = None


class _UpsertReq(BaseModel):
    results_dir: str
    fast_embeddings: bool = True

class _ReqListReq(BaseModel):
    results_dir: str

class _ReqEdit(BaseModel):
    id: str
    text_canonical: str

class _ReqSaveReq(BaseModel):
    results_dir: str
    edits: List[_ReqEdit]

class _ReqRerunReq(BaseModel):
    results_dir: str
    filter_status: List[str] | None = None


# -----------------------------
# Conflicts artifact (MVP persistence)
# -----------------------------

class _ConflictItem(BaseModel):
    id: str
    type: str  # 'duplicate' | 'numeric_mismatch' | custom
    groupId: Optional[str] = None
    resolved: bool = False
    notes: Optional[str] = None


class _SaveConflictsReq(BaseModel):
    doc_id: str
    items: List[_ConflictItem] = Field(default_factory=list)


@app.post("/api/conflicts/save")
def api_conflicts_save(req: _SaveConflictsReq):
    try:
        out_dir = Path(ARTIFACTS_ROOT)
        out_dir.mkdir(parents=True, exist_ok=True)
        # Use full doc_id string as provided; UI may pass first 12 chars for display only
        fname = f"conflicts_{req.doc_id}.json"
        path = out_dir / fname
        payload = {
            "docId": req.doc_id,
            "items": [i.model_dump(by_alias=True) for i in req.items],
            "saved_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        path.write_text(json.dumps(payload, indent=2))
        return {"ok": True, "path": str(path)}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.get("/api/conflicts/list")
def api_conflicts_list(doc_id: str):
    try:
        p = Path(ARTIFACTS_ROOT) / f"conflicts_{doc_id}.json"
        if not p.exists():
            return {"ok": True, "items": []}
        raw = json.loads(p.read_text())
        items = raw.get("items") if isinstance(raw, dict) else raw
        if not isinstance(items, list):
            items = []
        return {"ok": True, "items": items}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

# -----------------------------
# OSLC (very small offline stubs)
# -----------------------------

@app.get("/api/oslc/service")
def api_oslc_service():
    try:
        return {
            "ok": True,
            "resources": [
                {"@type": "oslc:ServiceProvider", "title": "Extractor OSLC Stub", "links": {"links": "/api/oslc/links"}},
            ],
        }
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.get("/api/oslc/links")
def api_oslc_links():
    try:
        p = Path(ARTIFACTS_ROOT) / "oslc_links.json"
        if not p.exists():
            return {"ok": True, "links": []}
        raw = json.loads(p.read_text())
        if isinstance(raw, list):
            return {"ok": True, "links": raw}
        if isinstance(raw, dict):
            # Normalize potential legacy shapes
            for k in ("links", "oslc:links"):
                if k in raw and isinstance(raw[k], list):
                    return {"ok": True, "links": raw[k]}
        return {"ok": True, "links": []}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


class _OslcLink(BaseModel):
    source: str
    target: str
    type: str = Field(default="oslc_rm:elaborates")


@app.post("/api/oslc/link")
def api_oslc_link(link: _OslcLink):
    try:
        out = Path(ARTIFACTS_ROOT) / "oslc_links.json"
        existing: list = []
        if out.exists():
            try:
                raw = json.loads(out.read_text())
                if isinstance(raw, list):
                    existing = raw
                elif isinstance(raw, dict):
                    existing = raw.get("links") or raw.get("oslc:links") or []
            except Exception:
                existing = []
        existing.append({"source": link.source, "target": link.target, "type": link.type, "saved_at": datetime.datetime.now(datetime.timezone.utc).isoformat()})
        out.write_text(json.dumps(existing, indent=2))
        return {"ok": True, "count": len(existing), "path": str(out)}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


def _resolve_pdf_for_ui(pdf_path: Optional[str], pdf_rel: Optional[str]) -> Path:
    if pdf_path:
        p = Path(pdf_path).expanduser().resolve()
        if not p.exists():
            raise HTTPException(400, f"pdf_path not found: {p}")
        return p
    if pdf_rel:
        candidates = [
            Path("prototypes/tabbed/html/public") / pdf_rel,
            Path("public") / pdf_rel,
            Path(pdf_rel),
            Path(SERVER_PDFS_ROOT) / pdf_rel,
        ]
        for c in candidates:
            if c.exists():
                return c.resolve()
        raise HTTPException(400, f"pdf_rel not found: {pdf_rel}")
    raise HTTPException(400, "Either pdf_path or pdf_rel must be provided")


def _ui_boxes_to_pipeline_annotations(pdf: Path, boxes_by_page: Dict[int, List[_Box]]) -> Dict[str, Any]:
    if fitz is None:
        raise HTTPException(503, "fitz_unavailable")
    doc = fitz.open(str(pdf))
    out: List[Dict[str, Any]] = []
    for page_key, boxes in boxes_by_page.items():
        try:
            page_index = int(page_key)
        except Exception:
            page_index = int(str(page_key))
        zero_based = max(0, page_index - 1)
        if zero_based >= len(doc):
            continue
        p = doc[zero_based]
        w = float(p.rect.width)
        h = float(p.rect.height)
        for b in boxes or []:
            x0 = max(0.0, min(w, b.x * w)); y0 = max(0.0, min(h, b.y * h))
            x1 = max(0.0, min(w, (b.x + b.w) * w)); y1 = max(0.0, min(h, (b.y + b.h) * h))
            pad_x = 0.1 * (x1 - x0); pad_y = 0.1 * (y1 - y0)
            ex0 = max(0.0, x0 - pad_x); ey0 = max(0.0, y0 - pad_y)
            ex1 = min(w, x1 + pad_x); ey1 = min(h, y1 + pad_y)
            t = (b.type or '').strip().lower()
            if t == 'section': a_type = 'section_header'
            elif t == 'table': a_type = 'table_region'
            elif t == 'figure': a_type = 'figure_region'
            else: a_type = t or 'region'
            out.append({
                'id': b.instanceId or b.id or f"anno_{len(out)+1:04d}",
                'page': zero_based,
                'type': a_type,
                'original_rect': [x0, y0, x1, y1],
                'expanded_rect': [ex0, ey0, ex1, ey1],
            })
    doc.close()
    return {
        'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'source_pdf': str(pdf),
        'status': 'Completed',
        'annotation_count': len(out),
        'annotations': out,
    }


@app.post("/api/pipeline/run-external")
def api_pipeline_run_external(req: _RunExternalReq):
    pdf = _resolve_pdf_for_ui(req.pdf_path, req.pdf_rel)
    results = Path(req.results_dir or (Path("data/results") / f"pipeline_ui_{os.getpid()}"))
    results.mkdir(parents=True, exist_ok=True)
    # Write external annotations to a temp file distinct from Stage‑01 canonical path
    anno = _ui_boxes_to_pipeline_annotations(pdf, req.boxes_by_page)
    anno_ext = results / "01_annotations_external.json"
    anno_ext.write_text(json.dumps(anno, indent=2))
    # Simple cleaner (Phase 1): copy original to a temp clean path (run_all will stage it)
    clean_path = results / f"{pdf.stem}_clean_tmp.pdf"; shutil.copyfile(str(pdf), str(clean_path))
    # Invoke run_all with skip-01
    env = os.environ.copy(); env["PYTHONPATH"] = str(REPO_ROOT / "src")
    cmd = [ sys.executable, "-m", "extractor.pipeline.run_all",
        "--pdf", str(pdf), "--results", str(results),
        "--annotations-json", str(anno_ext), "--clean-pdf", str(clean_path),
        "--skip-llm03", "--skip-descriptions06", "--summary-only07", "--skip-proving08", "--fast-embeddings10",
    ]
    proc = subprocess.run(cmd, env=env)
    ok = proc.returncode == 0
    summary = Path("scripts/artifacts/run_summary_happy.json")
    final_json = results / "final_report.json"; final_md = results / "final_report.md"
    # Write latest pointer for the UI (for quick load without passing dirs)
    try:
        pointer = Path(ARTIFACTS_ROOT) / "latest_results.json"
        pointer.write_text(json.dumps({"results_dir": str(results)}, indent=2))
    except Exception:
        pass
    return { 'ok': ok, 'results_dir': str(results),
             'summary_path': str(summary) if summary.exists() else None,
             'final_report_json': str(final_json) if final_json.exists() else None,
             'final_report_md': str(final_md) if final_md.exists() else None }


@app.get("/api/artifacts/file")
def api_artifact_file(path: str):
    # Restrict access to ARTIFACTS_ROOT for safety
    target = Path(path if Path(path).is_absolute() else Path(ARTIFACTS_ROOT) / path).resolve()
    root = Path(ARTIFACTS_ROOT).resolve()
    try:
        _ = target.relative_to(root)
    except Exception:
        return JSONResponse({"ok": False, "error": "outside_artifacts_root"}, status_code=400)
    if not target.exists() or not target.is_file():
        return JSONResponse({"ok": False, "error": "not_found"}, status_code=404)
    return FileResponse(str(target))


# -----------------------------
# Save consolidated annotations (UI normalized + Stage-01 canonical)
# -----------------------------

@app.post("/api/annotations/save")
def api_annotations_save(req: _SaveAnnotationsReq):
    try:
        pdf = _resolve_pdf_for_ui(req.pdf_path, req.pdf_rel)
        results = Path(req.results_dir or (Path("data/results") / f"pipeline_ui_{os.getpid()}"))
        results.mkdir(parents=True, exist_ok=True)

        # 1) Save UI-normalized annotations for the client (authoritative for UX)
        ui_payload = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "source_pdf": str(pdf),
            "normalized": True,
            "boxes_by_page": json.loads(json.dumps(req.boxes_by_page, default=lambda o: o.dict() if hasattr(o, 'dict') else o)),
        }
        norm_path = results / "annotations.json"
        norm_path.write_text(json.dumps(ui_payload, indent=2))

        # 2) Save canonical Stage-01 annotations for pipeline reuse (PDF points)
        stage01 = results / "01_annotation_processor"
        json_dir = stage01 / "json_output"
        json_dir.mkdir(parents=True, exist_ok=True)
        anno = _ui_boxes_to_pipeline_annotations(pdf, req.boxes_by_page)
        anno_path = json_dir / "01_annotations.json"
        anno_path.write_text(json.dumps(anno, indent=2))

        return {
            "ok": True,
            "results_dir": str(results),
            "annotations_path": str(norm_path),
            "stage01_annotations_path": str(anno_path),
        }
    except HTTPException as e:
        return JSONResponse({"ok": False, "error": e.detail}, status_code=e.status_code)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


# -----------------------------
# Upsert to ArangoDB (Stage 10 → 11 only)
# -----------------------------

@app.post("/api/pipeline/upsert")
def api_pipeline_upsert(req: _UpsertReq):
    try:
        results = Path(req.results_dir).resolve()
        if not results.exists():
            return JSONResponse({"ok": False, "error": "results_dir_not_found"}, status_code=400)

        reflow_json = results / "07_reflow_section" / "json_output" / "07_reflowed.json"
        summaries_json = results / "09_section_summarizer" / "json_output" / "09_summaries.json"
        if not reflow_json.exists() or not summaries_json.exists():
            return JSONResponse({"ok": False, "error": "missing_stage_inputs"}, status_code=400)

        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT / "src")

        # Stage 10
        cmd10 = [
            sys.executable,
            "src/extractor/pipeline/steps/10_arangodb_exporter.py",
            "run",
            "--reflowed", str(reflow_json),
            "--summaries", str(summaries_json),
            "-o", str(results),
        ] + (["--fast-embeddings"] if req.fast_embeddings else [])
        p10 = subprocess.run(cmd10, env=env)
        if p10.returncode != 0:
            return JSONResponse({"ok": False, "error": "stage10_failed"}, status_code=500)

        flat_json = results / "10_arangodb_exporter" / "json_output" / "10_flattened_data.json"
        confirm10 = results / "10_arangodb_exporter" / "json_output" / "10_export_confirmation.json"
        if not flat_json.exists() or not confirm10.exists():
            return JSONResponse({"ok": False, "error": "stage10_outputs_missing"}, status_code=500)

        # Stage 11
        cmd11 = [
            sys.executable,
            "src/extractor/pipeline/steps/11_arango_create_graph.py",
            "run",
            str(flat_json),
            "-o", str(results),
        ]
        p11 = subprocess.run(cmd11, env=env)
        if p11.returncode != 0:
            return JSONResponse({"ok": False, "error": "stage11_failed"}, status_code=500)

        confirm11 = results / "11_arango_create_graph" / "json_output" / "11_graph_confirmation.json"
        return {
            "ok": True,
            "results_dir": str(results),
            "export_confirmation": str(confirm10) if confirm10.exists() else None,
            "graph_confirmation": str(confirm11) if confirm11.exists() else None,
        }
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

# -----------------------------
# Requirements API (miner/enrichment UX support)
# -----------------------------

@app.get("/api/requirements/list")
def api_requirements_list(results_dir: str):
    try:
        results = Path(results_dir).resolve()
        req07 = results / "07_requirements_miner" / "json_output" / "07_requirements.json"
        req08 = results / "08_lean4_theorem_prover" / "json_output" / "08_requirements_enriched.json"
        if not req07.exists():
            return JSONResponse({"ok": False, "error": "requirements_not_found"}, status_code=404)
        base = json.loads(req07.read_text())
        items = base.get("requirements") or []
        by_id = {str(r.get("id")): r for r in items if r.get("id")}
        if req08.exists():
            try:
                enr = json.loads(req08.read_text()).get("requirements") or []
                for e in enr:
                    rid = str(e.get("id"))
                    if rid in by_id:
                        by_id[rid]["status"] = e.get("status")
            except Exception:
                pass
        # Build light list for UI
        out = []
        for r in by_id.values():
            out.append({
                "id": r.get("id"),
                "text_canonical": r.get("text_canonical") or r.get("text_raw"),
                "status": r.get("status", "new"),
                "confidence": r.get("confidence", 0.0),
                "source": r.get("source", {}),
            })
        return {"ok": True, "results_dir": str(results), "requirements": out}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/api/requirements/save")
def api_requirements_save(req: _ReqSaveReq):
    try:
        results = Path(req.results_dir).resolve()
        req07 = results / "07_requirements_miner" / "json_output" / "07_requirements.json"
        if not req07.exists():
            return JSONResponse({"ok": False, "error": "requirements_not_found"}, status_code=404)
        data = json.loads(req07.read_text())
        items = data.get("requirements") or []
        by_id = {str(r.get("id")): r for r in items if r.get("id")}
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        changed = 0
        for e in req.edits:
            r = by_id.get(e.id)
            if r:
                r["text_canonical"] = e.text_canonical
                r.setdefault("last_user_edit", {})
                r["last_user_edit"] = {"by": "ui", "at": now}
                changed += 1
        if changed:
            req07.write_text(json.dumps({"requirements": list(by_id.values())}, indent=2))
        # Mark edited in enriched file (create if absent)
        enr_dir = results / "08_lean4_theorem_prover" / "json_output"
        enr = enr_dir / "08_requirements_enriched.json"
        enr_dir.mkdir(parents=True, exist_ok=True)
        enr_items = []
        if enr.exists():
            try:
                enr_items = json.loads(enr.read_text()).get("requirements") or []
            except Exception:
                enr_items = []
        enr_by_id = {str(x.get("id")): x for x in enr_items if x.get("id")}
        for e in req.edits:
            x = enr_by_id.get(e.id) or {"id": e.id}
            x["status"] = "edited"
            x["compile_log"] = x.get("compile_log", "")
            x["diagnostics"] = x.get("diagnostics", [])
            x["formalization"] = x.get("formalization", None)
            # ensure text_canonical matches edited
            x["text_canonical"] = e.text_canonical
            enr_by_id[e.id] = x
        enr.write_text(json.dumps({"requirements": list(enr_by_id.values())}, indent=2))
        return {"ok": True, "edited": changed}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/api/requirements/rerun")
def api_requirements_rerun(req: _ReqRerunReq):
    try:
        results = Path(req.results_dir).resolve()
        if not results.exists():
            return JSONResponse({"ok": False, "error": "results_dir_not_found"}, status_code=400)
        reflow_json = results / "07_reflow_section" / "json_output" / "07_reflowed.json"
        if not reflow_json.exists():
            return JSONResponse({"ok": False, "error": "missing_reflowed"}, status_code=400)
        env = os.environ.copy(); env["PYTHONPATH"] = str(REPO_ROOT / "src")
        # Prefer native Stage 08 run; FORCE_PROVE08 can be set by operator to override offline
        cmd = [
            sys.executable,
            "src/extractor/pipeline/steps/08_lean4_theorem_prover.py",
            str(reflow_json),
            "-o", str(results),
        ]
        p = subprocess.run(cmd, env=env)
        ok = p.returncode == 0
        enr = results / "08_lean4_theorem_prover" / "json_output" / "08_requirements_enriched.json"
        return {"ok": ok, "enriched": str(enr) if enr.exists() else None}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

# -----------------------------
# Latest results pointer (UI convenience)
# -----------------------------

@app.get("/api/pipeline/latest")
def api_pipeline_latest():
    try:
        p = Path(ARTIFACTS_ROOT) / "latest_results.json"
        if not p.exists():
            return {"ok": True, "results_dir": ""}
        j = json.loads(p.read_text())
        return {"ok": True, "results_dir": j.get("results_dir", "")}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


class _LatestSet(BaseModel):
    results_dir: str


@app.post("/api/pipeline/latest-set")
def api_pipeline_latest_set(body: _LatestSet):
    try:
        p = Path(ARTIFACTS_ROOT) / "latest_results.json"
        p.write_text(json.dumps({"results_dir": body.results_dir}, indent=2))
        return {"ok": True, "path": str(p)}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

# -----------------------------
# Annotation events (labels) — MVP
# -----------------------------

ANNOTATION_DIR = Path(os.environ.get("ANNOTATION_EVENTS_DIR", "annotation_events"))
ANNOTATION_DIR.mkdir(parents=True, exist_ok=True)
EVENT_FILE = ANNOTATION_DIR / "events.jsonl"

class _FeatureSnapshot(BaseModel):
    fragmentation: int | None = None
    header_jaccard_max: float | None = None
    numeric_stability: float | None = None
    row_count: int | None = None
    col_count: int | None = None
    strategy_diversity: int | None = None
    merge_type_header_body: int | None = None
    foreign_numeric_ratio: float | None = None

class _OriginalPrediction(BaseModel):
    confidence: float | None = None
    structure_prob: float | None = None
    features_hash: str | None = None
    feature_snapshot: _FeatureSnapshot | None = None

class _GoldLabel(BaseModel):
    structure_correct: bool
    cell_accuracy: float | None = Field(default=None, ge=0, le=1)
    notes: str | None = None

class _ContextRef(BaseModel):
    page_indices: list[int] | None = None
    source_stage: str | None = None

class _AnnotationEventIn(BaseModel):
    doc_id: str
    object_type: str
    object_id: str
    gold_label: _GoldLabel
    context: _ContextRef | None = None
    original_prediction: _OriginalPrediction | None = None
    user_id: str | None = None

def _hash_feature_snapshot(fs: _FeatureSnapshot | None) -> str | None:
    if not fs:
        return None
    data = fs.model_dump()
    try:
        raw = json.dumps(data, sort_keys=True).encode()
        import hashlib
        return "sha256:" + hashlib.sha256(raw).hexdigest()
    except Exception:
        return None

@app.post("/api/labels")
def post_label(evt: _AnnotationEventIn):
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    event = {
        "event_id": str(uuid.uuid4()),
        "timestamp": now,
        "doc_id": evt.doc_id,
        "object_type": evt.object_type,
        "object_id": evt.object_id,
        "gold_label": evt.gold_label.model_dump(),
        "context": evt.context.model_dump() if evt.context else {},
        "user_id": evt.user_id or os.getenv("ANNOTATION_DEFAULT_USER", "unknown"),
        "original_prediction": evt.original_prediction.model_dump() if evt.original_prediction else {},
        "model_versions": {
            "table_calibrator": os.getenv("TABLE_CALIBRATOR_VERSION"),
            "extractor_commit": os.getenv("EXTRACTOR_GIT_COMMIT"),
        },
        "schema_version": "annotation_event@1.0.0",
    }

    op = event["original_prediction"]
    if op and not op.get("features_hash"):
        fs = op.get("feature_snapshot")
        if fs:
            try:
                op["features_hash"] = _hash_feature_snapshot(_FeatureSnapshot(**fs))
            except Exception:
                pass

    try:
        with EVENT_FILE.open("a") as fh:
            fh.write(json.dumps(event) + "\n")
    except Exception as e:
        return JSONResponse({"ok": False, "error": f"persist_failed: {e}"}, status_code=500)
    return {"ok": True, "event_id": event["event_id"]}

# -----------------------------
# Triage (ELS queues)
# -----------------------------

@app.get("/api/triage")
def api_triage(object_type: str = "table", band: str | None = None, limit: int = 50, run_id: str | None = None):
    """
    Serve ELS-ranked triage items for review.
    Currently supports object_type=table by reading the latest triage queue
    at data/results/pipeline/triage_queue/tables.json. When missing, attempts
    an on-the-fly computation from 05_tables.json.
    """
    try:
        results_root = (REPO_ROOT / "data" / "runs" / run_id / "triage") if run_id else (REPO_ROOT / "data" / "results" / "pipeline" / "triage_queue")
        # support all object types
        triage_map = {
            "table": "tables.json",
            "tables": "tables.json",
            "section": "sections.json",
            "sections": "sections.json",
            "figure": "figures.json",
            "figures": "figures.json",
            "entity": "entities.json",
            "entities": "entities.json",
        }
        fname = triage_map.get((object_type or "table").lower())
        if not fname:
            return JSONResponse({"ok": False, "error": "unsupported_object_type"}, status_code=400)
        qpath = results_root / "triage_queue" / fname
        if not qpath.exists():
            # Attempt local/quick computation
            try:
                import subprocess, sys as _sys
                env = os.environ.copy()
                if run_id:
                    env["RUN_ID"] = run_id
                _ = subprocess.run([
                    _sys.executable,
                    str(REPO_ROOT / "scripts/triage/triage_scoring.py"),
                ], env=env)
            except Exception:
                pass
        items = []
        if qpath.exists():
            raw = json.loads(qpath.read_text())
            if isinstance(raw, dict) and isinstance(raw.get("items"), list):
                items = raw.get("items", [])
            elif isinstance(raw, list):
                items = raw
        if band:
            band = band.strip().lower()
            items = [it for it in items if str(it.get("band","")) == band]
        items = sorted(items, key=lambda x: float(x.get("els", 0.0)), reverse=True)[: max(1, min(500, int(limit)))]
        return {
            "data": items,
            "meta": {
                "total": len(items),
                "band": band,
                "limit": int(limit),
                "supported_types": ["table","section","figure","entity"],
            },
        }
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
# -----------------------------
# Pipeline run + training status helpers
# -----------------------------

RUN_STATUS_FILE = REPO_ROOT / "scripts" / "artifacts" / "pipeline_status.json"
TRAIN_STATUS_FILE = REPO_ROOT / "scripts" / "artifacts" / "training_status.json"
TRAIN_LOCK_FILE = REPO_ROOT / "training" / ".train_lock"
TRAIN_APPROVALS_FILE = REPO_ROOT / "training" / "approvals.json"

class _RunRequest(BaseModel):
    pdf_rel: str
    offline: bool | None = True

def _write_json(path: Path, obj: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(obj, indent=2))
    except Exception:
        pass

def _run_pipeline_subprocess(pdf_rel: str, offline: bool) -> dict:
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    status = {"status": "running", "pdf_rel": pdf_rel, "offline": offline, "started_at": started}
    _write_json(RUN_STATUS_FILE, status)
    try:
        # serialize pipeline runs to reduce contention and resource spikes
        plock = REPO_ROOT / "scripts" / "artifacts" / ".pipeline_lock"
        if plock.exists():
            status.update({"status": "busy", "message": "another run is active"})
            _write_json(RUN_STATUS_FILE, status)
            return status
        try:
            plock.parent.mkdir(parents=True, exist_ok=True)
            plock.write_text(started)
        except Exception:
            pass
        results_dir = REPO_ROOT / "data" / "results" / "pipeline"
        results_dir.mkdir(parents=True, exist_ok=True)
        cmd = [
            sys.executable,
            "-m",
            "extractor.pipeline.run_all",
            "--pdf",
            str((REPO_ROOT / pdf_rel).resolve()),
            "--results",
            str(results_dir),
        ]
        if offline:
            cmd.append("--offline")
        env = os.environ.copy()
        p = subprocess.run(cmd, env=env)
        ended = datetime.datetime.now(datetime.timezone.utc).isoformat()
        ok = p.returncode == 0
        status.update({
            "status": "completed" if ok else "failed",
            "ended_at": ended,
            "results_dir": str(results_dir),
            "returncode": p.returncode,
        })
        # Update latest pointer used elsewhere
        try:
            latest = REPO_ROOT / "scripts" / "artifacts" / "latest_results.json"
            _write_json(latest, {"results_dir": str(results_dir)})
        except Exception:
            pass
    except Exception as e:
        status.update({"status": "failed", "error": str(e)})
    finally:
        try:
            plock.unlink(missing_ok=True)  # type: ignore[arg-type]
        except Exception:
            pass
    _write_json(RUN_STATUS_FILE, status)
    return status

def _train_background() -> dict:
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    status = {"status": "running", "started_at": started}
    _write_json(TRAIN_STATUS_FILE, status)
    try:
        # Promotion/training lock to avoid races
        TRAIN_LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
        if TRAIN_LOCK_FILE.exists():
            # Another training in progress
            status.update({"status": "busy", "message": "training lock present"})
            _write_json(TRAIN_STATUS_FILE, status)
            return status
        TRAIN_LOCK_FILE.write_text(started)
        # Export samples
        cmd1 = [sys.executable, str(REPO_ROOT / "training/scripts/export_training_samples.py")]
        # Train calibrator
        cmd2 = [sys.executable, str(REPO_ROOT / "training/scripts/train_table_calibrator.py")]
        rc1 = subprocess.run(cmd1).returncode
        rc2 = subprocess.run(cmd2).returncode
        ended = datetime.datetime.now(datetime.timezone.utc).isoformat()
        ok = (rc1 == 0 and rc2 == 0)
        status.update({"status": "completed" if ok else "failed", "ended_at": ended, "rc_export": rc1, "rc_train": rc2})
    except Exception as e:
        status.update({"status": "failed", "error": str(e)})
    finally:
        try:
            if TRAIN_LOCK_FILE.exists():
                TRAIN_LOCK_FILE.unlink()
        except Exception:
            pass
    _write_json(TRAIN_STATUS_FILE, status)
    return status

@app.post("/api/pipeline/run")
def api_pipeline_run(body: _RunRequest, bg: BackgroundTasks):
    try:
        # Start background run
        bg.add_task(_run_pipeline_subprocess, body.pdf_rel, bool(body.offline))
        return {"ok": True, "started": True, "pdf_rel": body.pdf_rel}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start pipeline: {e}")

@app.get("/api/pipeline/status")
def api_pipeline_status():
    try:
        if RUN_STATUS_FILE.exists():
            return json.loads(RUN_STATUS_FILE.read_text())
        return {"status": "idle"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read status: {e}")

@app.post("/api/train/start")
def api_train_start(bg: BackgroundTasks):
    try:
        bg.add_task(_train_background)
        return {"ok": True, "started": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start training: {e}")

@app.get("/api/train/status")
def api_train_status():
    try:
        if TRAIN_STATUS_FILE.exists():
            return json.loads(TRAIN_STATUS_FILE.read_text())
        return {"status": "idle"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read training status: {e}")

class _TrainApproval(BaseModel):
    version: str
    approved_by: str | None = None

@app.post("/api/train/approve")
def api_train_approve(body: _TrainApproval):
    try:
        approvals = []
        if TRAIN_APPROVALS_FILE.exists():
            try:
                approvals = json.loads(TRAIN_APPROVALS_FILE.read_text())
                if not isinstance(approvals, list):
                    approvals = []
            except Exception:
                approvals = []
        entry = {
            "version": body.version,
            "approved_by": body.approved_by,
            "approved_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        approvals.append(entry)
        TRAIN_APPROVALS_FILE.parent.mkdir(parents=True, exist_ok=True)
        TRAIN_APPROVALS_FILE.write_text(json.dumps(approvals, indent=2))
        # Reflect latest approval in training status for UI convenience
        try:
            status = json.loads(TRAIN_STATUS_FILE.read_text()) if TRAIN_STATUS_FILE.exists() else {}
            status["last_approved_version"] = body.version
            _write_json(TRAIN_STATUS_FILE, status)
        except Exception:
            pass
        return {"ok": True, "approved": body.version, "path": str(TRAIN_APPROVALS_FILE)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to record approval: {e}")

# -----------------------------
# PDF upload → run orchestration (alpha)
# -----------------------------

def _pdf_doc_id(path: Path) -> str:
    try:
        h = hashlib.sha256(path.read_bytes()).hexdigest()[:8]
    except Exception:
        h = "unknown"
    base = path.stem.lower()
    base_norm = "".join(ch if ch.isalnum() else "_" for ch in base).strip("_")
    return f"{base_norm}__{h}"

@app.post("/api/pdf")
async def api_upload_pdf(background: BackgroundTasks, file: UploadFile = File(...)):
    try:
        dest = UPLOAD_DIR / file.filename
        with dest.open("wb") as out:
            shutil.copyfileobj(file.file, out)
        doc_id = _pdf_doc_id(dest)
        run_id = f"run_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        run_dir = RUNS_DIR / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "doc_id": doc_id,
            "run_id": run_id,
            "pdf_path": str(dest),
            "status": "queued",
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

        def _task():
            mpath = run_dir / "manifest.json"
            manifest["status"] = "running"
            mpath.write_text(json.dumps(manifest, indent=2))
            env = os.environ.copy()
            env["DOC_ID"] = doc_id
            env["RUN_ID"] = run_id
            stages_dir = run_dir / "stages"
            stages_dir.mkdir(parents=True, exist_ok=True)
            cmd = [
                sys.executable,
                "-m",
                "extractor.pipeline.run_all",
                "--pdf",
                str(dest),
                "--results",
                str(stages_dir),
                "--offline",
            ]
            try:
                subprocess.run(cmd, check=True, env=env)
                subprocess.run([sys.executable, str(REPO_ROOT / "scripts/triage/triage_scoring.py")], check=True, env=env)
                manifest["status"] = "completed"
            except Exception as e:
                manifest["status"] = "error"
                manifest["error"] = str(e)
            manifest["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            mpath.write_text(json.dumps(manifest, indent=2))

        background.add_task(_task)
        return {"ok": True, "doc_id": doc_id, "run_id": run_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")

@app.get("/api/run/status")
def api_run_status(run_id: str):
    try:
        mpath = RUNS_DIR / run_id / "manifest.json"
        if not mpath.exists():
            return {"error": "run_not_found"}
        return json.loads(mpath.read_text())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Status failed: {e}")

@app.get("/api/run/progress")
def api_run_progress(run_id: str):
    try:
        return _progress_for_run(run_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Progress failed: {e}")

@app.get("/api/annotations")
def api_annotations(run_id: str):
    try:
        run_dir = RUNS_DIR / run_id
        stages = run_dir / "stages"
        def _load(p: Path):
            try:
                return json.loads(p.read_text())
            except Exception:
                return {}
        sec = _load(stages / "04_section_builder" / "json_output" / "04_sections.json")
        tab = _load(stages / "05_table_extractor" / "json_output" / "05_tables.json")
        fig = _load(stages / "06_figure_extractor" / "json_output" / "06_figures.json")
        return {
            "sections": sec.get("sections", []),
            "tables": tab.get("tables", []),
            "figures": fig.get("figures", []),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Annotations failed: {e}")

@app.get("/api/annotations/merged")
def api_annotations_merged(run_id: str):
    try:
        base = api_annotations(run_id)
        run_dir = RUNS_DIR / run_id
        cur_path = run_dir / "curated.json"
        if cur_path.exists():
            try:
                cur = json.loads(cur_path.read_text())
            except Exception:
                cur = {}
            cur_secs = {str(x.get("id") or x.get("object_id") or ""): x for x in (cur.get("sections") or [])}
            cur_tabs = {str(x.get("object_id") or x.get("id") or ""): x for x in (cur.get("tables") or [])}
            cur_figs = {str(x.get("figure_id") or x.get("object_id") or x.get("id") or ""): x for x in (cur.get("figures") or [])}
            for s in base.get("sections", []) or []:
                sid = str(s.get("id") or "")
                if sid and sid in cur_secs and cur_secs[sid].get("title"):
                    s["title"] = cur_secs[sid].get("title")
                for t in s.get("tables") or []:
                    key = str(t.get("object_id") or "")
                    if key and key in cur_tabs and (cur_tabs[key].get("bbox") or cur_tabs[key].get("rect")):
                        t["bbox"] = cur_tabs[key].get("bbox") or cur_tabs[key].get("rect")
                for f in s.get("figures") or []:
                    key = str(f.get("figure_id") or f.get("object_id") or "")
                    if key and key in cur_figs and (cur_figs[key].get("bbox") or cur_figs[key].get("rect")):
                        f["bbox"] = cur_figs[key].get("bbox") or cur_figs[key].get("rect")
        return {"ok": True, "data": base}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

# -----------------------------
# Save curated/blesed annotations (alpha)
# -----------------------------

class _CuratedPayload(BaseModel):
    run_id: str
    doc_id: str | None = None
    sections: list[dict] | None = None
    tables: list[dict] | None = None
    figures: list[dict] | None = None
    comments: list[dict] | None = None

@app.post("/api/annotations/save")
def api_annotations_save(body: _CuratedPayload):
    try:
        run_dir = RUNS_DIR / body.run_id
        out = run_dir / "curated.json"
        data = body.model_dump()
        out.write_text(json.dumps(data, indent=2))
        return {"ok": True, "path": str(out)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Save failed: {e}")

@app.post("/api/export/arango")
def api_export_arango(run_id: str, db: str = "extractor", url: str = "http://127.0.0.1:8529"):
    try:
        run_dir = RUNS_DIR / run_id
        stages = run_dir / "stages"
        cmd = [
            sys.executable,
            str(REPO_ROOT / "scripts/export/export_arango.py"),
            "--run-id", run_id,
            "--stages", str(stages),
            "--db", db,
            "--url", url,
        ]
        p = subprocess.run(cmd, capture_output=True, text=True)
        summary_path = Path("arango_export") / f"{run_id}_summary.json"
        # Start background FAISS-KNN clustering + LLM-verified rationale if available
        try:
            subprocess.Popen([sys.executable, str(REPO_ROOT / "scripts/arango/faiss_cluster.py"), "--run-id", run_id, "--db", db, "--url", url])
            subprocess.Popen([sys.executable, str(REPO_ROOT / "scripts/arango/verify_rationale.py"), "--run-id", run_id, "--db", db, "--url", url])
        except Exception:
            pass
        return {"ok": p.returncode == 0, "returncode": p.returncode, "summary_path": str(summary_path) if summary_path.exists() else None, "stdout": p.stdout[-4000:] if p.stdout else None, "stderr": p.stderr[-4000:] if p.stderr else None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {e}")
# Upload & runs directories (alpha)
UPLOAD_DIR = REPO_ROOT / "data" / "uploads"
RUNS_DIR = REPO_ROOT / "data" / "runs"
try:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    pass
# -----------------------------
# Progress computation helpers
# -----------------------------

STAGE_PATHS = [
    ("01_annotation_processor", "json_output"),
    ("02_marker_extractor", "json_output"),
    ("03_suspicious_headers", "json_output"),
    ("04_section_builder", "json_output/04_sections.json"),
    ("05_table_extractor", "json_output/05_tables.json"),
    ("06_figure_extractor", "json_output/06_figures.json"),
    ("07_reflow_section", "json_output/07_reflowed.json"),
]

def _progress_for_run(run_id: str) -> dict:
    run_dir = RUNS_DIR / run_id
    stages = run_dir / "stages"
    completed = 0
    total = len(STAGE_PATHS)
    details = []
    for name, rel in STAGE_PATHS:
        p = stages / name
        if rel:
            p = stages / name / rel
        ok = p.exists()
        if ok:
            completed += 1
        details.append({"stage": name, "present": ok, "path": str(p)})
    percent = int((completed / total) * 100) if total else 0
    return {"run_id": run_id, "percent": percent, "completed": completed, "total": total, "details": details}
