---
fixture: boeing_spec
pdf: tools/tasks_loop/fixtures/boeing_spec/source.pdf
agent_config:
  allow_auto_tune: true
  strict_calibration: true
steps:
  s08:
    name: "Requirement Extractor"
    expected:
      requirement_count: 2
---

# Boeing Canonical Archetype

This fixture calibrates for enterprise requirements specs (Boeing/BHT style).

## Key Features

- **Status Markers**: Tests extraction of markers like [APPROVED] or [DRAFT].
- **Nested Clauses**: Tests child-parent relationships in hierarchical lists.
- **Enterprise Headers**: Tests resilience to commercial-off-the-shelf headers/footers.
