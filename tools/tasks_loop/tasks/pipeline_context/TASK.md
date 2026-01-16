# Task: Pipeline Context Injection

---

task_id: pipeline_context
title: "Integrate s00 into Pipeline and Propagate Context"
status: done
priority: high

acceptance:

- `run_pipeline.py` runs `s00_profile_detector` as the first step (unless skipped).
- `run_pipeline.py` reads the detected preset from `s00` output.
- `run_pipeline.py` loads the preset configuration (from `presets.py` for now).
- Downstream steps (specifically `s04`) receive this configuration/context.
- A new artifact `pipeline_context.json` (or similar) is saved to the run output, confirming the active preset.

gate: gates/gate_pipeline_context.py
expected:
preset_detected: true
context_propagated: true

context:

- file:///home/graham/workspace/experiments/extractor/src/extractor/pipeline/run_pipeline.py
- file:///home/graham/workspace/experiments/extractor/src/extractor/pipeline/steps/s00_profile_detector.py
- file:///home/graham/workspace/experiments/extractor/src/extractor/core/presets.py

---

## Goal

Bridge the "Split Brain" gap by making `run_pipeline.py` aware of the document's Preset. This allows the pipeline to dynamically adjust heuristics (e.g., regex patterns) based on the document type (e.g., ArXiv vs. Boeing).

## Implementation Plan

1.  **Integrate Step 00**:

    - Import `s00_profile_detector` in `run_pipeline.py`.
    - Call `s00.run` at the start of execution.
    - Parse the output (`00_profile.json`) to get `detected_preset`.

2.  **Context Loading**:

    - In `run_pipeline.py`, look up the configuration for the detected preset using `extractor.core.presets.PRESET_REGISTRY`.
    - If no preset detected, use defaults.

3.  **Context Propagation**:

    - Update the `_step` function or the manual calls to `s04` (etc.) to accept a `context` or `preset_config` argument.
    - _Minimal Change Strategy_: Instead of refactoring every step immediately, we can start by having `run_pipeline` save the config to a standard location (`context.json`) that steps _can_ read if they want to.
    - _Better Strategy_: Pass `preset_config` explicitly to `s04.run`.

4.  **Verification**:
    - Run pipeline on `arxiv_archetype`.
    - Verify `s00` ran.
    - Verify `pipeline_context.json` confirms `arxiv` preset.
