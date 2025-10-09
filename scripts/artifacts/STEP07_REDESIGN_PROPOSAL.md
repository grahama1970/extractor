# Fork
Fork: grahama1970/extractor
Branch: feat/step07-micro-pipeline
Path: git@github.com:grahama1970/extractor.git#feat/step07-micro-pipeline

## Step‑07 Redesign Proposal (Deterministic Micro‑Pipeline + Sparse LLM)

This document captures the amended Stage‑07 approach discussed: a deterministic assembler with narrowly scoped, optional LLM refinements, grounded in the current code reality (Stages 04–06 and utils).

Contents
1) Problem restatement (based on actual code)
2) Target end‑state for Stage 07
3) Gap analysis tied to current code
4) Amended design (phases + contracts)
5) Concrete enabling changes for 04/05/06
6) Proposed new Step‑07 micro‑modules
7) Arango alignment
8) Clarifying questions
9) Enabling diffs (safe pre‑07)
10) Next actions
11) Defaults if no answers

---

## 1. Problem Restatement (From Current Code)
- Stage 04 builds sections and `section_hash` (title‑based) but not a full content hash of body text.
- Stage 05 explicitly avoids multi‑page merging; picks a single best per page; fragments exist for later reconciliation.
- Stage 06 extracts figures with IDs, optional captions.
- No integrated step computes section content hash for caching, captures cross‑refs, merges across section boundaries, or gates LLM polish.

## 2. Target End‑State (New Stage 07)
A slice of deterministic preprocess + sparse micro LLM calls + final assembly.

Substages
- 07a_canonicalize (no LLM): canonical per‑section JSON + continuity merges + content_hash
- 07b_polish_paragraphs (gated): only for noisy paragraphs; temp=0
- 07c_infer_table_titles (gated): only for null/weak titles
- 07d_refine_figure_captions (gated): only for weak/short captions
- 07e_assemble (no LLM): final reflow structure + provenance

Guardrails
- Never change table cell text (collapse internal whitespace only).
- Always emit provenance (content_hash, counts).
- Use section image only if `needs_layout_image` true.

## 3. Gap Analysis
- Need full `section_content_hash`.
- Need table continuity merging logic across pages/sections.
- Need stable `raw_table_id` and optional `normalized_label` (Table X‑Y).
- Need label normalization for figures (Figure X‑Y).
- Need simple paragraph noise gating.
- Need cache directory layout keyed by `section_content_hash`.

## 4. Amended Design (Contracts)
- 07a output per section includes: paragraphs[], tables[] (with density, merged_from, normalized_label, image_ref), figures[] (fid, image_ref, caption_candidate, normalized_label), `needs_layout_image`, `content_hash`.
- 07b/07c/07d produce small maps pid→polished_text, tid→title, fid→caption.
- 07e assembles `reflowed_json` + `provenance` with explicit counts.

## 5. Enabling Changes (Pre‑07)
- Stage 04: compute `section_content_hash` (title + text blocks); add `needs_layout_image` via simple dispersion heuristic.
- Stage 05: preserve `raw_table_id`; add `normalized_label` if caption/title matches pattern; do not merge.
- Stage 06: add `normalized_label` for figures from caption/description when found.

## 6. Proposed New Files
- src/extractor/pipeline/steps/07a_section_canonicalizer.py
- src/extractor/pipeline/steps/07b_paragraph_polish.py
- src/extractor/pipeline/steps/07c_table_title_infer.py
- src/extractor/pipeline/steps/07d_figure_caption_refine.py
- src/extractor/pipeline/steps/07e_assemble_reflow.py
- src/extractor/pipeline/utils/label_normalization.py
- tests for each substage + scenario harness

## 7. Arango Alignment
- Upsert blocks with `_key` = `blk::<docId>::<tid|fid>`; keep `normalized_label`, `section_id`, `content_hash`.
- Cross‑ref extraction for paragraphs to populate `references` edge collection.

## 8. Clarifying Questions
1) Arango collection names (sections, blocks, references)?
2) Keep legacy `07_reflowed.json` in addition to micro‑stage output? (yes/no)
3) Max parallel LLM calls per doc? (default 4)
4) Enable hash caching from day one? (yes/no)
5) Preserve `reflowed_json` as top‑level name? (yes/no)
6) Merge across section boundaries now? (yes/no; if yes, in 07a)
7) Offline switch to disable all LLM micro tasks? (env flag)

## 9. Enabling Diffs (Pre‑07)
See proposed diffs in COMPREHENSIVE_REVIEW_STEP07_REDESIGN.md or request me to apply them now.

## 10. Next Actions
- Answer questions → I generate the 07a–07e code + tests.
- Or “Proceed with defaults” (see below) and I will deliver the full bundle now.

## 11. Defaults (If No Answers)
- collections: sections, blocks, references, unresolved_refs
- keep legacy 07_reflowed.json alongside new 07e output
- LLM micro concurrency: 4
- enable hash caching: yes
- preserve reflowed_json: yes
- section‑boundary merge: yes (in 07a)
- offline flag: STAGE07_DISABLE_LLM
