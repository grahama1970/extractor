# Task List: Definition of Done Compliance Improvements

## Context

Improve the extractor project's Definition of Done compliance from 68% to 85%+. Based on assessment findings, we need to:
1. Formalize DoD documentation and templates
2. Complete missing pipeline gate coverage (S11-S13)
3. Fix test collection errors
4. Add explicit DoD sections to existing task files

## Crucial Dependencies (Sanity Scripts)

| Library | API/Method | Sanity Script | Status |
|---------|------------|---------------|--------|
| pytest | Collection | None needed | N/A (standard) |
| Lean4 (for S11) | `lake build` | `S11_lean4_docker.py` | [x] EXISTS |
| DuckDB (for gates) | `duckdb.connect()` | `S7_duckdb_basic.py` | [x] PASS |

> Sanity scripts already exist for non-standard dependencies used by gates.

## Tasks

- [ ] **Task 1**: Create DoD checklist and update task template

  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: none
  - Notes: Create formal DoD checklist document and update TEMPLATE.md to require explicit DoD sections
  - **Sanity**: None (documentation only)
  - **Definition of Done**:
    - File: `tools/tasks_loop/DOD_CHECKLIST.md` exists with verification steps
    - File: `tools/tasks_loop/tasks/TEMPLATE.md` updated with DoD section
    - Assertion: Template includes "Definition of Done" field with test + assertion format

- [ ] **Task 2**: Fix test collection errors (3 files)

  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: Task 1
  - Notes: Fix import errors in test_03_suspicious_headers_offline.py, test_04_section_builder_minimal.py, test_cli_extract.py
  - **Sanity**: None (uses pytest - standard)
  - **Definition of Done**:
    - Test: `pytest tests/ --collect-only` exits 0 with no collection errors
    - Assertion: All 187+ tests collect without import errors

- [ ] **Task 3**: Implement gate_s11.py (Lean4 compilation)

  - Agent: general-purpose
  - Parallel: 1
  - Dependencies: Task 1
  - Notes: Create gate script for S11 Lean4 theorem prover step. Check that Lean4 container is accessible and can compile.
  - **Sanity**: `tools/tasks_loop/sanity/S11_lean4_docker.py` (must pass)
  - **Definition of Done**:
    - File: `tools/tasks_loop/gates/gate_s11.py` exists
    - Test: `python tools/tasks_loop/gates/gate_s11.py` exits 0 or 42 (clarify if Lean4 not available)
    - Assertion: Gate validates Lean4 compilation step outputs

- [ ] **Task 4**: Implement gate_s12.py (PDF annotations)

  - Agent: general-purpose
  - Parallel: 1
  - Dependencies: Task 1
  - Notes: Create gate script for S12 annotation rendering step.
  - **Sanity**: None (uses PyMuPDF - covered by S1)
  - **Definition of Done**:
    - File: `tools/tasks_loop/gates/gate_s12.py` exists
    - Test: `python tools/tasks_loop/gates/gate_s12.py` exits 0
    - Assertion: Gate validates annotation overlay on PDF pages

- [ ] **Task 5**: Implement gate_s13.py (knowledge graph)

  - Agent: general-purpose
  - Parallel: 1
  - Dependencies: Task 1
  - Notes: Create gate script for S13 graph building step (if it exists in pipeline).
  - **Sanity**: None (uses networkx/ArangoDB - well-known)
  - **Definition of Done**:
    - File: `tools/tasks_loop/gates/gate_s13.py` exists OR documented as N/A
    - Test: Gate passes or returns 42 (clarify) if step doesn't exist
    - Assertion: Gate validates graph structure or documents step absence

- [ ] **Task 6**: Add explicit DoD to 01_TASKS.md

  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: Task 1, Task 2
  - Notes: Update the 26 tasks in 01_TASKS.md to have explicit Definition of Done sections referencing specific tests/gates
  - **Sanity**: None (documentation only)
  - **Definition of Done**:
    - File: `01_TASKS.md` updated with DoD sections for all 26 tasks
    - Assertion: Each task has "Definition of Done" with test file + assertion

- [ ] **Task 7**: Add explicit DoD to 02_TASKS.md

  - Agent: general-purpose
  - Parallel: 1
  - Dependencies: Task 1
  - Notes: Update 02_TASKS.md tasks to have explicit DoD format (already has good completion criteria)
  - **Sanity**: None (documentation only)
  - **Definition of Done**:
    - File: `02_TASKS.md` updated with explicit DoD format
    - Assertion: Tasks reference specific tests for completion verification

- [ ] **Task 8**: Run full quality gate and verify 85%+ compliance

  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: Task 2, Task 3, Task 4, Task 5, Task 6, Task 7
  - Notes: Final verification that all improvements work together
  - **Sanity**: None
  - **Definition of Done**:
    - Test: `make smokes-cli` passes
    - Test: `pytest tests/ --collect-only` shows 0 collection errors
    - Test: Gates S11, S12, S13 exist and return valid exit codes
    - Assertion: All task files have explicit DoD sections

## Completion Criteria

- DoD checklist created and template updated
- All test collection errors fixed (0 errors on `pytest --collect-only`)
- Gates S11, S12, S13 implemented (or documented as N/A)
- All task files (01_TASKS.md, 02_TASKS.md) have explicit DoD sections
- Quality gate passes: `make smokes-cli`

## Questions/Blockers

None - all questions resolved from assessment phase.
