# Provider Test Coverage Report

**Generated**: 2026-01-19
**Total Tests**: 187 (181 passed, 6 skipped)

## Coverage Summary

| Provider | Test Location | Tests | Coverage Type |
|----------|---------------|-------|---------------|
| **ImageProvider** | `tests/core/providers/test_image_provider.py` | 6 | Unit tests |
| **SpreadsheetProvider** | `tests/core/providers/test_spreadsheet_provider.py` | 6 | Unit tests |
| **HTMLProvider** | `tests/ingest/test_html_provider.py` | 7 | Unit tests |
| **DOCXProvider** | `tests/core/providers/test_docx_provider.py` | 4 | Unit tests |
| **XMLProvider** | `tests/core/providers/test_xml_provider.py` | 4 | Unit tests |
| **PPTXProvider** | `tests/core/providers/test_pptx_provider.py` | 4 | Unit tests |
| **EPUBProvider** | `tests/core/providers/test_epub_provider.py` | 4 | Unit tests |
| **RSTProvider** | `tests/core/providers/test_rst_provider.py` | 4 | Unit tests |
| **MarkdownProvider** | `tests/core/providers/test_markdown_provider.py` | 4 | Unit tests |
| **PDFProvider** | See below | Multiple | Layered coverage |

## PDFProvider Coverage (Layered)

PDFProvider is tested at multiple layers because it has two modes:

### Fast Mode (`--fast`)
Uses PyMuPDF directly for quick text extraction.

| Test | Location | What It Tests |
|------|----------|---------------|
| `test_extract_fast_text_basic` | `tests/unit/test_fast_extract_pymupdf_fast.py` | PyMuPDF text extraction |
| `test_extract_fast_text_pages_slice` | `tests/unit/test_fast_extract_pymupdf_fast.py` | Page range selection |
| `S1_pymupdf_open.py` | `tools/tasks_loop/sanity/` | Sanity: PyMuPDF opens PDF |

### Accurate Mode (`--accurate`)
Uses the full 14-stage pipeline via `run_pipeline.py`.

| Test | Location | What It Tests |
|------|----------|---------------|
| `test_cli_factories_all_steps` | `tests/pipeline/steps/` | All step CLI factories work |
| `test_03_suspicious_headers_offline` | `tests/pipeline/` | S03 header verification |
| `test_04_section_builder_minimal` | `tests/pipeline/` | S04 section building |
| `test_html_parity_specific` | `tests/pipeline/` | Cross-format parity |
| `S2_marker_extract.py` | `tools/tasks_loop/sanity/` | Sanity: Marker extraction |
| `S5b_scillm_chutes.py` | `tools/tasks_loop/sanity/` | Sanity: LLM calls |
| `S7_duckdb_basic.py` | `tools/tasks_loop/sanity/` | Sanity: DuckDB ingest |

### End-to-End
| Test | Location | What It Tests |
|------|----------|---------------|
| `sanity.sh` | Skill directory | "PDF --fast: OK (39s)" |
| `test_contract_bht_det.py` | `tests/contract/` | Deterministic extraction contract |

### Why No Dedicated PDFProvider Unit Test?

PDFProvider's `extract_document()` method delegates to `run_pipeline_main()`, which orchestrates the pipeline steps. Testing PDFProvider directly would duplicate:

1. **Sanity scripts** - Verify dependencies (pymupdf, pdftext, marker) work
2. **Pipeline step tests** - Each step (S01-S14) has its own tests
3. **Skill sanity** - End-to-end extraction works

This is the **correct architecture** - test at the layer where the logic lives.

## Sanity Scripts Status

| Script | Purpose | Status |
|--------|---------|--------|
| `S1_pymupdf_open.py` | PyMuPDF PDF opening | PASS |
| `S2_marker_extract.py` | Marker block extraction | PASS |
| `S5b_scillm_chutes.py` | LLM via Chutes API | PASS |
| `S7_duckdb_basic.py` | DuckDB operations | PASS |
| `camelot_table_extraction.py` | Camelot table extraction | PASS |

## Quality Gate

```
make smokes-cli
================= 181 passed, 6 skipped, 21 warnings in 11.06s =================
CLI smokes: PASS
```

## Test Files Created (2026-01-19)

```
tests/core/providers/
├── test_docx_provider.py     # 4 tests - heading, table, empty doc
├── test_epub_provider.py     # 4 tests - chapters, metadata, empty
├── test_markdown_provider.py # 4 tests - lists, code, tables
├── test_pptx_provider.py     # 4 tests - slides, bullets, empty
├── test_rst_provider.py      # 4 tests - sections, code, empty
└── test_xml_provider.py      # 4 tests - nested, attributes, empty
```

All tests use `tmp_path` fixtures (self-contained, no external dependencies).
