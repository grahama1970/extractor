#!/usr/bin/env python3
"""
OCR Preprocessing for Scanned PDFs
==================================
Uses OCRmyPDF (via Docker or local install) to add searchable text layer.

This module provides:
- Detection of scanned PDFs
- OCR preprocessing using OCRmyPDF
- Fallback to skip if OCR is not available
"""

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Tuple

from loguru import logger


def is_ocrmypdf_available() -> Tuple[bool, str]:
    """
    Check if OCRmyPDF is available (Docker or local).

    Returns:
        Tuple of (available, method) where method is 'docker', 'local', or 'none'
    """
    # Check for local installation
    if shutil.which("ocrmypdf"):
        return True, "local"

    # Check for Docker
    if shutil.which("docker"):
        try:
            result = subprocess.run(
                ["docker", "image", "inspect", "extractor-ocr"],
                capture_output=True,
                timeout=10,
            )
            if result.returncode == 0:
                return True, "docker"

            # Check for official image
            result = subprocess.run(
                ["docker", "image", "inspect", "jbarlow83/ocrmypdf"],
                capture_output=True,
                timeout=10,
            )
            if result.returncode == 0:
                return True, "docker-official"
        except (subprocess.TimeoutExpired, Exception):
            pass

    return False, "none"


def ocr_preprocess(
    input_pdf: Path,
    output_pdf: Optional[Path] = None,
    language: str = "eng",
    skip_text: bool = True,
    deskew: bool = False,
    timeout: int = 600,
) -> Tuple[bool, Path, str]:
    """
    Preprocess a scanned PDF with OCR to add searchable text layer.

    Args:
        input_pdf: Path to input PDF
        output_pdf: Path to output PDF (default: input_ocr.pdf)
        language: OCR language(s), e.g., "eng" or "eng+deu"
        skip_text: Skip pages that already have text
        deskew: Deskew crooked scans
        timeout: Timeout in seconds

    Returns:
        Tuple of (success, output_path, message)
    """
    input_pdf = Path(input_pdf).resolve()

    if not input_pdf.exists():
        return False, input_pdf, f"Input file not found: {input_pdf}"

    if output_pdf is None:
        output_pdf = input_pdf.parent / f"{input_pdf.stem}_ocr.pdf"
    else:
        output_pdf = Path(output_pdf).resolve()

    available, method = is_ocrmypdf_available()

    if not available:
        return False, input_pdf, "OCRmyPDF not available (install locally or build Docker image)"

    logger.info(f"Running OCR on {input_pdf.name} using {method}")

    # Build command
    if method == "local":
        cmd = ["ocrmypdf"]
    elif method == "docker":
        cmd = [
            "docker", "run", "--rm",
            "-v", f"{input_pdf.parent}:/input:ro",
            "-v", f"{output_pdf.parent}:/output",
            "extractor-ocr",
        ]
        # Adjust paths for Docker
        input_path = f"/input/{input_pdf.name}"
        output_path = f"/output/{output_pdf.name}"
    else:  # docker-official
        cmd = [
            "docker", "run", "--rm",
            "-v", f"{input_pdf.parent}:/input:ro",
            "-v", f"{output_pdf.parent}:/output",
            "jbarlow83/ocrmypdf",
        ]
        input_path = f"/input/{input_pdf.name}"
        output_path = f"/output/{output_pdf.name}"

    # Add options
    cmd.extend(["--language", language])
    cmd.append("--output-type")
    cmd.append("pdfa")

    if skip_text:
        cmd.append("--skip-text")
    if deskew:
        cmd.append("--deskew")

    # Add input/output paths
    if method == "local":
        cmd.extend([str(input_pdf), str(output_pdf)])
    else:
        cmd.extend([input_path, output_path])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode == 0:
            logger.info(f"OCR complete: {output_pdf}")
            return True, output_pdf, "OCR preprocessing successful"
        else:
            error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
            logger.error(f"OCR failed: {error_msg}")
            return False, input_pdf, f"OCR failed: {error_msg}"

    except subprocess.TimeoutExpired:
        return False, input_pdf, f"OCR timed out after {timeout}s"
    except Exception as e:
        return False, input_pdf, f"OCR error: {e}"


def maybe_ocr_preprocess(
    pdf_path: Path,
    scanned_info: dict,
    auto_ocr: bool = False,
    output_dir: Optional[Path] = None,
    language: str = "eng",
    skip_text: bool = True,
    deskew: bool = False,
    timeout: int = 600,
) -> Tuple[Path, dict]:
    """
    Conditionally preprocess a PDF if it's detected as scanned.

    Args:
        pdf_path: Path to input PDF
        scanned_info: Detection info from _detect_scanned_pdf()
        auto_ocr: Whether to automatically OCR scanned PDFs
        output_dir: Directory for OCR output (default: same as input)

    Returns:
        Tuple of (path_to_use, updated_scanned_info)
    """
    if not scanned_info.get("is_scanned"):
        return pdf_path, scanned_info

    if not auto_ocr:
        logger.warning(
            f"PDF detected as scanned but auto_ocr=False. "
            f"Set auto_ocr=True or preprocess with: "
            f"./docker/ocrmypdf/ocr_preprocess.sh {pdf_path}"
        )
        return pdf_path, scanned_info

    # Determine output path
    if output_dir:
        output_pdf = Path(output_dir) / f"{pdf_path.stem}_ocr.pdf"
    else:
        output_pdf = pdf_path.parent / f"{pdf_path.stem}_ocr.pdf"

    success, result_path, message = ocr_preprocess(
        pdf_path,
        output_pdf,
        language=language,
        skip_text=skip_text,
        deskew=deskew,
        timeout=timeout,
    )

    if success:
        scanned_info = scanned_info.copy()
        scanned_info["ocr_applied"] = True
        scanned_info["ocr_output"] = str(result_path)
        return result_path, scanned_info
    else:
        logger.warning(f"OCR preprocessing failed: {message}")
        scanned_info = scanned_info.copy()
        scanned_info["ocr_attempted"] = True
        scanned_info["ocr_error"] = message
        return pdf_path, scanned_info


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m extractor.pipeline.utils.ocr_preprocess <input.pdf> [output.pdf]")
        sys.exit(1)

    input_pdf = Path(sys.argv[1])
    output_pdf = Path(sys.argv[2]) if len(sys.argv) > 2 else None

    available, method = is_ocrmypdf_available()
    print(f"OCRmyPDF available: {available} ({method})")

    if available:
        success, result, message = ocr_preprocess(input_pdf, output_pdf)
        print(f"Result: {message}")
        if success:
            print(f"Output: {result}")
        sys.exit(0 if success else 1)
    else:
        print("OCRmyPDF not available. Install locally or build Docker image:")
        print("  docker build -t extractor-ocr docker/ocrmypdf/")
        sys.exit(1)
