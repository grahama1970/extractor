# Structured Formats → PDF Parity Plan

Legend: `[ ]` todo · `[~]` in progress · `[x]` done

Goal
- Bring HTML, DOCX, PPTX, Spreadsheet (XLSX/ODS), EPUB, RST, and Markdown to near‑parity with the PDF pipeline at Stage 10 by producing comparable `reflowed_sections` (+ `unified_document`) without LLM/reflow.
- Use mature libraries already present in providers; no custom parsers.
- Guard with smokes that comply with `docs/SMOKES_GUIDE.md` and Happy Path.

Global
- [x] Structured dispatcher routes non‑PDF formats to a fast path (`structured_pipeline.py`).
- [x] Parity smoke: `scripts/smokes/pipeline/smoke_structured_pdf_parity.py` (format‑agnostic).
- [ ] Tighten structured section builder to prefer provider hierarchies when available and assemble paragraphs/tables/figures per section deterministically.
- [ ] Update Stage 10 assertions to tolerate minor diffs but fail on missing tables/figures or mismatched heading titles.

Acceptance (per format)
- Flattened counts close (delta ≤ N) and types present (Text/Table/Figure as appropriate).
- Headings/section titles align with PDF (same order and labels where feasible).
- Tables present with matching row/column counts; figures present with captions.
- Artifacts: save structured `07_reflowed.json`, flattened `10_flattened_data.json`, and the smoke summary under `scripts/artifacts/`.

## HTML (BeautifulSoup + lxml)
- [ ] Headings → hierarchy: map `h1..h6` to `HierarchyNode(level=1..6)`; attach breadcrumbs.
- [ ] Paragraph aggregation: coalesce contiguous text nodes under the nearest heading.
- [ ] Tables: parse `<table>` → `TableBlock` with rows/cols/cells; detect header row.
- [ ] Figures: `<figure>/<img>` + `alt`/`figcaption` → `Figure` with caption; link image path.
- [ ] Links/refs: preserve anchors/URLs in block attributes where useful.
- [ ] Smoke: run parity vs PDF; assert headings/tables/figures present.

## DOCX (python-docx + docx2python)
- [ ] Numbered headings: read `w:numPr` and style (`Heading N`) to build levels accurately (e.g., 2.1.1).
- [ ] Paragraph aggregation: assign paragraphs to their nearest heading.
- [ ] Tables: use `python-docx` `document.tables` as primary; fallback to `docx2python` when needed.
- [ ] Figures/images: extract inline images; heuristics for captions (preceding/succeeding italic/"Figure" paragraphs).
- [ ] Footnotes/endnotes/comments: add as blocks or attributes as appropriate.
- [ ] Smoke: parity vs PDF; assert at least one table and the key section heading exists.

## PPTX (python-pptx)
- [ ] Slides → sections: map each slide title to a top‑level section; speaker notes as paragraphs.
- [ ] Slide tables: extract shapes of type `TABLE` into `TableBlock`.
- [ ] Images/figures: extract pictures; derive captions from alt/title or nearby text boxes.
- [ ] Ordering: respect slide order; include slide number in metadata.
- [ ] Smoke: parity vs PDF; expect fewer sections but figures/tables present when applicable.

## Spreadsheets (openpyxl / odfpy)
- [ ] Sheets → sections: each worksheet becomes a section (`title=sheet name`).
- [ ] Tables: entire sheet or named ranges; rows/cols/cells preserved; first row as headers.
- [ ] Images: embedded images as figures; note positions.
- [ ] Optional: allow “row blocks” as paragraphs when a description column exists.
- [ ] Smoke: parity vs PDF on known table dimensions; ignore unrelated text delta.

## RST (docutils)
- [ ] Use doctree `section` nodes for hierarchy; titles/levels from nodes.
- [ ] Paragraphs/list/code blocks under their parent section.
- [ ] Tables: map docutils tables (grid/simple) to `TableBlock`.
- [ ] Images: `image` nodes with `alt` and adjacent captions.
- [ ] Smoke: parity vs PDF section headings and at least one figure/table when present.

## Markdown (markdown-it-py or mistune)
- [ ] Headings `#..######` → hierarchy; lists/paragraphs assigned accordingly.
- [ ] GFM tables to `TableBlock`; fenced code blocks preserved.
- [ ] Images `![alt](src)` + nearby captions.
- [ ] Smoke: parity vs PDF for headings/tables.

## XML (lxml)
- [ ] Schema‑aware mapping: configure element→block mapping (e.g., `<section>`, `<title>`, `<table>`, `<figure>`).
- [ ] Attributes: carry IDs, xrefs; captions from known tags.
- [ ] Smoke: parity vs PDF on headings/tables where the schema permits.

## Smokes & CI
- [ ] Add per‑format smoke invocations to a Make target (`make smoke-structured-parity`) and VS Code task.
- [ ] Record artifact paths in issues/PRs under `scripts/artifacts/` as per `docs/SMOKES_GUIDE.md`.
- [ ] Gate: fail on missing tables/figures for formats that should contain them; allow small text deltas.

## References (libraries we already use)
- python-docx (numbering/style), docx2python (paragraph/text grid)
- python-pptx (shapes, placeholders, notes)
- BeautifulSoup + lxml (HTML DOM parsing)
- openpyxl / odfpy (spreadsheets)
- ebooklib (EPUB TOC/content)
- docutils (RST doctree)

## Quick commands
- HTML fast‑path: `python -m extractor.pipeline.pipeline_router data/.../BHT_CV32A65X_marked_clean.html --results data/results/structured_pipelines`
- Parity smoke: `python scripts/smokes/pipeline/smoke_structured_pdf_parity.py data/results/pipeline/07_reflow_section/json_output/07_reflowed.json data/results/.../<format-file> --format <html|docx|pptx|spreadsheet|epub|rst|xml>`

Status owner: Pipeline team — mark items as `[x]` when merged.
