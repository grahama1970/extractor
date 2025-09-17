# Smokes — Rebuild Verification (Gamified)

Purpose: validate that a freshly (re)created `prototypes/gamified` project is complete, runnable, and observable. These smokes are fast, deterministic, and gate further work.

---

## Preflight

- Python 3.10+
- Node ≥ 18 (for dashboard smoke; optional)
- Backend optional: if FastAPI server isn’t running, API smokes are skipped
- Shell at repo root: `/home/graham/workspace/experiments/extractor`

---

## Contract Surfaces (must exist after rebuild)

- Files/directories
  - `prototypes/gamified/README.md`
  - `prototypes/gamified/DEPRECATED.md`
  - `prototypes/gamified/TODO.md`
  - `prototypes/gamified/rules/score_v1.json`
  - `prototypes/gamified/docs/prompt_multiplication_with_tasks.md`
  - `prototypes/gamified/docs/tasks/001_Smokes.md/README.md`
  - `prototypes/gamified/docs/tasks/002_Smokes_Rebuild.md` (this file)
  - `prototypes/gamified/dashboard/` (if present: `package.json`, `src/App.tsx`, `vite.config.ts`)
- Orchestrator CLI
  - `python scripts/gamified.py --help` prints the `run` and `status` commands
- Instance Prompt Contract, Variant Agent Outputs, and Scorecard JSON adhere to the shapes defined in 001_Smokes.md

---

## Smoke A — Filesystem Skeleton

Goal: assert the rebuilt project tree is present and complete.

Run:
```
ls -la prototypes/gamified && ls -la prototypes/gamified/docs && ls -la prototypes/gamified/rules && test -f prototypes/gamified/docs/prompt_multiplication_with_tasks.md && rg -n "Prompt‑Driven|Quick Start|How It Works" prototypes/gamified/README.md
```

Pass when:
- All listed files exist; README contains Quick Start + How It Works sections

---

## Smoke B — Emit → Aggregate (Non‑waiting)

Goal: verify the orchestration rebuild can emit per‑instance prompts and aggregate a scorecard from synthetic outputs.

Run:
```
python scripts/gamified.py   --codebase .   --prompt-file prototypes/gamified/docs/prompt_multiplication_with_tasks.md   --instances 2   --emit-only   --no-autostart-backend --no-start-dashboard

RUN_ID=$(ls -1d workspace/runs/*/instances | tail -n1 | xargs dirname | xargs basename)
INST_ROOT=workspace/runs/$RUN_ID/instances

# Synthesize minimal iter_01.json for two variants
for d in "$INST_ROOT"/codex_*_*; do
  cat > "$d/iter_01.json" <<EOF
{ "approach": "$(basename "$d" | cut -d_ -f3)",
  "correctness": {"S": true, "M": false, "L": false},
  "timings_ms": {"S": 0.05, "M": 1e9, "L": 1e9},
  "robust": true, "loc": 10 }
EOF
done

python scripts/gamified.py   --codebase .   --run-id "$RUN_ID"   --aggregate-only   --no-autostart-backend --no-start-dashboard

jq -r '.winner' workspace/runs/$RUN_ID/scorecard.json
```

Pass when:
- `workspace/runs/$RUN_ID/scorecard.json` exists and `.winner` is one of the two variants

---

## Smoke C — Wait‑Here (Sequential, 2 variants)

Goal: prove the rebuilt flow runs in “wait‑here” mode with enforced timeouts.

Run:
```
python scripts/gamified.py   --codebase .   --prompt-file prototypes/gamified/docs/prompt_multiplication_with_tasks.md   --instances 2   --sequential   --instance-timeout-s 120   --idle-timeout-s 120   --no-autostart-backend --no-start-dashboard
```

Pass when:
- A new run appears under `workspace/runs/<run_id>/instances` with two instance dirs
- Each instance has `prompt.md`, at least `iter_01.json`, and a `done.json`
- Scorecard exists at `workspace/runs/<run_id>/scorecard.json`

Note: If the harness has very tight time budgets, prefer Smoke B for CI.

---

## Smoke D — Status CLI (CLI‑only defaults)

Goal: confirm the status surface is available for humans/agents.

Run:
```
python scripts/gamified.py status
```

Pass when:
- It prints a table: `variant | status | last_iter | age` for the latest run

---

## Smoke E — Dashboard (Optional)

Goal: validate that the React dashboard skeleton is present and can run locally.

Run:
```
cd prototypes/gamified/dashboard
npm install
VITE_API_BASE=http://localhost:8000 npm run dev
# open http://localhost:5199
```

Pass when:
- The dev server starts without build errors; the page loads

---

## Automated Tests Hook

- Contracts tests:
```
PYTHONPATH=./src pytest -q tests/smoke/gamified/test_contracts.py -q
```
- Aggregate smoke test:
```
PYTHONPATH=./src pytest -q tests/smoke/gamified/test_aggregate_smoke.py -q
```

---

## Recovery

- If `prototypes/gamified` is deleted, the orchestrator auto‑bootstraps a minimal skeleton on next `run` invocation.
- If you need an explicit restore, recreate using these smokes or re‑apply this repo’s `prototypes/gamified` folder from the last known good backup.
