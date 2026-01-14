#!/usr/bin/env python3
"""
S20_create_fixture_sanity.py - Sanity check for create_fixture_pdf.py

Verifies that we can programmatically generate complex test PDFs.
"""
import sys
import shutil
from pathlib import Path

# Add utils to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "utils"))
try:
    from create_fixture_pdf import create_fixture
except ImportError:
    print("❌ Failed to import create_fixture_pdf")
    sys.exit(1)

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "sanity_output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def run():
    print("== Sanity S20: Create Fixture PDF ==")
    
    fixture_name = "sanity_generated_fixture"
    
    # Define a complex spec
    spec = {
        "style": "standard",
        "sections": [
            {
                "title": "1. Test Section",
                "content": [
                    {"type": "text", "text": "This is a sanity check for PDF generation."},
                    {"type": "table", "columns": ["Col A", "Col B"], "rows": 2},
                    {"type": "figure", "description": "Sanity Check Diagram"},
                ]
            },
            {
                "title": "2. Equations",
                "content": [
                    {"type": "equation", "latex": "E = mc^2"},
                    {"type": "requirement", "id": "REQ-SANITY-001", "text": "The generator shall work."}
                ]
            }
        ]
    }
    
    try:
        fixture_dir = create_fixture(spec, fixture_name)
        
        # Verify outputs
        pdf_path = fixture_dir / "source.pdf"
        spec_path = fixture_dir / "SPEC.md"
        
        if not pdf_path.exists():
            print("❌ PDF not created")
            return 1
            
        if not spec_path.exists():
            print("❌ SPEC.md not created")
            return 1
            
        # Check output sizes
        if pdf_path.stat().st_size < 1000:
            print(f"❌ PDF seemingly too small: {pdf_path.stat().st_size} bytes")
            return 1
            
        print(f"✅ Created fixture at {fixture_dir}")
        print(f"✅ Generated PDF and SPEC.md successfully")
        
        # Cleanup (optional, maybe keep for inspection)
        # shutil.rmtree(fixture_dir)
        
        return 0
        
    except Exception as e:
        print(f"❌ Exception during generation: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(run())
