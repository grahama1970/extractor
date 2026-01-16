# Task: Enable s08 (Lean4) Context Awareness

---

task_id: s08_context
title: "Drive Lean4 Proving from Preset Config"
status: done
priority: medium

acceptance:

- `arxiv_archetype` fixture enables proving in its config.
- `boeing_spec` fixture explicitly disables or omits proving.
- `presets.py` contains `features` dict with `enable_proving`.
- `run_pipeline.py` uses this config to decide whether to run `s08` (if CLI args permit).
- Gate verifies that `s08` RUNS for Arxiv and SKIPS for Boeing (when running in auto mode).

gate: gates/gate_s08_context.py
expected:
arxiv_runs_s08: true
boeing_skips_s08: true

context:

- file:///home/graham/workspace/experiments/extractor/src/extractor/pipeline/run_pipeline.py
- file:///home/graham/workspace/experiments/extractor/tools/tasks_loop/utils/compile_presets.py

---

## Goal

`s08_lean4_theorem_prover` is domain-specific (Math/Scientific). It should not run on Engineering specs (waste of resources/errors).
We will control this via the Fixture/Preset config.

## Implementation

1.  **Schema Update**: Add `features: { enable_proving: true/false }` to `runtime` section of `twin_config.yml`.
2.  **Compiler Update**: Pass `features` from formatting to `presets.py`.
3.  **Pipeline Logic**: In `run_pipeline.py`, before running `s08`, check:
    ```python
    should_prove = args.prove_theorems or (preset_config.get("features", {}).get("enable_proving") and args.auto_mode?)
    ```
    _Decision_: If `args.prove_theorems` is explicitly set, obey it. If not, fallback to preset.
