# DuckDB Architecture Evaluation

**Date**: 2025-12-29
**Subject**: Replacing File-Based Handoffs (JSON/JSONL) with DuckDB

## 1. The Current Problem: "JSON Fatigue"

The pipeline currently operates as a chain of file transformations:
`input.pdf` -> `02_blocks.json` -> `04_sections.json` -> `07_reflowed.json`...

**Issues Identified:**

1.  **Staleness**: Hard to know if `04_sections.json` corresponds to the current `02_blocks.json` or a previous run.
2.  **IoC (Index of Confusion)**: Debugging requires opening 5 different large JSON files to trace one piece of text.
3.  **Inefficient Merging**: To find "Which section is this block in?", we currently load ALL sections and ALL blocks into Python RAM and loop. This is O(N\*M) or O(N log M) at best, and memory-heavy.

## 2. DuckDB Solution Evaluation

**Verdict: HIGHLY RECOMMENDED.**

DuckDB is an in-process SQL OLAP database. It fits this use case perfectly because:

### A. It Solves the "Merge" Problem (Spatial Joins)

Your proposed "Coordinate Sort & Merge" (Step 4) is native to SQL.

_Current Python (Pseudocode)_:

```python
for section in sections:
    section_blocks = []
    for block in blocks:
        if block.page in section.pages and block.y within section.y:
             section_blocks.append(block)
```

_DuckDB SQL_:

```sql
SELECT
    s.id as section_id,
    b.text,
    b.bbox
FROM sections s
JOIN blocks b
  ON s.page = b.page
  AND b.y_mid BETWEEN s.y_start AND s.y_end
ORDER BY s.id, b.y0
```

This is drastically faster, cleaner, and less brittle.

### B. It Solves the Stale Data Problem

- Use a single `pipeline.duckdb` file.
- Use explicit run IDs or overwrite tables transactionally.
- "Stage 04" doesn't produce a file; it populates the `sections` table.
- "Stage 05" populates the `tables` table.

### C. It Enables Analysis

You can instantly query:

- " Show me all sections with > 0 tables"
- "Count blocks per page"
- "Find all blocks with low confidence"
  ...without writing a custom Python script for every check.

## 3. Implementation Strategy

You don't need to rewrite the _extractors_ (Camelot/PyMuPDF). You just rewrite the **Sink** and **Source**.

**Adapters:**

1.  **Stage 02 (Marker)**: Instead of `json.dump`, use `con.execute("INSERT INTO blocks SELECT ...")`.
2.  **Stage 05 (Tables)**: Insert CSV content textual representation into `tables` table.
3.  **Stage 07 (Corpus Assembly)**: Is now just a SQL View or a `CREATE TABLE corpus AS SELECT ...`.

## 4. Conclusion

Moving to DuckDB addresses the "Confusing" and "Stale" parts of your critique. Combined with the "Focused Pivot" (removing Reflow), it creates a professional-grade ETL pipeline:

1.  **Extract** (PDF -> DB Tables)
2.  **Transform** (SQL: Clean, Dedup, Merge)
3.  **Load** (DB -> LLM Context)

**Recommendation**: Add `duckdb` to `pyproject.toml` and implement the "Asset Merger" (Step 7-Lite) as a DuckDB SQL script.
