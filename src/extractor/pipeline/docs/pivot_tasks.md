# Pivot Implementation Plan: The "DuckDB-First" Pipeline

**Branch**: `feature/duckdb-pivot`
**Date**: 2025-12-29

## Goal

Replace the brittle "Reflow" stages (06b, 07, 08) with a deterministic, DuckDB-based asset merger and a focused LLM extractor.

## Architecture Strategy

**"Load First, Query Later"**:
We will NOT modify the existing extractors (Stages 01-06). They appear stable and produce valid JSON.
Instead, **Stage 07** will become the **Loader/Assembler**. It will:

1.  Read the JSON artifacts from previous stages.
2.  Ingest them into a structured DuckDB (`pipeline.duckdb`).
3.  Perform deterministic spatial merges (Text + Tables + Figures) using SQL.

This minimizes regression risk for the working parts of the pipeline.

## Task Breakdown

### Phase 1: Infrastructure & Schema

- [x] **1. Create `utils/db/` package**:
  - `connection.py`: Manage DuckDB connection (persistent `data/results/pipeline/pipeline.duckdb`).
  - `schema.py`: Define DDL for tables (`sections`, `blocks`, `tables`, `figures`, `kv_store`).
- [x] **2. Validation**: Ensure `duckdb` (and extensions if needed) works in the environment.

### Phase 2: Stage 07 (The Loader & Merger)

- [ ] **3. Implement `steps/07_assemble_corpus.py`**:
  - **Ingest Logic**:
    - Load `04_sections.json` -> INSERT `sections`
    - Load `05_tables.json` -> INSERT `tables`
    - Load `06_figures.json` -> INSERT `figures`
    - Load `02_marker_blocks.json` -> INSERT `blocks` (raw text backup)
  - **Merge Logic (SQL)**:
    - Create a View `v_clean_blocks` that filters out Marker blocks that overlap significantly (>50% area) with Camelot Tables or PyMuPDF Figures.
    - **Rule**: strict priority `Camelot (Tables) > PyMuPDF (Figures) > Marker (Text)`.
    - If a Marker block is "covered" by a Table/Figure, it is suppressed (treated as a duplicate).
    - Create a View `v_corpus_sections` that joins Sections with these `v_clean_blocks` + `tables` + `figures` based on Page + BBox.
- [ ] **4. Verify Merger**:
  - Run `extract-pipeline ... --only-stages 07`.
  - Verify DB contains correctly associated tables (e.g. `SELECT * FROM tables WHERE section_id IS NOT NULL`).

### Phase 3: Stage 08 (Focused Extraction)

- [ ] **5. Implement `steps/08_extract_requirements.py`**:
  - **Iterator**: Query `v_corpus_sections`.
  - **Prompt**: "Here is the text for section X. Here are the CSVs for tables in section X. Extract Requirements."
  - **Output**: INSERT result into `requirements` table.
- [ ] **6. Resume Capability**:
  - Logic: `SELECT id FROM sections EXCEPT SELECT section_id FROM requirements`. Process only delta.

### Phase 4: Integration & Cleanup

- [ ] **7. Update `run_pipeline.py`**:
  - Sequence: `01 -> 02 -> 03 -> 04 -> 05 -> 06 -> 07(DB Load) -> 08(Extract) -> 14(Report)`.
  - Remove: `06b`, `07(Old)`, `08(Old)`, `09`.
- [ ] **8. Report Generator Update**:
  - Update Stage 14 to read from DuckDB `requirements` table instead of JSON files.
- [ ] **9. Create Gold Standard (Manual QA)**:
  - Manually review 10 sections and create "perfect" QRA pairs in `data/gold_standard_qra.json`.
  - Use for spot-checking Stage 08.

## Questions for Discussion

1.  **Ingestion Strategy**: Do we trust `04_sections.json` boundaries implicitly? (Assumption: Yes, Stage 04 is "Good Enough").
2.  **Table Content**: Do we use the CSV representation from Camelot for the LLM? (Assumption: Yes, it's token-efficient).
3.  **Embeddings**: Should we compute vector embeddings for sections inside DuckDB (using `duckdb-vss` or external)? (Recommendation: Phase 2. Keep Phase 1 strictly extraction).
