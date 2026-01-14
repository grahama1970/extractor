# Contract Loop (Strict Pipeline Convergence)

Note

- This is a contract-driven fork of the Ralph Wiggum loop, renamed to avoid confusion with the original agent retry pattern.

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

- Core engine in `tools/contract_loop/core.py`
- Extractor adapter in `tools/contract_loop/adapters/extractor.py`
- CLI wrapper in `tools/contract_loop/verify_pipeline_contract.py` (also `scripts/verify_pipeline_contract.py`)

Adapters

- The core loop is generic and portable.
- Project-specific behavior (step list, fixture checks, DB cleanup) lives in adapters.
- For this repo, use `tools/contract_loop/adapters/extractor.py`.
- Extractor-specific goals and helpers live under `tools/contract_loop/adapters/extractor/docs/`.

Adapter Responsibilities (Required)

- Define the step list and module paths (e.g., `extractor.pipeline.steps.s01_annotation_processor`).
- Implement fixture verification rules and LLM sample extraction.
- Provide downstream cleanup behavior for your storage model (files/DB).
- Provide step-specific clarifying questions.

Adapter Layout (Recommended)

- `tools/contract_loop/adapters/<name>.py` (adapter implementation)
- `tools/contract_loop/adapters/<name>/docs/CONTRACT.md` (pipeline contract)
- `tools/contract_loop/adapters/<name>/docs/GOAL.md` (fixture/goal expectations)
- `tools/contract_loop/adapters/<name>/fixtures/` (fixture JSON files)

Execution Flags

- `--max-tries N`         Max attempts per step (default 3).
- `--llm-judge`           Use Codex exec to judge LLM output reasonableness.
- `--skip-lean4`          Skip Lean4 verification.
- `--start-step <STEP>`   Start the loop from a specific step after validating upstream outputs.
- `--no-rerun-upstream`   Disable rerunning upstream steps (not recommended).
- `--no-clean-downstream` Disable downstream cleanup (not recommended).
- `--debug`               Enforce clean/rerun discipline, capture per-attempt logs, and write `debug.md` + manifest metadata for human collaboration.
- `--bundle-warn-mb`/`--bundle-max-mb` Tune collaboration bundle warning/fail thresholds (defaults: warn at 50 MB, hard-stop at 100 MB).
- `--debug` additionally enforces adapter-defined visual artifacts: steps must emit image files under `visual_output/` with counts matching extracted objects (tables, sections, figures, etc.). Requirements are the exception: they must carry page + bbox anchors, but images are optional.

Fixture Contracts

- Fixture expectations live under `tools/contract_loop/adapters/extractor/fixtures/`.
- Example fixture: `tools/contract_loop/adapters/extractor/fixtures/BHT_CV32A65X_with_requirements_noannots.json`
- The fixture defines per-step contracts, including LLM judge rules.
- If `pdf_sha256` is present in the fixture, the verifier enforces it.
  Judge outputs are persisted under `<output>/<step>/judge_output.json` and appended to `<output>/judge_index.jsonl` (not cleaned between retries).

Security Considerations

- Judge outputs include full prompts and samples; treat `<output>/` as sensitive if inputs are sensitive.
- If you need redaction, add a `--redact-prompts` flag (future enhancement).

Example (Deterministic Base)

```bash
python tools/contract_loop/verify_pipeline_contract.py \
  --pdf data/input/pipeline/BHT_CV32A65X_with_requirements_noannots.pdf \
  --fixture tools/contract_loop/adapters/extractor/fixtures/BHT_CV32A65X_with_requirements_noannots.json \
  --mode deterministic
```

Example (Full + LLM Judge)

```bash
python tools/contract_loop/verify_pipeline_contract.py \
  --pdf data/input/pipeline/BHT_CV32A65X_with_requirements_noannots.pdf \
  --fixture tools/contract_loop/adapters/extractor/fixtures/BHT_CV32A65X_with_requirements_noannots.json \
  --mode full \
  --llm-judge \
  --skip-lean4
```

Stop Conditions and Clarifying Questions

- If a step fails after max tries, the verifier prints a list of questions to the human.
- In debug mode, the loop now launches the structured clarifying UI:
  - Single-question failures show a curses-based selector inline.
  - Multi-question failures start a temporary Flask app (`http://127.0.0.1:<port>/`) that shuts down once the form is submitted. Responses are saved under `out/clarifications/<step>/attempt_<n>.json` and referenced in `manifest.json`.
  - The run fails with exit code 4 if no response is received before `--clarify-timeout` (default 900s).
- Outside of debug mode the CLI still prints the plain-text questions, but the structured UI is strongly recommended for collaborative debugging.

What to Change Over Time

- Tighten fixture expectations as the pipeline stabilizes.
- Add LLM judge rules only after deterministic steps are solid.
- Keep Lean4 verification disabled until the external dependency is stable.
