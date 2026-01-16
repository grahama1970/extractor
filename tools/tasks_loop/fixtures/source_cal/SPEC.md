---
fixture: source_cal
pdf: tools/tasks_loop/fixtures/source_cal/source.pdf
agent_config:
  allow_auto_tune: true
  strict_calibration: true
steps:
  s05:
    name: Table Extractor
    expected:
      table_count: 1
  s08:
    name: Requirement Extractor
    expected:
      requirement_count: 2
---

# source_cal Twin

Generated from: source.pdf
Pages: 5
Chaos: hyphenation, ligatures, trapped_headers, nesting_complexity
