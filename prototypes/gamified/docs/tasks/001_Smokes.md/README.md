# Gamified Orchestrator — Smokes + Contracts

Goal: Make the prompt‑first orchestrator reliable via fast, deterministic smokes and strict contracts. All changes must keep these green.

---

## Contracts (must hold for every run)

1) Instance Prompt Contract
- Sections required:
  - "## Original Prompt" (verbatim copy)
  - "## Context" with: Codebase, Variant, Output Dir
  - "## Gamified Rules (Summary)" with epsilon, window, max iters
  - "## Execute Exactly (non-interactive)" — one shell block with the variant_agent command including: `--approach`, `--bench`, `--baseline`, `--variants`, `--out-dir`, `--epsilon`, `--window`, `--max-iters`, `--run-id`, `--prompt-file`
  - "## Monitoring" — web logs URL and API links (/scoreboard, /episodes, /logs)

2) Variant Agent Artifacts
- `iter_XX.json` shape:
  - `approach: str`
  - `correctness: {S: bool, M: bool, L: bool}`
  - `timings_ms: {S: number, M: number, L: number}` (numbers may be `inf` on failure)
  - `robust: bool`
  - `loc: int`
- `iter_XX_summary.json` shape:
  - `iter: int`, `score: number`, `metrics: <as above>`
  - `stderr_lines: int`, `stdout_lines: int`
  - `mutation: {applied: bool, ...}` (freeform extras allowed)
- `done.json` shape:
  - `ok: bool`, `variant: str`, `best_score: number|null`, `best_iter: int|null`

3) Scorecard JSON
- `scales: ["S","M","L"]`
- `approaches: { <variant>: { correctness, timings_ms, robust, loc, speed_points, brevity_points, total_points } }`
- `winner: str|null` (must be a key in `approaches` when not null)

4) Ingest API (optional; when backend is up)
- `POST /ingest/log` and `POST /ingest/episode` accept the payloads used by the variant agent and orchestrator.
- `GET /scoreboard?run_id=...` returns last status rows.

---

## Smokes (≤ 90s total)

Smoke 01 — Wait‑Here (2 variants, sequential)
- Run:
  - `python scripts/gamified.py --codebase . --prompt-file prototypes/gamified/docs/prompt_multiplication_with_tasks.md --instances 2 --sequential --instance-timeout-s 120 --idle-timeout-s 120 --no-autostart-backend --no-start-dashboard`
- Assert:
  - Two instance dirs exist under `workspace/runs/<run_id>/instances/`
  - Each has `prompt.md` satisfying the Instance Prompt Contract (section headers present)
  - Each has `iter_01.json` and `done.json` with valid schema
  - Scorecard exists at `workspace/runs/<run_id>/scorecard.json` and is valid; `winner` is one of the two variants

Smoke 02 — Emit → Aggregate (non‑waiting)
- Run:
  - `python scripts/gamified.py --codebase . --prompt-file prototypes/gamified/docs/prompt_multiplication_with_tasks.md --instances 2 --emit-only --no-autostart-backend --no-start-dashboard`
  - Copy synthetic `iter_01.json` fixtures into each instance dir
  - `python scripts/gamified.py --codebase . --run-id <run_id> --aggregate-only --no-autostart-backend --no-start-dashboard`
- Assert: Scorecard written and valid; `winner` ∈ variants

Smoke 03 — Timeout Handling (unit‑level)
- Force a slow variant (or use a dummy command) and run with `--instance-timeout-s 5`; assert a `timed_out.txt` appears and the orchestrator aggregates remaining outputs.

Smoke 04 — API Optional (skipped if backend down)
- If backend is up: `GET /scoreboard?run_id=<run_id>` returns items; else skip.

---

## Runbook (quick)
- Prefer wait‑here with `--instance-timeout-s` and `--idle-timeout-s` when the harness allows.
- Use `--emit-only` → launch → `--aggregate-only` when long parent lifetimes are risky.
- Monitor via dashboard or `/proto/dashboard` and `/scoreboard`.

