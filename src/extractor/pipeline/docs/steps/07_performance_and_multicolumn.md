# Stage 07 Performance & Multi-Column Addendum

## New Environment Flags

| Variable | Default | Description |
|----------|---------|-------------|
| STAGE07_ENABLE_MULTICOLUMN | 1 | Enable heuristic multi-column detection & reordering |
| STAGE07_MULTICOLUMN_X_GAP | 40 | X-gap threshold (px) to separate column clusters |
| STAGE07_TABLE_MERGE_STRICT_GUARDS | 1 | Enable extra negative feature penalties in table merging |
| STAGE07_TABLE_MERGE_MAX_AUTO | 20 | Cap on auto merges per document (strict mode) |

## Multi-Column Heuristic

1. Cluster textual blocks by their bbox.x0 using a gap threshold.
2. If ≥2 clusters with at least 2 blocks each, reorder columns left→right, within each column top→bottom.
3. Set `multi_column_hint: true` in the section for downstream awareness.
4. No semantic reconstruction beyond ordering; safe fallback.

## Table Merge Strict Guards

Additional penalties applied if enabled:
- Large vertical gap (>30% combined table heights) -> penalty
- Extreme row disparity (min/max < 0.05) -> penalty
- >60% short (≤3 char) headers -> penalty
- Penalties may downgrade auto_merge to ambiguous.

## Resume Token Strengthening

Stage 07 skip now requires:
- 07_reflowed.json
- 07_reflow_manifest.json
- deterministic.json
- 07_resume_token.json
- Matching hash + plugins + plugin_versions + coherent mtimes

## Performance Metrics

`run_all_summary.json` aggregates per-stage:
```
{
  "total_duration_ms": ...,
  "stage_metrics": [
    {"stage":"02_marker_extractor","duration_ms":...,"rss_delta_mb":...},
    ...
  ]
}
```

Used for CI trend tracking.

