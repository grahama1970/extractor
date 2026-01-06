# Review: Wiggum Loop (Strict Step-by-Step Convergence)

## Repository and branch

- **Repo:** `grahama1970/extractor`
- **Branch:** `feature/wiggum`
- **Paths of interest:**
  - `WIGGUM_LOOP.md`
  - `scripts/verify_pipeline_contract.py`
  - `contracts/fixtures/BHT_CV32A65X_with_requirements_noannots.json`
  - `contracts/judges/llm_judge.schema.json`
  - `src/extractor/pipeline/steps/CONTRACT.md`

## Summary

We are adopting a **strict, step-by-step Wiggum loop** that:

1. **Reruns all upstream steps** on each attempt to avoid stale inputs.
2. **Deletes all downstream outputs** before retrying to prevent zombie artifacts.
3. **Blocks progression** until the current step passes its contract.
4. **Stops after max tries** and prompts the human with clarifying questions.

LLM steps are judged for **reasonableness** using a Codex exec call when `--llm-judge` is enabled and the fixture defines judge rules.

## Objectives

### 1. Code Review: Wiggum Loop Enforcement

In `scripts/verify_pipeline_contract.py`:

- Validate the **step sequencing** and upstream rerun logic.
- Validate **downstream cleanup** for all affected outputs.
- Ensure **max tries** halts and prints human questions.
- Confirm **LLM judge** integration is safe and only runs when enabled.
- Confirm **Lean4** is skipped unless explicitly enabled and fixture includes it.

### 2. Contract Alignment

In `src/extractor/pipeline/steps/CONTRACT.md`:

- Ensure active steps match `run_pipeline.py`.
- Verify deterministic vs. full (LLM) expectations are realistic and minimal.
- Ensure fixture usage and LLM judge guidance are clear.

## Constraints

- **Safety:** deletion must be scoped to the pipeline output dir only.
- **Determinism:** deterministic mode must not require network access.
- **Latency:** verify-only checks should be fast and avoid expensive recomputation.

## Acceptance criteria

- `python scripts/verify_pipeline_contract.py --mode deterministic --fixture contracts/fixtures/BHT_CV32A65X_with_requirements_noannots.json --pdf data/input/pipeline/BHT_CV32A65X_with_requirements_noannots.pdf`
  - Reruns upstream steps and deletes downstream outputs per attempt.
  - Stops on the first failing step.
- `python scripts/verify_pipeline_contract.py --mode full --llm-judge --skip-lean4 --fixture contracts/fixtures/BHT_CV32A65X_with_requirements_noannots.json --pdf data/input/pipeline/BHT_CV32A65X_with_requirements_noannots.pdf`
  - Executes LLM steps and Codex reasonableness checks.
  - Stops after max tries with human questions if a step fails.

## Test plan

1. Run deterministic loop on the BHT fixture (S01–S04 verified).
2. Run full loop with LLM judging (S05b/S06b/S08/S09 judged).
3. Confirm failures stop immediately and print clarifying questions.

## Clarifying questions

1. Should fixture expectations be versioned per PDF revision (hash/commit)?
2. Do we want to persist judge outputs (per-step artifacts) for auditability?
3. Should we add a `--step` flag to start the loop from a specific step?
