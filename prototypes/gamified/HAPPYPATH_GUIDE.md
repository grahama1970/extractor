# Gamified — Happy Path Guide

Purpose
- Keep surface area minimal. Avoid option sprawl. Deliver a predictable, collaborative flow that works the first time and every time.
- This guide is for agents and engineers to stay on the paved road. If a step isn’t here, it’s likely out of scope for MVP.

Principles
- One spec. One command. One dashboard.
- Progressive disclosure: defaults always work; overrides are rare.
- Collaboration-by-default: runs are shareable, replayable, and annotated.
- Deterministic where possible: store seeds/spec snapshots for replay.
- Arango-only for MVP: no alternative backends, no graph authoring.

Golden Path Overview
- CLI verbs (only 4):
  - `init` — create a spec via a tiny TUI wizard
  - `run` — execute from a spec; auto-start backend; print URLs
  - `open` — open the dashboard filtered to a run
  - `replay` — re-run using the stored spec snapshot
- Single spec file: `gamified.yaml` (v1), Pydantic-validated.
- Backend: FastAPI + Arango (auto-starts on a free port).
- Dashboard: React/Tailwind/Shadcn (Status, Episodes, Logs, Run Notes).

Prerequisites
- ArangoDB running and reachable:
  - `ARANGO_HOST=127.0.0.1 ARANGO_PORT=8529 ARANGO_USERNAME=root ARANGO_PASSWORD=openSesame ARANGO_DB=marker`
- Codex CLI available:
  - `export CODEX_BINARY_PATH=/absolute/path/to/codex` (optional if `codex` is on PATH)
- uv (recommended) and Node (for dashboard dev only). The CLI auto-starts the backend; dashboard dev server is started by the orchestrator; you don’t need to run it manually.

Spec v1 (canonical example)
```yaml
version: 1
codebase:
  repo_root: .
approaches:
  - name: fueling_density_mpc
  - name: edge_stability_mhd
  - name: heat_extraction_adaptive
runner:
  type: analysis_sim
scoring:
  weights: { correctness: 35, robustness: 25, speed: 25, brevity: 15 }
constraints:
  edge_density_threshold: 1.0e19  # m^-3
  q_min: 2.0                      # safety factor lower bound
  beta_max: 0.04                  # fraction
  heat_flux_peak_max: 10.0        # MW/m^2
optimizer:
  rules: prototypes/gamified/rules/prompt_optimization.yaml
execution:
  concurrency: 3
  codex_exec: true
  autostart_backend: true
  autostart_dashboard: true
observability:
  backend: arango
  dashboard: true
```

SOPs (Step-by-Step)
1) Initialize a spec
- `python -m prototypes.gamified.cli init`
- Answer 3–4 prompts; writes `gamified.yaml`.

2) Run from the spec
- `python -m prototypes.gamified.cli run --spec gamified.yaml`
- What happens:
  - Backend autostarts on a free port.
  - Prompt is rendered from the spec and optimized (POP). Any hard errors are printed and the run exits.
  - A spec snapshot is saved to `workspace/runs/<run_id>/manifests/spec.yaml`.
  - The CLI prints the API scoreboard URL and the Dashboard URL.

3) Open the last run
- `python -m prototypes.gamified.cli open`
- Prints all URLs and attempts to open the backend dashboard proto. Use `--run-id` to pick a specific run.

4) Replay a run (deterministic)
- `python -m prototypes.gamified.cli replay <run_id>`
- Uses the stored spec snapshot for the run.

5) Annotate and share
- Dashboard → Status tab → Run Notes block
- Enter short context for teammates; click Save Notes. Copy/share the URL with filters.

Programmatic API (MVP)
- `GET /spec?path=gamified.yaml` → `{ ok, path, content }`
- `PUT /spec` with `{ path, content }` to persist changes
- `POST /runs` with `{ spec_path | spec_content, run_id?, fast? }` → `{ ok, run_id }`
- `GET /runs/{id}/notes` → `{ ok, notes }`
- `POST /runs/{id}/notes` with `{ notes }`
- `GET /stream` (SSE), `GET /scoreboard?run_id=...`, `GET /episodes?run_id=...`, `GET /logs?run_id=...`

CI Smokes (already wired)
- Prompt/spec validation (POP strict): `.github/workflows/gamified-prompts.yml`
- Fast run smoke (emit-only; artifacts): `.github/workflows/gamified-smoke.yml`

Do / Don’t (to avoid bloat)
- Do:
  - Use `--spec` for runs; prefer `gamified.yaml` at repo root.
  - Define all constraints as concrete numbers; keep 3–5 approaches.
  - Let POP normalize scoring to 100; keep runner = `analysis_sim` for MVP.
  - Use Run Notes instead of adding comment systems.
- Don’t:
  - Don’t add new flags or optional knobs unless they are absolutely necessary.
  - Don’t leave placeholders (e.g., "define") or ambiguous sections.
  - Don’t introduce new backends or graph flows in MVP.

Troubleshooting (fast)
- Backend failed to start: ensure Arango env vars set; the CLI prints `[backend] not reachable; starting…` and exits on failure.
- `codex` not found: set `CODEX_BINARY_PATH` or ensure `codex` on PATH.
- Ports busy: the CLI picks a free port; if conflicting, re-run.
- Artifacts: see `workspace/runs/<run_id>/manifests` and `api_base.txt`, `scorecard.json`.

Playbooks
- Fresh run for a teammate:
  - `git pull` → `python -m prototypes.gamified.cli run --spec gamified.yaml` → share the printed URLs.
- Quick iteration:
  - Edit `gamified.yaml` → re-run → annotate notes → share link.
- CI verification for PR:
  - Let the two workflows run; ensure POP strict passes and smoke artifacts upload.

Roadmap (v2, explicitly out-of-scope for MVP)
- “Optimize + Run” with diff + Accept in the dashboard (Write /spec then spawn /runs).
- A/B compare view and threaded comments.
- Graph workflows and alternative observability backends (Langfuse/OTLP) behind feature flags.

FAQ
- Why spec-first? Predictability, collaboration, and replayability with one source of truth.
- Why Arango only? Fewer moving parts; adapters can come later without changing the spec.
- Why only 4 CLI verbs? Reduces the cognitive footprint; everything maps to spec.
