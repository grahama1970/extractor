# Contract Loop

The Contract Loop enforces step-by-step convergence for a pipeline.
Each step must satisfy its contract before any downstream work proceeds.
This prevents stale artifacts and makes failures actionable.

This approach is a contract-driven fork of the original Ralph Wiggum loop, renamed
"Contract Loop" to avoid confusion with the generic agent retry pattern.

This repo uses the extractor adapter in `tools/contract_loop/adapters/extractor.py`.

## Project Layout (Single Source of Truth)

```
tools/contract_loop/
  core.py                  # generic loop engine
  utils.py                 # small portable helpers
  judges/                  # judge schemas (Codex JSON)
  adapters/
    extractor.py           # extractor adapter (step list + checks)
    extractor/
      docs/                # CONTRACT.md + GOAL.md
      fixtures/            # fixture JSON files
contracts/
  contract_loop/           # per-task JSON contracts + CONTRACT.md index (project-owned)
```

Pipeline step code is referenced from the adapter. For this repo, the adapter
points to `src/extractor/pipeline/steps/*.py`.

## Contract-Loop Task Runner (Backend-Agnostic)

Per-task contracts live in the **project** (not inside `tools/contract_loop/`):
`contracts/contract_loop/CONTRACT.md` lists JSON contracts. The task loop reads
that index and runs each task via a Codex exec harness plus deterministic + LLM
gates.

```bash
python tools/contract_loop/run_task_loop.py \
  --contracts-root contracts/contract_loop
```

See `tools/contract_loop/docs/examples/` for a minimal contract template.

## Quick Start (Extractor Adapter)

Deterministic base (no LLM steps):

```bash
python tools/contract_loop/verify_pipeline_contract.py \
  --pdf data/input/pipeline/BHT_CV32A65X_with_requirements_noannots.pdf \
  --fixture tools/contract_loop/adapters/extractor/fixtures/BHT_CV32A65X_with_requirements_noannots.json \
  --mode deterministic
```

Full mode with LLM judge:

```bash
python tools/contract_loop/verify_pipeline_contract.py \
  --pdf data/input/pipeline/BHT_CV32A65X_with_requirements_noannots.pdf \
  --fixture tools/contract_loop/adapters/extractor/fixtures/BHT_CV32A65X_with_requirements_noannots.json \
  --mode full \
  --llm-judge \
  --skip-lean4
```

Wrapper (equivalent):

```bash
python scripts/verify_pipeline_contract.py \
  --pdf data/input/pipeline/BHT_CV32A65X_with_requirements_noannots.pdf \
  --fixture tools/contract_loop/adapters/extractor/fixtures/BHT_CV32A65X_with_requirements_noannots.json \
  --mode deterministic
```

## Outputs

- Per-step outputs live under the pipeline output directory (default is
  `data/results/pipeline_contract/`).
- `judge_output.json` is written per step when `--llm-judge` is enabled.
- `judge_index.jsonl` is appended for every judge call and is NOT cleaned
  between retries (audit trail).

## Key Flags

- `--max-tries N`: max attempts per step.
- `--start-step <STEP>`: start from a specific step (upstream verified first).
- `--no-rerun-upstream`: keep upstream outputs (not recommended).
- `--no-clean-downstream`: keep downstream outputs (not recommended).
- `--skip-lean4`: skip Lean4 verification.
- `--debug`: forces clean/rerun discipline, captures per-attempt stdout/stderr under `out/<step>/attempt_<n>/`, records debug metadata in `manifest.json`, and writes `out/debug.md` summarizing every attempt.
- `--bundle-warn-mb` / `--bundle-max-mb`: configure the collaboration-bundle warning/fail thresholds (default 50 MB warning, hard-stop at 100 MB).
- `--clarify-timeout`: seconds to wait for the structured clarifying UI (default 900s / 15 minutes). When retries are exhausted in debug mode, the CLI launches a curses prompt (single question) or Flask form (multi-question) and blocks until responses are submitted or the timeout hits.

## Docs in This Folder

- `CONTRACT_LOOP.md`: concept, rules, and examples.
- `01_TASKS.md`: Q1 2026 enhancement plan (non-automatic work).
- `TASKS.md`: maintenance tasks and update checklist.

### Clarify UI (TypeScript)

Multi-question clarifications are rendered by a React/TypeScript UI located at
`tools/contract_loop/clarify-ui` (Vite + React Hook Form + Zod).

- Build once after editing:
  - `tools/contract_loop/scripts/build_clarify_ui.sh`
- Dev server (hot reload + custom forms):
  - `PORT=4173 VITE_API_BASE=http://127.0.0.1:5057 tools/contract_loop/scripts/clarify_ui_dev.sh`
- The Python clarifying server serves the contents of `clarify-ui/dist`. If you
  see `Clarify UI build not found`, re-run the build script.

Extractor-specific docs live under the adapter:
- `tools/contract_loop/adapters/extractor/docs/GOAL.md`
- `tools/contract_loop/adapters/extractor/docs/s08_stop_hook_feedback.sh`

## Suggested Workflow

1. Tighten `tools/contract_loop/adapters/extractor/docs/CONTRACT.md` and fixture expectations.
2. Run deterministic mode until it passes consistently.
3. Enable full mode and add LLM judge rules only after the base is stable.

## Porting to Another Project

Use the core engine in `tools/contract_loop/core.py` and implement a new adapter
under `tools/contract_loop/adapters/` with your step list and fixture checks.

## Latest Task Status

`logs/contract_loop/latest_status.json` is regenerated after each task run.
To refresh it manually:

```bash
python -m tools.contract_loop.write_latest_status
```
