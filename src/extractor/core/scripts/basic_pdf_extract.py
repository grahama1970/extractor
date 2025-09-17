#!/usr/bin/env python3
"""
Basic PDF extraction using PyMuPDF directly
Fallback when marker has import issues
"""

import sys
import json
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    print("ERROR: PyMuPDF not installed. Run: pip install pymupdf")
    sys.exit(1)


def extract_pdf_basic(pdf_path: Path) -> dict:
    """Extract basic text and structure from PDF"""
    blocks = []

    try:
        doc = fitz.open(str(pdf_path))

        for page_num, page in enumerate(doc):
            # Get page dimensions
            page_height = page.rect.height
            page_width = page.rect.width

            # Extract text blocks
            text_dict = page.get_text("dict")

            for block_num, block in enumerate(text_dict["blocks"]):
                if block["type"] == 0:  # Text block
                    block_text = ""
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            block_text += span.get("text", "")
                        block_text += "\n"

                    if block_text.strip():
                        blocks.append(
                            {
                                "type": "Text",
                                "text": block_text.strip(),
                                "page": page_num,
                                "bbox": block["bbox"],
                                "block_id": f"page{page_num}_block{block_num}",
                            }
                        )

        doc.close()

    except Exception as e:
        print(f"ERROR extracting PDF: {e}")
        raise

    return {"blocks": blocks}


def main():
    if len(sys.argv) < 3:
        print("Usage: basic_pdf_extract.py <pdf_path> <output_json>")
        sys.exit(1)

    pdf_path = Path(sys.argv[1])
    output_json = Path(sys.argv[2])

    if not pdf_path.exists():
        print(f"ERROR: PDF not found: {pdf_path}")
        sys.exit(1)

    print(f"Extracting {pdf_path} -> {output_json}")

    try:
        # Extract PDF
        result = extract_pdf_basic(pdf_path)

        # Save output
        with open(output_json, "w") as f:
            json.dump(result, f, indent=2)

        print(f"Success! Extracted {len(result['blocks'])} blocks")
        return 0

    except Exception as e:
        print(f"ERROR: Extraction failed: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
