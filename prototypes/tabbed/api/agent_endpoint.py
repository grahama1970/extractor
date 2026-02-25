#!/usr/bin/env python3
"""Agent endpoint — routes voice/text queries to skills and returns AnswerPayload.

Two-stage classifier architecture:
  Stage 1 (binary): Should this response be a visualization or text?
    - _should_visualize() — keyword heuristic (Tier 0) + /assistant (Tier 0.5+)
    - Determines VISUALIZE vs TEXT_RESPONSE before gathering data
  Stage 2 (viz type): What is the optimal visualization?
    - /analytics data profiling → d3_catalog.recommend_viz() (Tier 0)
    - /assistant validate(task="viz-type-selector") (Tier 0.5+)
    - d3_catalog has 60 viz types, 32 implemented — recommends by data shape

Full Shadow-LEGO pipeline:
  1. Stage 1 binary gate — "should I visualize or respond with text?"
  2. classify_intent() — route to QUERY/SEARCH/COMPARE/NAVIGATE/EXPLAIN/VISUALIZE
  3. /memory recall — "where is the data?"
  4. /assistant data-sufficiency-gate — "is there enough data?"
  5. Stage 2 viz-type selector (d3_catalog + /analytics) — "what chart type?"
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

import asyncio
import json
import logging
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
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


# --- Models ---


class AskRequest(BaseModel):
    query: str
    persona: str = "embry"


class AnswerPayload(BaseModel):
    type: str  # "image" | "html" | "data" | "table" | "text"
    title: Optional[str] = None
    content: str  # URL, HTML, JSON string, or plain text
    summary: Optional[str] = None  # TTS speaks this
    source: Optional[str] = None  # citation


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

# Keywords that strongly suggest visualization
_VIZ_KEYWORDS = [
    "show", "display", "chart", "graph", "plot", "visualize", "trend",
    "convergence", "distribution", "breakdown", "compare", "versus", "vs",
    "composition", "proportion", "ranking", "rank", "top", "heatmap",
    "radar", "spider", "sankey", "flow", "treemap", "timeline", "histogram",
    "over time", "trajectory", "progress",
]

# Keywords that strongly suggest text response
_TEXT_KEYWORDS = [
    "explain", "what is", "what does", "why", "describe", "tell me about",
    "how does", "define", "meaning of", "help", "instructions",
]

# Keywords that could go either way — Stage 1 uses data availability to decide
_AMBIGUOUS_KEYWORDS = [
    "how many", "count", "total", "number of", "percentage", "rate", "score",
    "status", "summary", "overview",
]


def _should_visualize(query: str) -> dict:
    """Stage 1 binary classifier: VISUALIZE vs TEXT_RESPONSE.

    Returns dict with:
      - decision: "VISUALIZE" | "TEXT_RESPONSE" | "AMBIGUOUS"
      - confidence: 0.0 - 1.0
      - reason: explanation string

    When "AMBIGUOUS", the system gathers data first, then Stage 2 decides
    whether the data is better shown as a chart or text/table.
    """
    q = query.lower()

    # Strong viz signals
    viz_score = sum(1 for kw in _VIZ_KEYWORDS if kw in q)
    text_score = sum(1 for kw in _TEXT_KEYWORDS if kw in q)
    ambig_score = sum(1 for kw in _AMBIGUOUS_KEYWORDS if kw in q)

    # Also check d3_catalog keyword matches
    catalog_score = 0.0
    if D3_CATALOG_AVAILABLE:
        kw_matches = catalog_match_keywords(q)
        if kw_matches:
            top_name, top_score = kw_matches[0]
            # text type should not count as viz
            if top_name != "text":
                catalog_score = min(top_score, 1.0)

    total_viz = viz_score * 0.3 + catalog_score * 0.5
    total_text = text_score * 0.4

    if total_viz > total_text and total_viz >= 0.3:
        return {
            "decision": "VISUALIZE",
            "confidence": min(0.95, 0.5 + total_viz * 0.2),
            "reason": f"viz keywords ({viz_score}) + catalog ({catalog_score:.1f})",
        }
    elif total_text > total_viz and total_text >= 0.3:
        return {
            "decision": "TEXT_RESPONSE",
            "confidence": min(0.95, 0.5 + total_text * 0.2),
            "reason": f"text keywords ({text_score})",
        }
    elif ambig_score > 0:
        return {
            "decision": "AMBIGUOUS",
            "confidence": 0.5,
            "reason": f"could be viz or text — need data shape to decide",
        }
    else:
        # Default: if query is short and question-like → text; otherwise → ambiguous
        if len(query.split()) <= 5 and "?" in query:
            return {"decision": "TEXT_RESPONSE", "confidence": 0.6, "reason": "short question"}
        return {"decision": "AMBIGUOUS", "confidence": 0.4, "reason": "no strong signal"}


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


async def _select_viz_type(query: str, data_shape: dict) -> str:
    """Use /assistant Shadow-LEGO cascade to pick optimal chart type.

    Tier 0: _heuristic_viz_type (keyword + shape rules)
    Tier 0.5+: /assistant validate(task="viz-type-selector") with scillm shadow
    """
    result = await _assistant_validate(
        task="viz-type-selector",
        input_data={"query": query, "data_shape": data_shape},
        heuristic_fn=lambda query, data_shape: _heuristic_viz_type(query, data_shape),
    )
    return result.get("chart_type", "bar")


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

    input_file = CANVAS_TMP / f"input_{id(data)}.json"
    output_file = CANVAS_TMP / f"output_{id(data)}.html"
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


# --- Data helpers ---


async def _memory_recall(query: str, k: int = 10, scope: str = "") -> Optional[dict]:
    """Query /memory recall API."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            body: dict[str, Any] = {"q": query, "k": k, "threshold": 0.3}
            if scope:
                body["scope"] = scope
            resp = await client.post(f"{MEMORY_SERVICE_URL}/recall", json=body)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            log.warning("memory recall failed: %s", e)
            return None


async def _datalake_stats() -> Optional[dict]:
    """Fetch datalake stats."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(f"{DATALAKE_API_URL}/api/datalake/stats")
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None


async def _datalake_convergence(limit: int = 50) -> Optional[dict]:
    """Fetch convergence data."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(f"{DATALAKE_API_URL}/api/datalake/convergence?limit={limit}")
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None


async def _datalake_verdicts() -> Optional[dict]:
    """Fetch verdicts data."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(f"{DATALAKE_API_URL}/api/datalake/verdicts")
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


INTENT_PATTERNS = {
    "VISUALIZE": [
        r"\b(show|display|chart|graph|plot|visualize|trend|convergence)\b",
    ],
    "QUERY": [
        r"\b(how many|count|total|number of|what is the|percentage|rate|score)\b",
    ],
    "SEARCH": [
        r"\b(search|find|look for|where is|locate)\b",
    ],
    "COMPARE": [
        r"\b(compare|versus|vs|difference between|rank)\b",
    ],
    "NAVIGATE": [
        r"\b(open|go to|navigate|show document|review)\b.*\b(document|pdf|file)\b",
    ],
    "EXPLAIN": [
        r"\b(explain|what does|why|describe|tell me about|how does)\b",
    ],
}


def _classify_intent_classifier(query: str) -> str | None:
    """Try Tier 0.5 sklearn classifier for canvas-intent. Returns None on failure."""
    try:
        import joblib
        from pathlib import Path

        model_path = Path.home() / ".pi" / "models" / "classifiers" / "canvas_intent_classifier.joblib"
        if not model_path.exists():
            return None
        clf = joblib.load(model_path)
        proba = clf.predict_proba([query])[0]
        best_idx = proba.argmax()
        confidence = proba[best_idx]
        if confidence < 0.6:
            return None
        return clf.classes_[best_idx]
    except Exception:
        return None


def _classify_intent_heuristic(query: str) -> str:
    """Regex-based fallback intent classification."""
    q = query.lower()
    stage1 = _should_visualize(query)
    decision = stage1["decision"]

    if decision == "VISUALIZE":
        for pattern in INTENT_PATTERNS.get("COMPARE", []):
            if re.search(pattern, q):
                return "COMPARE"
        for pattern in INTENT_PATTERNS.get("NAVIGATE", []):
            if re.search(pattern, q):
                return "NAVIGATE"
        return "VISUALIZE"

    elif decision == "TEXT_RESPONSE":
        for intent in ("SEARCH", "NAVIGATE", "QUERY", "EXPLAIN"):
            for pattern in INTENT_PATTERNS.get(intent, []):
                if re.search(pattern, q):
                    return intent
        return "EXPLAIN"

    else:  # AMBIGUOUS
        for intent in ("NAVIGATE", "SEARCH", "COMPARE", "VISUALIZE", "QUERY"):
            for pattern in INTENT_PATTERNS.get(intent, []):
                if re.search(pattern, q):
                    return intent
        return "QUERY"


def classify_intent(query: str) -> str:
    """Cascade intent classification: Tier 0.5 classifier → regex heuristic.

    Shadow-LEGO: classifier runs in shadow_mode. Disagreements with heuristic
    are logged to ~/.pi/assistant/shadow.jsonl for nightly harvest + retrain.
    """
    # Tier 0.5: trained classifier (canvas-intent)
    clf_result = _classify_intent_classifier(query)
    heuristic_result = _classify_intent_heuristic(query)

    if clf_result is not None:
        # Log disagreements for shadow learning
        if clf_result != heuristic_result:
            _log_shadow_disagreement(query, clf_result, heuristic_result)
        # Classifier is still in shadow_mode — use heuristic as source of truth
        # Once promoted (shadow_mode=false), swap to return clf_result
        return heuristic_result

    return heuristic_result


def _log_shadow_disagreement(query: str, clf: str, heuristic: str) -> None:
    """Log classifier vs heuristic disagreement for shadow harvest."""
    import json
    from pathlib import Path

    shadow_path = Path.home() / ".pi" / "assistant" / "shadow.jsonl"
    entry = {
        "task": "canvas-intent",
        "input": {"text": query},
        "classifier": clf,
        "heuristic": heuristic,
        "ts": __import__("time").time(),
    }
    try:
        with open(shadow_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


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
    memory_task = _memory_recall(query, k=3, scope="extractor")
    stats_task = _datalake_stats()
    convergence_task = _datalake_convergence(limit=50)
    verdicts_task = _datalake_verdicts()

    memory, stats, convergence, verdicts = await asyncio.gather(
        memory_task, stats_task, convergence_task, verdicts_task
    )

    # --- Step 2: Determine what data we actually have ---
    sources_available = []
    gathered_data: dict[str, Any] = {}

    if memory and memory.get("items"):
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

    # --- Step 4: /assistant viz-type-selector ---
    chart_type = await _select_viz_type(query, primary_shape)

    # --- Step 5: Render with selected chart type ---
    return await _render_with_type(
        query, chart_type, primary_data, primary_shape, gathered_data,
        sufficiency_verdict=verdict,
    )


def _select_primary_data(query: str, gathered_data: dict) -> tuple[Any, dict]:
    """Pick the most relevant dataset for this query and describe its shape."""
    q = query.lower()

    # Convergence trend
    if any(w in q for w in ("convergence", "trend", "progress", "trajectory")):
        conv = gathered_data.get("convergence", {})
        entries = conv.get("entries", [])
        if entries:
            points = [
                {"x": i + 1, "y": e.get("overall_score", 0)}
                for i, e in enumerate(entries)
                if e.get("overall_score") is not None
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
        return AnswerPayload(
            type="table",
            title=f"Data{partial_note}",
            content=json.dumps(table_rows),
            summary=f"{len(table_rows)} rows of data.",
            source="datalake + viz-type-selector",
        )

    # Map chart_type to /create-figure subcommand
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
        return AnswerPayload(
            type="html",
            title=_infer_title(q, chart_type) + partial_note,
            content=html,
            summary=summary,
            source=f"viz-type-selector({chart_type}) + /create-figure",
        )

    # Fallback to inline D3 data
    if isinstance(primary_data, dict):
        chart_data = [{"label": k, "value": v} for k, v in primary_data.items()]
    elif isinstance(primary_data, list):
        chart_data = [
            {"label": str(p.get("x", p.get("label", i))), "value": p.get("y", p.get("value", 0))}
            for i, p in enumerate(primary_data)
        ] if primary_data and isinstance(primary_data[0], dict) else []
    else:
        chart_data = []

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


# --- Remaining intent handlers ---


async def _handle_query(query: str, persona: str) -> AnswerPayload:
    """Handle QUERY intent — fetch stats with /memory enrichment."""
    q = query.lower()
    stats_task = _datalake_stats()
    memory_task = _memory_recall(query, k=3)
    stats, memory = await asyncio.gather(stats_task, memory_task)

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

    memory_note = ""
    if memory and memory.get("items"):
        top = memory["items"][0]
        if top.get("confidence", 0) > 0.5:
            solution = top.get("solution", "")[:200]
            if solution:
                memory_note = f"\n\nRelated insight from memory:\n{solution}"

    if any(w in q for w in ("fail", "failure")):
        return AnswerPayload(
            type="text",
            title=f"{fail_count} Failures",
            content=f"There are {fail_count} failed documents out of {total} total.\n\n"
                    f"PASS: {pass_count}  |  WARN: {warn_count}  |  FAIL: {fail_count}\n\n"
                    f"Average score: {avg_score:.1%}{memory_note}",
            summary=f"There are {fail_count} failures out of {total} documents.",
        )

    if any(w in q for w in ("pass", "success")):
        pass_rate = (pass_count / total * 100) if total > 0 else 0
        return AnswerPayload(
            type="text",
            title=f"{pass_rate:.0f}% Pass Rate",
            content=f"{pass_count} of {total} documents pass ({pass_rate:.1f}%).\n\n"
                    f"PASS: {pass_count}  |  WARN: {warn_count}  |  FAIL: {fail_count}{memory_note}",
            summary=f"{pass_rate:.0f}% pass rate, {pass_count} of {total} documents.",
        )

    if any(w in q for w in ("total", "how many", "count", "size", "documents")):
        return AnswerPayload(
            type="text",
            title=f"{total:,} Documents",
            content=f"The datalake contains {total:,} documents.\n\n"
                    f"Average score: {avg_score:.1%}\n"
                    f"PASS: {pass_count}  |  WARN: {warn_count}  |  FAIL: {fail_count}{memory_note}",
            summary=f"The datalake has {total:,} documents with an average score of {avg_score:.0%}.",
        )

    if any(w in q for w in ("score", "average", "quality")):
        return AnswerPayload(
            type="text",
            title=f"{avg_score:.1%} Average Score",
            content=f"Average extraction quality score: {avg_score:.1%}\n\n"
                    f"{total:,} documents total\n"
                    f"PASS: {pass_count}  |  WARN: {warn_count}  |  FAIL: {fail_count}{memory_note}",
            summary=f"The average quality score is {avg_score:.0%}.",
        )

    return AnswerPayload(
        type="text",
        title="Datalake Summary",
        content=f"Documents: {total:,}\n"
                f"Average Score: {avg_score:.1%}\n"
                f"PASS: {pass_count}  |  WARN: {warn_count}  |  FAIL: {fail_count}\n\n"
                f"Grades: {json.dumps(stats.get('grades', {}), indent=2)}{memory_note}",
        summary=f"{total:,} documents, {avg_score:.0%} average score, {pass_count} passing.",
    )


async def _handle_search(query: str, persona: str) -> AnswerPayload:
    """Handle SEARCH intent — query /memory recall."""
    search_terms = re.sub(r"\b(search|find|look for|where is|locate)\b", "", query, flags=re.I).strip()
    if not search_terms:
        search_terms = query

    results = await _memory_recall(search_terms, k=10)
    if not results:
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.post(
                    f"{DATALAKE_API_URL}/api/datalake/search",
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

    return AnswerPayload(
        type="table",
        title=f"Search: {search_terms}",
        content=json.dumps(table_data),
        summary=f"Found {len(hits)} results for {search_terms}.",
        source="memory recall",
    )


async def _handle_compare(query: str, persona: str) -> AnswerPayload:
    """Handle COMPARE intent — Shadow-LEGO pipeline with radar chart."""
    verdicts_task = _datalake_verdicts()
    memory_task = _memory_recall(query, k=3)
    verdicts, memory = await asyncio.gather(verdicts_task, memory_task)

    if not verdicts:
        return await _handle_query(query, persona)

    # Build radar data
    radar_data: dict[str, dict[str, float]] = {}
    all_dims: dict[str, dict[str, float]] = {}
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
        return await _handle_query(query, persona)

    # Data shape for viz-type-selector
    shape = _describe_data_shape(radar_data)

    # /assistant viz-type-selector (shadow mode)
    chart_type = await _select_viz_type(query, shape)

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

    # Render with selected type (default radar for comparisons)
    if chart_type in ("radar", "heatmap"):
        html = await _render_figure(radar_data, chart_type, "", "Quality Comparison")
        if html:
            return AnswerPayload(
                type="html",
                title="Quality Comparison",
                content=html,
                summary=f"Comparing {len(all_dims)} dimensions across {len(radar_data)} categories.",
                source=f"viz-type-selector({chart_type}) + /create-figure",
            )

    # Fallback to table
    table_data = []
    for dim, scores in sorted(all_dims.items()):
        row: Dict[str, Any] = {"dimension": dim.replace("_", " ")}
        row.update(scores)
        table_data.append(row)

    return AnswerPayload(
        type="table",
        title="Dimension Comparison",
        content=json.dumps(table_data),
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

    return AnswerPayload(
        type="html",
        title=f"Opening: {stem}",
        content=f"""<!DOCTYPE html>
<html><body style="display:flex;align-items:center;justify-content:center;height:100vh;font-family:system-ui;">
<div style="text-align:center;">
<p style="font-size:24px;color:#666;">Navigating to review...</p>
<script>window.top.location.href = '/review?stem={stem}';</script>
</div>
</body></html>""",
        summary=f"Opening document {stem} in the review page.",
    )


async def _handle_explain(query: str, persona: str) -> AnswerPayload:
    """Handle EXPLAIN intent — query /memory for knowledge."""
    results = await _memory_recall(query, k=5)

    if not results:
        return AnswerPayload(
            type="text",
            title="Explanation",
            content=f"I couldn't reach the memory service to answer: {query}",
            summary="Memory service is not available.",
        )

    hits = results.get("items", results.get("results", results.get("lessons", [])))
    if not hits:
        return AnswerPayload(
            type="text",
            title="No Information Found",
            content=f"I don't have information about that in memory.\n\nQuestion: {query}",
            summary="I don't have enough information to answer that.",
        )

    parts = []
    sources = []
    for h in hits[:3]:
        text = h.get("text", h.get("content", h.get("solution", "")))
        if text:
            parts.append(text[:500])
        tags = h.get("tags", [])
        if tags:
            sources.extend(tags[:2])

    explanation = "\n\n---\n\n".join(parts)
    source_str = ", ".join(set(sources)) if sources else "memory"

    return AnswerPayload(
        type="text",
        title="Answer",
        content=explanation,
        summary=parts[0][:200] if parts else "No clear answer found.",
        source=source_str,
    )


# --- Router ---

INTENT_HANDLERS = {
    "VISUALIZE": _handle_visualize,
    "QUERY": _handle_query,
    "SEARCH": _handle_search,
    "COMPARE": _handle_compare,
    "NAVIGATE": _handle_navigate,
    "EXPLAIN": _handle_explain,
}


@router.post("/ask")
async def ask(req: AskRequest) -> Dict[str, Any]:
    """Two-stage classifier → intent handler → AnswerPayload.

    Stage 1: _should_visualize() — binary VISUALIZE vs TEXT_RESPONSE
    Stage 2: If VISUALIZE, viz-type-selector picks optimal chart from d3_catalog
    """
    # Stage 1 binary gate (logged for shadow training)
    stage1 = _should_visualize(req.query)
    intent = classify_intent(req.query)

    handler = INTENT_HANDLERS.get(intent, _handle_explain)
    payload = await handler(req.query, req.persona)

    result = payload.model_dump()
    # Attach classification metadata for debugging and shadow training
    result["_classification"] = {
        "stage1": stage1,
        "intent": intent,
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
      - {"event": "answer", "data": <AnswerPayload>}
      - {"event": "error", "data": {"message": "..."}}

    The frontend listens for these to drive the StatusIndicator in real-time
    instead of waiting for the full response.
    """
    async def event_generator():
        try:
            # Phase 1: classify
            yield _sse("status", {"status": "classifying", "detail": "Analyzing intent..."})
            stage1 = _should_visualize(req.query)
            intent = classify_intent(req.query)
            yield _sse("status", {
                "status": "classifying",
                "detail": f"Intent: {intent}",
                "intent": intent,
                "stage1": stage1["decision"],
            })

            # Phase 2: search / gather data
            yield _sse("status", {"status": "searching", "detail": "Gathering data..."})
            handler = INTENT_HANDLERS.get(intent, _handle_explain)
            payload = await handler(req.query, req.persona)

            # Phase 3: rendering (payload already built by handler)
            yield _sse("status", {"status": "rendering", "detail": "Preparing display..."})
            await asyncio.sleep(0.05)  # Allow SSE flush

            result = payload.model_dump()
            result["_classification"] = {
                "stage1": stage1,
                "intent": intent,
                "d3_catalog_available": D3_CATALOG_AVAILABLE,
            }

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
        "two_stage_classifier": {
            "stage1": "binary VISUALIZE vs TEXT_RESPONSE (keyword heuristic + d3_catalog)",
            "stage2": "d3_catalog.recommend_viz() + /analytics data profiling",
            "d3_catalog": catalog_info,
        },
        "shadow_lego": {
            "viz_type_selector": "shadow_mode (d3_catalog Tier 0 → scillm teacher)",
            "data_sufficiency_gate": "shadow_mode (threshold rules → scillm teacher)",
            "note": "Tier 0 heuristics active. Shadow logs at ~/.pi/assistant/shadow.jsonl",
        },
    }


# --- Voice proxy endpoints ---

WHISPER_URL = os.environ.get("WHISPER_URL", "http://127.0.0.1:2022")
KOKORO_URL = os.environ.get("KOKORO_URL", "http://127.0.0.1:8880")


class SpeakRequest(BaseModel):
    text: str
    voice: str = "af_sky"
    speed: float = 1.0


@router.post("/voice/transcribe")
async def voice_transcribe(request: Request):
    """Proxy STT to Whisper — accepts audio blob, returns transcript text.

    PersonaPlex voice pipeline: browser records audio → this endpoint →
    Whisper (port 2022) → transcript returned to browser.
    """
    body = await request.body()
    content_type = request.headers.get("content-type", "audio/webm")

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
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
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
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
