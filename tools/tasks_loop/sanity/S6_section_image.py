#!/usr/bin/env python3
"""
S6_section_image.py - Sanity check for section/region image rendering.

Purpose:
- Verify that we can render a section of a PDF to a PNG image.
- This is the core functionality for S04a (Layout Audit) visual proofs.

Dependencies:
- PyMuPDF (fitz)
- Fixture PDF

Success Criteria:
- PNG file created
- PNG file has non-zero size
"""

import sys
import tempfile
from pathlib import Path

# Resolve project root
ROOT = Path(__file__).resolve().parents[3]
FIXTURES_DIR = ROOT / "data" / "fixtures"
FIXTURE_PDF = FIXTURES_DIR / "test.pdf"

ALTERNATIVE_FIXTURES = [
    ROOT / "fixtures" / "test.pdf",
    ROOT / "data" / "input" / "pipeline" / "BHT_CV32A65X_test.pdf",
]


def main() -> int:
    try:
        import fitz
    except ImportError:
        print("FAIL: PyMuPDF (fitz) not installed")
        return 1
    
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
        print(f"SKIP: No fixture PDF found")
        return 0
    
    print(f"Testing section image rendering on: {pdf_path.name}")
    
    try:
        doc = fitz.open(str(pdf_path))
        if len(doc) == 0:
            print("FAIL: PDF has no pages")
            return 1
        
        page = doc[0]
        
        # Define a region (top quarter of page)
        rect = fitz.Rect(
            page.rect.x0,
            page.rect.y0,
            page.rect.x1,
            page.rect.y0 + page.rect.height / 4
        )
        
        # Render to pixmap
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=rect)
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            out_path = Path(f.name)
        
        pix.save(str(out_path))
        doc.close()
        
        # Verify
        if not out_path.exists():
            print("FAIL: PNG file not created")
            return 1
        
        size = out_path.stat().st_size
        if size == 0:
            print("FAIL: PNG file is empty")
            out_path.unlink()
            return 1
        
        print(f"OK: Created PNG ({size} bytes) at {out_path}")
        out_path.unlink()  # Cleanup
        return 0
        
    except Exception as e:
        print(f"FAIL: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
