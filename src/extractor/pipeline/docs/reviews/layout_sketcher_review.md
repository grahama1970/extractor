# Layout Sketcher: Token‑Light, Section‑Aware Summaries

## Repo / Branch
- Repo: `experiments/extractor`
- Branch: `feature/annotator-cleanup`

## Purpose
- We replaced heavy “full-section image” artifacts with a deterministic, token-light layout sketch per section to help downstream LLM steps (table merge, text reflow) understand structure without large images.
- Each section is summarized as nested bullets: Section → Page → Elements (tables with shape/density/acc/area; grouped text snippets). Snippets are short head/tail plus counts to keep tokens low.

## Relevant Files
- `scripts/generate_enhanced_walkthrough.py` (layout sketch generation)
- `walkthrough.md`, `scripts/artifacts/visuals_pipeline/walkthrough_local.md` (rendered output)
- Data inputs: `data/results/pipeline/06b_layout_sketcher/json_output/06b_layout_sketch.json`, `05_tables.json`, `04_sections.json`, `07_reflowed.json`

## Current Approach (high level)
1. Read 06b layout JSON; group text per page by column + proximity.
2. Summarize per section (using 04/07 section levels) → per page.
3. Tables: show shape, density, camelot acc, area, title (up to 3 per page).
4. Text: top 3 groups per page; head/tail (60 chars), char counts, block counts.
5. Hierarchy is numbered and indented; intended to be fed section-by-section to an LLM.

## Rationale
- Remove reliance on large images; keep deterministic, small text summaries.
- Preserve cues needed for table merge (sizes/areas) and text reflow (column grouping, order).
- Reduce token load by truncating snippets and limiting per-page items.

## Open Questions for Copilot
1. Are the per-page table fields sufficient (shape, density, acc, area), or should we add bbox height/width to aid merge heuristics?
2. Is limiting text to top 3 groups/page too aggressive for wide pages, or is it adequate for merge/reflow decisions?
3. Should we emit a single “dominant column” flag per page (e.g., >60% of chars) to guide reflow?
4. Would shorter snippets (e.g., 40/40) further reduce tokens without harming understanding?
5. Any benefit to emitting normalized y0 ordering for text groups (already in order) to strengthen reflow cues?

## Known Trade-offs
- We dropped connectors/overlays; pairing relies on order + labels.
- Text grouping is heuristic (column + small y-gap); may over-merge dense lists.
- Only top 3 tables/text groups per page to stay token-light.

## How to Reproduce Artifacts
```bash
source .venv/bin/activate && set -a && [ -f .env ] && source .env && set +a
python scripts/generate_enhanced_walkthrough.py
```
Outputs:
- `scripts/artifacts/visuals_pipeline/walkthrough_local.md`
- Annotated PNGs in `scripts/artifacts/visuals_pipeline/`

## Suggested Review Focus
- Does the section→page→element nesting give enough context for merges/reflow?
- Are the chosen per-table metrics the right minimal set?
- Should we emit more/less text group detail for LLM efficiency?

