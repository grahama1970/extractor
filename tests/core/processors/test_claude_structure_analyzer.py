"""
Test suite for Claude structure analysis functionality.

This test validates the background Claude instance integration for analyzing
document structure patterns and providing organizational insights.
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

from marker.processors.claude_structure_analyzer import (
    BackgroundStructureAnalyzer,
    AnalysisConfig as StructureAnalysisConfig,
    AnalysisResult as StructureAnalysisResult,
    TaskStatus,
    StructureInsight as OrganizationalInsight
)
from dataclasses import dataclass

@dataclass
class StructurePattern:
    type: str
    description: str
    strength: float
    examples: list
from marker.schema.blocks.text import Text
from marker.schema.blocks.sectionheader import SectionHeader
from marker.schema.blocks.listitem import ListItem
from marker.schema.blocks.table import Table
from marker.schema.blocks.figure import Figure
from marker.schema.blocks.equation import Equation
from marker.schema.blocks.code import Code
from marker.schema.groups.page import PageGroup
from marker.schema.document import Document


class TestClaudeStructureAnalyzer:
    """Test suite for Claude structure analysis"""
    
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
    def analyzer(self, temp_db):
        """Create analyzer instance with temporary database"""
        return BackgroundStructureAnalyzer(db_path=temp_db)
    
    @pytest.fixture
    def sample_hierarchical_document(self):
        """Create a document with hierarchical structure"""
        doc = Document(filepath="test_hierarchical.pdf")
        
        # Page 1 - Clear hierarchy
        page1 = PageGroup(page_id=0, bbox=[0, 0, 612, 792])
        
        # Chapter
        chapter = SectionHeader(text="Chapter 1: Introduction", level=1, bbox=[50, 100, 400, 130])
        page1.add_child(chapter)
        
        # Section
        section1 = SectionHeader(text="1.1 Background", level=2, bbox=[50, 150, 300, 170])
        page1.add_child(section1)
        
        text1 = Text(text="Background information about the topic.", bbox=[50, 180, 500, 200])
        page1.add_child(text1)
        
        # Subsection
        subsection = SectionHeader(text="1.1.1 Historical Context", level=3, bbox=[50, 220, 300, 240])
        page1.add_child(subsection)
        
        text2 = Text(text="Historical development of the field.", bbox=[50, 250, 500, 270])
        page1.add_child(text2)
        
        # Another section
        section2 = SectionHeader(text="1.2 Objectives", level=2, bbox=[50, 300, 300, 320])
        page1.add_child(section2)
        
        # List of objectives
        obj1 = ListItem(text="Understand the fundamental concepts", bbox=[70, 330, 400, 350])
        obj2 = ListItem(text="Apply theoretical knowledge", bbox=[70, 360, 400, 380])
        page1.add_child(obj1)
        page1.add_child(obj2)
        
        doc.pages.append(page1)
        return doc
    
    @pytest.fixture
    def sample_sequential_document(self):
        """Create a document with sequential/procedural structure"""
        doc = Document(filepath="test_sequential.pdf")
        
        page1 = PageGroup(page_id=0, bbox=[0, 0, 612, 792])
        
        # Title
        title = SectionHeader(text="Installation Guide", level=1, bbox=[50, 100, 400, 130])
        page1.add_child(title)
        
        # Step 1
        step1 = SectionHeader(text="Step 1: Prerequisites", level=2, bbox=[50, 150, 300, 170])
        page1.add_child(step1)
        
        prereq1 = ListItem(text="Python 3.8 or higher", bbox=[70, 180, 300, 200])
        prereq2 = ListItem(text="Git installed", bbox=[70, 210, 300, 230])
        page1.add_child(prereq1)
        page1.add_child(prereq2)
        
        # Step 2
        step2 = SectionHeader(text="Step 2: Download", level=2, bbox=[50, 250, 300, 270])
        page1.add_child(step2)
        
        code1 = Code(
            text="git clone https://github.com/example/repo.git",
            language="bash",
            bbox=[50, 280, 400, 300]
        )
        page1.add_child(code1)
        
        # Step 3
        step3 = SectionHeader(text="Step 3: Install", level=2, bbox=[50, 320, 300, 340])
        page1.add_child(step3)
        
        code2 = Code(
            text="pip install -r requirements.txt",
            language="bash",
            bbox=[50, 350, 400, 370]
        )
        page1.add_child(code2)
        
        doc.pages.append(page1)
        return doc
    
    @pytest.fixture
    def sample_modular_document(self):
        """Create a document with modular/reference structure"""
        doc = Document(filepath="test_modular.pdf")
        
        page1 = PageGroup(page_id=0, bbox=[0, 0, 612, 792])
        
        # Title
        title = SectionHeader(text="API Reference", level=1, bbox=[50, 100, 400, 130])
        page1.add_child(title)
        
        # Module 1
        module1 = SectionHeader(text="Authentication Module", level=2, bbox=[50, 150, 300, 170])
        page1.add_child(module1)
        
        # Function definition
        func1 = Code(
            text="def authenticate(username: str, password: str) -> bool:",
            language="python",
            bbox=[50, 180, 400, 200]
        )
        page1.add_child(func1)
        
        desc1 = Text(text="Authenticates a user with credentials.", bbox=[50, 210, 400, 230])
        page1.add_child(desc1)
        
        # Module 2
        module2 = SectionHeader(text="Database Module", level=2, bbox=[50, 250, 300, 270])
        page1.add_child(module2)
        
        # Function definition
        func2 = Code(
            text="def query(sql: str, params: dict) -> list:",
            language="python",
            bbox=[50, 280, 400, 300]
        )
        page1.add_child(func2)
        
        desc2 = Text(text="Executes a database query.", bbox=[50, 310, 400, 330])
        page1.add_child(desc2)
        
        doc.pages.append(page1)
        return doc
    
    def test_analyzer_initialization(self, analyzer, temp_db):
        """Test analyzer properly initializes database"""
        # Check database exists
        assert os.path.exists(temp_db)
        
        # Check tables are created
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = [row[0] for row in cursor.fetchall()]
            assert 'analysis_tasks' in tables
    
    def test_extract_structural_features(self, analyzer, sample_hierarchical_document):
        """Test extraction of structural features from document"""
        features = analyzer._extract_structural_features(sample_hierarchical_document)
        
        assert features['total_sections'] == 5  # 1 chapter + 2 sections + 2 subsections
        assert features['max_depth'] == 3
        assert features['has_lists'] is True
        assert features['has_code'] is False
        assert features['has_tables'] is False
        assert features['sections_per_page'] == [5]
        assert 'Introduction' in str(features['section_hierarchy'])
    
    def test_create_analysis_config(self, analyzer, sample_hierarchical_document):
        """Test creation of analysis configuration"""
        config = analyzer._create_analysis_config(
            document=sample_hierarchical_document,
            focus_areas=["hierarchy", "navigation"]
        )
        
        assert isinstance(config, StructureAnalysisConfig)
        assert config.document_type == "PDF"
        assert config.total_pages == 1
        assert config.structural_features['total_sections'] == 5
        assert "hierarchy" in config.focus_areas
        assert "navigation" in config.focus_areas
    
    @pytest.mark.asyncio
    async def test_analyze_structure(self, analyzer, sample_hierarchical_document):
        """Test async structure analysis submission"""
        config = analyzer._create_analysis_config(
            document=sample_hierarchical_document,
            focus_areas=["organization"]
        )
        
        task_id = await analyzer.analyze_structure(config)
        
        # Verify task was created in database
        with sqlite3.connect(analyzer.db_path) as conn:
            cursor = conn.execute(
                "SELECT status, config FROM analysis_tasks WHERE id = ?",
                (task_id,)
            )
            row = cursor.fetchone()
            assert row is not None
            assert row[0] == TaskStatus.PENDING.value
            
            # Verify config was stored correctly
            stored_config = json.loads(row[1])
            assert stored_config['total_pages'] == 1
            assert "organization" in stored_config['focus_areas']
    
    @pytest.mark.asyncio
    async def test_poll_analysis_result_hierarchical(self, analyzer):
        """Test polling returns result for hierarchical structure analysis"""
        # Create a completed task for hierarchical document
        task_id = "test-hierarchical-analysis"
        analysis_result = {
            "confidence": 0.92,
            "structure_type": "hierarchical",
            "patterns": [
                {
                    "type": "nested_sections",
                    "description": "Document uses clear 3-level hierarchy",
                    "strength": 0.95,
                    "examples": ["Chapter 1 > 1.1 Background > 1.1.1 Historical Context"]
                },
                {
                    "type": "consistent_numbering",
                    "description": "Sections follow consistent numbering scheme",
                    "strength": 0.90,
                    "examples": ["1.1", "1.1.1", "1.2"]
                }
            ],
            "insights": [
                {
                    "category": "organization",
                    "insight": "Well-structured hierarchical document with clear parent-child relationships",
                    "impact": "high",
                    "recommendation": "Maintain current structure for clarity"
                },
                {
                    "category": "navigation",
                    "insight": "Deep nesting may make navigation complex",
                    "impact": "medium",
                    "recommendation": "Consider adding a table of contents"
                }
            ],
            "complexity_score": 0.7,
            "organization_score": 0.88
        }
        
        with sqlite3.connect(analyzer.db_path) as conn:
            conn.execute(
                """INSERT INTO analysis_tasks 
                   (id, config, status, result, completed_at) 
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    task_id,
                    json.dumps({}),
                    TaskStatus.COMPLETED.value,
                    json.dumps(analysis_result),
                    datetime.now().isoformat()
                )
            )
        
        result = await analyzer.poll_analysis_result(task_id)
        assert isinstance(result, StructureAnalysisResult)
        assert result.confidence == 0.92
        assert result.structure_type == "hierarchical"
        assert len(result.patterns) == 2
        assert result.patterns[0].type == "nested_sections"
        assert result.organization_score == 0.88
    
    def test_sync_analyze_structure(self, analyzer, sample_sequential_document):
        """Test synchronous wrapper for structure analysis"""
        with patch.object(analyzer, 'analyze_structure') as mock_analyze:
            mock_analyze.return_value = asyncio.coroutine(lambda: "task-seq-123")()
            
            task_id = analyzer.sync_analyze_structure(
                document=sample_sequential_document,
                focus_areas=["flow", "procedures"]
            )
            
            assert task_id == "task-seq-123"
            mock_analyze.assert_called_once()
    
    def test_detect_sequential_structure(self, analyzer, sample_sequential_document):
        """Test detection of sequential/procedural document structure"""
        # Submit analysis
        task_id = analyzer.sync_analyze_structure(
            document=sample_sequential_document,
            focus_areas=["procedures", "flow"]
        )
        
        # Simulate background processing
        with sqlite3.connect(analyzer.db_path) as conn:
            result_data = {
                "confidence": 0.88,
                "structure_type": "sequential",
                "patterns": [
                    {
                        "type": "step_progression",
                        "description": "Document follows clear step-by-step progression",
                        "strength": 0.92,
                        "examples": ["Step 1: Prerequisites", "Step 2: Download", "Step 3: Install"]
                    },
                    {
                        "type": "code_instructions",
                        "description": "Each step includes executable code examples",
                        "strength": 0.85,
                        "examples": ["git clone", "pip install"]
                    }
                ],
                "insights": [
                    {
                        "category": "procedures",
                        "insight": "Clear procedural flow suitable for tutorials",
                        "impact": "high",
                        "recommendation": "Add completion indicators for each step"
                    },
                    {
                        "category": "flow",
                        "insight": "Linear progression without branching paths",
                        "impact": "medium",
                        "recommendation": "Consider adding troubleshooting sections"
                    }
                ],
                "complexity_score": 0.3,
                "organization_score": 0.90
            }
            conn.execute(
                """UPDATE analysis_tasks 
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
        result = analyzer.sync_poll_result(task_id)
        
        assert result is not None
        assert result.structure_type == "sequential"
        assert any(p.type == "step_progression" for p in result.patterns)
        assert result.complexity_score < 0.5  # Sequential docs are typically simpler
    
    def test_detect_modular_structure(self, analyzer, sample_modular_document):
        """Test detection of modular/reference document structure"""
        # Submit analysis
        task_id = analyzer.sync_analyze_structure(
            document=sample_modular_document,
            focus_areas=["modularity", "reference"]
        )
        
        # Simulate background processing
        with sqlite3.connect(analyzer.db_path) as conn:
            result_data = {
                "confidence": 0.85,
                "structure_type": "modular",
                "patterns": [
                    {
                        "type": "independent_modules",
                        "description": "Document organized as independent, self-contained modules",
                        "strength": 0.88,
                        "examples": ["Authentication Module", "Database Module"]
                    },
                    {
                        "type": "api_documentation",
                        "description": "Each module follows API documentation pattern",
                        "strength": 0.82,
                        "examples": ["Function signatures", "Parameter descriptions"]
                    }
                ],
                "insights": [
                    {
                        "category": "modularity",
                        "insight": "Highly modular structure allows independent reference",
                        "impact": "high",
                        "recommendation": "Add cross-references between related modules"
                    },
                    {
                        "category": "reference",
                        "insight": "Good for lookup but lacks narrative flow",
                        "impact": "medium",
                        "recommendation": "Consider adding usage examples"
                    }
                ],
                "complexity_score": 0.6,
                "organization_score": 0.82
            }
            conn.execute(
                """UPDATE analysis_tasks 
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
        result = analyzer.sync_poll_result(task_id)
        
        assert result is not None
        assert result.structure_type == "modular"
        assert any(p.type == "independent_modules" for p in result.patterns)
        assert any(i.category == "modularity" for i in result.insights)
    
    def test_focus_area_analysis(self, analyzer, sample_hierarchical_document):
        """Test analysis with specific focus areas"""
        focus_areas = ["navigation", "complexity", "accessibility"]
        
        task_id = analyzer.sync_analyze_structure(
            document=sample_hierarchical_document,
            focus_areas=focus_areas
        )
        
        # Check that config includes focus areas
        with sqlite3.connect(analyzer.db_path) as conn:
            cursor = conn.execute(
                "SELECT config FROM analysis_tasks WHERE id = ?",
                (task_id,)
            )
            row = cursor.fetchone()
            config = json.loads(row[0])
            assert all(area in config['focus_areas'] for area in focus_areas)


if __name__ == "__main__":
    # Run validation
    print("Testing Claude structure analyzer...")
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    try:
        analyzer = BackgroundStructureAnalyzer(db_path=db_path)
        
        # Create test document
        doc = Document(filepath="test_structure.pdf")
        page = PageGroup(page_id=0, bbox=[0, 0, 612, 792])
        
        # Add hierarchical structure
        h1 = SectionHeader(text="Main Topic", level=1, bbox=[0, 0, 200, 30])
        h2 = SectionHeader(text="Subtopic", level=2, bbox=[0, 40, 200, 60])
        text = Text(text="Content under subtopic.", bbox=[0, 70, 400, 90])
        
        page.add_child(h1)
        page.add_child(h2)
        page.add_child(text)
        doc.pages.append(page)
        
        # Test analysis
        task_id = analyzer.sync_analyze_structure(doc, focus_areas=["hierarchy"])
        print(f"✓ Created analysis task: {task_id}")
        
        # Check database
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute("SELECT * FROM analysis_tasks WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            if row:
                print(f"✓ Task stored in database with status: {row[2]}")
                config = json.loads(row[1])
                print(f"✓ Analyzing structure with {config['structural_features']['total_sections']} sections")
            else:
                print("✗ Task not found in database")
        
        print("✅ Claude structure analyzer validation passed!")
        
    finally:
        os.unlink(db_path)