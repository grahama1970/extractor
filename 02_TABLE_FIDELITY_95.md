# 02_TABLE_FIDELITY_95 — Table Fidelity to 95%+ Extraction Rate

> **Goal**: Raise table_fidelity from 0.76 → 0.95+ with near-zero fragmentation.
> **Baseline**: 98.7% extraction success, 1.3% fail rate, 0.76 table fidelity.
> **Target**: 99%+ extraction success, 0.95+ table fidelity, <2% fragmentation.
> **Validated**: 2026-02-23 via /project-state assessment + /dogpile research.
> **Shadow-LEGO**: Each task follows the 6-stage self-improving pattern (hard gate → fast-path → self-grade → episodic → QRA capture → warm pond).

---

## TASK-001: ML Cross-Page Table Merge Classifier (Priority 1)

**Status**: INFRASTRUCTURE READY (merge_inference.py exists, S05c wired, env gate works)
**Blocks**: TASK-005 (adversarial validation)
**Expected Impact**: table_fidelity +0.10-0.15 (biggest single gain)
**Existing Plan**: `bright-kindling-kay.md` (approved)
**Next**: Collect labeled pairs from 12TB corpus, run /classifier-lab benchmarks

### Description

Train and deploy a vision+tabular ML classifier to replace S05c's hardcoded merge heuristics. Current heuristics (column count match, width ratio >0.9, "continued" in title) miss many cross-page table continuations and produce false merges.

### Steps

1. **Collect labeled merge pairs from 12TB corpus** (`collect_merge_data.py`)
   - Scan profiles with S05/S05c output
   - Positive pairs: tables with `merged_with`/`components` fields
   - Negative pairs: adjacent tables on consecutive pages NOT merged
   - Generate side-by-side page-half images (PubTables-v2 approach)
   - Generate 9-feature tabular vectors
   - Target: 2,000-5,000 labeled pairs

2. **Run /classifier-lab benchmarks** (vision + tabular tracks)
   - Vision: `efficientnet_b0, convnextv2_nano, convnextv2_tiny, fastvit_sa12, edgenext_small`
   - Tabular: `gradient_boosting, random_forest, logistic_regression`
   - Decision: vision F1 > tabular+0.03 → vision; else consider tabular or ensemble

3. **Full training with winning backbone** (more epochs, augmentation, early stopping)

4. **Deploy inference API** (`merge_inference.py` → `TableMergePredictor.predict()`)

5. **Wire into S05c** with `USE_MERGE_CLASSIFIER=true` env gate

### Definition of Done

```bash
# Test: ML classifier achieves F1 >= 0.95 on held-out test set
pytest tests/pipeline/test_s05c_merge_classifier.py::test_merge_classifier_f1 -v
# Assertion: f1_score >= 0.95

# Test: S05c with classifier produces fewer false merges than heuristic
pytest tests/pipeline/test_s05c_merge_classifier.py::test_classifier_vs_heuristic -v
# Assertion: classifier_errors < heuristic_errors

# Test: Full pipeline run with USE_MERGE_CLASSIFIER=true succeeds
USE_MERGE_CLASSIFIER=true python -m extractor.pipeline.run_structured --pdf <test_pdf> --out /tmp/merge_test
# Assertion: exit code 0, 05c_merged_tables.json has merge_model field
```

---

## TASK-002: OCR Fragmentation Repair Model (Priority 2)

**Status**: NOT STARTED (3-tier heuristic exists in metrics.py, needs ML upgrade)
**Blocks**: TASK-005
**Expected Impact**: table_fidelity +0.03-0.05
**Next**: Harvest fragmentation examples from corpus, train binary classifier

### Description

Upgrade the 3-tier OCR fragmentation repair (suffix patterns → regex → lookup table) with an ML classifier that distinguishes real word boundaries from OCR breaks. Feed dead-letter failures into /table-lab to discover new break patterns.

### Steps

1. **Harvest fragmentation examples from corpus**
   - Scan S05 outputs for tables with fragmentation_score > 0
   - Extract cell pairs: (broken_text, correct_text) from before/after repair
   - Collect false-positive repairs (words incorrectly merged)
   - Target: 5,000+ labeled cell pairs

2. **Train binary classifier** via /classifier-lab tabular-benchmark
   - Features: char bigrams, length ratio, is_uppercase, has_underscore, dictionary_hit
   - Labels: should_merge (true/false)
   - Compare: gradient_boosting vs logistic_regression vs current heuristic

3. **Integrate into metrics.py** as `ml_sanitize_cell()` fallback
   - Keep 3-tier heuristic as Tier 0 fast path
   - ML classifier as Tier 0.5 for ambiguous cases
   - Gated by `USE_ML_FRAGMENTATION_REPAIR=true`

4. **Feed dead letters → new patterns**
   - Extract fragmented cells from 17 dead-letter PDFs
   - Add confirmed patterns to lookup table
   - Retrain if >50 new patterns found

### Definition of Done

```bash
# Test: ML repair has higher precision than heuristic on held-out set
pytest tests/pipeline/test_ocr_fragmentation_ml.py::test_ml_repair_precision -v
# Assertion: ml_precision >= 0.98 (must not merge real words)

# Test: fragmentation_score reduces to 0 on known-fragmented tables
pytest tests/pipeline/test_ocr_fragmentation_ml.py::test_fragmentation_score_zero -v
# Assertion: fragmentation_score == 0 for all test tables

# Test: No regression on clean tables
pytest tests/pipeline/test_ocr_fragmentation_ml.py::test_clean_table_no_change -v
# Assertion: clean tables unchanged after repair
```

---

## TASK-003: S00→S05 Profile-Driven Strategy Routing (Priority 3)

**Status**: DONE ✅ (S00 table_style/domain/has_multi_column → pipeline_context → S05 routing)
**Blocks**: TASK-005
**Expected Impact**: table_fidelity +0.02-0.03
**Verified**: 11/11 pytest tests pass (test_s05_strategy_routing.py)

### Description

Wire S00 profile signals into S05 strategy selection so the correct Camelot flavor is tried FIRST (not as fallback). Currently S05 always starts with lattice_default and falls through to stream — this wastes time and misses borderless tables that need stream-specific parameters.

### Steps

1. **Map S00 signals to optimal S05 strategies**
   ```
   table_style=bordered    → lattice_default (baseline)
   table_style=borderless  → stream_default (baseline), lattice as fallback
   table_style=mixed       → try both, pick best by fragmentation score
   has_multi_column=true   → increase TABLE_HORIZONTAL_PADDING_RATIO to 0.15
   domain=scientific       → use scientific stopwords in fragmentation
   domain=defense          → lattice_strong baseline (heavy bordered tables)
   ```

2. **Modify S05 `extract_tables_from_page()`** to read pipeline_context.json
   - If S00 profile available, select baseline from mapping above
   - Fall through to full strategy sweep if baseline fails
   - Track which S00 signal drove selection for audit

3. **Add `stream_sensitive` strategy** to CAMELOT_STRATEGIES
   - `{"flavor": "stream", "params": {"edge_tol": 30, "row_tol": 5}}`
   - For borderless tables with tight spacing

4. **Test with stratified corpus sample** (defense, scientific, engineering docs)

### Definition of Done

```bash
# Test: S00 profile with table_style=borderless routes to stream first
pytest tests/pipeline/test_s05_strategy_routing.py::test_borderless_routes_to_stream -v
# Assertion: strategy_history[0] == "stream_default"

# Test: S00 profile with table_style=bordered routes to lattice first
pytest tests/pipeline/test_s05_strategy_routing.py::test_bordered_routes_to_lattice -v
# Assertion: strategy_history[0] == "lattice_default"

# Test: Mixed tables try both and pick best
pytest tests/pipeline/test_s05_strategy_routing.py::test_mixed_picks_best -v
# Assertion: final strategy has lowest fragmentation_score

# Test: No regression on existing test suite
pytest tests/smoke/test_stage05_tables_smoke.py -v
# Assertion: all existing tests pass
```

---

## TASK-004: Borderless Table Stream Optimization (Priority 4)

**Status**: DONE ✅ (stream_tight, stream_wide, stream_columns added to CAMELOT_STRATEGIES)
**Blocks**: TASK-005
**Expected Impact**: table_fidelity +0.02-0.05 (domain-dependent)
**Verified**: 7 strategies registered, params verified in test_s05_strategy_routing.py

### Description

Camelot's stream mode for borderless tables uses a single `edge_tol=50` parameter that works poorly on scientific/academic PDFs with tight spacing. Add multiple stream strategies with domain-tuned parameters, and wire /table-lab to auto-discover optimal stream parameters per domain.

### Steps

1. **Add 3 new stream strategies** to `extraction.py`:
   ```python
   "stream_tight":    {"flavor": "stream", "params": {"edge_tol": 30, "row_tol": 5}}
   "stream_wide":     {"flavor": "stream", "params": {"edge_tol": 80, "row_tol": 15}}
   "stream_columns":  {"flavor": "stream", "params": {"edge_tol": 50, "column_tol": 10}}
   ```

2. **Extend S05 fallback sweep** to include all stream strategies
   - After lattice strategies exhausted, try stream_default → stream_tight → stream_wide
   - Pick best by fragmentation_score + table_score composite

3. **Wire /table-lab `tune` to discover stream params**
   - `table-lab tune <pdf> --flavor stream` sweeps edge_tol 20-100 step 10
   - Stores optimal params as hints per S00 domain

4. **Run /table-lab tune-corpus** on 12TB corpus for borderless-heavy domains
   - Scientific/arxiv PDFs
   - Government/regulatory PDFs
   - Academic theses

### Definition of Done

```bash
# Test: stream_tight extracts borderless table with lower fragmentation than stream_default
pytest tests/pipeline/test_s05_stream_strategies.py::test_stream_tight_vs_default -v
# Assertion: tight_frag <= default_frag

# Test: All 4 stream strategies are available in CAMELOT_STRATEGIES
pytest tests/pipeline/test_s05_stream_strategies.py::test_all_stream_strategies_registered -v
# Assertion: "stream_default", "stream_tight", "stream_wide", "stream_columns" all present

# Test: S05 tries stream strategies after lattice when profile says borderless
pytest tests/pipeline/test_s05_stream_strategies.py::test_stream_fallback_sweep -v
# Assertion: strategy_history includes at least 2 stream strategies

# Test: /table-lab tune --flavor stream produces valid hints
bash -c "cd /home/graham/.claude/skills/table-lab && ./run.sh tune test.pdf --flavor stream"
# Assertion: exit code 0, hints JSON updated
```

---

## TASK-005: Dead Letter → pdf-lab Feedback Loop + Adversarial Validation (Priority 5)

**Status**: NOT STARTED
**Depends On**: TASK-001, TASK-002, TASK-003, TASK-004
**Expected Impact**: +0.5% success rate + validates all other tasks

### Description

Feed the 17 dead-letter PDFs from learn-datalake into /pdf-lab for root-cause analysis. Then run adversarial validation against a stratified 12TB corpus sample to confirm all 5 priorities achieved their targets.

### Steps

1. **Extract dead-letter PDFs** from learn-datalake state
   - Parse `memory_retry_dead_letter_count: 17` from supervisor state
   - Identify specific PDFs from run logs
   - Classify failure modes (OOM, timeout, corrupt, extraction error)

2. **Run /pdf-lab diagnose** on each dead-letter PDF
   - Identify root cause per failure
   - Generate synthetic reproductions for fixable issues
   - Write fixes back to pipeline code

3. **Adversarial validation (12TB corpus sample)**
   - Pull stratified sample: 50 PDFs (10 defense, 10 scientific, 10 engineering, 10 government, 10 mixed)
   - Run full pipeline on each with all TASK-001→004 improvements enabled:
     ```
     USE_MERGE_CLASSIFIER=true
     USE_ML_FRAGMENTATION_REPAIR=true
     USE_S00_STRATEGY_ROUTING=true
     ```
   - Measure: table_fidelity, fragmentation_score, merge accuracy, success rate

4. **Compare before/after metrics**
   - Run same 50 PDFs WITHOUT improvements (baseline)
   - Statistical comparison: paired t-test on table_fidelity scores
   - Target: p < 0.05, mean improvement >= 0.15

5. **Report and /memory learn**
   - Store results in ArangoDB pipeline_metrics
   - `/memory learn` the winning configurations per domain
   - Update learn-datalake quality gate thresholds

### Definition of Done

```bash
# Test: All dead-letter PDFs diagnosed with root cause
pytest tests/pipeline/test_dead_letter_diagnosis.py::test_all_dead_letters_diagnosed -v
# Assertion: 17/17 have root_cause field

# Test: Adversarial validation achieves target fidelity
pytest tests/pipeline/test_adversarial_validation.py::test_fidelity_target -v
# Assertion: mean_table_fidelity >= 0.95

# Test: No regression on success rate
pytest tests/pipeline/test_adversarial_validation.py::test_success_rate -v
# Assertion: success_rate >= 0.99

# Test: Statistical significance of improvement
pytest tests/pipeline/test_adversarial_validation.py::test_statistical_significance -v
# Assertion: p_value < 0.05, mean_improvement >= 0.15
```

---

## Execution Order

```
TASK-003 (S00 routing)     ──┐
TASK-004 (stream strategies) ─┤──► TASK-005 (validation)
TASK-001 (merge classifier)  ─┤
TASK-002 (OCR repair model)  ─┘
```

Tasks 1-4 can run in parallel. Task 5 validates all of them.

## Skills Involved

| Skill | Role |
|-------|------|
| `/classifier-lab` | Benchmark vision + tabular backbones for TASK-001 and TASK-002 |
| `/table-lab` | Tune stream parameters (TASK-004), discover merge patterns |
| `/pdf-lab` | Diagnose dead-letter failures (TASK-005) |
| `/learn-datalake` | Continuous extraction with improvements enabled |
| `/create-table-classifier` | Full training for merge classifier |
| `/fixture-tricky` | Generate adversarial test PDFs |
| `/memory` | Store winning configs, learn from failures |
| `/test-lab` | Adversarial blind evaluation harness |

## Metrics Dashboard

| Metric | Baseline | Target | Measured |
|--------|----------|--------|----------|
| table_fidelity | 0.76 | ≥0.95 | TBD |
| fragmentation_rate | ~24% | <2% | TBD |
| merge_accuracy | ~80% (heuristic) | ≥95% (ML) | TBD |
| extraction_success | 98.7% | ≥99% | TBD |
| stream_table_recall | unknown | ≥90% | TBD |
| dead_letter_resolved | 0/17 | ≥14/17 | TBD |
