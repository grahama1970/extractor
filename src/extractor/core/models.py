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
        self.processor = type("_P", (), {"ocr_tokenizer": _DummyTokenizer(), "tokenizer": _DummyTokenizer()})()
        self.disable_tqdm = True
        # Let downstream guards detect this is not a real model
        self.is_dummy = True

    def __call__(self, images: List[Any], bboxes: List[Any], task_names: List[str], recognition_batch_size: int, sort_lines: bool):
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

    def __call__(self, *, images: List[Any], bboxes: List[Any], recognition_batch_size: int, sort_lines: bool):
        # Return an empty OCR result per page
        return [_DummyRecPage(0) for _ in images]


def create_model_dict() -> Dict[str, Any]:
    """Return a dict of model/artifact handles.

    In offline mode we return an empty mapping; processors that depend on LLMs
    should be disabled via config.use_llm=False in callers.
    """
    # Provide dummies for all predictors used by builders/processors
    artifacts: Dict[str, Any] = {"texify_model": _DummyTexifyModel()}
    # Try real Surya predictors first (support both 'surya' and 'surya_ocr' namespaces)
    try:
        try:
            from surya.detection import DetectionPredictor  # type: ignore
            from surya.ocr_error import OCRErrorPredictor  # type: ignore
            from surya.layout import LayoutPredictor  # type: ignore
            from surya.recognition import RecognitionPredictor  # type: ignore
            from surya.table_rec import TableRecPredictor  # type: ignore
        except Exception:
            from surya_ocr.detection import DetectionPredictor  # type: ignore
            from surya_ocr.ocr_error import OCRErrorPredictor  # type: ignore
            from surya_ocr.layout import LayoutPredictor  # type: ignore
            from surya_ocr.recognition import RecognitionPredictor  # type: ignore
            from surya_ocr.table_rec import TableRecPredictor  # type: ignore

        # Provide full predictor set (inline_detection_model intentionally None; still passed explicitly)
        artifacts.update(
            {
                "detection_model": DetectionPredictor(),
                "inline_detection_model": None,
                "ocr_error_model": OCRErrorPredictor(),
                "layout_model": LayoutPredictor(),
                "recognition_model": RecognitionPredictor(),
                "table_rec_model": TableRecPredictor(),
            }
        )
        return artifacts
    except Exception:
        # Fall back to minimal dummies; pipeline can still proceed in offline mode
        try:
            try:
                from surya.detection import DetectionPredictor  # type: ignore
                from surya.ocr_error import OCRErrorPredictor  # type: ignore
                from surya.layout import LayoutPredictor  # type: ignore
            except Exception:
                from surya_ocr.detection import DetectionPredictor  # type: ignore
                from surya_ocr.ocr_error import OCRErrorPredictor  # type: ignore
                from surya_ocr.layout import LayoutPredictor  # type: ignore
            artifacts.update(
                {
                    "detection_model": DetectionPredictor(),
                    "inline_detection_model": None,
                    "ocr_error_model": OCRErrorPredictor(),
                    "layout_model": LayoutPredictor(),
                }
            )
        except Exception:
            pass
        artifacts.setdefault("recognition_model", _DummyRecognitionModel())
        return artifacts
