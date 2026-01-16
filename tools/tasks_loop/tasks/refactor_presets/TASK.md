# Task: Refactor Presets Compilation

---

task_id: refactor_presets
title: "Compile Runtime Presets from Fixture Contracts"
status: done
priority: medium

acceptance:

- `tools/tasks_loop/fixtures/*/twin_config.yml` contains runtime detection config (keywords, patterns) previously in `presets.py`.
- `src/extractor/core/presets.py` is now an **auto-generated** file (with a warning header).
- A new tool `tools/tasks_loop/utils/compile_presets.py` exists and works.
- Running the pipeline still works (s00 detects correctly).

gate: gates/gate_presets_compilation.py
expected:
presets_py_generated: true
arxiv_config_present: true
boeing_config_present: true

context:

- file:///home/graham/workspace/experiments/extractor/src/extractor/core/presets.py
- file:///home/graham/workspace/experiments/extractor/tools/tasks_loop/fixtures/arxiv_archetype/twin_config.yml
- file:///home/graham/workspace/experiments/extractor/tools/tasks_loop/fixtures/boeing_spec/twin_config.yml

---

## Goal

Align with "Fixture-First" architecture. `presets.py` currently holds hardcoded logic that duplicates or hides knowledge from the Fixtures.
We will move this knowledge into `twin_config.yml` and auto-compile `presets.py`.

## Plan

1.  **Migrate Data**: Copy `detection` and `description` fields from `presets.py` into the respective `twin_config.yml` files.
2.  **Create Compiler**: Write `tools/tasks_loop/utils/compile_presets.py`.
    - Scans `tools/tasks_loop/fixtures/`.
    - Reads `twin_config.yml`.
    - Validates required runtime fields.
    - Generates `src/extractor/core/presets.py`.
3.  **Execute**: Run the compiler.
4.  **Verify**: Run verify tasks to ensure no regression.
