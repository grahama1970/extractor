# Task Template

#

# Copy this file to tasks/{task_id}/TASK.md and fill in the details.

# Each task gets a fresh context window with focused iteration.

---

task_id: example_task
title: "Example Task Title"
status: pending # pending, in_progress, blocked, done
priority: medium # low, medium, high, critical

# Acceptance Criteria

# What must be true for this task to be complete?

acceptance:

- Gate `gate_example.py` passes
- Documentation updated
- Tests added

# Verification

gate: gates/gate_example.py
expected:
feature_works: true

# Context

# Links to related code, docs, or issues

context:

- file:///path/to/relevant/file.py
- https://github.com/org/repo/issues/123

---

## Goal

Describe what needs to be built or changed.

## Background

Why is this needed? What problem does it solve?

## Implementation Notes

Any technical details, constraints, or approaches to consider.

## Agent Instructions

When working on this task:

1. Read related files in `context` section
2. Make minimal, focused changes
3. Run the gate to verify: `python gates/gate_example.py --task example_task`
4. Do NOT modify gate scripts unless instructed
