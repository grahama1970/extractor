# Task Template

# Copy this file to tasks/{task_id}/TASK.md and fill in the details.
# Each task gets a fresh context window with focused iteration.

---
task_id: example_task
title: "Example Task Title"
status: pending  # pending, in_progress, blocked, done
priority: medium  # low, medium, high, critical

# Acceptance Criteria - What must be true for this task to be complete?
acceptance:
  - Gate `gate_example.py` passes
  - All crucial dependencies have verified sanity scripts
  - Documentation updated
  - Tests added

# Definition of Done (Non-Negotiable)
# Each task MUST have specific tests and assertions BEFORE implementation
definition_of_done:
  - test: tests/path/to/test_file.py::test_function_name
    assertion: "What the test proves in plain English"
  - test: tests/path/to/test_file.py::test_another_function
    assertion: "What this test validates"

# Verification
gate: gates/gate_example.py
expected:
  feature_works: true

# Context - Links to related code, docs, or issues
context:
  - file:///path/to/relevant/file.py
  - https://github.com/org/repo/issues/123
---

## Goal

Describe what needs to be built or changed.

## Background

Why is this needed? What problem does it solve?

---

## Crucial Dependencies

> **COLLABORATION REQUIRED**: Before implementation begins, each non-standard
> dependency must have a verified sanity script. This proves the API works
> AND documents the correct invocation pattern for the agent.

### Dependency Identification Workflow

```
1. Agent identifies non-standard libraries/APIs needed
2. Agent uses research skills to find correct usage:
   - brave-search (free): General patterns, examples, StackOverflow
   - Context7: Library-specific documentation chunks
   - perplexity (paid): Complex research, comparisons
3. Agent creates sanity script in tools/tasks_loop/sanity/
4. Human confirms dependencies and verifies sanity scripts pass
5. Then Questions/Blockers can be marked "None"
```

### Dependencies for This Task

| Library | API/Method | Sanity Script | Status |
|---------|------------|---------------|--------|
| `{library1}` | `method()` | `sanity/{library1}.py` | [ ] verified |
| `{library2}` | `class.method()` | `sanity/{library2}.py` | [ ] verified |

**Standard libraries (no sanity needed)**: `json`, `pathlib`, `typing`, `dataclasses`, etc.

### Research Commands

```bash
# Brave search (free) - general usage, StackOverflow, blog posts
python .pi/skills/brave-search/search.py "camelot table extraction line_scale parameter"

# Context7 - library documentation chunks (LLM-ranked)
python .pi/skills/context7/context7.py search camelot "table extraction parameters"
python .pi/skills/context7/context7.py context /camelot-dev/camelot "read_pdf line_scale"

# Perplexity (paid) - complex research, comparisons
python .pi/skills/perplexity/perplexity.py ask "camelot vs tabula vs pdfplumber for table extraction"
```

### Sanity Script Requirements

Each script in `tools/tasks_loop/sanity/` must:

1. **Show correct imports** - What to import
2. **Document parameters** - With valid values and explanations
3. **Provide working example** - Agent copies this pattern
4. **Include edge cases** - What to avoid, known issues
5. **Exit codes**: 0=PASS, 1=FAIL, 42=CLARIFY

See: `tools/tasks_loop/sanity/TEMPLATE.py`

---

## Questions/Blockers

> **BLOCKED** until ALL items resolved AND crucial dependencies verified.

- [ ] Question or blocker 1
- [ ] Question or blocker 2
- [ ] All sanity scripts pass: `for f in sanity/*.py; do python "$f" || exit 1; done`

---

## Implementation Notes

Any technical details, constraints, or approaches to consider.

## Agent Instructions

When working on this task:

1. **Pre-flight**: Verify Definition of Done tests exist before implementing
2. Check crucial dependencies section - sanity scripts must pass first
3. Read related files in `context` section
4. Reference sanity scripts for correct API usage patterns
5. Make minimal, focused changes
6. Run DoD tests to verify completion
7. Run the gate to verify: `python gates/gate_example.py --task example_task`
8. Do NOT modify gate scripts unless instructed

See `tools/tasks_loop/DOD_CHECKLIST.md` for full verification requirements.
