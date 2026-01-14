---
fixture: structured_html
source: tools/tasks_loop/fixtures/structured_html/source.html
source_type: html

# No Twin needed for structured formats
agent_config:
  twin_required: false
  allow_auto_tune: false
  strict_calibration: false

# Structured Pipeline Steps (Provider → UnifiedAdapter → S07+)
steps:
  # Provider Step: HTML → UnifiedDocument
  provider:
    name: HTML Provider
    output: structured_html/provider_output/unified_document.json
    expected:
      block_count: 10
      has_headings: true
      has_tables: true

  # Adapter Step: UnifiedDocument → Pipeline Artifacts
  adapter:
    name: Unified Adapter
    output: structured_html/adapter_output/
    expected:
      artifacts:
        - 04_sections.json
        - 05_tables.json
        - 06_figures.json

  # S07: DuckDB Ingest (shared with PDF pipeline)
  s07:
    name: DuckDB Ingest
    output: structured_html/07_duckdb_ingest/pipeline.duckdb
    expected:
      tables_ingested: true
      sections_indexed: true

  # S08: Requirement Extraction (shared)
  s08:
    name: Requirements (LLM)
    output: structured_html/08_requirements/08_requirements.json
    expected:
      requirement_count: 0 # HTML may not have requirements

  # S10: Markdown Export (shared)
  s10:
    name: Markdown Exporter
    output: structured_html/10_markdown_exporter/final_output.md
    expected:
      contains_headings: true
      preserves_structure: true
---

# structured_html Fixture

This fixture validates the **Structured Format Pipeline** (non-PDF path).

## Purpose

Verify that HTML → UnifiedDocument → S07+ works correctly without requiring a Twin.

## Pipeline Flow

```
HTML Source → HTMLProvider → UnifiedDocument → UnifiedAdapter → S07/S08/S10
```

## Expected Behavior

1. Provider extracts headings, paragraphs, tables from HTML
2. Adapter writes `04_sections.json`, `05_tables.json`, `06_figures.json`
3. S07 ingests into DuckDB
4. S10 exports to Markdown

## No Twin Required

Unlike PDF fixtures, this fixture does NOT need a Twin because:

- HTML is already semantic (tags define structure)
- Extraction is deterministic (same input = same output)
