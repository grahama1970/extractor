# Wiggum Loop (Strict Pipeline Convergence)

Purpose

- Stop the "green but wrong" pipeline by enforcing a strict, repeatable, step-by-step loop.
- Each step must prove its contract before any downstream work is allowed.
- If a step fails after max tries, stop and ask the human for clarification.

Why This Exists

- LLM stages are nondeterministic.
- Past attempts failed because contracts were vague and stale outputs masked regressions.
- This loop forces clean inputs, verified outputs, and explicit acceptance checks.

Key Rules (Non-Negotiable)

1) Run upstream steps every attempt.
   - This prevents stale data from leaking into later steps.

2) Delete downstream outputs before retrying.
   - This prevents "old success" artifacts from hiding failures.

3) Do not proceed until the current step passes its contract.

4) If max tries are reached for a step, stop and ask the human.

How It Works

For each step N:

- Attempt 1..M:
  - Delete outputs for step N and all downstream steps.
  - Re-run steps 1..N in order.
  - Verify each step immediately after it runs.
  - If any step fails, retry (until max tries).
- If step N passes, move to step N+1.
- If step N fails after max tries, stop and ask the human.

This behavior is implemented by:

- `scripts/verify_pipeline_contract.py`

Execution Flags

- `--max-tries N`         Max attempts per step (default 3).
- `--llm-judge`           Use Codex exec to judge LLM output reasonableness.
- `--skip-lean4`          Skip Lean4 verification.
- `--no-rerun-upstream`   Disable rerunning upstream steps (not recommended).
- `--no-clean-downstream` Disable downstream cleanup (not recommended).

Fixture Contracts

- Fixture expectations live under `contracts/fixtures/`.
- Example fixture: `contracts/fixtures/BHT_CV32A65X_with_requirements_noannots.json`
- The fixture defines per-step contracts, including LLM judge rules.

Example (Deterministic Base)

```bash
python scripts/verify_pipeline_contract.py \
  --pdf data/input/pipeline/BHT_CV32A65X_with_requirements_noannots.pdf \
  --fixture contracts/fixtures/BHT_CV32A65X_with_requirements_noannots.json \
  --mode deterministic
```

Example (Full + LLM Judge)

```bash
python scripts/verify_pipeline_contract.py \
  --pdf data/input/pipeline/BHT_CV32A65X_with_requirements_noannots.pdf \
  --fixture contracts/fixtures/BHT_CV32A65X_with_requirements_noannots.json \
  --mode full \
  --llm-judge \
  --skip-lean4
```

Stop Conditions and Clarifying Questions

- If a step fails after max tries, the verifier prints a list of questions to the human.
- The loop does NOT continue until those questions are answered.

What to Change Over Time

- Tighten fixture expectations as the pipeline stabilizes.
- Add LLM judge rules only after deterministic steps are solid.
- Keep Lean4 verification disabled until the external dependency is stable.
