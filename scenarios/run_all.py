#!/usr/bin/env python3
"""Run Extractor live scenarios with colored output and summary.

This mirrors the LiteLLM `scenarios/run_all.py` pattern and is the entrypoint
for live (non-deterministic) checks. Deterministic tests remain under `tests/`.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple
import json
import time
import pathlib
import shutil

ROOT = Path(__file__).resolve().parents[1]
SCEN_DIR = ROOT / "scenarios"
PYTHON = sys.executable

# Each scenario is a human-friendly name and a command list.
SCENARIOS: List[Tuple[str, list[str]]] = [
    ("ux_cdp_health", ["node", str(SCEN_DIR / "ux_cdp_health.mjs")]),
    ("ux_console_errors", ["node", str(SCEN_DIR / "ux" / "console_errors.mjs")]),
    ("ux_no_preview_api", ["node", str(SCEN_DIR / "ux" / "no_preview_api_requests.mjs")]),
    ("ux_core_interactions", ["node", str(SCEN_DIR / "ux" / "core_interactions.mjs")]),
    ("ux_thumbnails_modes", ["node", str(SCEN_DIR / "ux" / "thumbnails_modes.mjs")]),
    ("ux_thumbnails_virtualized", ["node", str(SCEN_DIR / "ux" / "thumbnails_virtualized.mjs")]),
    ("ux_zoom_tooltip", ["node", str(SCEN_DIR / "ux" / "zoom_tooltip.mjs")]),
    ("ux_zoom_fit_pan", ["node", str(SCEN_DIR / "ux" / "zoom_fit_pan.mjs")]),
    ("ux_toolbar_hierarchy", ["node", str(SCEN_DIR / "ux" / "toolbar_hierarchy.mjs")]),
    (
        "ux_selection_handles_resize",
        ["node", str(SCEN_DIR / "ux" / "selection_handles_resize.mjs")],
    ),
    ("ux_inspector_pane_present", ["node", str(SCEN_DIR / "ux" / "inspector_pane_present.mjs")]),
    ("ux_requirements_pane_dom", ["node", str(SCEN_DIR / "ux" / "requirements_pane_dom.mjs")]),
    ("ux_keyboard_core", ["node", str(SCEN_DIR / "ux" / "keyboard_core.mjs")]),
    ("ux_a11y_focus_escape", ["node", str(SCEN_DIR / "ux" / "a11y_focus_escape.mjs")]),
    ("pipeline_api_health", [sys.executable, str(SCEN_DIR / "pipeline" / "api_health.py")]),
    (
        "pipeline_step_10_export_flattened",
        [sys.executable, str(SCEN_DIR / "pipeline" / "step_10_export_flattened.py")],
    ),
    (
        "pipeline_check_stage10_flattened",
        [sys.executable, str(SCEN_DIR / "pipeline" / "check_stage10_flattened.py")],
    ),
    (
        "pipeline_step_11_graph_db",
        [sys.executable, str(SCEN_DIR / "pipeline" / "step_11_graph_db.py")],
    ),
    (
        "pipeline_step_eval_step10",
        [sys.executable, str(SCEN_DIR / "pipeline" / "step_eval_agent.py")],
    ),
    (
        "pipeline_step_eval_step05",
        [sys.executable, str(SCEN_DIR / "pipeline" / "step05_eval_agent.py")],
    ),
    (
        "pipeline_step_eval_step06",
        [sys.executable, str(SCEN_DIR / "pipeline" / "step06_eval_agent.py")],
    ),
    (
        "pipeline_step_eval_step07",
        [sys.executable, str(SCEN_DIR / "pipeline" / "step07_eval_agent.py")],
    ),
    (
        "pipeline_step_eval_step09",
        [sys.executable, str(SCEN_DIR / "pipeline" / "step09_eval_agent.py")],
    ),
    (
        "pipeline_step_eval_step14",
        [sys.executable, str(SCEN_DIR / "pipeline" / "step14_eval_agent.py")],
    ),
    ("pipeline_run_all", [sys.executable, str(SCEN_DIR / "pipeline" / "run_pipeline_all.py")]),
    ("pipeline_pytest_smokes", [sys.executable, str(SCEN_DIR / "pipeline" / "pytest_smokes.py")]),
]

RESET = "\033[0m"
BLUE = "\033[1;34m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"


def _filtered_scenarios(all_scenarios: List[Tuple[str, list[str]]]) -> List[Tuple[str, list[str]]]:
    flt = os.getenv("SCENARIOS_FILTER", "").strip()
    if not flt:
        return all_scenarios
    keys = [k.strip() for k in flt.split(",") if k.strip()]
    if not keys:
        return all_scenarios
    out: List[Tuple[str, list[str]]] = []
    for name, cmd in all_scenarios:
        if any(k.lower() in name.lower() for k in keys):
            out.append((name, cmd))
    return out


def main() -> None:
    env = os.environ.copy()
    artifact_root = pathlib.Path(env.get("SCENARIOS_ARTIFACT_ROOT", "scripts/artifacts"))
    date_dir = time.strftime("%Y-%m-%d")
    artifact_dir = artifact_root / date_dir / env.get("GITHUB_SHA", "local") / "json"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    # Optional pruning knobs
    try:
        max_age_days = int(env.get("SCENARIOS_MAX_AGE_DAYS", "0") or "0")
        max_entries = int(env.get("SCENARIOS_MAX_ARTIFACTS", "0") or "0")
        root_for_prune = artifact_root / date_dir
        if root_for_prune.parent.exists():
            # prune by count
            if max_entries > 0:
                entries = sorted(
                    (p for p in root_for_prune.parent.iterdir() if p.is_dir()),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
                for p in entries[max_entries:]:
                    shutil.rmtree(p, ignore_errors=True)
            # prune by age
            if max_age_days > 0:
                cutoff = time.time() - max_age_days * 86400
                for p in root_for_prune.parent.iterdir():
                    try:
                        if p.stat().st_mtime < cutoff:
                            shutil.rmtree(p, ignore_errors=True)
                    except Exception:
                        pass
    except Exception:
        pass
    base = env.get("BASE_URL", "").strip()
    if not base:
        print(f"{YELLOW}Note: BASE_URL is not set. Defaulting to http://127.0.0.1:8080/main{RESET}")
        env["BASE_URL"] = "http://127.0.0.1:8080/main"

    # Prefer explicit websocket endpoint, otherwise allow discovery URL.
    ws = env.get("BROWSERLESS_WS", "").strip()
    disc = env.get("BROWSERLESS_DISCOVERY_URL", "").strip()
    if not ws and not disc:
        # Offer a helpful default for local headless Chrome
        env.setdefault("BROWSERLESS_WS", "ws://127.0.0.1:9222/devtools/browser")

    stop_on_fail = env.get("SCENARIOS_STOP_ON_FIRST_FAILURE", "").lower() in {"1", "true", "yes"}
    plan = _filtered_scenarios(SCENARIOS)
    results: list[tuple[str, bool, int]] = []
    json_results: list[dict] = []
    print(f"{YELLOW}Running {len(plan)} scenario(s)...{RESET}")
    t0 = time.time()
    for name, cmd in plan:
        print(f"{BLUE}▶ {name}{RESET}")
        proc = subprocess.run(cmd, env=env)
        ok = proc.returncode == 0
        results.append((name, ok, proc.returncode))
        json_results.append(
            {
                "name": name,
                "status": (
                    "pass"
                    if ok
                    else ("skip" if proc.returncode == 0 and "SKIP" in name.upper() else "fail")
                ),
                "exit_code": proc.returncode,
            }
        )
        if ok:
            print(f"{GREEN}✓ {name} succeeded{RESET}\n")
        else:
            print(f"{RED}✗ {name} failed (exit code {proc.returncode}){RESET}\n")
            if stop_on_fail:
                break

    passed = [n for n, ok, _ in results if ok]
    failed = [(n, rc) for n, ok, rc in results if not ok]

    print("\n" + "=" * 60)
    print("Scenario Summary")
    print("=" * 60)
    for n in passed:
        print(f"{GREEN}  ✓ {n}{RESET}")
    for n, rc in failed:
        print(f"{RED}  ✗ {n} (code {rc}){RESET}")

    # Write JSON summary
    summary = {
        "elapsed_sec": round(time.time() - t0, 3),
        "results": [
            {"name": n, "status": ("pass" if ok else "fail"), "exit_code": rc}
            for n, ok, rc in results
        ],
    }
    try:
        (artifact_dir / "scenarios_summary.json").write_text(json.dumps(summary, indent=2))
    except Exception:
        pass

    if not failed:
        print(f"\n{GREEN}All scenarios succeeded!{RESET}")
        sys.exit(0)
    else:
        print(f"\n{YELLOW}{len(failed)} scenario(s) failed. See logs above.{RESET}")
        sys.exit(1)


if __name__ == "__main__":
    main()
