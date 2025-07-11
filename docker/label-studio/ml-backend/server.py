"""
Module: server.py

External Dependencies:
- numpy: https://numpy.org/doc/
- torch: https://pytorch.org/docs/
- requests: https://docs.python-requests.org/

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

#!/usr/bin/env python
"""
Label Studio ML Backend for Marker OCR Pre-annotation

This script provides an ML backend for Label Studio that integrates
Marker's OCR models for pre-annotation of OCR tasks. It automatically'
detects text in images and provides transcriptions to accelerate the 
annotation process.

Usage:
    python server.py --port 9090
"""

import os
import logging
import argparse
import json
import numpy as np
import torch
from PIL import Image
import io
import base64
from urllib.parse import urlparse
import requests
from dotenv import load_dotenv
from label_studio_ml.model import LabelStudioMLBase
from label_studio_ml.utils import get_image_size

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Get environment variables with defaults
OCR_BATCH_SIZE = int(os.getenv('OCR_BATCH_SIZE', '8'))
OCR_CONFIDENCE_THRESHOLD = float(os.getenv('OCR_CONFIDENCE_THRESHOLD', '0.5'))
MARKER_MODEL_PATH = os.getenv('MARKER_MODEL_PATH', '/models')


class MarkerOCRModel(LabelStudioMLBase):
    """ML backend for Marker OCR pre-annotation."""
    
    def __init__(self, **kwargs):
        """Initialize the model."""
        super(MarkerOCRModel, self).__init__(**kwargs)
        
        # Initialize variables
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.batch_size = OCR_BATCH_SIZE
        self.confidence_threshold = OCR_CONFIDENCE_THRESHOLD
        self.model_path = MARKER_MODEL_PATH
        self.initialized = False
        self.models = None
        self.model_version = "marker-ocr-1.0"
        
        # Check for expected labels in config
        self.from_name = self.parsed_label_config.get('from_name')
        self.to_name = self.parsed_label_config.get('to_name')
        self.labels = self.parsed_label_config.get('labels')
        self.transcription_from_name = None
        
        # Find transcription field
        for tag_name, tag_info in self.parsed_label_config.items():
            if tag_info['type'] == 'TextArea':
                self.transcription_from_name = tag_name
                break
        
        # Initialize model asynchronously
        self.init_model()
        
    def init_model(self):
        """Initialize the Marker OCR models."""
        if self.initialized:
            return
        
        logger.info(f"Initializing Marker OCR model on {self.device}")
        
        try:
            # Import Marker
            from marker.models import create_model_dict
            
            # Initialize models
            custom_model_paths = {}
            
            # Check if we have a custom recognition model
            recognition_model_path = os.path.join(self.model_path, 'recognition')
            if os.path.exists(recognition_model_path):
                logger.info(f"Using custom recognition model from {recognition_model_path}")
                custom_model_paths["recognition_model"] = recognition_model_path
            
            # Create models dictionary
            self.models = create_model_dict(device=self.device, custom_model_paths=custom_model_paths)
            
            # Get OCR models
            self.recognition_model = self.models["recognition_model"]
            self.detection_model = self.models["detection_model"]
            
            logger.info("Marker OCR model initialized successfully")
            self.initialized = True
            
        except Exception as e:
            logger.error(f"Error initializing Marker OCR model: {e}")
            self.initialized = False
            
    def _get_image(self, task):
        """Get image from task."""
        image_url = task['data'].get(self.to_name)
        if not image_url:
            logger.error(f"No image found in task data with key {self.to_name}")
            return None
            
        try:
            # Check if image is a URL or base64 encoded
            if image_url.startswith('data:'):
                # Get base64 encoded image data
                b64data = image_url.split(',')[1]
                image_data = base64.b64decode(b64data)
                return Image.open(io.BytesIO(image_data))
            else:
                # Download image from URL
                parsed_url = urlparse(image_url)
                if parsed_url.scheme:
                    response = requests.get(image_url)
                    response.raise_for_status()
                    return Image.open(io.BytesIO(response.content))
                else:
                    # Treat as local file path
                    return Image.open(image_url)
        except Exception as e:
            logger.error(f"Error loading image: {e}")
            return None
    
    def predict(self, tasks, **kwargs):
        """Run prediction on tasks."""
        predictions = []
        
        # Check if model is initialized
        if not self.initialized:
            self.init_model()
            if not self.initialized:
                logger.error("Model initialization failed")
                return predictions
        
        # Process each task
        for task in tasks:
            # Get image from task
            image = self._get_image(task)
            if image is None:
                continue
            
            # Get image dimensions
            img_width, img_height = get_image_size(image)
            
            try:
                # Run detection to find text regions
                regions = self.detection_model([image])[0]
                
                # Create bounding boxes for recognition
                boxes = [region.bbox for region in regions]
                
                # Skip if no regions detected
                if not boxes:
                    logger.info(f"No text regions detected in task {task['id']}")
                    continue
                
                # Run recognition on detected regions
                recognition_results = self.recognition_model(
                    images=[image],
                    bboxes=[boxes]
                )[0]
                
                # Format results for Label Studio
                results = []
                
                for i, (region, text_line) in enumerate(zip(regions, recognition_results.text_lines)):
                    x, y, x2, y2 = region.bbox
                    w, h = x2 - x, y2 - y
                    
                    # Normalize coordinates to percentages (required by Label Studio)
                    x_percent = x / img_width * 100
                    y_percent = y / img_height * 100
                    width_percent = w / img_width * 100
                    height_percent = h / img_height * 100
                    
                    # Calculate confidence score (placeholder)
                    confidence = 0.9  # In a real model, this would be from the model
                    
                    # Skip low-confidence predictions
                    if confidence < self.confidence_threshold:
                        continue
                    
                    # Determine label (simplified, could be more sophisticated)
                    label = self.labels[0]  # Default to first label (usually "Text")
                    
                    # Create rectangle result
                    rectangle_id = f"result_{i+1}"
                    results.append({
                        "id": rectangle_id,
                        "type": "rectanglelabels",
                        "value": {
                            "rectanglelabels": [label],
                            "x": x_percent,
                            "y": y_percent,
                            "width": width_percent,
                            "height": height_percent
                        },
                        "to_name": self.to_name,
                        "from_name": self.from_name,
                        "score": confidence
                    })
                    
                    # Add transcription if supported
                    if self.transcription_from_name:
                        results.append({
                            "id": f"transcription_{i+1}",
                            "type": "textarea",
                            "value": {
                                "text": text_line.text
                            },
                            "to_name": self.to_name,
                            "from_name": self.transcription_from_name,
                            "score": confidence,
                            "parentID": rectangle_id
                        })
                
                # Create prediction object
                predictions.append({
                    "model_version": self.model_version,
                    "result": results,
                    "score": sum([r.get('score', 0) for r in results]) / len(results) if results else 0
                })
                
            except Exception as e:
                logger.error(f"Error processing task {task.get('id')}: {e}")
        
        return predictions
    
    def fit(self, annotations, **kwargs):
        """
        This method is called when annotations are created/updated.
        Can be used to re-train the model based on new annotations.
        """
        logger.info(f"Received {len(annotations)} annotations for model training")
        
        # Could implement an automated fine-tuning cycle here
        # For now, just log the event
        return {
            "model_version": self.model_version,
            "annotations_processed": len(annotations)
        }


def main():
    """Start the ML backend server."""
    parser = argparse.ArgumentParser(description='Label Studio ML Backend for Marker OCR')
    parser.add_argument('--port', type=int, default=9090, help='Server port')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Server host')
    parser.add_argument('--debug', action='store_true', help='Run in debug mode')
    
    args = parser.parse_args()
    
    # Start the server
    from label_studio_ml.api import init_app
    init_app(
        model_class=MarkerOCRModel,
        port=args.port,
        host=args.host,
        debug=args.debug
    )


if __name__ == "__main__":
    main()