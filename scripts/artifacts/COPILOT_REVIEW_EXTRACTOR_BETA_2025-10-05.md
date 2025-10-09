Fork: grahama1970/extractor
Branch: feat/step07-iteration3-diffs
Path: git@github.com:grahama1970/extractor.git#feat/step07-iteration3-diffs

Title: Beta Readiness Review — Full Extractor Pipeline (PDF/HTML/Markdown, VLM + Text)

Context
- End-to-end pipeline is running to completion for the with_requirements PDF with deterministic artifacts, vision header verification, table/figure extraction, and section reflow.
- We patched Router retry-after handling in our wrapper to prevent TypeError on 429 without Retry-After, and added a probe. Stage 06 now has MED→LARGE→SMALL VLM escalation with tunable timeouts.
- This review covers all supported formats (pdf, html, markdown) and the pipeline code across utils + steps.

Live Scenarios (current env)
- Vision models in .env:
  - SMALL: openai/chutesai/Mistral-Small-3.1-24B-Instruct-2503
  - MED:   openai/Qwen/Qwen2.5-VL-72B-Instruct
  - LARGE: openai/Qwen/Qwen3-VL-235B-A22B-Instruct
- Text (large): openai/deepseek-ai/DeepSeek-R1
- Completed artifacts for with_requirements (today):
  - 02: data/results/pipeline/02_marker_extractor/json_output/02_marker_blocks_with_requirements.json
  - 03: data/results/pipeline/03_suspicious_headers/json_output/03_verified_blocks.json
  - 05: data/results/pipeline/05_table_extractor/json_output/05_tables.json
  - 06: data/results/pipeline/06_figure_extractor/json_output/06_figures.json (captions present)
  - 07: data/results/pipeline/07_reflow_section/json_output/07_reflowed.json
  - Event log: data/results/pipeline/pipeline_events.log (start/end + counts/hashes for each stage)

What changed recently (highlights)
- Determinism: sorted outputs + content_hashes for 02/03/05/06; stage start/end JSONL events.
- Stage 06: robust description flow with model escalation (MED→LARGE→SMALL), concurrency=1, env timeouts; accepts plain caption when JSON not returned.
- litellm_call: set Router retry_after default=0.5; added retry-after floor to avoid None→TypeError; added probe script in debug/chutes/.
- Logging: start/summary logs for 05/06/07; improved 03 clean-PDF selection.

Questions
1) Vision routing & resiliency
  - Are MED→LARGE→SMALL retries placed optimally (timeouts, retries)? Recommend any specific backoff or jitter adjustments?
  - Should 07 reflow attach vision only for specific anchors to reduce provider load?
2) Determinism & schema
  - Any remaining places where ordering or hashes should be added (e.g., 07 reflow block ordering)?
  - Is the current figures/tables schema sufficient for downstream exporters?
3) litellm Router patch
  - Would you accept a minimal PR to scillm to floor retry-after at the Router layer? Any preferred location for the guard (Router init vs retry calc)?
4) HTML/Markdown pipelines
  - Please review HTML/Markdown converters and integrators for parity with PDF stages (02/03/05/06/07). Identify missing gates, timeouts, or schema inconsistencies.

Please provide
- Point-by-point answers (numbered) and unified diffs for improvements.

Files of interest (relative paths)
- src/extractor/pipeline/steps/02_marker_extractor.py
- src/extractor/pipeline/steps/03_suspicious_headers.py
- src/extractor/pipeline/steps/05_table_extractor.py
- src/extractor/pipeline/steps/06_figure_extractor.py
- src/extractor/pipeline/steps/07_reflow_section.py
- src/extractor/pipeline/utils/litellm_call.py
- src/extractor/pipeline/utils/pipeline_event_logger.py
- src/extractor/core/converters/ (pdf/html/md)
- src/extractor/core/providers/ (pdftext integration)
- debug/chutes/router_retry_floor_probe.py

Acceptance
- Aim for concrete, minimal diffs to harden availability/latency and align schemas across formats, while preserving determinism.
