# HTML vs PDF Parity Task List

Legend: `[ ]` todo · `[~]` in progress · `[x]` done

Goal: Achieve near-identical Stage 10 outputs for the BHT PDF and its HTML counterpart by leveraging HTML structure, with smokes to keep them aligned.

---

## 1) HTML Extraction Improvements

- [x] Add an HTML-specific ingestion path that bypasses PDF-style reflow and emits `UnifiedDocument` directly.
- [x] Register DOCX, PPTX, Spreadsheet, EPUB, RST, and XML providers with the structured pipeline dispatcher so they share the same fast path.
- [ ] Enhance `HTMLProvider` to produce `TableBlock`, `ImageBlock`/`Figure`, and list/code blocks from native DOM nodes.
- [ ] Map HTML headings (H1–H6) into hierarchy levels and breadcrumbs consistent with Stage 07 PDF sections.
- [ ] Associate captions/alt text with table and figure blocks for parity with PDF metadata.
- [ ] Ensure HTML paragraph blocks aggregate contiguous text so Stage 10 sees coherent sections.

## 2) Pipeline Integration

- [ ] Update Stage 07 orchestration to detect `SourceType.HTML` and skip LLM reflow, returning the native `UnifiedDocument` payload.
- [x] Confirm Stage 10 flattening accepts html `UnifiedDocument` input without legacy `reflowed_sections` present.
- [x] Refine `build_unified_document_from_reflow` to deduplicate text and preserve merged/source text for PDFs.
- [ ] Propagate source metadata (`source_html`, `conversion_notes`) so Arango records indicate origin format.

## 3) Smoke Tests & Regression Guards

- [ ] Add `tests/smoke/test_stage10_html_vs_pdf.py` comparing flattened outputs across PDF/HTML pairs (object counts, table/figure presence, breadcrumb titles).
- [x] Create `scripts/smokes/pipeline/smoke_stage10_html_parity.py` to run the comparison end-to-end and archive artifacts.
- [ ] Capture normalized text diff artifacts (`*.json`, `*.txt`) for CI reporting.
- [ ] Document new smoke acceptance in `docs/SMOKES_GUIDE.md` and ensure `make smokes` includes the parity check.

## 4) Documentation & Tooling

- [ ] Update `docs/03_guides/HAPPYPATH_GUIDE.md` with the HTML fast-path (no reflow stage required).
- [ ] Add a VS Code task / Make target (`make smoke-html-parity`) for contributors.
- [ ] Note HTML parity requirements in `docs/pipeline/README.md` (or equivalent) for future datasets.

## 5) Follow-up Enhancements (optional once parity holds)

- [ ] Explore fallback rendering for HTML pages that require canvas/JS to render tables, logging when conversion occurs.
- [ ] Investigate leveraging DOM semantics to enrich Stage 09 summaries without extra LLM calls.

---

*Status owner:* Pipeline team – mark tasks as `[x]` when merged.
