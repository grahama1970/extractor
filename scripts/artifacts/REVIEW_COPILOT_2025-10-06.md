Fork: grahama1970/extractor
Branch: feat/pdfplumber-numeric-audit
Path: git@github.com:grahama1970/extractor.git#feat/pdfplumber-numeric-audit

# Request: Focused Diagnostic + Comprehensive Review

We need help diagnosing a SciLLM client usage issue and a broader review for maintainability and determinism. Please answer questions inline and propose unified diffs for fixes.

## 0) Blocker Summary (Diagnostic Needed First)

- Symptom: Direct SciLLM client calls (imported as `litellm`, the client module shipped by scillm) sometimes reject `api_key` on the async path with `AuthenticationError: The api_key client option must be set…`, while the sync path works. We’ve standardized the eval harness on the sync client to proceed, but we want a clean async path and removal of workarounds.
- What we tried: Passing `api_key` and `base_url` explicitly; also setting `OPENAI_API_KEY` env when `provider=openai`. The error persists on `acompletion` but not on `completion` for the same inputs.

Please help determine whether this is:
1) a client bug (async path ignoring explicit `api_key`/`base_url`),
2) an argument name mismatch between client versions,
3) an environment precedence issue (env overrides vs kwargs), or
4) incorrect provider routing for Chutes (`provider=openai`, `base_url=https://llm.chutes.ai/v1`).

Deliverables for this diagnostic:
- Minimal patch (unified diff) that makes async calls work with explicit `api_key`/`base_url` and no env reliance.
- If the fix belongs in scillm client, suggest the upstream diff; otherwise provide the repo-side diff (central helper or corrected param names).

Reproducer:
- File: `scripts/evals/chutes_eval.py`:line 1
- Function: `_call_json_scillm_direct` (uses `litellm.completion` now). Change to `litellm.acompletion` with equivalent args and confirm no auth error.

## 1) Project Context

- Purpose: PDF→structured pipeline with LLM/VLM stages. Stages 01/03/06/07 include LLM/VLM calls; 05/06 have determinism concerns; 07 reflow requires LLM.
- Determinism: We introduced deterministic mode guidance; added figure/table ordering and summaries; plan to centralize flags.
- Evaluations: Added `scripts/evals/chutes_eval.py` to probe Chutes SOTA models and optional local Ollama student models.

## 2) Live Features and Scenarios

- Scenarios runner: `scenarios/run_all.py`:line 1 (CI/local smokes and pipeline scenarios)
- UX prototype: `prototypes/tabbed/html` (React+Vite, not the focus of this review but present)
- Pipeline stages of interest:
  - `src/extractor/pipeline/steps/01_annotation_processor.py`:line 1
  - `src/extractor/pipeline/steps/03_suspicious_headers.py`:line 1
  - `src/extractor/pipeline/steps/06_figure_extractor.py`:line 1
  - `src/extractor/pipeline/steps/07_reflow_section.py`:line 1

## 3) What Changed Recently (so you can diff intent)

- New: `scripts/evals/chutes_eval.py` — ScillM client direct calls, provider routing for Chutes/Ollama, optional Ollama discovery, student-size filter.
- Adjusted: `src/extractor/pipeline/utils/scillm_call.py` exists but is being phased out; eval harness no longer uses it.

## 4) Clarifying Questions for You

1) SciLLM client surface
   - Expected canonical import: `import scillm as client` vs `import litellm as client`? The package publishes as “scillm” but currently exposes the module surface via `litellm`. Should we always import `litellm` until a `scillm` module is exported?
2) Async call parameters
   - Confirm the correct param names for the async client to honor explicit `api_key` + `base_url` for non-OpenAI endpoints (Chutes). Should we set `base_url` or `api_base`? Any provider-specific kwarg needed?
3) Provider routing
   - Is `custom_llm_provider='openai'` with `base_url='https://llm.chutes.ai/v1'` the correct route for Chutes in the current client? If not, please propose the exact arguments.
4) Response schema
   - We always request `response_format={"type":"json_object"}`. Any issues with this on the Chutes route under SciLLM?
5) Removal plan
   - We intend to remove `scillm_call.py` and `litellm_call.py`, and call the client directly in stages 01/03/06/07. Any pitfalls or recommended shared helper for only provider/env resolution (not a wrapper)?

## 5) Files to Review (paths are repo‑relative)

- Eval harness: `scripts/evals/chutes_eval.py`:line 1 (focus: `_call_json_scillm_direct`)
- Pipeline LLM sites to convert to direct SciLLM client calls next:
  - `src/extractor/pipeline/steps/01_annotation_processor.py`:line 1
  - `src/extractor/pipeline/steps/03_suspicious_headers.py`:line 1
  - `src/extractor/pipeline/steps/06_figure_extractor.py`:line 1
  - `src/extractor/pipeline/steps/07_reflow_section.py`:line 1
- Transitional helper (to be removed): `src/extractor/pipeline/utils/scillm_call.py`:line 1

## 6) Acceptance for Diagnostic Fix

- Running: `uv run scripts/evals/chutes_eval.py --model openai/zai-org/GLM-4.5-Air --no-record`
- Expected: Table shows `ok=true` using async client (no env hacks beyond CHUTES_*), no AuthenticationError, stable latency similar to current sync run.

## 7) Broader Review Ask (after diagnostic)

Please provide a concise, prioritized set of diffs to:
- Migrate stages 01/03/06/07 to direct SciLLM client usage (remove wrappers), with strict JSON, bounded concurrency, and deterministic toggles.
- Centralize provider/env routing in a tiny helper (no call wrapper), e.g., returns `{provider, base_url, api_key}` for text/vlm tiers.
- Confirm deterministic outputs for stages 05/06 (existing summaries) and propose any missing stable sorts/tie-breakers.

Thank you — please include unified diffs in your response.

