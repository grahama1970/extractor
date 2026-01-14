#!/usr/bin/env python3
"""
Simple marker extraction without LLM processors
"""

import sys
import json
from pathlib import Path

# Try marker/extractor PdfConverter; if unavailable, we will robustly fall back to PyMuPDF
PdfConverter = None  # type: ignore
create_model_dict = None  # type: ignore
try:
    from marker.converters.pdf import PdfConverter as _PdfConverter  # type: ignore
    from marker.models import create_model_dict as _create_model_dict  # type: ignore
    PdfConverter = _PdfConverter
    create_model_dict = _create_model_dict
except Exception:
    try:
        from extractor.core.converters.pdf import PdfConverter as _PdfConverter2  # type: ignore
        from extractor.core.models import create_model_dict as _create_model_dict2  # type: ignore
        PdfConverter = _PdfConverter2
        create_model_dict = _create_model_dict2
    except Exception:
        PdfConverter = None  # type: ignore
        create_model_dict = None  # type: ignore


def main():
    if len(sys.argv) < 3:
        print("Usage: simple_marker_extract.py <pdf_path> <output_json>")
        sys.exit(1)

    pdf_path = Path(sys.argv[1])
    output_json = Path(sys.argv[2])

    if not pdf_path.exists():
        print(f"ERROR: PDF not found: {pdf_path}")
        sys.exit(1)

    print(f"Extracting {pdf_path} -> {output_json}")

    try:
        if PdfConverter is not None and create_model_dict is not None:
            # Create minimal config
            config = {
                "disable_multiprocessing": True,
                "output_format": "json",
                "disable_image_extraction": True,
                "disable_ocr": False,
                "paginate_output": False,
            }
            print("Loading models...")
            models = create_model_dict()
            # Use safest constructor signature; avoid free‑form processor strings to prevent upstream changes
            print("Creating converter...")
            converter = PdfConverter(config=config, artifact_dict=models)
            print("Converting PDF…")
            result, images, metadata = converter(str(pdf_path))
            blocks = getattr(result, "blocks", []) if result is not None else []
            
            # FIX: If Marker returns 0 blocks, force fallback to PyMuPDF
            if not blocks:
                raise RuntimeError("Marker returned 0 blocks; forcing PyMuPDF fallback")

            output_data = {"blocks": blocks, "metadata": metadata}
            with open(output_json, "w") as f:
                json.dump(output_data, f, indent=2)
            print(f"Success! Output saved to {output_json}")
            return 0
        else:
            raise RuntimeError("Marker PdfConverter unavailable; using PyMuPDF fallback")
    except Exception as e:
        # Robust fallback: PyMuPDF text blocks with bbox/page_index
        print(f"WARN: Marker path failed ({e}); falling back to PyMuPDF block extraction")
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(pdf_path)
            blocks = []
            for page_idx, page in enumerate(doc):
                try:
                    for b in page.get_text("blocks"):
                        if not b:
                            continue
                        x0, y0, x1, y1, *rest = b
                        text = ""
                        if len(rest) >= 1 and isinstance(rest[0], str):
                            text = rest[0]
                        blocks.append({
                            "block_type": "Text",
                            "page_idx": page_idx,
                            "page": page_idx,
                            "text": (text or "").strip(),
                            "bbox": [float(x0), float(y0), float(x1), float(y1)],
                        })
                except Exception:
                    continue
            output_data = {"blocks": blocks, "metadata": {"source": str(pdf_path)}}
            with open(output_json, "w") as f:
                json.dump(output_data, f, indent=2)
            print(f"Fallback success. Output saved to {output_json}")
            return 0
        except Exception as e2:
            print(f"ERROR: Fallback extraction failed: {e2}")
            import traceback
            traceback.print_exc()
            return 1


if __name__ == "__main__":
    sys.exit(main())
