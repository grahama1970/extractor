# Evals Execution Tasks (Multimodal Reflow)

Scope: Advance the LLM evals for Stage 07 reflow to consistently choose the cheapest accurate multimodal model. Annotations are explicitly out of scope for this tasks list and will be discussed separately with reference to `src/extractor/pipeline/steps/01_annotation_processor.py`.

## A. Vision Gate, Stability, Determinism
- [ ] Add explicit `--require-vision/--no-require-vision` flag to `run_llm_evals.py` (default: require vision for Stage 07 profile).
- [x] Use `preflight_vision_support()` to gate models that reject images (fail early in evals).
- [x] Generate larger preflight image inline (default 256x256 PNG) to avoid Gemini Flash rejecting tiny images. Env: `VISION_PREFLIGHT_SIZE`.
- [ ] Record `vision_capable` and preflight errors in per-item metrics (e.g., `fail_reason: vision_rejected`).
- [x] Deterministic defaults in harness (temperature=0, top_p=1; provider-specific params dropped by LiteLLM).

## B. Dataset Expansion & Hints
- [ ] Add 3–5 varied sections to `src/extractor/evals/datasets/registry.json` (multi-page merged tables, figure-adjacent tables, OCR-ish text).
- [ ] Ensure section images are ≥256x256 (or resized) to avoid provider image rejections.
- [ ] Include Stage 05 table hints (columns + shape) for each new section.

## C. Pricing & Cost
- [ ] Replace placeholder per‑1K rates for OpenAI and Gemini with verified current pricing (note source URL + date).
- [x] Keep OpenRouter Qwen3 and Moonshot Kimi rates verified (already added from vendor pages).
- [ ] (Optional, later) Add a flag-gated pricing refresher that can update `ratecards.yaml` from official docs; keep static by default to avoid brittleness.

## D. Eval Run & Recommendation
- [ ] Run full multimodal eval (require vision) for: `gemini/gemini-2.5-flash`, `moonshot/kimi-k2-turbo-preview`, `openai/gpt-5-mini` (and `openai/gpt-5` for reference).
- [ ] Confirm per-model artifacts exist: raw, parsed, metrics, usage, cost; ensure fail reasons are captured when not ok.
- [ ] Confirm summary aggregates and “cheapest passing” recommendation is stable across expanded dataset.

## E. Pipeline Defaults & Docs
- [x] Set Stage 07 default to `gemini/gemini-2.5-flash` in code; allow override via `LITELLM_VLM_MODEL`.
- [ ] Document the default and how to override (README/note in Stage 07 docs).
- [ ] Keep a secondary “budget text-only” profile documented (e.g., OpenRouter Qwen3) but not used for Stage 07.

## F. Metrics & Debuggability
- [x] Accept `reflowed_json` as dict with `blocks` or list of blocks; accept `ocr_corrections` as dict or list; `improvements_made` as str or list; accept `columns` or `header`.
- [ ] Add explicit metrics fields for: `fail_reason`, `missing_titles`, `columns_mismatch`, `rows_out_of_tolerance`, `missing_top_keys`, `vision_rejected`.
- [x] Keep asserts tunable via CLI: `--row-tol`, `--text-min-chars`, `--assert-has-keys`, `--assert-pass`.
- [x] Persist `run_manifest.json` with git SHA, env, model registry, registry.json.

## G. Operations & Safety
- [ ] Add budget cap CLI `--max-cost` (soft stop once exceeded).
- [ ] Provide two model lists: `models.yaml` (multimodal default) and `models_text_only.yaml` (budget, not used for Stage 07).
- [ ] Add a small weekly eval (1–2 docs) to sanity-check recommendation and detect drift in accuracy/pricing; keep within budget.

## H. Commands (examples)
- Full run with defaults and strict asserts (multimodal):
  - `python src/extractor/evals/scripts/run_llm_evals.py --task reflow --assert-pass`
- Single model (debug):
  - `python src/extractor/evals/scripts/run_llm_evals.py --task reflow --models data/evals/models_gemini.yaml --assert-pass`
- Loosen row tolerance (15%) and raise text threshold (200 chars):
  - `python src/extractor/evals/scripts/run_llm_evals.py --task reflow --row-tol 0.15 --text-min-chars 200 --assert-pass`

## I. Out of Scope (Annotations)
- Annotations-driven evals (box + nearby FreeText with an id pointing to expected JSON) are not included here.
- We will discuss the design and integration with `src/extractor/pipeline/steps/01_annotation_processor.py` before creating an annotations tasks list.

