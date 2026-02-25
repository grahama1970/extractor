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
"""Datalake API gateway — proxies /memory HTTP service for the visual review UI.

Exposes stats, verdicts, convergence, search, and persona-query endpoints.
All queries go through the /memory HTTP API (port 8601) — no bespoke ArangoDB
connections per CLAUDE.md rules.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
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
REPORTS_DIR = Path(
    os.environ.get(
        "REPORTS_DIR",
        "/home/graham/workspace/experiments/pi-mono/.pi/skills/review-pdf/reports",
    )
)
CONVERGENCE_LOG = Path(
    os.environ.get(
        "CONVERGENCE_LOG",
        "/home/graham/workspace/experiments/pi-mono/.pi/skills/learn-datalake/state/memory_convergence_log.jsonl",
    )
)
STATE_DIR = Path(
    os.environ.get(
        "STATE_DIR",
        "/home/graham/workspace/experiments/pi-mono/.pi/skills/learn-datalake/state",
    )
)


# --- Helpers ---


async def _memory_recall(query: str, k: int = 20, tags: Optional[List[str]] = None) -> Dict[str, Any]:
    """Call /memory recall via HTTP."""
    params: Dict[str, Any] = {"q": query, "k": k}
    if tags:
        params["tags"] = ",".join(tags)
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.get(f"{MEMORY_SERVICE_URL}/recall", params=params)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            return {"ok": False, "error": str(e), "results": []}


def _load_json(path: Path) -> Optional[Any]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def _scan_all_reports() -> List[Dict[str, Any]]:
    """Scan all per-doc reports across all report runs."""
    reports: List[Dict[str, Any]] = []
    if not REPORTS_DIR.is_dir():
        return reports
    for run_dir in sorted(REPORTS_DIR.iterdir()):
        per_doc = run_dir / "per_doc"
        if not per_doc.is_dir():
            continue
        for f in per_doc.glob("*.json"):
            data = _load_json(f)
            if data and "overall" in data:
                reports.append(data)
    return reports


def _latest_reports_by_stem() -> Dict[str, Dict[str, Any]]:
    """Get latest report per stem (last run wins)."""
    index: Dict[str, Dict[str, Any]] = {}
    for report in _scan_all_reports():
        stem = report.get("doc_id", "")
        if stem:
            index[stem] = report
    return index


# --- Endpoints ---


@app.get("/api/datalake/stats")
async def datalake_stats() -> Dict[str, Any]:
    """Aggregate statistics about the datalake."""
    reports = _latest_reports_by_stem()

    # Domain distribution
    domains: Dict[str, int] = {}
    grades: Dict[str, int] = {}
    scores: List[float] = []
    verdicts: Dict[str, int] = {"PASS": 0, "WARN": 0, "FAIL": 0}

    for stem, r in reports.items():
        domain = r.get("domain", "unknown")
        domains[domain] = domains.get(domain, 0) + 1

        overall = r.get("overall", {})
        grade = overall.get("grade", "?")
        grades[grade] = grades.get(grade, 0) + 1

        verdict = overall.get("verdict")
        if verdict in verdicts:
            verdicts[verdict] += 1

        score = overall.get("score")
        if isinstance(score, (int, float)):
            scores.append(score)

    avg_score = sum(scores) / len(scores) if scores else 0

    # Score histogram (10 buckets)
    histogram = [0] * 10
    for s in scores:
        bucket = min(9, int(s * 10))
        histogram[bucket] += 1

    return {
        "total_docs": len(reports),
        "avg_score": round(avg_score, 4),
        "verdicts": verdicts,
        "grades": grades,
        "domains": domains,
        "score_histogram": histogram,
    }


@app.get("/api/datalake/verdicts")
async def datalake_verdicts() -> Dict[str, Any]:
    """Verdict breakdown with per-dimension averages."""
    reports = _latest_reports_by_stem()

    by_verdict: Dict[str, List[Dict]] = {"PASS": [], "WARN": [], "FAIL": []}
    for r in reports.values():
        verdict = r.get("overall", {}).get("verdict")
        if verdict in by_verdict:
            by_verdict[verdict].append(r)

    result: Dict[str, Any] = {}
    for verdict, rlist in by_verdict.items():
        dim_sums: Dict[str, float] = {}
        dim_counts: Dict[str, int] = {}
        for r in rlist:
            for dim_key, dim_val in r.get("dimensions", {}).items():
                if isinstance(dim_val, dict) and dim_val.get("state") not in ("not_available", "unknown"):
                    score = dim_val.get("score", 0)
                    dim_sums[dim_key] = dim_sums.get(dim_key, 0) + score
                    dim_counts[dim_key] = dim_counts.get(dim_key, 0) + 1

        dim_avgs = {k: round(dim_sums[k] / dim_counts[k], 4) for k in dim_sums if dim_counts.get(k, 0) > 0}
        result[verdict] = {
            "count": len(rlist),
            "dimension_averages": dim_avgs,
        }

    return result


@app.get("/api/datalake/convergence")
async def datalake_convergence(limit: int = Query(100, ge=1, le=1000)) -> Dict[str, Any]:
    """Time-series convergence data from the convergence log."""
    entries: List[Dict[str, Any]] = []
    if CONVERGENCE_LOG.exists():
        for line in CONVERGENCE_LOG.read_text().strip().split("\n"):
            if not line.strip():
                continue
            try:
                entries.append(json.loads(line))
            except Exception:
                pass

    # Take last N entries
    entries = entries[-limit:]

    # Also read supervisor state
    sup_state = _load_json(STATE_DIR / "watchdogs" / "supervisor_corpus.json")

    return {
        "entries": entries,
        "total_entries": len(entries),
        "supervisor_state": sup_state,
    }


class SearchRequest(BaseModel):
    query: str
    asset_type: Optional[str] = None  # table, text, figure, section
    k: int = 20
    domain: Optional[str] = None


@app.post("/api/datalake/search")
async def datalake_search(req: SearchRequest) -> Dict[str, Any]:
    """Search the datalake via /memory recall with optional asset_type filter."""
    tags = []
    if req.asset_type:
        tags.append(req.asset_type)
    if req.domain:
        tags.append(req.domain)

    # Build query with asset type hint
    query = req.query
    if req.asset_type:
        query = f"{req.asset_type} {query}"

    data = await _memory_recall(query, k=req.k, tags=tags or None)
    results = data.get("results", [])

    return {
        "query": req.query,
        "asset_type": req.asset_type,
        "result_count": len(results),
        "results": results,
    }


class PersonaQueryRequest(BaseModel):
    query: str
    persona: str = "margaret"  # margaret, jennifer, brandon, paul, noah, embry
    k: int = 20


# Persona weights (ported from annealing.py)
PERSONA_WEIGHTS: Dict[str, Dict[str, float]] = {
    "margaret": {
        "table_fidelity": 0.30,
        "equation_fidelity": 0.25,
        "section_alignment": 0.25,
        "content_coverage": 0.10,
        "ordering_yx": 0.10,
    },
    "jennifer": {
        "data_quality": 0.25,
        "table_fidelity": 0.25,
        "section_alignment": 0.20,
        "content_coverage": 0.15,
        "figure_fidelity": 0.15,
    },
    "brandon": {
        "content_coverage": 0.25,
        "section_alignment": 0.20,
        "table_fidelity": 0.20,
        "data_quality": 0.15,
        "ordering_yx": 0.10,
        "figure_fidelity": 0.10,
    },
    "paul": {
        "equation_fidelity": 0.30,
        "content_coverage": 0.25,
        "section_alignment": 0.20,
        "table_fidelity": 0.15,
        "ordering_yx": 0.10,
    },
    "noah": {
        "data_quality": 0.30,
        "content_coverage": 0.25,
        "table_fidelity": 0.20,
        "section_alignment": 0.15,
        "ordering_yx": 0.10,
    },
    "embry": {
        "content_coverage": 0.22,
        "section_alignment": 0.18,
        "table_fidelity": 0.16,
        "equation_fidelity": 0.14,
        "ordering_yx": 0.12,
        "figure_fidelity": 0.10,
        "data_quality": 0.08,
    },
}


@app.get("/api/datalake/personas")
async def list_personas() -> Dict[str, Any]:
    """List available personas and their dimension weights."""
    return {"personas": PERSONA_WEIGHTS}


@app.post("/api/datalake/persona-query")
async def persona_query(req: PersonaQueryRequest) -> Dict[str, Any]:
    """Query the datalake with persona-weighted scoring."""
    weights = PERSONA_WEIGHTS.get(req.persona.lower())
    if not weights:
        raise HTTPException(400, f"Unknown persona: {req.persona}")

    data = await _memory_recall(req.query, k=req.k, tags=["pdf_assessment"])
    results = data.get("results", [])

    # Re-score results by persona weights
    scored: List[Dict[str, Any]] = []
    for r in results:
        meta = r.get("metadata", {}) or {}
        dimensions = meta.get("dimensions", {})
        if not dimensions:
            scored.append({**r, "persona_score": None})
            continue

        # Compute weighted score
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

    # Sort by persona score (descending)
    scored.sort(key=lambda x: x.get("persona_score") or 0, reverse=True)

    return {
        "query": req.query,
        "persona": req.persona,
        "weights": weights,
        "result_count": len(scored),
        "results": scored,
    }


class CorrectionApplyRequest(BaseModel):
    stem: str
    corrections: List[Dict[str, Any]]
    trigger_reextract: bool = False


@app.post("/api/datalake/corrections/{stem}/apply")
async def apply_corrections(stem: str, req: CorrectionApplyRequest) -> Dict[str, Any]:
    """Store correction as /memory lesson and optionally trigger re-extraction."""
    # Store to /memory via recall (learn endpoint)
    lesson_text = f"Human correction for {stem}: {json.dumps(req.corrections[:5])}"
    tags = ["correction", "human_review", stem[:30]]

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(
                f"{MEMORY_SERVICE_URL}/learn",
                json={"text": lesson_text, "tags": tags},
            )
            resp.raise_for_status()
            learn_result = resp.json()
        except httpx.HTTPError as e:
            learn_result = {"ok": False, "error": str(e)}

    return {
        "stem": stem,
        "stored": learn_result.get("ok", False),
        "reextract_triggered": False,  # Placeholder for Phase 5
    }


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "memory_service_url": MEMORY_SERVICE_URL,
        "reports_dir_exists": REPORTS_DIR.is_dir(),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8004, log_level="info")
