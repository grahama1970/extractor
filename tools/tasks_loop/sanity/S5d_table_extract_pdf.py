#!/usr/bin/env python3
"""
S5d_table_extract_pdf.py - Sanity check for real PDF table extraction.

Purpose:
- Verify that Camelot can extract tables from our actual fixture PDF.
- S3_camelot_extract_fixture uses a hello-world PDF, this uses the real fixture.

Dependencies:
- camelot-py[cv]
- Fixture PDF

Success Criteria:
- At least 1 table extracted from fixture PDF
- Table has rows and columns
"""

import sys
from pathlib import Path

# Resolve project root
ROOT = Path(__file__).resolve().parents[3]
FIXTURE_PDF = ROOT / "data" / "input" / "pipeline" / "BHT_CV32A65X_test.pdf"


def main() -> int:
    try:
        import camelot
    except ImportError:
        print("FAIL: camelot-py not installed")
        return 1

    if not FIXTURE_PDF.exists():
        print(f"SKIP: Fixture PDF not found: {FIXTURE_PDF}")
        return 0

    print(f"Testing table extraction on: {FIXTURE_PDF.name}")

    try:
        # Try lattice mode first (structured tables)
        tables = camelot.read_pdf(str(FIXTURE_PDF), pages="1-5", flavor="lattice")

        if len(tables) == 0:
            print("  Lattice mode found 0 tables, trying stream...")
            tables = camelot.read_pdf(str(FIXTURE_PDF), pages="1-5", flavor="stream")

        if len(tables) == 0:
            print("FAIL: No tables extracted from fixture PDF")
            return 1

        print(f"  Found {len(tables)} table(s)")

        # Verify first table has content
        first = tables[0]
        df = first.df
        rows, cols = df.shape

        if rows < 1 or cols < 1:
            print(f"FAIL: First table is empty ({rows}x{cols})")
            return 1

        print(f"  First table: {rows} rows x {cols} cols")
        print(f"  Preview: {df.iloc[0].tolist()[:3]}...")

        print("\n✅ PDF table extraction sanity check passed")
        return 0

    except Exception as e:
        print(f"FAIL: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
