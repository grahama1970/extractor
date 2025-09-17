# Gamified Orchestrator — Prompt‑Driven, Codex‑Exec Compatible

This prototype is now prompt‑first. You write a single, well‑structured Markdown prompt (codebase + approaches + constraints + evidence + execution), and the CLI+agent does the rest:
- Parses approaches → N variants
- Autostarts the backend (FastAPI) and the React dashboard
- Validates and optimizes the prompt (no ambiguity) before any run
- Launches one Codex instance per approach (concurrent, supervised)
- Streams logs and episodes to the ingest API
- Scores and declares a winner; writes a scorecard JSON

---

## Quick Start (Happy Path)

1) Start ArangoDB (or point to an existing instance)
````
make arango-up
export ARANGO_HOST=127.0.0.1
export ARANGO_PORT=8529
export ARANGO_USERNAME=root
export ARANGO_PASSWORD=openSesame
export ARANGO_DB=marker
````

2) Create a spec (one file drives everything)
```
python -m prototypes.gamified.cli init   # answers 3–4 questions → writes gamified.yaml
```

3) Run from the spec (no flags required)
```
python -m prototypes.gamified.cli run --spec gamified.yaml
```
This autostarts the backend on a free port and prints the Dashboard URL. A snapshot of the spec is stored under `workspace/runs/<run_id>/manifests/spec.yaml` for replay.

4) Open and collaborate
```
python -m prototypes.gamified.cli open   # opens the last run in the Dashboard
```
In the Dashboard, filter to the Run, add run notes (shareable), and monitor logs/episodes.

## Quick Start

Prompt examples:
- `prototypes/gamified/docs/prompt_multiplication_poc.md`
- `prototypes/gamified/docs/prompt_multiplication_with_tasks.md`

Run with a prompt file (autostarts backend + dashboard):
Preferred (canonical module):
```
python -m prototypes.gamified.cli run \
  --prompt-file prototypes/gamified/docs/prompt_multiplication_poc.md \
  --codebase .
```
Back-compat wrapper still works:
```
python scripts/gamified.py run \
  --prompt-file prototypes/gamified/docs/prompt_multiplication_poc.md \
  --codebase .
```

What happens:
- The optimizer enforces required sections, canonical approach names, scoring normalization, constraints defined (no "define"), and evidence checklists.
- Backend (FastAPI logger, torch‑free) autostarts on a free port.
- Dashboard (React/Tailwind/Shadcn) autostarts on a free port.
- One Codex instance per approach runs concurrently; each instance has its own prompt file under `workspace/runs/<run_id>/instances/.../prompt.md`.
- Scorecard is written to `bench/results/multiply_scorecard.json` and `workspace/runs/<run_id>/scorecard.json`.
- Winner is posted to `/ingest/episode` so the scoreboard/episodes update live.

---

## Prompt Optimization (POP)

- Rules file: `prototypes/gamified/rules/prompt_optimization.yaml`
  - Required sections: codebase, approaches, runner, scoring, constraints, evidence, execution, references, tasks
  - Approach names: snake_case, canonicalized, min/max count enforced
  - Scoring: weights normalized to 100, hard gate if `constraints_ok == false`
  - Constraints: all required globals must be defined (no placeholders)
  - Evidence schema: per‑approach checklists (e.g., stability_margin, density_ok, heat_flux_peak, constraints_ok)
  - Execution defaults: concurrency=3, codex_exec=true, autostart backend/dashboard
- Optimizer CLI: `python -m prototypes.gamified.tools.prompt_opt`
  - `optimize <in.md> -o <out.md> --show-diff`
  - `validate <in.md> --strict` (CI gate)
  - `lint <in.md>`
- Orchestrator integration:
  - `--optimize-prompt/--no-optimize` (default: on) and `--rules <path>`
  - Optimized prompt is written to `workspace/runs/<run_id>/manifests/prompt_optimized.md` and used for the run.

Collaborative loop (2–4 turns)
- You share a research‑level prompt; I run optimize+lint and return a short diff and any missing constraints/evidence.
- I propose defaults or ask for the exact numbers; you confirm or edit.
- I re‑optimize and run 3 Codex instances; you get Winner + live dashboard.

Approach‑to‑Module (A2M) protocol (when approaches aren’t code‑testable)
- I add minimal algorithmic directions, function signatures, constraints, and an evidence checklist so Codex has a starting point it can implement and the judge can score.

---

## CLI Usage (Happy Path)

Commands
- `init` — tiny TUI to scaffold `gamified.yaml`
- `run` — main orchestrator (accepts `--spec gamified.yaml`)
- `open` — opens the dashboard filtered to the last (or `--run-id`)
- `replay` — re-run from a stored `spec.yaml` snapshot
- `status` — print per‑variant status for latest (or `--run-id`)

Key flags (run)
- `--spec gamified.yaml` — Happy Path: one file drives everything
- `--run-id myrun-001` — optional explicit run id
- `--emit-only` — write per‑instance prompts + `launch_all.sh`, then exit (CI)
- `--no-autostart-backend` / `--no-start-dashboard` — disable autostart (CI)

Legacy flags remain for compatibility but are not needed on the Happy Path.

Monitoring
- Web logs: `GET /proto/dashboard` on the backend (zero setup)
- React dev: `cd prototypes/gamified/dashboard && npm run dev`
- Scoreboard API: `GET /scoreboard?run_id=<run_id>`

Recommended flows
- Wait‑here: defaults (timeouts enforced); good for local dev
- Non‑waiting: `--emit-only` → launch → `--aggregate-only`; good for tight CI/harness budgets

---

## Prompt Anatomy (Minimal)

Use our template `prototypes/gamified/docs/MD_RULES_TEMPLATE.md` or copy the multiplication POC prompt. Key sections:
- Codebase (repo root or directory)
- Approaches (bullet list; names become variants)
- Optional Tasks (in a `json tasks` fenced block) with scopes: `pre`, `per_variant`, `post`

Optional flags:
- `--instances` caps concurrency (defaults to min(#approaches, CPU))
- `--no-autostart-backend`, `--no-start-dashboard` to disable autostart

---

## How It Works (Under the Hood)

1) CLI parses the prompt, extracts approaches, and ensures minimal artifacts (baseline/variants/bench) for the POC.
2) Starts FastAPI ingest and React dashboard.
3) Runs `scripts/variant_agent.py` per approach. Each agent:
   - Benchmarks, computes an iteration score, posts `/ingest/episode` and `/ingest/log`
   - Detects plateau via epsilon/window; stops when stabilized
4) The CLI aggregates the latest metrics, computes the cross‑variant scoreboard, saves JSON, and logs the winner.

---

## Smokes & Contracts

Specs
- Contracts + Smokes: `prototypes/gamified/docs/tasks/001_Smokes.md/README.md`
- Rebuild smokes: `prototypes/gamified/docs/tasks/002_Smokes_Rebuild.md`

Run locally (Makefile)
- Contracts: `make contracts-all`
- Gamified smokes (pytest): `make smoke-gamified-all`
- Gamified smokes (CLI): `make smoke-gamified-cli`
- Full gate (contracts + smokes): `make qa-all`

Note on CLI location

- The canonical Typer app lives at `prototypes/gamified/cli.py`.
- `scripts/gamified.py` is a tiny shim that re-exports the app to keep existing
  scripts and CI stable.
- Gamified smokes live under `prototypes/gamified/smokes/` with wrappers in
  `scripts/smokes/gamified/` for backwards compatibility.

CI
- See `.github/workflows/ci-smokes.yml` — calls Make targets to keep parity with local

---

## Dashboards

- React (dev on 5199): `cd prototypes/gamified/dashboard && npm run dev`
- Prototype HTML (zero setup): `GET /proto/dashboard` on the backend
- The logger backend is lightweight and torch‑free; it only imports FastAPI + python‑arango + dotenv.

### Memory Integration (Happy Path)

Memory is available to all projects (including Gamified) via ArangoDB. We keep it under the hood so your CLI stays unchanged.

- On‑failure suggestions (automatic): when a stderr line arrives, the backend appends a short "[memory] Suggestions:" block to Run Notes (top 2–3 lessons with a compact why). Open the Status tab, edit/share notes as usual.
- Timeline freshness (operator): update temporal recency so "recent" queries get a tiny nudge.
  - `make -C prototypes/gamified memory-timeline`
- Research ideas panel (optional): the Status tab shows a "New Research Ideas" block sourced from arXiv (scope=research). Click Refresh, then mark Helpful/Not helpful (feeds back to memory).
- Configure memory env (shared Arango instance):
  - `ARANGO_URL=http://127.0.0.1:8529 ARANGO_DB=lessons ARANGO_USER=root ARANGO_PASS=openSesame`
  - Install Graph Memory in the same venv: `uv pip install -e ../../memory".[faiss]"` (and optionally `.[code]` for Tree‑sitter)

Make targets (operator):
- `memory-timeline` — uv run lessons-timeline build --scope gamified
- `research-update` — on‑demand lessons-arxiv-research for `scope=research` (MAX=3, PDF_TOP=0)

---

## Deprecated (moved to `deprecated/`)

The previous manifest/harness/JS‑variant flow is archived. Prefer the prompt‑driven CLI above.
- `harness/` (manifest adapter, JS eval)
- `variants/` (JS title‑case examples)
- `web/` (static logger demo)
- `tests/` (legacy tests for JS flow)
- `orchestrator_smoke.py`

---

## Preflight

- Ensure Python and uvicorn are available.
- Optional: Node ≥ 18 for the React dashboard.
- Required: ArangoDB 3.11+ reachable via env (`ARANGO_HOST/PORT/USERNAME/PASSWORD/ARANGO_DB`).
- Backend health:
  - `curl -fsS http://localhost:8000/scoreboard`
  - `curl -fsS -X POST http://localhost:8000/ingest/log -H 'Content-Type: application/json' -d '{"ts":0,"run_id":"smoke","variant":"noop","episode_id":null,"stream":"app","source":"preflight","message":"ping","meta":{}}'`

### ArangoDB Setup (Docker)

```
make arango-up
export ARANGO_HOST=127.0.0.1
export ARANGO_PORT=8529
export ARANGO_USERNAME=root
export ARANGO_PASSWORD=openSesame
export ARANGO_DB=marker
```

### Run 3 Codex Instances and Dashboard

```
export CODEX_BINARY_PATH=/absolute/path/to/codex
./scripts/gamified_show_and_tell.py --codebase . \
  --prompt "$(cat prototypes/gamified/docs/02_tokamak_prompt.md)"
```

The CLI autostarts the backend and dashboard on free ports and connects to ArangoDB using
the env above. Artifacts are written under `workspace/runs/<run_id>/` with a scorecard.

---

## Rebuild Notes

- If `prototypes/gamified` is missing, `scripts/gamified.py run` will auto‑bootstrap a minimal skeleton (rules + prompt + README) without overwriting existing files.
- For a full rebuild verification, follow `docs/tasks/002_Smokes_Rebuild.md`.


---

## Research → Prompt → Run (Tokamak example)

- Start from research: `prototypes/gamified/docs/003_challenges/tokamak/tokamak_research.md`
- Draft a prompt: copy `prototypes/gamified/docs/02_tokamak_prompt.md` and adjust constraints/thresholds
- Optimize:
  - `python -m prototypes.gamified.tools.prompt_opt optimize <raw.md> -o <optimized.md> --show-diff`
- Run:
  - `./scripts/gamified_show_and_tell.py --codebase . --prompt "$(cat <optimized.md>)"`
- Iterate: refine constraints, evidence, and scoring; re‑optimize; re‑run.
