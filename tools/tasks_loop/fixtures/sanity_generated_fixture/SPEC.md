---
fixture: sanity_generated_fixture
pdf: fixtures/sanity_generated_fixture/source.pdf
generated: 2026-02-09T07:56:43.958657

steps:
  s02:
    name: Marker Blocks
    expected:
      block_count_min: 12
  s04:
    name: Section Builder
    expected:
      section_count: 2
  s05:
    name: Table Extractor
    expected:
      table_count: 1
  s06:
    name: Figure Extractor
    expected:
      figure_count: 1
  s08:
    name: Requirements (LLM)
    expected:
      requirement_count: 1
  s10:
    name: Markdown Exporter
    expected:
      section_headers: 2
      requirements: 1
      equations_min: 1
---

# sanity_generated_fixture Fixture Notes

## Generated Content

- **Sections**: 2
- **Tables**: 1
- **Figures**: 1
- **Requirements**: 1
- **Equations**: 1
- **Annotations**: 0

## Sections

- 1. Test Section (page 0)
- 2. Equations (page 0)

## Requirements

- **REQ-SANITY-001**: The generator shall work....
