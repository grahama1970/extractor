"""
Test suite for Claude section verification functionality.

This test validates the background Claude instance integration for verifying
document section hierarchies and detecting structural issues.
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

from marker.processors.claude_section_verifier import (
    BackgroundSectionVerifier,
    VerificationConfig as SectionVerificationConfig,
    VerificationResult as SectionVerificationResult,
    TaskStatus,
    SectionIssue as StructuralIssue
)
from marker.schema.blocks.sectionheader import SectionHeader
from marker.schema.blocks.text import Text
from marker.schema.groups.page import PageGroup
from marker.schema.document import Document
from marker.schema.polygon import PolygonBox


class TestClaudeSectionVerifier:
    """Test suite for Claude section verification"""
    
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
    def verifier(self, temp_db):
        """Create verifier instance with temporary database"""
        return BackgroundSectionVerifier(db_path=temp_db)
    
    @pytest.fixture
    def sample_document_correct(self):
        """Create a document with correct section hierarchy"""
        doc = Document(filepath="test_correct.pdf")
        page1 = PageGroup(page_id=0, polygon=PolygonBox.from_bbox([0, 0, 612, 792]))
        
        # Level 1 header
        h1 = SectionHeader(
            polygon=PolygonBox.from_bbox([50, 100, 300, 120]),
            text="1. Introduction",
            level=1
        )
        page1.add_child(h1)
        
        # Level 2 header (correct - under level 1)
        h2 = SectionHeader(
            polygon=PolygonBox.from_bbox([50, 150, 300, 170]),
            text="1.1 Background",
            level=2
        )
        page1.add_child(h2)
        
        # Some content
        text1 = Text(
            polygon=PolygonBox.from_bbox([50, 180, 500, 200]),
            text="This section provides background information."
        )
        page1.add_child(text1)
        
        # Level 2 header
        h2_2 = SectionHeader(
            polygon=PolygonBox.from_bbox([50, 250, 300, 270]),
            text="1.2 Objectives",
            level=2
        )
        page1.add_child(h2_2)
        
        doc.pages.append(page1)
        return doc
    
    @pytest.fixture
    def sample_document_incorrect(self):
        """Create a document with incorrect section hierarchy"""
        doc = Document(filepath="test_incorrect.pdf")
        page1 = PageGroup(page_id=0, polygon=PolygonBox.from_bbox([0, 0, 612, 792]))
        
        # Level 2 header without level 1 (incorrect)
        h2 = SectionHeader(
            polygon=PolygonBox.from_bbox([50, 100, 300, 120]),
            text="1.1 Background",
            level=2
        )
        page1.add_child(h2)
        
        # Level 1 header after level 2 (incorrect order)
        h1 = SectionHeader(
            polygon=PolygonBox.from_bbox([50, 150, 300, 170]),
            text="1. Introduction",
            level=1
        )
        page1.add_child(h1)
        
        # Level 3 jumping from level 1 (skipping level 2)
        h3 = SectionHeader(
            polygon=PolygonBox.from_bbox([50, 200, 300, 220]),
            text="1.1.1 Details",
            level=3
        )
        page1.add_child(h3)
        
        doc.pages.append(page1)
        return doc
    
    @pytest.fixture
    def sample_page_images(self):
        """Create mock page images for multimodal analysis"""
        # In real usage, these would be PIL Images
        return {
            0: MagicMock(name="page_0_image"),
            1: MagicMock(name="page_1_image")
        }
    
    def test_verifier_initialization(self, verifier, temp_db):
        """Test verifier properly initializes database"""
        # Check database exists
        assert os.path.exists(temp_db)
        
        # Check tables are created
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = [row[0] for row in cursor.fetchall()]
            assert 'verification_tasks' in tables
    
    def test_extract_section_hierarchy(self, verifier, sample_document_correct):
        """Test extraction of section hierarchy from document"""
        hierarchy = verifier._extract_section_hierarchy(sample_document_correct)
        
        assert len(hierarchy) == 3
        assert hierarchy[0]['text'] == "1. Introduction"
        assert hierarchy[0]['level'] == 1
        assert hierarchy[1]['text'] == "1.1 Background"
        assert hierarchy[1]['level'] == 2
        assert hierarchy[2]['text'] == "1.2 Objectives"
        assert hierarchy[2]['level'] == 2
    
    def test_create_verification_config(self, verifier, sample_document_correct, sample_page_images):
        """Test creation of verification configuration"""
        config = verifier._create_verification_config(
            document=sample_document_correct,
            page_images=sample_page_images
        )
        
        assert isinstance(config, SectionVerificationConfig)
        assert len(config.sections) == 3
        assert config.document_type == "PDF"
        assert config.total_pages == 1
        assert config.has_images is True
    
    @pytest.mark.asyncio
    async def test_verify_sections(self, verifier, sample_document_correct):
        """Test async section verification submission"""
        config = verifier._create_verification_config(
            document=sample_document_correct,
            page_images=None
        )
        
        task_id = await verifier.verify_sections(config)
        
        # Verify task was created in database
        with sqlite3.connect(verifier.db_path) as conn:
            cursor = conn.execute(
                "SELECT status, config FROM verification_tasks WHERE id = ?",
                (task_id,)
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == TaskStatus.PENDING.value
            
            # Verify config was stored correctly
            stored_config = json.loads(row[1])
            assert len(stored_config['sections']) == 3
            assert stored_config['document_type'] == "PDF"
    
    @pytest.mark.asyncio
    async def test_poll_verification_result_completed(self, verifier):
        """Test polling returns result for completed verification"""
        # Create a completed task with issues
        task_id = "test-completed-verification"
        verification_result = {
            "confidence": 0.78,
            "is_valid": False,
            "issues": [
                {
                    "type": "hierarchy_skip",
                    "page": 0,
                    "section": "1.1.1 Details",
                    "description": "Level 3 header appears without level 2",
                    "severity": "warning"
                },
                {
                    "type": "misplaced_header",
                    "page": 0,
                    "section": "1. Introduction",
                    "description": "Level 1 header appears after level 2",
                    "severity": "error"
                }
            ],
            "suggestions": [
                "Reorder sections to maintain proper hierarchy",
                "Add missing level 2 headers"
            ],
            "structural_score": 0.65
        }
        
        with sqlite3.connect(verifier.db_path) as conn:
            conn.execute(
                """INSERT INTO verification_tasks 
                   (id, config, status, result, completed_at) 
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    task_id,
                    json.dumps({}),
                    TaskStatus.COMPLETED.value,
                    json.dumps(verification_result),
                    datetime.now().isoformat()
                )
            )
        
        result = await verifier.poll_verification_result(task_id)
        assert isinstance(result, SectionVerificationResult)
        assert result.confidence == 0.78
        assert result.is_valid is False
        assert len(result.issues) == 2
        assert result.issues[0].type == "hierarchy_skip"
        assert result.issues[1].severity == "error"
        assert result.structural_score == 0.65
    
    def test_sync_verify_sections(self, verifier, sample_document_correct):
        """Test synchronous wrapper for section verification"""
        with patch.object(verifier, 'verify_sections') as mock_verify:
            mock_verify.return_value = asyncio.coroutine(lambda: "task-456")()
            
            task_id = verifier.sync_verify_sections(
                document=sample_document_correct,
                page_images=None
            )
            
            assert task_id == "task-456"
            mock_verify.assert_called_once()
    
    def test_detect_hierarchy_issues(self, verifier, sample_document_incorrect):
        """Test detection of hierarchy issues in document"""
        # Submit verification
        task_id = verifier.sync_verify_sections(
            document=sample_document_incorrect,
            page_images=None
        )
        
        # Simulate background processing
        with sqlite3.connect(verifier.db_path) as conn:
            result_data = {
                "confidence": 0.85,
                "is_valid": False,
                "issues": [
                    {
                        "type": "orphan_header",
                        "page": 0,
                        "section": "1.1 Background",
                        "description": "Level 2 header appears without parent level 1",
                        "severity": "error"
                    },
                    {
                        "type": "hierarchy_inversion",
                        "page": 0,
                        "section": "1. Introduction",
                        "description": "Level 1 header appears after level 2",
                        "severity": "error"
                    },
                    {
                        "type": "level_skip",
                        "page": 0,
                        "section": "1.1.1 Details",
                        "description": "Jumps from level 1 to level 3",
                        "severity": "warning"
                    }
                ],
                "suggestions": [
                    "Move '1. Introduction' before '1.1 Background'",
                    "Add intermediate level 2 header before '1.1.1 Details'"
                ],
                "structural_score": 0.45
            }
            conn.execute(
                """UPDATE verification_tasks 
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
        result = verifier.sync_poll_result(task_id)
        
        assert result is not None
        assert result.is_valid is False
        assert len(result.issues) == 3
        assert any(issue.type == "orphan_header" for issue in result.issues)
        assert result.structural_score < 0.5
    
    def test_multimodal_verification(self, verifier, sample_document_correct, sample_page_images):
        """Test verification with page images for multimodal analysis"""
        task_id = verifier.sync_verify_sections(
            document=sample_document_correct,
            page_images=sample_page_images
        )
        
        # Check that config includes image information
        with sqlite3.connect(verifier.db_path) as conn:
            cursor = conn.execute(
                "SELECT config FROM verification_tasks WHERE id = ?",
                (task_id,)
            )
            row = cursor.fetchone()
            config = json.loads(row[0])
            assert config['has_images'] is True
    
    def test_auto_fix_sections(self, verifier, sample_document_incorrect):
        """Test automatic section fixing when enabled"""
        verifier.auto_fix_enabled = True
        
        # Create a result with fixable issues
        mock_result = SectionVerificationResult(
            confidence=0.9,
            is_valid=False,
            issues=[
                StructuralIssue(
                    type="hierarchy_inversion",
                    page=0,
                    section="1. Introduction",
                    description="Out of order",
                    severity="error"
                )
            ],
            suggestions=["Reorder sections"],
            structural_score=0.7
        )
        
        with patch.object(verifier, '_apply_section_fixes') as mock_fix:
            verifier._process_verification_result(
                sample_document_incorrect,
                mock_result
            )
            
            mock_fix.assert_called_once_with(
                sample_document_incorrect,
                mock_result.issues
            )


if __name__ == "__main__":
    # Run validation
    print("Testing Claude section verifier...")
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    try:
        verifier = BackgroundSectionVerifier(db_path=db_path)
        
        # Create test document
        doc = Document(filepath="test_validation.pdf")
        page = PageGroup(page_id=0, polygon=PolygonBox.from_bbox([0, 0, 612, 792]))
        
        # Add some headers
        h1 = SectionHeader(polygon=PolygonBox.from_bbox([0, 0, 100, 20]), text="Introduction", level=1)
        h2 = SectionHeader(polygon=PolygonBox.from_bbox([0, 30, 100, 50]), text="Background", level=2)
        page.add_child(h1)
        page.add_child(h2)
        doc.pages.append(page)
        
        # Test verification
        task_id = verifier.sync_verify_sections(doc)
        print(f"✓ Created verification task: {task_id}")
        
        # Check database
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute("SELECT * FROM verification_tasks WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            if row:
                print(f"✓ Task stored in database with status: {row[2]}")
                config = json.loads(row[1])
                print(f"✓ Verifying {len(config['sections'])} sections")
            else:
                print("✗ Task not found in database")
        
        print("✅ Claude section verifier validation passed!")
        
    finally:
        os.unlink(db_path)