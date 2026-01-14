# Skill: Contract Preflight (Anti-Flakiness)

## Purpose
Before implementing code or writing gates, review `CONTRACTS.md` to detect:
- ambiguity,
- mini-app flakiness risks,
- missing examples,
- requirements that can’t be enforced deterministically.

Goal: make the contract crisp so the loop converges in few retries.

---

## Inputs
- `CONTRACTS.md`

## Outputs
1) **Requirements Table**:
- ID, requirement, type (Deterministic/Fuzzy/Clarify), flakiness risk, proposed enforcement

2) **Mini-app risk list**:
- any UI/devtools/browser/network/timing requirements
- deterministic substitutes proposed

3) **Clarify trigger quality**:
- confirm stop condition is deterministic
- emit exact `CLARIFY:` questions

4) **Contract tightening edits**:
- rewrite ambiguous text into testable language
- propose canonical example input/output when missing

---

## Rules of thumb
- Prefer **one deterministic verifier command** per task (`verify_taskN.sh`)
- Deterministic gates must be:
  - stable across machines
  - fast
  - clear failure messages (expected vs got)
- Fuzzy checks are **advisory only** unless you accept flake:
  - require artifacts (snapshot/text report) to judge against
  - use rubric + score
- Clarify triggers must:
  - be deterministic to detect
  - exit with code 42
  - print explicit questions as `CLARIFY:` lines

---

## Anti-patterns to flag immediately
- “looks modern” as a blocking requirement
- “no errors” without specifying *which* logs/commands prove it
- browser/devtools steps without a deterministic runner (e.g., Playwright) + stable assertions
- network-dependent requirements in gates
- time-based waits without bounded conditions

---

## Success criteria
After preflight, every requirement is either:
- a deterministic gate,
- an advisory fuzzy check with artifact + rubric,
- or a deterministic clarify trigger.


## Sanity prerequisites check

During preflight, for each task requirement, identify which sanity checks (from `SANITY_MATRIX.md`) must be present and passing.

Example:
- If a contract asserts "PDF has 4 tables", require:
  - S3 (Camelot can extract a table from fixture)
  - and a deterministic table-count command (e.g., `tools/table_count.py`) to be used by the gate.


## Sanity scope filter (very important)
Only propose sanity scripts for **non-standard, failure-prone, project-specific capabilities**:
- Camelot / PDF table extraction
- SciLLM / LLM call wrappers
- ArangoDB connectivity
- GPU/CUDA toolchain checks (if relevant)
- Browser automation runners (if explicitly used)

Do **NOT** propose sanity scripts for standard operations:
- reading/writing files
- JSON/JSONL parsing
- sorting/deduping
- basic Python/runtime availability
