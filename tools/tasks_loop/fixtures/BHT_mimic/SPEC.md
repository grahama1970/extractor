---
fixture: BHT_mimic
pdf: fixtures/BHT_mimic/source.pdf
generated: 2026-01-13T10:16:52.410541

steps:
  s02:
    name: Marker Blocks
    expected:
      block_count_min: 27
  s04:
    name: Section Builder
    expected:
      section_count: 4
  s05:
    name: Table Extractor
    expected:
      table_count: 6
  s06:
    name: Figure Extractor
    expected:
      figure_count: 1
  s10:
    name: Markdown Exporter
    expected:
      section_headers: 4
---

# BHT_mimic Fixture Notes

## Generated Content

- **Sections**: 4
- **Tables**: 6
- **Figures**: 1
- **Requirements**: 0
- **Equations**: 0
- **Annotations**: 0

## Sections

- Document Start (page 0)
- ‭BHT is implemented as a memory which is composed of‬ ‭BHTDepth configuration parameter‬ (page 0)
- ‭For any HW configuration,‬ (page 1)
- ‭As DebugEn = False,‬ (page 1)
