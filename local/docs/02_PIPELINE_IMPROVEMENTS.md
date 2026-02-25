# Task List: Pipeline Improvements & Skill Integration

> Generated: 2026-02-04
> Quality Gate: Enabled

## Context

Execute Phase 1 (verification) and Phase 2 (skill integration testing) from PLAN_PIPELINE_IMPROVEMENTS.md. The blocking issues (TASK-001 to TASK-008) have already been verified as complete. This task list focuses on verifying remaining tasks and running skill integration tests.

## Crucial Dependencies (Sanity Scripts)

| Library | API/Method | Sanity Script | Status |
|---------|------------|---------------|--------|
| pytest | collect/run | Standard library | N/A |
| extractor.pipeline | step imports | `tests/pipeline/steps/test_cli_factories_all_steps.py` | [x] PASS (14/14) |

> All sanity scripts PASS - standard pytest infrastructure verified.

## Tasks

- [ ] **Task 1**: Verify medium-priority tasks (TASK-009 to TASK-012) completion status
  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: none
  - Notes: Check if code quality issues (unreachable code, duplicate functions, duplicate imports, deprecated code) have been resolved
  - **Sanity**: N/A (verification only)
  - **Definition of Done**:
    - Test: Manual verification via grep/read
    - Assertion: Each issue either fixed or documented as false positive in 01_TASKS.md

- [ ] **Task 2**: Verify low-priority tasks (TASK-013 to TASK-015) completion status
  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: Task 1
  - Notes: Check no-op parameters, commented code, stub implementations
  - **Sanity**: N/A (verification only)
  - **Definition of Done**:
    - Test: Manual verification via grep/read
    - Assertion: Each issue either fixed or documented in 01_TASKS.md

- [ ] **Task 3**: Verify preset propagation tasks (TASK-016 to TASK-026) completion status
  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: Task 2
  - Notes: All 14 pipeline step files already have preset_config - verify proper usage
  - **Sanity**: N/A (verification only)
  - **Definition of Done**:
    - Test: `grep -l "preset_config" src/extractor/pipeline/steps/*.py | wc -l`
    - Assertion: 14+ files contain preset_config

- [ ] **Task 4**: Update 01_TASKS.md with full verification results
  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: Task 3
  - Notes: Mark all verified tasks as complete with status notes
  - **Sanity**: N/A (documentation update)
  - **Definition of Done**:
    - Test: File contains "✅ COMPLETE" for all verified tasks
    - Assertion: 01_TASKS.md reflects current codebase state

- [ ] **Task 5**: Run extractor skill sanity check
  - Agent: general-purpose
  - Parallel: 1
  - Dependencies: Task 4
  - Notes: Verify the /extractor skill works correctly
  - **Sanity**: N/A (integration test)
  - **Definition of Done**:
    - Test: `/home/graham/workspace/experiments/pi-mono/.pi/skills/extractor/sanity.sh`
    - Assertion: Exit code 0, all format tests pass

- [ ] **Task 6**: Run fixture-tricky → extractor integration test
  - Agent: general-purpose
  - Parallel: 1
  - Dependencies: Task 4
  - Notes: Generate adversarial PDF and verify extractor handles it
  - **Sanity**: N/A (integration test)
  - **Definition of Done**:
    - Test: Generate false-tables PDF and extract with --fast mode
    - Assertion: Extraction completes without crash

- [ ] **Task 7**: Run comprehensive pytest suite
  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: Task 5, Task 6
  - Notes: Final verification that all tests pass
  - **Sanity**: N/A (test suite)
  - **Definition of Done**:
    - Test: `pytest tests/pipeline/steps/test_cli_factories_all_steps.py tests/pipeline/test_03_suspicious_headers_offline.py -v`
    - Assertion: All tests pass (exit code 0)

- [ ] **Task 8**: Update CHANGELOG.md with verification summary
  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: Task 7
  - Notes: Document the assessment and improvements made
  - **Sanity**: N/A (documentation)
  - **Definition of Done**:
    - Test: CHANGELOG.md contains entry for 2026-02-04
    - Assertion: Entry documents task verification and skill integration

## Completion Criteria

All tasks marked complete with:
- 01_TASKS.md fully updated with verification status
- Skill sanity checks passing
- Pytest suite passing
- CHANGELOG.md updated

## Questions/Blockers

None - all questions resolved, infrastructure verified.
