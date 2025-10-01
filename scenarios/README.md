# Extractor Scenarios (Live)

Live, operator-invoked scenarios for the UI and pipeline. These replace legacy
smokes with environment-gated checks, CDP screenshots, and concise artifacts.

Like the LiteLLM project, we provide:
- An orchestrator (`scenarios/run_all.py`) with colored output
- Small, focused scenarios that SKIP cleanly when a prerequisite is missing
- A “run all” pipeline feature for developer workflows

Scenarios do not start long‑lived servers. Use VS Code tasks or your own shell
to run Vite preview/dev and the backend.

## How to Run

1) Export endpoints
- UI: `BASE_URL=http://127.0.0.1:8080/main`
- CDP (choose one)
  - `BROWSERLESS_WS=ws://127.0.0.1:9222/devtools/browser`
  - `BROWSERLESS_DISCOVERY_URL=http://127.0.0.1:3000/json/version`
- Preview-only checks: `PREVIEW=1`

2) Run
- All scenarios: `python scenarios/run_all.py`
- Make target: `make run-scenarios`
- Filter subset: `SCENARIOS_FILTER=ux_ console pipeline python scenarios/run_all.py`
- Stop on first failure: `SCENARIOS_STOP_ON_FIRST_FAILURE=1 python scenarios/run_all.py`

Artifacts live under `scripts/artifacts/YYYY-MM-DD/<sha-or-local>/` with subfolders:
- `screenshots/` — per-scenario PNGs
- `logs/` — scenario logs
- `json/` — summaries like `scenarios_summary.json` and `pipeline_all_*.json`

## Scenario Index

UI (CDP)
- `ux_cdp_health.mjs` — mount/overlay/console/pageerror gate; screenshot+log.
- `ux/console_errors.mjs` — hard error gate after ready; screenshot+log.
- `ux/no_preview_api_requests.mjs` — asserts no `/api/*` after ready (preview); screenshot.
- `ux/core_interactions.mjs` — draw/duplicate/delete/label; toolbar not occluding canvas; multiple screenshots.
- `ux/thumbnails_modes.mjs` — left rail and bottom filmstrip; screenshots + metrics.
- `ux/thumbnails_virtualized.mjs` — ensures list grows on scroll; screenshots.
- `ux/zoom_tooltip.mjs` — tooltip on hover; screenshot + size/position check.
- `ux/zoom_fit_pan.mjs` — fit + pan gesture; screenshot.
- `ux/toolbar_hierarchy.mjs` — toolbar present and not overlapping canvas; screenshot.
- `ux/selection_handles_resize.mjs` — selection handles present; small resize; screenshot.
- `ux/inspector_pane_present.mjs` — inspector exists; screenshot.
- `ux/requirements_pane_dom.mjs` — requirements pane DOM present; screenshot.
- `ux/keyboard_core.mjs` — N to draw; Delete to remove; screenshot + counts.
- `ux/a11y_focus_escape.mjs` — dialog Escape returns focus; before/after screenshots.

Pipeline (Live, non-deterministic)
- `pipeline/api_health.py` — probes `/api/health/llm` and prints JSON; SKIP if unreachable.
- `pipeline/step_10_export_flattened.py` — checks latest Step 10 flattened JSON; SKIP if none.
- `pipeline/step_11_graph_db.py` — basic Arango presence check; SKIP if not configured.
- `pipeline/run_pipeline_all.py` — runs full pipeline driver and captures a log.

## Notes & Conventions
- Scenarios must SKIP rather than hang if a service/endpoint is missing.
- Always capture at least one screenshot for UX scenarios and a small log.
- Prefer small JSON snippets in logs; avoid dumping huge payloads.
 
### Environment
- `BASE_URL` — application base (default http://localhost:5173)
- `BROWSERLESS_WS` — explicit WS endpoint (preferred); else `BROWSERLESS_DISCOVERY_URL`
- `SCENARIOS_FILTER` — comma-separated includes; prefix with `!` to exclude
- `SCENARIOS_STOP_ON_FIRST_FAILURE` — `1` to fail fast
- `SCENARIOS_ARTIFACT_ROOT` — artifacts root (default `scripts/artifacts`)
- `SCENARIOS_MAX_AGE_DAYS`, `SCENARIOS_MAX_ARTIFACTS` — optional pruning (default off)
- `SCENARIO_ROUTES` — comma-separated (default `/main,/classic`)
- `SCENARIO_VIEWPORTS` — optional `WxH` list (default `1366x900`)
- `SANITIZE_SCREENSHOTS` — `1` to obfuscate text/images in screenshots (opt-in)

Chrome: recommend Chrome 120+ (or Browserless at equivalent level) for stable headless/CDP behavior.
