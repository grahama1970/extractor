"""Per-session Chutes API cost tracker.

Tracks all LLM calls routed through the SciLLM router and writes a
cost summary to the pipeline output directory.

Usage:
    from extractor.pipeline.utils.chutes_cost_tracker import cost_tracker

    # Automatic: scillm_router.py calls cost_tracker.record() on each completion
    # Manual summary:
    cost_tracker.summary()          # → dict with totals
    cost_tracker.write_report(path) # → writes JSON to disk
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


class ChutesCostTracker:
    """Thread-safe accumulator for Chutes API call metrics."""

    def __init__(self) -> None:
    """Initialize instance with thread lock, call log, and optional budget limit."""
        self._lock = threading.Lock()
        self._calls: List[Dict[str, Any]] = []
        self._session_start = time.monotonic()
        self._budget_limit: Optional[int] = None
        budget_env = os.environ.get("CHUTES_CALL_BUDGET", "").strip()
        if budget_env.isdigit() and int(budget_env) > 0:
            self._budget_limit = int(budget_env)

    def record(
        self,
        *,
        model: str,
        route: str,
        tokens_in: int = 0,
        tokens_out: int = 0,
        latency_ms: float = 0,
        success: bool = True,
        fallback: bool = False,
    ) -> None:
        """Record a single LLM API call."""
        with self._lock:
            self._calls.append({
                "model": model,
                "route": route,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "latency_ms": round(latency_ms, 1),
                "success": success,
                "fallback": fallback,
                "ts": time.time(),
            })

    @property
    def call_count(self) -> int:
    """Perform call count operation."""
        with self._lock:
            return len(self._calls)

    @property
    def over_budget(self) -> bool:
    """Check if call count exceeds budget limit."""
        if self._budget_limit is None:
            return False
        return self.call_count >= self._budget_limit

    def summary(self) -> Dict[str, Any]:
        """Return aggregated cost summary."""
        with self._lock:
            calls = list(self._calls)

        by_model: Dict[str, Dict[str, Any]] = {}
        by_route: Dict[str, int] = {}
        total_in = 0
        total_out = 0
        failures = 0
        fallbacks = 0

        for c in calls:
            model = c["model"]
            route = c["route"]

            if model not in by_model:
                by_model[model] = {"calls": 0, "tokens_in": 0, "tokens_out": 0, "failures": 0}
            by_model[model]["calls"] += 1
            by_model[model]["tokens_in"] += c["tokens_in"]
            by_model[model]["tokens_out"] += c["tokens_out"]
            if not c["success"]:
                by_model[model]["failures"] += 1

            by_route[route] = by_route.get(route, 0) + 1
            total_in += c["tokens_in"]
            total_out += c["tokens_out"]
            if not c["success"]:
                failures += 1
            if c["fallback"]:
                fallbacks += 1

        return {
            "total_calls": len(calls),
            "total_tokens_in": total_in,
            "total_tokens_out": total_out,
            "total_tokens": total_in + total_out,
            "failures": failures,
            "fallbacks": fallbacks,
            "budget_limit": self._budget_limit,
            "over_budget": self.over_budget,
            "elapsed_seconds": round(time.monotonic() - self._session_start, 1),
            "by_model": by_model,
            "by_route": by_route,
        }

    def write_report(self, path: Path) -> None:
        """Write cost summary JSON to disk."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.summary(), indent=2) + "\n")

    def reset(self) -> None:
    """Reset call counter and session timer."""
        with self._lock:
            self._calls.clear()
            self._session_start = time.monotonic()


# Module-level singleton
cost_tracker = ChutesCostTracker()
