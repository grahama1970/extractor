# Bug Template

#

# Copy this file to bugs/{bug_id}/BUG.md and fill in the details.

# Each bug gets a fresh context window with focused iteration.

---

bug_id: example_bug
title: "Example Bug Title"
status: open # open, investigating, fix_pending, verified, closed
severity: medium # low, medium, high, critical
reported: 2024-01-15

# Symptoms

# What's happening that shouldn't be?

symptoms:

- Describe observable behavior
- Include error messages if any

# Expected Behavior

expected: |
What should happen instead?

# Reproduction

# Minimal steps to reproduce

reproduction:

- Step 1
- Step 2
- Step 3

# Verification

gate: gates/gate_bug_example.py
fix_criteria:
error_logged: true
does_not_crash: true

# Context

context:

- file:///path/to/buggy/file.py#L123

---

## Analysis

Root cause analysis (fill in after investigation).

## Fix Approach

Proposed solution.

## Agent Instructions

When fixing this bug:

1. Reproduce the issue first
2. Identify root cause
3. Make minimal fix
4. Run gate to verify: `python gates/gate_bug_example.py --bug example_bug`
5. Do NOT modify gate scripts
6. Do NOT fix unrelated issues in the same context
