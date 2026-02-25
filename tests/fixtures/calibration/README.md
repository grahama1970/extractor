# Calibration Test Fixtures

This directory contains fixtures for testing the calibration workflow.

## Files

### expected_elements.json

Ground truth for a 10-page test document with known elements:

- **Total elements**: 25
- **Headers**: 12 (section headers like "1. Introduction", "1.1 Background")
- **Tables**: 6 (various row/column combinations)
- **Figures**: 7 (with captions like "Figure 3.1: System Architecture")

Each element includes:
- `element_idx`: Index on page
- `element_type`: header, table, or figure
- `bbox`: Bounding box coordinates [x0, y0, x1, y1]
- `expected_verdict`: What a human should say (usually "correct")

### sample_session.json

Pre-recorded calibration session for testing:

- **Session key**: `test_doc_2026-01-20`
- **Preset ID**: `test-document`
- **Status**: `in_progress`
- **Examples reviewed**: 23
- **Accuracy**: 95.65%

Includes:
- Session metadata
- 23 example verdicts (mix of correct and one wrong_type)
- 3 learned patterns (one per element type)
- Aggregated stats

### test_doc.pdf (Generated)

A 10-page PDF with known elements for testing.

**To generate**: Use the `pdf-fixture` skill:

```bash
/pdf-fixture --output tests/fixtures/calibration/test_doc.pdf \
  --pages 10 \
  --sections "Introduction,Requirements,Technical Specifications,Testing Procedures,Deployment,Maintenance,Appendix,References" \
  --tables 6 \
  --figures 7
```

Or programmatically with the `create_test_pdf` helper (see test files).

## Usage in Tests

```python
import json
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "calibration"

# Load expected elements
with open(FIXTURES_DIR / "expected_elements.json") as f:
    expected = json.load(f)

# Load sample session
with open(FIXTURES_DIR / "sample_session.json") as f:
    session = json.load(f)

# Access data
total_elements = expected["summary"]["total_elements"]
session_stats = session["stats"]
```

## Creating New Fixtures

When adding new fixtures:

1. Follow the existing JSON schema
2. Use realistic bounding boxes (Letter paper: 612x792 points)
3. Include expected verdicts for validation
4. Document in this README
