# CONTRACTS.md Template (Collaboration Surface)

This file is **written first** by the human + agent together.
It captures what “done” means in *human language* and then maps each requirement to a deterministic gate.

> Rule: anything truly “must” be true goes under **Deterministic (blocking)**.
> Fuzzy checks stay **advisory** unless you accept flakiness.

---

## Task: <TASK_NAME>

### Goal (1–2 sentences)
- What must this task produce? (outputs, artifacts, side effects)
- What is the success boundary? (usually `verify_<task>.sh` passes)

### Inputs
- Files / parameters / environment variables:
  - ...

### Outputs
- Files produced:
  - path: `...`
  - format/schema: `...`
- Console output expectations (if any):
  - ...


### Sanity prerequisites (non-standard capabilities only)
Reference IDs from `SANITY_MATRIX.md` **only** for non-standard, failure-prone capabilities (e.g., Camelot, SciLLM, Arango).
Do **not** add sanity checks for standard operations (file IO, JSON parsing, sorting, basic Python).

Reference IDs from `SANITY_MATRIX.md` **only** for non-standard capabilities.

If a sanity prerequisite is **semi-deterministic** (LLM/network), mark it explicitly and require it for **preflight only**:

- S5 (semi-deterministic, preflight only): SciLLM minimal call via Chutes

Never place semi-deterministic sanity checks inside deterministic verifiers (`verify_task*.sh`).

- S?: ...

### Deterministic requirements (blocking)
Write these as testable invariants.

- R1: ...
- R2: ...
- R3: ...

### Canonical examples (high leverage)
Provide at least one canonical example for non-trivial transforms.

#### Example A
**Input:**
- (inline, or point to `tools/sample_*.jsonl` etc.)

**Expected output:**
- (inline, or point to `tools/expected_*.json` etc.)

### Clarification triggers (stop + ask)
When the agent cannot proceed without human input, define deterministic triggers.

- C1 Trigger: <deterministic condition>
  - Questions to ask (printed as `CLARIFY:` lines):
    - CLARIFY: ...
    - CLARIFY: ...

### Advisory checks (non-blocking)
Fuzzy checks must specify:
- artifact inputs (what the judge looks at)
- rubric (what “good” means)
- whether it’s a score or a comment

- A1: “readability >= 7/10” based on diff + file snapshot (advisory only)

### Non-goals / out of scope
- Explicitly say what you are *not* doing to prevent drift.

### Enforcement mapping
Map each requirement to a gate or command.

| ID | Requirement | Enforcement (gate/command) |
|---:|-------------|----------------------------|
| R1 | ...         | `tools/gate_<task>_*.py`   |
| C1 | ...         | `exit 42` + CLARIFY lines  |
| A1 | ...         | `soft_judge.sh`            |

---

## Notes (contract evolution)
- Add new requirements only when discovered by failures or ambiguity.
- Keep requirements minimal but complete.
