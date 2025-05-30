#!/usr/bin/env python3
"""
Label Studio Python SDK utilities for OCR annotation and fine-tuning.

This module provides a high-level interface to the Label Studio API
for creating OCR annotation projects, importing data, exporting annotations,
and integrating with Marker's OCR fine-tuning pipeline.

Usage:
    from marker.finetuning.utils.label_studio import LabelStudioClient
    client = LabelStudioClient(url="http://localhost:8080", api_key="your_api_key")
    project_id = client.create_ocr_project("OCR Fine-Tuning Project")
    client.import_images(project_id, "path/to/images")
"""

import os
import json
import time
import logging
import base64
import requests
from urllib.parse import urljoin
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any
import shutil
from PIL import Image
import io
import random

from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class LabelStudioClient:
    """Client for interacting with the Label Studio API for OCR tasks."""

    def __init__(
        self, 
        url: Optional[str] = None, 
        api_key: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: int = 1
    ):
        """
        Initialize the Label Studio client.
        
        Args:
            url: Label Studio URL (default: from LABEL_STUDIO_URL env var)
            api_key: API key (default: from LABEL_STUDIO_API_KEY env var)
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries for API calls
            retry_delay: Delay between retries in seconds
        """
        self.url = url or os.getenv("LABEL_STUDIO_URL", "http://localhost:8080")
        self.api_key = api_key or os.getenv("LABEL_STUDIO_API_KEY")
        
        if not self.api_key:
            logger.warning("No API key provided. Authentication will likely fail.")
        
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # Ensure URL ends with a slash
        if not self.url.endswith('/'):
            self.url += '/'
            
        # Initialize session with authentication
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json"
        })
        
        logger.info(f"Initialized Label Studio client for {self.url}")
    
    def _request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make a request to the Label Studio API with retry logic.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (without base URL)
            data: JSON data for the request
            files: Files to upload
            params: Query parameters
            
        Returns:
            Dict containing the JSON response
            
        Raises:
            Exception if all retries fail
        """
        url = urljoin(self.url, endpoint.lstrip('/'))
        
        for attempt in range(self.max_retries):
            try:
                if files:
                    # Don't use JSON content type for file uploads
                    headers = {"Authorization": f"Token {self.api_key}"}
                    response = requests.request(
                        method=method,
                        url=url,
                        headers=headers,
                        data=data,
                        files=files,
                        params=params,
                        timeout=self.timeout
                    )
                else:
                    response = self.session.request(
                        method=method,
                        url=url,
                        json=data,
                        params=params,
                        timeout=self.timeout
                    )
                
                response.raise_for_status()
                
                if response.content:
                    return response.json()
                return {}
                
            except requests.exceptions.RequestException as e:
                if attempt < self.max_retries - 1:
                    logger.warning(f"Request to {url} failed: {e}. Retrying in {self.retry_delay}s...")
                    time.sleep(self.retry_delay)
                else:
                    logger.error(f"Request to {url} failed after {self.max_retries} attempts: {e}")
                    if hasattr(e, 'response') and e.response is not None:
                        logger.error(f"Response content: {e.response.text}")
                    raise
    
    def test_connection(self) -> bool:
        """
        Test the connection to the Label Studio API.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            response = self._request("GET", "/api/projects")
            logger.info("Successfully connected to Label Studio API")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Label Studio API: {e}")
            return False
    
    def get_projects(self) -> List[Dict[str, Any]]:
        """
        Get all projects from the Label Studio instance.
        
        Returns:
            List of project dictionaries
        """
        return self._request("GET", "/api/projects")
    
    def get_project(self, project_id: int) -> Dict[str, Any]:
        """
        Get a project by ID.
        
        Args:
            project_id: Project ID
            
        Returns:
            Project dictionary
        """
        return self._request("GET", f"/api/projects/{project_id}")
    
    def create_ocr_project(
        self, 
        name: str, 
        description: str = "OCR annotation project for fine-tuning",
        label_config: Optional[str] = None
    ) -> int:
        """
        Create a new OCR annotation project.
        
        Args:
            name: Project name
            description: Project description
            label_config: Custom label config XML (optional)
            
        Returns:
            Project ID if successful
            
        Raises:
            Exception if project creation fails
        """
        # Default OCR label config if not provided
        if not label_config:
            label_config = """
            <View>
              <Image name="image" value="$image"/>
              <RectangleLabels name="label" toName="image">
                <Label value="Text" background="green"/>
                <Label value="Handwriting" background="blue"/>
                <Label value="Signature" background="red"/>
              </RectangleLabels>
              <TextArea name="transcription" toName="image" editable="true" perRegion="true" 
                        displayMode="region-list" required="true"/>
            </View>
            """
        
        data = {
            "title": name,
            "description": description,
            "label_config": label_config.strip()
        }
        
        try:
            response = self._request("POST", "/api/projects", data=data)
            project_id = response.get("id")
            
            if project_id:
                logger.info(f"Created OCR project with ID: {project_id}")
                return project_id
            else:
                logger.error(f"Failed to create project: {response}")
                raise Exception("Project creation failed")
                
        except Exception as e:
            logger.error(f"Failed to create project: {e}")
            raise
    
    def connect_ml_backend(
        self, 
        project_id: int, 
        url: str = "http://localhost:9090",
        title: str = "Marker OCR",
        use_for_interactive_preannotations: bool = True
    ) -> bool:
        """
        Connect an ML backend to a project.
        
        Args:
            project_id: Project ID
            url: ML backend URL
            title: ML backend title
            use_for_interactive_preannotations: Whether to use for interactive pre-annotations
            
        Returns:
            True if successful, False otherwise
        """
        data = {
            "project": project_id,
            "url": url,
            "title": title,
            "description": "Marker OCR model for pre-annotation",
            "model_version": "marker-ocr-1.0",
            "use_for_interactive_preannotations": use_for_interactive_preannotations
        }
        
        try:
            response = self._request("POST", "/api/ml", data=data)
            ml_backend_id = response.get("id")
            
            if ml_backend_id:
                logger.info(f"Connected ML backend with ID: {ml_backend_id} to project {project_id}")
                return True
            else:
                logger.error(f"Failed to connect ML backend: {response}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to connect ML backend: {e}")
            return False
    
    def import_images(
        self, 
        project_id: int, 
        image_dir: str,
        extensions: List[str] = ['.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp'],
        batch_size: int = 20
    ) -> Tuple[int, int]:
        """
        Import images from a directory to a project.
        
        Args:
            project_id: Project ID
            image_dir: Directory containing images
            extensions: File extensions to import
            batch_size: Number of images to import per batch
            
        Returns:
            Tuple of (number of images imported, number of failed imports)
        """
        image_dir = Path(image_dir)
        if not image_dir.exists() or not image_dir.is_dir():
            logger.error(f"Image directory {image_dir} does not exist or is not a directory")
            raise ValueError(f"Invalid image directory: {image_dir}")
        
        # Get all image files
        image_files = []
        for ext in extensions:
            image_files.extend(list(image_dir.glob(f"*{ext}")))
            image_files.extend(list(image_dir.glob(f"*{ext.upper()}")))
        
        if not image_files:
            logger.warning(f"No images found in {image_dir} with extensions {extensions}")
            return 0, 0
        
        logger.info(f"Found {len(image_files)} images to import")
        
        # Import images in batches
        imported = 0
        failed = 0
        batches = [image_files[i:i + batch_size] for i in range(0, len(image_files), batch_size)]
        
        for batch_idx, batch in enumerate(batches):
            logger.info(f"Importing batch {batch_idx + 1}/{len(batches)} ({len(batch)} images)")
            
            # Prepare batch data
            tasks = []
            
            for img_path in batch:
                try:
                    # Check if file is readable and valid image
                    image = Image.open(img_path)
                    image.verify()  # Verify image is valid
                    
                    # Create base64 encoded image for direct upload
                    with open(img_path, "rb") as f:
                        img_data = base64.b64encode(f.read()).decode("utf-8")
                    
                    # Determine image format
                    img_format = img_path.suffix.lstrip('.').lower()
                    if img_format in ['jpg', 'jpeg']:
                        img_format = 'jpeg'
                    
                    tasks.append({
                        "data": {
                            "image": f"data:image/{img_format};base64,{img_data}"
                        }
                    })
                    
                except Exception as e:
                    logger.error(f"Error processing image {img_path}: {e}")
                    failed += 1
                    continue
            
            # Skip if all images in batch failed
            if not tasks:
                continue
            
            # Import tasks
            try:
                import_data = json.dumps(tasks)
                
                files = {
                    'file': ('tasks.json', import_data, 'application/json')
                }
                
                response = self._request(
                    method="POST",
                    endpoint=f"/api/projects/{project_id}/import",
                    files=files
                )
                
                # Check response for successful import
                if "task_count" in response and response["task_count"] > 0:
                    imported += response["task_count"]
                    logger.info(f"Successfully imported {response['task_count']} tasks in batch")
                else:
                    logger.warning(f"Import may have failed for batch: {response}")
                    failed += len(tasks)
                
            except Exception as e:
                logger.error(f"Failed to import batch: {e}")
                failed += len(tasks)
                continue
        
        logger.info(f"Import complete: {imported} successful, {failed} failed")
        return imported, failed
    
    def get_tasks(
        self, 
        project_id: int, 
        filters: Optional[Dict[str, Any]] = None, 
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get tasks from a project with optional filtering.
        
        Args:
            project_id: Project ID
            filters: Filter parameters
            limit: Maximum number of tasks to return
            offset: Offset for pagination
            
        Returns:
            List of task dictionaries
        """
        params = {
            "project": project_id,
            "limit": limit,
            "offset": offset
        }
        
        if filters:
            params.update(filters)
        
        return self._request("GET", "/api/tasks", params=params)
    
    def get_task(self, task_id: int) -> Dict[str, Any]:
        """
        Get a task by ID.
        
        Args:
            task_id: Task ID
            
        Returns:
            Task dictionary
        """
        return self._request("GET", f"/api/tasks/{task_id}")
    
    def get_annotations(
        self, 
        project_id: int, 
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get annotations from a project with optional filtering.
        
        Args:
            project_id: Project ID
            filters: Filter parameters
            
        Returns:
            List of annotation dictionaries
        """
        params = {"project": project_id}
        
        if filters:
            params.update(filters)
        
        return self._request("GET", "/api/annotations", params=params)
    
    def export_annotations(
        self, 
        project_id: int, 
        export_type: str = "JSON"
    ) -> List[Dict[str, Any]]:
        """
        Export annotations from a project.
        
        Args:
            project_id: Project ID
            export_type: Export format (JSON, CSV, etc.)
            
        Returns:
            List of exported annotations
        """
        params = {"exportType": export_type}
        
        try:
            return self._request("GET", f"/api/projects/{project_id}/export", params=params)
        except Exception as e:
            logger.error(f"Failed to export annotations: {e}")
            raise
    
    def export_annotations_for_finetuning(
        self, 
        project_id: int, 
        output_dir: str,
        train_split: float = 0.8,
        val_split: float = 0.1,
        test_split: float = 0.1,
        seed: int = 42
    ) -> str:
        """
        Export annotations from a project and convert to format for OCR fine-tuning.
        
        Args:
            project_id: Project ID
            output_dir: Directory to output prepared data
            train_split: Proportion for training set
            val_split: Proportion for validation set
            test_split: Proportion for test set
            seed: Random seed for reproducibility
            
        Returns:
            Path to the output directory
        """
        if train_split + val_split + test_split != 1.0:
            logger.warning("Split proportions don't sum to 1.0. Normalizing...")
            total = train_split + val_split + test_split
            train_split /= total
            val_split /= total
            test_split /= total
        
        # Set random seed
        random.seed(seed)
        
        # Create output directories
        output_dir = Path(output_dir)
        line_crops_dir = output_dir / "line_crops"
        transcriptions_dir = output_dir / "transcriptions"
        splits_dir = output_dir / "splits"
        
        os.makedirs(line_crops_dir, exist_ok=True)
        os.makedirs(transcriptions_dir, exist_ok=True)
        os.makedirs(splits_dir, exist_ok=True)
        
        logger.info(f"Exporting annotations from project {project_id} to {output_dir}")
        
        # Export annotations
        annotations = self.export_annotations(project_id, "JSON")
        
        if not annotations:
            logger.error("No annotations found to export")
            return str(output_dir)
        
        logger.info(f"Processing {len(annotations)} annotated tasks")
        
        # Process annotations
        all_lines = []
        
        for i, item in enumerate(annotations):
            if "annotations" not in item or not item["annotations"]:
                logger.debug(f"Skipping item {i} - no annotations")
                continue
                
            # Get image data
            image_data = item["data"].get("image")
            if not image_data:
                logger.debug(f"Skipping item {i} - no image data")
                continue
            
            # Get image in memory
            try:
                if image_data.startswith('data:image'):
                    # Extract base64 data
                    b64data = image_data.split(',')[1]
                    image = Image.open(io.BytesIO(base64.b64decode(b64data)))
                else:
                    # URL or path case
                    response = requests.get(image_data)
                    response.raise_for_status()
                    image = Image.open(io.BytesIO(response.content))
            except Exception as e:
                logger.error(f"Error processing image in item {i}: {e}")
                continue
            
            # Get image dimensions
            img_width, img_height = image.size
            
            # Process annotations
            annotation = item["annotations"][0]  # Take first annotation set
            results = annotation.get("result", [])
            
            # Group results by region
            regions = {}
            
            for result in results:
                result_type = result.get("type")
                
                if result_type == "rectanglelabels":
                    # This is a bounding box with label
                    region_id = result.get("id")
                    
                    if region_id:
                        value = result.get("value", {})
                        
                        # Get normalized coordinates
                        x = value.get("x", 0) / 100.0 * img_width
                        y = value.get("y", 0) / 100.0 * img_height
                        width = value.get("width", 0) / 100.0 * img_width
                        height = value.get("height", 0) / 100.0 * img_height
                        
                        # Get label if available
                        labels = value.get("rectanglelabels", ["Text"])
                        label = labels[0] if labels else "Text"
                        
                        regions[region_id] = {
                            "bbox": [
                                x, 
                                y, 
                                x + width, 
                                y + height
                            ],
                            "label": label
                        }
                
                elif result_type == "textarea" and "parentID" in result:
                    # This is transcription text associated with a region
                    parent_id = result.get("parentID")
                    
                    if parent_id in regions:
                        text = result.get("value", {}).get("text", "")
                        regions[parent_id]["text"] = text
            
            # Process each region with text
            for j, (region_id, region_data) in enumerate(regions.items()):
                if "text" not in region_data or not region_data["text"].strip():
                    logger.debug(f"Skipping region {region_id} - no text")
                    continue
                
                # Create unique line ID
                task_id = item.get("id", i)
                line_id = f"task_{task_id}_line_{j}"
                
                # Crop and save the image region
                try:
                    bbox = [int(coord) for coord in region_data["bbox"]]
                    line_crop = image.crop(bbox)
                    
                    # Save line crop
                    crop_path = str(line_crops_dir / f"{line_id}.png")
                    line_crop.save(crop_path)
                    
                    # Save transcription
                    trans_path = str(transcriptions_dir / f"{line_id}.txt")
                    with open(trans_path, 'w', encoding='utf-8') as f:
                        f.write(region_data["text"])
                    
                    # Add to all lines
                    all_lines.append({
                        "line_id": line_id,
                        "image_path": crop_path,
                        "text_path": trans_path,
                        "text": region_data["text"],
                        "label": region_data.get("label", "Text")
                    })
                    
                except Exception as e:
                    logger.error(f"Error processing region in item {i}, region {j}: {e}")
                    continue
        
        if not all_lines:
            logger.warning("No valid line regions found in annotations")
            return str(output_dir)
        
        logger.info(f"Extracted {len(all_lines)} annotated text lines")
        
        # Shuffle lines for splitting
        random.shuffle(all_lines)
        total_lines = len(all_lines)
        
        # Create train/val/test splits
        train_end = int(total_lines * train_split)
        val_end = train_end + int(total_lines * val_split)
        
        train_lines = all_lines[:train_end]
        val_lines = all_lines[train_end:val_end]
        test_lines = all_lines[val_end:]
        
        # Save splits
        for split_name, lines in [("train", train_lines), ("val", val_lines), ("test", test_lines)]:
            split_file = str(splits_dir / f"{split_name}.json")
            with open(split_file, 'w') as f:
                json.dump({
                    "lines": lines
                }, f, indent=2)
        
        logger.info(f"Created dataset splits: train={len(train_lines)}, val={len(val_lines)}, test={len(test_lines)}")
        logger.info(f"Fine-tuning dataset prepared at: {output_dir}")
        
        return str(output_dir)
    
    def submit_predictions(
        self, 
        project_id: int, 
        predictions: List[Dict[str, Any]]
    ) -> bool:
        """
        Submit model predictions to Label Studio.
        
        Args:
            project_id: Project ID
            predictions: List of prediction objects
            
        Returns:
            True if successful, False otherwise
        """
        try:
            response = self._request("POST", "/api/predictions", data=predictions)
            return True
        except Exception as e:
            logger.error(f"Failed to submit predictions: {e}")
            return False


def create_ocr_project(
    project_name: str, 
    description: str = "OCR annotation project for Marker fine-tuning"
) -> int:
    """
    Convenience function to create a new OCR project.
    
    Args:
        project_name: Name for the project
        description: Project description
        
    Returns:
        Project ID if successful, None otherwise
    """
    client = LabelStudioClient()
    
    try:
        project_id = client.create_ocr_project(project_name, description)
        return project_id
    except Exception as e:
        logger.error(f"Failed to create OCR project: {e}")
        return None


def import_tasks_from_images(
    project_id: int, 
    image_dir: str
) -> bool:
    """
    Convenience function to import images to a project.
    
    Args:
        project_id: Project ID
        image_dir: Directory containing images
        
    Returns:
        True if successful, False otherwise
    """
    client = LabelStudioClient()
    
    try:
        imported, failed = client.import_images(project_id, image_dir)
        return imported > 0
    except Exception as e:
        logger.error(f"Failed to import images: {e}")
        return False


def export_annotations_for_finetuning(
    project_id: int, 
    output_dir: str
) -> str:
    """
    Convenience function to export annotations for OCR fine-tuning.
    
    Args:
        project_id: Project ID
        output_dir: Directory to save prepared data
        
    Returns:
        Path to output directory if successful, None otherwise
    """
    client = LabelStudioClient()
    
    try:
        return client.export_annotations_for_finetuning(project_id, output_dir)
    except Exception as e:
        logger.error(f"Failed to export annotations for fine-tuning: {e}")
        return None


def preannotate_tasks_with_marker(
    project_id: int, 
    model_path: Optional[str] = None
) -> bool:
    """
    Pre-annotate tasks with Marker OCR model.
    
    This is a placeholder for now - ML backend integration should handle this.
    
    Args:
        project_id: Project ID
        model_path: Path to custom model (optional)
        
    Returns:
        True if successful, False otherwise
    """
    logger.info(f"Pre-annotation requested for project {project_id}")
    logger.info("Note: Pre-annotation should be handled by the ML backend integration")
    logger.info("This function is a placeholder for direct pre-annotation if needed")
    
    # Could implement direct pre-annotation here if ML backend is not available
    return True


if __name__ == "__main__":
    # Simple CLI for testing
    import argparse
    
    parser = argparse.ArgumentParser(description="Label Studio client for OCR annotation")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Test connection command
    test_parser = subparsers.add_parser("test", help="Test connection to Label Studio")
    
    # Create project command
    create_parser = subparsers.add_parser("create", help="Create a new OCR project")
    create_parser.add_argument("name", help="Project name")
    create_parser.add_argument("--description", help="Project description")
    
    # Import images command
    import_parser = subparsers.add_parser("import", help="Import images to a project")
    import_parser.add_argument("project_id", type=int, help="Project ID")
    import_parser.add_argument("image_dir", help="Directory containing images")
    
    # Export annotations command
    export_parser = subparsers.add_parser("export", help="Export annotations for fine-tuning")
    export_parser.add_argument("project_id", type=int, help="Project ID")
    export_parser.add_argument("output_dir", help="Directory to save prepared data")
    
    args = parser.parse_args()
    
    # Execute command
    client = LabelStudioClient()
    
    if args.command == "test":
        if client.test_connection():
            print("Connection successful")
        else:
            print("Connection failed")
            
    elif args.command == "create":
        project_id = client.create_ocr_project(args.name, args.description or "")
        if project_id:
            print(f"Created project with ID: {project_id}")
        else:
            print("Failed to create project")
            
    elif args.command == "import":
        imported, failed = client.import_images(args.project_id, args.image_dir)
        print(f"Imported {imported} images, {failed} failed")
            
    elif args.command == "export":
        output_dir = client.export_annotations_for_finetuning(args.project_id, args.output_dir)
        print(f"Exported annotations to: {output_dir}")