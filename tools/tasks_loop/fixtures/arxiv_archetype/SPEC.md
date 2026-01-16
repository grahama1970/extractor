---
fixture: arxiv_archetype
pdf: tools/tasks_loop/fixtures/arxiv_archetype/source.pdf
agent_config:
  allow_auto_tune: true
  strict_calibration: true

# Step 00: Expected Profile (Pre-Flight Assessment)
# This defines what the profile detector should find for this fixture type.
# Updated to match actual arxiv_archetype source.pdf content
profile:
  domain: engineering # PDF has requirements text
  layout: double
  elements:
    tables: false
    figures: false
    formulas: false
    requirements: true
  section_style: markdown

steps:
  s00:
    name: "Profile Detector"
    expected:
      domain: engineering
      layout: { columns: 2, style: double }
      route: fast # No formulas = fast route
  s04:
    name: "Section Builder"
    expected:
      section_count: 5
      required_headings:
        ["Abstract", "1. Background", "Equations & Math", "References [1]"]
  s05:
    name: "Table Extractor"
    expected:
      table_count: 1
  s06:
    name: "Figure Extractor"
    expected:
      figure_count: 0
---

# ArXiv Canonical Archetype

This fixture calibrates the pipeline for scientific literature following the standard 2-column ArXiv/LaTeX templates.

## Key Features

- **2-Column Layout**: Tests reading order across vertical gutters.
- **Equations**: Tests preservation of math fragments (e.g., E = mc²).
- **Citations**: Tests handling of bracketed references [1] without breaking block flow.
- **Abstract Zone**: Tests specialized preamble sections.
