---
fixture: example_test
pdf: fixtures/example_test/source.pdf
generated: 2026-01-12T13:41:49.593421

steps:
  s02:
    name: Marker Blocks
    expected:
      block_count_min: 17
  s04:
    name: Section Builder
    expected:
      section_count: 3
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
      requirement_count: 2
---

# example_test Fixture Notes

## Generated Content

- **Sections**: 3
- **Tables**: 1
- **Figures**: 1
- **Requirements**: 2
- **Equations**: 2
- **Annotations**: 0

## Sections

- 1. Introduction (page 0)
- 2. Requirements (page 0)
- 3. Analysis (page 0)

## Requirements

- **REQ-001**: The system shall process input within 1 second....
- **REQ-002**: The system must support UTF-8 encoding....
