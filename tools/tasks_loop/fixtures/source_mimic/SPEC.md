---
fixture: source_mimic
pdf: tools/tasks_loop/fixtures/source_mimic/source.pdf
steps:
  s10:
    name: Markdown Exporter
    expected:
      not_contains:
      - SECTION 5 START
  s05:
    name: Table Extractor
    expected:
      table_count: 1
  s08:
    name: Requirement Extractor
    expected:
      requirement_count: 2
---
# Auto-generated Spec from Source Mimic Ground Truth
# This ensures the Contract matches the Twin Intent.
