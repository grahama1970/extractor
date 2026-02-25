# Task List: Provider Unit Tests

## Context

Add unit tests for the 6 providers currently lacking dedicated test coverage: DOCX, XML, PPTX, EPUB, RST, and expand Markdown tests. Follow the pattern established in `test_image_provider.py` and `test_spreadsheet_provider.py`: 4-6 focused tests per provider using temporary files (no fixture dependencies).

## Crucial Dependencies (Sanity Scripts)

| Library | API/Method | Sanity Script | Status |
|---------|------------|---------------|--------|
| pytest | `tmp_path` fixture | None needed | N/A (standard) |
| python-docx | `Document()` | None needed | N/A (well-known) |
| python-pptx | `Presentation()` | None needed | N/A (well-known) |
| ebooklib | `epub.EpubBook()` | None needed | N/A (well-known) |
| docutils | `publish_doctree()` | None needed | N/A (well-known) |

> No sanity scripts required - all dependencies are standard library or well-known packages.

## Tasks

- [x] **Task 1**: Create unit tests for DOCXProvider

  - Agent: general-purpose
  - Parallel: 0
  - Dependencies: none
  - Notes: Test heading extraction, paragraph handling, table extraction. Use python-docx to create temp files.
  - **Sanity**: None (uses python-docx - well-known)
  - **Definition of Done**:
    - Test: `tests/core/providers/test_docx_provider.py::test_docx_provider_basic_extraction`
    - Test: `tests/core/providers/test_docx_provider.py::test_docx_provider_heading_hierarchy`
    - Test: `tests/core/providers/test_docx_provider.py::test_docx_provider_table_extraction`
    - Test: `tests/core/providers/test_docx_provider.py::test_docx_provider_empty_document`
    - Assertion: All 4 tests pass, DOCXProvider extracts headings as heading blocks, paragraphs as text blocks, tables as table blocks

- [x] **Task 2**: Create unit tests for XMLProvider

  - Agent: general-purpose
  - Parallel: 1
  - Dependencies: none
  - Notes: Test basic element extraction, nested structure, attribute handling. Create XML strings in temp files.
  - **Sanity**: None (uses defusedxml - standard pattern)
  - **Definition of Done**:
    - Test: `tests/core/providers/test_xml_provider.py::test_xml_provider_basic_extraction`
    - Test: `tests/core/providers/test_xml_provider.py::test_xml_provider_nested_elements`
    - Test: `tests/core/providers/test_xml_provider.py::test_xml_provider_with_attributes`
    - Test: `tests/core/providers/test_xml_provider.py::test_xml_provider_empty_document`
    - Assertion: All 4 tests pass, XMLProvider converts elements to appropriate block types

- [x] **Task 3**: Create unit tests for PPTXProvider

  - Agent: general-purpose
  - Parallel: 1
  - Dependencies: none
  - Notes: Test slide extraction, title/body separation, shape handling. Use python-pptx to create temp files.
  - **Sanity**: None (uses python-pptx - well-known)
  - **Definition of Done**:
    - Test: `tests/core/providers/test_pptx_provider.py::test_pptx_provider_basic_extraction`
    - Test: `tests/core/providers/test_pptx_provider.py::test_pptx_provider_slide_titles`
    - Test: `tests/core/providers/test_pptx_provider.py::test_pptx_provider_bullet_points`
    - Test: `tests/core/providers/test_pptx_provider.py::test_pptx_provider_empty_presentation`
    - Assertion: All 4 tests pass, PPTXProvider extracts slides with titles as headings and content as text blocks

- [x] **Task 4**: Create unit tests for EPUBProvider

  - Agent: general-purpose
  - Parallel: 1
  - Dependencies: none
  - Notes: Test chapter extraction, metadata handling, HTML content parsing. Use ebooklib to create temp EPUB.
  - **Sanity**: None (uses ebooklib - well-known)
  - **Definition of Done**:
    - Test: `tests/core/providers/test_epub_provider.py::test_epub_provider_basic_extraction`
    - Test: `tests/core/providers/test_epub_provider.py::test_epub_provider_chapter_structure`
    - Test: `tests/core/providers/test_epub_provider.py::test_epub_provider_metadata`
    - Test: `tests/core/providers/test_epub_provider.py::test_epub_provider_empty_book`
    - Assertion: All 4 tests pass, EPUBProvider extracts chapters with HTML content converted to blocks

- [x] **Task 5**: Create unit tests for RSTProvider

  - Agent: general-purpose
  - Parallel: 1
  - Dependencies: none
  - Notes: Test section extraction, directive handling, inline markup. Create RST strings in temp files.
  - **Sanity**: None (uses docutils - well-known)
  - **Definition of Done**:
    - Test: `tests/core/providers/test_rst_provider.py::test_rst_provider_basic_extraction`
    - Test: `tests/core/providers/test_rst_provider.py::test_rst_provider_section_hierarchy`
    - Test: `tests/core/providers/test_rst_provider.py::test_rst_provider_code_blocks`
    - Test: `tests/core/providers/test_rst_provider.py::test_rst_provider_empty_document`
    - Assertion: All 4 tests pass, RSTProvider extracts sections with correct heading levels

- [x] **Task 6**: Expand unit tests for MarkdownProvider

  - Agent: general-purpose
  - Parallel: 1
  - Dependencies: none
  - Notes: Current coverage is minimal (1 test in test_provider_hierarchy.py). Add focused tests for edge cases.
  - **Sanity**: None (uses mistune - well-known)
  - **Definition of Done**:
    - Test: `tests/core/providers/test_markdown_provider.py::test_markdown_provider_basic_extraction`
    - Test: `tests/core/providers/test_markdown_provider.py::test_markdown_provider_nested_lists`
    - Test: `tests/core/providers/test_markdown_provider.py::test_markdown_provider_code_blocks`
    - Test: `tests/core/providers/test_markdown_provider.py::test_markdown_provider_tables`
    - Assertion: All 4 tests pass, MarkdownProvider handles nested structures and code blocks correctly

## Completion Criteria

- All 6 test files created in `tests/core/providers/`
- All 24 tests pass (`pytest tests/core/providers/ -v`)
- No new dependencies added
- Tests are self-contained (use tmp_path, no external fixtures)

## Note: PDFProvider Coverage

PDFProvider was intentionally excluded from this task. It has **layered coverage**:

| Mode | Coverage |
|------|----------|
| `--fast` | `tests/unit/test_fast_extract_pymupdf_fast.py` + `S1_pymupdf_open.py` sanity |
| `--accurate` | Pipeline step tests (`tests/pipeline/`) + sanity scripts (S2, S5b, S7) |
| End-to-end | `sanity.sh` + `test_contract_bht_det.py` |

See `docs/PROVIDER_TEST_COVERAGE.md` for details.

## Questions/Blockers

None - all questions resolved, standard testing patterns apply.
