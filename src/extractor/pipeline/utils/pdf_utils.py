"""
Simple PDF utility functions

No complex classes, just simple functions that work!
"""

import fitz  # PyMuPDF
from pathlib import Path
from typing import Dict, Any, List, Optional
from loguru import logger


def clean_pdf(input_path: str, output_path: str, remove_annotations: bool = True) -> Dict[str, Any]:
    """Remove annotations from a PDF to create a clean version for Marker.
    
    Args:
        input_path: Path to input PDF
        output_path: Path to save cleaned PDF
        remove_annotations: Whether to remove annotations
        
    Returns:
        Dict with success status and annotation count
    """
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
            "output_path": output_path
        }
        
    except Exception as e:
        logger.error(f"Failed to clean PDF: {e}")
        return {
            "success": False,
            "error": str(e),
            "annotations_removed": 0
        }


def extract_image_from_bbox(
    pdf_path: Path,
    page_num: int,
    bbox: List[float],
    zoom: float = 2.0
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
        logger.error(f"Failed to extract image: {e}")
        return None