# Complete Pipeline Code Review Request

## Repository and Branch

- **Repo:** `grahama1970/extractor`
- **Branch:** `feature/stage-09-llm-enrichment`

## Scope

Review the **entire PDF extraction pipeline** from ingestion to report generation.

## Files to Review

### Orchestration

- `src/extractor/pipeline/run_pipeline.py` - Main router with PDF/HTML strategies

### Pipeline Steps (in execution order)

1. `src/extractor/pipeline/steps/s01_annotation_processor.py` - PDF annotation extraction
2. `src/extractor/pipeline/steps/s02_marker_extractor.py` - Block/text extraction via Marker
3. `src/extractor/pipeline/steps/s03_suspicious_headers.py` - Header candidate detection
4. `src/extractor/pipeline/steps/s03b_header_verifier.py` - LLM header verification
5. `src/extractor/pipeline/steps/s04_section_builder.py` - Section hierarchy construction
6. `src/extractor/pipeline/steps/s04a_layout_audit.py` - Layout validation
7. `src/extractor/pipeline/steps/s05_table_extractor.py` - Table extraction via Camelot
8. `src/extractor/pipeline/steps/s06_figure_extractor.py` - Figure detection/extraction
9. `src/extractor/pipeline/steps/s06b_figure_describer.py` - VLM figure description
10. `src/extractor/pipeline/steps/s07_assemble_corpus.py` - DuckDB corpus assembly
11. `src/extractor/pipeline/steps/s08_extract_requirements.py` - Requirements extraction to merged_content
12. `src/extractor/pipeline/steps/s09_llm_enrichment.py` - LLM enrichment
13. `src/extractor/pipeline/steps/s09_section_summarizer.py` - Section summarization
14. `src/extractor/pipeline/steps/s10_markdown_exporter.py` - Markdown export
15. `src/extractor/pipeline/steps/s14_report_generator.py` - Final report

### Multi-Format Ingestion

- `src/extractor/pipeline/ingest/html_provider.py` - HTML → UnifiedDocument
- `src/extractor/pipeline/adapters/unified_adapter.py` - UnifiedDocument → Pipeline Artifacts

### Schema & Database

- `src/extractor/pipeline/utils/db/schema.py` - DuckDB schema (sections, blocks, requirements, lean4_proofs, merged_content)

### Key Utilities

- `src/extractor/pipeline/utils/scillm_router.py` - LLM routing
- `src/extractor/pipeline/utils/reliability.py` - Error handling
- `src/extractor/pipeline/utils/marker_runner.py` - Marker integration
- `src/extractor/pipeline/utils/headers/runner.py` - Header verification logic
- `src/extractor/pipeline/utils/sections/runner.py` - Section building logic
- `src/extractor/pipeline/utils/tables/runner.py` - Table extraction logic

## Review Focus Areas

### 1. Architecture

- Is the router/strategy pattern (`_run_pdf_strategy`, `_run_html_strategy`, `_run_common_stages`) sound?
- Is the separation between extraction (S01-S06) and semantics (S07-S14) appropriate?
- Are there circular dependencies or tight coupling issues?

### 2. Data Flow

- Is the JSON artifact handoff between stages robust?
- Are there missing validations when reading previous stage outputs?
- Could schema drift break downstream stages silently?

### 3. Error Handling

- Are there bare `except Exception` blocks that swallow errors?
- Are failures logged with sufficient context?
- Do stages fail fast or silently continue with corrupt data?

### 4. LLM Integration

- Are LLM responses validated before use?
- Is there retry/fallback logic for API failures?
- Are prompts structured to minimize hallucination?

### 5. Database Schema

- Is `merged_content` the right approach for reading order?
- Should requirements have their own table or be in merged_content?
- Is the `lean4_proofs` 1:N relationship correctly modeled?

### 6. Idempotency & Resume

- Can stages be re-run safely without duplicating data?
- Is there checkpoint/resume logic for long-running stages?

### 7. Performance

- Are there N+1 query patterns in DuckDB operations?
- Are imports placed at module top (not inside loops)?
- Are there unnecessary file re-reads between stages?

### 8. Code Quality

- Unused parameters or dead code?
- Magic numbers without named constants?
- Inconsistent naming conventions?

## Known Issues (Already Identified)

- HTMLProvider encoding fallback is minimal
- No idempotency check in S08 (re-run duplicates requirements)
- LLM response schema not validated

## Deliverable

Provide a structured review with:

1. **🔴 CRITICAL** - Will break in production
2. **🟡 MEDIUM** - Will cause problems at scale
3. **🔵 REFINEMENT** - Code quality improvements
4. **✅ STRENGTHS** - Good patterns to preserve

For each issue, provide:

- File and line number
- Description of the problem
- Impact/risk
- Suggested fix (code diff preferred)
