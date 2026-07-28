"""Human-agent feedback loop for uncertain PDF extractions.

When the extraction pipeline encounters low-confidence tables, figures, or
sections, this module renders the PDF page, overlays the agent's proposed
bounding boxes, and presents them to a human via the /interview skill's
bbox_annotation question type.

The human can:
- Confirm correct detections (keep)
- Delete false positives (delete)
- Draw missed regions (add)

The agent then re-extracts using the human-corrected coordinates.

Usage:
    from extractor.pipeline.utils.human_feedback import request_bbox_feedback

    corrections = request_bbox_feedback(
        pdf_path="/path/to/doc.pdf",
        page_num=3,
        detections=[
            {"type": "Table", "bbox": [72, 200, 540, 400], "confidence": 0.45},
            {"type": "Figure", "bbox": [100, 500, 480, 700], "confidence": 0.62},
        ],
        render_dpi=150,
        context="S05 table extraction found 2 uncertain regions",
    )
    # corrections = [
    #   {"action": "keep", "type": "Table", "bbox": [72, 200, 540, 400]},
    #   {"action": "delete", "type": "Figure", "bbox": [100, 500, 480, 700]},
    #   {"action": "add", "type": "Table", "bbox": [50, 710, 520, 900]},
    # ]

Env vars:
    HUMAN_FEEDBACK_ENABLED=true   Enable feedback loop (default: false)
    HUMAN_FEEDBACK_THRESHOLD=0.7  Confidence threshold below which feedback is requested
    HUMAN_FEEDBACK_TIMEOUT=600    Seconds to wait for human response (default: 600)
    INTERVIEW_MODE=html           Interview display mode (html or tui)
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

# Skill paths
_SKILLS_DIR = Path(os.environ.get(
    "PI_SKILLS_DIR",
    Path.home() / "workspace/experiments/pi-mono/.pi/skills",
))
_INTERVIEW_DIR = _SKILLS_DIR / "interview"
_PDF_SCREENSHOT_DIR = _SKILLS_DIR / "pdf-screenshot"

# Configuration
FEEDBACK_ENABLED = os.environ.get("HUMAN_FEEDBACK_ENABLED", "false").lower() in ("true", "1", "yes")
CONFIDENCE_THRESHOLD = float(os.environ.get("HUMAN_FEEDBACK_THRESHOLD", "0.7"))
FEEDBACK_TIMEOUT = int(os.environ.get("HUMAN_FEEDBACK_TIMEOUT", "600"))

# Default bbox labels with colors matching the pipeline's asset types
DEFAULT_LABELS = [
    {"name": "Table", "color": "#22c55e"},
    {"name": "Figure", "color": "#f59e0b"},
    {"name": "Section", "color": "#3b82f6"},
    {"name": "Equation", "color": "#a855f7"},
]


def needs_feedback(detections: List[Dict[str, Any]]) -> bool:
    """Check if any detection is below the confidence threshold."""
    if not FEEDBACK_ENABLED:
        return False
    return any(
        d.get("confidence", 1.0) < CONFIDENCE_THRESHOLD
        for d in detections
    )


def render_page(pdf_path: str | Path, page_num: int, dpi: int = 150) -> Optional[Path]:
    """Render a PDF page to PNG using /pdf-screenshot skill.

    Returns path to the rendered PNG, or None on failure.
    """
    pdf_path = Path(pdf_path)
    output_dir = Path(tempfile.mkdtemp(prefix="human_feedback_"))
    output_path = output_dir / f"{pdf_path.stem}_page{page_num}.png"

    run_sh = _PDF_SCREENSHOT_DIR / "run.sh"
    if not run_sh.exists():
        logger.warning("pdf-screenshot skill not found at %s", _PDF_SCREENSHOT_DIR)
        return None

    try:
        result = subprocess.run(
            [
                str(run_sh),
                str(pdf_path),
                "--page", str(page_num),
                "--dpi", str(dpi),
                "--out", str(output_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(_PDF_SCREENSHOT_DIR),
        )
        if result.returncode != 0:
            logger.warning("pdf-screenshot failed: %s", result.stderr[:200])
            return None
        if output_path.exists():
            return output_path
        # Check if it wrote to a different location
        for p in output_dir.iterdir():
            if p.suffix == ".png":
                return p
        return None
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.warning("pdf-screenshot error: %s", exc)
        return None


def request_bbox_feedback(
    *,
    pdf_path: str | Path,
    page_num: int,
    detections: List[Dict[str, Any]],
    render_dpi: int = 150,
    context: str = "",
    labels: Optional[List[Dict[str, str]]] = None,
    timeout: Optional[int] = None,
) -> Optional[List[Dict[str, Any]]]:
    """Request human feedback on bounding box detections for a PDF page.

    Args:
        pdf_path: Path to the source PDF.
        page_num: 0-indexed page number.
        detections: List of {"type": str, "bbox": [x0,y0,x1,y1], "confidence": float}.
        render_dpi: DPI for page rendering (must match pipeline's DPI).
        context: Human-readable context for the question.
        labels: Custom label definitions. Defaults to Table/Figure/Section/Equation.
        timeout: Seconds to wait for response. Defaults to FEEDBACK_TIMEOUT.

    Returns:
        List of annotation dicts with "action" (add/keep/delete), "type", "bbox",
        or None if feedback could not be obtained.
    """
    if not FEEDBACK_ENABLED:
        return None

    pdf_path = Path(pdf_path)
    timeout = timeout or FEEDBACK_TIMEOUT
    labels = labels or DEFAULT_LABELS

    # Step 1: Render the page
    page_image = render_page(pdf_path, page_num, dpi=render_dpi)
    if page_image is None:
        logger.warning("Could not render page %d of %s for feedback", page_num, pdf_path)
        return None

    # Step 2: Build pre-annotations from agent detections
    pre_annotations = []
    for det in detections:
        pre_annotations.append({
            "type": det.get("type", "Table"),
            "bbox": det["bbox"],
            "page": page_num,
        })

    # Step 3: Create interview question JSON
    question = {
        "id": f"bbox_page_{page_num}",
        "type": "bbox_annotation",
        "header": f"Page {page_num}",
        "text": (
            context or
            f"Review {len(detections)} detected region(s) on page {page_num}. "
            "Draw new boxes for missed items, delete false positives."
        ),
        "images": [str(page_image)],
        "bbox_labels": labels,
        "pre_annotations": pre_annotations,
        "render_dpi": render_dpi,
        "page_num": page_num,
    }

    session_data = {
        "title": f"Extraction Review: {pdf_path.stem}",
        "context": f"PDF: {pdf_path.name}\nPage: {page_num}\n{context}",
        "questions": [question],
    }

    # Step 4: Run interview
    interview_file = page_image.parent / "interview_request.json"
    interview_file.write_text(json.dumps(session_data, indent=2))

    run_sh = _INTERVIEW_DIR / "run.sh"
    if not run_sh.exists():
        logger.warning("interview skill not found at %s", _INTERVIEW_DIR)
        return None

    mode = os.environ.get("INTERVIEW_MODE", "html")
    try:
        result = subprocess.run(
            [str(run_sh), "--file", str(interview_file), "--mode", mode],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(_INTERVIEW_DIR),
        )
        if result.returncode != 0:
            logger.warning("interview failed: %s", result.stderr[:200])
            return None
    except subprocess.TimeoutExpired:
        logger.info("Human feedback timed out after %ds for %s page %d", timeout, pdf_path, page_num)
        return None
    except OSError as exc:
        logger.warning("interview error: %s", exc)
        return None

    # Step 5: Parse response
    try:
        # Interview writes response to session file
        sessions_dir = _INTERVIEW_DIR / "sessions"
        # Find the most recent session
        session_files = sorted(sessions_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not session_files:
            logger.warning("No interview session file found")
            return None

        session_resp = json.loads(session_files[0].read_text())
        responses = session_resp.get("responses", {})
        bbox_resp = responses.get(f"bbox_page_{page_num}", {})

        annotations = bbox_resp.get("annotations", [])
        if not annotations:
            # Check if decision was "accept" (all pre-annotations confirmed)
            if bbox_resp.get("decision") == "accept":
                return [{"action": "keep", **a} for a in pre_annotations]
            return None

        return annotations

    except (json.JSONDecodeError, KeyError, IndexError, OSError) as exc:
        logger.warning("Failed to parse interview response: %s", exc)
        return None


def request_multi_page_feedback(
    *,
    pdf_path: str | Path,
    pages: Dict[int, List[Dict[str, Any]]],
    render_dpi: int = 150,
    context: str = "",
    labels: Optional[List[Dict[str, str]]] = None,
    timeout: Optional[int] = None,
) -> Dict[int, List[Dict[str, Any]]]:
    """Request feedback on multiple pages at once.

    Args:
        pdf_path: Path to the source PDF.
        pages: Dict mapping page_num → list of detections.
        render_dpi: DPI for page rendering.
        context: Human-readable context.
        labels: Custom label definitions.
        timeout: Seconds to wait for response.

    Returns:
        Dict mapping page_num → list of annotation corrections.
        Pages with no feedback are omitted.
    """
    results: Dict[int, List[Dict[str, Any]]] = {}

    for page_num, detections in sorted(pages.items()):
        feedback = request_bbox_feedback(
            pdf_path=pdf_path,
            page_num=page_num,
            detections=detections,
            render_dpi=render_dpi,
            context=context,
            labels=labels,
            timeout=timeout,
        )
        if feedback:
            results[page_num] = feedback

    return results
