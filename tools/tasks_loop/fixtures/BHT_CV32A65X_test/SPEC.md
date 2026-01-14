---
# BHT_CV32A65X_test Fixture Contract
# Ground truth validation fixture for real BHT specification
description: |
  Real BHT CV32A65X specification document.
  Used for ground truth validation of extraction accuracy.

steps:
  s01:
    expected:
      output_dir: "01_annotation_processor"
      output_files: ["source_clean.pdf"]
  s02:
    expected:
      output_type: "json"
      block_count_min: 1
  s03:
    expected:
      output_type: "json"
      header_count_min: 1
  s04:
    expected:
      # Real BHT has more sections than synthetic fixture
      section_count_min: 3
  s05:
    expected:
      table_count_min: 1
  s06:
    expected:
      figure_count_min: 0
  s07:
    expected:
      database: "pipeline.duckdb"
  s07b:
    expected:
      pass_through: true
  s08:
    expected:
      # Ground truth: expect multiple requirements
      requirement_count_min: 3
  s09:
    expected:
      pass_through: true
  s10:
    expected:
      output_dir: "10_markdown_exporter"
      status: "PASS"
  s14:
    expected:
      status: "PASS"
---

# BHT CV32A65X Test Fixture

**Ground Truth Validation** - This fixture uses the real BHT specification PDF
to validate extraction accuracy against known requirements.

## Expected Elements

| Element      | Minimum Count | Notes                                        |
| ------------ | ------------- | -------------------------------------------- |
| Sections     | ≥3            | Introduction, Functional Description, Design |
| Tables       | ≥1            | Configuration parameters, truth tables       |
| Requirements | ≥3            | Shall/must statements                        |
| Conditionals | ≥1            | When/If requirements                         |

## Verification Notes

- All tables are requirements (defines behavioral specifications)
- Conditional patterns: "When X: Y", "If X, Y"
- ID patterns: REQ-BHT-_, REQ-_
