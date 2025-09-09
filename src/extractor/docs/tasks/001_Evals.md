# Evals Suite — Cheapest Accurate Models and Extraction Settings

Owner: extractor team  
Goal: Build an evals/ suite to select the cheapest accurate LLMs per pipeline task (e.g., Stage 07 reflow, annotations) and to tune Camelot/PDF extraction parameters against gold standards.

## Objectives
- [ ] Cheapest‑accurate model selection for Stage 07 reflow (section JSON/blocks) and annotations.
- [ ] Ground‑truthed accuracy against gold datasets (strict, robust checks with normalization & tolerances).
- [ ] Cost‑aware evaluation using provider‑reported cost when available; otherwise token‑based estimate.
- [ ] Extraction quality evals for Camelot and PDF text normalization strategies.
- [ ] Strong reproducibility & provenance for every run (deterministic params, manifests).

## Code References
- Chat adapter (Chat‑only): `src/extractor/pipeline/utils/litellm_call.py`
- Chat helpers: `src/extractor/pipeline/utils/model_params.py` (build_chat_messages, build_chat_extras)
- Stage 07 reference (prompt/shape): `src/extractor/pipeline/steps/07_reflow_section.py`
- Robust JSON clean: `src/extractor/core/services/utils/json_utils.py` (clean_json_string)
- Example eval script (manual): `tests/stage07_manual/007_llm_evals.py`

## Pricing URLs
- Moonshot (Kimi): https://platform.moonshot.ai/docs/pricing/chat  
  JS fallback snapshot: https://r.jina.ai/http://platform.moonshot.ai/docs/pricing/chat
- OpenAI: https://openai.com/api/pricing
- Google (Gemini): https://ai.google.dev/pricing
- Anthropic: https://www.anthropic.com/pricing
- OpenRouter models: https://openrouter.ai/models (confirm model slugs and per‑1K pricing)

## Directory Layout (to add under src/extractor/evals/)
- [ ] `llm/` — LLM eval harnesses and metrics
  - [ ] `harness.py` — unified Chat runner (concurrency, retries, logging)
  - [ ] `models.yaml` — model registry (provider, name, extras, enabled)
  - [ ] `prompts/` — task prompts (e.g., reflow_section_system.txt)
  - [ ] `tasks/` — per‑task drivers (e.g., `reflow_section.py`, `annotations.py`)
  - [ ] `metrics/` — scoring (`reflow_metrics.py`, `annotation_metrics.py`)
- [ ] `extraction/` — Camelot/PDF evaluation
  - [ ] `camelot_eval.py` — parameter sweeps + metrics vs gold
  - [ ] `pdf_eval.py` — text normalization strategies + contiguity metrics
- [ ] `providers/`
  - [ ] `ratecards.yaml` — primary source of per‑1K input/output USD rates (manually curated)
  - [ ] `pricing_fetchers.py` — optional fetch/parse pricing (Moonshot/OpenAI/Gemini/Anthropic) with TTL cache (off by default to avoid brittleness)
  - [ ] `cost_utils.py` — compute run cost; prefer provider‑reported cost
- [ ] `datasets/`
  - [ ] `registry.json` — list of PDFs, pages, tasks, hints
  - [ ] `gold/` — gold JSON for reflow/tables/annotations
- [ ] `utils/` — shared helpers (`image.py`, `io.py`, `json_norm.py`, `timing.py`)
- [ ] `scripts/` — CLIs (`run_llm_evals.py`, `run_extraction_evals.py`, `summarize.py`)
- [ ] `schemas/` — JSONSchemas for gold and eval outputs (validators)
- [ ] `reports/` — optional HTML/MD summaries (latency, accuracy, cost)

Outputs
- [ ] `data/evals/runs/<timestamp>/<task>/<model>/` (raw, parsed, usage, cost, logs)
- [ ] `data/evals/summaries/<task>.json` (aggregated results + recommendation)
- [ ] `data/evals/runs/<timestamp>/run_manifest.json` (dataset subset, commit SHA, CLI flags, model registry hash, env info)

## Phase 1 — LLM Eval MVP (Reflow / Stage 07)
- [ ] Implement `llm/harness.py`
  - [ ] Standard Chat call via `litellm.acompletion` (no Responses path)
  - [ ] Add `response_format={"type":"json_object"}` for OpenAI only
  - [ ] Robust parsing (strip code fences; `clean_json_string`)
  - [ ] Determinism: default `temperature=0`, `top_p=1`; record model version, provider, all params, prompt text
  - [ ] Concurrency + retry with jitter/backoff; per‑provider concurrency caps
  - [ ] Budget: CLI `--max-cost`, `--max-requests`; dry‑run to estimate tokens/cost
  - [ ] Resume/idempotency: skip completed via hashed `(prompt, inputs, model, params)`
  - [ ] Save request/response artifacts; capture provider‑reported cost if present; redact PII
  - [ ] Emit `run_manifest.json` with git SHA and env info
- [ ] `llm/models.yaml`
  - [ ] Register: `openai/gpt-5-mini`, `openai/gpt-5`, `gemini/gemini-2.5-flash`, `moonshot/kimi-k2-turbo-preview` (enable flags)
  - [ ] Optional: Qwen via OpenRouter (add a model slug like `openrouter/qwen/qwen2.5-72b-instruct` or a VL variant; confirm exact slug on OpenRouter; set `OPENROUTER_API_KEY`)
- [ ] `llm/prompts/reflow_section_system.txt`
  - [ ] Requirements (dataset‑driven): expected counts for tables/figures read from `datasets/registry.json`; default for our seed set: 1 table + 1 figure
  - [ ] Titles “INFERRED: …”; contiguous text block (≥150 chars); preserve reading order
  - [ ] Explicitly forbid changing table cell values or spelling inside tables; allow spelling fixes outside tables
- [ ] `llm/tasks/reflow_section.py`
  - [ ] Compose user content from section context + (optional) section image data URL
  - [ ] Include Table Hints from Stage 05 (columns, shape) when available
- [ ] `llm/metrics/reflow_metrics.py`
  - [ ] Checks: parsable JSON with `reflowed_json`; table/figure counts match dataset expectations; titles inferred
  - [ ] Table headers: normalization (NFKC, case/punct/space folding), order‑insensitive compare or permutation‑aware match
  - [ ] Rows: row count within tolerance (e.g., ±10%) plus sampled cell exact‑match rate; header Jaccard score
  - [ ] Text: good contiguous text (support `text` or `content` fields), contiguity score optional
- [ ] `scripts/run_llm_evals.py`
  - [ ] CLI: `--task reflow`, `--models all|subset`, `--dataset-registry`
  - [ ] CLI additions: `--resume`, `--shard N/K`, `--max-cost`, `--max-samples`, `--seed`, `--parallel`, `--fail-fast`, `--only models.yaml:enabled`
  - [ ] Writes artifacts under `data/evals/runs/<ts>/llm/reflow/<model>/`

## Phase 2 — Pricing + Cost Utilities
- [ ] `providers/pricing_fetchers.py`
  - [ ] Optional fetch (behind flag); normalize per‑1K input/output USD and record `pricing_fetched_at`, `source`, `unit`
  - [ ] Moonshot Kimi: parse $/1M and convert to $/1K (e.g., Turbo Preview input 0.0024/1K miss, output 0.01/1K)
  - [ ] Fallback to r.jina.ai snapshot for JS‑heavy pages
  - [ ] 24h TTL cache to `data/evals/pricing_cache.json`; manual overrides
- [ ] `providers/cost_utils.py`
  - [ ] `calc_cost(model, usage, response_cost, pricing_map)`; prefer provider cost; fallback to tokens×rate
  - [ ] Standardize output schema: `{ provider_cost: { reported: <float|null>, estimated: <float|null>, pricing_source: <url|ratecard>, fetched_at: <ts> } }`
  - [ ] Accumulate per‑doc and per‑run costs

## Phase 3 — Datasets & Gold Standards
- [ ] `datasets/registry.json`
  - [ ] Fields: `pdf_path`, `pages`, `tasks`, `hints` (columns/shape), `expected_tables`, `expected_figures`, `split`, `dataset_version`, `license`, `language`, `ocr_required`, `notes`
- [ ] `datasets/gold/`
  - [ ] Gold for Stage 07 reflowed_json (order, merged table, figure, text)
  - [ ] Gold tables (columns, row count, sample cells)
  - [ ] Gold annotations (entities/labels/spans)
- [ ] `gold_validator.py` — schema validator + diff tool to explain metric failures
- [ ] Checksums (MD5/SHA256) for PDFs and gold files

## Phase 4 — Camelot & PDF Extraction Evals
- [ ] `extraction/camelot_eval.py`
  - [ ] Parameter sweeps: `flavor(lattice|stream)`, `edge_tol`, `shift_text`, `line_scale`, `table_areas`, `process_background`
  - [ ] Page selection: fixed pages, auto table‑dense pages
  - [ ] Metrics vs gold: column count match, header Jaccard, row count ratio, sampled cell exact match, merged table correctness
  - [ ] Output: best params per doc; Pareto (accuracy vs runtime)
  - [ ] Docs: https://camelot-py.readthedocs.io
- [ ] `extraction/pdf_eval.py`
  - [ ] Text normalization strategies (PyMuPDF config, hyphenation fixes, whitespace/encoding normalization)
  - [ ] Contiguity metrics (paragraph merge, noise reduction)
  - [ ] Downstream readiness: % meaningful text; improvement to Stage 07 metrics
 - [ ] Vision inputs: enforce image size limits, record image bytes count/hash, preflight logs
 - [ ] Optional baselines: pdfplumber/tabula for reference (later phase)

## Phase 5 — Annotations Eval (Stage 01‑like)
- [ ] `llm/tasks/annotations.py` — prompt to produce structured annotations
- [ ] `llm/metrics/annotation_metrics.py` — precision/recall/F1; span overlap; label normalization

## Phase 6 — Stress Suite & Recommendations
- [ ] `datasets/stress/` — noisy OCR, fragmented multi‑page tables, rotated scans, figures near tables, mixed language PDFs
- [ ] `scripts/summarize.py`
  - [ ] Aggregate pass rate, accuracy, cost/doc, latency
  - [ ] Record p50/p95 latency and error rate (timeouts, non‑JSON); gate on stability
  - [ ] Filter to models passing strict gates; pick cheapest; also present top‑2 with trade‑offs (cheapest vs fastest)
  - [ ] Save to `data/evals/summaries/<task>.json`

## Phase 7 — CI & Developer UX
- [ ] Add lightweight scheduled run (nightly/weekly) on small canonical set to refresh pricing cache and sanity‑check recommendations
- [ ] `EVALS.md` usage doc (this file); examples and contribution guidance

## Initial Targets (Cheapest‑Accurate)
- [ ] Reflow (Stage 07): compare `moonshot/kimi-k2-turbo-preview`, `gemini/gemini-2.5-flash`, `openai/gpt-5-mini` on 3–5 gold PDFs; gate on merged table+figure with inferred titles, table shape match, contiguous text; choose lowest cost passing model
- [ ] Camelot: run param sweeps on 3 table‑heavy PDFs; produce recommended params per doc family (specs, academic PDFs, scans)

## Commands (after scaffolding)
- [ ] `python -m extractor.evals.scripts.run_llm_evals --task reflow --models all --dataset-registry src/extractor/evals/datasets/registry.json`
- [ ] `python -m extractor.evals.scripts.run_extraction_evals --target camelot`
- [ ] `python -m extractor.evals.scripts.summarize --task reflow`

## Acceptance Criteria
- [ ] Deterministic, reproducible runs stored under `data/evals/runs/<timestamp>/...`
- [ ] Summary JSON exists per task with cheapest accurate model recommendation
- [ ] Pricing sourced from `ratecards.yaml`; optional auto‑fetch (flagged) with TTL cache; provider `response_cost` used when available
- [ ] Gold comparisons enforce strict structure + content for reflow and tables
- [ ] Camelot eval produces actionable param profiles and Pareto trade‑offs
 - [ ] Run manifests include commit SHA, prompt text, model versions, and params; artifacts redact PII

## Notes
- Keep all LLM calls Chat‑only (no OpenAI Responses path).  
- Use data URL images to avoid external downloads (see `utils/vision.py` preflight update).
- Standardize JSON schema across providers; allow minor field naming differences (e.g., text under `text` or `content`).
- OpenRouter / Qwen: set `OPENROUTER_API_KEY` (and optional `OPENROUTER_API_BASE`) in env. Confirm model slug on https://openrouter.ai/models and add it to `llm/models.yaml`. Pricing entries live in `providers/ratecards.yaml`.
  - NOTE: We also accept `OPEN_ROUTER_API_KEY` as an alias and map it to `OPENROUTER_API_KEY` in the harness for convenience.
  - Example slug added: `openrouter/Qwen3-235B-A22B-2507`.

## Future Iterations (Annotations as Ground Truth)
- Add an annotations‑driven eval track where users add a box annotation with a nearby FreeText note and provide an ID that points to a JSON file of the expected result. The eval harness will:
  - Parse the annotations from the PDF (box + FreeText),
  - Load the referenced expected JSON by ID,
  - Run extraction and compare against expected results with strict metrics.
- This yields clear, document‑embedded expected outputs that make accuracy judgments unambiguous for extraction steps.
