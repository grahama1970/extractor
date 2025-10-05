# Fork
Fork: grahama1970/extractor
Branch: feat/section-heuristics-and-overlay
Path: git@github.com:grahama1970/extractor.git#feat/section-heuristics-and-overlay

## Stage 07 Status Update + Help Request (DeepSeek OK; GLM 503) — Please advise with unified diffs

Summary of what we just validated (via debug tools):
- Prompt = SYSTEM contract + USER first text part (JSON guard + section summary + truncated text), then images appended in deterministic order: section image → up to 2 low‑confidence table crops → first figure.
- Models tested via `debug/step07_prompt_lab.py` on this repo’s environment:
  - openai/deepseek-ai/DeepSeek-V3.1: strict → ok:true (parse_strategy=direct, has_reflowed_json=true)
  - openai/deepseek-ai/DeepSeek-V3.1: minimal → ok:true (parse_strategy=direct, has_reflowed_json=true)
  - openai/zai-org/GLM-4.5-Air: both guards failed with 503 “No instances available” (Chutes service availability)
- Artifacts: `scripts/artifacts/prompt_lab_runs/run_YYYYMMDD_HHMMSS/summary.json` (latest run id present in the repo).

Questions back to you (Copilot):
1) Tables & metrics — did we carry Camelot+pandas metrics into the prompt and reflow results as expected?
   - Stage 05 emits `pandas_metrics` (shape, columns, density, etc.) and (optionally) `camelot_metrics`. We want your confirmation we’re preserving these signals in the reflow and—in the case of table merging—using them to guide merges.
2) Merge across pages 0–1 — were the two table fragments that span pages 0 and 1 merged into a single logical table block in `reflowed_json.blocks`?
   - If not: Please propose a minimal diff (unified) for the Stage 07 merge heuristic to ensure same‑column fragments across adjacent pages merge deterministically.
3) Step 07 purpose alignment — confirm this is your understanding:
   - “Reflow sections using text + images to produce strict JSON (`reflowed_json`) with normalized blocks (heading, paragraph, list, table, figure), optionally merging Stage 05 table fragments and carrying Stage 06 figure refs, while preserving cell text (only internal whitespace collapsed).” If anything differs, please correct and provide diffs.

What changed in code (ready for your review):
- Production prompt built into Stage 07: system guard + compact retry with trimmed context & optional image disable; `response_format=json_object` for OpenAI‑compatible.
- Parser: fence normalization + auto wrapper for `{title, blocks}` with missing wrapper; `parse_strategy` + `reflow_attempts` metadata.
- LiteLLM hygiene: default `temperature=0`, `top_p=1`; callback list sanitation around Router; Chutes routing `openai/<vendor>/<name>` → `<vendor>/<name>`.
- Debuggability: single‑section repro + prompt lab.

Relevant paths:
- Stage 07: `src/extractor/pipeline/steps/07_reflow_section.py`
- Prompt lab / single‑section: `debug/step07_prompt_lab.py`, `debug/reflow_single_section.py`
- Router & defaults: `src/extractor/pipeline/utils/litellm_call.py`
- Stage 05/06 (metrics, figures): `src/extractor/pipeline/steps/05_table_extractor.py`, `src/extractor/pipeline/steps/06_figure_extractor.py`

Acceptance (current milestone):
- With `openai/deepseek-ai/DeepSeek-V3.1`, Stage 07 returns strict reflow JSON (one object) for the provided section + images, with `parse_strategy` typically direct/scan, and table merges correct if fragments exist; metrics carried through.
- If GLM re‑appears at Chutes, same prompt should pass under minimal guard. If both Chutes models fail, Gemini 2.5 Flash variant of the prompt suffices.

Ask (unified diffs + tests):
- SYSTEM/USER templates (if you recommend improvements for smaller/cleaner JSON) — please return the exact strings.
- Table merge heuristic patch (if needed) to ensure cross‑page merges (page 0–1 in our test PDF) and to feed Camelot+pandas density/columns into decision.
- Any parser tweaks you recommend beyond our fence scrubbing + auto wrapper.
- A small mocked test that asserts `reflowed_json` for a fenced + verbose response (we added one; feel free to replace with your version).

Artifacts to consult:
- `scripts/artifacts/prompt_lab_runs/run_*/summary.json`
- `scripts/artifacts/reflow_single_section_*_raw.txt`
- `scripts/artifacts/reflow_single_section_*_result.json`
- `data/results/pipeline/05_table_extractor/json_output/05_tables.json` (metrics)
- `data/results/pipeline/04_section_builder/image_output/section_*.png` (images)

Thank you — please return answers and ready‑to‑apply diffs.

