"""Document type classifier for Stage-00 profile detection.

Vision + text feature hybrid classifier using pre-trained model from
pi-mono/create-classifier skill.  Runs in shadow mode by default —
predictions are logged but don't override heuristic preset matching.

Inputs: PIL images of first N PDF pages + analysis dict with text features
Outputs: (predicted_label, confidence) tuple
Failure: Returns (None, 0.0) if model unavailable or inference fails
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

try:
    import fitz
    _HAVE_FITZ = True
except ImportError:
    _HAVE_FITZ = False

from PIL import Image

# Classifier skill path — configurable via env var
CLASSIFIER_SKILL_DIR = Path(
    os.getenv(
        "CLASSIFIER_SKILL_DIR",
        str(Path.home() / "workspace/experiments/pi-mono/.pi/skills/create-classifier"),
    )
)
if str(CLASSIFIER_SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(CLASSIFIER_SKILL_DIR))

# Global state
_CLASSIFIER_MODEL: Any = None
_CLASSIFIER_LABELS: Dict[int, str] = {}
_CLASSIFIER_LOADED = False

# Defer heavy ML imports (torch, torchvision, timm) until actually needed.
_HAVE_TORCH: Optional[bool] = None


def ensure_torch() -> bool:
    """Lazy-check for torch/torchvision/timm availability."""
    global _HAVE_TORCH
    if _HAVE_TORCH is None:
        try:
            import torch  # noqa: F401
            import timm   # noqa: F401
            _HAVE_TORCH = True
        except ImportError:
            _HAVE_TORCH = False
    return _HAVE_TORCH


def extract_page_images(pdf_path: Path, num_pages: int = 3) -> List[Any]:
    """Extract first N pages as 224x224 PIL images for classification."""
    if not _HAVE_FITZ:
        return []

    try:
        doc = fitz.open(pdf_path)
        images = []
        for i in range(min(num_pages, len(doc))):
            page = doc[i]
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            img = img.resize((224, 224))
            images.append(img)
        return images
    except Exception as e:
        logger.warning(f"Failed to extract images from {pdf_path}: {e}")
        return []


def predict_with_classifier_images(
    images: List[Any],
    analysis: Dict[str, Any],
) -> Tuple[Optional[str], float]:
    """Run document type classifier using pre-extracted images and text features."""
    if not _CLASSIFIER_LOADED or not _CLASSIFIER_MODEL:
        return None, 0.0

    try:
        import torch
        import torch.nn.functional as F
        from torchvision import transforms

        if not images:
            return None, 0.0

        preprocess = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ),
        ])

        batch_tensors = [preprocess(img) for img in images]
        if not batch_tensors:
            return None, 0.0

        import math
        page_count = analysis.get("page_count", 1)
        norm_pages = math.log10(max(1, page_count)) / 3.0

        has_formulas = 1.0 if analysis.get("has_formulas") else 0.0
        has_tables = 1.0 if analysis.get("has_tables") else 0.0

        layout_style = analysis.get("layout", {}).get("style", "single")
        is_double = 1.0 if layout_style == "double" else 0.0

        section_style = analysis.get("section_style", "decimal")
        is_roman = 1.0 if section_style == "roman" else 0.0

        text_feat_tensor = torch.tensor(
            [[norm_pages, has_formulas, has_tables, is_double, is_roman]],
            dtype=torch.float32,
        )

        vis_batch = torch.stack(batch_tensors)
        text_batch = text_feat_tensor.repeat(vis_batch.size(0), 1)

        _CLASSIFIER_MODEL.eval()
        with torch.no_grad():
            logits, confidences = _CLASSIFIER_MODEL(vis_batch, text_batch)

            avg_logits = torch.mean(logits, dim=0)
            avg_confidence = torch.mean(confidences).item()

            probs = F.softmax(avg_logits, dim=0)
            max_prob, idx = torch.max(probs, dim=0)

            label_idx = idx.item()
            predicted_label = _CLASSIFIER_LABELS.get(label_idx)
            final_confidence = (max_prob.item() + avg_confidence) / 2

            return predicted_label, final_confidence

    except Exception as e:
        logger.error(f"Classifier inference failed: {e}")
        return None, 0.0


def load_classifier_lazily() -> Any:
    """Load the document type classifier if enabled and not already loaded."""
    global _CLASSIFIER_MODEL, _CLASSIFIER_LOADED, _CLASSIFIER_LABELS

    if os.getenv("USE_PRESET_CLASSIFIER", "false").lower() != "true":
        return None

    if not ensure_torch():
        logger.warning("Cannot load classifier: PyTorch dependencies missing")
        _CLASSIFIER_LOADED = True
        return None

    if _CLASSIFIER_LOADED:
        return _CLASSIFIER_MODEL

    try:
        from templates.vision_classifier import HybridClassifier

        model_dir = CLASSIFIER_SKILL_DIR / "models" / "v3_hybrid"
        best_model = model_dir / "best_model.pt"

        if not best_model.exists():
            logger.warning(f"Best model not found at {best_model}, skipping classifier load")
            _CLASSIFIER_LOADED = True
            return None

        logger.info(f"Loading hybrid document type classifier from {best_model}")

        import torch
        checkpoint = torch.load(best_model, map_location="cpu")
        idx_to_label = checkpoint.get("idx_to_label", {})
        _CLASSIFIER_LABELS = {int(k): v for k, v in idx_to_label.items()}
        num_classes = len(_CLASSIFIER_LABELS)

        if num_classes == 0:
            logger.warning("Checkpoint missing idx_to_label mapping")
            return None

        model = HybridClassifier(
            backbone="efficientnet_b0",
            num_classes=num_classes,
            text_feature_dim=5,
        )
        model.load_state_dict(checkpoint["model_state_dict"])
        model.eval()

        _CLASSIFIER_MODEL = model
        _CLASSIFIER_LOADED = True
        logger.info(
            f"Hybrid document type classifier loaded successfully "
            f"with {num_classes} classes"
        )
        return _CLASSIFIER_MODEL

    except Exception as e:
        logger.error(f"Failed to load document classifier: {e}")
        import traceback
        logger.error(traceback.format_exc())
        _CLASSIFIER_LOADED = True
        return None
