# Prompt Hardening Task List (Extractor)

Owner: project agent (execute when directed)
Goal: every LLM prompt passes Kimi grading (no P0/P1, <=3 attempts) and prompt audit is green.

## Steps per prompt
1) Run Kimi grading using `docs/prompts_extractor/GRADE_PROMPT.md` with the prompt + example payloads from the matching `*_PROMPT.md` doc.
2) Save critique to `docs/prompts_extractor/critiques/<prompt>.json` with fields: `overall`, `highest_severity`, `attempts`, `findings`.
   - Must satisfy: `overall=pass`, `highest_severity` ∈ {P2, info}, `attempts<=3`.
3) If Kimi flags issues, update the canonical prompt `src/extractor/pipeline/prompts/<prompt>.json` and the doc mirror `docs/prompts_extractor/<prompt>_PROMPT.md`, then re-grade (up to 3 times).
4) After all prompts have passing critiques, run:
   ```bash
   PYTHONPATH=src uv run scripts/prompt_audit.py \
     --prompts-dir src/extractor/pipeline/prompts \
     --docs-dir docs/prompts_extractor \
     --critiques-dir docs/prompts_extractor/critiques
   ```
   Audit must exit 0.

## Prompts to grade (current set)
- 01_annotation_processor
- 03_suspicious_headers
- 07_reflow_section
- 09_section_summarizer

## Status log
- [ ] 01_annotation_processor: critique stored? attempts ≤3? highest_severity ≤ P2?
- [ ] 03_suspicious_headers: critique stored? attempts ≤3? highest_severity ≤ P2?
- [ ] 07_reflow_section: critique stored? attempts ≤3? highest_severity ≤ P2?
- [ ] 09_section_summarizer: critique stored? attempts ≤3? highest_severity ≤ P2?
- [ ] Prompt audit passes (`scripts/prompt_audit.py`).

Note: No placeholders or ellipses are allowed in docs; example payloads must be fully concrete (include base64 images where applicable). Runtime loads must use `prompt_loader` per SCILLM paved-path contract.
