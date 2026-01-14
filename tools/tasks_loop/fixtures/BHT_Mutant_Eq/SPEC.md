---
fixture: BHT_Mutant_Eq
pdf: fixtures/BHT_Mutant_Eq/source.pdf
generated: 2026-01-13T11:40:44.601471

steps:
  s02:
    name: Marker Blocks
    expected:
      block_count_min: 26
  s04:
    name: Section Builder
    expected:
      section_count_min: 1 # Existence check (Schema-Based Gate)
  s05:
    name: Table Extractor
    expected:
      table_count_min: 1 # Existence check
  s06:
    name: Figure Extractor
    expected:
      figure_count_min: 0 # Can be zero
  s08:
    name: Requirements (LLM)
    expected:
      requirement_count_min: 1 # Existence check
  s10:
    name: Markdown Exporter
    expected:
      section_headers_min: 1
      requirements_min: 1
      equations_min: 0
---

# BHT_Mutant_Eq Fixture Notes

## Generated Content

- **Sections**: 4
- **Tables**: 3
- **Figures**: 0
- **Requirements**: 4
- **Equations**: 3
- **Annotations**: 0

## Sections

- Document Start (page 0)
- 4.1.5.4.1. REQUIREMENTS (Simulated) (page 1)
- 4.1.6 TABLE MERGE SCENARIOS (Simulated) (page 1)
- 4.1.5. TABLE MERGE SCENARIOS (Simulated) (page 1)

## Requirements

- **REQ-001**: REQ-BHT-1: The BHT shall implement BHTDepth entrie...
- **REQ-002**: The BHT shall locate the entry indexed by the prov...
- **REQ-003**: If the indexed entry exists, the BHT shall return ...
- **REQ-004**: Table 4-2 and Table 4-3 are distinct datasets and ...
