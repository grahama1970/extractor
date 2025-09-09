Awesome start—this is already quite thorough. Below is a tight review: what’s solid, gaps that will bite you later, a few logic traps, and concrete add-ons you can paste back into the checklist.

# What looks solid

* Clear separation of **LLM evals**, **extraction evals**, **pricing/cost**, and **datasets**.
* Explicit **outputs** and **artifacts** layout.
* Early focus on **cost-per-accuracy** and **provider-reported cost**.
* Stress suite + CI hooks are in scope. ✅

# Missing pieces / high-impact gaps

1. **Reproducibility & provenance**

   * Pin **temperature=0, top\_p=1**, seed where supported, and **record model version**, provider, params, **prompt text**, and **git SHA**.
   * Emit a **run\_manifest.json** per run (dataset subset, commit, CLI flags, model registry hash, env info).
   * Store provider **raw HTTP** (redacted) and **tokenizer versions** if available.

2. **Budget, rate limiting & stability**

   * Global **max-budget per run**, **per-provider concurrency**, **exponential backoff/jitter** on 429/5xx, and **resume** (skip already-completed items).
   * “Dry-run” mode to estimate **cost and duration** without calling models.
   * Deterministic sharding of datasets for parallel CI.

3. **Dataset governance**

   * Dataset and gold **versioning** (semantic version + checksum/MD5), **licenses**, and **provenance**.
   * Train/dev/test **splits** (don’t tune prompts/params on the same gold you report).
   * Schema **validator** for gold files + a **diff tool** to explain metric failures.

4. **Metrics robustness (Reflow & Tables)**

   * Table header matching should allow **order-insensitive** compare + **string normalization** (case, punctuation, Unicode, spaces).
   * Row checks: “rows ≥ baseline” can be gamed (duplication). Use **row recall/precision** or **row-count tolerance** + **sampled cell exact-match rate**.
   * Figure detection: some sections have **0 or >1 figures/tables**. Either add **task metadata** that specifies expected counts or allow **graceful N=0/≥1** policies per section.
   * Text quality: ≥150 chars is arbitrary. Add **contiguity score** (avg paragraph length, merge ratio) and **noise ratio** instead.

5. **Annotation evals (Phase 5)**

   * Define an **ontology** / allowed labels, **normalization** rules, **micro/macro F1**, **partial span credit** (IoU/character overlap), and **inter-annotator agreement** baseline if human gold varies.

6. **Pricing & cost**

   * Normalize **currencies** and **units** (\$/1K tokens vs \$/1M). Cache **timestamp & source URL** in pricing\_map.
   * If provider returns `response_cost`, note its **coverage** (some exclude tool/image costs).
   * Handle **image pricing** distinctly where applicable and **context window truncation** (cost ≠ accuracy if content is dropped).

7. **Vision / image handling**

   * Enforce **image size limits**, base64 **truncation checks**, and consistent **downscale** policy with stored **preflight logs**.
   * Record **image bytes** or **hash** used in the request (reproducibility).

8. **Extraction eval breadth**

   * Add **pdfplumber / tabula** or at least a **baseline extractor** to anchor Camelot gains.
   * For OCR scans, include a **Tesseract (or equivalent) path** and metrics; otherwise the stress suite won’t be comparable.

9. **Security/PII & compliance**

   * Redact PII in saved artifacts; configurable **redaction rules**.
   * Separate **secret material** (API keys) from artifacts; document retention policy.

10. **Dev UX**

* CLI: `--resume`, `--shard N/K`, `--max-cost`, `--max-samples`, `--seed`, `--parallel`, `--fail-fast`, `--only models.yaml:enabled`.
* A small **HTML/MD report** summarizing p50/p95 latency, accuracy, cost, stability.

# Logic/consistency issues to fix

* **“EXACTLY 1 table & 1 figure”** (prompt + metrics): This will mis-score valid sections. Either:

  * Encode expectations in `datasets/registry.json` per section (`expected_tables`, `expected_figures`) **or**
  * Change gate to **“≥0, ≤1 required”** based on metadata.
* **Columns == hints (strict)**: Order and minor normalization will fail good outputs. Use **normalized set or permutation-aware match** with tolerances.
* **“rows ≥ baseline”**: Replace with **row count within tolerance** (e.g., ±10%) plus **cell-level exact-match sample** and **header Jaccard**.
* **OpenAI-only `response_format`**: Good, but ensure non-OpenAI paths have robust **JSON fence stripping + retry-with-stricter prompt** fallback.
* **“Attach user session id”**: If this is a PII, make it optional or hashed; document why it’s needed.
* **`_hidden_params.response_cost`**: Don’t rely on internal/private fields; standardize on a wrapper schema `provider_cost.reported` with provenance.

# Concrete additions you can drop in

## Directory Layout (augment)

* [ ] `reports/` — HTML/MD summaries with charts (accuracy, p50/p95 latency, cost/doc)
* [ ] `schemas/` — JSONSchema for gold and outputs; validators
* [ ] `mocks/` — provider stubs for CI without spend

## Phase 1 — LLM Eval MVP (add)

* [ ] Determinism: default `temperature=0`, `top_p=1`; record all request params and tokenizer family.
* [ ] Budget control: `--max-cost`, `--max-requests`, per-provider concurrency & backoff.
* [ ] Resume & caching: skip completed samples; hash `(prompt, inputs, model, params)` for idempotency.
* [ ] Redaction: scrub PII from saved artifacts.

## Phase 2 — Pricing (add)

* [ ] Currency normalization (USD), **unit tests** for unit conversions.
* [ ] Record `pricing_fetched_at`, `source`, `unit` in cache; allow manual overrides per model.

## Phase 3 — Datasets (add)

* [ ] `registry.json` fields: `dataset_version`, `license`, `split`, `expected_tables`, `expected_figures`, `language`, `ocr_required`.
* [ ] `gold_validator.py` + CI step to validate schemas.
* [ ] Checksums (MD5/SHA256) for PDFs and gold files.

## Phase 4 — Extraction (add)

* [ ] Baselines: pdfplumber/tabula runs for comparison.
* [ ] OCR track for scan PDFs; log OCR config and language packs.
* [ ] Throughput metrics (pages/s), CPU/MEM stats to inform Pareto curves.

## Phase 5 — Annotations (add)

* [ ] Ontology config with aliasing; **strict vs lenient** scoring modes.
* [ ] Metrics: character-level and token-level IoU; micro/macro F1; calibration of thresholds.

## Phase 6 — Stress & Recommendations (add)

* [ ] Stability: **error rate** (non-JSON, timeouts) as a gating metric.
* [ ] Recommend **top-2** with trade-offs (cheapest vs fastest), not only a single winner.

## Phase 7 — CI & DX (add)

* [ ] PR check: run **small canary** subset with mocks + 1 live sample capped by `--max-cost`.
* [ ] Nightly schedule respects **budget ceiling**; alerts when pricing changes beyond threshold.
* [ ] Publish `reports/last.html` as CI artifact.

## Prompts/metrics clarifications

* [ ] Reflow prompt: explicitly **forbid changing table cell values** and **spelling in tables**; allow spelling fixes **outside** tables.
* [ ] Metrics: normalize strings (NFKC), collapse whitespace, case-insensitive compare for headers; keep tables strict.

# Small nits / clarifications

* Include **latency stats** (p50/p95) in `summarize.py`.
* Add `--models file:models.yaml#enabled` convenience filter.
* Record **context truncation** (input tokens vs model limit) to avoid silent accuracy loss.
* Consider a simple **dashboard script** that renders charts from summaries.

---

If you want, I can turn these into PR-ready TODO checkboxes and a couple of JSONSchemas (gold + reflow output) so you can wire validators immediately.
