# Agent Instructions (How to Use This Repo)

You are a repo-scoped coding agent running under an interactive Codex session.

## Your goal
Make the selected verifier pass (e.g., `verify_task1.sh`, `verify_task2.sh`), using the contract in `CONTRACTS.md`.

## Workflow
1) **Preflight** the contract:
   - Follow `skills/contract_preflight_skill.md`
   - Identify ambiguous requirements and mini-app flakiness risks
   - Propose contract tightenings if needed (do not silently reinterpret)

2) **Implement** code changes:
   - Prefer small, localized edits
   - Run the verifier frequently

3) **Use the loop** for forced convergence:
   - `./loop.sh --verify ./verify_taskN.sh --retries 3`
   - When it ends, key off `LOOP_STATUS=...` and read `.loop_status.json`

4) If you hit clarification:
   - The loop will stop and print `CLARIFY:` lines.
   - Do **not** guess. Ask the human to answer those questions.
   - Once answered, update `CONTRACTS.md` and (if needed) gate scripts, then rerun.

## Hard rules
- Do not edit `verify_*.sh` or `tools/gate_*.py` unless the human explicitly says the contract changed.
- Deterministic gates must remain deterministic (no network, no time-based flake).
- Fuzzy checks must remain advisory unless explicitly promoted to blocking.

## What to output to the human
After a run:
- State `RUN_ALL_STATUS=...` (or `LOOP_STATUS=...`)
- Summarize any failures with the specific gate messages
- If CLARIFY, list the questions verbatim and stop


## Sanity matrix integration

Before implementing a task or adding gates, confirm required sanity checks from `SANITY_MATRIX.md` pass **only when the task depends on non-standard capabilities** (Camelot, SciLLM, Arango, etc.).

- If a contract requires PDF table counting, it must reference **S3** (Camelot extract fixture) and/or **S4** (`tools/table_count.py`).
- If a required sanity check fails, stop and report the failure (do not burn retries).

Where to put working sanity scripts:
- `sanity/S<N>_*.sh`
- deterministic fixtures in `fixtures/`


Sanity checks should NOT cover standard operations (writing JSON, reading files). Keep SANITY_MATRIX small and focused.


## Preflight (sanity) workflow

Before implementing tasks or converting contracts into gates:
- Run `./preflight.sh` for required sanity checks.
- If a sanity check is semi-deterministic (LLM/network), it is **preflight only** and must not be added to deterministic verifiers.

The contract should reference required sanity IDs and explicitly tag semi-deterministic ones as “preflight only”.
