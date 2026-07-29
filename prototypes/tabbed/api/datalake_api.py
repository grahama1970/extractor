#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "fastapi>=0.115.0",
#   "uvicorn>=0.32.0",
#   "httpx>=0.27.0",
#   "pydantic>=2.4.0",
# ]
# ///
"""Datalake API gateway — proxies /memory service for the dashboard UI.

All data flows through the /memory HTTP API (port 8601).
No direct ArangoDB connections — /memory is the authorized interface.
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from pydantic import BaseModel

app = FastAPI(title="Datalake API Gateway")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MEMORY_SERVICE_URL = os.environ.get("MEMORY_SERVICE_URL", "http://127.0.0.1:8601")
PI_SKILLS_ROOT = Path(
    os.environ.get("PI_SKILLS_ROOT", Path.home() / "workspace/experiments/pi-mono/.pi/skills")
)
STATE_DIR = Path(
    os.environ.get(
        "STATE_DIR",
        PI_SKILLS_ROOT / "learn-datalake/state",
    )
)
TASK_MONITOR_DIR = STATE_DIR / "task_monitor"
SHADOW_DIR = Path(os.environ.get(
    "SHADOW_DIR",
    STATE_DIR / "shadow",
))


def _append_shadow(filename: str, record: dict) -> None:
    """Append a JSON line to SHADOW_DIR / filename. Never raises."""
    try:
        SHADOW_DIR.mkdir(parents=True, exist_ok=True)
        record["timestamp"] = datetime.now(timezone.utc).isoformat()
        with open(SHADOW_DIR / filename, "a") as f:
            f.write(json.dumps(record) + "\n")
    except Exception:
        pass


# --- Shared HTTP client (connection pooling) + retry ---

_memory_client: Optional[httpx.AsyncClient] = None

_MAX_RETRIES = 3
_RETRY_BACKOFF = [1, 2, 4]  # seconds


def _get_memory_client() -> httpx.AsyncClient:
    """Lazy-init a persistent AsyncClient for connection pooling."""
    global _memory_client
    if _memory_client is None or _memory_client.is_closed:
        _memory_client = httpx.AsyncClient(
            base_url=MEMORY_SERVICE_URL,
            timeout=30.0,
        )
    return _memory_client


async def _memory_request(
    method: str, path: str, *, params: Optional[Dict] = None,
    body: Optional[Dict] = None, timeout: float = 30,
) -> Dict[str, Any]:
    """HTTP request to /memory with retry on transient failures.

    Retries ConnectError and TimeoutException up to 3 times with
    exponential backoff (1s, 2s, 4s). Docker/systemd restart the
    memory service on crash — retries bridge the gap.
    """
    client = _get_memory_client()
    last_err: Optional[Exception] = None

    for attempt in range(_MAX_RETRIES):
        try:
            if method == "GET":
                resp = await client.get(path, params=params or {}, timeout=timeout)
            else:
                resp = await client.post(path, json=body, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            last_err = e
            if attempt < _MAX_RETRIES - 1:
                wait = _RETRY_BACKOFF[attempt]
                logger.warning(
                    "Memory service %s %s failed (attempt %d/%d), retrying in %ds: %s",
                    method, path, attempt + 1, _MAX_RETRIES, wait, type(e).__name__,
                )
                await asyncio.sleep(wait)
            else:
                logger.error(
                    "Memory service %s %s failed after %d attempts: %s",
                    method, path, _MAX_RETRIES, e,
                )
        except httpx.HTTPStatusError as e:
            logger.error("Memory service %s %s returned %s: %s", method, path, e.response.status_code, e)
            return {"error": f"HTTP {e.response.status_code}: {MEMORY_SERVICE_URL}{path}"}
        except httpx.HTTPError as e:
            logger.error("Memory service %s %s failed: %s (%s)", method, path, type(e).__name__, e)
            return {"error": f"{type(e).__name__}: {e}"}

    err_type = type(last_err).__name__ if last_err else "Unknown"
    return {"error": f"{err_type} after {_MAX_RETRIES} retries: {MEMORY_SERVICE_URL}{path}"}


# --- Helpers ---

async def _memory_get(path: str, params: Optional[Dict] = None, timeout: float = 60) -> Dict[str, Any]:
    """GET request to /memory service with retry."""
    return await _memory_request("GET", path, params=params, timeout=timeout)


async def _memory_post(path: str, body: Dict) -> Dict[str, Any]:
    """POST request to /memory service with retry."""
    return await _memory_request("POST", path, body=body)


async def _recall_all(query: str, target_k: int = 50) -> List[Dict[str, Any]]:
    """Recall from /memory with k capped at 50 (API limit)."""
    k = min(target_k, 50)
    data = await _memory_post("/recall", {"q": query, "k": k, "threshold": 0.1})
    items = data.get("items", [])
    if not items and "results" in data:
        items = data["results"]
    return items


def _load_json(path: Path) -> Optional[Any]:
    """Load JSON from path, returning None on failure."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


# --- Endpoints: proxy to /memory datalake endpoints ---


def _parse_assessment(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Parse a /memory item into assessment data. Returns None if not an assessment."""
    tags = item.get("tags", [])
    if not any(t in tags for t in ["pdf_assessment", "quality_gate", "extraction_quality"]):
        return None

    sol_text = item.get("solution") or item.get("playbook") or ""
    sol: Dict[str, Any] = {}
    try:
        sol = json.loads(sol_text)
    except (json.JSONDecodeError, TypeError):
        pass

    # Extract verdict from tags first, then from parsed JSON
    verdict = None
    for v in ("PASS", "WARN", "FAIL"):
        if v in tags or v.lower() in tags:
            verdict = v
            break
    if not verdict:
        verdict = sol.get("verdict")

    # Extract score from parsed JSON, fall back to regex
    score = sol.get("overall_score")
    if score is None:
        import re as _re
        m = _re.search(r'"overall_score":\s*(\d+\.?\d*)', sol_text)
        if m:
            score = float(m.group(1))

    # Extract grade from parsed JSON, fall back to tags
    grade = sol.get("grade")
    if not grade:
        for t in tags:
            if t in ("A+", "A", "B", "C", "F"):
                grade = t
                break

    return {
        "score": float(score) if score is not None else None,
        "verdict": verdict,
        "grade": grade,
        "dimensions": sol.get("dimensions", {}),
        "margaret_verdict": sol.get("margaret_verdict"),
        "jennifer_verdict": sol.get("jennifer_verdict"),
        "pdf_path": sol.get("pdf_path", ""),
        "pdf_hash": sol.get("pdf_hash", ""),
        "key": item.get("_key", ""),
        "title": item.get("title", ""),
        "updated_at": item.get("updated_at"),
    }


@app.get("/api/datalake/stats")
async def datalake_stats() -> Dict[str, Any]:
    """Aggregate statistics from /memory's datalake stats endpoint (AQL-backed)."""
    # Single attempt, short timeout — recall fallback is more reliable
    try:
        client = _get_memory_client()
        resp = await client.get("/datalake/stats", timeout=5)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        data = {"error": "timeout"}
    if "error" in data:
        logger.warning("Falling back to recall-based stats: %s", data["error"])
        # Fallback: limited recall-based stats
        return await _datalake_stats_fallback()
    return data


async def _datalake_stats_fallback() -> Dict[str, Any]:
    """Fallback stats via /memory recall (capped at ~150 docs)."""
    pass_items, fail_items, warn_items = await asyncio.gather(
        _recall_all("pdf_assessment overall_score verdict PASS quality grade", target_k=50),
        _recall_all("pdf_assessment overall_score verdict FAIL quality grade", target_k=50),
        _recall_all("pdf_assessment overall_score verdict WARN quality grade", target_k=50),
    )
    seen_keys: set = set()
    items: List[Dict[str, Any]] = []
    for batch in [pass_items, fail_items, warn_items]:
        for item in batch:
            key = item.get("key") or item.get("_key") or id(item)
            if key not in seen_keys:
                seen_keys.add(key)
                items.append(item)

    verdicts: Dict[str, int] = {"PASS": 0, "WARN": 0, "FAIL": 0}
    scores: List[float] = []
    grades: Dict[str, int] = {}
    margaret_verdicts: Dict[str, int] = {}
    jennifer_verdicts: Dict[str, int] = {}
    dim_sums: Dict[str, float] = {}
    dim_counts: Dict[str, int] = {}
    total_assessed = 0
    parsed_items: List[Dict[str, Any]] = []

    for item in items:
        parsed = _parse_assessment(item)
        if not parsed:
            continue

        total_assessed += 1
        parsed_items.append(parsed)

        if parsed["verdict"] and parsed["verdict"] in verdicts:
            verdicts[parsed["verdict"]] += 1

        if parsed["score"] is not None:
            s = parsed["score"]
            if s <= 1.0:
                scores.append(s)
            elif s <= 100:
                scores.append(s / 100.0)

        if parsed["grade"]:
            g = parsed["grade"]
            grades[g] = grades.get(g, 0) + 1

        mv = parsed.get("margaret_verdict")
        if mv:
            margaret_verdicts[mv] = margaret_verdicts.get(mv, 0) + 1
        jv = parsed.get("jennifer_verdict")
        if jv:
            jennifer_verdicts[jv] = jennifer_verdicts.get(jv, 0) + 1

        dims = parsed.get("dimensions") or {}
        for dim_name, dim_val in dims.items():
            s = None
            if isinstance(dim_val, dict):
                s = dim_val.get("score")
                if dim_val.get("state") in ("not_available", "unknown"):
                    s = None
            elif isinstance(dim_val, (int, float)):
                s = float(dim_val)
            if isinstance(s, (int, float)) and 0 < s <= 1.0:
                dim_sums[dim_name] = dim_sums.get(dim_name, 0.0) + s
                dim_counts[dim_name] = dim_counts.get(dim_name, 0) + 1

    avg_score = sum(scores) / len(scores) if scores else 0.0
    total = total_assessed or max(1, sum(verdicts.values()))
    dim_averages = {k: round(dim_sums[k] / dim_counts[k], 4) for k in dim_sums if dim_counts.get(k)}

    # Approximate recent_100 from items with timestamps (sorted by recency)
    timestamped = [(p, p.get("updated_at") or "") for p in parsed_items if p.get("updated_at")]
    timestamped.sort(key=lambda x: x[1], reverse=True)
    recent_100: Dict[str, int] = {"PASS": 0, "WARN": 0, "FAIL": 0}
    for p, _ in timestamped[:100]:
        v = p.get("verdict")
        if v and v in recent_100:
            recent_100[v] += 1

    return {
        "total_docs": total,
        "avg_score": round(avg_score, 4),
        "verdicts": verdicts,
        "grades": grades,
        "assessed_count": total_assessed,
        "scores_count": len(scores),
        "personas": {
            "margaret": margaret_verdicts,
            "jennifer": jennifer_verdicts,
        },
        "dimension_averages": dim_averages,
        "recent_100": recent_100 if timestamped else None,
        "target_pass_rate_pct": 95,
        "_fallback": True,
    }


@app.get("/api/datalake/verdicts")
async def datalake_verdicts() -> Dict[str, Any]:
    """Verdict breakdown with per-verdict dimension averages from /memory.

    Returns dimension_averages per verdict so _handle_compare can build
    radar/grouped-bar charts comparing PASS vs FAIL quality profiles.
    """
    # Try /memory's direct datalake/verdicts endpoint first (AQL-backed, no k-cap).
    # Single attempt with short timeout — fall through to recall fallback quickly.
    try:
        client = _get_memory_client()
        resp = await client.get("/datalake/verdicts", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        if data.get("verdicts"):
            return data
    except Exception:
        pass  # Fall through to recall-based fallback

    # Fallback: recall-based (capped at ~150 docs)
    pass_items, fail_items, warn_items = await asyncio.gather(
        _recall_all("pdf_assessment overall_score verdict PASS dimensions quality", target_k=50),
        _recall_all("pdf_assessment overall_score verdict FAIL dimensions quality", target_k=50),
        _recall_all("pdf_assessment overall_score verdict WARN dimensions quality", target_k=50),
    )
    # Deduplicate by key
    seen_keys: set = set()
    items: List[Dict[str, Any]] = []
    for batch in [pass_items, fail_items, warn_items]:
        for item in batch:
            key = item.get("key") or item.get("_key") or id(item)
            if key not in seen_keys:
                seen_keys.add(key)
                items.append(item)

    verdicts: Dict[str, List[Dict[str, Any]]] = {"PASS": [], "WARN": [], "FAIL": []}
    dimensions = ["content_coverage", "section_alignment", "table_fidelity",
                   "equation_fidelity", "ordering_yx", "figure_fidelity", "data_quality"]
    # Per-verdict dimension scores for comparison charts
    per_verdict_dims: Dict[str, Dict[str, List[float]]] = {
        v: {d: [] for d in dimensions} for v in verdicts
    }
    # Global dimension scores
    dim_scores: Dict[str, List[float]] = {d: [] for d in dimensions}

    for item in items:
        parsed = _parse_assessment(item)
        if not parsed:
            continue

        verdict = parsed["verdict"]
        if verdict and verdict in verdicts:
            verdicts[verdict].append({"key": parsed["key"], "title": parsed["title"][:80]})

        # Extract dimension scores from parsed JSON
        for dim in dimensions:
            dim_data = parsed["dimensions"].get(dim, {})
            s = None
            state = ""
            if isinstance(dim_data, dict):
                s = dim_data.get("score")
                state = dim_data.get("state", "")
            elif isinstance(dim_data, (int, float)) and dim_data <= 1.0:
                s = float(dim_data)
            if isinstance(s, (int, float)) and s <= 1.0 and state not in ("not_available", "unknown"):
                dim_scores[dim].append(s)
                if verdict and verdict in per_verdict_dims:
                    per_verdict_dims[verdict][dim].append(s)

    dim_avgs = {d: round(sum(v) / len(v), 4) if v else None for d, v in dim_scores.items()}
    # Per-verdict dimension averages (for _handle_compare radar/bar charts)
    per_verdict_avgs: Dict[str, Dict[str, Any]] = {}
    for v, dim_map in per_verdict_dims.items():
        count = len(verdicts[v])
        if count > 0:
            avgs = {d: round(sum(scores) / len(scores), 4) if scores else None
                    for d, scores in dim_map.items()}
            per_verdict_avgs[v] = {
                "count": count,
                "dimension_averages": {d: a for d, a in avgs.items() if a is not None},
            }

    return {
        "verdicts": {v: len(items) for v, items in verdicts.items()},
        "verdict_details": {v: items[:10] for v, items in verdicts.items()},
        "dimension_averages": dim_avgs,
        "per_verdict": per_verdict_avgs,
    }


@app.get("/api/datalake/dimension-failures")
async def dimension_failures() -> Dict[str, Any]:
    """Top dimension failures for FAIL PDFs from /memory."""
    items = await _recall_all("extraction overall_score verdict FAIL dimension", target_k=50)

    dimensions = ["content_coverage", "section_alignment", "table_fidelity",
                   "equation_fidelity", "ordering_yx", "figure_fidelity", "data_quality"]
    failures: Dict[str, int] = {d: 0 for d in dimensions}

    for item in items:
        parsed = _parse_assessment(item)
        if not parsed or parsed["verdict"] != "FAIL":
            continue
        for dim in dimensions:
            dim_data = parsed["dimensions"].get(dim, {})
            s = None
            if isinstance(dim_data, dict):
                s = dim_data.get("score")
            elif isinstance(dim_data, (int, float)):
                s = dim_data
            if isinstance(s, (int, float)) and s <= 1.0 and s < 0.65:
                failures[dim] += 1

    ranked = sorted(failures.items(), key=lambda x: x[1], reverse=True)
    return {"dimension_failures": [{"dimension": d, "fail_count": c} for d, c in ranked if c > 0]}


@app.get("/api/datalake/convergence")
async def datalake_convergence(limit: int = Query(100, ge=1, le=1000)) -> Dict[str, Any]:
    """Convergence data — assessment scores over time from /memory."""
    # Separate queries per verdict to get balanced PASS/FAIL representation
    pass_items, fail_items, warn_items = await asyncio.gather(
        _recall_all("pdf_assessment overall_score verdict PASS quality", target_k=50),
        _recall_all("pdf_assessment overall_score verdict FAIL quality", target_k=50),
        _recall_all("pdf_assessment overall_score verdict WARN quality", target_k=50),
    )
    seen_keys: set = set()
    items: List[Dict[str, Any]] = []
    for batch in [pass_items, fail_items, warn_items]:
        for item in batch:
            key = item.get("key") or item.get("_key") or id(item)
            if key not in seen_keys:
                seen_keys.add(key)
                items.append(item)

    entries: List[Dict[str, Any]] = []
    for item in items:
        parsed = _parse_assessment(item)
        if not parsed:
            continue
        entries.append({
            "key": parsed["key"],
            "score": parsed["score"],
            "verdict": parsed["verdict"],
            "updated_at": parsed["updated_at"],
        })

    entries.sort(key=lambda e: e.get("updated_at") or 0)
    result: Dict[str, Any] = {"entries": entries[-limit:], "total": len(entries)}
    result["supervisor_state"] = _load_json(TASK_MONITOR_DIR / "learn_datalake_supervisor_corpus.json")
    return result


@app.get("/api/datalake/quarantine")
async def quarantine_list(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> Dict[str, Any]:
    """List FAIL PDFs — the human collaboration queue from /memory."""
    items = await _recall_all("pdf assessment FAIL quarantine extraction", target_k=50)

    quarantined: List[Dict[str, Any]] = []
    for item in items:
        tags = item.get("tags", [])
        if "fail" not in tags and "FAIL" not in tags and "quarantine" not in tags:
            continue
        quarantined.append({
            "key": item.get("_key", ""),
            "title": (item.get("problem") or item.get("title") or "")[:120],
            "tags": tags,
            "updated_at": item.get("updated_at"),
        })

    return {
        "quarantined": quarantined[offset:offset + limit],
        "total": len(quarantined),
        "offset": offset,
        "limit": limit,
    }


@app.get("/api/datalake/supervisor")
async def supervisor_status() -> Dict[str, Any]:
    """Live supervisor state from task monitor files."""
    sup_state = _load_json(TASK_MONITOR_DIR / "learn_datalake_supervisor_corpus.json")
    if not sup_state:
        return {"status": "not_running"}

    workers = []
    for i in range(12):
        wf = TASK_MONITOR_DIR / f"review_state_worker_{i}.json"
        w = _load_json(wf)
        if w:
            workers.append({
                "worker": i,
                "status": w.get("stats", {}).get("status", "unknown"),
                "current_item": w.get("current_item", ""),
                "completed": w.get("completed", 0),
            })

    return {"supervisor": sup_state, "workers": workers}


# --- Document Detail (for data integrity verification) ---


@app.get("/api/datalake/document/{stem}")
async def document_detail(stem: str) -> Dict[str, Any]:
    """Get everything /memory knows about a specific document.

    Proxies to /memory's datalake/document/{stem} endpoint which uses
    semantic + BM25 + multi-hop graph traversal.
    """
    return await _memory_get(f"/datalake/document/{stem}")


# --- Search & Persona ---


class SearchRequest(BaseModel):
    """Build a search request with query and optional parameters."""
    query: str
    asset_type: Optional[str] = None
    k: int = 20
    domain: Optional[str] = None


@app.post("/api/datalake/search")
async def datalake_search(req: SearchRequest) -> Dict[str, Any]:
    """Search the datalake via /memory recall."""
    tags = []
    if req.asset_type:
        tags.append(req.asset_type)
    if req.domain:
        tags.append(req.domain)

    query = req.query
    if req.asset_type:
        query = f"{req.asset_type} {query}"

    params: Dict[str, Any] = {"q": query, "k": req.k}
    if tags:
        params["tags"] = ",".join(tags)

    data = await _memory_get("/recall", params)
    results = data.get("results", [])

    return {
        "query": req.query,
        "asset_type": req.asset_type,
        "result_count": len(results),
        "results": results,
    }


class PersonaQueryRequest(BaseModel):
    """Specify a query request with a persona and a result limit."""
    query: str
    persona: str = "margaret"
    k: int = 20


PERSONA_WEIGHTS: Dict[str, Dict[str, float]] = {
    "margaret": {
        "table_fidelity": 0.30, "equation_fidelity": 0.25,
        "section_alignment": 0.25, "content_coverage": 0.10, "ordering_yx": 0.10,
    },
    "jennifer": {
        "data_quality": 0.25, "table_fidelity": 0.25,
        "section_alignment": 0.20, "content_coverage": 0.15, "figure_fidelity": 0.15,
    },
    "brandon": {
        "content_coverage": 0.25, "section_alignment": 0.20, "table_fidelity": 0.20,
        "data_quality": 0.15, "ordering_yx": 0.10, "figure_fidelity": 0.10,
    },
    "paul": {
        "equation_fidelity": 0.30, "content_coverage": 0.25,
        "section_alignment": 0.20, "table_fidelity": 0.15, "ordering_yx": 0.10,
    },
    "noah": {
        "data_quality": 0.30, "content_coverage": 0.25,
        "table_fidelity": 0.20, "section_alignment": 0.15, "ordering_yx": 0.10,
    },
    "embry": {
        "content_coverage": 0.22, "section_alignment": 0.18, "table_fidelity": 0.16,
        "equation_fidelity": 0.14, "ordering_yx": 0.12, "figure_fidelity": 0.10,
        "data_quality": 0.08,
    },
}


@app.get("/api/datalake/personas")
async def list_personas() -> Dict[str, Any]:
    """Return a dictionary of personas with their corresponding weights."""
    return {"personas": PERSONA_WEIGHTS}


@app.post("/api/datalake/persona-query")
async def persona_query(req: PersonaQueryRequest) -> Dict[str, Any]:
    """Query the datalake with persona-weighted scoring."""
    weights = PERSONA_WEIGHTS.get(req.persona.lower())
    if not weights:
        raise HTTPException(400, f"Unknown persona: {req.persona}")

    params: Dict[str, Any] = {"q": req.query, "k": req.k, "tags": "pdf_assessment"}
    data = await _memory_get("/recall", params)
    results = data.get("results", [])

    scored: List[Dict[str, Any]] = []
    for r in results:
        meta = r.get("metadata", {}) or {}
        dimensions = meta.get("dimensions", {})
        if not dimensions:
            scored.append({**r, "persona_score": None})
            continue

        total_weight = 0
        weighted_sum = 0
        dim_scores: Dict[str, float] = {}
        for dim_key, w in weights.items():
            dim_data = dimensions.get(dim_key)
            if isinstance(dim_data, dict):
                s = dim_data.get("score")
                if isinstance(s, (int, float)) and dim_data.get("state") not in ("not_available", "unknown"):
                    weighted_sum += s * w
                    total_weight += w
                    dim_scores[dim_key] = s

        persona_score = weighted_sum / total_weight if total_weight > 0 else None
        scored.append({
            **r,
            "persona_score": round(persona_score, 4) if persona_score is not None else None,
            "persona_dimensions": dim_scores,
        })

    scored.sort(key=lambda x: x.get("persona_score") or 0, reverse=True)
    return {
        "query": req.query, "persona": req.persona, "weights": weights,
        "result_count": len(scored), "results": scored,
    }


# --- Corrections ---


class CorrectionApplyRequest(BaseModel):
    """Return a request to apply corrections to a text stem."""
    stem: str
    corrections: List[Dict[str, Any]]
    trigger_reextract: bool = False


@app.post("/api/datalake/corrections/{stem}/apply")
async def apply_corrections(stem: str, req: CorrectionApplyRequest) -> Dict[str, Any]:
    """Store correction via /memory learn."""
    lesson_text = f"Human correction for {stem}: {json.dumps(req.corrections[:5])}"
    result = await _memory_post("/learn", {
        "problem": f"correction_{stem}",
        "solution": lesson_text,
        "tags": ["correction", "human_review", stem[:30]],
    })
    _append_shadow("corrections.jsonl", {
        "stem": stem, "corrections": req.corrections[:5], "action": "correction",
    })
    return {
        "stem": stem,
        "stored": result.get("ok", False) if "error" not in result else False,
        "reextract_triggered": False,
    }


# --- Human Feedback (Nico Collaboration) ---

class FeedbackRequest(BaseModel):
    """Feedback request with reviewer, action, and optional dimensions."""
    stem: str
    reviewer: str = "nico"
    action: str = "note"  # note, reextract, escalate, approve, dismiss
    notes: str = ""
    dimensions: Optional[List[str]] = None
    priority: str = "normal"  # low, normal, high, critical


@app.post("/api/datalake/feedback")
async def submit_feedback(req: FeedbackRequest) -> Dict[str, Any]:
    """Store human feedback for a quarantined PDF via /memory learn."""
    import time as _time
    solution = json.dumps({
        "stem": req.stem, "reviewer": req.reviewer, "action": req.action,
        "notes": req.notes, "dimensions": req.dimensions,
        "priority": req.priority, "timestamp": _time.time(),
    })
    result = await _memory_post("/learn", {
        "problem": f"human_feedback_{req.stem}",
        "solution": solution,
        "tags": ["human_feedback", f"reviewer_{req.reviewer}", req.action, req.stem[:30]],
    })
    _append_shadow("feedback.jsonl", {
        "stem": req.stem, "feedback_action": req.action,
        "params": {"notes": req.notes, "dimensions": req.dimensions, "priority": req.priority},
        "action": "feedback",
    })
    # If action is reextract, also write the request file for the supervisor
    reextract_triggered = False
    if req.action == "reextract":
        reextract_dir = STATE_DIR / "reextract_requests"
        reextract_dir.mkdir(parents=True, exist_ok=True)
        (reextract_dir / f"{req.stem}.json").write_text(json.dumps({
            "stem": req.stem,
            "reason": req.notes or f"Re-extraction requested by {req.reviewer}",
            "dimensions": req.dimensions, "priority": req.priority,
            "reviewer": req.reviewer,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }))
        reextract_triggered = True
    return {
        "stem": req.stem,
        "stored": "error" not in result,
        "reextract_triggered": reextract_triggered,
    }


@app.get("/api/datalake/feedback/{stem}")
async def get_feedback(stem: str) -> Dict[str, Any]:
    """Get all human feedback for a specific PDF stem from /memory."""
    data = await _memory_get("/recall", {"q": f"human_feedback_{stem}", "k": 20, "tags": "human_feedback"})
    results = data.get("results", [])
    feedback = []
    for r in results:
        sol_text = r.get("solution") or r.get("text") or ""
        try:
            sol = json.loads(sol_text)
            if sol.get("stem") == stem:
                feedback.append(sol)
        except (json.JSONDecodeError, TypeError):
            pass
    feedback.sort(key=lambda f: f.get("timestamp", 0), reverse=True)
    return {"stem": stem, "feedback": feedback}


@app.get("/api/datalake/feedback")
async def list_recent_feedback(limit: int = Query(50, ge=1, le=200)) -> Dict[str, Any]:
    """List recent human feedback across all PDFs."""
    data = await _memory_get("/recall", {"q": "human_feedback", "k": limit, "tags": "human_feedback"})
    results = data.get("results", [])
    feedback = []
    for r in results:
        sol_text = r.get("solution") or r.get("text") or ""
        try:
            sol = json.loads(sol_text)
            feedback.append(sol)
        except (json.JSONDecodeError, TypeError):
            pass
    feedback.sort(key=lambda f: f.get("timestamp", 0), reverse=True)
    return {"feedback": feedback[:limit], "total": len(feedback)}


@app.get("/api/health")
def health():
    """Return health status and memory service URL in a JSON response."""
    return {"status": "ok", "memory_service_url": MEMORY_SERVICE_URL}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8004, log_level="info")
