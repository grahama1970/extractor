#!/usr/bin/env python3
"""
preflight.py - Sanity checks before running gates

Verifies dependencies are available:
- PyMuPDF (fitz)
- Camelot
- SCILLM (optional, soft failure)
- DuckDB

Usage:
    python tools/tasks_loop/preflight.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEST_PDF = ROOT / "data" / "input" / "pipeline" / "BHT_CV32A65X_test.pdf"


def check_pymupdf() -> bool:
    """Check PyMuPDF can open the test PDF."""
    try:
        import fitz
        if not TEST_PDF.exists():
            print(f"WARN: Test PDF not found: {TEST_PDF}")
            return True  # Not a hard failure
        doc = fitz.open(str(TEST_PDF))
        page_count = len(doc)
        doc.close()
        print(f"✅ PyMuPDF: OK ({page_count} pages)")
        return True
    except Exception as e:
        print(f"❌ PyMuPDF: FAIL - {e}")
        return False


def check_camelot() -> bool:
    """Check Camelot can extract tables from test PDF."""
    try:
        import camelot
        if not TEST_PDF.exists():
            print("WARN: Test PDF not found, skipping camelot check")
            return True
        tables = camelot.read_pdf(str(TEST_PDF), pages="1")
        print(f"✅ Camelot: OK ({len(tables)} tables on page 1)")
        return True
    except Exception as e:
        print(f"❌ Camelot: FAIL - {e}")
        return False


def check_duckdb() -> bool:
    """Check DuckDB can create and query a database."""
    try:
        import duckdb
        conn = duckdb.connect(":memory:")
        conn.execute("CREATE TABLE test (id INTEGER)")
        conn.execute("INSERT INTO test VALUES (1)")
        result = conn.execute("SELECT COUNT(*) FROM test").fetchone()
        conn.close()
        print(f"✅ DuckDB: OK (test query returned {result[0]})")
        return True
    except Exception as e:
        print(f"❌ DuckDB: FAIL - {e}")
        return False


def check_scillm() -> bool:
    """Check SCILLM import (soft failure - LLM steps are optional)."""
    try:
        from extractor.pipeline.utils.scillm_router import get_text_router
        print("✅ SCILLM: OK (import successful)")
        return True
    except Exception as e:
        print(f"⚠️  SCILLM: WARN - {e} (LLM steps may fail)")
        return True  # Soft failure


def main() -> int:
    print("=" * 50)
    print("PREFLIGHT CHECKS")
    print("=" * 50)
    print(f"Test PDF: {TEST_PDF}")
    print()
    
    results = [
        ("PyMuPDF", check_pymupdf()),
        ("Camelot", check_camelot()),
        ("DuckDB", check_duckdb()),
        ("SCILLM", check_scillm()),
    ]
    
    print()
    print("=" * 50)
    print("SUMMARY")
    print("=" * 50)
    
    failed = [name for name, passed in results if not passed]
    for name, passed in results:
        status = "✅" if passed else "❌"
        print(f"  {status} {name}")
    
    if failed:
        print(f"\n❌ PREFLIGHT FAILED: {failed}")
        return 1
    else:
        print("\n✅ PREFLIGHT PASSED")
        return 0


if __name__ == "__main__":
    sys.exit(main())
