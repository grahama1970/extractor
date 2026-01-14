# Contract Loop Maintenance Tasks

This checklist keeps the Contract Loop aligned with the pipeline and fixtures.
Use it when steps change or when contracts need to be tightened.

Extractor-specific assets live under:
- `tools/contract_loop/adapters/extractor/docs/CONTRACT.md`
- `tools/contract_loop/adapters/extractor/docs/GOAL.md`

## 1) Keep Steps and Contracts Aligned

- Update your pipeline contract doc when steps are added or removed.
- Update your adapter's step list and output paths.
- Ensure the pipeline execution order matches the Contract Loop step order.

## 2) Maintain Fixtures

- Keep fixtures under `tools/contract_loop/adapters/<name>/fixtures/`.
- If a PDF fixture changes, update `pdf_sha256` in the fixture.
- Keep per-step expectations minimal but meaningful (avoid fragile exact counts).

## 3) LLM Judge Rules

- Keep judge rules in fixture under `steps.<step>.judge`.
- Update `tools/contract_loop/judges/llm_judge.schema.json` if the judge output schema changes.
- Use small sample sizes and minimums to control cost.

## 4) Contract Loop Validation

Use the adapter-specific docs for concrete commands and fixtures.
For this repo, see `tools/contract_loop/adapters/extractor/docs/GOAL.md`.

## 5) When a Step Fails

- Read the step failure message and clarifying questions.
- In debug mode the structured clarifying UI will launch automatically (curses for single questions, Flask form for multi-question flows). Submit responses or re-run with `--clarify-timeout` adjusted if you need more time.
- Need to tweak the React UI? Use `tools/contract_loop/scripts/clarify_ui_dev.sh` for hot reload and `tools/contract_loop/scripts/build_clarify_ui.sh` before shipping changes so the Python host serves the new `dist/`.
- Fix the failing step or relax the contract if it is too strict.
- Re-run the loop with the same fixture.

## 6) Adding a New Step

- Add the step to `run_pipeline.py`.
- Add a minimal contract to `CONTRACT.md`.
- Add the step to `verify_pipeline_contract.py` with output paths and verify hook.
- Add a fixture expectation for the new step (if applicable).
