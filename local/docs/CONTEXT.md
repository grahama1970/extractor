# CONTEXT.md - Learn Datalake / Review PDF Handoff

**Last Updated**: 2026-02-20 (session 3)
**Session Focus**: Shadow-LEGO implemented in actual code
**Primary Working Repo**: `/home/graham/workspace/experiments/pi-mono` (skills)
**Secondary Repo**: `/home/graham/workspace/experiments/extractor` (pipeline code)

---

## Current State

- `learn-datalake` supervised loop running: `corpus_1771594040`, 8 workers, `--inline-review`
- Supervisor PID: active, restart_count: 255
- Memory server: healthy on port 8601
- `SHADOW_S00=true` enabled in extractor .env

### Pipeline Quality (Prior Run, 350 verdicts)

334 PASS (95.4%), 14 WARN (4.0%), 2 FAIL (0.6%). Average score ~0.94.

### Shadow-LEGO Implementation (THIS SESSION)

**All three Shadow-LEGO components are now implemented in actual code:**

#### 1. Shadow S00 Classifier (Seed Producer) — DEPLOYED
- **Training data**: 724 samples harvested from corpus (S00 profiles + S05 actual outcomes)
- **Labels**: `needs_stream` (356), `no_tables` (348), `lattice_sufficient` (20)
- **Model**: GradientBoosting, CV macro_F1=0.584, full-data F1=0.98
- **Top features**: page_count (0.16), columns (0.12), estimated_sections (0.10), font_body_size (0.08)
- **Inference**: `ShadowS00Predictor.predict(profile)` returns `needs_stream`, `stream_confidence`, `class_probabilities`
- **Files**:
  - `create-table-classifier/scripts/harvest_shadow_s00.py` — Training data harvester
  - `create-table-classifier/scripts/train_shadow_s00.py` — Model training
  - `create-table-classifier/scripts/shadow_s00_inference.py` — Inference API
  - `create-table-classifier/models/shadow-s00/shadow_s00_model.joblib` — Trained model

#### 2. S05 Pipeline Integration — DEPLOYED
- **Env var**: `SHADOW_S00=true` in `extractor/.env`
- **Behavior**: When Shadow S00 predicts `needs_stream` with confidence >= 0.6, S05 tries `stream_default` strategy FIRST (before lattice). This is a seed — not a gate. Stream still runs as fallback regardless.
- **File**: `src/extractor/pipeline/steps/s05_table_extractor.py` — `_get_shadow_s00_prediction()` + strategy reordering in `extract_all_tables()`
- **Logging**: Shadow prediction stored in `quality_summary["shadow_s00"]` for observability

#### 3. Co-evolutionary Feedback Loop — DEPLOYED
- **Recording**: After inline review scores table_fidelity, `shadow_s00_feedback.record_shadow_feedback()` stores the verdict as training signal
- **Retrain trigger**: When 50+ new verdicts accumulate, `check_retrain()` returns True
- **Auto-retrain**: `trigger_retrain()` merges feedback with original training data and retrains
- **File**: `create-table-classifier/scripts/shadow_s00_feedback.py`
- **Wired into**: `inline_reviewer.py` Step 5d (after content ingestion)

### Bug Fixes This Session

1. **S05 Stream Mode Never Fired** — Removed S00 gate, stream always runs as fallback
2. **Memory Learn VIRTUAL_ENV Mismatch** — Added `_clean_env()` to strip inherited venv vars
3. **Memory Service store.py Taxonomy Gate** — Exempted datalake scopes from bridge validation

### Key Files Modified

- `src/extractor/pipeline/steps/s05_table_extractor.py` — Shadow S00 integration + stream always runs
- `pi-mono/.pi/skills/extractor-quality-check/inline_reviewer.py` — Feedback recording (Step 5d)
- `pi-mono/.pi/skills/extractor-quality-check/review_memory.py` — VIRTUAL_ENV cleanup
- `pi-mono/.pi/skills/extractor-quality-check/inline_review_loop.py` — VIRTUAL_ENV cleanup
- `pi-mono/.pi/skills/create-table-classifier/scripts/harvest_shadow_s00.py` — NEW: Data harvester
- `pi-mono/.pi/skills/create-table-classifier/scripts/train_shadow_s00.py` — NEW: Model training
- `pi-mono/.pi/skills/create-table-classifier/scripts/shadow_s00_inference.py` — NEW: Inference API
- `pi-mono/.pi/skills/create-table-classifier/scripts/shadow_s00_feedback.py` — NEW: Co-evolutionary feedback
- `memory/src/graph_memory/lessons/store.py` — Datalake scope exemption

### Next Steps

1. **Monitor Shadow S00 impact** — verify stream prioritization improves table_fidelity
2. **Accumulate 50+ feedback verdicts** → auto-retrain Shadow S00 with co-evolutionary signal
3. **Graph-based parameter transfer** — query ArangoDB for similar PDFs' extraction params (not yet implemented)
