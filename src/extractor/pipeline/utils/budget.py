from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional


def _ledger_path() -> Path:
    return Path("data/results/pipeline/budget/ledger.json")


def _load_ledger() -> dict:
    p = _ledger_path()
    if not p.exists():
        return {"days": {}}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {"days": {}}


def _save_ledger(data: dict) -> None:
    p = _ledger_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2))


def check_and_update_budget(stage: str, num_items: int, est_tokens_per_item: Optional[int] = None) -> None:
    """
    Basic daily budget gate. Estimates tokens by item count when usage is unknown.
    Env:
      LLM_DAILY_TOKEN_BUDGET=int
      LLM_STAGE_ALLOCATION_JSON=json string (optional per-stage % caps)
      LLM_EST_TOKENS_PER_ITEM=int (default 150)
      LLM_BUDGET_DRY_RUN=1 (log only)
      LLM_BUDGET_FORCE=1 (skip checks)
    """
    if os.getenv("LLM_BUDGET_FORCE", "0") in ("1", "true", "yes"):
        return
    budget = int(os.getenv("LLM_DAILY_TOKEN_BUDGET", "0") or 0)
    if budget <= 0:
        return
    est = est_tokens_per_item or int(os.getenv("LLM_EST_TOKENS_PER_ITEM", "150"))
    today = datetime.utcnow().strftime("%Y-%m-%d")
    data = _load_ledger()
    day = data.setdefault("days", {}).setdefault(today, {"total": 0, "stages": {}})
    # soft stage cap
    cap_map = {}
    try:
        cap_map = json.loads(os.getenv("LLM_STAGE_ALLOCATION_JSON", "{}"))
    except Exception:
        cap_map = {}
    stage_cap_pct = float(cap_map.get(stage, 1.0)) if isinstance(cap_map, dict) else 1.0
    stage_cap = int(budget * stage_cap_pct)

    predicted = day["total"] + (num_items * est)
    if predicted > budget or (day["stages"].get(stage, 0) + num_items * est) > stage_cap:
        # pause low-priority stages by default
        msg = {
            "budget_status": "paused_low_priority",
            "today_total": day["total"],
            "predicted": predicted,
            "budget": budget,
            "stage": stage,
            "est_tokens": num_items * est,
        }
        (_ledger_path().parent / "pause_log.json").write_text(json.dumps(msg, indent=2))
        if os.getenv("LLM_BUDGET_DRY_RUN", "0") in ("1", "true", "yes"):
            return
        raise SystemExit(f"Budget pause for stage {stage}: predicted tokens exceed budget")
    # update ledger
    day["total"] = predicted
    day["stages"][stage] = day["stages"].get(stage, 0) + num_items * est
    _save_ledger(data)

