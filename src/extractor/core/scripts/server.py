"""
Module: server.py

External Dependencies:
- traceback: [Documentation URL]
- click: [Documentation URL]
- pydantic: https://docs.pydantic.dev/
- starlette: [Documentation URL]
- marker: [Documentation URL]
- base64: [Documentation URL]
- contextlib: [Documentation URL]
- fastapi: https://fastapi.tiangolo.com/
- uvicorn: [Documentation URL]

Notes:
- Heavy pipeline imports (torch, PdfConverter, etc.) are optional and loaded lazily so
  the logging endpoints work even when those dependencies aren't available.
"""

import asyncio
import base64
import datetime
import io
import json
import json as _json
import os
import subprocess
import time
import traceback
from contextlib import asynccontextmanager
from typing import Annotated, Any, Dict, List, Optional

import click
from dotenv import find_dotenv, load_dotenv
from fastapi import FastAPI, File, Form, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from starlette.responses import HTMLResponse

from extractor.core.config.parser import ConfigParser
from extractor.core.output import text_from_rendered
from scillm import acompletion as sc_acompletion  # type: ignore

# Lazy/heavy imports guarded to avoid hard Torch dependency for logger-only mode
try:  # pragma: no cover - optional heavy deps
    from extractor.core.converters.pdf import PdfConverter  # type: ignore
    from extractor.core.models import create_model_dict  # type: ignore
    from extractor.core.settings import settings  # type: ignore

    _MARKER_FEATURES_AVAILABLE = True
except Exception:  # pragma: no cover - run without heavy deps
    PdfConverter = None  # type: ignore
    create_model_dict = None  # type: ignore
    settings = type(
        "_S", (), {"OUTPUT_IMAGE_FORMAT": "PNG", "OUTPUT_ENCODING": "utf-8"}
    )()  # minimal
    _MARKER_FEATURES_AVAILABLE = False

async def _sc_chat(
    messages,
    model: str,
    *,
    response_format: str | None = None,
    timeout: int = 60,
    temperature: float = 0.0,
):
    resp = await sc_acompletion(
        model=model,
        api_base=os.getenv("SCILLM_API_BASE", "http://localhost:4010"),
        api_key=os.getenv("SCILLM_PROXY_KEY", "sk-dev-proxy-123"),
        custom_llm_provider="openai",
        messages=messages,
        response_format={"type": "json_object"} if response_format == "json_object" else None,
        timeout=timeout,
        temperature=temperature,
    )
    content = (resp.get("choices") or [{}])[0].get("message", {}).get("content")
    return content


try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None  # type: ignore
try:
    import camelot  # type: ignore
except Exception:
    camelot = None  # type: ignore

# ArangoDB utils (project-standard)
try:
    from arango.database import StandardDatabase
    from extractor.core.utils.arango_setup import (
        connect_arango,
        ensure_database,
        ensure_collection,
        DEFAULT_CONFIG,
    )
except Exception:  # pragma: no cover - allow server to run even if arango optional
    StandardDatabase = None  # type: ignore
    connect_arango = ensure_database = ensure_collection = None  # type: ignore
    DEFAULT_CONFIG = {"arango": {"db_name": "marker"}}

app_data = {}


UPLOAD_DIRECTORY = "./uploads"
os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Only initialize heavy model artifacts if available
    if locals().get("_MARKER_FEATURES_AVAILABLE") and create_model_dict is not None:
        try:
            app_data["models"] = create_model_dict()
        except Exception:
            app_data["models"] = {}

    yield

    if "models" in app_data:
        del app_data["models"]


app = FastAPI(lifespan=lifespan)

# Project standard: load environment variables from .env early
try:
    load_dotenv(find_dotenv())
except Exception:
    pass

# Allow cross-origin calls from the Vite preview/dev servers (8080) and others during prototyping
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return HTMLResponse(
        """
<h1>Marker API</h1>
<ul>
    <li><a href="/docs">API Documentation</a></li>
    <li><a href="/marker">Run marker (post request only)</a></li>
</ul>
"""
    )


# In development, make stale/cached responses impossible by default
@app.middleware("http")
async def no_cache_middleware(request, call_next):
    response = await call_next(request)
    try:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, proxy-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        response.headers["Surrogate-Control"] = "no-store"
    except Exception:
        pass
    return response


@app.get("/api/build")
async def api_build():
    try:
        git = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"]).decode().strip()
    except Exception:
        git = "unknown"
    return {"git": git, "started_at": datetime.datetime.utcnow().isoformat() + "Z"}


class CommonParams(BaseModel):
    filepath: Annotated[Optional[str], Field(description="The path to the PDF file to convert.")]
    page_range: Annotated[
        Optional[str],
        Field(
            description="Page range to convert, specify comma separated page numbers or ranges.  Example: 0,5-10,20",
            example=None,
        ),
    ] = None
    languages: Annotated[
        Optional[str],
        Field(
            description="Comma separated list of languages to use for OCR. Must be either the names or codes from from https://github.com/VikParuchuri/surya/blob/master/surya/recognition/languages.py.",
            example=None,
        ),
    ] = None
    force_ocr: Annotated[
        bool,
        Field(
            description="Force OCR on all pages of the PDF.  Defaults to False.  This can lead to worse results if you have good text in your PDFs (which is true in most cases)."
        ),
    ] = False
    paginate_output: Annotated[
        bool,
        Field(
            description="Whether to paginate the output.  Defaults to False.  If set to True, each page of the output will be separated by a horizontal rule that contains the page number (2 newlines, {PAGE_NUMBER}, 48 - characters, 2 newlines)."
        ),
    ] = False
    output_format: Annotated[
        str,
        Field(
            description="The format to output the text in.  Can be 'markdown', 'json', or 'html'.  Defaults to 'markdown'."
        ),
    ] = "markdown"


async def _convert_pdf(params: CommonParams):
    assert params.output_format in ["markdown", "json", "html"], "Invalid output format"
    if not locals().get("_MARKER_FEATURES_AVAILABLE") or PdfConverter is None:
        return {
            "success": False,
            "error": "Marker conversion unavailable on this server (heavy dependencies missing).",
        }
    try:
        options = params.model_dump()
        print(options)
        config_parser = ConfigParser(options)
        config_dict = config_parser.generate_config_dict()
        config_dict["pdftext_workers"] = 1
        converter_cls = PdfConverter
        converter = converter_cls(
            config=config_dict,
            artifact_dict=app_data["models"],
            processor_list=config_parser.get_processors(),
            renderer=config_parser.get_renderer(),
            llm_service=config_parser.get_llm_service(),
        )
        rendered = converter(params.filepath)
        text, _, images = text_from_rendered(rendered)
        metadata = rendered.metadata
    except Exception as e:
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e),
        }

    encoded = {}
    for k, v in images.items():
        byte_stream = io.BytesIO()
        v.save(byte_stream, format=settings.OUTPUT_IMAGE_FORMAT)
        encoded[k] = base64.b64encode(byte_stream.getvalue()).decode(settings.OUTPUT_ENCODING)

    return {
        "format": params.output_format,
        "output": text,
        "images": encoded,
        "metadata": metadata,
        "success": True,
    }


@app.post("/marker")
async def convert_pdf(params: CommonParams):
    return await _convert_pdf(params)


@app.post("/marker/upload")
async def convert_pdf_upload(
    page_range: Optional[str] = Form(default=None),
    languages: Optional[str] = Form(default=None),
    force_ocr: Optional[bool] = Form(default=False),
    paginate_output: Optional[bool] = Form(default=False),
    output_format: Optional[str] = Form(default="markdown"),
    file: UploadFile = File(
        ..., description="The PDF file to convert.", media_type="application/pdf"
    ),
):
    upload_path = os.path.join(UPLOAD_DIRECTORY, file.filename)
    with open(upload_path, "wb+") as upload_file:
        file_contents = await file.read()
        upload_file.write(file_contents)

    params = CommonParams(
        filepath=upload_path,
        page_range=page_range,
        languages=languages,
        force_ocr=force_ocr,
        paginate_output=paginate_output,
        output_format=output_format,
    )
    results = await _convert_pdf(params)
    os.remove(upload_path)
    return results


# -----------------------------
# UX: WebSocket + HTTP generate
# -----------------------------


@app.websocket("/ws/ux/generate")
async def ws_generate(websocket: WebSocket):
    await websocket.accept()
    try:
        data = await websocket.receive_json()
        if not isinstance(data, dict) or data.get("cmd") != "generate":
            await websocket.send_json({"type": "error", "error": "invalid_command"})
            await websocket.close()
            return

        model = (
            data.get("model")
            or os.getenv("CHUTES_TEXT_MODEL")
            or os.getenv("CHUTES_VLM_MODEL")
            or ""
        )
        prompt = data.get("prompt") or ""
        image = data.get("image")

        await websocket.send_json({"type": "status", "stage": "queued"})

        params = {"model": model, "text": prompt}
        if image:
            params["image"] = image

        await websocket.send_json({"type": "status", "stage": "running"})
        try:
            content = await _sc_chat(
                messages=[{"role": "user", "content": prompt}],
                model=model,
                response_format=None,
                timeout=60,
            )
            await websocket.send_json({"type": "result", "data": content})
            await websocket.close()
        except Exception as e:
            await websocket.send_json({"type": "error", "error": str(e)})
            await websocket.close()
    except WebSocketDisconnect:
        return


@app.post("/api/ux/generate")
async def http_generate(payload: dict):
    # Mock path (for demos without API keys)
    if os.getenv("UX_MOCK_GENERATE", "0") in ("1", "true", "TRUE", "yes"):
        sample = {
            "title": "INFERRED_Table_Example",
            "columns": ["Col A", "Col B", "Col C"],
            "data": [["A1", "B1", "C1"], ["A2", "B2", "C2"]],
        }
        return JSONResponse({"ok": True, "data": sample})

    model = (
        payload.get("model")
        or os.getenv("CHUTES_TEXT_MODEL")
        or os.getenv("CHUTES_VLM_MODEL")
        or ""
    )
    prompt = payload.get("prompt") or ""
    image = payload.get("image")
    params = {"model": model, "text": prompt}
    if image:
        params["image"] = image
    try:
        # Optional debug: include sanitized request/kwargs and exception details
        debug_flag = bool(payload.get("debug"))
        if debug_flag:
            content = await _sc_chat(
                messages=[{"role": "user", "content": prompt}],
                model=model,
                response_format="json_object",
                timeout=60,
            )
            dbg = {"model": model}
            if isinstance(content, str):
                try:
                    obj = _json.loads(content)
                    return JSONResponse({"ok": True, "data": obj, "debug": dbg})
                except Exception:
                    return JSONResponse(
                        {"ok": False, "error": "non_json_output", "debug": dbg}, status_code=502
                    )
            return JSONResponse(
                {"ok": False, "error": "empty_output", "debug": dbg}, status_code=502
            )
        content = await _sc_chat(
            messages=[{"role": "user", "content": prompt}],
            model=model,
            response_format="json_object",
            timeout=60,
        )
        # Normalize to a plain JSON-serializable object
        if isinstance(content, str):
            try:
                obj = _json.loads(content)
                return JSONResponse({"ok": True, "data": obj})
            except Exception:
                return JSONResponse({"ok": True, "data": {"text": content}})
        elif isinstance(content, dict):
            return JSONResponse({"ok": True, "data": content})
        return JSONResponse({"ok": False, "error": "empty_output"}, status_code=502)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/api/ux/mock/generate")
async def http_generate_mock():
    sample = {
        "title": "INFERRED_Table_Example",
        "columns": ["Col A", "Col B", "Col C"],
        "data": [["A1", "B1", "C1"], ["A2", "B2", "C2"]],
    }
    return JSONResponse({"ok": True, "data": sample})


@click.command()
@click.option("--port", type=int, default=8000, help="Port to run the server on")
@click.option("--host", type=str, default="127.0.0.1", help="Host to run the server on")
def server_cli(port: int, host: str):
    import uvicorn

    # Run the server
    uvicorn.run(
        app,
        host=host,
        port=port,
    )


# -----------------------------
# Explorer: list PDFs and stream PDF files
# -----------------------------


def _default_pdfs_root() -> str:
    try:
        here = os.path.abspath(os.path.dirname(__file__))
        cur = here
        for _ in range(6):
            candidate = os.path.join(cur, "data", "pdfs")
            if os.path.isdir(candidate):
                return candidate
            nxt = os.path.dirname(cur)
            if nxt == cur:
                break
            cur = nxt
    except Exception:
        pass
    return os.path.abspath(os.path.join(os.getcwd(), "data", "pdfs"))


SERVER_PDFS_ROOT = os.getenv("SERVER_PDFS_ROOT", _default_pdfs_root())


def _is_within_root(path: str, root: str) -> bool:
    try:
        rp = os.path.realpath(path)
        rr = os.path.realpath(root)
        return rp == rr or rp.startswith(rr + os.sep)
    except Exception:
        return False


def _list_pdfs(root: str) -> list[dict]:
    items: list[dict] = []
    if not os.path.isdir(root):
        return items
    for name in sorted(os.listdir(root)):
        if not name.lower().endswith(".pdf"):
            continue
        fp = os.path.join(root, name)
        try:
            st = os.stat(fp)
            items.append(
                {
                    "name": name,
                    "rel": name,
                    "size": st.st_size,
                    "mtime": st.st_mtime,
                }
            )
        except Exception:
            continue
    return items


@app.get("/api/list")
async def api_list(dir: str | None = None):
    base = SERVER_PDFS_ROOT if not dir else os.path.join(SERVER_PDFS_ROOT, dir)
    if not _is_within_root(base, SERVER_PDFS_ROOT):
        return JSONResponse({"ok": False, "error": "invalid_dir"}, status_code=400)
    return {"ok": True, "root": SERVER_PDFS_ROOT, "items": _list_pdfs(base)}


@app.get("/list")
async def api_list_alias(dir: str | None = None):
    return await api_list(dir)


@app.get("/api/pdf")
async def api_pdf(rel: str):
    fp = os.path.join(SERVER_PDFS_ROOT, rel)
    if not _is_within_root(fp, SERVER_PDFS_ROOT) or not os.path.isfile(fp):
        return JSONResponse({"ok": False, "error": "not_found"}, status_code=404)
    return FileResponse(fp, media_type="application/pdf", filename=os.path.basename(fp))


@app.get("/pdf")
async def api_pdf_alias(rel: str):
    return await api_pdf(rel)


# Simple health endpoint for UI to detect backend status
@app.get("/api/health")
async def api_health():
    try:
        root_exists = os.path.isdir(SERVER_PDFS_ROOT)
        items = _list_pdfs(SERVER_PDFS_ROOT)[:3]
        return {"ok": True, "root": SERVER_PDFS_ROOT, "root_exists": root_exists, "sample": items}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


# Simple LLM health that round-trips a trivial JSON prompt via litellm_call
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
    try:
        out = await _sc_chat(
            messages=[{"role": "user", "content": prompt}],
            model=eff_model,
            response_format="json_object",
            timeout=timeout,
        )
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        ok = False
        data = None
        try:
            data = json.loads((out or "").strip())
            if isinstance(data, dict):
                ok = bool(data.get("ok") is True)
                # Some adapters wrap in {content:{ok:true}}
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
        return JSONResponse(payload, status_code=502)
    except Exception as e:
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        return JSONResponse(
            {"ok": False, "error": str(e), "model": eff_model, "elapsed_ms": elapsed_ms},
            status_code=500,
        )


# -----------------------------
# Proto Telemetry (ArangoDB)
# -----------------------------

EVENTS_COL = "proto_events"
EPISODES_COL = "proto_episodes"
STATUS_COL = "proto_status"
LOGS_COL = "proto_logs"


class EventIngest(BaseModel):
    ts: float
    run_id: str
    variant: str
    session_id: Optional[str] = None
    event: str
    page: Optional[int] = None
    meta: Dict[str, Any] = {}


class EpisodeIngest(BaseModel):
    ts: float
    run_id: str
    episode_id: str
    variant: str
    pass_: bool = Field(default=True, alias="pass")
    score: Optional[float] = None
    metrics: Dict[str, Any] = {}
    error_count: int = 0
    screenshots: List[str] = []

    class Config:
        populate_by_name = True


def _get_db() -> Optional[StandardDatabase]:
    db = app_data.get("arango_db")
    if db is not None:
        return db  # type: ignore

    # Attempt one-time connection on first call
    if connect_arango and ensure_database and ensure_collection:
        client = connect_arango()
        if client is None:
            return None
        db = ensure_database(client)
        if db is None:
            return None
        # Ensure collections
        ensure_collection(db, EVENTS_COL)
        ensure_collection(db, EPISODES_COL)
        ensure_collection(db, STATUS_COL)
        ensure_collection(db, LOGS_COL)
        _ensure_logs_indexes(db)
        app_data["arango_db"] = db
        return db
    return None


# Simple in-process broadcaster for live updates (SSE)
_subscribers: List[asyncio.Queue] = []


async def _broadcast(message: Dict[str, Any]):
    if not _subscribers:
        return
    data = json.dumps(message)
    for q in list(_subscribers):
        try:
            q.put_nowait(data)
        except Exception:
            pass


@app.post("/ingest/event")
async def ingest_event(payload: EventIngest):
    db = _get_db()
    doc = payload.model_dump(by_alias=True)
    if db is not None:
        try:
            db.collection(EVENTS_COL).insert(doc)
        except Exception:
            traceback.print_exc()
    # Also broadcast lightweight update
    await _broadcast({"type": "event", "data": doc})
    return {"ok": True}


@app.post("/ingest/episode")
async def ingest_episode(payload: EpisodeIngest):
    db = _get_db()
    doc = payload.model_dump(by_alias=True)
    if db is not None:
        try:
            db.collection(EPISODES_COL).insert(doc)
            # Upsert status
            aql = f"""
            UPSERT {{ run_id: @run_id, variant: @variant }}
            INSERT {{ run_id: @run_id, variant: @variant, last_ts: @ts, last_score: @score, error_count: @error_count }}
            UPDATE {{ last_ts: @ts, last_score: @score, error_count: @error_count }} IN {STATUS_COL}
            RETURN NEW
            """
            db.aql.execute(
                aql,
                bind_vars={
                    "run_id": doc.get("run_id"),
                    "variant": doc.get("variant"),
                    "ts": doc.get("ts"),
                    "score": doc.get("score"),
                    "error_count": doc.get("error_count", 0),
                },
            )
        except Exception:
            traceback.print_exc()

    await _broadcast({"type": "episode", "data": doc})
    return {"ok": True}


@app.get("/scoreboard")
async def get_scoreboard(run_id: Optional[str] = None):
    db = _get_db()
    if db is None:
        return JSONResponse({"ok": False, "error": "ArangoDB unavailable"}, status_code=503)
    # Simple last-score per variant
    aql = f"""
    FOR s IN {STATUS_COL}
      {"FILTER s.run_id == @run_id" if run_id else ""}
      RETURN s
    """
    rows = list(db.aql.execute(aql, bind_vars={"run_id": run_id} if run_id else None))
    return {"ok": True, "items": rows}


@app.get("/stream")
async def stream():
    async def event_generator():
        q: asyncio.Queue = asyncio.Queue()
        _subscribers.append(q)
        try:
            while True:
                data = await q.get()
                yield f"data: {data}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            try:
                _subscribers.remove(q)
            except ValueError:
                pass

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/episodes")
async def list_episodes(
    run_id: Optional[str] = None, variant: Optional[str] = None, limit: int = 50
):
    db = _get_db()
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
    rows = list(
        db.aql.execute(aql, bind_vars={"run_id": run_id, "variant": variant, "limit": limit})
    )
    return {"ok": True, "items": rows}


@app.get("/logs")
async def list_logs(
    run_id: Optional[str] = None,
    variant: Optional[str] = None,
    source: Optional[str] = None,
    stream: Optional[str] = None,
    limit: int = 100,
):
    db = _get_db()
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
    rows = list(
        db.aql.execute(
            aql,
            bind_vars={
                "run_id": run_id,
                "variant": variant,
                "source": source,
                "stream": stream,
                "limit": limit,
            },
        )
    )
    return {"ok": True, "items": rows}


class LogIngest(BaseModel):
    ts: float
    run_id: str
    variant: Optional[str] = None
    episode_id: Optional[str] = None
    stream: str  # stdout|stderr|app
    level: Optional[str] = None
    source: Optional[str] = None  # orchestrator|validator|codex
    message: str
    meta: Dict[str, Any] = {}


@app.post("/ingest/log")
async def ingest_log(payload: LogIngest):
    db = _get_db()
    doc = payload.model_dump()
    if db is not None:
        try:
            db.collection(LOGS_COL).insert(doc)
        except Exception:
            traceback.print_exc()
    await _broadcast({"type": "log", "data": doc})
    return {"ok": True}


@app.get("/proto/dashboard")
async def proto_dashboard():
    html = """
<!DOCTYPE html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Prototype Orchestrator Dashboard</title>
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 0; background: #0b1220; color: #e6edf3; }
    header { padding: 12px 16px; background: #0f172a; border-bottom: 1px solid #1f2a44; }
    .container { padding: 16px; }
    .row { display: flex; gap: 16px; flex-wrap: wrap; }
    .card { background: #0f172a; border: 1px solid #1f2a44; border-radius: 8px; padding: 12px; min-width: 260px; }
    .muted { color: #9fb3c8; font-size: 12px; }
    .title { font-weight: 600; margin-bottom: 8px; }
    .score { font-size: 28px; font-weight: 700; }
    .ok { color: #26d3a9; }
    .warn { color: #facc15; }
    .err { color: #f87171; }
    table { width: 100%; border-collapse: collapse; margin-top: 12px; }
    th, td { padding: 6px 8px; border-bottom: 1px solid #1f2a44; text-align: left; }
    input, select { background: #0b1220; color: #e6edf3; border: 1px solid #1f2a44; border-radius: 6px; padding: 6px 8px; }
  </style>
  <script>
    const state = { runId: '', status: {}, episodes: [] };
    const logsState = { runId: '', variant: '', source: '', stream: '', limit: 50, items: [] };

    async function fetchScoreboard() {
      const qs = state.runId ? ('?run_id=' + encodeURIComponent(state.runId)) : '';
      const res = await fetch('/scoreboard' + qs);
      const js = await res.json();
      if (js.ok) {
        const map = {};
        for (const it of js.items) { map[it.variant] = it; }
        state.status = map;
        render();
      }
    }

    async function fetchEpisodes(limit=25) {
      const p = new URLSearchParams();
      if (state.runId) p.set('run_id', state.runId);
      p.set('limit', String(limit));
      const res = await fetch('/episodes?' + p.toString());
      const js = await res.json();
      if (js.ok) {
        state.episodes = js.items || [];
        render();
      }
    }

    function connectSSE() {
      const es = new EventSource('/stream');
      es.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data);
          if (msg.type === 'episode') {
            // Update status cache
            const d = msg.data || {};
            const key = d.variant;
            state.status[key] = {
              run_id: d.run_id,
              variant: d.variant,
              last_ts: d.ts,
              last_score: d.score,
              error_count: d.error_count || 0
            };
            // Prepend to episodes (cap at 50)
            state.episodes.unshift(d);
            if (state.episodes.length > 50) state.episodes.length = 50;
            render();
          } else if (msg.type === 'log') {
            const d = msg.data || {};
            const f = logsState;
            if (f.runId && d.run_id !== f.runId) return;
            if (f.variant && d.variant !== f.variant) return;
            if (f.source && d.source !== f.source) return;
            if (f.stream && d.stream !== f.stream) return;
            logsState.items.unshift(d);
            if (logsState.items.length > f.limit) logsState.items.length = f.limit;
            renderLogs();
          }
        } catch (err) {
          console.log('SSE parse error', err);
        }
      };
    }

    function tsFmt(t) {
      if (!t) return '';
      const d = new Date(t*1000);
      return d.toLocaleTimeString();
    }

    function render() {
      const root = document.getElementById('app');
      const keys = Object.keys(state.status).sort();
      const cards = keys.map(k => {
        const s = state.status[k] || {};
        const score = s.last_score != null ? Number(s.last_score).toFixed(2) : '--';
        const color = s.error_count ? 'err' : 'ok';
        return `
          <div class=\"card\">
            <div class=\"title\">Variant: <span>${k}</span></div>
            <div class=\"score ${color}\">${score}</div>
            <div class=\"muted\">Run: ${s.run_id || ''}</div>
            <div class=\"muted\">Updated: ${tsFmt(s.last_ts)}</div>
            <div class=\"muted\">Errors: ${s.error_count || 0}</div>
          </div>
        `;
      }).join('');

      const epRows = (state.episodes || []).map(e => `
        <tr>
          <td>${tsFmt(e.ts)}</td>
          <td>${e.run_id || ''}</td>
          <td>${e.variant || ''}</td>
          <td>${e.episode_id || ''}</td>
          <td>${e.score != null ? Number(e.score).toFixed(2) : ''}</td>
          <td>${e.error_count || 0}</td>
        </tr>
      `).join('');

      root.innerHTML = `
        <div class=\"container\">
          <div style=\"display:flex; gap:8px; align-items:center; margin-bottom:12px;\">
            <label class=\"muted\">Run ID filter</label>
            <input id=\"runInput\" placeholder=\"run-...\" value=\"${state.runId || ''}\" />
            <button id=\"applyBtn\">Apply</button>
          </div>
          <div class=\"row\">${cards}</div>
          <div class=\"card\" style=\"margin-top:16px; width:100%;\">
            <div class=\"title\">Recent Episodes</div>
            <table>
              <thead><tr><th>Time</th><th>Run</th><th>Variant</th><th>Episode</th><th>Score</th><th>Errors</th></tr></thead>
              <tbody>${epRows}</tbody>
            </table>
          </div>
          <div class=\"card\" style=\"margin-top:16px; width:100%;\">
            <div class=\"title\">Logs</div>
            <div style=\"display:flex; gap:8px; flex-wrap: wrap; align-items:center;\">
              <label class=\"muted\">Run</label>
              <input id=\"logRun\" placeholder=\"run-...\" value=\"${logsState.runId || ''}\" />
              <label class=\"muted\">Variant</label>
              <input id=\"logVariant\" placeholder=\"variant\" value=\"${logsState.variant || ''}\" />
              <label class=\"muted\">Source</label>
              <input id=\"logSource\" placeholder=\"codex|server|research|codereview\" value=\"${logsState.source || ''}\" />
              <label class=\"muted\">Stream</label>
              <input id=\"logStream\" placeholder=\"stdout|stderr|app|frontend\" value=\"${logsState.stream || ''}\" />
              <label class=\"muted\">Limit</label>
              <input id=\"logLimit\" type=\"number\" min=\"1\" max=\"500\" value=\"${logsState.limit}\" />
              <button id=\"logApply\">Apply</button>
              <button id=\"logRefresh\">Refresh</button>
            </div>
            <div id=\"logsTable\"></div>
          </div>
        </div>
      `;

      document.getElementById('applyBtn').onclick = async () => {
        const v = (document.getElementById('runInput') || {}).value || '';
        state.runId = v.trim();
        await fetchScoreboard();
        await fetchEpisodes();
      };
      document.getElementById('logApply').onclick = async () => {
        logsState.runId = (document.getElementById('logRun')||{}).value||'';
        logsState.variant = (document.getElementById('logVariant')||{}).value||'';
        logsState.source = (document.getElementById('logSource')||{}).value||'';
        logsState.stream = (document.getElementById('logStream')||{}).value||'';
        const n = parseInt((document.getElementById('logLimit')||{}).value||'50', 10);
        logsState.limit = Number.isFinite(n)? n : 50;
        await fetchLogs();
      };
      document.getElementById('logRefresh').onclick = async () => { await fetchLogs(); };
      renderLogs();
    }

    async function fetchLogs(){
      const p = new URLSearchParams();
      if (logsState.runId) p.set('run_id', logsState.runId);
      if (logsState.variant) p.set('variant', logsState.variant);
      if (logsState.source) p.set('source', logsState.source);
      if (logsState.stream) p.set('stream', logsState.stream);
      p.set('limit', String(logsState.limit||50));
      const res = await fetch('/logs?' + p.toString());
      const js = await res.json();
      if (js.ok){ logsState.items = js.items||[]; renderLogs(); }
    }

    function renderLogs(){
      const cont = document.getElementById('logsTable');
      if (!cont) return;
      const rows = (logsState.items||[]).map(l => `
        <tr>
          <td>${tsFmt(l.ts)}</td>
          <td>${l.run_id||''}</td>
          <td>${l.variant||''}</td>
          <td>${l.source||''}</td>
          <td>${l.stream||''}</td>
          <td style=\"max-width:800px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;\">${(l.message||'').toString().replace(/</g,'&lt;')}</td>
        </tr>
      `).join('');
      cont.innerHTML = `
        <table>
          <thead><tr><th>Time</th><th>Run</th><th>Variant</th><th>Source</th><th>Stream</th><th>Message</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>`;
    }

    window.addEventListener('DOMContentLoaded', async () => {
      connectSSE();
      await fetchScoreboard();
      await fetchEpisodes();
    });
  </script>
</head>
<body>
  <header>
    <div>Prototype Orchestrator Dashboard</div>
  </header>
  <div id=\"app\" class=\"container\">Loading…</div>
</body>
</html>
    """
    return HTMLResponse(html)


def _ensure_logs_indexes(db: StandardDatabase) -> None:  # type: ignore[valid-type]
    try:
        col = db.collection(LOGS_COL)
        existing = list(col.indexes())

        def has(fields, type_):
            for idx in existing:
                if idx.get("type") == type_ and idx.get("fields") == fields:
                    return True
            return False

        # Hash indexes for common filters
        if not has(["run_id"], "hash"):
            col.add_hash_index(["run_id"])
        if not has(["variant"], "hash"):
            col.add_hash_index(["variant"])
        if not has(["source"], "hash"):
            col.add_hash_index(["source"])
        if not has(["stream"], "hash"):
            col.add_hash_index(["stream"])
        # Persistent index for time range queries
        if not has(["ts"], "persistent"):
            col.add_persistent_index(["ts"])
    except Exception:
        # Best-effort; indexes are convenience
        pass


# -----------------------------
# COCO Export (layout)
# -----------------------------
@app.post("/api/coco/export")
async def api_coco_export(payload: dict):
    rel = payload.get("rel")
    boxes_by_page = payload.get("boxes_by_page") or {}
    if not isinstance(rel, str) or not boxes_by_page:
        return JSONResponse({"ok": False, "error": "missing_rel_or_boxes"}, status_code=400)
    fp = os.path.join(SERVER_PDFS_ROOT, rel)
    if not _is_within_root(fp, SERVER_PDFS_ROOT) or not os.path.isfile(fp):
        return JSONResponse({"ok": False, "error": "not_found"}, status_code=404)
    if fitz is None:
        return JSONResponse({"ok": False, "error": "pymupdf_missing"}, status_code=500)
    ts = time.strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.abspath(os.path.join("scripts", "artifacts", f"coco_export_{ts}"))
    os.makedirs(out_dir, exist_ok=True)
    images_out = os.path.join(out_dir, "images")
    os.makedirs(images_out, exist_ok=True)
    coco = {"images": [], "annotations": [], "categories": []}
    seen_types = {}
    ann_id = 1
    img_id = 1
    try:
        doc = fitz.open(fp)
        for p_str, boxes in boxes_by_page.items():
            try:
                page_num = int(p_str)
            except Exception:
                continue
            if page_num < 1 or page_num > len(doc):
                continue
            page = doc[page_num - 1]
            mat = fitz.Matrix(2, 2)
            pix = page.get_pixmap(matrix=mat)
            img_name = f"{os.path.splitext(os.path.basename(rel))[0]}_p{page_num:04d}.png"
            img_path = os.path.join(images_out, img_name)
            pix.save(img_path)
            width, height = pix.width, pix.height
            coco["images"].append(
                {"id": img_id, "file_name": img_name, "width": width, "height": height}
            )
            for b in boxes or []:
                bx = float(b.get("x", 0))
                by = float(b.get("y", 0))
                bw = float(b.get("w", 0))
                bh = float(b.get("h", 0))
                typ = str(b.get("type", "Box"))
                if typ not in seen_types:
                    seen_types[typ] = len(seen_types) + 1
                cat_id = seen_types[typ]
                x_px = max(0, min(width, int(bx * width)))
                y_px = max(0, min(height, int(by * height)))
                w_px = max(1, min(width - x_px, int(bw * width)))
                h_px = max(1, min(height - y_px, int(bh * height)))
                coco["annotations"].append(
                    {
                        "id": ann_id,
                        "image_id": img_id,
                        "category_id": cat_id,
                        "bbox": [x_px, y_px, w_px, h_px],
                        "iscrowd": 0,
                        "area": w_px * h_px,
                    }
                )
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
    if camelot is None:
        return JSONResponse({"ok": False, "error": "camelot_missing"}, status_code=500)
    fp = os.path.join(SERVER_PDFS_ROOT, rel)
    if not _is_within_root(fp, SERVER_PDFS_ROOT) or not os.path.isfile(fp):
        return JSONResponse({"ok": False, "error": "not_found"}, status_code=404)
    try:
        tables = None
        try:
            tables = camelot.read_pdf(str(fp), pages=str(page), flavor="lattice")
        except Exception:
            tables = None
        if (not tables) or (tables.n == 0):
            try:
                tables = camelot.read_pdf(str(fp), pages=str(page), flavor="stream")
            except Exception:
                tables = None
        if (not tables) or tables.n == 0:
            return {"ok": True, "suggestions": []}
        if fitz is None:
            return JSONResponse({"ok": False, "error": "pymupdf_missing"}, status_code=500)
        doc = fitz.open(fp)
        pg = doc[page - 1]
        pw, ph = pg.rect.width, pg.rect.height
        out = []
        for t in tables:
            bb = getattr(t, "_bbox", None) or getattr(t, "bbox", None)
            if not bb:
                continue
            x1, y1, x2, y2 = bb
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
JOBS: dict[str, dict] = {}


@app.post("/api/pipeline/run")
async def api_pipeline_run(payload: dict):
    rel = payload.get("rel")
    if not isinstance(rel, str):
        return JSONResponse({"ok": False, "error": "missing_rel"}, status_code=400)
    job_id = f"job_{int(time.time()*1000)}"
    JOBS[job_id] = {"id": job_id, "rel": rel, "status": "queued", "started": time.time()}

    async def _runner(jid: str, rel_path: str):
        JOBS[jid]["status"] = "running"
        try:
            await asyncio.sleep(1.0)
            JOBS[jid]["result"] = {
                "out_dir": os.path.abspath(os.path.join("scripts", "artifacts", f"pipeline_{jid}"))
            }
            JOBS[jid]["status"] = "done"
        except Exception as e:
            JOBS[jid]["status"] = "error"
            JOBS[jid]["error"] = str(e)

    asyncio.create_task(_runner(job_id, rel))
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
