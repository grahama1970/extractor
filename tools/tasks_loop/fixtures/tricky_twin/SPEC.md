# SPEC: Tricky Twin Fixture

## Overview

This is a synthetic fixture generated from `twin_profile.yml`.
It is designed to stress-test the extractor with:

- Ambiguous Headers (False Positives for S05).
- Trap Requirements (False Positives for S08).
- Embedded "Section Start" text in Tables (Traps for S05/S06).
- Strictly verified Critical Content.

## Requirements

- All items in `_expected.json` MUST be extracted.
- NONE of the False Positives (e.g. "REQ-FAKE") should be extracted.
- Critical Content must match 100%.

## Tables

- Tables must be extracted exactly (Score > 80%).

## Lessons Learned (Calibration Phase)

1. **Layout Collisions**: Requirements or text placed physically "under" or "overlapping" tables will be rightfully suppressed by the pipeline (S07 Suppression Logic). Generators must ensure spatial separation (e.g. Page Breaks).
2. **Artifact Hygiene**: The presence of multiple `*_clean.pdf` files (e.g. from previous runs) can cause S04/S05 to process the wrong source. Strict filename matching defaults have been enforced.
3. **Table Verification**: Strict string equality for tables is fragile. Fuzzy CSV comparison or content-based matching is required.
4. **Table Splitting**: S05 Text-Heavy Heuristic was too aggressive (`avg_words > 2.5`), deleting valid data tables with verbose descriptions. Relaxed to `5.0`. Fixed.
