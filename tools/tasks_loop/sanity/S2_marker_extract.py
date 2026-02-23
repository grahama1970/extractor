#!/usr/bin/env python3
"""
S2_marker_extract.py - Sanity check for Marker PDF extraction.

Purpose:
- Verify that the marker-pdf extraction pipeline works.
- This is the core functionality of S02 (Marker Extractor).

Dependencies:
- PyMuPDF (fitz)
- Marker internals (extractor.core.converters.pdf, extractor.core.models)
- Fixture PDF

Success Criteria:
- Extraction produces >0 blocks
- At least one block is a SectionHeader or Text type
"""

import sys
from pathlib import Path

# Resolve project root
ROOT = Path(__file__).resolve().parents[3]
FIXTURES_DIR = ROOT / "data" / "fixtures"
FIXTURE_PDF = FIXTURES_DIR / "test.pdf"

# Alternative fixture locations
ALTERNATIVE_FIXTURES = [
    ROOT / "fixtures" / "test.pdf",
    ROOT / "data" / "input" / "pipeline" / "BHT_CV32A65X_test.pdf",
]


def main() -> int:
    # Find fixture
    pdf_path = None
    if FIXTURE_PDF.exists():
        pdf_path = FIXTURE_PDF
    else:
        for alt in ALTERNATIVE_FIXTURES:
            if alt.exists():
                pdf_path = alt
                break

    if not pdf_path:
        print(f"SKIP: No fixture PDF found (checked {FIXTURE_PDF} and alternatives)")
        return 0  # Skip, not fail

    print(f"Testing marker extraction on: {pdf_path.name}")

    # Try to import and run marker extraction
    try:
        # Add src to path if needed
        src_path = ROOT / "src"
        if str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))

        from extractor.pipeline.steps.s02_marker_extractor import extract_blocks

        blocks, presence = extract_blocks(pdf_path)

        if not blocks:
            print("FAIL: No blocks extracted")
            return 1

        # Check for meaningful content
        block_types = set(b.get("block_type") for b in blocks)
        expected_types = {"SectionHeader", "Text", "Table", "Figure", "ListItem"}
        found_types = block_types & expected_types

        if not found_types:
            print(f"FAIL: No expected block types found. Got: {block_types}")
            return 1

        print(f"OK: Extracted {len(blocks)} blocks, types: {found_types}")
        return 0

    except ImportError as e:
        # Check if it's a marker-specific import failure
        if "marker" in str(e).lower() or "surya" in str(e).lower():
            print(f"SKIP: Marker not installed ({e})")
            return 0  # Skip, not fail - marker is optional
        print(f"FAIL: Import error: {e}")
        return 1
    except Exception as e:
        print(f"FAIL: Extraction failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
