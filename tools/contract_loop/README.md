# Contract Loop (Project-Level Readme)

The Contract Loop is a strict, step-by-step pipeline orchestrator that
prevents "green but wrong" outputs by enforcing per-step contracts before any
downstream work proceeds. It is designed to be shared across projects and
adapted via project-specific adapters and contracts.

Use this when:
- You have multi-step pipelines where downstream steps can mask upstream errors.
- You need reproducible, deterministic retries with clear failure evidence.
- You want contract-driven development (gate + artifacts + structured review).

Not ideal when:
- Your workflow is a single step with no downstream dependencies.
- You cannot express clear, testable contracts for each step.

## Quickstart (Existing Project)

1) Add a project adapter:
   - Create `tools/contract_loop/adapters/<project>.py`.
   - Add `tools/contract_loop/adapters/<project>/docs/CONTRACT.md`.
   - Add `tools/contract_loop/adapters/<project>/docs/GOAL.md` and fixtures.

2) Add project contracts:
   - Create `contracts/contract_loop/CONTRACT.md`.
   - Add per-task JSON contracts under `contracts/contract_loop/`.

3) Add sanity matrices:
   - Module sanity: `tools/contract_loop/docs/SANITY_MATRIX_CONTRACT.md`
   - Project sanity: `tools/contract_loop/adapters/<project>/docs/SANITY_MATRIX.md`

4) Run the task contract loop:
   - `python -m tools.contract_loop.run_task_loop --contracts-root contracts/contract_loop`

5) Run the pipeline loop (project adapter):
   - `python tools/contract_loop/verify_pipeline_contract.py --mode deterministic`

## Quickstart (New Project)

Minimal checklist:
- Add an adapter under `tools/contract_loop/adapters/`.
- Place project contracts under `contracts/contract_loop/`.
- Provide a project sanity matrix under the adapter docs.
- Add at least one fixture and a deterministic pipeline run.

## Directory Layout (Key Paths)

```
tools/contract_loop/
  README.md               # this file
  core.py                 # pipeline contract loop engine
  run_task_loop.py        # per-task Codex exec loop
  adapters/               # project adapters
  clarify/                # clarifying UI host (TUI + Flask)
  clarify-ui/             # React UI for multi-question flows
  judges/                 # strict JSON output schemas
  scripts/                # build/sanity helpers

contracts/contract_loop/
  CONTRACT.md             # index of per-task JSON contracts
  task_*.json             # per-task contract files
```

## How It Works (Short)

- Each pipeline step must pass its contract before any downstream step runs.
- Failed steps are retried up to `--max-tries`.
- In debug mode, the loop enforces strict cleanup + logs + visuals.
- Deterministic checks run first; optional LLM judges run only after they pass.

## Debug Visuals (Canonical Path)

- Steps emit images under `visual_output/` (sibling to `json_output/`).
- In debug mode, visual count must match object count.
- The adapter can create symlinks under `out/visuals/<step>/` for UI browsing.

## Clarifying UI

When a step fails after max retries, the loop prompts for structured feedback:
- Single-question: curses TUI.
- Multi-question: React UI served by a temporary Flask app.

Build UI assets:
  - `tools/contract_loop/scripts/build_clarify_ui.sh`

## Contracts (Per-Task)

- `contracts/contract_loop/CONTRACT.md` lists task JSON files.
- Each task JSON has deterministic gates and LLM judge config.
- The task loop logs artifacts under `logs/contract_loop/<task>/<timestamp>/`.

## Sanity Gates

- Module-level sanity lives in `tools/contract_loop/docs/SANITY_MATRIX_CONTRACT.md`.
- Project-level sanity lives in `tools/contract_loop/adapters/<project>/docs/SANITY_MATRIX.md`.
- The contract loop refuses to run if required sanity checks are missing or failing.

## Adaptation for Other Projects

Only adapter and project contracts are project-specific. The core module stays
reusable and self-contained.
