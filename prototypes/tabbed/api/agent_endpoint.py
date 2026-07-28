#!/usr/bin/env python3
"""Agent endpoint — routes voice/text queries to skills and returns AnswerPayload.

Classification pipeline (no bespoke regex — all via /assistant + /memory):
  1. classify_intent() → /assistant classify --task canvas-intent (SetFit Tier 0.5 → scillm Tier 2)
     Routes to CODE/COMPARE/EXPLAIN/NAVIGATE/QUERY/SEARCH/SKILL/VISUALIZE
  2. SKILL handler → /memory recall skill_route (full /recommend-skill-chain cascade
     integrated into capability_routing.enrich_with_capabilities)
  3. /memory recall — "where is the data?" + skill routing in one call
  4. /assistant validate(task="data-sufficiency-gate") — "is there enough?"
  5. /assistant validate(task="viz-type-selector") + d3_catalog — "what chart type?"
  6. /create-figure — render interactive HTML
  7. AnswerPayload returned to canvas

Shadow-LEGO integration:
  - viz-type-selector and data-sufficiency-gate are registered in /assistant's
    model_registry.json with shadow_mode=true
  - Tier 0 heuristics bootstrap immediately (d3_catalog.recommend_viz + keyword rules)
  - Tier 2 scillm (DeepSeek V3.2) acts as teacher
  - Disagreements logged to ~/.pi/assistant/shadow.jsonl
  - /assistant-lab nightly harvest promotes local models after >=200 labels
  - d3_catalog.py has 60 D3.js viz types with data shape, keyword, and backend metadata

Integration points:
  - /assistant (subprocess): validate() for viz-type-selector, data-sufficiency-gate
  - /memory (port 8601): POST /recall — semantic search over ArangoDB graph
  - /analytics (subprocess): group-by, chart, describe — data profiling for Stage 2
  - /create-figure (subprocess): all chart commands — HTML rendering
  - d3_catalog (import): 60 viz types, recommend_viz(), match_keywords()
  - datalake_api (port 8004): stats, verdicts, convergence — structured data
"""
from __future__ import annotations

import atexit
import asyncio
import html as html_mod
import json
import logging
import os
import re
import sys
import tempfile
import time
import urllib.parse
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

# --- Shared HTTP clients (connection pooling) ---
_http_memory = httpx.AsyncClient(base_url=os.environ.get("MEMORY_SERVICE_URL", "http://127.0.0.1:8601"), timeout=15.0)
_http_datalake = httpx.AsyncClient(base_url=os.environ.get("DATALAKE_API_URL", "http://127.0.0.1:8004"), timeout=30.0)
_http_voice = httpx.AsyncClient(timeout=30.0)

# --- Query length limit (security) ---
MAX_QUERY_LENGTH = 2000
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api/agent", tags=["agent"])
log = logging.getLogger("agent_endpoint")

MEMORY_SERVICE_URL = os.environ.get("MEMORY_SERVICE_URL", "http://127.0.0.1:8601")
DATALAKE_API_URL = os.environ.get("DATALAKE_API_URL", "http://127.0.0.1:8004")

# Skill paths — resolve from pi-mono sibling repo
_PROJECT_ROOT = Path(__file__).resolve().parents[3]  # extractor/
_PI_MONO = _PROJECT_ROOT.parent / "pi-mono"
SKILLS_DIR = _PI_MONO / ".pi" / "skills"
CREATE_FIGURE = SKILLS_DIR / "create-figure" / "run.sh"
ANALYTICS = SKILLS_DIR / "analytics" / "run.sh"
ASSISTANT_PY = SKILLS_DIR / "assistant" / "assistant.py"

# Temp dir for intermediate files
CANVAS_TMP = Path(tempfile.gettempdir()) / "canvas_figures"
CANVAS_TMP.mkdir(exist_ok=True)

# Persistent storage on 12TB drive — all artifacts go here
STORAGE_12TB = Path("/mnt/storage12tb")
D3_GALLERY_DIR = STORAGE_12TB / "artifacts" / "d3_gallery" / "working"
D3_GALLERY_DIR.mkdir(parents=True, exist_ok=True)
D3_METADATA_DIR = STORAGE_12TB / "artifacts" / "d3_gallery" / "metadata"
D3_METADATA_DIR.mkdir(parents=True, exist_ok=True)

EPISODIC_ARCHIVER = SKILLS_DIR / "episodic-archiver" / "run.sh"
SESSIONS_DIR = STORAGE_12TB / "artifacts" / "canvas_sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


# --- Canvas Session Tracker ---
# Tracks the full interaction arc (query → viz → manipulation → manipulation → ...)
# per persona session for /episodic-archiver archival.


class CanvasSession:
    """Tracks a single canvas interaction session for episodic archival.

    A session starts with the first visualization query and accumulates all
    follow-up manipulation commands. Sessions are flushed to disk and archived
    when: (a) a new non-manipulation query arrives, (b) the session times out
    (5 minutes of inactivity), or (c) explicitly flushed.

    Schema matches /episodic-archiver's expected transcript format.
    """

    SESSION_TIMEOUT = 300  # 5 minutes of inactivity → new session

    def __init__(self, persona: str):
        """Initialize a session with a unique ID and persona."""
        self.session_id = str(uuid.uuid4())[:12]
        self.persona = persona
        self.messages: list[dict] = []
        self.started_at = time.time()
        self.last_activity = time.time()
        self.viz_context: dict = {}  # active viz: chart_type, viz_family, title
        self.manipulation_count = 0

    def is_expired(self) -> bool:
        """Check if the session has expired based on last activity time."""
        return (time.time() - self.last_activity) > self.SESSION_TIMEOUT

    def add_user_query(self, query: str, intent: str, confidence: float, source: str) -> None:
        """Append a user query with metadata to the messages list."""
        self.messages.append({
            "from": "User",
            "content": query,
            "timestamp": time.time(),
            "type": "user",
            "metadata": {
                "intent": intent,
                "confidence": confidence,
                "source": source,
            },
        })
        self.last_activity = time.time()

    def add_agent_answer(self, payload: dict, chart_type: str = "", viz_family: str = "") -> None:
        """Record agent's visualization or text response."""
        category = "visualization" if payload.get("type") == "html" else payload.get("type", "text")
        self.messages.append({
            "from": "agent",
            "content": payload.get("summary", payload.get("title", "")),
            "timestamp": time.time(),
            "type": "answer",
            "category": category,
            "metadata": {
                "answer_type": payload.get("type"),
                "chart_type": chart_type,
                "viz_family": viz_family,
                "source": payload.get("source", ""),
                "title": payload.get("title", ""),
            },
        })
        self.viz_context = {
            "chart_type": chart_type,
            "viz_family": viz_family,
            "title": payload.get("title", ""),
        }
        self.last_activity = time.time()

    def add_manipulation(self, query: str, commands: list[dict]) -> None:
        """Record a manipulation command on the active visualization."""
        self.messages.append({
            "from": "User",
            "content": query,
            "timestamp": time.time(),
            "type": "user",
            "category": "manipulation",
        })
        self.messages.append({
            "from": "agent",
            "content": json.dumps(commands),
            "timestamp": time.time(),
            "type": "manipulation",
            "category": "manipulation",
            "metadata": {
                "commands": commands,
                "viz_context": self.viz_context.copy(),
                "manipulation_index": self.manipulation_count,
            },
        })
        self.manipulation_count += 1
        self.last_activity = time.time()

    def to_transcript(self) -> dict:
        """Serialize to /episodic-archiver transcript format."""
        return {
            "session_id": f"canvas_{self.session_id}",
            "user_id": os.environ.get("PI_USER_ID", "graham"),
            "persona_id": self.persona,
            "source": "canvas_voice",
            "started_at": self.started_at,
            "ended_at": self.last_activity,
            "duration_s": self.last_activity - self.started_at,
            "total_turns": len(self.messages),
            "manipulation_count": self.manipulation_count,
            "viz_context": self.viz_context,
            "messages": self.messages,
        }

    def flush_to_disk(self) -> Optional[Path]:
        """Write transcript to ~/.pi/sessions/canvas/ for archival."""
        if not self.messages:
            return None
        transcript = self.to_transcript()
        filename = f"{self.session_id}_{self.persona}_{int(self.started_at)}.json"
        path = SESSIONS_DIR / filename
        path.write_text(json.dumps(transcript, indent=2))
        log.info(
            "Canvas session flushed: %s (%d turns, %d manipulations)",
            path.name, len(self.messages), self.manipulation_count,
        )
        return path


async def _archive_session(session: CanvasSession) -> None:
    """Flush session to disk and submit to /episodic-archiver."""
    path = session.flush_to_disk()
    if not path:
        return

    if not EPISODIC_ARCHIVER.exists():
        log.debug("episodic-archiver not found, session saved to %s only", path)
        return

    try:
        cmd = [str(EPISODIC_ARCHIVER), "archive", str(path)]
        rc, stdout, stderr = await _run_skill(cmd, timeout=30.0)
        if rc != 0:
            log.warning("episodic-archiver failed (rc=%d): %s", rc, stderr[:200])
        else:
            log.info("Session archived: %s", path.name)
    except Exception as e:
        log.warning("episodic-archiver error: %s", e)


# Active sessions per persona — single session per persona at a time
_active_sessions: dict[str, CanvasSession] = {}
_session_lock = asyncio.Lock()


async def _get_or_create_session(persona: str, is_manipulation: bool = False) -> CanvasSession:
    """Get the active session for a persona, or create a new one.

    If the current session is expired OR a new non-manipulation query arrives,
    the old session is flushed and a new one starts.
    """
    async with _session_lock:
        session = _active_sessions.get(persona)

        if session is None:
            session = CanvasSession(persona)
            _active_sessions[persona] = session
            return session

        if session.is_expired():
            asyncio.get_running_loop().create_task(_archive_session(session))
            session = CanvasSession(persona)
            _active_sessions[persona] = session
            return session

        return session


# --- Models ---


class AskRequest(BaseModel):
    """Define an ask request with query and optional persona."""
    query: str
    persona: str = "embry"


class AnswerPayload(BaseModel):
    """Define a structured payload for various answer content types."""
    type: str  # "image" | "html" | "data" | "table" | "text"
    title: Optional[str] = None
    content: str  # URL, HTML, JSON string, or plain text
    summary: Optional[str] = None  # TTS speaks this
    source: Optional[str] = None  # citation
    vizFamily: Optional[str] = None  # D3 viz family hint for manipulation routing
    sources_cited: int = 0  # Number of /memory QRA sources cited in response


# --- Subprocess helpers ---


async def _run_skill(cmd: list[str], timeout: float = 30.0) -> tuple[int, str, str]:
    """Run a skill subprocess and return (returncode, stdout, stderr)."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return -1, "", "Skill timed out"
    return proc.returncode or 0, stdout.decode(errors="replace"), stderr.decode(errors="replace")


# --- d3_catalog integration ---

# Import the D3 visualization catalog from /create-figure
sys.path.insert(0, str(SKILLS_DIR / "create-figure"))
try:
    from d3_catalog import (
        D3_VIZ_CATALOG,
        recommend_viz,
        match_keywords as catalog_match_keywords,
        get_viz_type,
        get_implemented_viz_types,
        DataShape,
    )
    D3_CATALOG_AVAILABLE = True
except ImportError:
    D3_CATALOG_AVAILABLE = False
    log.warning("d3_catalog not importable — using legacy heuristics")


# --- Stage 1: Binary classifier — VISUALIZE vs TEXT_RESPONSE ---
# "Can the user's question map to a visualization, or is a text/voice response
#  more appropriate?" This gate runs BEFORE data gathering.

_VIZ_INTENTS = {"VISUALIZE", "COMPARE"}
_TEXT_INTENTS = {"EXPLAIN", "QUERY", "SEARCH", "CODE", "NAVIGATE"}


# --- /assistant Shadow-LEGO integration ---


# Tier 0 heuristic: data shape → sufficiency
_MIN_POINTS_FOR_CHART: dict[str, int] = {}
if D3_CATALOG_AVAILABLE:
    _MIN_POINTS_FOR_CHART = {name: v.min_data_points for name, v in D3_VIZ_CATALOG.items()}
else:
    _MIN_POINTS_FOR_CHART = {
        "line": 3, "bar": 2, "hbar": 2, "pie": 2, "radar": 3,
        "heatmap": 4, "sankey": 2, "table": 1, "text": 0,
    }


def _heuristic_viz_type(query: str, data_shape: dict) -> Optional[dict]:
    """Stage 2 Tier 0 heuristic for viz-type-selector.

    Uses d3_catalog.recommend_viz() for data-shape-driven recommendations,
    plus keyword matching from the catalog's 60 viz types.

    Returns dict with chart_type/reason/confidence, or None to escalate to /assistant.
    """
    q = query.lower()
    row_count = data_shape.get("row_count", 0)
    col_count = data_shape.get("col_count", 0)
    has_time_axis = data_shape.get("has_time_axis", False)
    max_label_len = data_shape.get("max_label_len", 0)
    nested = data_shape.get("nested", False)

    # No data → text
    if row_count == 0:
        return {"chart_type": "text", "reason": "no data available", "confidence": 0.95}
    if row_count == 1:
        return {"chart_type": "gauge", "reason": "single data point — KPI display", "confidence": 0.8}

    # Use d3_catalog for data-shape-driven recommendation
    if D3_CATALOG_AVAILABLE:
        # Infer column types from data_shape
        col_types: dict[str, str] = {}
        if has_time_axis:
            col_types["time"] = "datetime"
        if col_count >= 2:
            for i in range(min(col_count, 10)):
                col_types[f"col_{i}"] = "numeric"

        recs = recommend_viz(
            n_rows=row_count,
            n_cols=col_count,
            col_types=col_types,
            has_time=has_time_axis,
            has_hierarchy=nested,
            query=query,
        )

        if recs:
            top_name, top_conf, top_reason = recs[0]
            # Check if this viz type has a rendering backend
            viz = get_viz_type(top_name)
            if viz and viz.backend.value != "not_yet":
                return {
                    "chart_type": top_name,
                    "reason": f"d3_catalog: {top_reason}",
                    "confidence": min(0.9, 0.5 + top_conf * 0.15),
                    "alternatives": [
                        {"type": r[0], "score": r[1], "reason": r[2]}
                        for r in recs[1:4]
                    ],
                }

    # Legacy fallback when d3_catalog unavailable
    if has_time_axis and row_count >= 3:
        return {"chart_type": "line", "reason": "time series data with 3+ points", "confidence": 0.9}
    if col_count >= 5 and row_count >= 3:
        return {"chart_type": "table", "reason": "wide data (5+ columns)", "confidence": 0.7}
    if nested and col_count >= 3:
        return {"chart_type": "radar", "reason": "nested multi-dimensional data", "confidence": 0.7}
    if max_label_len > 15 and row_count >= 2:
        return {"chart_type": "hbar", "reason": "long labels suggest horizontal bar", "confidence": 0.65}
    if 2 <= row_count <= 8:
        return {"chart_type": "bar", "reason": "small categorical dataset", "confidence": 0.6}

    return None  # escalate to higher tier


def _heuristic_data_sufficiency(query: str, data_summary: dict) -> Optional[dict]:
    """Tier 0 heuristic for data-sufficiency-gate. Returns dict or None to escalate."""
    sources = data_summary.get("sources_available", [])
    row_count = data_summary.get("row_count", 0)
    null_pct = data_summary.get("null_pct", 0)

    if not sources:
        return {
            "verdict": "INSUFFICIENT",
            "reason": "No data sources responded",
            "missing": ["datalake API", "memory service"],
            "confidence": 0.95,
        }

    if row_count == 0:
        return {
            "verdict": "INSUFFICIENT",
            "reason": "Data sources responded but returned no records",
            "missing": ["relevant data for this query"],
            "confidence": 0.9,
        }

    if null_pct > 50:
        return {
            "verdict": "PARTIAL",
            "reason": f"Data is {null_pct:.0f}% null/missing",
            "missing": ["complete data"],
            "confidence": 0.8,
        }

    if row_count >= 2:
        return {
            "verdict": "SUFFICIENT",
            "reason": f"{row_count} data points from {', '.join(sources)}",
            "missing": [],
            "confidence": 0.85,
        }

    # Single data point
    return {
        "verdict": "PARTIAL",
        "reason": "Only 1 data point — can answer but not visualize trends",
        "missing": ["historical data for comparison"],
        "confidence": 0.75,
    }


async def _assistant_validate(task: str, input_data: dict, heuristic_fn=None) -> dict:
    """Call /assistant validate() via subprocess with Shadow-LEGO cascade.

    Tier 0 heuristic runs inline. If it returns a result with confidence >= threshold,
    we use it. Otherwise escalates to /assistant (Tier 0.5 → 1.5 → 2).

    The shadow log captures ALL decisions for nightly harvest.
    """
    # Try Tier 0 heuristic first
    if heuristic_fn:
        result = heuristic_fn(**input_data) if callable(heuristic_fn) else None
        if result and result.get("confidence", 0) >= 0.7:
            # Log shadow entry for the heuristic decision
            # (shadow mode in /assistant will also run scillm in parallel)
            return result

    # Escalate to /assistant validate (Tier 0.5 → 1.5 → 2)
    if not ASSISTANT_PY.exists():
        log.warning("assistant.py not found at %s, using heuristic only", ASSISTANT_PY)
        # Fall back to heuristic with lower threshold
        if heuristic_fn:
            result = heuristic_fn(**input_data) if callable(heuristic_fn) else None
            if result:
                return result
        return {}

    cmd = [
        sys.executable, str(ASSISTANT_PY),
        "validate",
        "--task", task,
        "--input", json.dumps(input_data),
    ]

    rc, stdout, stderr = await _run_skill(cmd, timeout=15.0)
    if rc != 0:
        log.warning("assistant validate task=%s failed (rc=%d): %s", task, rc, stderr[:300])
        # Heuristic fallback on assistant failure
        if heuristic_fn:
            result = heuristic_fn(**input_data) if callable(heuristic_fn) else None
            if result:
                return result
        return {}

    # Parse the result — assistant outputs JSON to stdout
    try:
        result = json.loads(stdout)
        # TierResult has .result field containing the actual output
        actual = result.get("result", result)
        if isinstance(actual, str):
            try:
                actual = json.loads(actual)
            except json.JSONDecodeError:
                actual = {"raw": actual}
        return actual
    except json.JSONDecodeError:
        log.warning("assistant validate returned non-JSON: %s", stdout[:200])
        return {}


def _extract_explicit_viz_type(query: str) -> Optional[str]:
    """Tier -1: Check if the user explicitly named a chart type.

    Personas often request specific visualizations by name:
      "Show me a Sankey chart of the supply chain for Component X"
      "heatmap of compliance scores"
      "radar chart comparing Margaret vs Jennifer"

    If they said it by name, that IS the answer — no classification needed.
    Returns the viz type name or None if no explicit mention found.
    """
    if not D3_CATALOG_AVAILABLE:
        return None

    q = query.lower()

    # Check all 60 catalog types — longest match first to avoid "bar" matching "stacked_bar"
    explicit_matches: list[tuple[str, int]] = []
    for name, viz in D3_VIZ_CATALOG.items():
        # Check the machine name (e.g., "sankey", "heatmap", "force_graph")
        readable_name = name.replace("_", " ")
        if readable_name in q:
            explicit_matches.append((name, len(readable_name)))
        # Check the human label (e.g., "Sankey Diagram", "Radar / Spider Chart")
        label_lower = viz.label.lower()
        # Handle labels with "/" like "Radar / Spider Chart"
        for label_variant in label_lower.split(" / "):
            label_variant = label_variant.strip()
            if label_variant in q:
                explicit_matches.append((name, len(label_variant)))

    if not explicit_matches:
        return None

    # Return the longest match (most specific)
    explicit_matches.sort(key=lambda x: x[1], reverse=True)
    best_name = explicit_matches[0][0]

    # Validate the type has a backend (even NOT_YET — /figure-lab may compose it)
    viz = get_viz_type(best_name)
    if viz:
        log.info("Explicit viz type '%s' extracted from query", best_name)
        return best_name
    return None


async def _select_viz_type(query: str, data_shape: dict) -> str:
    """Use Shadow-LEGO cascade to pick optimal chart type.

    Tier -1:  Explicit mention (user said the chart type by name)
    Tier 0.5: SetFit viz-type classifier (if trained)
    Tier 0:   d3_catalog heuristic (keyword + shape rules)
    Tier 1.5+: /assistant validate(task="viz-type-selector") with scillm shadow

    Disagreements between classifier and heuristic are logged for nightly harvest.
    """
    # Tier -1: Explicit chart type in query — highest priority.
    # Uses /assistant cascade: regex heuristic → chart-type-extractor classifier → scillm.
    # If user says "sankey chart" or "spider chart", that IS the answer.
    explicit = _extract_explicit_viz_type(query)
    if explicit:
        return explicit

    # Also try /assistant chart-type-extractor for cases regex misses (synonyms, etc.)
    extractor_result = await _assistant_validate(
        task="chart-type-extractor",
        input_data={"query": query},
        heuristic_fn=lambda query: (
            {"chart_type": _extract_explicit_viz_type(query), "confidence": 0.95}
            if _extract_explicit_viz_type(query)
            else None
        ),
    )
    extracted = extractor_result.get("chart_type")
    if extracted and extracted != "null":
        return extracted

    # Tier 0.5: Try SetFit classifier
    clf_type, clf_confidence = _classify_viz_type_classifier(query)
    heuristic_result = _heuristic_viz_type(query, data_shape)
    heuristic_type = heuristic_result.get("chart_type") if heuristic_result else None

    if clf_type is not None:
        # Log disagreement for shadow harvest
        if heuristic_type and clf_type != heuristic_type:
            _log_viz_type_disagreement(query, clf_type, heuristic_type, data_shape)
        return clf_type

    # Tier 0: Heuristic with high confidence
    if heuristic_result and heuristic_result.get("confidence", 0) >= 0.7:
        return heuristic_result.get("chart_type", "bar")

    # Tier 1.5+: Escalate to /assistant
    result = await _assistant_validate(
        task="viz-type-selector",
        input_data={"query": query, "data_shape": data_shape},
        heuristic_fn=lambda query, data_shape: _heuristic_viz_type(query, data_shape),
    )
    return result.get("chart_type", heuristic_type or "bar")


def _log_viz_type_disagreement(
    query: str, clf: str, heuristic: str, data_shape: dict,
) -> None:
    """Log viz-type classifier vs heuristic disagreement for shadow harvest."""
    shadow_path = Path.home() / ".pi" / "assistant" / "shadow.jsonl"
    entry = {
        "task": "viz-type-selector",
        "input": {"text": query, "data_shape": data_shape},
        "classifier": clf,
        "heuristic": heuristic,
        "ts": __import__("time").time(),
    }
    try:
        with open(shadow_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


async def _check_data_sufficiency(query: str, data_summary: dict) -> dict:
    """Use /assistant Shadow-LEGO cascade to check if enough data exists.

    Tier 0: _heuristic_data_sufficiency (threshold rules)
    Tier 0.5+: /assistant validate(task="data-sufficiency-gate") with scillm shadow
    """
    result = await _assistant_validate(
        task="data-sufficiency-gate",
        input_data={"query": query, "data_summary": data_summary},
        heuristic_fn=lambda query, data_summary: _heuristic_data_sufficiency(query, data_summary),
    )
    return result


# --- /create-figure rendering ---


def _get_viz_family(chart_type: str) -> str:
    """Look up the VizFamily for a chart type from d3_catalog."""
    if D3_CATALOG_AVAILABLE:
        viz = get_viz_type(chart_type)
        if viz:
            return viz.family.value
    # Fallback mapping for common types
    _FALLBACK_FAMILIES = {
        "bar": "bar", "hbar": "bar", "grouped_bar": "bar", "stacked_bar": "bar",
        "line": "line", "area": "area", "sparkline": "line",
        "scatter": "dot", "bubble": "dot", "beeswarm": "dot",
        "pie": "pie", "donut": "pie",
        "radar": "radial", "gauge": "radial",
        "heatmap": "specialty", "calendar": "specialty", "word_cloud": "specialty",
        "treemap": "hierarchy", "sunburst": "hierarchy", "circle_packing": "hierarchy",
        "icicle": "hierarchy", "tidy_tree": "hierarchy", "radial_tree": "hierarchy",
        "force_graph": "network", "chord": "network", "arc_diagram": "network",
        "sankey": "flow",
        "histogram": "distribution", "violin": "distribution", "ridgeline": "distribution",
        "table": "table", "text": "table",
    }
    return _FALLBACK_FAMILIES.get(chart_type, "bar")


def _inject_manipulation_runtime(html: str, viz_family: str = "") -> str:
    """Inject the D3 manipulation runtime into HTML visualization output.

    The runtime enables postMessage-based manipulation of D3 visualizations:
    zoom, pan, highlight, focus, filter, expand, collapse, drill_down, etc.

    Every HTML visualization returned to the canvas gets this injected so that
    follow-up voice commands ("zoom in on Node X") can manipulate the live viz.
    """
    runtime_path = Path(__file__).parent.parent / "html" / "src" / "lib" / "d3-manipulate-runtime.js"
    if runtime_path.exists():
        runtime_js = runtime_path.read_text()
    else:
        # Inline minimal runtime if file not found
        runtime_js = _INLINE_MANIPULATION_RUNTIME

    # Add viz family hint as a data attribute
    family_attr = f' data-viz-family="{viz_family}"' if viz_family else ""
    _safe_family = json.dumps(viz_family).replace("</", "<\\/") if viz_family else ""
    family_script = f"\nwindow.__vizFamily = {_safe_family};" if viz_family else ""

    script = f"<script>{family_script}\n{runtime_js}</script>"

    if "</body>" in html:
        return html.replace("</body>", f"{script}\n</body>")
    if "</html>" in html:
        return html.replace("</html>", f"{script}\n</html>")
    return html + script


# Inline fallback — minimal manipulation runtime when the file isn't bundled
_INLINE_MANIPULATION_RUNTIME = """
(function() {
  var svg, zoomBehavior;
  function init() {
    svg = document.querySelector('svg');
    if (!svg) { setTimeout(init, 200); return; }
    if (typeof d3 !== 'undefined' && d3.zoom) {
      zoomBehavior = d3.zoom().scaleExtent([0.1, 20]).on('zoom', function(e) {
        var g = svg.querySelector('g.zoom-layer');
        if (!g) { g = document.createElementNS('http://www.w3.org/2000/svg','g'); g.classList.add('zoom-layer'); while(svg.firstChild&&svg.firstChild!==g) g.appendChild(svg.firstChild); svg.appendChild(g); }
        g.setAttribute('transform', e.transform.toString());
      });
      d3.select(svg).call(zoomBehavior);
    }
  }
  var handlers = {
    zoom_in: function(c) { if(zoomBehavior&&svg) d3.select(svg).transition().duration(500).call(zoomBehavior.scaleBy, c.params&&c.params.scale||1.5); },
    zoom_out: function(c) { if(zoomBehavior&&svg) d3.select(svg).transition().duration(500).call(zoomBehavior.scaleBy, c.params&&c.params.scale||0.67); },
    highlight: function(c) {
      if(!svg||!c.target) return;
      svg.querySelectorAll('.d3m-dimmed').forEach(function(el){el.classList.remove('d3m-dimmed');el.style.removeProperty('opacity');});
      svg.querySelectorAll('.d3m-highlighted').forEach(function(el){el.classList.remove('d3m-highlighted');el.style.removeProperty('stroke');el.style.removeProperty('stroke-width');el.style.removeProperty('filter');});
      var t=c.target.toLowerCase();
      svg.querySelectorAll('text').forEach(function(txt){
        if((txt.textContent||'').toLowerCase().includes(t)){
          var p=txt.closest('g')||txt;
          p.classList.add('d3m-highlighted');
          p.style.stroke='#FFD700';p.style.strokeWidth='3px';p.style.filter='drop-shadow(0 0 6px #FFD700)';
        }
      });
    },
    reset: function() {
      if(!svg) return;
      svg.querySelectorAll('.d3m-highlighted,.d3m-dimmed').forEach(function(el){el.classList.remove('d3m-highlighted','d3m-dimmed');el.style.removeProperty('opacity');el.style.removeProperty('stroke');el.style.removeProperty('stroke-width');el.style.removeProperty('filter');});
      if(zoomBehavior) d3.select(svg).transition().duration(500).call(zoomBehavior.transform, d3.zoomIdentity);
    },
    pan: function(c) { if(zoomBehavior&&svg) d3.select(svg).transition().duration(300).call(zoomBehavior.translateBy, c.params&&c.params.dx||0, c.params&&c.params.dy||0); },
    focus: function(c) { handlers.highlight(c); },
    expand: function() {},
    collapse: function() {},
    drill_down: function() {},
    drill_up: function() { handlers.reset(); },
    filter: function() {},
    highlight_related: function(c) { handlers.highlight(c); },
    highlight_path: function(c) { handlers.highlight(c); },
    explode: function() {},
    zoom_to: function(c) { handlers.highlight(c); handlers.zoom_in(c); }
  };
  window.addEventListener('message', function(e) {
    if(!e.data||e.data.type!=='d3-manipulate') return;
    (e.data.commands||[]).forEach(function(cmd){ var h=handlers[cmd.action]; if(h) try{h(cmd)}catch(err){} });
    if(e.source) e.source.postMessage({type:'d3-manipulate-ack',executed:(e.data.commands||[]).map(function(c){return c.action})},e.origin);
  });
  window.d3Manipulate = function(cmd) { var h=handlers[cmd.action]; if(h) h(cmd); };
  var style=document.createElement('style');
  style.textContent='.d3m-highlighted{transition:all .3s ease-out}.d3m-dimmed{transition:opacity .3s;pointer-events:none}svg{cursor:grab}svg:active{cursor:grabbing}';
  document.head.appendChild(style);
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',init); else init();
})();
"""


async def _render_figure(
    data: dict,
    chart_type: str = "metrics",
    figure_type: str = "bar",
    title: str = "Chart",
    canvas: bool = True,
) -> Optional[str]:
    """Render data through /create-figure and return HTML content.

    Pipeline: write JSON → run create-figure → read HTML/SVG output.
    When canvas=True (default for answer canvas), passes --canvas flag
    for 5ft distance-aware responsive HTML output.
    Returns None if rendering fails (caller falls back to D3).
    """
    if not CREATE_FIGURE.exists():
        log.warning("create-figure not found at %s", CREATE_FIGURE)
        return None

    _uid = uuid.uuid4().hex[:12]
    input_file = CANVAS_TMP / f"input_{_uid}.json"
    output_file = CANVAS_TMP / f"output_{_uid}.html"
    input_file.write_text(json.dumps(data))

    try:
        cmd = [
            str(CREATE_FIGURE),
            chart_type,
            "--input", str(input_file),
            "--output", str(output_file),
            "--title", title,
        ]
        if chart_type == "metrics" and figure_type:
            cmd.extend(["--type", figure_type])
        if canvas:
            cmd.append("--canvas")

        rc, stdout, stderr = await _run_skill(cmd, timeout=30.0)

        if rc != 0:
            log.warning("create-figure failed (rc=%d): %s", rc, stderr[:500])
            svg_file = output_file.with_suffix(".svg")
            if svg_file.exists():
                return svg_file.read_text()
            return None

        if output_file.exists():
            return output_file.read_text()

        # create-figure may produce .svg/.png instead of .html
        for ext in (".svg", ".png", ".pdf"):
            alt = output_file.with_suffix(ext)
            if alt.exists():
                if ext == ".svg":
                    return alt.read_text()
                import base64
                b64 = base64.b64encode(alt.read_bytes()).decode()
                mime = "image/png" if ext == ".png" else "application/pdf"
                return f'<img src="data:{mime};base64,{b64}" style="max-width:100%;max-height:90vh;"/>'

        return None
    except Exception as e:
        log.warning("create-figure error: %s", e)
        return None
    finally:
        input_file.unlink(missing_ok=True)
        output_file.unlink(missing_ok=True)
        for _ext in (".svg", ".png", ".pdf"):
            output_file.with_suffix(_ext).unlink(missing_ok=True)


# --- Data helpers ---


async def _memory_recall(query: str, k: int = 10, scope: str = "") -> Optional[dict]:
    """Query /memory recall API (uses shared httpx client)."""
    try:
        body: dict[str, Any] = {"q": query[:MAX_QUERY_LENGTH], "k": k, "threshold": 0.3}
        if scope:
            body["scope"] = scope
        resp = await _http_memory.post("/recall", json=body)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        log.warning("memory recall failed: %s", e)
        return None


# --- Taxonomy bridge keywords (inline, mirrors pi-mono/.pi/skills/taxonomy/taxonomy.py) ---

_BRIDGE_KEYWORDS: dict[str, list[str]] = {
    "Precision": [
        "optimiz", "efficien", "precis", "algorithm", "calculat", "method",
        "methodical", "analytical", "strategic", "technical", "meticulous",
        "systematic", "logical", "quantitative", "accuracy", "exact",
    ],
    "Resilience": [
        "error handl", "fault tol", "robust", "redund", "recover", "resili",
        "harden", "isolate", "restore", "defense", "endur", "withstand",
        "retry", "fallback", "failover", "backup", "durab",
    ],
    "Fragility": [
        "fail", "break", "crash", "vulner", "weak", "brittle", "unstable",
        "fragile", "degrad", "corrupt", "broken", "bug", "error", "issue",
        "problem", "bottleneck", "limitation",
    ],
    "Corruption": [
        "tamper", "inject", "exploit", "malicious", "poison", "corrupt",
        "manipulat", "forge", "spoof", "compromis", "adversar",
    ],
    "Loyalty": [
        "trust", "verif", "authentic", "complian", "certif", "audit",
        "standard", "regulat", "loyal", "reliab", "consistent", "faithful",
        "DO-178", "MIL-STD", "NIST", "quality",
    ],
    "Stealth": [
        "stealth", "hidden", "covert", "obfuscat", "evasion", "cach",
        "latent", "background", "silent", "implicit", "shadow",
    ],
}


def _extract_query_bridges(text: str) -> set[str]:
    """Fast keyword-based bridge tag extraction from query text (~0ms)."""
    text_lower = text.lower()
    bridges = set()
    for tag, patterns in _BRIDGE_KEYWORDS.items():
        if any(p in text_lower for p in patterns):
            bridges.add(tag)
    return bridges


def _item_bridges(item: dict) -> set[str]:
    """Extract bridge tags from a /memory recall item."""
    bridges = set()
    # From taxonomy.bridge_attributes or taxonomy.bridge_tags
    tax = item.get("taxonomy", {})
    if not isinstance(tax, dict):
        tax = {}
    for field in ("bridge_attributes", "bridge_tags"):
        val = tax.get(field, [])
        if isinstance(val, list):
            for tag in val:
                bridges.add(tag)
    # From top-level bridge_attributes
    for tag in item.get("bridge_attributes", []):
        bridges.add(tag)
    # From tags (some items store bridges as tags)
    for tag in item.get("tags", []):
        if tag in ("Precision", "Resilience", "Fragility", "Corruption", "Loyalty", "Stealth"):
            bridges.add(tag)
    return bridges


def _item_collection_tags(item: dict) -> set[str]:
    """Extract collection tags from a /memory recall item for intersection."""
    tags = set()
    tax = item.get("taxonomy", {})
    if not isinstance(tax, dict):
        return tags
    ct = tax.get("collection_tags", {})
    if not isinstance(ct, dict):
        return tags
    for dim_values in ct.values():
        if isinstance(dim_values, str):
            tags.add(dim_values.lower())
        elif isinstance(dim_values, list):
            tags.update(v.lower() for v in dim_values)
    return tags


def _rank_by_taxonomy(query: str, items: list[dict]) -> list[dict]:
    """Re-rank /memory recall items by taxonomy bridge intersection with query.

    Scoring: bridge_overlap * 0.6 + tag_keyword_overlap * 0.2 + original_rank * 0.2
    Items with zero intersection keep their original position (no penalty).
    """
    if not items:
        return items

    query_bridges = _extract_query_bridges(query)
    query_tags = set(re.findall(r"\b\w{4,}\b", query.lower()))

    scored = []
    for rank, item in enumerate(items):
        item_br = _item_bridges(item)
        item_tags = set(t.lower() for t in item.get("tags", []))

        # Bridge intersection (0.0 - 1.0)
        if query_bridges and item_br:
            bridge_score = len(query_bridges & item_br) / max(len(query_bridges), 1)
        elif not query_bridges:
            bridge_score = 0.5  # No bridges in query → neutral
        else:
            bridge_score = 0.0

        # Tag keyword overlap (0.0 - 1.0)
        if item_tags:
            tag_score = len(query_tags & item_tags) / max(len(item_tags), 1)
        else:
            tag_score = 0.0

        # Original rank score (higher = worse, normalized to 0-1)
        rank_score = 1.0 - (rank / max(len(items), 1))

        composite = bridge_score * 0.6 + tag_score * 0.2 + rank_score * 0.2
        scored.append((composite, rank, item))

    scored.sort(key=lambda x: (-x[0], x[1]))
    return [item for _, _, item in scored]


def _format_citations(items: list[dict], max_citations: int = 3) -> str:
    """Format top /memory items as QRA citations for Embry's response.

    Citations are always included when relevant items exist.
    Format: numbered list with source scope and key.
    """
    if not items:
        return ""

    lines = ["\n\n---\n**Sources cited:**"]
    for i, item in enumerate(items[:max_citations]):
        key = item.get("_key", "")
        scope = item.get("scope", "")
        source = item.get("_source", "")
        solution = (item.get("solution") or item.get("playbook") or "")[:300]
        problem = (item.get("problem") or item.get("title") or "")[:120]

        if not solution:
            continue

        scope_label = f" ({scope})" if scope else ""
        source_label = f" [{source}]" if source else ""
        lines.append(f"\n[{i+1}] **{problem}**{scope_label}{source_label}")
        lines.append(f"   {solution}")

    if len(lines) <= 1:
        return ""
    return "\n".join(lines)


def _format_citations_html(items: list[dict], max_citations: int = 3) -> str:
    """Format citations as HTML block for embedding in viz responses."""
    if not items:
        return ""

    parts = ["<div style='font-family:system-ui;font-size:14px;padding:8px 16px;"
             "border-top:1px solid #e2e8f0;margin-top:8px;color:#64748b;'>"]
    parts.append("<details><summary style='cursor:pointer;font-weight:600;"
                 "font-size:13px;'>Sources cited</summary>")
    for i, item in enumerate(items[:max_citations]):
        scope = item.get("scope", "")
        solution = (item.get("solution") or "")[:200]
        problem = (item.get("problem") or item.get("title") or "")[:100]
        if not solution:
            continue
        scope_label = f" <em>({scope})</em>" if scope else ""
        parts.append(f"<p style='margin:4px 0;font-size:13px;'>"
                     f"<strong>[{i+1}]</strong> {problem}{scope_label}<br/>"
                     f"<span style='color:#94a3b8;'>{solution}</span></p>")
    parts.append("</details></div>")
    return "\n".join(parts)


async def _recall_and_rank(
    query: str, k: int = 10, scope: str = "",
) -> tuple[list[dict], str, str]:
    """Recall from /memory, rank by taxonomy intersection, format citations.

    Returns (ranked_items, text_citations, html_citations).
    """
    memory = await _memory_recall(query, k=k, scope=scope)
    items = memory.get("items", []) if memory else []
    ranked = _rank_by_taxonomy(query, items)
    text_cites = _format_citations(ranked)
    html_cites = _format_citations_html(ranked)
    return ranked, text_cites, html_cites


async def _get_skill_route(query: str) -> str | None:
    """Extract skill name from /memory recall skill_route.

    /memory recall now includes the full /recommend-skill-chain cascade
    (Markov + DistilBERT + scillm) via capability_routing.enrich_with_capabilities().
    Returns the first skill in the chain or None.
    """
    recall = await _memory_recall(query, k=3)
    if not recall:
        return None
    route = recall.get("skill_route")
    if not route:
        return None

    # Full cascade format: {chain: [...], confidence: float, ...}
    chain = route.get("chain", [])
    confidence = route.get("confidence", 0)
    if chain and confidence >= 0.4:
        skill = chain[0] if isinstance(chain, list) else str(chain)
        # Handle error responses (dict or string repr)
        is_error = (isinstance(skill, dict) and "error" in skill) or (
            isinstance(skill, str) and "error" in skill.lower() and skill.startswith("{")
        )
        if is_error:
            # Try next skill in chain
            if len(chain) > 1:
                skill = chain[1]
            else:
                skill = None
        if skill and isinstance(skill, str) and not skill.startswith("{"):
            return skill.lstrip("/")

    # Supplementary BM25 context: skills list from skill_registry
    skills = route.get("skills", [])
    if skills:
        name = skills[0].get("name", "")
        if name:
            return str(name).lstrip("/")

    # Legacy format: suggested_chain from BM25 compositions
    suggested = route.get("suggested_chain")
    if suggested and suggested.get("chain"):
        return str(suggested["chain"][0]).lstrip("/")

    return None


async def _datalake_stats() -> Optional[dict]:
    """Fetch datalake stats (uses shared httpx client)."""
    try:
        resp = await _http_datalake.get("/api/datalake/stats")
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


async def _datalake_convergence(limit: int = 50) -> Optional[dict]:
    """Fetch convergence data (uses shared httpx client)."""
    try:
        resp = await _http_datalake.get(f"/api/datalake/convergence?limit={limit}")
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


async def _datalake_verdicts() -> Optional[dict]:
    """Fetch verdicts data (uses shared httpx client)."""
    try:
        resp = await _http_datalake.get("/api/datalake/verdicts")
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


def _describe_data_shape(data: Any) -> dict:
    """Describe the shape of gathered data for the viz-type-selector."""
    if isinstance(data, list):
        row_count = len(data)
        if row_count > 0 and isinstance(data[0], dict):
            cols = list(data[0].keys())
            col_count = len(cols)
            max_label_len = max(
                (len(str(data[0].get(cols[0], ""))) for _ in [1]) if cols else [0],
                default=0,
            )
            # Check for time-like columns
            has_time = any(c in ("date", "time", "timestamp", "x", "step", "epoch") for c in cols)
            # Compute null percentage
            total_cells = row_count * col_count
            null_cells = sum(1 for row in data for v in row.values() if v is None or v == "")
            null_pct = (null_cells / total_cells * 100) if total_cells > 0 else 0
        else:
            col_count = 1
            max_label_len = max((len(str(x)) for x in data), default=0)
            has_time = False
            null_pct = 0
        return {
            "row_count": row_count,
            "col_count": col_count,
            "max_label_len": max_label_len,
            "has_time_axis": has_time,
            "null_pct": null_pct,
        }
    elif isinstance(data, dict):
        keys = list(data.keys())
        row_count = len(keys)
        max_label_len = max((len(str(k)) for k in keys), default=0)
        # Check if values are dicts (nested → heatmap/radar candidate)
        nested = any(isinstance(v, dict) for v in data.values())
        return {
            "row_count": row_count,
            "col_count": max(len(v) for v in data.values()) if nested else 1,
            "max_label_len": max_label_len,
            "has_time_axis": False,
            "null_pct": 0,
            "nested": nested,
        }
    return {"row_count": 0, "col_count": 0, "max_label_len": 0, "has_time_axis": False, "null_pct": 0}


# --- /create-figure chart type → subcommand mapping ---
# Auto-populated from d3_catalog when available, with manual overrides.

_CHART_TO_FIGURE_CMD: dict[str, tuple[str, str]] = {}
if D3_CATALOG_AVAILABLE:
    for name, viz in D3_VIZ_CATALOG.items():
        if viz.create_figure_cmd:
            parts = viz.create_figure_cmd.split(" --type ")
            cmd = parts[0]
            fig_type = parts[1] if len(parts) > 1 else ""
            _CHART_TO_FIGURE_CMD[name] = (cmd, fig_type)
        elif name in ("table", "text", "gauge"):
            _CHART_TO_FIGURE_CMD[name] = ("", "")  # handled inline
else:
    _CHART_TO_FIGURE_CMD = {
        "bar": ("metrics", "bar"),
        "hbar": ("metrics", "hbar"),
        "pie": ("metrics", "pie"),
        "line": ("training-curves", ""),
        "radar": ("radar", ""),
        "heatmap": ("heatmap", ""),
        "sankey": ("sankey", ""),
        "table": ("", ""),
        "text": ("", ""),
    }


# --- Intent classification ---


MANIPULATE_PATTERNS = [
    r"\b(zoom\s*(in|out|to|into)?|pan\s*(left|right|up|down|to)?)\b",
    r"\b(highlight|dim|focus\s*on|unfocus)\b",
    r"\b(expand|collapse|drill\s*(down|up|into)?)\b",
    r"\b(filter|hide|show\s+only|remove)\b.{0,40}\b(nodes?|edges?|links?|bars?|slices?|points?|series|connections?|items?|rows?|docs?|documents?|specs?)\b",
    r"\b(filter\s+(to|by|for)|show\s+only|hide\s+(all|the))\b",
    r"\b(reset|clear|undo|restore)\b.*\b(view|zoom|filter|highlight|graph|chart)\b",
    r"\b(select|click\s*on|tap)\b.*\b(nodes?|bars?|slices?|points?|areas?)\b",
    r"\b(show\s+(all\s+)?related|related\s+nodes?)\b",
]


# --- D3 Manipulation command parsing ---
# Maps natural language manipulation commands to structured D3 operations.

# Action keyword → ManipulationAction mapping
_MANIP_ACTION_MAP = [
    (r"\bzoom\s*in\b", "zoom_in"),
    (r"\bzoom\s*out\b", "zoom_out"),
    (r"\bzoom\s*(to|into|on)\b", "zoom_to"),
    (r"\bpan\b", "pan"),
    (r"\b(show\s+(all\s+)?related|related\s+nodes?)\b", "highlight_related"),
    (r"\bhighlight\s*(the\s+)?related\b", "highlight_related"),
    (r"\bhighlight\s*(the\s+)?path\b", "highlight_path"),
    (r"\bhighlight\b", "highlight"),
    (r"\bfocus\s*(on)?\b", "focus"),
    (r"\bexpand\b", "expand"),
    (r"\bcollapse\b", "collapse"),
    (r"\bdrill\s*down\b", "drill_down"),
    (r"\bdrill\s*(up|back|out)\b", "drill_up"),
    (r"\b(filter|show\s+only|hide)\b", "filter"),
    (r"\bexplode\b", "explode"),
    (r"\b(reset|clear|undo|restore)\b", "reset"),
    (r"\bselect\b", "highlight"),
]

# Direction keywords for pan
_PAN_DIRECTIONS = {
    "left": {"dx": -100, "dy": 0},
    "right": {"dx": 100, "dy": 0},
    "up": {"dx": 0, "dy": -100},
    "down": {"dx": 0, "dy": 100},
}


def _is_manipulation_command(query: str) -> bool:
    """Detect if query is a manipulation command for the active D3 visualization.

    Manipulation commands reference the existing viz (zoom, highlight, filter, etc.)
    rather than requesting new data or a new visualization.
    """
    q = query.lower().strip()
    for pattern in MANIPULATE_PATTERNS:
        if re.search(pattern, q):
            return True
    return False


def _parse_manipulation_commands(query: str) -> list[dict]:
    """Parse natural language into structured ManipulationCommand dicts.

    Handles compound commands: "Zoom in on Node X and highlight the related nodes"
    → [{action: "zoom_to", target: "Node X"}, {action: "highlight_related", target: "Node X"}]
    """
    q = query.strip()
    commands: list[dict] = []

    # Split on "and", "then", ",", ";" for compound commands
    parts = re.split(r"\s+(?:and|then|,|;)\s+", q, flags=re.IGNORECASE)
    if not parts:
        parts = [q]

    for part in parts:
        part_lower = part.lower().strip()
        if not part_lower:
            continue

        action = None
        for pattern, act in _MANIP_ACTION_MAP:
            if re.search(pattern, part_lower):
                action = act
                break

        if not action:
            continue

        # Extract target — everything after the action keyword and prepositions
        target = _extract_manipulation_target(part, action)

        cmd: dict = {"action": action}
        if target:
            cmd["target"] = target

        # Add direction params for pan
        if action == "pan":
            for direction, offsets in _PAN_DIRECTIONS.items():
                if direction in part_lower:
                    cmd["params"] = offsets
                    break

        # Add scale params for zoom
        if action in ("zoom_in", "zoom_out"):
            # Look for numeric scale: "zoom in 2x", "zoom in by 3"
            scale_match = re.search(r"(\d+(?:\.\d+)?)\s*x?\b", part_lower)
            if scale_match:
                scale = float(scale_match.group(1))
                if action == "zoom_out":
                    scale = 1.0 / scale
                cmd["params"] = {"scale": scale}

        commands.append(cmd)

    # If no commands parsed, try treating the whole query as a single command
    if not commands:
        for pattern, act in _MANIP_ACTION_MAP:
            if re.search(pattern, q.lower()):
                target = _extract_manipulation_target(q, act)
                cmd = {"action": act}
                if target:
                    cmd["target"] = target
                commands.append(cmd)
                break

    return commands


def _extract_manipulation_target(text: str, action: str) -> Optional[str]:
    """Extract the target entity from a manipulation phrase.

    "zoom in on Node X" → "Node X"
    "highlight Component Assembly" → "Component Assembly"
    "focus on the supply chain node" → "supply chain"
    """
    # Remove the action verb and prepositions
    cleaned = text.strip()
    # Remove common prefixes
    cleaned = re.sub(
        r"^(?:please\s+|can\s+you\s+|could\s+you\s+)",
        "", cleaned, flags=re.IGNORECASE
    )
    # Remove the action keyword
    for pattern, act in _MANIP_ACTION_MAP:
        if act == action:
            cleaned = re.sub(pattern, "", cleaned, count=1, flags=re.IGNORECASE)
            break
    # Remove prepositions
    cleaned = re.sub(
        r"^\s*(?:on|to|at|in|into|the|for|of|a|an)\s+",
        "", cleaned, flags=re.IGNORECASE
    )
    # Remove trailing noise
    cleaned = re.sub(
        r"\s*(?:node|nodes|edge|edges|bar|bars|slice|slices|point|points|series|link|links)?\s*$",
        "", cleaned, flags=re.IGNORECASE
    )
    cleaned = cleaned.strip().strip('"\'')

    return cleaned if cleaned and len(cleaned) > 0 else None


_SETFIT_MODEL = None  # cached SetFit model singleton
_VIZ_TYPE_MODEL = None  # cached SetFit model for viz-type-selector


def _classify_viz_type_classifier(query: str) -> tuple[str | None, float]:
    """Try Tier 0.5 classifier for viz-type-selector.

    Tries SetFit first, falls back to sklearn joblib model.
    Returns (viz_type, confidence) or (None, 0.0) on failure.
    """
    global _VIZ_TYPE_MODEL
    try:
        # Try SetFit model first (preferred)
        for setfit_name in ("viz_type_selector_setfit", "viz_type_setfit"):
            model_dir = Path.home() / ".pi" / "models" / "classifiers" / setfit_name
            if model_dir.exists():
                if _VIZ_TYPE_MODEL is None:
                    from setfit import SetFitModel
                    _VIZ_TYPE_MODEL = SetFitModel.from_pretrained(str(model_dir))

                proba = _VIZ_TYPE_MODEL.predict_proba([query])[0]
                best_idx = int(proba.argmax())
                confidence = float(proba[best_idx])
                if confidence < 0.6:
                    return None, confidence

                config_path = model_dir / "training_config.json"
                config = json.loads(config_path.read_text())
                label = config["id2label"][str(best_idx)]
                return label, confidence

        # Fallback: sklearn joblib model
        joblib_path = Path.home() / ".pi" / "models" / "classifiers" / "viz_type_selector_classifier.joblib"
        if joblib_path.exists():
            if _VIZ_TYPE_MODEL is None:
                import joblib
                _VIZ_TYPE_MODEL = joblib.load(str(joblib_path))

            model = _VIZ_TYPE_MODEL
            if hasattr(model, "predict_proba"):
                proba = model.predict_proba([query])[0]
                best_idx = int(proba.argmax())
                confidence = float(proba[best_idx])
                label = model.classes_[best_idx]
                if confidence < 0.6:
                    return None, confidence
                return str(label), confidence
            else:
                pred = model.predict([query])[0]
                return str(pred), 0.7

        return None, 0.0
    except Exception as exc:
        log.warning("viz-type-selector classifier load failed: %s", exc)
        return None, 0.0


def _classify_intent_classifier(query: str) -> tuple[str | None, float]:
    """Try Tier 0.5 SetFit classifier for canvas-intent.

    Returns (label, confidence) or (None, 0.0) on failure.
    """
    global _SETFIT_MODEL
    try:
        from pathlib import Path

        model_dir = Path.home() / ".pi" / "models" / "classifiers" / "canvas_intent_setfit"
        if not model_dir.exists():
            return None, 0.0

        if _SETFIT_MODEL is None:
            from setfit import SetFitModel

            _SETFIT_MODEL = SetFitModel.from_pretrained(str(model_dir))

        proba = _SETFIT_MODEL.predict_proba([query])[0]
        best_idx = int(proba.argmax())
        confidence = float(proba[best_idx])
        if confidence < 0.6:
            return None, confidence

        import json

        config_path = model_dir / "training_config.json"
        config = json.loads(config_path.read_text())
        label = config["id2label"][str(best_idx)]
        return label, confidence
    except Exception as exc:
        log.warning("SetFit canvas-intent load failed: %s", exc)
        return None, 0.0


_ASSISTANT_RUN_SH = SKILLS_DIR / "assistant" / "run.sh"


async def _classify_intent_assistant(query: str) -> tuple[str | None, float]:
    """Call /assistant classify --task canvas-intent for intent classification.

    Uses run.sh (which activates the assistant's own venv with setfit installed)
    and the Shadow-LEGO cascade (SetFit Tier 0.5 → scillm Tier 2).
    Returns (label, confidence) or (None, 0.0) on failure.
    """
    if not _ASSISTANT_RUN_SH.exists():
        log.warning("assistant run.sh not found at %s", _ASSISTANT_RUN_SH)
        return None, 0.0

    cmd = [
        "bash", str(_ASSISTANT_RUN_SH),
        "classify",
        "--task", "canvas-intent",
        "--text", query,
    ]

    rc, stdout, stderr = await _run_skill(cmd, timeout=30.0)
    if rc != 0:
        log.warning("assistant classify canvas-intent failed (rc=%d): %s", rc, stderr[:300])
        return None, 0.0

    try:
        result = json.loads(stdout)
        prediction = result.get("prediction") or result.get("result", {}).get("prediction")
        confidence = float(result.get("confidence", 0.0))
        if prediction and confidence >= 0.4:
            return prediction.upper(), confidence
        return None, confidence
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        log.warning("assistant classify returned unparseable output: %s (%s)", stdout[:200], exc)
        return None, 0.0


async def classify_intent(query: str) -> dict:
    """Cascade intent classification — no bespoke regex.

    Tier 0: Slash-command prefix (syntactic)
    Tier 0.5+: /assistant classify --task canvas-intent (SetFit → scillm)
    Skill override: /memory recall skill_route (full /recommend-skill-chain cascade)

    Returns dict with intent, confidence, source.
    """
    # Tier 0: Slash-command prefix is syntactically unambiguous
    if re.match(r"^/[\w-]+", query.strip()):
        return {"intent": "SKILL", "confidence": 1.0, "source": "prefix"}

    # Tier 0: Pipeline stage references → CODE intent (when not explicitly visual)
    # Questions about S00-S14 stages, pipeline internals, extractors, etc.
    q_lower = query.lower()
    _PIPELINE_STAGE_RE = re.compile(r'\bs\d{2}\b', re.IGNORECASE)
    _PIPELINE_TERMS = {"pipeline step", "extractor handle", "extraction stage", "merge classifier",
                       "re-extract", "preflight", "table count estimate", "equation detection",
                       "how does the", "how reliable"}
    _VISUAL_CUES = {"show me", "chart", "plot", "histogram", "timeline", "heatmap", "bar chart",
                    "radar", "visualiz"}
    has_pipeline_ref = _PIPELINE_STAGE_RE.search(query) or any(t in q_lower for t in _PIPELINE_TERMS)
    has_visual_cue = any(v in q_lower for v in _VISUAL_CUES)
    if has_pipeline_ref and not has_visual_cue:
        return {"intent": "CODE", "confidence": 0.85, "source": "pipeline-heuristic"}

    # Tier 0: Datalake aggregate/count queries → QUERY intent
    # BUT if "compare" is in query, let it go to COMPARE handler
    _QUERY_TERMS = {"pass rate", "on track", "how far", "how many document", "what percentage",
                    "quarantine", "not_available", "human feedback", "re-extract",
                    "worst-scoring", "lowest-scoring", "top 5", "top 10",
                    "margaret passed", "jennifer passed", "margaret failed", "jennifer failed"}
    has_compare = "compare" in q_lower or "comparison" in q_lower
    if any(t in q_lower for t in _QUERY_TERMS) and not has_compare:
        return {"intent": "QUERY", "confidence": 0.80, "source": "query-heuristic"}

    # Tier 0.5 → 2: /assistant classify (SetFit → scillm cascade)
    assistant_result, assistant_confidence = await _classify_intent_assistant(query)

    if assistant_result is not None:
        # If classifier confidence is modest, check if /memory skill_route
        # suggests this is actually an operational command
        if assistant_confidence < 0.85:
            skill = await _get_skill_route(query)
            if skill and skill in _SKILL_REGISTRY:
                return {"intent": "SKILL", "confidence": 0.75, "source": "memory-skill-route"}

        return {
            "intent": assistant_result,
            "confidence": assistant_confidence,
            "source": "assistant",
        }

    # Classifier failed — check /memory skill_route for skill invocation
    skill = await _get_skill_route(query)
    if skill and skill in _SKILL_REGISTRY:
        return {"intent": "SKILL", "confidence": 0.6, "source": "memory-skill-route"}

    # Try local SetFit directly (subprocess failed but model may be loadable)
    clf_result, clf_confidence = _classify_intent_classifier(query)
    if clf_result is not None:
        return {
            "intent": clf_result,
            "confidence": clf_confidence,
            "source": "classifier_local",
        }

    # Everything failed — default to EXPLAIN with low confidence
    return {
        "intent": "EXPLAIN",
        "confidence": 0.3,
        "source": "default",
    }



# --- Intent handlers ---
# Each handler follows the full Shadow-LEGO pipeline:
#   1. /memory + datalake → gather raw data
#   2. /assistant data-sufficiency-gate → is there enough data?
#   3. /assistant viz-type-selector → what chart type? (for VISUALIZE/COMPARE)
#   4. /create-figure → render with selected chart type
# Falls back to inline D3 data when skills unavailable.


async def _handle_visualize(query: str, persona: str) -> AnswerPayload:
    """Handle VISUALIZE intent — full Shadow-LEGO pipeline.

    Flow:
      /memory context → datalake data → data-sufficiency-gate →
      viz-type-selector → /create-figure render → AnswerPayload
    """
    q = query.lower()

    # --- Step 1: Gather data from /memory + datalake (parallel) ---
    recall_task = _recall_and_rank(query, k=10, scope="extractor")
    stats_task = _datalake_stats()
    convergence_task = _datalake_convergence(limit=50)
    verdicts_task = _datalake_verdicts()

    (ranked_items, text_cites, html_cites), stats, convergence, verdicts = await asyncio.gather(
        recall_task, stats_task, convergence_task, verdicts_task
    )

    # --- Step 2: Determine what data we actually have ---
    sources_available = []
    gathered_data: dict[str, Any] = {}

    if ranked_items:
        sources_available.append("memory")
    if stats:
        sources_available.append("datalake_stats")
        gathered_data["stats"] = stats
    if convergence and convergence.get("entries"):
        sources_available.append("datalake_convergence")
        gathered_data["convergence"] = convergence
    if verdicts:
        sources_available.append("datalake_verdicts")
        gathered_data["verdicts"] = verdicts

    # --- Step 3: /assistant data-sufficiency-gate ---
    # Determine the most relevant data for this query
    primary_data, primary_shape = _select_primary_data(q, gathered_data)

    data_summary = {
        "sources_available": sources_available,
        "row_count": primary_shape.get("row_count", 0),
        "null_pct": primary_shape.get("null_pct", 0),
        "column_types": list(primary_data[0].keys()) if isinstance(primary_data, list) and primary_data else [],
    }

    sufficiency = await _check_data_sufficiency(query, data_summary)
    verdict = sufficiency.get("verdict", "SUFFICIENT")

    if verdict == "INSUFFICIENT":
        # Before giving up, check if /memory skill_route can find an orchestration
        # that gathers the data we need (e.g. code analysis → /analytics → /create-figure).
        chain_skill = await _get_skill_route(query)
        if chain_skill and chain_skill in _SKILL_REGISTRY:
            return await _handle_skill(query, persona)

        # Try code-scoped /memory recall as fallback for code+viz queries
        code_items, _, _ = await _recall_and_rank(query, k=10, scope="extractor")
        if code_items:
            # Extract any numeric/structured data from code knowledge items
            code_data = _extract_chartable_data(code_items, query)
            if code_data:
                primary_data = code_data
                primary_shape = _describe_data_shape(code_data)
                # Re-check sufficiency with the code data
                data_summary["sources_available"].append("code_knowledge")
                data_summary["row_count"] = primary_shape.get("row_count", 0)
                verdict = "SUFFICIENT"  # override — we found data via code recall

        if verdict == "INSUFFICIENT":
            reason = sufficiency.get("reason", "Not enough data")
            missing = sufficiency.get("missing", [])
            return AnswerPayload(
                type="text",
                title="Insufficient Data",
                content=f"I don't have enough data to visualize that.\n\n"
                        f"Reason: {reason}\n"
                        f"Missing: {', '.join(missing) if missing else 'unknown'}",
                summary=reason,
                source="data-sufficiency-gate",
            )

    # --- Step 3.5: /analytics describe — data profiling for format decision ---
    # /analytics examines the actual data and recommends whether to chart, table, or text
    if isinstance(primary_data, list) and primary_data and isinstance(primary_data[0], dict):
        analytics_profile = await _analytics_profile(primary_data)
        if analytics_profile:
            # Enrich shape with analytics column types (key is "columns" per analytics output)
            col_types = analytics_profile.get("columns", analytics_profile.get("col_types", {}))
            if col_types:
                primary_shape["col_types"] = col_types
            # /analytics returns recommendations: [{name, chart_type, encoding, ...}]
            recs = analytics_profile.get("recommendations", [])
            if recs and isinstance(recs, list) and len(recs) > 0:
                # Use first recommendation's chart_type as the analytics suggestion
                first_rec = recs[0]
                analytics_rec = first_rec.get("chart_type") if isinstance(first_rec, dict) else None
                if analytics_rec:
                    primary_shape["analytics_recommendation"] = analytics_rec
                    primary_shape["analytics_encoding"] = first_rec.get("encoding", {})
                # Store all recommendations for fallback
                primary_shape["analytics_all_recommendations"] = [
                    {"name": r.get("name"), "chart_type": r.get("chart_type")}
                    for r in recs if isinstance(r, dict)
                ]

    # --- Step 4: viz-type-selector (classifier → heuristic → /assistant) ---
    chart_type = await _select_viz_type(query, primary_shape)

    # --- Step 5: Render with selected chart type ---
    payload = await _render_with_type(
        query, chart_type, primary_data, primary_shape, gathered_data,
        sufficiency_verdict=verdict,
    )
    # Append citations — HTML for viz, text for text/table
    if payload.type == "html" and html_cites:
        payload.content = payload.content + html_cites
    elif text_cites:
        payload.content = (payload.content or "") + text_cites
    if text_cites and payload.summary:
        payload.summary = payload.summary.rstrip(".") + ". Sources cited."
    return payload


def _extract_chartable_data(items: list[dict], query: str) -> list[dict] | None:
    """Extract numeric/categorical data from code knowledge items for charting.

    Looks for items with structured data (dicts with numeric values),
    or synthesizes label→count data from tags/categories.
    """
    # Strategy 1: items with embedded data dicts (e.g. metrics, scores)
    for item in items:
        data = item.get("data") or item.get("metrics") or item.get("stats")
        if isinstance(data, dict) and len(data) >= 2:
            # Check if values are numeric
            numeric = {k: v for k, v in data.items() if isinstance(v, (int, float))}
            if len(numeric) >= 2:
                return [{"label": k, "value": v} for k, v in numeric.items()]

    # Strategy 2: synthesize from tags/categories across items
    tag_counts: dict[str, int] = {}
    for item in items:
        for tag in item.get("tags", []):
            if isinstance(tag, str) and tag not in ("code_symbol", "extracted_content"):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
    if len(tag_counts) >= 3:
        top = sorted(tag_counts.items(), key=lambda x: -x[1])[:15]
        return [{"label": k, "value": v} for k, v in top]

    # Strategy 3: item titles as categories with relevance scores
    if len(items) >= 3:
        return [
            {"label": (item.get("title") or "item")[:40], "value": round(item.get("score", 0.5), 3)}
            for item in items[:10]
            if item.get("title")
        ]

    return None


def _select_primary_data(query: str, gathered_data: dict) -> tuple[Any, dict]:
    """Pick the most relevant dataset for this query and describe its shape."""
    q = query.lower()

    # Convergence trend
    if any(w in q for w in ("convergence", "trend", "progress", "trajectory")):
        conv = gathered_data.get("convergence", {})
        entries = conv.get("entries", [])
        if entries:
            points = [
                {"x": i + 1, "y": e.get("score", e.get("overall_score", 0))}
                for i, e in enumerate(entries)
                if e.get("score", e.get("overall_score")) is not None
            ]
            return points, _describe_data_shape(points)

    # Grade/verdict distribution
    if any(w in q for w in ("grade", "verdict", "pass", "fail")):
        stats = gathered_data.get("stats", {})
        grades = stats.get("grades", {})
        if grades:
            return grades, _describe_data_shape(grades)
        verdicts_data = stats.get("verdicts", {})
        if verdicts_data:
            return verdicts_data, _describe_data_shape(verdicts_data)

    # Domain breakdown
    if any(w in q for w in ("domain", "category", "type", "breakdown")):
        stats = gathered_data.get("stats", {})
        domains = stats.get("domains", {})
        if domains:
            top = dict(sorted(domains.items(), key=lambda x: -x[1])[:10])
            return top, _describe_data_shape(top)

    # Persona dimensions
    if any(w in q for w in ("persona", "dimension", "radar", "spider", "quality")):
        verdicts = gathered_data.get("verdicts", {})
        if verdicts:
            radar_data = {}
            for vk, vd in verdicts.items():
                if isinstance(vd, dict) and vd.get("dimension_averages"):
                    radar_data[vk] = {
                        d.replace("_", " "): round(v, 3)
                        for d, v in vd["dimension_averages"].items()
                    }
            if radar_data:
                return radar_data, _describe_data_shape(radar_data)

    # Generic fallback — use stats verdicts
    stats = gathered_data.get("stats", {})
    verdicts_data = stats.get("verdicts", {})
    if verdicts_data:
        return verdicts_data, _describe_data_shape(verdicts_data)

    return {}, _describe_data_shape({})


async def _render_with_type(
    query: str,
    chart_type: str,
    primary_data: Any,
    primary_shape: dict,
    gathered_data: dict,
    sufficiency_verdict: str = "SUFFICIENT",
) -> AnswerPayload:
    """Render data using the /assistant-selected chart type via /create-figure."""
    q = query.lower()
    stats = gathered_data.get("stats", {})
    partial_note = " (partial data)" if sufficiency_verdict == "PARTIAL" else ""

    # Text/table bypass — no /create-figure needed
    if chart_type == "text":
        return await _handle_query(query, "embry")
    if chart_type == "table":
        if isinstance(primary_data, dict):
            table_rows = [{"key": k, "value": v} for k, v in primary_data.items()]
        elif isinstance(primary_data, list):
            table_rows = primary_data
        else:
            table_rows = [{"value": str(primary_data)}]
        # Format as readable text (Markdown table) to avoid raw JSON
        lines = []
        if table_rows:
            headers = list(table_rows[0].keys()) if isinstance(table_rows[0], dict) else ["value"]
            lines.append("| " + " | ".join(str(h) for h in headers) + " |")
            lines.append("| " + " | ".join("---" for _ in headers) + " |")
            for row in table_rows[:50]:
                if isinstance(row, dict):
                    lines.append("| " + " | ".join(str(row.get(h, "")) for h in headers) + " |")
                else:
                    lines.append(f"| {row} |")
        return AnswerPayload(
            type="table",
            title=f"Data{partial_note}",
            content="\n".join(lines) if lines else "No data available.",
            summary=f"{len(table_rows)} rows of data.",
            source="datalake + viz-type-selector",
        )

    # /figure-lab is the primary rendering path — it composes persona-aware D3
    # visualizations using /create-figure as its backend. The endpoint always
    # goes through /figure-lab, never calls /create-figure directly.
    figlab_data = primary_data if isinstance(primary_data, list) else (
        [{"label": k, "value": v} for k, v in primary_data.items()]
        if isinstance(primary_data, dict) else [{"value": primary_data}]
    )
    figlab_html = await _figure_lab_compose(
        figlab_data, chart_type,
        title=_infer_title(q, chart_type),
        persona="embry",
        canvas=True,
    )
    if figlab_html:
        viz_family = _get_viz_family(chart_type)
        title = _infer_title(q, chart_type) + partial_note
        final_html = _inject_manipulation_runtime(figlab_html, viz_family)
        # Store working D3 in /memory for future recall (non-blocking)
        asyncio.create_task(_learn_d3_to_memory(
            figlab_html, chart_type, viz_family, query, title,
            primary_shape, source=f"figure-lab",
        ))
        return AnswerPayload(
            type="html",
            title=title,
            content=final_html,
            summary=_build_summary(q, primary_data, stats),
            source=f"viz-type-selector({chart_type}) + /figure-lab",
            vizFamily=viz_family,
        )

    # Legacy /create-figure path — only for cases where /figure-lab compose
    # returns None (e.g., compose iteration fails to meet quality threshold).
    # This path will be removed once /figure-lab gallery covers all 60 types.
    fig_cmd, fig_type = _CHART_TO_FIGURE_CMD.get(chart_type, ("metrics", "bar"))

    # Prepare data in the format /create-figure expects
    if fig_cmd == "metrics":
        if isinstance(primary_data, dict):
            figure_data = {"metrics": primary_data}
        elif isinstance(primary_data, list) and primary_data and isinstance(primary_data[0], dict):
            # Convert list of {label, value} to metrics dict
            figure_data = {"metrics": {
                str(row.get("label", row.get("key", f"item_{i}"))): row.get("value", row.get("y", 0))
                for i, row in enumerate(primary_data)
            }}
        else:
            figure_data = {"metrics": {"value": primary_data}}
        title = _infer_title(q, chart_type)
        html = await _render_figure(figure_data, "metrics", fig_type, title)

    elif fig_cmd == "training-curves":
        # Shape as {series_name: {x: [...], y: [...]}}
        if isinstance(primary_data, list) and primary_data and isinstance(primary_data[0], dict):
            xs = [p.get("x", i) for i, p in enumerate(primary_data)]
            ys = [p.get("y", p.get("value", 0)) for p in primary_data]
        elif isinstance(primary_data, dict):
            xs = list(range(len(primary_data)))
            ys = list(primary_data.values())
        else:
            xs, ys = [], []
        figure_data = {"Trend": {"x": xs, "y": ys}}
        title = _infer_title(q, "line")
        html = await _render_figure(figure_data, "training-curves", "", title)

    elif fig_cmd == "radar":
        figure_data = primary_data if isinstance(primary_data, dict) else {"data": primary_data}
        title = _infer_title(q, "radar")
        html = await _render_figure(figure_data, "radar", "", title)

    elif fig_cmd == "heatmap":
        figure_data = primary_data if isinstance(primary_data, dict) else {}
        title = _infer_title(q, "heatmap")
        html = await _render_figure(figure_data, "heatmap", "", title)

    elif fig_cmd == "sankey":
        figure_data = primary_data if isinstance(primary_data, list) else []
        title = _infer_title(q, "sankey")
        html = await _render_figure(figure_data, "sankey", "", title)

    else:
        html = None

    if html:
        summary = _build_summary(q, primary_data, stats)
        viz_family = _get_viz_family(chart_type)
        title = _infer_title(q, chart_type) + partial_note
        final_html = _inject_manipulation_runtime(html, viz_family)
        # Store working D3 in /memory (non-blocking)
        asyncio.create_task(_learn_d3_to_memory(
            html, chart_type, viz_family, query, title,
            primary_shape, source="create-figure",
        ))
        return AnswerPayload(
            type="html",
            title=title,
            content=final_html,
            summary=summary,
            source=f"viz-type-selector({chart_type}) + /create-figure",
            vizFamily=viz_family,
        )

    # Fallback: generate inline D3 HTML so manipulation runtime still works
    if isinstance(primary_data, dict):
        chart_data = [{"label": k, "value": v} for k, v in primary_data.items()]
    elif isinstance(primary_data, list):
        chart_data = [
            {"label": str(p.get("x", p.get("label", i))), "value": p.get("y", p.get("value", 0))}
            for i, p in enumerate(primary_data)
        ] if primary_data and isinstance(primary_data[0], dict) else []
    else:
        chart_data = []

    # Wrap data as inline D3 HTML (instead of raw JSON) so iframe manipulation works
    viz_family = _get_viz_family(chart_type)
    inline_html = _data_to_inline_d3_html(chart_data, chart_type, _infer_title(q, chart_type))
    if inline_html:
        return AnswerPayload(
            type="html",
            title=_infer_title(q, chart_type) + partial_note,
            content=_inject_manipulation_runtime(inline_html, viz_family),
            summary=_build_summary(q, primary_data, stats),
            source="viz-type-selector + inline D3",
            vizFamily=viz_family,
        )

    # Ultimate fallback: raw data (no manipulation support)
    return AnswerPayload(
        type="data",
        title=_infer_title(q, chart_type) + partial_note,
        content=json.dumps(chart_data),
        summary=_build_summary(q, primary_data, stats),
        source="viz-type-selector + D3 fallback",
    )


def _infer_title(query: str, chart_type: str) -> str:
    """Generate a concise title from the query."""
    q = query.lower()
    if "convergence" in q or "trend" in q:
        return "Convergence Trend"
    if "grade" in q:
        return "Grade Distribution"
    if "verdict" in q or "pass" in q or "fail" in q:
        return "Verdict Distribution"
    if "domain" in q or "category" in q:
        return "Top Domains"
    if "dimension" in q or "persona" in q or "radar" in q:
        return "Quality Dimensions"
    if "score" in q or "quality" in q:
        return "Quality Scores"
    return f"Analysis ({chart_type})"


def _build_summary(query: str, data: Any, stats: dict) -> str:
    """Build a TTS-friendly summary of the data."""
    total = stats.get("total_docs", 0)
    avg_score = stats.get("avg_score", 0)

    if isinstance(data, list):
        n = len(data)
        if n > 0 and isinstance(data[0], dict) and "y" in data[0]:
            latest = data[-1]["y"]
            return f"{n} data points. Latest value: {latest:.1%}."
        return f"Showing {n} items."
    elif isinstance(data, dict):
        n = len(data)
        if n <= 5:
            items = ", ".join(f"{k}: {v}" for k, v in data.items())
            return items
        return f"{n} categories shown."

    if total:
        return f"{total:,} documents, {avg_score:.0%} average score."
    return "Data displayed."


def _data_to_inline_d3_html(data: list[dict], chart_type: str, title: str) -> Optional[str]:
    """Generate inline D3 HTML from data so fallback renders still get manipulation support.

    Instead of returning raw JSON (type="data"), we wrap the data in a standalone
    HTML page with inline D3 that renders the chart. This way it loads in an iframe
    and the manipulation runtime can control it.
    """
    if not data:
        return None

    data_json = json.dumps(data)
    # Determine chart variant
    ct = chart_type.lower()
    if ct in ("bar", "hbar", "grouped_bar", "stacked_bar", "diverging_bar", "waterfall"):
        chart_js = _INLINE_BAR_CHART
    elif ct in ("line", "area", "sparkline", "step"):
        chart_js = _INLINE_LINE_CHART
    elif ct in ("pie", "donut", "sunburst"):
        chart_js = _INLINE_PIE_CHART
    elif ct in ("scatter", "bubble"):
        chart_js = _INLINE_SCATTER_CHART
    else:
        chart_js = _INLINE_BAR_CHART  # default fallback

    safe_title = html_mod.escape(title)
    # Escape </script> in JSON data to prevent script tag breakout
    safe_data = data_json.replace("</", "<\\/")
    return f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<script src="https://d3js.org/d3.v7.min.js"></script>
<style>
  body {{ margin:0; padding:20px; font-family:system-ui,-apple-system,sans-serif; background:#111; color:#eee; }}
  h2 {{ text-align:center; font-size:36px; font-weight:700; margin-bottom:16px; }}
  #chart {{ width:100%; height:calc(100vh - 100px); }}
  svg {{ display:block; width:100%; height:100%; }}
  .bar {{ transition: opacity 0.3s; cursor: pointer; }}
  .bar:hover {{ opacity: 0.8; }}
  .axis text {{ fill: #b0b0b0; font-size: 24px; }}
  .axis path, .axis line {{ stroke: #555; }}
</style>
</head><body>
<h2>{safe_title}</h2>
<div id="chart"></div>
<script>
var DATA = {safe_data};
{chart_js}
</script>
</body></html>"""


# Inline D3 chart templates — minimal, readable, manipulation-compatible
_INLINE_BAR_CHART = """
(function() {
  var rect = document.getElementById('chart').getBoundingClientRect();
  var fullW = rect.width || 800, fullH = rect.height || 500;
  var margin = {top: 20, right: 30, bottom: 80, left: 100};
  var width = fullW - margin.left - margin.right;
  var height = fullH - margin.top - margin.bottom;
  var svg = d3.select('#chart').append('svg')
    .attr('viewBox', '0 0 ' + fullW + ' ' + fullH)
    .attr('preserveAspectRatio', 'xMidYMid meet')
    .append('g').attr('transform', 'translate(' + margin.left + ',' + margin.top + ')');
  var x = d3.scaleBand().range([0, width]).padding(0.2)
    .domain(DATA.map(function(d) { return d.label; }));
  var y = d3.scaleLinear().range([height, 0])
    .domain([0, d3.max(DATA, function(d) { return +d.value; }) * 1.1]);
  svg.append('g').attr('class', 'axis').attr('transform', 'translate(0,' + height + ')')
    .call(d3.axisBottom(x)).selectAll('text').attr('transform', 'rotate(-35)').style('text-anchor', 'end');
  svg.append('g').attr('class', 'axis').call(d3.axisLeft(y));
  svg.selectAll('.bar').data(DATA).enter().append('rect')
    .attr('class', 'bar').attr('data-label', function(d) { return d.label; })
    .attr('x', function(d) { return x(d.label); }).attr('width', x.bandwidth())
    .attr('y', function(d) { return y(+d.value); }).attr('height', function(d) { return height - y(+d.value); })
    .attr('fill', '#4a9eff');
})();
"""

_INLINE_LINE_CHART = """
(function() {
  var rect = document.getElementById('chart').getBoundingClientRect();
  var fullW = rect.width || 800, fullH = rect.height || 500;
  var margin = {top: 20, right: 30, bottom: 80, left: 100};
  var width = fullW - margin.left - margin.right;
  var height = fullH - margin.top - margin.bottom;
  var svg = d3.select('#chart').append('svg')
    .attr('viewBox', '0 0 ' + fullW + ' ' + fullH)
    .attr('preserveAspectRatio', 'xMidYMid meet')
    .append('g').attr('transform', 'translate(' + margin.left + ',' + margin.top + ')');
  var x = d3.scalePoint().range([0, width]).padding(0.5)
    .domain(DATA.map(function(d) { return d.label; }));
  var y = d3.scaleLinear().range([height, 0])
    .domain([0, d3.max(DATA, function(d) { return +d.value; }) * 1.1]);
  svg.append('g').attr('class', 'axis').attr('transform', 'translate(0,' + height + ')')
    .call(d3.axisBottom(x)).selectAll('text').attr('transform', 'rotate(-35)').style('text-anchor', 'end');
  svg.append('g').attr('class', 'axis').call(d3.axisLeft(y));
  var line = d3.line().x(function(d) { return x(d.label); }).y(function(d) { return y(+d.value); });
  svg.append('path').datum(DATA).attr('fill', 'none').attr('stroke', '#4a9eff').attr('stroke-width', 3).attr('d', line);
  svg.selectAll('.dot').data(DATA).enter().append('circle')
    .attr('class', 'dot').attr('data-label', function(d) { return d.label; })
    .attr('cx', function(d) { return x(d.label); }).attr('cy', function(d) { return y(+d.value); })
    .attr('r', 10).attr('fill', '#4a9eff');
})();
"""

_INLINE_PIE_CHART = """
(function() {
  var rect = document.getElementById('chart').getBoundingClientRect();
  var size = Math.min(rect.width || 500, rect.height || 500);
  var radius = size / 2 - 40;
  var svg = d3.select('#chart').append('svg')
    .attr('viewBox', '0 0 ' + size + ' ' + size)
    .attr('preserveAspectRatio', 'xMidYMid meet')
    .append('g').attr('transform', 'translate(' + size/2 + ',' + size/2 + ')');
  var color = d3.scaleOrdinal(d3.schemeTableau10);
  var pie = d3.pie().value(function(d) { return +d.value; });
  var arc = d3.arc().innerRadius(0).outerRadius(radius);
  var labelArc = d3.arc().innerRadius(radius * 0.65).outerRadius(radius * 0.65);
  svg.selectAll('.slice').data(pie(DATA)).enter().append('path')
    .attr('class', 'slice').attr('data-label', function(d) { return d.data.label; })
    .attr('d', arc).attr('fill', function(d,i) { return color(i); }).attr('stroke', '#111').attr('stroke-width', 2);
  svg.selectAll('.label').data(pie(DATA)).enter().append('text')
    .attr('transform', function(d) { return 'translate(' + labelArc.centroid(d) + ')'; })
    .attr('text-anchor', 'middle').attr('fill', '#eee').attr('font-size', '24px').attr('font-weight', '600')
    .text(function(d) { return d.data.label; });
})();
"""

_INLINE_SCATTER_CHART = """
(function() {
  var rect = document.getElementById('chart').getBoundingClientRect();
  var fullW = rect.width || 800, fullH = rect.height || 500;
  var margin = {top: 20, right: 30, bottom: 80, left: 100};
  var width = fullW - margin.left - margin.right;
  var height = fullH - margin.top - margin.bottom;
  var svg = d3.select('#chart').append('svg')
    .attr('viewBox', '0 0 ' + fullW + ' ' + fullH)
    .attr('preserveAspectRatio', 'xMidYMid meet')
    .append('g').attr('transform', 'translate(' + margin.left + ',' + margin.top + ')');
  var vals = DATA.map(function(d) { return +d.value; });
  var x = d3.scaleLinear().range([0, width]).domain([0, DATA.length]);
  var y = d3.scaleLinear().range([height, 0]).domain([d3.min(vals) * 0.9, d3.max(vals) * 1.1]);
  svg.append('g').attr('class', 'axis').attr('transform', 'translate(0,' + height + ')').call(d3.axisBottom(x));
  svg.append('g').attr('class', 'axis').call(d3.axisLeft(y));
  svg.selectAll('.dot').data(DATA).enter().append('circle')
    .attr('class', 'dot').attr('data-label', function(d) { return d.label; })
    .attr('cx', function(d,i) { return x(i); }).attr('cy', function(d) { return y(+d.value); })
    .attr('r', 12).attr('fill', '#4a9eff').attr('opacity', 0.7);
})();
"""


_learned_d3_types: set[str] = set()  # dedup within session

async def _learn_d3_to_memory(
    html: str, chart_type: str, viz_family: str, query: str,
    title: str, data_shape: dict, source: str,
) -> None:
    """Store working D3 visualization in /memory AND on 12TB drive.

    1. Persists HTML + metadata JSON to /mnt/storage12tb/artifacts/d3_gallery/
    2. Learns summary + tags to /memory for semantic recall
    3. Each stored visualization becomes a reusable skill template
    Deduplicates: only learns each chart_type once per session (still saves artifacts).
    """
    try:
        ts = int(time.time())
        slug = re.sub(r"[^a-z0-9]+", "_", chart_type.lower())

        # --- Step 1: Persist to 12TB drive ---
        html_path = D3_GALLERY_DIR / f"{slug}_{ts}.html"
        html_path.write_text(html)

        metadata = {
            "chart_type": chart_type,
            "viz_family": viz_family,
            "query": query,
            "title": title,
            "data_shape": data_shape,
            "source": source,
            "timestamp": ts,
            "html_path": str(html_path),
            "html_size_bytes": len(html),
        }
        meta_path = D3_METADATA_DIR / f"{slug}_{ts}.json"
        meta_path.write_text(json.dumps(metadata, indent=2))

        log.info("D3 artifact saved: %s (%d bytes)", html_path.name, len(html))

        # Dedup: only learn each chart_type once per session
        if chart_type in _learned_d3_types:
            log.debug("Skipping /memory learn for %s (already learned this session)", chart_type)
            return
        _learned_d3_types.add(chart_type)

        # --- Step 2: Learn to /memory for semantic recall ---
        summary = (
            f"Working {chart_type} ({viz_family}) D3 visualization: {title}. "
            f"Query: '{query}'. Data shape: {data_shape.get('rows', '?')} rows, "
            f"cols: {list(data_shape.get('col_types', {}).keys())[:5]}. "
            f"Source: {source}. Artifact: {html_path}"
        )

        tags = [
            "working_d3", f"viz_type:{chart_type}", f"viz_family:{viz_family}",
            "canvas_visualization", f"source:{source}",
        ]
        for col, ctype in list(data_shape.get("col_types", {}).items())[:5]:
            tags.append(f"col_type:{ctype}")

        memory_skill = SKILLS_DIR / "memory" / "run.sh"
        if not memory_skill.exists():
            return

        cmd = [str(memory_skill), "learn", "--scope", "working_d3"]
        for t in tags:
            cmd.extend(["--tag", t])
        # /memory learn uses --problem / --solution (not --text / --attach)
        # Include domain vocabulary for taxonomy extraction (defense, compliance, etc.)
        problem = (
            f"Defense compliance extraction pipeline needs a {chart_type} ({viz_family}) "
            f"D3 visualization for 5ft data canvas: {query}. "
            f"Document processing quality analysis across aerospace, military, and standards domains."
        )
        solution = (
            f"Working D3 {chart_type} chart: {title}. "
            f"Self-contained HTML with D3 v7, dark theme, 5ft canvas friendly (18px+ fonts). "
            f"Data shape: {data_shape.get('rows', '?')} rows, "
            f"cols: {list(data_shape.get('col_types', {}).keys())[:5]}. "
            f"Supports zoom, pan, highlight, filter manipulation commands. "
            f"Source: {source}. Artifact: {html_path}"
        )
        cmd.extend([
            "--problem", problem,
            "--solution", solution,
        ])

        rc, stdout, stderr = await _run_skill(cmd, timeout=15.0)
        if rc == 0:
            log.info("Learned D3 %s to /memory: %s", chart_type, title)
        else:
            log.debug("D3 /memory learn failed (rc=%d): %s", rc, stderr[:200])
    except Exception as e:
        log.debug("D3 /memory learn error: %s", e)


def _build_inline_table(rows: list[dict]) -> str:
    """Build a simple HTML table from a list of dicts for inline display (dark theme, 5ft)."""
    if not rows:
        return "<p style='color:#e2e8f0;font-size:24px;'>No data</p>"
    cols = list(rows[0].keys())
    header = "".join(
        f"<th style='padding:16px 20px;text-align:left;border-bottom:2px solid #334155;color:#94a3b8;font-size:20px;'>"
        f"{html_mod.escape(str(c))}</th>"
        for c in cols
    )
    body = ""
    for row in rows:
        cells = "".join(
            f"<td style='padding:14px 20px;border-bottom:1px solid #1e293b;color:#e2e8f0;font-size:24px;'>"
            f"{html_mod.escape(str(row.get(c, '')))}</td>"
            for c in cols
        )
        body += f"<tr>{cells}</tr>\n"
    return (
        f"<table style='width:100%;border-collapse:collapse;font-family:system-ui;background:#111;'>"
        f"<thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"
    )


FIGURE_LAB = SKILLS_DIR / "figure-lab" / "run.sh"


async def _analytics_profile(data: list[dict]) -> Optional[dict]:
    """Run /analytics describe on data to get column types and viz recommendations.

    This is the FORMAT DECISION stage: /analytics examines the data and recommends
    whether to produce a chart, table, voice/text response, or specific viz type.

    Returns dict with columns (col types), recommendations (viz list), etc. or None on failure.
    """
    if not ANALYTICS.exists() or not data:
        return None

    input_file = CANVAS_TMP / f"analytics_input_{uuid.uuid4().hex[:12]}.json"
    input_file.write_text(json.dumps(data))

    try:
        cmd = [
            str(ANALYTICS), "describe",
            str(input_file),
            "--json",
        ]
        rc, stdout, stderr = await _run_skill(cmd, timeout=15.0)
        if rc != 0:
            log.warning("analytics describe failed (rc=%d): %s", rc, stderr[:300])
            return None

        return json.loads(stdout)
    except Exception as e:
        log.warning("analytics profile error: %s", e)
        return None
    finally:
        input_file.unlink(missing_ok=True)


async def _figure_lab_compose(
    data: list[dict],
    viz_type: str,
    title: str,
    persona: str = "embry",
    canvas: bool = True,
) -> Optional[str]:
    """Run /figure-lab compose to create a persona-aware D3 visualization.

    This is the VISUALIZATION SELECTION stage: given data + /assistant cascade +
    persona context, figure-lab determines the best specific D3 rendering and
    iterates to quality. It composes from working D3 examples in its gallery.

    Returns rendered HTML or None on failure.
    """
    if not FIGURE_LAB.exists():
        return None

    _fuid = uuid.uuid4().hex[:12]
    input_file = CANVAS_TMP / f"figlab_input_{_fuid}.json"
    output_file = CANVAS_TMP / f"figlab_output_{_fuid}.html"
    input_file.write_text(json.dumps(data))

    try:
        cmd = [
            str(FIGURE_LAB), "compose",
            f"Render a {viz_type} for {persona}: {title}",
            "--type", viz_type,
            "--data", str(input_file),
            "--output", str(output_file),
        ]
        if canvas:
            cmd.append("--canvas")

        rc, stdout, stderr = await _run_skill(cmd, timeout=45.0)
        if rc != 0:
            log.warning("figure-lab compose failed (rc=%d): %s", rc, stderr[:300])
            return None

        if output_file.exists():
            return output_file.read_text()
        return None
    except Exception as e:
        log.warning("figure-lab compose error: %s", e)
        return None
    finally:
        input_file.unlink(missing_ok=True)
        output_file.unlink(missing_ok=True)


# --- Remaining intent handlers ---


async def _handle_query(query: str, persona: str) -> AnswerPayload:
    """Handle QUERY intent — fetch stats + /memory, offer viz for numeric data.

    All responses cite relevant QRAs from /memory, ranked by taxonomy bridge
    intersection with the query. Citations are always included.
    """
    q = query.lower()
    stats_task = _datalake_stats()
    recall_task = _recall_and_rank(query, k=10)
    stats, (ranked_items, text_cites, html_cites) = await asyncio.gather(stats_task, recall_task)

    if not stats:
        return AnswerPayload(
            type="text",
            title="Query Error",
            content="Could not reach the datalake API. Is it running on port 8004?",
            summary="I couldn't reach the datalake API.",
        )

    total = stats.get("total_docs", 0)
    avg_score = stats.get("avg_score", 0)
    verdicts = stats.get("verdicts", {})
    pass_count = verdicts.get("PASS", 0)
    fail_count = verdicts.get("FAIL", 0)
    warn_count = verdicts.get("WARN", 0)

    if any(w in q for w in ("fail", "failure")):
        return AnswerPayload(
            type="text",
            title=f"{fail_count} Failures",
            content=f"There are {fail_count} failed documents out of {total} total.\n\n"
                    f"PASS: {pass_count}  |  WARN: {warn_count}  |  FAIL: {fail_count}\n\n"
                    f"Average score: {avg_score:.1%}{text_cites}",
            summary=f"There are {fail_count} failures out of {total} documents.",
        )

    if any(w in q for w in ("pass", "success")):
        pass_rate = (pass_count / total * 100) if total > 0 else 0
        return AnswerPayload(
            type="text",
            title=f"{pass_rate:.0f}% Pass Rate",
            content=f"{pass_count} of {total} documents pass ({pass_rate:.1f}%).\n\n"
                    f"PASS: {pass_count}  |  WARN: {warn_count}  |  FAIL: {fail_count}{text_cites}",
            summary=f"{pass_rate:.0f}% pass rate, {pass_count} of {total} documents.",
        )

    if any(w in q for w in ("total", "how many", "count", "size", "documents")):
        return AnswerPayload(
            type="text",
            title=f"{total:,} Documents",
            content=f"The datalake contains {total:,} documents.\n\n"
                    f"Average score: {avg_score:.1%}\n"
                    f"PASS: {pass_count}  |  WARN: {warn_count}  |  FAIL: {fail_count}{text_cites}",
            summary=f"The datalake has {total:,} documents with an average score of {avg_score:.0%}.",
        )

    if any(w in q for w in ("score", "average", "quality")):
        return AnswerPayload(
            type="text",
            title=f"{avg_score:.1%} Average Score",
            content=f"Average extraction quality score: {avg_score:.1%}\n\n"
                    f"{total:,} documents total\n"
                    f"PASS: {pass_count}  |  WARN: {warn_count}  |  FAIL: {fail_count}{text_cites}",
            summary=f"The average quality score is {avg_score:.0%}.",
        )

    # Persona-specific queries (Margaret, Jennifer)
    personas = stats.get("personas", {})
    if any(w in q for w in ("margaret", "jennifer", "persona")):
        lines = []
        for pname, pverdicts in personas.items():
            if pverdicts:
                ptotal = sum(pverdicts.values())
                ppass = pverdicts.get("PASS", 0)
                prate = (ppass / ptotal * 100) if ptotal > 0 else 0
                lines.append(f"**{pname.title()}**: {ptotal} assessed, {prate:.1f}% PASS ({pverdicts})")
        return AnswerPayload(
            type="text",
            title="Persona Comparison",
            content="\n".join(lines) + f"\n\nTotal documents: {total}{text_cites}" if lines else f"No persona data available.{text_cites}",
            summary=f"Comparing {len(personas)} persona assessments across {total} documents.",
        )

    # Convergence/trend queries
    if any(w in q for w in ("improv", "declin", "trend", "convergence", "track", "on track")):
        recent = stats.get("recent_100") or {}
        recent_pass = recent.get("PASS", 0)
        recent_total = sum(recent.values()) if recent else 0
        recent_rate = (recent_pass / recent_total * 100) if recent_total > 0 else 0
        overall_rate = (pass_count / total * 100) if total > 0 else 0
        target = stats.get("target_pass_rate_pct", 95)
        if recent_total > 0:
            delta = recent_rate - overall_rate
            trend = "improving" if delta > 1 else "declining" if delta < -1 else "stable"
            recent_line = f"Recent {recent_total}: {recent_rate:.1f}% ({recent_pass}/{recent_total})\n"
            trend_line = f"Trend: **{trend}** (Δ{delta:+.1f}pp)\n"
        else:
            trend = "stable"
            recent_line = ""
            trend_line = ""
        target_line = f"Target: {target}% — {'on track' if overall_rate >= target else f'{target - overall_rate:.1f}pp away'}"
        return AnswerPayload(
            type="text",
            title=f"Quality {trend.title()}",
            content=f"Overall pass rate: {overall_rate:.1f}% ({pass_count}/{total})\n"
                    f"{recent_line}{trend_line}{target_line}{text_cites}",
            summary=f"Quality is {trend}. Overall {overall_rate:.1f}% pass rate across {total} docs.",
        )

    # Dimension-specific queries
    if any(w in q for w in ("dimension", "which dimension", "most failure", "worst dimension", "equation", "table_fidelity", "content_coverage", "section")):
        # Fetch dimension data from verdicts endpoint
        verdicts_data = await _datalake_verdicts()
        if verdicts_data and verdicts_data.get("dimension_averages"):
            dim_avgs = verdicts_data["dimension_averages"]
            sorted_dims = sorted(dim_avgs.items(), key=lambda x: x[1] if x[1] is not None else 1.0)
            lines = [f"**{d.replace('_', ' ').title()}**: {v:.1%}" for d, v in sorted_dims if v is not None]
            worst = sorted_dims[0] if sorted_dims else None
            return AnswerPayload(
                type="text",
                title=f"Dimension Analysis",
                content=f"Dimension averages (worst → best):\n\n" + "\n".join(lines) +
                        (f"\n\nWorst dimension: **{worst[0].replace('_', ' ')}** at {worst[1]:.1%}" if worst and worst[1] is not None else "") +
                        f"{text_cites}",
                summary=f"{'The worst dimension is ' + worst[0].replace('_', ' ') + ' at ' + f'{worst[1]:.0%}' if worst and worst[1] is not None else 'Dimension analysis.'}",
            )

    # Default: offer a chart of verdicts + grades alongside text summary
    verdict_data = [
        {"label": "PASS", "value": pass_count},
        {"label": "WARN", "value": warn_count},
        {"label": "FAIL", "value": fail_count},
    ]
    grades = stats.get("grades", {})
    if grades:
        grade_data = [{"label": g, "value": c} for g, c in sorted(grades.items())]
        chart_data = grade_data if len(grade_data) > 3 else verdict_data
    else:
        chart_data = verdict_data

    shape = _describe_data_shape(chart_data)
    chart_type = await _select_viz_type(query, shape)
    if chart_type not in ("text",):
        html = await _figure_lab_compose(chart_data, chart_type, "Datalake Summary", persona)
        if html:
            text_block = (
                f"<div style='font-family:system-ui;font-size:18px;padding:16px;'>"
                f"<p>Documents: {total:,} | Average Score: {avg_score:.1%}</p>"
                f"<p>PASS: {pass_count} | WARN: {warn_count} | FAIL: {fail_count}</p>"
                f"</div>"
                f"{html_cites}"
            )
            viz_family = _get_viz_family(chart_type)
            return AnswerPayload(
                type="html",
                title="Datalake Summary",
                content=_inject_manipulation_runtime(f"{html}\n{text_block}", viz_family),
                summary=f"{total:,} documents, {avg_score:.0%} average score, {pass_count} passing.",
                source=f"datalake stats + viz({chart_type})",
                vizFamily=viz_family,
            )

    return AnswerPayload(
        type="text",
        title="Datalake Summary",
        content=f"Documents: {total:,}\n"
                f"Average Score: {avg_score:.1%}\n"
                f"PASS: {pass_count}  |  WARN: {warn_count}  |  FAIL: {fail_count}\n\n"
                f"Grades: {json.dumps(stats.get('grades', {}), indent=2)}{text_cites}",
        summary=f"{total:,} documents, {avg_score:.0%} average score, {pass_count} passing.",
    )


async def _handle_search(query: str, persona: str) -> AnswerPayload:
    """Handle SEARCH intent — query /memory recall, rank by taxonomy, cite sources."""
    search_terms = re.sub(r"\b(search|find|look for|where is|locate)\b", "", query, flags=re.I).strip()
    if not search_terms:
        search_terms = query

    ranked_items, text_cites, html_cites = await _recall_and_rank(search_terms, k=10)
    # Wrap in the expected dict format for backward compat
    results = {"items": ranked_items} if ranked_items else None
    if not results:
        try:
            resp = await _http_datalake.post(
                "/api/datalake/search",
                json={"query": search_terms, "k": 10},
            )
            resp.raise_for_status()
            results = resp.json()
        except Exception:
            return AnswerPayload(
                type="text",
                title="Search Error",
                content=f"Could not search for '{search_terms}'. Services may be down.",
                summary="Search services are not available right now.",
            )

    hits = results.get("items", results.get("results", results.get("lessons", [])))
    if not hits:
        return AnswerPayload(
            type="text",
            title=f"No results for '{search_terms}'",
            content=f"No matches found in memory for: {search_terms}",
            summary=f"I didn't find anything matching {search_terms}.",
        )

    table_data = []
    for h in hits[:20]:
        text = h.get("text", h.get("content", h.get("problem", "")))[:200]
        score = h.get("score", h.get("confidence", h.get("relevance", 0)))
        tags = h.get("tags", [])
        table_data.append({
            "text": text,
            "score": round(score, 3) if isinstance(score, float) else score,
            "tags": ", ".join(tags[:3]) if tags else "",
        })

    # When 3+ results with numeric scores, offer a visualization alongside the table
    numeric_results = [r for r in table_data if isinstance(r.get("score"), (int, float)) and r["score"] > 0]
    if len(numeric_results) >= 3:
        shape = _describe_data_shape(table_data)
        chart_type = await _select_viz_type(query, shape)
        if chart_type not in ("table", "text"):
            # Try to render a chart of the results
            chart_data = [
                {"label": r["text"][:40], "value": r["score"]}
                for r in numeric_results[:15]
            ]
            html = await _figure_lab_compose(chart_data, chart_type, f"Search: {search_terms}", persona)
            if html:
                # Return as HTML with both chart and table
                table_html = _build_inline_table(table_data)
                combined = f"{html}\n<details><summary style='font-size:18px;cursor:pointer;margin:16px 0;'>Show raw results ({len(hits)})</summary>\n{table_html}\n</details>"
                viz_family = _get_viz_family(chart_type)
                return AnswerPayload(
                    type="html",
                    title=f"Search: {search_terms}",
                    content=_inject_manipulation_runtime(combined, viz_family),
                    summary=f"Found {len(hits)} results for {search_terms}.",
                    source=f"memory recall + viz({chart_type})",
                    vizFamily=viz_family,
                )

    # Return results as an HTML table for structured display
    table_html = _build_inline_table(table_data)
    return AnswerPayload(
        type="html",
        title=f"Search: {search_terms}",
        content=table_html + text_cites,
        summary=f"Found {len(hits)} results for {search_terms}.",
        source="memory recall (taxonomy-ranked)",
    )


async def _handle_compare(query: str, persona: str) -> AnswerPayload:
    """Handle COMPARE intent — route to appropriate comparison sub-handler.

    Detects comparison type from query keywords:
    - Persona comparison (Margaret vs Jennifer)
    - Convergence/trend comparison (improving vs declining)
    - Dimension comparison (which dimension is worst)
    - Default: PASS/WARN/FAIL dimension comparison chart
    """
    q = query.lower()

    # --- Sub-routing: persona comparison ---
    if any(w in q for w in ("margaret", "jennifer", "persona", "assessor")):
        stats = await _datalake_stats()
        _, text_cites, _ = await _recall_and_rank(query, k=5)
        if stats and stats.get("personas"):
            personas = stats["personas"]
            lines = []
            for pname, pverdicts in personas.items():
                if pverdicts:
                    ptotal = sum(pverdicts.values())
                    ppass = pverdicts.get("PASS", 0)
                    prate = (ppass / ptotal * 100) if ptotal > 0 else 0
                    lines.append(f"**{pname.title()}**: {ptotal} assessed, {prate:.1f}% PASS ({pverdicts})")
            return AnswerPayload(
                type="text",
                title="Persona Comparison",
                content="\n".join(lines) + f"\n\n{text_cites}" if lines else f"No persona data available.{text_cites}",
                summary=f"Comparing {len(personas)} persona assessments.",
            )

    # --- Sub-routing: convergence/trend comparison ---
    if any(w in q for w in ("improv", "declin", "trend", "convergence", "track", "on track", "getting better", "getting worse")):
        stats = await _datalake_stats()
        _, text_cites, _ = await _recall_and_rank(query, k=5)
        if stats:
            total = stats.get("total_docs", 0)
            pass_count = stats.get("verdicts", {}).get("PASS", 0)
            recent = stats.get("recent_100") or {}
            recent_pass = recent.get("PASS", 0)
            recent_total = sum(recent.values()) if recent else 0
            recent_rate = (recent_pass / recent_total * 100) if recent_total > 0 else 0
            overall_rate = (pass_count / total * 100) if total > 0 else 0
            target = stats.get("target_pass_rate_pct", 95)
            if recent_total > 0:
                delta = recent_rate - overall_rate
                trend = "improving" if delta > 1 else "declining" if delta < -1 else "stable"
                recent_line = f"Recent {recent_total}: {recent_rate:.1f}% ({recent_pass}/{recent_total})\n"
                trend_line = f"Trend: **{trend}** (Δ{delta:+.1f}pp)\n"
            else:
                trend = "unknown"
                recent_line = ""
                trend_line = ""
                overall_rate_val = overall_rate
            target_line = f"Target: {target}% — {'on track' if overall_rate >= target else f'{target - overall_rate:.1f}pp away'}"
            return AnswerPayload(
                type="text",
                title=f"Quality {trend.title()}",
                content=f"Overall pass rate: {overall_rate:.1f}% ({pass_count}/{total})\n"
                        f"{recent_line}{trend_line}{target_line}\n\n{text_cites}",
                summary=f"Quality is {trend}. Overall {overall_rate:.1f}% pass rate across {total} docs.",
            )

    # --- Sub-routing: dimension failure ranking ---
    if any(w in q for w in ("dimension", "which dimension", "most failure", "worst", "best dimension")):
        verdicts_data = await _datalake_verdicts()
        _, text_cites, _ = await _recall_and_rank(query, k=5)
        if verdicts_data and verdicts_data.get("dimension_averages"):
            dim_avgs = verdicts_data["dimension_averages"]
            sorted_dims = sorted(dim_avgs.items(), key=lambda x: x[1] if x[1] is not None else 1.0)
            lines = [f"**{d.replace('_', ' ').title()}**: {v:.1%}" for d, v in sorted_dims if v is not None]
            worst = sorted_dims[0] if sorted_dims else None
            return AnswerPayload(
                type="text",
                title="Dimension Ranking",
                content=f"Dimension averages (worst → best):\n\n" + "\n".join(lines) +
                        (f"\n\nWorst: **{worst[0].replace('_', ' ')}** at {worst[1]:.1%}" if worst and worst[1] is not None else "") +
                        f"\n\n{text_cites}",
                summary=f"{'Worst: ' + worst[0].replace('_', ' ') + ' at ' + f'{worst[1]:.0%}' if worst and worst[1] is not None else 'Dimension analysis.'}",
            )

    # --- Default: PASS/WARN/FAIL dimension comparison chart ---
    verdicts_task = _datalake_verdicts()
    recall_task = _recall_and_rank(query, k=10)
    verdicts, (ranked_items, text_cites, html_cites) = await asyncio.gather(verdicts_task, recall_task)

    if not verdicts:
        return await _handle_query(query, persona)

    # Build radar data from per_verdict dimension averages
    # The verdicts endpoint returns: {verdicts: {}, per_verdict: {PASS: {dimension_averages: {}}, ...}}
    per_verdict = verdicts.get("per_verdict", {})
    radar_data: dict[str, dict[str, float]] = {}
    all_dims: dict[str, dict[str, float]] = {}

    # First try per_verdict structure (new format)
    if per_verdict:
        for vk, vd in per_verdict.items():
            if not isinstance(vd, dict):
                continue
            dim_avgs = vd.get("dimension_averages", {})
            if dim_avgs:
                radar_data[vk] = {d.replace("_", " "): round(v, 3) for d, v in dim_avgs.items() if v is not None}
            for dim, avg in dim_avgs.items():
                if avg is None:
                    continue
                if dim not in all_dims:
                    all_dims[dim] = {}
                all_dims[dim][vk] = round(avg, 3)
    else:
        # Fallback: legacy format where dimension_averages is at top level
        for vk, vd in verdicts.items():
            if not isinstance(vd, dict):
                continue
            dim_avgs = vd.get("dimension_averages", {})
            if dim_avgs:
                radar_data[vk] = {d.replace("_", " "): round(v, 3) for d, v in dim_avgs.items()}
            for dim, avg in dim_avgs.items():
                if dim not in all_dims:
                    all_dims[dim] = {}
                all_dims[dim][vk] = round(avg, 3)

    if not radar_data:
        # Last resort: use top-level dimension_averages as single series
        top_dims = verdicts.get("dimension_averages", {})
        if top_dims and any(v is not None for v in top_dims.values()):
            radar_data["Overall"] = {d.replace("_", " "): round(v, 3)
                                     for d, v in top_dims.items() if v is not None}
            for dim, avg in top_dims.items():
                if avg is not None:
                    all_dims[dim] = {"Overall": round(avg, 3)}

    if not radar_data:
        return await _handle_query(query, persona)

    # Data shape for viz-type-selector
    shape = _describe_data_shape(radar_data)

    # /assistant viz-type-selector (shadow mode)
    chart_type = await _select_viz_type(query, shape)

    # Constrain to comparison-appropriate chart types.
    # Treemap, pie, sunburst etc. make no sense for multi-series dimension comparison.
    _COMPARE_CHART_TYPES = {
        "grouped_bar", "bar", "hbar", "radar", "heatmap",
        "parallel_coords", "slope", "scatter", "spider",
    }
    if chart_type not in _COMPARE_CHART_TYPES:
        chart_type = "grouped_bar"

    # /assistant data-sufficiency-gate
    sufficiency = await _check_data_sufficiency(query, {
        "sources_available": ["datalake_verdicts"],
        "row_count": len(radar_data),
        "null_pct": 0,
        "column_types": list(next(iter(radar_data.values()), {}).keys()),
    })

    if sufficiency.get("verdict") == "INSUFFICIENT":
        return AnswerPayload(
            type="text",
            title="Insufficient Data for Comparison",
            content=sufficiency.get("reason", "Not enough data"),
            summary=sufficiency.get("reason", "Not enough data"),
        )

    # Render via /figure-lab — it handles data format adaptation internally.
    # Prepare data in the shape that best represents the comparison.
    if chart_type in ("grouped_bar", "bar", "hbar"):
        render_data = []
        for dim, scores in sorted(all_dims.items()):
            row: Dict[str, Any] = {"dimension": dim.replace("_", " ")}
            row.update(scores)
            render_data.append(row)
    elif chart_type == "parallel_coords":
        render_data = []
        for series_name, dim_scores in radar_data.items():
            row = {"series": series_name}
            row.update(dim_scores)
            render_data.append(row)
    elif chart_type == "slope":
        series_names = list(radar_data.keys())[:2]
        render_data = []
        if len(series_names) >= 2:
            dims = set()
            for s in series_names:
                dims.update(radar_data[s].keys())
            for dim in sorted(dims):
                render_data.append({
                    "dimension": dim,
                    series_names[0]: radar_data[series_names[0]].get(dim, 0),
                    series_names[1]: radar_data[series_names[1]].get(dim, 0),
                })
    elif chart_type == "scatter":
        render_data = []
        for series_name, dim_scores in radar_data.items():
            vals = list(dim_scores.values())
            if len(vals) >= 2:
                render_data.append({"label": series_name, "x": vals[0], "y": vals[1]})
    else:
        # radar, heatmap, etc. — flatten radar_data to list
        render_data = [
            {"label": k, **v} if isinstance(v, dict) else {"label": k, "value": v}
            for k, v in radar_data.items()
        ]

    html = await _figure_lab_compose(render_data, chart_type, "Quality Comparison", persona)

    if html:
        viz_family = _get_viz_family(chart_type)
        return AnswerPayload(
            type="html",
            title="Quality Comparison",
            content=_inject_manipulation_runtime(html, viz_family),
            summary=f"Comparing {len(all_dims)} dimensions across {len(radar_data)} categories.",
            source=f"viz-type-selector({chart_type}) + /figure-lab",
            vizFamily=viz_family,
        )

    # Fallback to table when rendering fails
    table_data = []
    for dim, scores in sorted(all_dims.items()):
        row_data: Dict[str, Any] = {"dimension": dim.replace("_", " ")}
        row_data.update(scores)
        table_data.append(row_data)

    # Format as Markdown table instead of raw JSON
    lines = []
    if table_data:
        headers = list(table_data[0].keys())
        lines.append("| " + " | ".join(str(h) for h in headers) + " |")
        lines.append("| " + " | ".join("---" for _ in headers) + " |")
        for row in table_data:
            vals = []
            for h in headers:
                v = row.get(h, "")
                vals.append(f"{v:.3f}" if isinstance(v, float) else str(v))
            lines.append("| " + " | ".join(vals) + " |")
    return AnswerPayload(
        type="table",
        title="Dimension Comparison",
        content="\n".join(lines) if lines else "No dimension data available.",
        summary=f"Comparing {len(all_dims)} quality dimensions.",
        source="datalake verdicts",
    )


async def _handle_navigate(query: str, persona: str) -> AnswerPayload:
    """Handle NAVIGATE intent — generate a link to the review page."""
    match = re.search(r'"([^"]+)"', query)
    if match:
        stem = match.group(1)
    else:
        words = query.lower().split()
        stop = {"open", "go", "to", "navigate", "show", "document", "review", "pdf", "file", "the", "a"}
        stem_words = [w for w in words if w not in stop]
        stem = "_".join(stem_words) if stem_words else query

    safe_stem = json.dumps(stem).replace("</", "<\\/")
    return AnswerPayload(
        type="html",
        title=f"Opening: {stem}",
        content=f"""<!DOCTYPE html>
<html><body style="display:flex;align-items:center;justify-content:center;height:100vh;font-family:system-ui;">
<div style="text-align:center;">
<p style="font-size:24px;color:#666;">Navigating to review...</p>
<script>window.location.href = '/review?stem=' + encodeURIComponent({safe_stem});</script>
</div>
</body></html>""",
        summary=f"Opening document {stem} in the review page.",
    )


async def _handle_explain(query: str, persona: str) -> AnswerPayload:
    """Handle EXPLAIN intent — query /memory, rank by taxonomy, cite sources."""
    ranked_items, text_cites, html_cites = await _recall_and_rank(query, k=10)

    if not ranked_items:
        return AnswerPayload(
            type="text",
            title="Explanation",
            content=f"I couldn't find information about that in memory.\n\nQuestion: {query}",
            summary="No relevant information found in memory.",
        )

    parts = []
    sources = []
    for h in ranked_items[:3]:
        text = h.get("text", h.get("content", h.get("solution", "")))
        if text:
            parts.append(text[:500])
        tags = h.get("tags", [])
        if tags:
            sources.extend(tags[:2])

    explanation = "\n\n---\n\n".join(parts) + text_cites
    source_str = ", ".join(set(sources)) if sources else "memory"

    return AnswerPayload(
        type="text",
        title="Answer",
        content=explanation,
        summary=parts[0][:200] if parts else "No clear answer found.",
        source=f"{source_str} (taxonomy-ranked)",
    )


# --- Code intent handler ---


async def _handle_code(query: str, persona: str) -> AnswerPayload:
    """Handle CODE intent — query /memory for code_symbol knowledge items.

    Uses two recall passes:
    1. Scoped recall with code_symbol tag for precise code knowledge
    2. General recall for supporting context (architecture, bugs fixed)
    """
    # Pass 1: Code-specific knowledge (6,037 code symbols from /ingest-code)
    code_items, code_text_cites, code_html_cites = await _recall_and_rank(
        query, k=10, scope="extractor"
    )

    # Pass 2: General knowledge for broader context
    general_items, _, _ = await _recall_and_rank(query, k=5)

    # Merge and deduplicate — code items first, then general
    seen_keys = set()
    merged = []
    for item in code_items + general_items:
        key = item.get("_key", item.get("title", id(item)))
        if key not in seen_keys:
            seen_keys.add(key)
            merged.append(item)

    if not merged:
        return AnswerPayload(
            type="text",
            title="Code",
            content=(
                f"I couldn't find code knowledge about that in memory.\n\n"
                f"Question: {query}\n\n"
                f"Try asking about specific pipeline steps (S00-S14), "
                f"modules, or functions."
            ),
            summary="No code knowledge found in memory.",
        )

    # Format response with file paths and code context
    parts = []
    sources = []
    for item in merged[:5]:
        title = item.get("title", "")
        text = item.get("text", item.get("content", item.get("solution", "")))
        problem = item.get("problem", "")
        file_path = item.get("file_path", "")
        tags = item.get("tags", [])

        section = ""
        if title:
            section += f"**{title}**\n"
        if file_path:
            section += f"`{file_path}`\n"
        if problem and problem != title:
            section += f"\n{problem}\n"
        if text:
            section += f"\n{text[:600]}\n"
        parts.append(section.strip())

        if file_path:
            sources.append(file_path.split("/")[-1])
        elif tags:
            sources.extend(tags[:2])

    content = "\n\n---\n\n".join(parts)
    if code_text_cites:
        content += code_text_cites
    source_str = ", ".join(list(set(sources))[:5]) if sources else "codebase"

    return AnswerPayload(
        type="text",
        title="Code",
        content=content,
        summary=parts[0][:200] if parts else "No code knowledge found.",
        source=f"{source_str} (code knowledge)",
    )


# --- Skill invocation ---

# Known skills that Nico can invoke through Embry conversation.
# Maps skill-name → (run.sh directory relative to pi-mono, description).
# /memory recall with scope=monitor-codebase also routes dynamically.
_SKILL_REGISTRY: dict[str, tuple[str, str]] = {
    "corpus-report": (".pi/skills/corpus-report", "Extraction corpus statistics and quality report"),
    "service-status": (".pi/skills/service-status", "Health check of Embry OS service daemons"),
    "monitor-codebase": (".pi/skills/monitor-codebase", "Codebase health scan for all registered projects"),
    "monitor-skills": (".pi/skills/monitor-skills", "Continuous skill health monitoring with drift correction"),
    "skill-lab": (".pi/skills/skill-lab", "Skill soup scanner, capability gap analysis, and skill creation"),
    "project-state": (".pi/skills/project-state", "Comprehensive Embry OS project state assessment"),
    "assess": (".pi/skills/assess", "Critical project state reassessment"),
    "monitor-skill-health": (".pi/skills/monitor-skill-health", "Nightly skill quality scan"),
    "dashboard": (".pi/skills/dashboard", "Unified Embry OS development dashboard"),
    "data-audit": (".pi/skills/data-audit", "SPARTA QRA pipeline data completeness report"),
}


# _recommend_skill_chain subprocess removed — now integrated into /memory recall
# via capability_routing.enrich_with_capabilities() → check_skill_chain().
# Use _get_skill_route(query) to access the full cascade through /memory.


def _extract_skill_name(query: str) -> tuple[str | None, str]:
    """Extract skill name from /prefix (syntactic only).

    NL→skill mapping is handled by /recommend-skill-chain in _handle_skill().
    Returns (skill_name, args_str) or (None, query) if no /prefix found.
    """
    q = query.strip()
    m = re.match(r"^/([\w-]+)\s*(.*)", q)
    if m:
        return m.group(1), m.group(2).strip()
    return None, q


async def _run_skill_subprocess(skill_dir: str, args: str, timeout: float = 30.0) -> str:
    """Run a skill's run.sh and capture output."""
    pi_mono = Path(os.environ.get("PI_MONO_DIR", str(Path(__file__).resolve().parents[4] / "pi-mono")))
    skill_path = pi_mono / skill_dir
    run_sh = skill_path / "run.sh"

    if not run_sh.exists():
        return f"Skill not found: {skill_dir} (run.sh missing at {run_sh})"

    cmd = f"cd {skill_path} && bash run.sh {args}"
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(skill_path),
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        output = stdout.decode("utf-8", errors="replace").strip()
        if not output and stderr:
            output = stderr.decode("utf-8", errors="replace").strip()
        # Truncate long output for chat display
        if len(output) > 4000:
            output = output[:3800] + f"\n\n... (truncated, {len(output)} chars total)"
        return output or "(no output)"
    except asyncio.TimeoutError:
        return f"Skill timed out after {timeout}s"
    except Exception as e:
        return f"Skill execution error: {e}"


async def _handle_skill(query: str, persona: str) -> AnswerPayload:
    """Handle SKILL intent — route to skill subprocess via Shadow-LEGO.

    Flow:
      1. Extract skill name from /prefix or NL mapping
      2. If no explicit skill, use /memory recall capability_routing to find one
      3. Execute skill via run.sh subprocess
      4. Return formatted output with citations from /memory
    """
    skill_name, args = _extract_skill_name(query)

    # If no /prefix, use /memory recall skill_route (full cascade via capability_routing)
    if not skill_name:
        skill_name = await _get_skill_route(query)
        if skill_name:
            args = query  # pass full query as args when skill found via NL

    # Still no skill? Fall back to /memory recall for an explanation
    if not skill_name or skill_name not in _SKILL_REGISTRY:
        # Try to answer from /memory knowledge about the topic
        ranked_items, text_cites, html_cites = await _recall_and_rank(query, k=10)
        if ranked_items:
            top = ranked_items[0]
            solution = top.get("solution") or top.get("playbook") or ""
            return AnswerPayload(
                type="text",
                title="Answer",
                content=f"{solution[:2000]}{text_cites}",
                summary=f"Answered from /memory. No matching skill found for direct execution.",
                source="memory (skill fallback)",
            )
        return AnswerPayload(
            type="text",
            title="Skill Not Found",
            content=f"I couldn't find a matching skill for: {query}\n\n"
                    f"Available skills: {', '.join(f'/{k}' for k in sorted(_SKILL_REGISTRY))}",
            summary="No matching skill found.",
            source="skill-router",
        )

    skill_dir, skill_desc = _SKILL_REGISTRY[skill_name]

    # Execute the skill
    log.info("SKILL intent: skill=%s args=%r", skill_name, args)
    output = await _run_skill_subprocess(skill_dir, args, timeout=45.0)

    # --- Synthesize skill output with /memory knowledge ---
    # Build a domain-specific recall query from the skill output (not the raw user query).
    # Extract key terms from the first 500 chars of output for a better /memory match.
    output_snippet = output[:500].replace("\n", " ").strip()
    # Combine user query + skill output keywords for a richer recall
    synthesis_query = f"{query} {output_snippet}"[:300]

    # Recall domain knowledge using the enriched query (no scope restriction)
    ranked_items, text_cites, _ = await _recall_and_rank(synthesis_query, k=5)

    # If skill output has structured data (numbers, scores, status), enrich with context
    has_data = any(c in output for c in ("%", "score", "PASS", "FAIL", "running", "stopped"))

    if ranked_items and text_cites:
        # Embry synthesizes: skill output + citations from /memory
        content = (
            f"**/{skill_name}** — {skill_desc}\n\n"
            f"```\n{output}\n```\n\n"
            f"{text_cites}"
        )
    else:
        # No /memory citations available — return skill output directly
        content = f"**/{skill_name}** — {skill_desc}\n\n```\n{output}\n```"

    return AnswerPayload(
        type="text",
        title=f"/{skill_name}",
        content=content,
        summary=f"Ran /{skill_name}. {output[:150]}",
        source=f"skill:{skill_name}",
    )


# --- Router ---

INTENT_HANDLERS = {
    "VISUALIZE": _handle_visualize,
    "QUERY": _handle_query,
    "SEARCH": _handle_search,
    "COMPARE": _handle_compare,
    "NAVIGATE": _handle_navigate,
    "EXPLAIN": _handle_explain,
    "CODE": _handle_code,
    "SKILL": _handle_skill,
    # MANIPULATE is handled specially in ask-stream — not a regular handler
}


@router.post("/ask")
async def ask(req: AskRequest) -> Dict[str, Any]:
    """/assistant classify → intent handler → AnswerPayload."""
    if len(req.query) > MAX_QUERY_LENGTH:
        return {"type": "text", "content": "Query too long.", "error": "Query exceeds maximum length."}
    classification = await classify_intent(req.query)
    intent = classification["intent"]

    handler = INTENT_HANDLERS.get(intent, _handle_explain)
    payload = await handler(req.query, req.persona)

    result = payload.model_dump()
    # Attach classification metadata for debugging and shadow training
    result["_classification"] = {
        "intent": intent,
        "confidence": classification["confidence"],
        "source": classification["source"],
        "d3_catalog_available": D3_CATALOG_AVAILABLE,
    }
    return result


@router.post("/ask-stream")
async def ask_stream(req: AskRequest):
    """SSE streaming version of /ask — emits status events during processing.

    Events:
      - {"event": "status", "data": {"status": "classifying"}}
      - {"event": "status", "data": {"status": "searching"}}
      - {"event": "status", "data": {"status": "rendering"}}
      - {"event": "status", "data": {"status": "manipulating"}}
      - {"event": "answer", "data": <AnswerPayload>}
      - {"event": "manipulate", "data": {"commands": [...]}}
      - {"event": "error", "data": {"message": "..."}}

    The frontend listens for these to drive the StatusIndicator in real-time
    instead of waiting for the full response.

    MANIPULATE intent: When the user's query is a manipulation command (zoom,
    highlight, filter, etc.) targeting the active visualization, we emit a
    "manipulate" event instead of "answer". The frontend forwards the commands
    to the active D3 iframe via postMessage.
    """
    if len(req.query) > MAX_QUERY_LENGTH:
        async def _err():
            yield _sse("error", {"message": "Query too long"})
        return StreamingResponse(_err(), media_type="text/event-stream")
    async def event_generator():
        try:
            # Session tracking — get or create session for this persona
            is_manip = _is_manipulation_command(req.query)
            session = await _get_or_create_session(req.persona, is_manipulation=is_manip)

            # Phase 0: Check for manipulation commands FIRST
            # Manipulation is fast — no data gathering needed
            if is_manip:
                yield _sse("status", {"status": "manipulating", "detail": "Parsing command..."})
                commands = _parse_manipulation_commands(req.query)

                if commands:
                    log.info(
                        "Manipulation: query=%r → %d commands: %s",
                        req.query, len(commands),
                        [c["action"] for c in commands],
                    )

                    # Track manipulation in session
                    session.add_manipulation(req.query, commands)

                    yield _sse("manipulate", {
                        "commands": commands,
                        "query": req.query,
                    })

                    # Also speak a brief confirmation
                    actions = [c["action"].replace("_", " ") for c in commands]
                    targets = [c.get("target", "") for c in commands if c.get("target")]
                    summary = f"Done. {', '.join(actions)}"
                    if targets:
                        summary += f" on {targets[0]}"
                    yield _sse("answer", {
                        "type": "text",
                        "content": "",
                        "summary": summary,
                    })
                    return

            # Phase 1: classify via /assistant (SetFit → scillm cascade)
            yield _sse("status", {"status": "classifying", "detail": "Analyzing intent..."})
            classification = await classify_intent(req.query)
            intent = classification["intent"]

            # Track user query in session
            session.add_user_query(
                req.query, intent,
                classification["confidence"],
                classification["source"],
            )

            yield _sse("status", {
                "status": "classifying",
                "detail": f"Intent: {intent} ({classification['confidence']:.0%})",
                "intent": intent,
                "confidence": classification["confidence"],
                "source": classification["source"],
            })

            # Phase 2: search / gather data
            yield _sse("status", {"status": "searching", "detail": "Gathering data..."})
            handler = INTENT_HANDLERS.get(intent, _handle_explain)

            # Run handler with periodic heartbeats so SSE read-timeout doesn't fire.
            # httpx read=30s means the client drops if no data arrives in 30s.
            # Handlers (esp. SKILL, VISUALIZE) can take 45-60s.
            handler_task = asyncio.create_task(handler(req.query, req.persona))
            heartbeat_n = 0
            while not handler_task.done():
                try:
                    await asyncio.wait_for(asyncio.shield(handler_task), timeout=10.0)
                except asyncio.TimeoutError:
                    heartbeat_n += 1
                    yield _sse("status", {
                        "status": "searching",
                        "detail": f"Working... ({heartbeat_n * 10}s)",
                    })
            payload = handler_task.result()

            # Phase 3: rendering (payload already built by handler)
            yield _sse("status", {"status": "rendering", "detail": "Preparing display..."})
            await asyncio.sleep(0.05)  # Allow SSE flush

            result = payload.model_dump()

            # Count QRA sources cited in the response content (text or HTML format)
            _content = result.get("content", "")
            if "Sources cited" in _content:
                # Count [N] citation markers — works for both text ("[1]") and HTML ("<strong>[1]</strong>")
                _cite_section = _content.split("Sources cited")[-1]
                _cite_matches = re.findall(r"\[(\d+)\]", _cite_section)
                result["sources_cited"] = len(_cite_matches) if _cite_matches else 0

            result["_classification"] = {
                "intent": intent,
                "confidence": classification["confidence"],
                "source": classification["source"],
                "d3_catalog_available": D3_CATALOG_AVAILABLE,
            }

            # Track agent answer in session
            chart_type = result.get("_classification", {}).get("chart_type", "")
            viz_family = result.get("vizFamily", "")
            session.add_agent_answer(result, chart_type, viz_family)

            yield _sse("answer", result)
        except Exception as e:
            log.exception("SSE ask-stream error")
            yield _sse("error", {"message": str(e)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _sse(event: str, data: dict) -> str:
    """Format a Server-Sent Event."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("/session/flush")
async def flush_session(req: AskRequest):
    """Flush the active canvas session to disk and archive via /episodic-archiver.

    Called when the user navigates away, closes the canvas, or on periodic flush.
    Also useful for the frontend to trigger explicit archival.
    """
    async with _session_lock:
        session = _active_sessions.pop(req.persona, None)
    if not session or not session.messages:
        return {"ok": True, "flushed": False, "reason": "no active session"}

    await _archive_session(session)
    return {
        "ok": True,
        "flushed": True,
        "session_id": session.session_id,
        "turns": len(session.messages),
        "manipulations": session.manipulation_count,
        "duration_s": session.last_activity - session.started_at,
    }


@router.get("/session/status")
async def session_status():
    """Report active canvas sessions — useful for debugging and monitoring."""
    sessions = {}
    for persona, session in _active_sessions.items():
        sessions[persona] = {
            "session_id": session.session_id,
            "turns": len(session.messages),
            "manipulations": session.manipulation_count,
            "duration_s": time.time() - session.started_at,
            "idle_s": time.time() - session.last_activity,
            "expired": session.is_expired(),
            "viz_context": session.viz_context,
        }
    return {"active_sessions": sessions}


def flush_all_sessions_sync() -> int:
    """Synchronously flush all active sessions — called at shutdown/atexit.

    Returns count of sessions flushed.
    """
    count = 0
    for persona in list(_active_sessions.keys()):
        session = _active_sessions.pop(persona, None)
        if session and session.messages:
            session.flush_to_disk()
            count += 1
            log.info("Shutdown flush: session %s (%d turns)", session.session_id, len(session.messages))
    return count


# Register atexit handler so sessions are always saved even on ungraceful shutdown
atexit.register(flush_all_sessions_sync)


@router.get("/health")
async def health() -> Dict[str, Any]:
    """Health check — reports skill availability and Shadow-LEGO status."""
    catalog_info = {}
    if D3_CATALOG_AVAILABLE:
        implemented = get_implemented_viz_types()
        catalog_info = {
            "total_viz_types": len(D3_VIZ_CATALOG),
            "implemented": len(implemented),
            "chart_cmds": len(_CHART_TO_FIGURE_CMD),
        }

    return {
        "ok": True,
        "skills": {
            "create_figure": CREATE_FIGURE.exists(),
            "analytics": ANALYTICS.exists(),
            "assistant": ASSISTANT_PY.exists(),
            "memory": MEMORY_SERVICE_URL,
            "datalake": DATALAKE_API_URL,
        },
        "classifier": {
            "canvas_intent": "/assistant classify --task canvas-intent (SetFit → scillm cascade)",
            "viz_type": "d3_catalog.recommend_viz() + /analytics data profiling",
            "skill_routing": "/recommend-skill-chain (Markov + DistilBERT + scillm cascade)",
            "d3_catalog": catalog_info,
        },
    }


# --- Voice proxy endpoints ---

WHISPER_URL = os.environ.get("WHISPER_URL", "http://127.0.0.1:2022")
KOKORO_URL = os.environ.get("KOKORO_URL", "http://127.0.0.1:8880")


class SpeakRequest(BaseModel):
    """Represent a request for speech synthesis."""
    text: str
    voice: str = "af_sky"
    speed: float = 1.0


MAX_AUDIO_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/voice/transcribe")
async def voice_transcribe(request: Request):
    """Proxy STT to Whisper — accepts audio blob, returns transcript text.

    PersonaPlex voice pipeline: browser records audio → this endpoint →
    Whisper (port 2022) → transcript returned to browser.
    """
    content_length = int(request.headers.get("content-length", 0))
    if content_length > MAX_AUDIO_BYTES:
        return JSONResponse({"error": "Audio too large", "text": ""}, status_code=413)

    body = await request.body()
    if len(body) > MAX_AUDIO_BYTES:
        return JSONResponse({"error": "Audio too large", "text": ""}, status_code=413)

    content_type = request.headers.get("content-type", "audio/webm")

    try:
        resp = await _http_voice.post(
            f"{WHISPER_URL}/v1/audio/transcriptions",
            files={"file": ("audio.webm", body, content_type)},
            data={"model": "whisper-1", "language": "en"},
        )
        resp.raise_for_status()
        result = resp.json()
        return {"text": result.get("text", "").strip()}
    except httpx.HTTPError as e:
        log.warning("Whisper STT failed: %s", e)
        return {"text": "", "error": str(e)}


@router.post("/voice/speak")
async def voice_speak(req: SpeakRequest):
    """Proxy TTS to Kokoro — returns audio/mpeg stream for browser playback.

    PersonaPlex voice pipeline: answer summary → this endpoint →
    Kokoro (port 8880) → audio streamed to browser.
    """
    try:
        resp = await _http_voice.post(
            f"{KOKORO_URL}/v1/audio/speech",
            json={
                "model": "kokoro",
                "input": req.text,
                "voice": req.voice,
                "speed": req.speed,
                "response_format": "mp3",
            },
        )
        resp.raise_for_status()
    except httpx.HTTPError as e:
        log.warning("Kokoro TTS failed: %s", e)
        return {"ok": False, "error": str(e)}

    return StreamingResponse(
        iter([resp.content]),
        media_type="audio/mpeg",
        headers={"Content-Disposition": "inline"},
    )
