# Extractor Prompt Library Playbook

Purpose: keep every LLM prompt used by the extractor pipeline in one place, fully spelled out (system + user), defensively structured, copy/pasteable for critique, and gated by Kimi-based grading.

Guidelines (mirrors memory/devops prompt conventions + CONTRACT prompt hardening)
- **Self-contained**: Each file shows exactly what we send (system + user). No hidden defaults.
- **Defensive**: JSON-only guard, soft targets (length), explicit empty-output rules, anti-hallucination guidance.
- **Examples/Placeholders**: Minimal inline examples; runtime placeholders like `{section_text}` documented.
- **Token-efficient**: Put meta-instructions in system; user payload references them instead of repeating.
- **Drift control**: Code loads prompts from `src/extractor/pipeline/prompts/*.json`; docs mirror the live text.
- **Critique + grading**: Every prompt must have a stored Kimi critique (see `docs/prompts_extractor/GRADE_PROMPT.md`) under `docs/prompts_extractor/critiques/NAME.json`. The prompt audit fails if any critique is missing or reports P0/P1. Max 3 grading attempts per prompt; more than 3 attempts is a hard fail until fixed.
- **Agent-driven loop**: The project agent owns running Kimi grading, applying fixes to the canonical prompt (`src/extractor/pipeline/prompts/NAME.json`) and its doc mirror, rerunning grading, and saving the passing critique. Humans don’t need to patch prompts manually once the agent is instructed.
- **Rules reference**: Follow `docs/prompts_extractor/PROMPT_RULES.md` (aligned with memory/devops PROMPT_RULES) before grading to avoid common P0/P1 issues.

How to add/update a prompt
1) Edit the live JSON under `src/extractor/pipeline/prompts/NAME.json`.
2) Mirror the same content under `docs/prompts_extractor/NAME_PROMPT.md` (system + user + notes). No placeholders or ellipses in docs.
3) Produce a ready-to-send example payload in the doc (real PDF snippets). Include base64 image URLs where applicable.
4) Run Kimi grading using `docs/prompts_extractor/GRADE_PROMPT.md`; save the critique to `docs/prompts_extractor/critiques/NAME.json` with fields: `overall`, `highest_severity`, `attempts`, `findings`.
5) Run `PYTHONPATH=src uv run scripts/prompt_audit.py`. Audit fails if any critique is missing, has P0/P1, or attempts > 3.
6) Ensure the pipeline step loads via `prompt_loader.load_prompt(NAME)`; avoid inline literals.

Current prompts
- `01_annotation_processor.json`
- `03_suspicious_headers.json`
- `07_reflow_section.json`
- `09_section_summarizer.json`

Next to externalize (follow same pattern)
- 08 Lean4 theorem prover prompt
- 09a annotator (if any LLM use) / other LLM steps
