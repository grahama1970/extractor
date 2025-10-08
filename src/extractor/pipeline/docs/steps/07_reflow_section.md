# Stage 07 – Reflow Section (Summary‑Only Baseline)

Stage 07 produces a normalized reflowed representation of each section before downstream requirement mining (Stage 07r).
This baseline implementation defaults to summary‑only mode (no LLM calls) for determinism and reliability.

## Inputs

| Source Stage | File |
|--------------|------|
| Stage 04 | 04_section_builder/json_output/04_sections.json |
| Stage 05 | 05_table_extractor/json_output/05_tables.json |
| Stage 06 | 06_figure_extractor/json_output/06_figures.json |

## Output

```
07_reflow_section/
  json_output/
    07_reflowed.json        # { reflowed_sections: [...] }
    07_reflow_error.json    # (only if consolidation failed)
  stage_07_reflow.log       # JSON summary: counts, hash, summary_only flag
```

Minimal schema (summary‑only):

```json
{
  "reflowed_sections": [
    {
      "id": "S1",
      "title": "Intro",
      "blocks": [
        { "type": "paragraph", "text": "System shall ..." }
      ],
      "tables": [ /* Stage 05 pass‑through (pandas_df/pandas_metrics) */ ],
      "figures": [ /* Stage 06 pass‑through */ ],
      "reflowed_text": "System shall ...",
      "reflow_status": "summary_only"
    }
  ]
}
```

## Environment Flags

| Variable | Effect |
|----------|--------|
| `SUMMARY_ONLY07=1` | Forces summary‑only mode (overrides CLI) |
| `STAGE07_REQUIREMENTS_MINER=0` | Skips Stage 07r in run_all |
| `STAGE07_DEBUG=1` | Adds quick_summary snippets to help QA |

## Failure Modes & Artifacts

| Condition | Artifact | Action |
|-----------|----------|--------|
| Missing / unreadable Stage 04/05/06 JSON | 07_reflow_error.json | Inspect paths; ensure upstream stages ran |
| Empty sections array | 07_reflowed.json (empty list) | Allowed; 07r will emit empty requirements |
| Post‑run file missing (in run_all) | run_all raises with details | Fix Stage 07 invocation or set SUMMARY_ONLY07=1 |

## Rationale

- Summary‑only path guarantees downstream 07r progress.
- Deterministic hash enables QA diffing without LLM variance.
- Schema normalization avoids silent misses in requirement mining.

## Next Enhancements (Optional)

1. Reintroduce LLM/VLM reflow behind `--enable-llm` or `STAGE07_ENABLE_LLM=1`.
2. Add paragraph ordering heuristics for multi‑column PDFs.
3. Integrate figure/table cross‑references.

