# Fork
Fork: grahama1970/extractor
Branch: feat/step07-micro-pipeline
Path: git@github.com:grahama1970/extractor.git#feat/step07-micro-pipeline

## Comprehensive Review Request — Stage‑07 Micro‑Pipeline Redesign

Please review the new Step‑07 direction (deterministic micro‑pipeline + sparse LLM), confirm the contracts, and return unified diffs for the minimal enabling changes and any prompt/merge heuristics you recommend.

Context & Scenarios
- Pipeline must output strict `reflowed_json` per section; table fragments across pages/sections must merge deterministically; figures retain image_ref; cell text preserved.
- LLM used sparingly (paragraph polish, title/caption inference) under gates; temperature=0.
- Determinism prioritized; provenance and content_hash included for caching.

What to Review
- Proposal: scripts/artifacts/STEP07_REDESIGN_PROPOSAL.md
- Current stages: src/extractor/pipeline/steps/{04_section_builder.py,05_table_extractor.py,06_figure_extractor.py}
- Stage‑07 legacy: src/extractor/pipeline/steps/07_reflow_section.py (for comparison; will be replaced by micro‑stages)
- Utils: src/extractor/pipeline/utils/{litellm_call.py,unified_conversion.py}
- Debug tools: debug/{step07_prompt_lab.py,reflow_single_section.py}

Clarifying Questions (answer explicitly)
1) Arango names and legacy output compatibility? (see proposal #8)
2) Concurrency limits for micro‑LLM steps?
3) Hash‑based caching acceptance?
4) Keep `reflowed_json` top‑level field name?
5) Section boundary table merge now or later?

Return (Acceptance)
- Unified diffs for: Stage 04 content_hash + needs_layout_image; Stage 05 raw_table_id + normalized_label; Stage 06 normalized_label; any prompt/merge heuristic; and one minimal new file (utils/label_normalization.py).
- A small test plan (unit + scenario) verifying: content_hash stable, label normalization, and cross‑page merge.

Artifacts / Repro
- Use debug/step07_prompt_lab.py and debug/reflow_single_section.py with your preferred model list (DeepSeek V3.1 works today; GLM availability varies on Chutes).

Thank you — please provide answers and ready‑to‑apply diffs.
