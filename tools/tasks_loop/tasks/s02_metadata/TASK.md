# Task: Add s02 Metadata

---

task_id: s02_metadata
title: "Add llm_used metadata to s02 output"
status: done
priority: medium

acceptance:

- s02 output JSON includes top-level `metadata` field
- `metadata` includes `llm_used` boolean
- `metadata` includes `blocks_count` integer
- Code handles both fast (pymupdf) and accurate (marker) paths

gate: gates/gate_s02_metadata.py
expected:
metadata_present: true

context:

- file:///home/graham/workspace/experiments/extractor/src/extractor/pipeline/steps/s02_marker_extractor.py

---

## Goal

Add metadata tracking to Stage 02 (Marker Extractor) output so downstream steps and operators can verify if the LLM was actually used during extraction.

## Background

Currently, `s02_marker_blocks.json` contains a flat list of blocks (or a dict with `blocks` key). It's hard to tell from the output whether the expensive LLM path was taken or the fast fallback.

## Implementation Notes

- Modify `extract_real` (or equivalent) in `s02_marker_extractor.py` output structure.
- Ensure backwards compatibility if possible, or update consumers (s03, s14 report generator).
- Return structure should ideally be:
  ```json
  {
    "metadata": {
      "llm_used": true,
      "page_count": 5
    },
    "blocks": [...]
  }
  ```

## Agent Instructions

1.  Analyze `s02_marker_extractor.py` return format.
2.  Update it to return a dictionary with `blocks` and `metadata`.
3.  Create a gate to verify the output format.
4.  Run the gate.
