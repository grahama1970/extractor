Fork: grahama1970/extractor
Branch: feat/strict-stage07-tenacity
Path: git@github.com:grahama1970/extractor.git#feat/strict-stage07-tenacity

Request: Comprehensive review of the entire Extractor pipeline (PDF + structured formats: HTML and Markdown now; note any gaps/risks for DOCX/PPTX/XLSX/EPUB), with a focus on reliability under provider limits, determinism, schema consistency, and maintainability. Please include concrete unified diffs for proposed changes.

Scope and Context
- Pipeline (01→14) under src/extractor/pipeline/steps/*.py, orchestrated by src/extractor/pipeline/run_all.py.
- PDF path (primary): 01 annotations → 02 blocks → 03 VLM header verify → 04 sections → 05 tables (Camelot) → 06 figures (crops + captions) → 07 reflow (LLM/VLM strict JSON) → …
- Structured providers (non‑PDF):
  - HTML: src/extractor/core/providers/html.py → emits UnifiedDocument directly (SourceType.HTML)
  - Markdown: src/extractor/core/providers/markdown.py → emits UnifiedDocument directly (SourceType.MD)
- Router/resilience: src/extractor/pipeline/utils/litellm_call.py (LiteLLM Router + tenacity retry wrapper)
- Recent work on this branch (strict stability):
  - Tenacity‑backed retries (429 Retry‑After + jitter; 5xx/timeouts) and Router num_retries=0
  - Stage 07 strict: tolerant JSON auto‑wrap ({blocks: …} or list → reflowed_json wrapper)
  - Env snapshot logging for Stage 06/07; Stage 03 clean PDF selection fix

Acceptance/Scenarios (please run or simulate)
1) PDF strict path (with_requirements.pdf)
   - Commands (venv + .env always):
     - source .venv/bin/activate && set -a && source .env && set +a && export PYTHONPATH=$(pwd)/src
     - python -m extractor.pipeline.steps.01_annotation_processor run data/pdfs/qb50_system_requirements_and_recommendations_marked.pdf -o data/results/pipeline
     - python -m extractor.pipeline.steps.02_marker_extractor run data/pdfs/qb50_system_requirements_and_recommendations_marked.pdf -o data/results/pipeline --output-suffix with_requirements --no-spawn
     - python src/extractor/pipeline/steps/03_suspicious_headers.py run data/results/pipeline/02_marker_extractor/json_output/02_marker_blocks_with_requirements.json --pdf-dir data/results/pipeline/01_annotation_processor -o data/results/pipeline -c 1 --dpi 150
     - python src/extractor/pipeline/steps/04_section_builder.py run data/results/pipeline/03_suspicious_headers/json_output/03_verified_blocks.json --pdf-dir data/results/pipeline/01_annotation_processor -o data/results/pipeline
     - python src/extractor/pipeline/steps/05_table_extractor.py run data/results/pipeline/04_section_builder/json_output/04_sections.json --pdf-dir data/results/pipeline/01_annotation_processor -o data/results/pipeline
     - python src/extractor/pipeline/steps/06_figure_extractor.py run data/results/pipeline/02_marker_extractor/json_output/02_marker_blocks_with_requirements.json --sections data/results/pipeline/04_section_builder/json_output/04_sections.json --pdf-dir data/results/pipeline/01_annotation_processor -o data/results/pipeline
     - MED strict reflow (selective vision):
       - export LITELLM_VLM_MODEL="${LITELLM_MED_VLM_MODEL}"
       - export STAGE07_VISION_SELECTIVE=1 STAGE07_TIMEOUT=200 MAX_CONCURRENT_LLM_CALLS=1 LITELLM_MAX_PARALLEL=1 LITELLM_NUM_RETRIES=2 LITELLM_RETRY_AFTER_MIN=0.5
       - python src/extractor/pipeline/steps/07_reflow_section.py run --sections data/results/pipeline/04_section_builder/json_output/04_sections.json --tables data/results/pipeline/05_table_extractor/json_output/05_tables.json --figures data/results/pipeline/06_figure_extractor/json_output/06_figures.json -o data/results/pipeline --timeout 200
   - Expect: 06_figures.json has captions; 07_reflowed.json present; per‑section logs under 07_reflow_section/logs/. No hidden fallbacks.

2) HTML fast-path (no reflow) and parity basics
   - Convert/prepare an HTML fixture of the BHT doc (or use an existing one) and run: provider extracts UnifiedDocument
   - Entry: src/extractor/core/providers/html.py (extract_document). Verify:
     - headings → hierarchy nodes; paragraphs, tables (if supported), images captured
     - UnifiedDocument is acceptable to Stage 10 flattening (if invoked) without reflowed_sections
   - Parity checks (manual): compare Stage 10 flatten counts vs PDF: sections/tables/figures present and reasonable.

3) Markdown path
   - src/extractor/core/providers/markdown.py (extract_document): headings → hierarchy; lists → list blocks; paragraphs
   - Confirm the UnifiedDocument schema and minimal metadata are consistent; note any gaps for Stage 10.

Reliability & Rate Limits (critical)
- File: src/extractor/pipeline/utils/litellm_call.py
  - Tenacity policy: 429 → honor Retry‑After (floor 0.5s), exponential jitter otherwise; 5xx/timeouts → retry; Fast‑fail 401/403/404/Auth/NotFound → single fallback once then fail
  - Router num_retries=0 to avoid double retries; Router timeout bounded; file logs at data/results/pipeline/logs/litellm_call.log
- Stage 07: concurrency=1; selective vision to reduce payload on text‑dominant sections.

Determinism & Schema
- Stage 05 tables: row_count/col_count present; stable ordering; deterministic summaries
- Stage 06 figures: single PDF open; concurrency bound; deterministic.json present
- Stage 07: stricter JSON extraction + auto-wrap for common variants; still enforces schema_keys presence

Security & Config hygiene
- .env usage: CHUTES_API_BASE=/v1; CHUTES_API_KEY; LITELLM_* model slugs; log redaction verified in env snapshots
- Avoid logging base64 images in full; sanitization adds truncation/sha in logs

What to Review (please include actionable diffs)
1) Reliability
   - Tenacity policy correctness: retry classes, maximum attempts, backoff caps, jitter
   - Whether Router num_retries=0 is correct for our use; recommend a proxy + Redis cooldown config if better
   - Concurrency controls and where we should add rate smoothing/globals (e.g., MED/LARGE VLM)

2) Correctness & Schema
   - Stage 07 parsing path: hardened extraction + auto-wrap — acceptable or require stricter JSON responses (response_format per provider)?
   - HTML/MD UnifiedDocument fields: ensure Stage 10 compatibility; recommend additions for tables/figures and breadcrumb handling

3) Performance & Memory
   - Stage 06: PDF reuse and semaphore sizing; suggest per‑doc caps
   - HTML provider: opportunities to avoid full DOM traversal or add table/image detection cheaply

4) Maintainability
   - Logging footprint: env snapshots, litellm_call.log; propose a standardized logger utility and sampling rules
   - Refactor opportunities: central schema helpers, shared hashing utilities

5) Security/Privacy
   - Ensure logs redact secrets; confirm no raw base64 persists outside artifacts

Clarifying Questions
1) Prefer response_format=json_object for providers supporting it (and keep relaxed fallback), or keep current hardened parsing only?
2) Should Stage 07 always include at least one figure block when figures exist (we currently tolerate missing and may auto‑add)?
3) For HTML/MD, do you want optional reflow (LLM) for longform headings, or keep them as direct UnifiedDocument only?
4) Rate‑limit governance: should we add a small per‑section jitter gate globally to reduce multi‑process thundering?

Key Paths to Inspect (relative)
- PDF pipeline steps: src/extractor/pipeline/steps/0*/**.py (esp. 03, 05, 06, 07)
- Orchestrator: src/extractor/pipeline/run_all.py
- Router/resilience: src/extractor/pipeline/utils/litellm_call.py
- Non‑PDF providers:
  - src/extractor/core/providers/html.py
  - src/extractor/core/providers/markdown.py
- Schema + conversion: src/extractor/pipeline/utils/unified_conversion.py

Smokes & Commands (quick)
- Strict PDF (sections/tables/figures → reflow): see scenario 1 command list
- HTML fast‑path: construct a small HTML fixture and run extract_document() directly; optionally add a smoke to flatten
- Markdown: same as HTML provider — verify UnifiedDocument integrity

Please respond with:
- Findings grouped by Reliability, Correctness, Performance, Maintainability, Security
- Exact unified diffs for recommended changes (patches per file)
- Any acceptance tests/smokes and precise CLI commands to reproduce

