# Generalized Copilot Request — Patch + Answers (No PRs, No Links)

**AGENT INSTRUCTIONS**
Remember to commit and push the current branch to the repo first.
Do NOT IGNORE.

**Project**

- Fork/Repo: <OWNER/REPO>
- Branch: <BRANCH>
- Path: <GIT_SOURCE_WITH_BRANCH>

**Task**

- Comprehensive pipeline review and targeted hardening for SciLLM-only extractor (no bespoke wrappers, async-only calls), plus small reliability/tooling fixes.

**Context (brief)**

- The PDF extraction pipeline was migrated to SciLLM (Chutes) only; litellm legacy paths should be removed. We’ve seen intermittent hangs due to shell xtrace/quoting and JSON parsing that assumes string-only.
- Goal: produce a minimal, safe unified diff that removes remaining litellm/shims, normalizes JSON mode handling, and eliminates ad-hoc wrappers, improving robustness across diverse PDFs.

**Review Scope (relative paths)**

- Primary pipeline stages (focus correctness, brittle bits, ad-hoc helpers):
  - src/extractor/pipeline/steps/01_annotation_processor.py
  - src/extractor/pipeline/steps/03_suspicious_headers.py
  - src/extractor/pipeline/steps/05_table_extractor.py
  - src/extractor/pipeline/steps/06_figure_extractor.py
  - src/extractor/pipeline/steps/06a_title_caption_enricher.py
  - src/extractor/pipeline/steps/06b_layout_sketcher.py
  - src/extractor/pipeline/steps/07_reflow_section.py
  - src/extractor/pipeline/steps/08_lean4_theorem_prover.py
  - src/extractor/pipeline/steps/09_section_summarizer.py
  - src/extractor/pipeline/steps/11_arango_create_graph.py
- LLM adapter and utils (normalize JSON dict-or-string, async use of SciLLM, remove litellm):
  - src/llm_adapter/adapter.py
  - src/extractor/pipeline/utils/litellm_response_utils.py
  - src/extractor/pipeline/utils/litellm_call.py (should be removed)
- Runners/tools/docs (hangs/xtrace, PDF annotation safety, doc drift):
  - scripts/run_simple.sh
  - scripts/tools/pipeline_xtrace.sh (NEW: propose array-based xtrace runner)
  - scripts/tools/remove_pdf_annotations.py
  - AGENTS.md
  - SCILLM_USAGE.md
  - README.md (LLM usage references)

**Objectives**

- Remove litellm shim and any remaining imports/usages; adopt SciLLM `acompletion` across pipeline (no httpx fallbacks).
- Normalize JSON mode response handling to accept either dict or string in `choices[0].message.content` with a single helper; fix Stage 07 “empty content” cases.
- Eliminate ad-hoc/bespoke SciLLM wrappers; call SciLLM directly and consistently.
- Add a safe xtrace runner (`scripts/tools/pipeline_xtrace.sh`) using array-based exec, trapping errors, and saving per-stage logs to avoid “hang” misdiagnosis.
- Ensure annotations are stripped from input PDFs (never mutate originals); keep `remove_pdf_annotations.py` as the canonical tool.
- Tighten docs: AGENTS.md/SCILLM_USAGE.md/README to reflect SciLLM-only, async-only policy.

**Constraints**

- Unified diff only, inline in a single fenced block.
- No PRs, no hosted links, no extra commentary.
- Include a one-line commit subject inside the patch.
- Numeric hunk headers only (`@@ -old,+new @@`).
- Patch must apply cleanly on branch <BRANCH>.

**Acceptance (we will validate)**

- `rg -n "litellm_call|chutes_scillm|achutes_chat|httpx"` → no matches under `src/extractor/` (except tests, if added).
- Stage 07 no longer errors on “LLM returned empty content” for JSON dict content; a small local run writes non-empty JSON outputs.
- `scripts/tools/pipeline_xtrace.sh` produces per-stage `.out/.err` and a summary JSON; no shell quoting-induced early exits.
- Docs reflect SciLLM-only async policy; example commands are consistent.

**Deliverables (STRICT — inline only; exactly these sections, in this order)**

1. **UNIFIED_DIFF:**

```diff
<entire unified diff here>
```

2. **ANSWERS:**

- <Answer to dependencies/models>
- <Answer to schema drift>
- <Answer to safety/guards>
- <Answer to tests/smokes>
- <Answer to performance/timeouts>
- <Answer to observability/summary lines>

**Clarifying Questions (answer succinctly in the ANSWERS section; if unknown, reply `TBD` + minimal dependency needed)**

- Dependencies/data sources: Should we pin CHUTES_* models from your tenant’s `/v1/models`, or keep env-driven?
- Schema drift: Should exporters/parsers tolerate renamed/missing keys with warnings or fail-fast with smokes?
- Safety: Confirm never mutating PDFs under `data/input/`; is a global guard desired?
- Tests/smokes: Which deterministic smokes must pass locally (JSON present, counts > 0), and which are CI-only?
- Performance: Any preferred default concurrency/timeout for SciLLM `acompletion` (e.g., 6–12 workers, 60–120s)?
- Observability: What minimal summary lines should stages print (counts, failures, path to artifacts)?

**Output Format (must match exactly; no extra text):**
UNIFIED_DIFF:

```diff
<entire unified diff here>
```

ANSWERS:

- <answers to: deps, schema drift, safety, tests, performance, observability>

