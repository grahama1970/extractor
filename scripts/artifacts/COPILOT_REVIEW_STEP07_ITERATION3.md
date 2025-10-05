Fork: grahama1970/extractor
Branch: feat/step07-iteration3-diffs
Path: git@github.com:grahama1970/extractor.git#feat/step07-iteration3-diffs

Title: Step‑07 Micro‑Pipeline – Continuity, Prompts/Gates, Arango Hardening (Iteration 3) – Request for Comprehensive Code Review

Context
- We split legacy Stage 07 into a micro‑pipeline for clarity and guardrails.
- Live features: continuity merge across sections (tables), gated paragraph polish, gated table‑title inference, gated figure‑caption refine, final reflow assembler, and Arango export scaffolding.
- LLM/VLM calls are required for the polish/infer/refine steps; they are temp=0 and gated to reduce hallucinations and drift.

What changed in this iteration (high‑leverage refinements)
- 07a_section_canonicalizer: tighter continuity heuristic (env‑tunable thresholds), vertical‑gap guard, provenance reason codes; deterministic ordering preserved.
- 07b_paragraph_polish: stricter system intent (no rephrase), suppression radius env multiplier, output length inflation cap.
- 07c_table_title_infer: density threshold (env) and explicit non‑hallucination instruction.
- 07d_figure_caption_refine: length gate env override, placeholder/generic guards, clarified system intent; CLI accepts --verified03.
- 07f_arango_export: collection existence checks, basic retry, optional ignore‑errors env.
- New regression test: test_07a_no_false_merge.py to prevent spurious continuity merges.

Primary Files to Review (relative paths)
- src/extractor/pipeline/steps/07a_section_canonicalizer.py
- src/extractor/pipeline/steps/07b_paragraph_polish.py
- src/extractor/pipeline/steps/07c_table_title_infer.py
- src/extractor/pipeline/steps/07d_figure_caption_refine.py
- src/extractor/pipeline/steps/07f_arango_export.py
- tests/pipeline/steps/test_07a_no_false_merge.py

Execution Notes (local)
- Typical run (Stage 07a → 07e → 07f) expects Stage‑03/05/06 artifacts under data/results/pipeline.
- Env toggles for review:
  - CONTINUITY_DICE_THRESHOLD, CONTINUITY_JACCARD_THRESHOLD, CONTINUITY_TOP_PAGE_Y_CUTOFF, CONTINUITY_MIN_COLS_JACCARD, CONTINUITY_MAX_VERTICAL_GAP
  - PARA_NOISE_THRESHOLD, PARA_SUPPRESS_RADIUS_MULT, PARA_LEN_INFLATION_CAP
  - TABLE_INFER_MIN_DENSITY
  - FIGURE_REFINE_MAX_LEN
  - ARANGO_IGNORE_ERRORS

Clarifying Questions for Reviewers
1) Continuity heuristic: Are the defaults (Dice/Jaccard 0.75, min_cols=3, vertical_gap<=420px) appropriate, or should we tighten/loosen for wide‑but‑shallow tables? Any suggested additional cues that are cheap to compute?
2) Paragraph polish: Is the “no rephrase” system guidance sufficiently constraining across your chosen model? Would you prefer a JSON contract and wrapper enforcement instead of plain text?
3) Table title inference: Is the min density gate at 0.35 a reasonable default on your docs? Any failure modes you’ve seen where density is high but titles are still risky to infer?
4) Figure caption refine: Are the placeholder/generic guards adequate, or should we add a stricter lexical whitelist/banlist?
5) Arango export: Do you want hard failures on any HTTP error (current default), or should we always continue with logged errors for staging clusters?

Acceptance Focus
- No false merges across sections (test_07a_no_false_merge.py guards this).
- Provenance continuation_reason present when continuity occurs.
- Gated LLM paths avoid structural rewrites and cap length inflation.
- Arango export is resilient (collections ensured; one retry) and fails loudly when appropriate.

Please provide
- Answers to the clarifying questions above.
- Unified diffs for any suggested code changes (minimal, targeted patches preferred).
- Optional: quick sanity scenarios or additional tiny tripwire tests you’d add.

Thanks!

