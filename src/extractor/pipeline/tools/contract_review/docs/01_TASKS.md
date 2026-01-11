```markdown name=tools/contract_review/V1_SPEC.md
# contract_review v1 specification

## Goal

Provide a portable, self-contained tool (stored under `tools/`) that enforces a “Contract.md is complete and unambiguous before proceeding” workflow.

The tool:

- scans a contract file for ambiguity markers
- generates a deterministic set of questions for missing/ambiguous items
- integrates with **pi-interview-tool** by writing/reading JSON artifacts
- applies answers back into `Contract.md` using tool-managed sections
- **fails fast** (blocking) when ambiguity exists and answers are not yet applied

This tool is intended to be used by an agent in iterative loops:

1. scan → generate questions → run interview → apply answers → re-scan until clean

---

## Repository layout (must follow exactly)

All module code and docs live under:

- `tools/contract_review/` (module root)

All runtime state is stored under:

- `tools/contract_review/.state/`

State must be **gitignored** (see `.gitignore` enforcement below).

### Required files/directories (v1)

- `tools/contract_review/` (Python package / scripts)
- `tools/contract_review/.state/` (created at runtime; **ignored by git**)
- `tools/contract_review/V1_SPEC.md` (this file)
- `tools/contract_review/AGENTS.md` (agent-facing usage + trigger list)

---

## Contract file support

### Single contract per invocation

The tool operates on exactly **one** contract per run.

### Contract path input

- Primary: `--contract <path-to-Contract.md>`
- If `--contract` is omitted, the tool auto-detects:
  1. `./Contract.md`
  2. else `./docs/Contract.md`
  3. else fail with actionable error: “Contract.md not found; pass --contract”

Multi-module repos are handled by running the tool separately for each module contract file (e.g. `modules/foo/Contract.md`).

---

## Ambiguity triggers (blocking markers)

### Trigger set (fixed for v1)

Ship with the **conservative default list**:

- `TBD`
- `TODO`
- `FIXME`
- `???`
- `depends`
- `not sure`
- `maybe`
- `unknown`

### Scope

- Scan the **entire** `Contract.md` file (including tool-managed sections and logs).

### Agent visibility requirement

The agent must be explicitly informed which ambiguity triggers exist:

- `tools/contract_review/AGENTS.md` must list them.
- CLI should print them in scan output or behind `--verbose` (implementation choice), but they must be readily visible in standard agent logs.

### Blocking behavior

If any ambiguity triggers are found:

- the tool must **fail fast**
- exit code must be **2**
- questions must be generated (see below)
- the agent must not proceed until the contract is cleaned / answered and re-applied

---

## Questions + interview integration (pi-interview-tool)

### Output question file

The tool generates a JSON question set compatible with **pi-interview-tool**.

Default location (per-contract, see state partitioning):

- `.../questions.json`

Override:

- `--out <path>` (must be supported)

### Input responses file

The tool reads answers as JSON produced by pi-interview-tool.

Default location (per-contract):

- `.../responses.json`

Override:

- `--responses <path>` (must be supported)

### Expected workflow

1. `contract_review scan --contract <path>` generates questions JSON
2. pi-interview-tool is run externally using that questions JSON and produces responses JSON
3. `contract_review apply --contract <path>` reads responses JSON and updates `Contract.md`
4. repeat scan until no triggers remain

The contract_review tool does **not** implement its own web UI in v1.

---

## State storage (portable + per-contract partitioned)

### State is under tools/ and gitignored

All tool state lives under:

- `tools/contract_review/.state/`

This makes the module portable (everything it needs is under `tools/`) while keeping state out of git.

### Per-contract state directories

State must be **separate per contract path** to avoid collisions.

Per-contract state directory key = `slug + short hash` derived from the contract path.

Example:

- contract: `modules/payments/Contract.md`
- state dir: `tools/contract_review/.state/modules__payments__Contract_md__a1b2c3d4e5f6/`
  - `questions.json`
  - `responses.json`

The exact slug format is up to implementation, but must:

- be stable across runs for the same contract path
- be filesystem-safe
- include a short hash component to prevent collisions

### Index file

The tool must create/update:

- `tools/contract_review/.state/index.json`

This records a mapping to make state discoverable and debuggable:

- contract path → state directory key
- optional metadata (timestamps, last run, etc.) is allowed but not required

---

## `.gitignore` enforcement

The tool must ensure the repo root `.gitignore` includes an ignore rule for the state directory.

- Required ignore target: `tools/contract_review/.state/`
- The update must be **idempotent**:
  - add the ignore line only if not already covered by an equivalent pattern
  - treat equivalent patterns as sufficient (e.g., `tools/contract_review/.state` without trailing slash)

If `.gitignore` is missing:

- do **not** create it
- fail with an actionable error (assumption: `.gitignore` always exists)

---

## How answers are applied to Contract.md (document hygiene)

The tool must not attempt to “surgically” edit arbitrary parts of the contract.

Instead it manages three sections at the **end** of `Contract.md`:

1. `## Open Questions` (tool-managed)
2. `## Resolved Decisions` (tool-managed)
3. `## Decision Log` (append-only, tool-managed)

### Rules

- Unanswered questions live under **Open Questions**
- When answered, items are moved to **Resolved Decisions**
- Every apply run appends a record to **Decision Log** (append-only)
- Tool-managed sections must be clearly marked as managed (implementation may add HTML comments or sentinel markers)

Because the tool scans the entire contract, these managed sections must not contain ambiguity markers after apply (except as literal historical artifacts; if they do, scan will still block per policy).

---

## CLI / entrypoints

Provide a Python CLI with:

- primary command: `contract_review`
- short alias: `cr`

Minimum subcommands (suggested; exact names may vary but functionality must exist):

- `contract_review scan`

  - scans for triggers
  - generates/updates per-contract `questions.json`
  - updates `Contract.md` managed sections as needed (optional), but must at least produce questions
  - enforces `.gitignore` rule
  - exits:
    - `0` when no ambiguity triggers found
    - `2` when ambiguity triggers found (blocking)

- `contract_review apply`
  - reads `responses.json`
  - updates `Contract.md` by moving Open → Resolved and appending Decision Log
  - should be deterministic and idempotent if re-run with same inputs

Optional utility command (allowed, not required):

- `contract_review triggers` (prints trigger list)

---

## Non-goals for v1

- No per-repo configuration file (trigger list is **fixed** in v1)
- No automatic guessing of “right place” to insert answers into the main contract body
- No multi-contract scanning in a single invocation (run once per contract)
- No requirement to commit any `.state` artifacts

---

## Acceptance criteria (v1 “definition of done”)

1. Running `contract_review scan --contract <path>`:

   - enforces `.gitignore` contains ignore for `tools/contract_review/.state/` (idempotent)
   - creates/updates per-contract state dir and `index.json`
   - scans the entire contract
   - generates per-contract `questions.json`
   - exits `2` if any trigger is present; exits `0` otherwise

2. Running pi-interview-tool against the generated questions and producing responses, then `contract_review apply --contract <path>`:

   - updates Contract.md with the three managed sections
   - moves answered items Open → Resolved
   - appends a Decision Log entry
   - re-running apply with the same responses is safe (no duplicated decisions beyond the defined logging behavior)

3. The tool documents the ambiguity triggers it uses in `tools/contract_review/AGENTS.md`, and that list matches runtime behavior.
```
