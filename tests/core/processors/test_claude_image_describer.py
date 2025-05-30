"""
Test suite for Claude image description functionality.

This test validates the background Claude instance integration for multimodal
image analysis and description generation.
"""

import asyncio
import json
import os
import pytest
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from unittest.mock import patch, MagicMock
import numpy as np

from marker.processors.claude_image_describer import (
    BackgroundImageDescriber,
    DescriptionConfig as ImageDescriptionConfig,
    DescriptionResult as ImageDescriptionResult,
    TaskStatus,
    ImageType
)
from dataclasses import dataclass
from typing import Optional, Any, Dict, List

@dataclass  
class ExtractedData:
    type: str
    values: Optional[List[Dict[str, Any]]] = None
    columns: Optional[List[str]] = None
    rows: Optional[int] = None
    trend: Optional[str] = None
    title: Optional[str] = None
from marker.schema.blocks.figure import Figure
from marker.schema.blocks.picture import Picture
from marker.schema.blocks.table import Table
from marker.schema.groups.page import PageGroup
from marker.schema.document import Document


class TestClaudeImageDescriber:
    """Test suite for Claude image description"""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        yield db_path
        # Cleanup
        try:
            os.unlink(db_path)
        except:
            pass
    
    @pytest.fixture
    def describer(self, temp_db):
        """Create describer instance with temporary database"""
        return BackgroundImageDescriber(db_path=temp_db)
    
    @pytest.fixture
    def sample_chart_image(self):
        """Create a sample chart image"""
        img = Image.new('RGB', (400, 300), color='white')
        draw = ImageDraw.Draw(img)
        
        # Draw axes
        draw.line([(50, 250), (350, 250)], fill='black', width=2)  # X-axis
        draw.line([(50, 50), (50, 250)], fill='black', width=2)   # Y-axis
        
        # Draw bars
        bars = [60, 80, 120, 100, 140]
        bar_width = 50
        for i, height in enumerate(bars):
            x = 70 + i * 60
            draw.rectangle(
                [(x, 250 - height), (x + bar_width, 250)],
                fill='blue',
                outline='black'
            )
        
        # Add title
        draw.text((150, 20), "Sales by Quarter", fill='black')
        
        return img
    
    @pytest.fixture
    def sample_table_image(self):
        """Create a sample table image"""
        img = Image.new('RGB', (400, 200), color='white')
        draw = ImageDraw.Draw(img)
        
        # Draw table grid
        rows, cols = 4, 3
        cell_width, cell_height = 130, 40
        
        for i in range(rows + 1):
            y = 20 + i * cell_height
            draw.line([(10, y), (10 + cols * cell_width, y)], fill='black')
        
        for j in range(cols + 1):
            x = 10 + j * cell_width
            draw.line([(x, 20), (x, 20 + rows * cell_height)], fill='black')
        
        # Add headers
        headers = ["Product", "Q1 Sales", "Q2 Sales"]
        for j, header in enumerate(headers):
            x = 15 + j * cell_width
            draw.text((x, 25), header, fill='black')
        
        # Add data
        data = [
            ["Widget A", "$10,000", "$12,000"],
            ["Widget B", "$8,000", "$9,500"],
            ["Widget C", "$15,000", "$14,000"]
        ]
        for i, row in enumerate(data):
            for j, cell in enumerate(row):
                x = 15 + j * cell_width
                y = 25 + (i + 1) * cell_height
                draw.text((x, y), cell, fill='black')
        
        return img
    
    @pytest.fixture
    def sample_diagram_image(self):
        """Create a sample diagram image"""
        img = Image.new('RGB', (400, 300), color='white')
        draw = ImageDraw.Draw(img)
        
        # Draw flowchart boxes
        boxes = [
            (50, 50, 150, 100, "Start"),
            (225, 50, 325, 100, "Process"),
            (50, 150, 150, 200, "Decision"),
            (225, 150, 325, 200, "End")
        ]
        
        for x1, y1, x2, y2, text in boxes:
            draw.rectangle([(x1, y1), (x2, y2)], fill='lightblue', outline='black')
            text_x = x1 + (x2 - x1) // 2 - 20
            text_y = y1 + (y2 - y1) // 2 - 10
            draw.text((text_x, text_y), text, fill='black')
        
        # Draw arrows
        draw.line([(150, 75), (225, 75)], fill='black', width=2)
        draw.line([(275, 100), (275, 150)], fill='black', width=2)
        draw.line([(100, 100), (100, 150)], fill='black', width=2)
        draw.line([(150, 175), (225, 175)], fill='black', width=2)
        
        return img
    
    @pytest.fixture
    def sample_document_with_images(self):
        """Create a document with image blocks"""
        doc = Document(filepath="test_images.pdf")
        page = PageGroup(page_id=0, bbox=[0, 0, 612, 792])
        
        # Add a figure
        figure = Figure(
            bbox=[50, 100, 350, 300],
            caption="Figure 1: Sales performance chart"
        )
        page.add_child(figure)
        
        # Add a picture
        picture = Picture(
            bbox=[50, 350, 350, 500],
            caption="Company workflow diagram"
        )
        page.add_child(picture)
        
        doc.pages.append(page)
        return doc
    
    def test_describer_initialization(self, describer, temp_db):
        """Test describer properly initializes database"""
        # Check database exists
        assert os.path.exists(temp_db)
        
        # Check tables are created
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = [row[0] for row in cursor.fetchall()]
            assert 'description_tasks' in tables
    
    def test_create_description_config(self, describer, sample_chart_image):
        """Test creation of description configuration"""
        config = describer._create_description_config(
            image=sample_chart_image,
            context="Sales performance for Q1-Q4 2023",
            image_type="chart",
            extract_data=True
        )
        
        assert isinstance(config, ImageDescriptionConfig)
        assert config.image_type == "chart"
        assert config.context == "Sales performance for Q1-Q4 2023"
        assert config.extract_data is True
        assert config.image_dimensions == (400, 300)
        assert config.has_text is False  # Simple test image
    
    @pytest.mark.asyncio
    async def test_describe_image(self, describer, sample_chart_image):
        """Test async image description submission"""
        config = describer._create_description_config(
            image=sample_chart_image,
            context="Quarterly sales data",
            image_type="chart"
        )
        
        task_id = await describer.describe_image(config)
        
        # Verify task was created in database
        with sqlite3.connect(describer.db_path) as conn:
            cursor = conn.execute(
                "SELECT status, config FROM description_tasks WHERE id = ?",
                (task_id,)
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == TaskStatus.PENDING.value
            
            # Verify config was stored correctly
            stored_config = json.loads(row[1])
            assert stored_config['image_type'] == "chart"
            assert stored_config['context'] == "Quarterly sales data"
    
    @pytest.mark.asyncio
    async def test_poll_description_result_chart(self, describer):
        """Test polling returns result for chart description"""
        # Create a completed task for chart description
        task_id = "test-chart-description"
        description_result = {
            "confidence": 0.92,
            "image_type": "chart",
            "description": "Bar chart showing sales data across 5 quarters. The chart displays an upward trend with values ranging from approximately 60 to 140 units.",
            "accessibility_text": "Bar chart with 5 bars representing quarterly sales. Values from left to right: 60, 80, 120, 100, and 140 units.",
            "extracted_data": {
                "type": "bar_chart",
                "values": [
                    {"label": "Q1", "value": 60},
                    {"label": "Q2", "value": 80},
                    {"label": "Q3", "value": 120},
                    {"label": "Q4", "value": 100},
                    {"label": "Q5", "value": 140}
                ],
                "trend": "overall_increasing",
                "title": "Sales by Quarter"
            },
            "tags": ["chart", "bar_chart", "sales_data", "quarterly_data"]
        }
        
        with sqlite3.connect(describer.db_path) as conn:
            conn.execute(
                """INSERT INTO description_tasks 
                   (id, config, status, result, completed_at) 
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    task_id,
                    json.dumps({}),
                    TaskStatus.COMPLETED.value,
                    json.dumps(description_result),
                    datetime.now().isoformat()
                )
            )
        
        result = await describer.poll_description_result(task_id)
        assert isinstance(result, ImageDescriptionResult)
        assert result.confidence == 0.92
        assert result.image_type == ImageType.CHART
        assert "bar chart" in result.description.lower()
        assert result.extracted_data is not None
        assert result.extracted_data.type == "bar_chart"
        assert len(result.extracted_data.values) == 5
        assert "sales_data" in result.tags
    
    @pytest.mark.asyncio
    async def test_poll_description_result_table(self, describer):
        """Test polling returns result for table image description"""
        # Create a completed task for table description
        task_id = "test-table-description"
        description_result = {
            "confidence": 0.88,
            "image_type": "table",
            "description": "A 3x4 table showing product sales data for Q1 and Q2. Contains sales figures for Widget A, B, and C.",
            "accessibility_text": "Table with 3 columns (Product, Q1 Sales, Q2 Sales) and 3 data rows showing sales figures for different widgets.",
            "extracted_data": {
                "type": "table",
                "values": [
                    {"Product": "Widget A", "Q1 Sales": "$10,000", "Q2 Sales": "$12,000"},
                    {"Product": "Widget B", "Q1 Sales": "$8,000", "Q2 Sales": "$9,500"},
                    {"Product": "Widget C", "Q1 Sales": "$15,000", "Q2 Sales": "$14,000"}
                ],
                "columns": ["Product", "Q1 Sales", "Q2 Sales"],
                "rows": 3
            },
            "tags": ["table", "sales_data", "quarterly_comparison", "financial_data"]
        }
        
        with sqlite3.connect(describer.db_path) as conn:
            conn.execute(
                """INSERT INTO description_tasks 
                   (id, config, status, result, completed_at) 
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    task_id,
                    json.dumps({}),
                    TaskStatus.COMPLETED.value,
                    json.dumps(description_result),
                    datetime.now().isoformat()
                )
            )
        
        result = await describer.poll_description_result(task_id)
        assert isinstance(result, ImageDescriptionResult)
        assert result.image_type == ImageType.TABLE
        assert result.extracted_data.type == "table"
        assert len(result.extracted_data.values) == 3
        assert "Product" in result.extracted_data.values[0]
    
    def test_sync_describe_image(self, describer, sample_diagram_image):
        """Test synchronous wrapper for image description"""
        with patch.object(describer, 'describe_image') as mock_describe:
            mock_describe.return_value = asyncio.coroutine(lambda: "task-img-123")()
            
            task_id = describer.sync_describe_image(
                image=sample_diagram_image,
                context="Process flow diagram",
                image_type="diagram"
            )
            
            assert task_id == "task-img-123"
            mock_describe.assert_called_once()
    
    def test_describe_multiple_image_types(self, describer, sample_chart_image, sample_table_image, sample_diagram_image):
        """Test description of different image types"""
        images = [
            (sample_chart_image, "chart", "Sales chart"),
            (sample_table_image, "table", "Product sales table"),
            (sample_diagram_image, "diagram", "Process flow")
        ]
        
        task_ids = []
        for img, img_type, context in images:
            task_id = describer.sync_describe_image(
                image=img,
                context=context,
                image_type=img_type,
                extract_data=(img_type in ["chart", "table"])
            )
            task_ids.append(task_id)
        
        # Verify all tasks were created
        with sqlite3.connect(describer.db_path) as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM description_tasks WHERE status = ?",
                (TaskStatus.PENDING.value,)
            )
            count = cursor.fetchone()[0]
            assert count >= 3
    
    def test_extract_images_from_document(self, describer, sample_document_with_images):
        """Test extraction of images from document blocks"""
        images = describer._extract_images_from_document(sample_document_with_images)
        
        assert len(images) == 2
        assert images[0]['block_type'] == 'Figure'
        assert images[0]['caption'] == "Figure 1: Sales performance chart"
        assert images[1]['block_type'] == 'Picture'
        assert images[1]['caption'] == "Company workflow diagram"
    
    def test_batch_image_description(self, describer):
        """Test batch processing of multiple images"""
        # Create multiple test images
        images = []
        for i in range(3):
            img = Image.new('RGB', (200, 200), color='white')
            draw = ImageDraw.Draw(img)
            draw.text((50, 90), f"Test Image {i+1}", fill='black')
            images.append(img)
        
        # Submit batch
        task_ids = []
        for i, img in enumerate(images):
            task_id = describer.sync_describe_image(
                image=img,
                context=f"Test image {i+1}",
                image_type="unknown"
            )
            task_ids.append(task_id)
        
        assert len(task_ids) == 3
        assert len(set(task_ids)) == 3  # All unique IDs
    
    def test_accessibility_text_generation(self, describer):
        """Test generation of accessibility text for images"""
        # Create a completed result with accessibility focus
        mock_result = ImageDescriptionResult(
            confidence=0.85,
            image_type=ImageType.DIAGRAM,
            description="Complex flowchart showing decision process",
            accessibility_text="Flowchart with 4 boxes connected by arrows. "
                            "Flow starts at 'Start', proceeds to 'Process', "
                            "then branches at 'Decision' before reaching 'End'.",
            extracted_data=None,
            tags=["flowchart", "process_diagram"]
        )
        
        assert mock_result.accessibility_text is not None
        assert "Start" in mock_result.accessibility_text
        assert "Process" in mock_result.accessibility_text
        assert len(mock_result.accessibility_text) > len(mock_result.description) * 0.5


if __name__ == "__main__":
    # Run validation
    print("Testing Claude image describer...")
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    try:
        describer = BackgroundImageDescriber(db_path=db_path)
        
        # Create test image
        img = Image.new('RGB', (200, 150), color='white')
        draw = ImageDraw.Draw(img)
        draw.rectangle([(20, 20), (180, 130)], fill='lightblue', outline='black')
        draw.text((60, 65), "Test Chart", fill='black')
        
        # Test description
        task_id = describer.sync_describe_image(
            image=img,
            context="Test chart for validation",
            image_type="chart"
        )
        print(f"✓ Created description task: {task_id}")
        
        # Check database
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute("SELECT * FROM description_tasks WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            if row:
                print(f"✓ Task stored in database with status: {row[2]}")
                config = json.loads(row[1])
                print(f"✓ Describing {config['image_type']} image")
            else:
                print("✗ Task not found in database")
        
        print("✅ Claude image describer validation passed!")
        
    finally:
        os.unlink(db_path)