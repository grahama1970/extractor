# 🦆 DuckDB Pivot Walkthrough

**Status**: 🚧 IN PROGRESS
**Branch**: `feature/duckdb-pivot`

This document tracks the migration to the "DuckDB-First" architecture.

---

## 🛠️ Phase 1: Infrastructure (The Foundation)

Goal: Establish the database connection and schema.

- [ ] **1.1. Create `utils/db/connection.py`**

  - Singleton pattern for `duckdb.connect()`.
  - Persistent path: `data/results/pipeline/pipeline.duckdb`.
  - Extensions: Ensure `vss` (Vector Similarity Search) is available (optional for now).

- [ ] **1.2. Create `utils/db/schema.py`**
  - Define `create_schema(con)` function.
  - **Tables**:
    - `blocks`: `(id, page, x0, y0, x1, y1, text, type)`
    - `tables`: `(id, page, x0, y0, x1, y1, csv_data, html_data)`
    - `figures`: `(id, page, x0, y0, x1, y1, image_path)`
    - `sections`: `(id, title, page_start, page_end, parent_id)`
    - `requirements`: `(id, section_id, text, type, confidence, citation_snippet, is_table_row)`

---

## 🏗️ Phase 2: Stage 07 (The Assembler)

Goal: Ingest JSON artifacts and create the "Clean View".

- [ ] **2.1. Implement `steps/07_assemble_corpus.py`**

  - **Backwards Compat**: Reads `02_marker_blocks.json`, `04_sections.json`, `05_tables.json`, `06_figures.json`.
  - **Ingestion**: Bulk inserts (using `con.executemany` or Appender).
  - **Schema Design**: A SINGLE table `sections` stores metadata for all sections. `blocks`, `tables` etc. FK to `sections`.

- [ ] **2.2. Implement SQL De-Duplication**

  - Create View `v_clean_blocks`:
    ```sql
    SELECT * FROM blocks b
    WHERE NOT EXISTS (
      SELECT 1 FROM tables t
      WHERE b.page = t.page AND overlap_area(b.bbox, t.bbox) > 0.5
    )
    ```

- [ ] **2.3. Verification**
  - Run `python -m extractor.pipeline.steps.07_assemble_corpus`.
  - Run `duckdb data/results/pipeline/pipeline.duckdb "SELECT count(*) FROM v_clean_blocks"` to verify filtering.

---

## 🧠 Phase 3: Stage 08 (The Extractor & Verifier)

Goal: Focused requirement extraction using the clean corpus and citation checks.

- [ ] **3.1. Implement `steps/08_extract_requirements.py`**

  - **Strategy**: Keep corpus RAW. Do not summarize before extraction.
  - **Heuristic Filter**: Only process sections containing "shall", "must", "require", or a Table.
  - **Prompting**:
    - "Extract requirements from this raw text/table data."
    - "For each requirement, provide a verbatim citation snippet from the text/table row."
  - **Verification**: Post-hoc check that `citation_snippet` fuzzy-matches the raw `blocks` in DB.

- [ ] **3.2. (Future) Lean4 Formalization**
  - Now that we have clean requirements in DB, Lean4 can run as **Stage 09** (Post-Process).
  - Input: `SELECT * FROM requirements`.
  - Output: `.lean` files.

---

## 🧹 Phase 4: Cleanup (The Pruning)

Goal: Remove the slop.

- [ ] **4.1. Archive Legacy Steps**

  - Move `06b_layout_sketcher.py`, `07_reflow_section.py`, `08_lean4_*.py` to `steps/archive/`.
  - Update `run_pipeline.py` to skip them.

- [ ] **4.2. Create Gold Standard (Manual QA)**
  - Manually review 10 sections and create "perfect" QRA pairs.
  - Save to `data/gold_standard_qra.json`.
  - Use this to spot-check the new Stage 08 outputs.

---

## ❓ Decision Log

- **Directory Structure**: Kept single `steps/` directory to share imports with Stages 01-06. Legacy codes moved to `steps/archive/`.
- **Duplicate Handling**: Handled via SQL `NOT EXISTS` / Spatial Join in Phase 2.2.
