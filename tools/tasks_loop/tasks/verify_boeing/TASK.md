# Task: Verify Boeing Preset

---

task_id: verify_boeing
title: "Verify Context Inference for Requirements Spec"
status: done
priority: high

acceptance:

- Pipeline runs on `fixtures/boeing_spec/source.pdf`.
- `s00` correctly identifies `requirements_spec` preset.
- `pipeline_context.json` confirms `requirements_spec`.
- `s04_section_builder` builds a hierarchy.
- `04_sections.json` contains sections.

gate: gates/gate_boeing.py
expected:
preset: requirements_spec
sections_found: true

context:

- file:///home/graham/workspace/experiments/extractor/src/extractor/core/presets.py
- file:///home/graham/workspace/experiments/extractor/tools/tasks_loop/fixtures/boeing_spec/SPEC.md

---

## Goal

Confirm that the new "Preset-Aware" pipeline correctly identifies and configures for the `requirements_spec` (Boeing) archetype.  
Previously this required hardcoded hacks; now it should be driven by `s00` + `presets.py`.

## Plan

1.  **Run Pipeline**: Run against `boeing_spec/source.pdf`.
2.  **Verify Context**: Gate checks `pipeline_context.json`.
3.  **Verify Sections**: Gate checks `04_sections.json` to ensure the specific section regex worked.
