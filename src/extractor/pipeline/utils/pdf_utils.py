"""
Simple PDF utility functions

No complex classes, just simple functions that work!
"""

import fitz  # PyMuPDF
from pathlib import Path
from typing import Dict, Any, List, Optional
from loguru import logger
from extractor.pipeline.utils.reliability import log_stage_error


def clean_pdf(input_path: str, output_path: str, remove_annotations: bool = True) -> Dict[str, Any]:
    """Remove annotations from a PDF to create a clean version for Marker.

    Args:
        input_path: Path to input PDF
        output_path: Path to save cleaned PDF
        remove_annotations: Whether to remove annotations

    Returns:
        Dict with success status and annotation count
    """
    ctx = {"input": input_path, "output": output_path}
    try:
        # Open the PDF
        pdf_doc = fitz.open(input_path)
        annotations_removed = 0

        if remove_annotations:
            # Remove all annotations from all pages
            for page_num in range(len(pdf_doc)):
                page = pdf_doc[page_num]

                # Get list of annotations (iterate backwards to avoid index issues)
                annots = list(page.annots())
                for annot in reversed(annots):
                    page.delete_annot(annot)
                    annotations_removed += 1

        # Save the cleaned PDF
        pdf_doc.save(output_path)
        pdf_doc.close()

        logger.info(f"Created clean PDF: {output_path}, removed {annotations_removed} annotations")

        return {
            "success": True,
            "annotations_removed": annotations_removed,
            "output_path": output_path,
        }

    except Exception as e:
        log_stage_error("pdf_utils.clean_pdf", e, ctx)
        raise


def extract_image_from_bbox(
    pdf_path: Path, page_num: int, bbox: List[float], zoom: float = 2.0
) -> Optional[bytes]:
    """Extract an image from a specific bbox in a PDF page.

    Args:
        pdf_path: Path to PDF
        page_num: Page number (0-indexed)
        bbox: [x0, y0, x1, y1] coordinates
        zoom: Zoom factor for better quality

    Returns:
        PNG image bytes or None
    """
    ctx = {"pdf": str(pdf_path), "page": page_num}
    try:
        pdf_doc = fitz.open(str(pdf_path))

        if page_num >= len(pdf_doc):
            return None

        page = pdf_doc[page_num]

        # Convert bbox to fitz.Rect
        rect = fitz.Rect(bbox)

        # Create matrix for zoom
        mat = fitz.Matrix(zoom, zoom)

        # Extract the region
        pix = page.get_pixmap(matrix=mat, clip=rect)
        img_data = pix.tobytes("png")

        pdf_doc.close()

        return img_data

    except Exception as e:
        log_stage_error("pdf_utils.extract_image_from_bbox", e, ctx)
        raise


def replace_text_in_pdf(
    input_path: Path,
    output_path: Path,
    replacements: Dict[int, Dict[str, str]],
) -> None:
    """Naive in-place text replacement for small, trusted PDFs.

    Args:
        input_path: source PDF path
        output_path: where to write the modified PDF
        replacements: {page_index: {old_text: new_text, ...}, ...}
    """
    doc = fitz.open(str(input_path))
    try:
        for page_index, mapping in replacements.items():
            if page_index < 0 or page_index >= len(doc):
                continue
            page = doc[page_index]
            text = page.get_text("text")
            new_text = text
            for old, new in mapping.items():
                if old in new_text:
                    new_text = new_text.replace(old, new)
            if new_text != text:
                # Clear page and reinsert as a single text block.
                page.clean_contents()
                page.insert_text(
                    fitz.Point(72, 72),
                    new_text,
                    fontsize=11,
                )
        doc.save(str(output_path))
    finally:
        doc.close()


def patch_bht_reqs_table_merge_headers(pdf_path: Path) -> None:
    """Patch TABLE MERGE SCENARIOS headings in BHT_CV32A65X_reqs.pdf.

    Changes:
      4.1.5. TABLE MERGE SCENARIOS (Simulated)
        -> 4.1.6 TABLE MERGE SCENARIOS (Simulated)
      4.1.5. TABLE MERGE SCENARIOS (Simulated) - Continued
        -> 4.1.6 TABLE MERGE SCENARIOS (Simulated) - Continued
    """

    def _rgb_from_int(n: int) -> tuple[float, float, float]:
        r = (n >> 16) & 0xFF
        g = (n >> 8) & 0xFF
        b = n & 0xFF
        return (r / 255.0, g / 255.0, b / 255.0)

    doc = fitz.open(str(pdf_path))
    try:
        targets = {
            3: {
                "old": "4.1.5. TABLE MERGE SCENARIOS (Simulated)",
                "new": "4.1.6 TABLE MERGE SCENARIOS (Simulated)",
            },
            4: {
                "old": "4.1.5. TABLE MERGE SCENARIOS (Simulated) - Continued",
                "new": "4.1.6 TABLE MERGE SCENARIOS (Simulated) - Continued",
            },
        }

        for page_index, spec in targets.items():
            if page_index < 0 or page_index >= len(doc):
                continue
            page = doc[page_index]
            d = page.get_text("dict")
            for block in d.get("blocks", []):
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        txt = span.get("text") or ""
                        if spec["old"] in txt:
                            bbox = span.get("bbox")
                            if not bbox:
                                continue
                            rect = fitz.Rect(bbox)
                            color_int = (
                                int(span.get("color", 0)) if span.get("color") is not None else 0
                            )
                            color = _rgb_from_int(color_int) if color_int else (0, 0, 0)
                            fontname = span.get("font") or "Helvetica"
                            fontsize = float(span.get("size") or 12.0)
                            # Paint over old text and draw the new heading at same position
                            page.draw_rect(rect, color=(1, 1, 1), fill=(1, 1, 1))
                            page.insert_text(
                                fitz.Point(bbox[0], bbox[1] + fontsize),
                                spec["new"],
                                fontname=fontname,
                                fontsize=fontsize,
                                color=color,
                            )
                            break
                    else:
                        continue
                    break
        # Save incrementally to modify in place
        doc.save(str(pdf_path), incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)
    finally:
        doc.close()
