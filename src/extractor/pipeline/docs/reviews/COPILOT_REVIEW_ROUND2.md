# Follow-Up Pipeline Review Request (Round 2)

## Repository and Branch

- **Repo:** `grahama1970/extractor`
- **Branch:** `feature/stage-09-llm-enrichment`

## Context

This is a **follow-up review** after addressing issues from the first Copilot review:

### Critical Issues Fixed (Round 1)

- ✅ S03b: Index mismatch (parallel lists → tuple approach)
- ✅ S03b: Prompt bug (duplicate non-fstring line)
- ✅ S06: Unreachable code after `raise` (5 locations)
- ✅ S10: Wrong DB name (`corpus.duckdb` → `pipeline.duckdb` priority)

### Medium Issues Fixed (Round 2)

- ✅ S08: Idempotency (deterministic IDs via sha1, skip existing sections)
- ✅ Schema: Added `llm_summary`, `llm_key_concepts`, `llm_metadata` to sections table
- ✅ HTMLProvider: 3-tier encoding fallback with `errors='replace'`

## Files Modified Since Last Review

```
src/extractor/pipeline/steps/s03b_header_verifier.py
src/extractor/pipeline/steps/s06_figure_extractor.py
src/extractor/pipeline/steps/s08_extract_requirements.py
src/extractor/pipeline/steps/s10_markdown_exporter.py
src/extractor/pipeline/utils/db/schema.py
src/extractor/pipeline/ingest/html_provider.py
```

## Please Review Focus Areas

### 1. Orchestration (`run_pipeline.py`)

- Is the router/strategy pattern sound?
- Are stage dependencies correctly wired?
- Error propagation between stages?

### 2. Data Flow / JSON Handoffs

- Are there missing validations when reading previous stage outputs?
- Could schema drift break downstream stages silently?

### 3. S09 Asset Coverage (Deferred Issue)

- S09 enrichment relies on `merged_content` being complete for tables/figures
- Currently skips if assets not found in `merged_content`
- Is this acceptable or should S09 build assets from primary tables?

### 4. Remaining Medium Issues from Round 1

- S09 summarizer still does `ALTER TABLE ... ADD COLUMN` at runtime
- Should we remove the ALTER and rely on schema.py?

### 5. LLM Response Validation

- S03b, S06b, S08 don't validate LLM response schema
- Should we add jsonschema validation or rely on json_repair?

## Deliverable

Please provide:

1. Any **NEW** critical or medium issues not caught in Round 1
2. Validation that the fixes are correct
3. Recommendations for orchestration improvements
