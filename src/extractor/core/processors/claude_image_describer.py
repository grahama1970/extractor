"""
Background Image Description using Claude Code Instances
Module: claude_image_describer.py
Description: Implementation of claude image describer functionality

Provides multimodal image description using Claude's vision capabilities.
Generates detailed descriptions of figures, charts, diagrams, and other visual elements.
Based on BackgroundTableAnalyzer patterns for robust Claude instance management.
"""

import asyncio
import json
import subprocess
import tempfile
import sqlite3
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from loguru import logger
import time
import os
import base64
from PIL import Image
import io

class TaskStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class ImageType(Enum):
    FIGURE = "figure"
    CHART = "chart"
    DIAGRAM = "diagram"
    PHOTO = "photo"
    SCREENSHOT = "screenshot"
    TABLE_IMAGE = "table_image"
    EQUATION_IMAGE = "equation_image"
    UNKNOWN = "unknown"

@dataclass
class ImageData:
    """Data for an image to be described."""
    image_path: Path
    image_type: ImageType
    page_number: int
    context: Optional[str] = None  # Surrounding text
    caption: Optional[str] = None  # Existing caption if any
    alt_text: Optional[str] = None  # Existing alt text if any
    bbox: Optional[List[float]] = None  # Bounding box coordinates

@dataclass
class DescriptionConfig:
    """Configuration for image description."""
    images: List[ImageData]
    detail_level: str = "comprehensive"  # brief, standard, comprehensive
    include_data_extraction: bool = True  # Extract data from charts/tables
    include_accessibility: bool = True  # Generate accessibility descriptions
    language: str = "en"
    timeout: int = 180
    confidence_threshold: float = 0.9
    model: str = "claude-3-5-sonnet-20241022"
    max_retries: int = 3

@dataclass
class ImageDescription:
    """Description result for an image."""
    image_id: str
    description: str
    detail_level: str
    image_type: ImageType
    confidence: float
    extracted_data: Optional[Dict[str, Any]] = None  # Data from charts/tables
    accessibility_text: Optional[str] = None  # Alt text for accessibility
    keywords: List[str] = field(default_factory=list)
    detected_text: Optional[str] = None  # OCR text in image
    visual_elements: Optional[Dict[str, Any]] = None  # Colors, shapes, etc.

@dataclass
class DescriptionResult:
    """Result of image description task."""
    task_id: str
    descriptions: List[ImageDescription]
    processing_time: float
    status: TaskStatus = TaskStatus.COMPLETED
    error: Optional[str] = None

class BackgroundImageDescriber:
    """
    Background Claude Code instance manager for image description.
    Uses patterns from BackgroundTableAnalyzer for robust execution.
    """
    
    def __init__(self, workspace_dir: Optional[Path] = None, db_path: Optional[Path] = None):
        self.workspace_dir = workspace_dir or Path(tempfile.mkdtemp(prefix="image_describer_"))
        self.db_path = db_path or self.workspace_dir / "description_tasks.db"
        self.executor = None
        self._init_database()
        
    def _init_database(self):
        """Initialize SQLite database for task persistence."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS description_tasks (
                    id TEXT PRIMARY KEY,
                    config TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
    
    async def describe_images(self, config: DescriptionConfig) -> str:
        """
        Submit image description task for background processing.
        Returns task ID immediately for polling.
        """
        task_id = str(uuid.uuid4())
        
        # Convert config to JSON-serializable format
        config_dict = {
            'images': [
                {
                    'image_path': str(img.image_path),
                    'image_type': img.image_type.value,
                    'page_number': img.page_number,
                    'context': img.context,
                    'caption': img.caption,
                    'alt_text': img.alt_text,
                    'bbox': img.bbox
                }
                for img in config.images
            ],
            'detail_level': config.detail_level,
            'include_data_extraction': config.include_data_extraction,
            'include_accessibility': config.include_accessibility,
            'language': config.language,
            'timeout': config.timeout,
            'confidence_threshold': config.confidence_threshold,
            'model': config.model,
            'max_retries': config.max_retries
        }
        
        # Store task in database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO description_tasks (id, config, status) VALUES (?, ?, ?)",
                (task_id, json.dumps(config_dict), TaskStatus.PENDING.value)
            )
            conn.commit()
        
        # Schedule background execution
        if self.executor is None:
            self.executor = asyncio.create_task(self._process_tasks())
        
        return task_id
    
    async def get_description_result(self, task_id: str) -> Optional[DescriptionResult]:
        """Get description result by task ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT config, status, result FROM description_tasks WHERE id = ?",
                (task_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                return None
            
            config_data, status, result_data = row
            status_enum = TaskStatus(status)
            
            if status_enum == TaskStatus.COMPLETED and result_data:
                result_dict = json.loads(result_data)
                
                # Convert descriptions back to ImageDescription objects
                descriptions = []
                for desc_dict in result_dict.get('descriptions', []):
                    desc = ImageDescription(
                        image_id=desc_dict['image_id'],
                        description=desc_dict['description'],
                        detail_level=desc_dict['detail_level'],
                        image_type=ImageType(desc_dict['image_type']),
                        confidence=desc_dict['confidence'],
                        extracted_data=desc_dict.get('extracted_data'),
                        accessibility_text=desc_dict.get('accessibility_text'),
                        keywords=desc_dict.get('keywords', []),
                        detected_text=desc_dict.get('detected_text'),
                        visual_elements=desc_dict.get('visual_elements')
                    )
                    descriptions.append(desc)
                
                return DescriptionResult(
                    task_id=task_id,
                    status=status_enum,
                    descriptions=descriptions,
                    processing_time=result_dict.get('processing_time', 0.0)
                )
            elif status_enum == TaskStatus.FAILED and result_data:
                error_dict = json.loads(result_data)
                return DescriptionResult(
                    task_id=task_id,
                    status=status_enum,
                    descriptions=[],
                    processing_time=0.0,
                    error=error_dict.get("error", "Unknown error")
                )
            else:
                return DescriptionResult(
                    task_id=task_id,
                    status=status_enum,
                    descriptions=[],
                    processing_time=0.0
                )
    
    async def _process_tasks(self):
        """Background task processor."""
        while True:
            try:
                # Get pending tasks
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.execute(
                        "SELECT id, config FROM description_tasks WHERE status = ? ORDER BY created_at",
                        (TaskStatus.PENDING.value,)
                    )
                    tasks = cursor.fetchall()
                
                for task_id, config_json in tasks:
                    try:
                        # Mark as processing
                        self._update_task_status(task_id, TaskStatus.PROCESSING)
                        
                        # Parse config
                        config_dict = json.loads(config_json)
                        
                        # Execute description
                        start_time = time.time()
                        result = await self._execute_claude_description(config_dict)
                        result['processing_time'] = time.time() - start_time
                        
                        # Store result
                        with sqlite3.connect(self.db_path) as conn:
                            conn.execute(
                                "UPDATE description_tasks SET status = ?, result = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                                (TaskStatus.COMPLETED.value, json.dumps(result), task_id)
                            )
                            conn.commit()
                            
                        logger.info(f"Completed description task {task_id}")
                        
                    except Exception as e:
                        logger.error(f"Failed to process task {task_id}: {e}")
                        error_result = {"error": str(e)}
                        with sqlite3.connect(self.db_path) as conn:
                            conn.execute(
                                "UPDATE description_tasks SET status = ?, result = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                                (TaskStatus.FAILED.value, json.dumps(error_result), task_id)
                            )
                            conn.commit()
                
                # Sleep before next check
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"Task processor error: {e}")
                await asyncio.sleep(5)
    
    def _update_task_status(self, task_id: str, status: TaskStatus):
        """Update task status in database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE description_tasks SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status.value, task_id)
            )
            conn.commit()
    
    async def _execute_claude_description(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute Claude description using background instance.
        Returns structured description results.
        """
        
        descriptions = []
        
        # Process each image
        for img_data in config['images']:
            try:
                # Create description prompt
                prompt = self._create_description_prompt(img_data, config)
                
                # Write prompt to temporary file
                prompt_file = self.workspace_dir / f"description_prompt_{uuid.uuid4().hex[:8]}.md"
                prompt_file.write_text(prompt)
                
                # Copy image to workspace
                img_path = Path(img_data['image_path'])
                if img_path.exists():
                    dest_path = self.workspace_dir / img_path.name
                    subprocess.run(['cp', str(img_path), str(dest_path)], check=True)
                    
                    # Execute Claude with image
                    cmd_str = f'''cd {self.workspace_dir} && timeout {config['timeout']}s claude \
                        --print \
                        --output-format json \
                        --model {config['model']} \
                        --image {dest_path.name} \
                        < {prompt_file.name}'''
                    
                    logger.debug(f"Executing: {cmd_str}")
                    
                    # Use subprocess with streaming output
                    process = subprocess.Popen(
                        cmd_str,
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        cwd=self.workspace_dir
                    )
                    
                    # Get the JSON response
                    stdout, stderr = process.communicate()
                    
                    if process.returncode != 0:
                        raise Exception(f"Claude execution failed: {stderr}")
                        
                    # Parse the JSON response
                    try:
                        response_data = json.loads(stdout)
                        full_response = response_data.get("result", response_data.get("content", ""))
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse JSON response, using raw output")
                        full_response = stdout
                    
                    # Parse the structured response
                    description = self._parse_description_response(full_response, img_data)
                    descriptions.append(description)
                    
                    # Cleanup
                    if prompt_file.exists():
                        prompt_file.unlink()
                    if dest_path.exists():
                        dest_path.unlink()
                        
            except Exception as e:
                logger.error(f"Failed to describe image {img_data['image_path']}: {e}")
                # Add error description
                descriptions.append({
                    'image_id': str(uuid.uuid4()),
                    'description': f"Failed to describe image: {e}",
                    'detail_level': config['detail_level'],
                    'image_type': img_data['image_type'],
                    'confidence': 0.0
                })
        
        return {'descriptions': descriptions}
    
    def _create_description_prompt(self, img_data: Dict[str, Any], config: Dict[str, Any]) -> str:
        """Create description prompt for an image."""
        
        detail_instructions = {
            'brief': "Provide a brief 1-2 sentence description of the image.",
            'standard': "Provide a clear description of the image including main elements and their relationships.",
            'comprehensive': "Provide a detailed, comprehensive description including all visible elements, data, text, colors, and spatial relationships."
        }
        
        prompt = f"""# Image Description Task

Analyze the provided image and generate a description based on the requirements below.

## Image Context
- Image Type: {img_data['image_type']}
- Page Number: {img_data['page_number']}
"""
        
        if img_data.get('context'):
            prompt += f"- Surrounding Text: {img_data['context']}\n"
        
        if img_data.get('caption'):
            prompt += f"- Original Caption: {img_data['caption']}\n"
            
        prompt += f"""
## Description Requirements

{detail_instructions.get(config['detail_level'], detail_instructions['standard'])}

### Additional Requirements:
"""
        
        if config['include_data_extraction'] and img_data['image_type'] in ['chart', 'table_image']:
            prompt += """
- **Data Extraction**: Extract all numeric data, labels, and values from charts/graphs
- **Data Relationships**: Describe trends, patterns, and relationships in the data
"""
        
        if config['include_accessibility']:
            prompt += """
- **Accessibility**: Generate alternative text suitable for screen readers
- **Visual Elements**: Describe colors, shapes, and visual hierarchy
"""
        
        prompt += """
## Response Format

Provide your analysis in this EXACT JSON format:

```json
{
    "description": "Main description of the image",
    "image_type": "figure/chart/diagram/photo/screenshot/table_image/equation_image/unknown",
    "confidence": 0.95,
    "extracted_data": {
        "labels": ["Label1", "Label2"],
        "values": [10, 20],
        "units": "unit type",
        "relationships": "Description of data relationships"
    },
    "accessibility_text": "Concise description for screen readers",
    "keywords": ["keyword1", "keyword2", "keyword3"],
    "detected_text": "Any text detected in the image",
    "visual_elements": {
        "colors": ["primary colors used"],
        "layout": "Description of visual layout",
        "emphasis": "What draws attention"
    }
}
```

## Analysis Guidelines

- Be accurate and specific in your descriptions
- Include all visible text and numbers
- For charts/graphs, extract exact values when visible
- Describe spatial relationships between elements
- Note any important visual hierarchies or emphasis

Please analyze the image and provide the structured response.
"""
        
        return prompt
    
    def _parse_description_response(self, response: str, img_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Claude's description response."""
        try:
            # First try to parse as direct JSON
            try:
                parsed = json.loads(response.strip())
                
                result = {
                    "image_id": str(uuid.uuid4()),
                    "description": parsed.get("description", ""),
                    "detail_level": "comprehensive",  # From config
                    "image_type": parsed.get("image_type", img_data['image_type']),
                    "confidence": float(parsed.get("confidence", 0.8)),
                    "extracted_data": parsed.get("extracted_data"),
                    "accessibility_text": parsed.get("accessibility_text"),
                    "keywords": parsed.get("keywords", []),
                    "detected_text": parsed.get("detected_text"),
                    "visual_elements": parsed.get("visual_elements")
                }
                
                logger.debug(f"Successfully parsed direct JSON response")
                return result
                
            except json.JSONDecodeError:
                # If not direct JSON, try to extract from markdown
                import re
                json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
                
                if json_match:
                    json_str = json_match.group(1)
                    parsed = json.loads(json_str)
                    
                    result = {
                        "image_id": str(uuid.uuid4()),
                        "description": parsed.get("description", ""),
                        "detail_level": "comprehensive",
                        "image_type": parsed.get("image_type", img_data['image_type']),
                        "confidence": float(parsed.get("confidence", 0.8)),
                        "extracted_data": parsed.get("extracted_data"),
                        "accessibility_text": parsed.get("accessibility_text"),
                        "keywords": parsed.get("keywords", []),
                        "detected_text": parsed.get("detected_text"),
                        "visual_elements": parsed.get("visual_elements")
                    }
                    
                    logger.debug(f"Successfully parsed JSON from markdown block")
                    return result
                else:
                    # Fallback - use raw response as description
                    logger.warning("Could not parse Claude response as JSON, using as plain text")
                    return {
                        "image_id": str(uuid.uuid4()),
                        "description": response[:1000],  # Limit length
                        "detail_level": "comprehensive",
                        "image_type": img_data['image_type'],
                        "confidence": 0.5,
                        "extracted_data": None,
                        "accessibility_text": None,
                        "keywords": [],
                        "detected_text": None,
                        "visual_elements": None
                    }
                
        except Exception as e:
            logger.error(f"Failed to parse Claude description response: {e}")
            return {
                "image_id": str(uuid.uuid4()),
                "description": f"Parse error: {e}",
                "detail_level": "error",
                "image_type": img_data['image_type'],
                "confidence": 0.0
            }

# High-level interface for integration
class ImageDescriptionEngine:
    """
    High-level interface for image description using background Claude analysis.
    """
    
    def __init__(self, workspace_dir: Optional[Path] = None):
        self.describer = BackgroundImageDescriber(workspace_dir)
        self.pending_tasks = {}
    
    async def submit_images(self, 
                           images: List[ImageData],
                           detail_level: str = "comprehensive",
                           include_data_extraction: bool = True,
                           include_accessibility: bool = True) -> str:
        """Submit images for description."""
        
        config = DescriptionConfig(
            images=images,
            detail_level=detail_level,
            include_data_extraction=include_data_extraction,
            include_accessibility=include_accessibility
        )
        
        task_id = await self.describer.describe_images(config)
        self.pending_tasks[task_id] = {
            "submitted_at": time.time(),
            "config": config
        }
        
        return task_id
    
    async def get_descriptions(self, task_id: str, timeout: float = 300.0) -> Optional[DescriptionResult]:
        """Get description results, waiting up to timeout seconds."""
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            result = await self.describer.get_description_result(task_id)
            
            if result and result.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                # Clean up tracking
                self.pending_tasks.pop(task_id, None)
                return result
            
            await asyncio.sleep(2)
        
        logger.warning(f"Description task {task_id} timed out after {timeout}s")
        return None
    
    # Synchronous wrappers for non-async contexts
    def submit_images_sync(self, 
                          images: List[ImageData],
                          detail_level: str = "comprehensive",
                          include_data_extraction: bool = True,
                          include_accessibility: bool = True) -> str:
        """Synchronous wrapper for submit_images."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self.submit_images(images, detail_level, include_data_extraction, include_accessibility)
            )
        finally:
            loop.close()
    
    def get_descriptions_sync(self, task_id: str, timeout: float = 300.0) -> Optional[DescriptionResult]:
        """Synchronous wrapper for get_descriptions."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self.get_descriptions(task_id, timeout)
            )
        finally:
            loop.close()

# Example usage and testing
async def test_image_describer():
    """Test the image describer with sample images."""
    
    engine = ImageDescriptionEngine()
    
    # Sample images (would be actual image paths in real usage)
    images = [
        ImageData(
            image_path=Path("/tmp/test_chart.png"),
            image_type=ImageType.CHART,
            page_number=5,
            context="This chart shows quarterly revenue growth",
            caption="Figure 3: Revenue Growth Q1-Q4"
        ),
        ImageData(
            image_path=Path("/tmp/test_diagram.png"),
            image_type=ImageType.DIAGRAM,
            page_number=10,
            context="System architecture overview"
        )
    ]
    
    # Submit for description
    task_id = await engine.submit_images(
        images=images,
        detail_level="comprehensive",
        include_data_extraction=True,
        include_accessibility=True
    )
    print(f"Submitted description task: {task_id}")
    
    # Get results
    result = await engine.get_descriptions(task_id)
    if result:
        print(f"\nDescribed {len(result.descriptions)} images:")
        for desc in result.descriptions:
            print(f"\nImage Type: {desc.image_type.value}")
            print(f"Description: {desc.description}")
            print(f"Confidence: {desc.confidence:.2f}")
            if desc.extracted_data:
                print(f"Extracted Data: {desc.extracted_data}")
            if desc.accessibility_text:
                print(f"Alt Text: {desc.accessibility_text}")
    else:
        print("Description failed or timed out")

if __name__ == "__main__":
    # Create test images for demo
    import matplotlib.pyplot as plt
    import numpy as np
    
    # Create a test chart
    plt.figure(figsize=(8, 6))
    quarters = ['Q1', 'Q2', 'Q3', 'Q4']
    revenue = [100, 120, 140, 165]
    plt.bar(quarters, revenue)
    plt.title('Quarterly Revenue Growth')
    plt.ylabel('Revenue (Million $)')
    plt.savefig('/tmp/test_chart.png')
    plt.close()
    
    # Create a test diagram
    plt.figure(figsize=(8, 6))
    plt.text(0.5, 0.7, 'Web Server', ha='center', va='center', bbox=dict(boxstyle="round,pad=0.3", facecolor="lightblue"))
    plt.text(0.5, 0.5, '↓', ha='center', va='center', fontsize=20)
    plt.text(0.5, 0.3, 'Application Server', ha='center', va='center', bbox=dict(boxstyle="round,pad=0.3", facecolor="lightgreen"))
    plt.text(0.5, 0.1, 'Database', ha='center', va='center', bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow"))
    plt.axis('off')
    plt.title('System Architecture')
    plt.savefig('/tmp/test_diagram.png')
    plt.close()
    
    # Run test
    asyncio.run(test_image_describer())