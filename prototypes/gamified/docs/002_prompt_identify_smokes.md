# Unified Prompt — Contracts & Smokes (Script Analyzer)

Mission: Analyze ONE script → define Contracts (schemas + rules) → define Smokes (≤90s total) → only then propose code changes. If anything is ambiguous, stop and ask the human.

Standards: Use Typer CLI where applicable; JSON outputs carry "schema":"*_v1"; tests are pytest; CI and Makefile targets included; write only inside `workspace/` for temp artifacts.

---

## 0) Inputs (fill first)
- [ ] Script path: `__FILL_ME__` (e.g., `scripts/gamified.py`)
- [ ] Purpose (1–2 sentences from README/docstring): `__FILL_ME__`
- [ ] Runtime context: python version, required env vars, external tools: `__FILL_ME__`
- [ ] Constraints: CI time budget, network/DB availability, protected paths: `__FILL_ME__`

---

## 1) Discover (doc + run)
- [ ] Read relevant README sections and the script’s top‑level docstring; summarize expected behavior.
- [ ] Run `python <script> --help` (or module form) and capture key flags; if not Typer, note actual CLI behavior.
- [ ] Static scan the code for:
  - [ ] Inputs (flags/stdin/files) and outputs (files/stdout/exit codes)
  - [ ] Side effects (network/API, DB collections, file system paths)
  - [ ] External deps (imports, binaries) and optional features
- [ ] Try a dry‑run in a temp directory (e.g., `workspace/tmp/analyze_<ts>`). Use minimal/no‑op flags if available; capture outputs and logs.

Deliverable:
- [ ] “Doc vs Observed” bullets (explicit deltas if any)

---

## 2) Contracts (must hold, testable)
Define strict, testable invariants for each surface:
- [ ] CLI: required/optional flags, exit codes (0 ok, 2 bad args, 1 runtime), timeouts, `--out-dir`, `--dry-run`
- [ ] Files: list of outputs; for JSON outputs, provide schemas; for text, define required markers/lines
- [ ] Telemetry (if any): minimal payload shapes (fields/types)
- [ ] API/DB (if used): endpoints/collections, required fields, idempotency/order guarantees
- [ ] Timeouts: default overall/idle behavior + graceful termination markers

Artifacts:
- [ ] Pydantic/JSON Schema models in `src/.../contracts_<script>.py` or `contracts/*.schema.json` with `"schema":"*_v1"`
- [ ] Brief contract doc in `tests/contracts/` or `docs/`

---

## 3) Smokes (fast, deterministic)
Create ≤3–5 smokes; total ≤90s; avoid network unless permitted.
- [ ] help_text: `--help` prints Usage and key flags
- [ ] dry_run: minimal command writes outputs; JSON validates against schema(s)
- [ ] timeout_graceful: tiny `--timeout` triggers graceful exit; markers/logs/files present
- [ ] filesystem_skeleton (if the script scaffolds files/dirs)
- [ ] api_optional: only when backend/DB available; otherwise skip

For each smoke, specify:
- [ ] Name, command(s)
- [ ] Preconditions (fixtures/temp dirs/env)
- [ ] Pass criteria (exit code, file exists, schema‑valid JSON, substrings)

Artifacts:
- [ ] Pytest tests under `tests/smoke/<script_basename>/...` (use a generic helper when helpful)
- [ ] Makefile targets: `smoke-<script-basename>-*` and `smoke-<script-basename>-all`
- [ ] CI entries (skip optional smokes if deps absent)

---

## 4) Clarify (ask human if blocking)
- [ ] Is network/DB allowed in smokes? Which endpoints/collections and what test data?
- [ ] Where are fixtures? Any licensing constraints?
- [ ] CI time budget per smoke?
- [ ] Protected paths (no writes outside `workspace/`)?
- [ ] Are logs exact strings or just presence/levels?

---

## 5) Wire (after 1–4 only)
- [ ] Implement contract schemas and tests
- [ ] Add smokes (temp dirs; deterministic inputs)
- [ ] Add Makefile targets and CI job steps
- [ ] Run locally; confirm green in ≤90s total

---

## 6) Handoff Summary
- [ ] Script analyzed: `__FILL_ME__`
- [ ] Contracts added/updated: files `__FILL_ME__`, schemas `__FILL_ME__`
- [ ] Smokes added: `__FILL_ME__`, `__FILL_ME__`
- [ ] Makefile targets/CI: `__FILL_ME__`
- [ ] Open questions (if any): `__FILL_ME__`

---

## Example snippets (drop‑in)
- JSON Schema (contracts/episode_v1.schema.json) with `"schema":"episode_v1"`
- help_text smoke: ensure `--help` shows Usage + flags
- dry_run smoke: assert JSON stdout validates against schema with fastjsonschema
- Typer invariant: `--out-dir`, `--timeout`, `--dry-run` (use when evolving scripts)

---

# Agent Card — Contracts & Smokes (One‑Pager)

Goal: For one script, deliver schemas + smokes (≤90s). No code changes until tests exist.

1) Fill Inputs: path, purpose, runtime, constraints
2) Discover: README + docstring + `--help`, static scan, dry‑run
3) Contracts: schemas in `contracts/`; CLI flags; outputs; timeouts; optional API
4) Smokes: help_text, dry_run, timeout_graceful (+ skeleton/api_optional as needed)
5) Clarify: only if blocking (net/DB, fixtures, CI time, protected paths, log strictness)
6) Wire: tests, Makefile, CI → green locally ≤90s
