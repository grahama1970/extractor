#!/usr/bin/env python3
"""
prepare_test_pdf.py - Create the canonical test PDF fixture

This script creates `BHT_CV32A65X_test.pdf` with:
1. Added simulated requirements pages (from original PDF)
2. Fixed section numbering (4.1.5 → 4.1.6)
3. Added test annotations (freetext, highlight, rect)
4. Outputs both annotated and clean versions

Usage:
    python tools/tasks_loop/prepare_test_pdf.py

Output:
    data/input/pipeline/BHT_CV32A65X_test.pdf        # With annotations
    data/input/pipeline/BHT_CV32A65X_test_clean.pdf  # Without annotations
    tools/tasks_loop/fixtures/expected_annotations.json  # Expected annotation data
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    sys.exit("PyMuPDF required: pip install pymupdf")

ROOT = Path(__file__).resolve().parents[2]
INPUT_DIR = ROOT / "data" / "input" / "pipeline"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def add_test_annotations(pdf_path: Path, output_path: Path) -> list[dict]:
    """Add test annotations to a PDF and return their expected data."""
    doc = fitz.open(str(pdf_path))
    annotations = []

    try:
        # Page 0: Add a FreeText annotation
        page0 = doc[0]
        rect0 = fitz.Rect(100, 100, 300, 130)
        page0.add_freetext_annot(
            rect0,
            "Test annotation for Stage 01",
            fontsize=12,
            fontname="Helvetica",
            text_color=(0, 0, 0),
            fill_color=(1, 1, 0.8),
        )
        annotations.append(
            {
                "page": 0,
                "type": "FreeText",
                "bbox": list(rect0),
                "content": "Test annotation for Stage 01",
            }
        )

        # Page 0: Add a Highlight annotation over some text
        rect1 = fitz.Rect(72, 200, 400, 220)
        page0.add_highlight_annot(rect1)
        annotations.append(
            {
                "page": 0,
                "type": "Highlight",
                "bbox": list(rect1),
                "content": None,
            }
        )

        # Page 1: Add a Rect (box) annotation
        if len(doc) > 1:
            page1 = doc[1]
            rect2 = fitz.Rect(150, 300, 450, 400)
            annot2 = page1.add_rect_annot(rect2)
            annot2.set_colors(stroke=(1, 0, 0))  # Red border
            annot2.update()
            annotations.append(
                {
                    "page": 1,
                    "type": "Square",
                    "bbox": list(rect2),
                    "content": None,
                }
            )

        # Page 2: Add a Text (sticky note) annotation
        if len(doc) > 2:
            page2 = doc[2]
            point = fitz.Point(200, 150)
            page2.add_text_annot(point, "Review this section for requirements")
            annotations.append(
                {
                    "page": 2,
                    "type": "Text",
                    "bbox": [200, 150, 220, 170],  # Approximate sticky note size
                    "content": "Review this section for requirements",
                }
            )

        # Handle saving to same file
        if output_path == pdf_path:
            import tempfile

            fd, temp_path = tempfile.mkstemp(suffix=".pdf")
            import os

            os.close(fd)
            doc.save(temp_path)
            doc.close()
            import shutil

            shutil.move(temp_path, str(output_path))
        else:
            doc.save(str(output_path))
    finally:
        doc.close()

    return annotations


def create_clean_pdf(input_path: Path, output_path: Path) -> int:
    """Remove all annotations and return count removed."""
    doc = fitz.open(str(input_path))
    removed = 0
    try:
        for page in doc:
            for annot in list(page.annots()):
                page.delete_annot(annot)
                removed += 1
        doc.save(str(output_path))
    finally:
        doc.close()
    return removed


def main() -> int:
    # Source: Use the version with requirements pages added
    source_with_reqs = INPUT_DIR / "BHT_CV32A65X_with_requirements_noannots.pdf"

    if not source_with_reqs.exists():
        # Fallback: create from original
        original = INPUT_DIR / "BHT CV32A65X_original.pdf"
        if not original.exists():
            print(f"ERROR: No source PDF found in {INPUT_DIR}")
            return 1

        # Add requirements pages first
        print(f"Creating test PDF from: {original}")
        import subprocess

        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "add_simulated_requirements_page.py"),
                "--input",
                str(original),
                "--output",
                str(source_with_reqs),
            ]
        )
        if result.returncode != 0:
            print("ERROR: Failed to add requirements pages")
            return 1

    # Output paths
    test_pdf = INPUT_DIR / "BHT_CV32A65X_test.pdf"
    test_pdf_clean = INPUT_DIR / "BHT_CV32A65X_test_clean.pdf"

    # Step 1: Apply 4.1.5 → 4.1.6 fix
    print("Applying section numbering fix...")
    # Copy source first
    import shutil

    shutil.copy(source_with_reqs, test_pdf)

    # Apply the patch (imports pdf_utils)
    sys.path.insert(0, str(ROOT / "src"))
    from extractor.pipeline.utils.pdf_utils import patch_bht_reqs_table_merge_headers

    patch_bht_reqs_table_merge_headers(test_pdf)
    print("  Fixed: 4.1.5 → 4.1.6")

    # Step 2: Add test annotations
    print("Adding test annotations...")
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    annotations = add_test_annotations(test_pdf, test_pdf)
    print(f"  Added: {len(annotations)} annotations")

    # Save expected annotations
    expected_path = FIXTURES_DIR / "expected_annotations.json"
    expected_path.write_text(json.dumps(annotations, indent=2), encoding="utf-8")
    print(f"  Saved: {expected_path}")

    # Step 3: Create clean version
    print("Creating clean PDF...")
    removed = create_clean_pdf(test_pdf, test_pdf_clean)
    print(f"  Removed: {removed} annotations from clean version")

    # Summary
    print("\n✅ Test fixture created:")
    print(f"   Annotated: {test_pdf}")
    print(f"   Clean:     {test_pdf_clean}")
    print(f"   Expected:  {expected_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
