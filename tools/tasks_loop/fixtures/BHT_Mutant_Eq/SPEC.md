---
fixture: BHT_Mutant_Eq
pdf: fixtures/BHT_Mutant_Eq/source.pdf
generated: 2026-01-20T22:02:44.538024

steps:
  s02:
    name: Marker Blocks
    expected:
      block_count_min: 31
  s04:
    name: Section Builder
    expected:
      section_count: 5
  s05:
    name: Table Extractor
    expected:
      table_count: 5
  s06:
    name: Figure Extractor
    expected:
      figure_count: 1
  s08:
    name: Requirements (LLM)
    expected:
      requirement_count: 4
  s10:
    name: Markdown Exporter
    expected:
      section_headers: 5
      requirements: 4
      equations_min: 3
---

# BHT_Mutant_Eq Fixture Notes

## Generated Content

- **Sections**: 5
- **Tables**: 5
- **Figures**: 1
- **Requirements**: 4
- **Equations**: 3
- **Annotations**: 0

## Sections

- Document Start (page 0)
- ‭4.1.5.4. BHT (Branch History Table) submodule‬ (page 0)
- 4.1.5.4.1. REQUIREMENTS (Simulated) (page 1)
- 4.1.6 TABLE MERGE SCENARIOS (Simulated) (page 1)
- 4.1.5. TABLE MERGE SCENARIOS (Simulated) (page 1)

## Requirements

- **REQ-001**: REQ-BHT-1: The BHT shall implement BHTDepth entrie...
- **REQ-002**: The BHT shall locate the entry indexed by the prov...
- **REQ-003**: If the indexed entry exists, the BHT shall return ...
- **REQ-004**: Table 4-2 and Table 4-3 are distinct datasets and ...
