# Task List: Close Shadow-LEGO Feedback Loop + Fix Non-Blocking Issues

**Created**: 2026-02-24
**Goal**: Fix the Tier 0.5 classifier feature mismatch, close the Shadow-LEGO feedback loop end-to-end, and clean up defense WARN documentation.

## Context

The table extraction pipeline achieves 99.8% cell accuracy and 97.5% strategy family accuracy. Three non-blocking issues remain:

1. **Tier 0.5 classifier crashes on every call** — `strategy_selector.py:183-193` builds a 3-feature vector but the trained model expects 21 features. The model loads (~1s), then fails silently. This happens on EVERY page extraction.
2. **14 defense WARNs** in synthetic corpus — these are false positives from generic column headers in synthetic PDFs, not real quality issues.
3. **Shadow-LEGO loop not closed** — harvest/train/register pipeline exists in `learn-datalake/orchestrator.py` but the strategy_selector inference code doesn't match the training schema, so the deployed model can never fire.

## Capability Overlap

- `/learn-datalake` — already has `orchestrator.py` with `run_learning_cycle()` (harvest → train → register → promote). **EXTEND**, don't rebuild.
- `/assistant` — already has model registry. **USE**, don't rebuild.
- `strategy_selector.py` — already has 3-tier cascade. **FIX** Tier 0.5 feature vector.

## Crucial Dependencies (Sanity Scripts)

| Library | API/Method | Sanity Script | Status |
|---------|------------|---------------|--------|
| joblib | `load()` model | N/A (already working) | PASS |
| sklearn | `GradientBoostingClassifier.predict()` | N/A (model exists) | PASS |

> No new dependencies. All sanity checks pass — the model loads fine, it just receives the wrong features.

## Questions/Blockers

None — all requirements clear from assessment.

## Tasks

### P0: Fix Feature Vector (Sequential — Unblocks Everything)

- [x] **Task 1**: Fix `_tier05_classifier()` feature vector to match training schema (21 features)
  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: none
  - **File**: `src/extractor/pipeline/utils/tables/strategy_selector.py`
  - **What**: Replace the 3-feature vector at lines 183-193 with the correct 21-feature vector matching `train_strategy.py:FEATURE_COLS`. Pre-sweep features (table_style one-hot, domain one-hot, category) come from S00 profile. Post-sweep features (frag_*, lattice_found, stream_found, num_strategies_tried) default to -1 or 0 since they aren't available at prediction time. Add `category` parameter to `_tier05_classifier()` and `predict_strategy()` signatures. Use label_encoder.joblib to decode predicted class index back to strategy name.
  - **Feature vector schema** (21 features + 1 encoded category = 21 total):
    ```
    table_style_borderless, table_style_bordered, table_style_mixed,
    domain_scientific, domain_defense, domain_engineering,
    num_tables (default 0), num_strategies_tried (default 0),
    max_fragmentation (default 0), has_fragmentation (default 0),
    lattice_found (default 0), stream_found (default 0),
    frag_lattice_default (-1), frag_lattice_strong (-1),
    frag_stream_default (-1), frag_stream_tight (-1),
    frag_stream_wide (-1), frag_stream_columns (-1),
    frag_agent_tuned (-1), frag_memory_learned (-1),
    category_encoded (int)
    ```
  - **Definition of Done**:
    - Test: `tests/pipeline/test_strategy_selector.py::test_tier05_classifier_feature_vector`
    - Assertion: `_tier05_classifier(table_style="bordered", domain="defense", has_borders=True)` returns a StrategyPrediction (not None), and no "features mismatch" error in logs

- [x] **Task 2**: Add post-sweep classifier confirmation call
  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: Task 1
  - **File**: `src/extractor/pipeline/utils/tables/strategy_selector.py`
  - **What**: Add a `confirm_strategy()` function that takes full post-sweep data (frag_scores dict, strategies_tried list, lattice_found count, stream_found count) and runs the classifier with ALL 21 features populated. This is the high-accuracy path (F1=0.99) since all features are available. Wire this into `log_disagreement()` — when the classifier disagrees with the sweep result AND confidence > 0.90, log a `classifier_override` event. Do NOT override the sweep result yet (shadow mode only).
  - **Definition of Done**:
    - Test: `tests/pipeline/test_strategy_selector.py::test_confirm_strategy_with_full_features`
    - Assertion: `confirm_strategy()` with full feature dict returns prediction with confidence > 0.70

### P1: Tests + Documentation (Parallel)

- [x] **Task 3**: Write/update tests for the feature vector fix
  - Agent: general-purpose
  - Parallel: 1
  - Dependencies: Task 1, Task 2
  - **File**: `tests/pipeline/test_strategy_selector.py`
  - **What**: Add these test cases:
    1. `test_tier05_classifier_feature_vector` — verify `_tier05_classifier()` builds 21-feature vector and model returns a valid prediction
    2. `test_confirm_strategy_with_full_features` — verify post-sweep confirmation with all features
    3. `test_classifier_fallback_on_missing_model` — verify graceful None return when model.joblib missing
    4. `test_label_encoder_decodes_strategy_names` — verify label_encoder.joblib maps integers to strategy names
    5. `test_predict_strategy_cascade_order` — verify Tier 0.5 runs before Tier 0 heuristic
  - **Definition of Done**:
    - Test: `pytest tests/pipeline/test_strategy_selector.py -v`
    - Assertion: All 5 new tests pass, no existing tests regress

- [x] **Task 4**: Update 02_TABLE_FIDELITY_95.md defense WARN documentation
  - Agent: general-purpose
  - Parallel: 1
  - Dependencies: none
  - **File**: `02_TABLE_FIDELITY_95.md`
  - **What**: Update the "14 defense WARNs" note to clarify these are synthetic PDF artifacts (generic integer column headers from auto-generated tables), not real extraction quality issues. All 14-16 are defense+nested_header combinations. Extraction quality is 96-100% Camelot accuracy with 0 fragmentation. No code fix needed.
  - **Definition of Done**:
    - Test: Manual verification — grep for "14 defense" in the file shows updated explanation
    - Assertion: Documentation accurately explains the WARN root cause

### P2: Validation + Integration (After Implementation)

- [x] **Task 5**: Run cell-level accuracy validator to confirm no regression
  - Agent: general-purpose
  - Parallel: 2
  - Dependencies: Task 1, Task 2, Task 3
  - **What**: Run `python scripts/validate_cell_accuracy.py` and verify overall accuracy remains >= 99.7%. The feature vector fix should not change extraction results (classifier is in shadow mode — predict but don't override). Also run `pytest tests/pipeline/test_strategy_selector.py -v` to confirm all tests pass.
  - **Definition of Done**:
    - Test: `python scripts/validate_cell_accuracy.py 2>&1 | tail -1`
    - Assertion: Output shows `cell_accuracy=99.8%` or higher; `pytest` exit code 0

- [x] **Task 6**: Run a sample extraction with classifier active to verify end-to-end
  - Agent: general-purpose
  - Parallel: 2
  - Dependencies: Task 1, Task 2, Task 3
  - **What**: Extract 3 synthetic PDFs (1 bordered/defense, 1 borderless/scientific, 1 thin_grid/medical) with `STRATEGY_SELECTOR_MODE=shadow` and verify:
    1. No "features mismatch" errors in logs
    2. `05_strategy_outcomes.jsonl` contains `predicted_strategy` with confidence > 0
    3. Classifier predictions logged (even if they disagree with sweep)
  - **Definition of Done**:
    - Test: Extract 3 PDFs, check logs for classifier prediction messages
    - Assertion: 0 "Classifier prediction failed" errors in logs; strategy outcomes show non-null predictions

## Completion Criteria

- [x] All tasks marked [x]
- [x] `pytest tests/pipeline/test_strategy_selector.py -v` passes all 24 tests (15 existing + 9 new)
- [x] `python scripts/validate_cell_accuracy.py` shows 99.8% overall accuracy (56,752/56,847 cells)
- [x] No "Classifier prediction failed: X has 3 features" errors — classifier builds correct 21-feature vector
- [x] 02_TABLE_FIDELITY_95.md documents defense WARN root cause (synthetic PDF artifacts)

## Notes

- The trained model (F1=0.99) was trained on 12,328 samples with post-sweep features. Pre-sweep predictions (features default to -1) will have lower accuracy — this is expected and fine for shadow mode. The post-sweep `confirm_strategy()` call gets the full F1=0.99 accuracy.
- `STRATEGY_SELECTOR_MODE` remains `shadow` (default). The model predicts and logs but doesn't override the brute-force sweep. Promotion to `active` mode is gated by the existing `check_promotion_gate()` in the orchestrator.
- The learn-datalake supervisor wiring (periodic re-harvest/retrain) is already implemented in `orchestrator.py:run_learning_cycle()`. No additional wiring needed — it runs when table-lab tune-corpus completes.
