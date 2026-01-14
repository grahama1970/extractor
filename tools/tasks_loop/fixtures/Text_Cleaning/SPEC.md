---
fixture: Text_Cleaning
pdf: fixtures/Text_Cleaning/source.pdf
generated: 2026-01-13T11:02:33.579974

steps:
  s02:
    name: Marker Blocks
    expected:
      block_count_min: 1
  s05c:
    name: Table Merger
    expected:
      merged_table_count: 0
  s04:
    name: Section Builder
    expected:
      section_count: 1
  s10:
    name: Markdown Exporter
    expected:
      section_headers: 1
---

# Text_Cleaning Fixture Notes

## Generated Content

- **Sections**: 1
- **Tables**: 0
- **Figures**: 0
- **Requirements**: 0
- **Equations**: 0
- **Annotations**: 0

## Sections

- 1. Cleaning Test (page 0)
