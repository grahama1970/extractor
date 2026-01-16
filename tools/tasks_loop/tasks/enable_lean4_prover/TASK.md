# Task: Enable Lean4 Theorem Prover

---

task_id: enable_lean4_prover
title: "Enable Lean4 Theorem Prover with Max Theorems Limit"
status: done
priority: medium

acceptance:

- Lean4 prover runs in pipeline when `--prove-requirements` flag is set
- Max theorems limit configurable via env var or flag
- Gate `gate_lean4.py` passes with sample requirements
- Smoke test with 3 theorems completes in < 30s

gate: gates/gate_lean4.py
expected:
theorems_generated: 3
all_pass: true

context:

- file:///home/graham/workspace/experiments/extractor/src/extractor/pipeline/run_pipeline.py#L947
- file:///home/graham/workspace/experiments/extractor/src/extractor/pipeline/steps/s08_lean4_theorem_prover.py

---

## Goal

Enable the Lean4 theorem prover step (currently disabled as "Aspirational") with a configurable max theorems limit for testing.

## Background

The Lean4 prover was marked aspirational but the infrastructure exists. We need to:

1. Remove the DISABLED comment
2. Add `--max-theorems N` flag for testing
3. Ensure it integrates with the pipeline

## Implementation Notes

- Look at `run_pipeline.py:947` for the disabled section
- The prover step is `s08_lean4_theorem_prover.py`
- Use `LEAN4_MAX_THEOREMS` env var as fallback

## Agent Instructions

1. Read the context files
2. Enable Lean4 in run_pipeline.py
3. Add max_theorems parameter to s08
4. Create gate_lean4.py for verification
5. Run smoke test with 3 theorems
