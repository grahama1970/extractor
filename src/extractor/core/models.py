"""
Module: models.py
Description: Data models and schemas for models

External Dependencies:
- surya: [Documentation URL]

Sample Input:
>>> # Add specific examples based on module functionality

Expected Output:
>>> # Add expected output examples

Example Usage:
>>> # Add usage examples
"""

import os
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1" # Transformers uses .isin for an op, which is not supported on MPS

try:
    import cv2
except ImportError:
    print("⚠️  OpenCV (cv2) not installed. Surya models require OpenCV.")
    print("   To fix this, run from the extractor directory:")
    print("   1. cd /home/graham/workspace/experiments/extractor")
    print("   2. source .venv/bin/activate (or create one with: uv venv --python=3.10.11)")
    print("   3. uv add opencv-python")
    print("   4. uv pip install -e .")
    raise ImportError("OpenCV (cv2) is required for Surya models. See instructions above.")

from surya.detection import DetectionPredictor
from surya.layout import LayoutPredictor
from surya.ocr_error import OCRErrorPredictor
from surya.recognition import RecognitionPredictor
from surya.table_rec import TableRecPredictor


def create_model_dict(device=None, dtype=None) -> dict:
    return {
        "layout_model": LayoutPredictor(device=device, dtype=dtype),
        "texify_model": RecognitionPredictor(device=device, dtype=dtype),  # Use RecognitionPredictor for texify
        "recognition_model": RecognitionPredictor(device=device, dtype=dtype),
        "table_rec_model": TableRecPredictor(device=device, dtype=dtype),
        "detection_model": DetectionPredictor(device=device, dtype=dtype),
        "ocr_error_model": OCRErrorPredictor(device=device, dtype=dtype),
        "inline_detection_model": None  # Optional, can be None
    }