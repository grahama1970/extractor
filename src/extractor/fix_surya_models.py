#!/usr/bin/env python3
"""
Module: fix_surya_models.py
Description: Fix Surya model initialization in extractor to match marker-pdf

This script analyzes and fixes the differences between marker-pdf and extractor
in how they initialize and use Surya models.

External Dependencies:
- surya-ocr: https://github.com/VikParuchuri/surya

Sample Input:
>>> # Run this script to analyze and provide fixes

Expected Output:
>>> Analysis of model initialization differences and recommended fixes

Example Usage:
>>> python fix_surya_models.py
"""

import os
import sys
from pathlib import Path

def analyze_model_differences():
    """Analyze differences in model initialization between marker-pdf and extractor"""
    
    print("="*60)
    print("🔍 SURYA MODEL INITIALIZATION ANALYSIS")
    print("="*60)
    
    # Key findings from analysis
    print("\n📊 KEY FINDINGS:")
    print("-" * 40)
    
    print("\n1. EQUATION PROCESSOR ISSUE:")
    print("   ❌ Extractor's equation processor doesn't pass bboxes to RecognitionPredictor")
    print("   ✅ Marker-pdf passes bboxes: recognition_model(images=..., bboxes=...)")
    print("   💡 This causes: 'You need to pass in a detection predictor' error")
    
    print("\n2. MODEL DICTIONARY DIFFERENCES:")
    print("   Marker-pdf models.py:")
    print("   - layout_model")
    print("   - recognition_model") 
    print("   - table_rec_model")
    print("   - detection_model")
    print("   - ocr_error_model")
    print("\n   Extractor models.py adds:")
    print("   - texify_model (alias for recognition_model)")
    print("   - inline_detection_model (set to None)")
    
    print("\n3. PROCESSOR DIFFERENCES:")
    print("   ❌ Extractor's equation processor extracts images without bboxes")
    print("   ✅ Marker-pdf's equation processor uses page images + bboxes")

def generate_fixes():
    """Generate fixes for the identified issues"""
    
    print("\n" + "="*60)
    print("🔧 RECOMMENDED FIXES")
    print("="*60)
    
    print("\n📝 FIX 1: Update equation processor to match marker-pdf")
    print("-" * 40)
    
    equation_fix = '''# In extractor/core/processors/equation.py, update get_latex_batched:

def get_latex_batched(self, equation_data: List[dict]):
    """Process equations with proper bbox handling"""
    # Extract images and bboxes from equation data
    inference_images = []
    bboxes_list = []
    
    for eq in equation_data:
        inference_images.append(eq["image"])
        # Create a bbox that covers the entire image
        h, w = eq["image"].height, eq["image"].width
        bbox = [[0, 0, w, h]]  # Single bbox covering whole image
        bboxes_list.append(bbox)
    
    self.texify_model.disable_tqdm = self.disable_tqdm
    
    # Now pass bboxes to avoid det_predictor requirement
    model_output = self.texify_model(
        images=inference_images,
        bboxes=bboxes_list,  # ADD THIS!
        task_names=["block_without_boxes"] * len(inference_images),
        recognition_batch_size=self.get_batch_size(),
        sort_lines=False
    )
    
    # Rest of the function remains the same...
'''
    print(equation_fix)
    
    print("\n📝 FIX 2: Alternative - Pass detection model")
    print("-" * 40)
    
    detection_fix = '''# Alternative fix - pass the detection model:

def get_latex_batched(self, equation_data: List[dict]):
    inference_images = [eq["image"] for eq in equation_data]
    
    # Get detection model from artifact_dict
    det_predictor = self.detection_model  # Assuming it's available
    
    model_output = self.texify_model(
        images=inference_images,
        det_predictor=det_predictor,  # Pass detector
        task_names=["block_without_boxes"] * len(inference_images),
        recognition_batch_size=self.get_batch_size(),
        sort_lines=False
    )
'''
    print(detection_fix)
    
    print("\n📝 FIX 3: Update model initialization")
    print("-" * 40)
    
    model_fix = '''# In extractor/core/models.py, ensure all models are properly initialized:

def create_model_dict(device=None, dtype=None) -> dict:
    """Create model dictionary matching marker-pdf structure"""
    models = {
        "layout_model": LayoutPredictor(device=device, dtype=dtype),
        "recognition_model": RecognitionPredictor(device=device, dtype=dtype),
        "table_rec_model": TableRecPredictor(device=device, dtype=dtype),
        "detection_model": DetectionPredictor(device=device, dtype=dtype),
        "ocr_error_model": OCRErrorPredictor(device=device, dtype=dtype),
    }
    
    # Add aliases for compatibility
    models["texify_model"] = models["recognition_model"]  # Same model
    models["inline_detection_model"] = None  # Optional
    
    return models
'''
    print(model_fix)

def test_fix():
    """Test that the fix works"""
    
    print("\n" + "="*60)
    print("🧪 TESTING THE FIX")
    print("="*60)
    
    test_code = '''# Test script to verify the fix works:

from extractor.core.models import create_model_dict
from PIL import Image
import numpy as np

# Create models
models = create_model_dict()

# Create a test image
test_image = Image.fromarray(np.zeros((100, 100, 3), dtype=np.uint8))

# Test with bboxes (should work)
try:
    result = models["recognition_model"](
        images=[test_image],
        bboxes=[[[0, 0, 100, 100]]],  # Provide bbox
        task_names=["block_without_boxes"],
        recognition_batch_size=1,
        sort_lines=False
    )
    print("✅ Recognition with bboxes: SUCCESS")
except Exception as e:
    print(f"❌ Recognition with bboxes failed: {e}")
'''
    print(test_code)

def main():
    """Main analysis and fix generation"""
    
    # Analyze the differences
    analyze_model_differences()
    
    # Generate fixes
    generate_fixes()
    
    # Show how to test
    test_fix()
    
    print("\n" + "="*60)
    print("💡 SUMMARY")
    print("="*60)
    print("\nThe main issue is that extractor's equation processor doesn't pass")
    print("bboxes to the RecognitionPredictor, which then requires a det_predictor.")
    print("\nThe simplest fix is to provide bboxes that cover the entire image")
    print("for each equation, matching how marker-pdf handles it.")
    print("\n✨ Apply FIX 1 to resolve the Surya model initialization error!")

if __name__ == "__main__":
    main()