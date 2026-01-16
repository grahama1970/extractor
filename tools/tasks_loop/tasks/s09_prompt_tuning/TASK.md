# Task: Context-Aware Prompt Tuning for s09

---

task_id: s09_prompt_tuning
title: "Tune Summarization Prompts via Preset Context"
status: done
priority: medium

acceptance:

- `twin_config.yml` (Arxiv/Boeing) contains `summarization_prompt` logic.
- `presets.py` includes this prompt in `features`.
- `s09_section_summarizer` uses the custom prompt if present.
- Verification run shows different prompts being used (log the prompt or check output).

context:

- file:///home/graham/workspace/experiments/extractor/src/extractor/pipeline/steps/s09_section_summarizer.py
- file:///home/graham/workspace/experiments/extractor/src/extractor/pipeline/run_pipeline.py

---

## Goal

Customize LLM prompts for different document types.

## Plan

1.  **Schema**: Add `prompts` section to `twin_config.yml` runtime features.
2.  **Compiler**: Update `compile_presets.py`.
3.  **Pipeline**: Pass `preset_config` to `s09` call in `run_pipeline.py`.
4.  **Implementation**: Logic in `s09` to select prompt.
