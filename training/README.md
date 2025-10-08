# Calibration & Active Learning (MVP)

This directory contains schemas, scripts, and models for table (and later section) confidence calibration.

## Flow

1. User annotates objects in the tabbed UI → events appended to `annotation_events/events.jsonl`.
2. Export samples:
   ```bash
   python training/scripts/export_training_samples.py \
     --events annotation_events/events.jsonl \
     --object-type table \
     --out training/derived/table_samples.jsonl
   ```
3. Train calibrator:
   ```bash
   python training/scripts/train_table_calibrator.py \
     --samples training/derived/table_samples.jsonl \
     --out-dir training/models/table_calibrator/2025.10.0 \
     --version 2025.10.0
   ```
4. (Optional) Compare with previous:
   ```bash
   python training/scripts/promotion_decision.py \
     --new training/models/table_calibrator/2025.10.0/metrics.json \
     --old training/models/table_calibrator/2025.09.30/metrics.json
   ```
5. Promote by setting:
   ```bash
   export TABLE_CALIBRATOR_PATH=training/models/table_calibrator/2025.10.0/model.pkl
   export TABLE_CALIBRATOR_VERSION=2025.10.0
   ```

## Promotion Rules

Default gate (in `promotion_decision.py`):
- Holdout AUC improves ≥ 0.01 OR Brier improves ≥5%
- AND holdout accuracy not worse by >1%
- Minimum holdout samples: 30 (override with `--force`)

## Files

| Path | Purpose |
|------|---------|
| schemas/annotation_event.schema.json | Validates raw labeling events |
| schemas/training_sample.schema.json | Validates derived training samples |
| scripts/export_training_samples.py | Convert events → samples |
| scripts/extract_table_features.py | Recompute features from Stage 05 output |
| scripts/train_table_calibrator.py | Train + calibrate logistic model |
| scripts/promotion_decision.py | Decide if new model should be promoted |

## Reliability Curve

Stored inside `metrics.json` (holdout-based). Use to monitor calibration drift.
If mid-bin (0.4–0.6) deviation > 0.05 from diagonal, schedule retraining.

## Next extensions
- Section calibrator using heading anomalies + numeric recall
- Hallucination factor (numeric precision / foreign token ratio)
- Entity-based features for section calibration
