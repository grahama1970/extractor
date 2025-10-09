# Table Merge Modes (Stage 07)

| Env Var | Values | Default | Description |
|---------|--------|---------|-------------|
| `STAGE07_TABLE_MERGE_MODE` | off \| strict \| assist \| llm | strict | Controls deterministic merge application |
| `STAGE07_TABLE_MERGE_HARD` | float 0–1 | 0.75 | Auto-merge threshold (strict) |
| `STAGE07_TABLE_MERGE_SOFT` | float 0–1 | 0.45 | Ambiguity / candidate lower bound |
| `STAGE07_TABLE_MERGE_MAX_ROWS` | int | 10000 | Safety cap on merged rows |
| `STAGE07_LLM_TABLE_MERGE_DECISIONS` | path | — | Deterministic adjudication file (JSON) |
| `STAGE07_TABLE_MERGE_USE_LLM` | 0/1 | 0 | Allow live LLM adjudication (requires model) |
| `STAGE07_LLM_MODEL` | string | — | Model name (when LLM adjudication enabled) |
| `STAGE07_TABLE_LOW_CONF_DENSITY` | float | 0.25 | Density threshold for low confidence |
| `STAGE07_TABLE_LOW_CONF_MIN_ROWS` | int | 2 | Minimum rows to avoid low-confidence classification |

## Scoring Formula

```
score = 0.40*header_similarity
      + 0.25*iou_x
      + 0.20*page_proximity
      + 0.15*row_pattern_score
```

Where:
- `header_similarity`: Jaccard on normalized header tokens
- `iou_x`: horizontal span IoU
- `page_proximity`: 1.0 (same page) or 0.5 (next page) else 0
- `row_pattern_score`: 1.0 for header+body, 0.6 for body+body, 0 otherwise

## Mode Semantics

| Mode | Auto-Merge | Ambiguity Recorded | LLM Adjudication |
|------|------------|--------------------|------------------|
| off | No | No | No |
| strict | Yes (score ≥ HARD) | Yes (SOFT ≤ score < HARD) | No |
| assist | No | Yes (score ≥ SOFT) | No |
| llm | No | Yes (score ≥ SOFT) | Yes (via plugin) |

## Artifacts

| File | Purpose |
|------|---------|
| `07_reflowed.json` | Final structural + (maybe) merged tables |
| `07_table_merge_adjudication.json` | LLM or decision file adjudication results (llm mode) |

LLM prompt is deliberately minimal & structural to avoid semantic drift. Low-confidence tables or failing structural criteria are skipped without a call.
