"""Minimal model registry for offline/CI environments.

Provides create_model_dict() expected by Marker converter paths. In full
deployments this can be replaced with a richer registry that loads OCR/LLM
artifacts. For CI and default extraction stages that do not require LLM, an
empty dict is sufficient.
"""

from __future__ import annotations

from typing import Any, Dict, List


class _DummyTexifyOutput:
    def __init__(self, txt: str = "") -> None:
        class _TL:
            def __init__(self, t: str) -> None:
                self.text = t

        self.text_lines = [_TL(txt)] if txt else []


class _DummyTokenizer:
    def __call__(self, text: str) -> Dict[str, List[int]]:
        # naive tokenization: 1 token per 4 chars
        n = max(1, len(text) // 4)
        return {"input_ids": list(range(n))}


class _DummyTexifyModel:
    def __init__(self) -> None:
        # Provide both attrs used by EquationProcessor
        self.processor = type(
            "_P", (), {"ocr_tokenizer": _DummyTokenizer(), "tokenizer": _DummyTokenizer()}
        )()
        self.disable_tqdm = True
        # Let downstream guards detect this is not a real model
        self.is_dummy = True

    def __call__(
        self,
        images: List[Any],
        bboxes: List[Any],
        task_names: List[str],
        recognition_batch_size: int,
        sort_lines: bool,
    ):
        # Return empty predictions (EquationProcessor will ignore)
        return [_DummyTexifyOutput("") for _ in images]


class _DummyRecLine:
    def __init__(self, txt: str = "") -> None:
        self.text = txt


class _DummyRecPage:
    def __init__(self, n: int = 0) -> None:
        self.text_lines = [_DummyRecLine("") for _ in range(n)]


class _DummyRecognitionModel:
    def __init__(self) -> None:
        self.disable_tqdm = True

    def __call__(
        self, *, images: List[Any], bboxes: List[Any], recognition_batch_size: int, sort_lines: bool
    ):
        # Return an empty OCR result per page
        return [_DummyRecPage(0) for _ in images]


def create_model_dict() -> Dict[str, Any]:
    """Return a dict of model/artifact handles.

    In offline mode we return an empty mapping; processors that depend on LLMs
    should be disabled via config.use_llm=False in callers.
    """
    import os
    import logging

    logger = logging.getLogger(__name__)

    # Provide dummies for all predictors used by builders/processors
    artifacts: Dict[str, Any] = {"texify_model": _DummyTexifyModel()}

    # Load models individually to isolate failures
    # Critical models for text detection: detection_model, layout_model
    model_load_errors: List[str] = []

    # 1. Detection model (critical for text detection)
    try:
        from surya.detection import DetectionPredictor  # type: ignore
        artifacts["detection_model"] = DetectionPredictor()
    except Exception as e:
        model_load_errors.append(f"detection_model: {e}")

    # 2. Layout model (critical for block classification)
    try:
        from surya.layout import LayoutPredictor  # type: ignore
        artifacts["layout_model"] = LayoutPredictor()
    except Exception as e:
        model_load_errors.append(f"layout_model: {e}")

    # 3. Recognition model (for OCR text extraction)
    try:
        from surya.recognition import RecognitionPredictor  # type: ignore
        artifacts["recognition_model"] = RecognitionPredictor()
    except Exception as e:
        model_load_errors.append(f"recognition_model: {e}")
        artifacts["recognition_model"] = _DummyRecognitionModel()

    # 4. OCR error model (optional, for error correction)
    try:
        from surya.ocr_error import OCRErrorPredictor  # type: ignore
        artifacts["ocr_error_model"] = OCRErrorPredictor()
    except Exception as e:
        model_load_errors.append(f"ocr_error_model: {e}")

    # 5. Table recognition model (optional, for table structure)
    try:
        from surya.table_rec import TableRecPredictor  # type: ignore
        artifacts["table_rec_model"] = TableRecPredictor()
    except Exception as e:
        model_load_errors.append(f"table_rec_model: {e}")

    # Always set inline_detection_model to None (not used in current pipeline)
    artifacts["inline_detection_model"] = None

    # Log any model loading failures
    if model_load_errors:
        for err in model_load_errors:
            logger.warning(f"Model load failed: {err}")

        # Check if critical models are missing
        if "layout_model" not in artifacts:
            logger.error(
                "CRITICAL: layout_model failed to load. Text detection will not work. "
                "Check: 1) Surya is installed, 2) GPU memory available, 3) CUDA compatible."
            )
        if "detection_model" not in artifacts:
            logger.error(
                "CRITICAL: detection_model failed to load. Line detection will not work."
            )

    return artifacts
