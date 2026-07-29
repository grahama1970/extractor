"""ML-based strategy prediction helpers for Stage 05.

Contains:
- Shadow S00 classifier integration (seed producer for strategy ordering)
- Strategy predictor (ensemble ML model for optimal Camelot strategy selection)
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from loguru import logger



# ------------------------------------------------------------------
# Shadow S00 classifier (Shadow-LEGO seed producer)
# ------------------------------------------------------------------

SHADOW_S00_ENABLED = os.environ.get("SHADOW_S00", "false").lower() == "true"
_shadow_s00_predictor = None


def _get_shadow_s00_prediction(profile: dict) -> dict:
    """Get Shadow S00 prediction. Returns empty dict on any failure.

    This is a SEED PRODUCER -- informs strategy ordering, never gates.
    """
    global _shadow_s00_predictor
    if not SHADOW_S00_ENABLED:
        return {}
    try:
        if _shadow_s00_predictor is None:
            # Import from sibling pi-mono repo. Use env var or path discovery.
            scripts_dir = os.environ.get("SHADOW_S00_SCRIPTS_DIR", "")
            if not scripts_dir:
                # Auto-discover from extractor repo -> pi-mono sibling
                extractor_root = Path(__file__).resolve().parents[5]
                scripts_dir = str(extractor_root.parent / "pi-mono" / ".pi" / "skills" / "create-table-classifier" / "scripts")
            if scripts_dir not in sys.path:
                sys.path.insert(0, scripts_dir)
            from shadow_s00_inference import ShadowS00Predictor
            _shadow_s00_predictor = ShadowS00Predictor()
        pred = _shadow_s00_predictor.predict(profile)
        return {
            "predicted_class": pred.predicted_class,
            "needs_stream": pred.needs_stream,
            "stream_confidence": pred.stream_confidence,
            "class_probabilities": pred.class_probabilities,
        }
    except Exception as e:
        logger.debug(f"Shadow S00 prediction failed (non-blocking): {e}")
        return {}


# ------------------------------------------------------------------
# Strategy Predictor (ML-based strategy selection)
# ------------------------------------------------------------------

USE_STRATEGY_PREDICTOR = os.getenv("USE_STRATEGY_PREDICTOR", "false").lower() in (
    "1",
    "true",
    "yes",
    "y",
)
STRATEGY_PREDICTOR_CONFIDENCE_THRESHOLD = float(
    os.getenv("STRATEGY_PREDICTOR_CONFIDENCE_THRESHOLD", 0.75)
)
STRATEGY_PREDICTOR_MODEL_PATH = os.getenv(
    "STRATEGY_PREDICTOR_MODEL_PATH",
    str(
        Path.home()
        / "workspace/experiments/pi-mono/.pi/skills/create-table-classifier/models/table-classifier-ensemble-final"
    ),
)

# Global predictor instance (lazy loaded)
_strategy_predictor = None


def _get_strategy_predictor():
    """Lazy load the strategy predictor."""
    global _strategy_predictor
    if _strategy_predictor is not None:
        return _strategy_predictor

    if not USE_STRATEGY_PREDICTOR:
        return None

    try:
        model_path = Path(STRATEGY_PREDICTOR_MODEL_PATH)
        if not model_path.exists():
            logger.warning(f"Strategy predictor model not found at {model_path}")
            return None

        # Import from the skill
        sys.path.insert(0, str(model_path.parent.parent / "scripts"))
        from inference import TableStrategyPredictor

        _strategy_predictor = TableStrategyPredictor(model_path)
        logger.info(f"Loaded strategy predictor from {model_path}")
        return _strategy_predictor

    except Exception as e:
        logger.warning(f"Failed to load strategy predictor: {e}")
        return None


def _predict_strategy_for_table(
    pdf_doc: Any,
    page_num: int,
    bbox: Tuple[float, float, float, float],
    preset: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Use ML predictor to suggest optimal strategy for a table region.

    Args:
        pdf_doc: PyMuPDF document
        page_num: Page number (0-indexed)
        bbox: Table bounding box (x0, y0, x1, y1)
        preset: Optional preset hint

    Returns:
        Dict with strategy name, params, confidence or None
    """
    predictor = _get_strategy_predictor()
    if predictor is None:
        return None

    try:
        from PIL import Image
        import io

        # Extract table region image
        page = pdf_doc[page_num]
        clip = type("R", (), {"x0": bbox[0], "y0": bbox[1], "x1": bbox[2], "y1": bbox[3]})()
        mat = type("M", (), {"a": 2.0})()  # 2x zoom for better quality
        pix = page.get_pixmap(matrix=mat, clip=clip)
        img_data = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_data)).convert("RGB")

        # Get prediction
        pred = predictor.predict(img, preset=preset)

        if pred.confidence < STRATEGY_PREDICTOR_CONFIDENCE_THRESHOLD:
            logger.debug(
                f"Predictor confidence {pred.confidence:.2f} below threshold, skipping"
            )
            return None

        # Map to CAMELOT_STRATEGIES name
        strategy_name = pred.strategy
        if strategy_name == "lattice_sensitive":
            strategy_name = "lattice_sensitive"
        elif strategy_name == "stream":
            strategy_name = "stream_default"
        else:
            strategy_name = "lattice_default"

        logger.info(
            f"Predictor suggests {strategy_name} (conf={pred.confidence:.2f}, "
            f"line_scale={pred.line_scale}, edge_tol={pred.edge_tol})"
        )

        return {
            "name": strategy_name,
            "flavor": pred.flavor,
            "line_scale": pred.line_scale,
            "edge_tol": pred.edge_tol,
            "confidence": pred.confidence,
            "predicted": True,
        }

    except Exception as e:
        logger.debug(f"Strategy prediction failed: {e}")
        return None
