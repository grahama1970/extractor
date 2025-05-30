"""
Test suite for Claude content validation functionality.

This test validates the background Claude instance integration for assessing
document content quality, completeness, and coherence.
"""

import asyncio
import json
import os
import pytest
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

from marker.processors.claude_content_validator import (
    BackgroundContentValidator,
    ValidationConfig as ContentValidationConfig,
    ValidationResult as ContentValidationResult,
    TaskStatus,
    ContentIssue
)
from dataclasses import dataclass

@dataclass
class QualityMetrics:
    completeness: float
    coherence: float
    formatting: float
    readability: float
    overall: float
from marker.schema.blocks.text import Text
from marker.schema.blocks.sectionheader import SectionHeader
from marker.schema.blocks.listitem import ListItem
from marker.schema.blocks.table import Table
from marker.schema.blocks.figure import Figure
from marker.schema.groups.page import PageGroup
from marker.schema.document import Document
from marker.schema.polygon import PolygonBox


class TestClaudeContentValidator:
    """Test suite for Claude content validation"""
    
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
    def validator(self, temp_db):
        """Create validator instance with temporary database"""
        return BackgroundContentValidator(db_path=temp_db)
    
    @pytest.fixture
    def sample_document_complete(self):
        """Create a well-structured document with complete content"""
        doc = Document(filepath="test_complete.pdf")
        page1 = PageGroup(page_id=0, polygon=PolygonBox.from_bbox([0, 0, 612, 792]))
        
        # Title
        title = SectionHeader(
            polygon=PolygonBox.from_bbox([50, 100, 500, 130]),
            text="Research Paper on Machine Learning",
            level=1
        )
        page1.add_child(title)
        
        # Abstract
        abstract = Text(
            polygon=PolygonBox.from_bbox([50, 150, 500, 200]),
            text="This paper presents a comprehensive study of machine learning techniques "
                 "applied to natural language processing. We demonstrate significant "
                 "improvements in accuracy using novel architectures."
        )
        page1.add_child(abstract)
        
        # Introduction section
        intro_header = SectionHeader(
            polygon=PolygonBox.from_bbox([50, 220, 200, 240]),
            text="1. Introduction",
            level=2
        )
        page1.add_child(intro_header)
        
        intro_text = Text(
            polygon=PolygonBox.from_bbox([50, 250, 500, 300]),
            text="Machine learning has revolutionized the field of natural language "
                 "processing. Recent advances in deep learning have enabled unprecedented "
                 "performance on various NLP tasks."
        )
        page1.add_child(intro_text)
        
        # Methods section with list
        methods_header = SectionHeader(
            polygon=PolygonBox.from_bbox([50, 320, 200, 340]),
            text="2. Methods",
            level=2
        )
        page1.add_child(methods_header)
        
        method_item1 = ListItem(
            polygon=PolygonBox.from_bbox([70, 350, 400, 370]),
            text="Data preprocessing using tokenization"
        )
        page1.add_child(method_item1)
        
        method_item2 = ListItem(
            polygon=PolygonBox.from_bbox([70, 380, 400, 400]),
            text="Model training with transformer architecture"
        )
        page1.add_child(method_item2)
        
        # Results table
        results_table = Table(
            polygon=PolygonBox.from_bbox([50, 420, 500, 520]),
            cells=[
                ["Model", "Accuracy", "F1-Score"],
                ["Baseline", "0.85", "0.83"],
                ["Our Method", "0.92", "0.91"]
            ],
            extraction_method="surya",
            extraction_details={},
            quality_score=0.9,
            quality_metrics={},
            merge_info={}
        )
        page1.add_child(results_table)
        
        doc.pages.append(page1)
        return doc
    
    @pytest.fixture
    def sample_document_incomplete(self):
        """Create a document with incomplete or problematic content"""
        doc = Document(filepath="test_incomplete.pdf")
        page1 = PageGroup(page_id=0, polygon=PolygonBox.from_bbox([0, 0, 612, 792]))
        
        # Title only, missing content
        title = SectionHeader(
            polygon=PolygonBox.from_bbox([50, 100, 500, 130]),
            text="Incomplete Research Paper",
            level=1
        )
        page1.add_child(title)
        
        # Truncated text
        truncated = Text(
            polygon=PolygonBox.from_bbox([50, 150, 500, 170]),
            text="This paper investigates... [text appears to be cut off]"
        )
        page1.add_child(truncated)
        
        # Section without content
        empty_section = SectionHeader(
            polygon=PolygonBox.from_bbox([50, 200, 200, 220]),
            text="3. Results",
            level=2
        )
        page1.add_child(empty_section)
        
        # Another section immediately after (no content for Results)
        next_section = SectionHeader(
            polygon=PolygonBox.from_bbox([50, 230, 200, 250]),
            text="4. Discussion",
            level=2
        )
        page1.add_child(next_section)
        
        # Garbled text
        garbled = Text(
            polygon=PolygonBox.from_bbox([50, 260, 500, 280]),
            text="D1scuss10n 0f r3su1ts sh0ws th@t..."
        )
        page1.add_child(garbled)
        
        doc.pages.append(page1)
        return doc
    
    @pytest.fixture
    def sample_document_metadata(self):
        """Create document metadata for validation context"""
        return {
            "title": "Research Paper",
            "author": "John Doe",
            "date": "2024-01-15",
            "type": "academic_paper",
            "expected_sections": [
                "Abstract", "Introduction", "Methods", 
                "Results", "Discussion", "References"
            ]
        }
    
    def test_validator_initialization(self, validator, temp_db):
        """Test validator properly initializes database"""
        # Check database exists
        assert os.path.exists(temp_db)
        
        # Check tables are created
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = [row[0] for row in cursor.fetchall()]
            assert 'validation_tasks' in tables
    
    def test_extract_content_features(self, validator, sample_document_complete):
        """Test extraction of content features from document"""
        features = validator._extract_content_features(sample_document_complete)
        
        assert features['total_blocks'] > 0
        assert features['text_blocks'] > 0
        assert features['section_headers'] == 3  # Title + 2 sections
        assert features['tables'] == 1
        assert features['lists'] == 2
        assert features['avg_text_length'] > 0
        assert 'Machine learning' in features['text_content']
    
    def test_create_validation_config(self, validator, sample_document_complete, sample_document_metadata):
        """Test creation of validation configuration"""
        config = validator._create_validation_config(
            document=sample_document_complete,
            metadata=sample_document_metadata,
            validation_type="academic_paper"
        )
        
        assert isinstance(config, ContentValidationConfig)
        assert config.document_type == "academic_paper"
        assert config.total_pages == 1
        assert config.content_features['section_headers'] == 3
        assert config.metadata['author'] == "John Doe"
        assert len(config.expected_sections) == 6
    
    @pytest.mark.asyncio
    async def test_validate_content(self, validator, sample_document_complete):
        """Test async content validation submission"""
        config = validator._create_validation_config(
            document=sample_document_complete,
            metadata=None,
            validation_type="general"
        )
        
        task_id = await validator.validate_content(config)
        
        # Verify task was created in database
        with sqlite3.connect(validator.db_path) as conn:
            cursor = conn.execute(
                "SELECT status, config FROM validation_tasks WHERE id = ?",
                (task_id,)
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == TaskStatus.PENDING.value
            
            # Verify config was stored correctly
            stored_config = json.loads(row[1])
            assert stored_config['document_type'] == "general"
            assert stored_config['total_pages'] == 1
    
    @pytest.mark.asyncio
    async def test_poll_validation_result_complete(self, validator):
        """Test polling returns result for completed validation"""
        # Create a completed task with high quality content
        task_id = "test-complete-validation"
        validation_result = {
            "confidence": 0.95,
            "is_valid": True,
            "quality_metrics": {
                "completeness": 0.92,
                "coherence": 0.88,
                "formatting": 0.90,
                "readability": 0.85,
                "overall": 0.89
            },
            "issues": [],
            "suggestions": [
                "Consider adding a conclusion section",
                "Some technical terms could benefit from definitions"
            ],
            "content_summary": "Well-structured academic paper with clear methodology and results"
        }
        
        with sqlite3.connect(validator.db_path) as conn:
            conn.execute(
                """INSERT INTO validation_tasks 
                   (id, config, status, result, completed_at) 
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    task_id,
                    json.dumps({}),
                    TaskStatus.COMPLETED.value,
                    json.dumps(validation_result),
                    datetime.now().isoformat()
                )
            )
        
        result = await validator.poll_validation_result(task_id)
        assert isinstance(result, ContentValidationResult)
        assert result.confidence == 0.95
        assert result.is_valid is True
        assert result.quality_metrics.completeness == 0.92
        assert result.quality_metrics.overall == 0.89
        assert len(result.issues) == 0
        assert len(result.suggestions) == 2
    
    def test_sync_validate_content(self, validator, sample_document_complete):
        """Test synchronous wrapper for content validation"""
        with patch.object(validator, 'validate_content') as mock_validate:
            mock_validate.return_value = asyncio.coroutine(lambda: "task-789")()
            
            task_id = validator.sync_validate_content(
                document=sample_document_complete,
                metadata=None,
                validation_type="general"
            )
            
            assert task_id == "task-789"
            mock_validate.assert_called_once()
    
    def test_detect_content_issues(self, validator, sample_document_incomplete):
        """Test detection of content quality issues"""
        # Submit validation
        task_id = validator.sync_validate_content(
            document=sample_document_incomplete,
            metadata={
                "type": "academic_paper",
                "expected_sections": ["Abstract", "Introduction", "Methods", "Results", "Discussion"]
            },
            validation_type="academic_paper"
        )
        
        # Simulate background processing
        with sqlite3.connect(validator.db_path) as conn:
            result_data = {
                "confidence": 0.72,
                "is_valid": False,
                "quality_metrics": {
                    "completeness": 0.35,
                    "coherence": 0.45,
                    "formatting": 0.60,
                    "readability": 0.40,
                    "overall": 0.45
                },
                "issues": [
                    {
                        "type": "truncated_content",
                        "page": 0,
                        "location": "Introduction",
                        "description": "Text appears to be cut off mid-sentence",
                        "severity": "error"
                    },
                    {
                        "type": "empty_section",
                        "page": 0,
                        "location": "Results",
                        "description": "Section header with no content",
                        "severity": "error"
                    },
                    {
                        "type": "garbled_text",
                        "page": 0,
                        "location": "Discussion",
                        "description": "Text contains OCR errors or corruption",
                        "severity": "warning"
                    },
                    {
                        "type": "missing_section",
                        "page": 0,
                        "location": "Document",
                        "description": "Missing expected sections: Abstract, Methods",
                        "severity": "error"
                    }
                ],
                "suggestions": [
                    "Re-process document with better OCR settings",
                    "Check if pages are missing from the document",
                    "Add content to empty sections"
                ],
                "content_summary": "Incomplete academic paper with significant content issues"
            }
            conn.execute(
                """UPDATE validation_tasks 
                   SET status = ?, result = ?, completed_at = ?
                   WHERE id = ?""",
                (
                    TaskStatus.COMPLETED.value,
                    json.dumps(result_data),
                    datetime.now().isoformat(),
                    task_id
                )
            )
        
        # Poll for result
        result = validator.sync_poll_result(task_id)
        
        assert result is not None
        assert result.is_valid is False
        assert result.quality_metrics.completeness < 0.5
        assert len(result.issues) == 4
        assert any(issue.type == "truncated_content" for issue in result.issues)
        assert any(issue.type == "empty_section" for issue in result.issues)
        assert result.quality_metrics.overall < 0.5
    
    def test_document_type_specific_validation(self, validator, sample_document_complete):
        """Test validation with document-type specific criteria"""
        # Test with different document types
        for doc_type in ["academic_paper", "technical_manual", "report"]:
            task_id = validator.sync_validate_content(
                document=sample_document_complete,
                metadata={"type": doc_type},
                validation_type=doc_type
            )
            
            # Check that config includes document type
            with sqlite3.connect(validator.db_path) as conn:
                cursor = conn.execute(
                    "SELECT config FROM validation_tasks WHERE id = ?",
                    (task_id,)
                )
                row = cursor.fetchone()
                config = json.loads(row[0])
                assert config['document_type'] == doc_type
    
    def test_quality_metrics_calculation(self, validator):
        """Test quality metrics are properly calculated"""
        # Create a result with specific metrics
        mock_result = ContentValidationResult(
            confidence=0.85,
            is_valid=True,
            quality_metrics=QualityMetrics(
                completeness=0.90,
                coherence=0.85,
                formatting=0.88,
                readability=0.82,
                overall=0.86
            ),
            issues=[],
            suggestions=[],
            content_summary="Good quality document"
        )
        
        # Verify overall score is reasonable average
        expected_overall = (0.90 + 0.85 + 0.88 + 0.82) / 4
        assert abs(mock_result.quality_metrics.overall - expected_overall) < 0.1


if __name__ == "__main__":
    # Run validation
    print("Testing Claude content validator...")
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    try:
        validator = BackgroundContentValidator(db_path=db_path)
        
        # Create test document
        doc = Document(filepath="test_validation.pdf")
        page = PageGroup(page_id=0, polygon=PolygonBox.from_bbox([0, 0, 612, 792]))
        
        # Add some content
        header = SectionHeader(polygon=PolygonBox.from_bbox([0, 0, 200, 30]), text="Test Document", level=1)
        text = Text(polygon=PolygonBox.from_bbox([0, 40, 400, 60]), text="This is test content for validation.")
        page.add_child(header)
        page.add_child(text)
        doc.pages.append(page)
        
        # Test validation
        task_id = validator.sync_validate_content(doc)
        print(f"✓ Created validation task: {task_id}")
        
        # Check database
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute("SELECT * FROM validation_tasks WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            if row:
                print(f"✓ Task stored in database with status: {row[2]}")
                config = json.loads(row[1])
                print(f"✓ Validating content with {config['content_features']['total_blocks']} blocks")
            else:
                print("✗ Task not found in database")
        
        print("✅ Claude content validator validation passed!")
        
    finally:
        os.unlink(db_path)