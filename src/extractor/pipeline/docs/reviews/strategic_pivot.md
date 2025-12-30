# Strategic Pivot: From Aspiration to Reliability

**Date**: 2025-12-29
**Author**: Antigravity Agent

## 1. Executive Summary: "The User is Right"

The user's proposed 7-step plan is not a "restart" — it is a **simplification** of the current architecture. The current pipeline attempts to do exactly what is proposed (Marker + Camelot + PyMuPDF), but it wraps them in a heavy layer of "Aspirational" complexity (LLM-based Reflow, Provers, Layout Sketchers) that makes it brittle.

**Verdict**:

- **Stop** trying to "Reflow" text with LLMs (Stage 07).
- **Stop** trying to "Proove" theorems (Stage 08) until basic extraction works.
- **Pivot** to a deterministic "Asset Merger" that simply zips Text, Tables, and Figures by coordinate sorting.

## 2. Capability Mapping (Current vs. Proposed)

We are closer than it feels. We do not need to restart 6x.

| User Proposal Step            | Current Pipeline Stage          | Implementation             | Status                |
| :---------------------------- | :------------------------------ | :------------------------- | :-------------------- |
| 1. Marker Extract (JSON/BBox) | **Stage 02** (Marker Extractor) | `surya`/`marker`           | ✅ Working            |
| 2. PyMuPDF Images             | **Stage 06** (Figure Extractor) | `fitz` (PyMuPDF)           | ✅ Working            |
| 3. Camelot Tables             | **Stage 05** (Table Extractor)  | `camelot-py`               | ✅ Working            |
| 4. Sort & Merge by BBox       | **Stage 06b** (Layout Sketcher) | _Over-engineered_          | ❌ Brittle            |
| 5. Dedup Figures/Tables       | **Stage 06a/b**                 | _Partial/Complex_          | ⚠️ Reliability issues |
| 6. Delimit Sections           | **Stage 04** (Section Builder)  | `SectionHeader` heuristics | ✅ Working            |
| 7. Stop with clean sections   | **Stage 07** (Reflow)           | _LLM-based_ (Too heavy)    | ❌ Replace            |

## 3. The Pivot Plan

We can deliver the user's robust pipeline by **pruning** rather than rewriting.

### Phase A: The Great Pruning works

- **Disable** `06b_layout_sketcher` (The "Sketcher").
- **Disable** `07_reflow_section` (The "LLM Writer").
- **Disable** `08_lean4_theorem_prover` (The "Dream").

### Phase B: The Deterministic Merger (New Stage 07-Lite)

Create a new, boring `07_merge_assets.py`:

1.  Load `04_sections.json` (Text blocks).
2.  Load `05_tables.json` (Camelot).
3.  Load `06_figures.json` (PyMuPDF).
4.  **Algorithm**:
    - For each page:
      - Collect all items (Text blocks, Table bboxes, Figure bboxes).
      - Remove Text blocks that overlap >50% with Table/Figure bboxes (Dedup).
      - Sort remaining items by `(y0, x0)`.
    - Group by Section (from Stage 04 boundaries).
    - Output: `sections_merged.json` (List of content items in reading order).

### Phase C: Success Criteria

- No LLM calls required for extraction (only for enrichment/summary if desired).
- Deterministic output.
- Fast execution.

## 4. Recommendation to User

**Do not restart.** You have the components. You just need to stop the "pipeline" before it enters the "AI Slop" territory of Stages 07/08.

**Immediate Action**:

1.  Verify Stage 05 (Tables) is outputting decent JSON.
2.  Verify Stage 06 (Figures) is outputting images.
3.  Write the "Merger" script (Phase B).
4.  Delete/Archive the rest.
