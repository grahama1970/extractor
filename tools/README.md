# Contract Loop v1 (2 tasks)

This is a **clean minimal** proof-of-concept for:

- Human+agent collaboration on **natural-language task contracts**
- Converting those contracts into deterministic **gates** (assertions)
- A tiny loop that forces an agent to iterate until the verifier passes,
  or stops with **clarifying questions**

No schemas. No DSL. No event parsing. One boundary: a verifier script.

---

## Repo contents

- `CONTRACTS.md` — collaboration surface (natural language)
- `verify_task1.sh` — deterministic verifier for task 1
- `verify_task2.sh` — deterministic verifier for task 2
- `loop.sh` — retry loop that runs a verifier, tees output to `verify.log`,
  and (on failure) runs a fresh `codex exec` using only the log tail
- `soft_judge.sh` — optional advisory check (non-blocking)
- `src/contacts.py` — task 1: implement `normalize_contacts`
- `tools/contacts_cli.py` — task 2: implement a small CLI wrapper
- `tools/gate_*.py` — deterministic gates

---

## Quickstart

Prereqs:
- bash (Linux/macOS/WSL)
- Python 3.10+
- `codex` CLI installed + authenticated (only needed for `./loop.sh`)

Run task 1 loop (default 3 retries):
```bash
./loop.sh --verify ./verify_task1.sh
```

Run task 2 loop:
```bash
./loop.sh --verify ./verify_task2.sh
```

Run gates manually:
```bash
./verify_task1.sh
./verify_task2.sh
```

---

## Status reporting (how a “main agent” knows what happened)

`loop.sh` always writes a small status file:

- `./.loop_status.json`

This file includes:
- `status`: PASS / FAIL / CLARIFY
- `exit_code`
- `verify` (which verifier was run)
- `attempts_used`
- `log_path`
- `clarify_lines` (if any)

So a “main project agent” can:
1) run `./loop.sh ...`
2) read `.loop_status.json`
3) decide what to do next (answer clarifying questions, add gates, etc.)

---

## Exit codes (minimal set)

Keep this small to avoid harness brittleness:

- `0`  PASS (verifier succeeded)
- `1`  FAIL after exhausting retries (retryable failure during attempts)
- `2`  HARNESS/ENV error (missing `codex`, bad args)
- `3`  CLARIFY stop (loop stopped due to clarification gate)
- `42` CLARIFY code from gate scripts (verifier returns 42; loop converts to exit 3)

You can add more later **only** when you have a concrete need (e.g. a “SKIP” code).

---

## Contracts: natural language → assertions

The highest leverage is improving `CONTRACTS.md`.

Workflow:
1) Human writes clear bullets about what “done” means.
2) Agent proposes the *smallest deterministic assertion* that enforces each bullet.
3) Human edits bullets and assertions until they match intent.
4) The loop forces convergence and reduces regressions.

As ambiguity is discovered, you update:
- `CONTRACTS.md` (intent)
- `tools/gate_*.py` (enforcement)


## Run all tasks

```bash
./run_all.sh
```

This runs task 1 then task 2 (each via `./loop.sh`) and stops on the first FAIL or CLARIFY.
It writes `./.run_all_status.json` with per-task results.


## One-line summaries for interactive agents

`run_all.sh` prints a final single-line status you can key off in scrollback:

- `RUN_ALL_STATUS=PASS|FAIL|CLARIFY|ERROR`
- `RUN_ALL_RC=<exit code>`

`loop.sh` prints `LOOP_STATUS=PASS|FAIL|CLARIFY` when it ends.


## Contract preflight skill

Before converting `CONTRACTS.md` into gates, run a preflight review using:

- `skills/contract_preflight_skill.md`

Use it to identify mini-app flakiness risks, tighten ambiguous requirements, and propose deterministic enforcement.


## Templates

Use these to add new tasks without inventing a framework:

- `templates/CONTRACTS_TEMPLATE.md`
- `templates/GATE_TEMPLATE.py`
- `templates/VERIFY_TEMPLATE.sh`
- `templates/ADVISORY_TEMPLATE.md`

## Agent instructions

See `AGENT_INSTRUCTIONS.md` for the exact workflow the interactive project agent should follow.

## Sanity matrix (non-standard capability checks)

Use `SANITY_MATRIX.md` + `sanity/` scripts **only** for non-standard, failure-prone capabilities that the agent cannot safely assume (e.g., Camelot table extraction, SciLLM calls).

Do **not** create sanity scripts for standard operations (file IO, JSON parsing, sorting, etc.). Those belong in normal gates/implementation.

### Example: “PDF has 4 tables”
If a task contract asserts a PDF has 4 tables:
- Require a Camelot sanity (S3) so the agent knows table extraction works at all.
- Enforce the actual table count deterministically in a gate (e.g., via `tools/table_count.py`).


## Preflight convention

Run sanity checks before implementing tasks or running the loop:

```bash
./preflight.sh
```

- Deterministic sanity (e.g., Camelot fixture extraction) may be included here.
- Semi-deterministic sanity (LLM/network) **must** run here (or manually), and must **not** be called from `verify_task*.sh`.

Choose checks:

```bash
PREFLIGHT_DET="S3" PREFLIGHT_SEMI="S5" ./preflight.sh
```
