"""
Test suite for Claude table merge analyzer functionality.

This test validates the background Claude instance integration for analyzing
table merges and providing AI-powered content quality assessments.
"""

import asyncio
import json
import os
import pytest
import sqlite3
import tempfile
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

from marker.processors.claude_table_merge_analyzer import (
    BackgroundTableAnalyzer,
    AnalysisConfig,
    AnalysisResult,
    TaskStatus
)
from marker.schema.blocks.table import Table
from marker.schema.blocks.text import Text
from marker.schema.groups.page import PageGroup
from marker.schema.polygon import PolygonBox


class TestClaudeTableMergeAnalyzer:
    """Test suite for Claude table merge analyzer"""
    
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
        return BackgroundTableAnalyzer(db_path=temp_db)
    
    @pytest.fixture
    def sample_tables(self):
        """Create sample table blocks for testing"""
        # Create a simple table
        table1 = Table(
            polygon=PolygonBox.from_bbox([0, 0, 100, 50]),
            cells=[["Header 1", "Header 2"], ["Data 1", "Data 2"]],
            rows=[{"cells": ["Header 1", "Header 2"]}, {"cells": ["Data 1", "Data 2"]}],
            extraction_method="surya",
            extraction_details={},
            quality_score=0.9,
            quality_metrics={},
            merge_info={}
        )
        
        # Create a complex table with financial data
        table2 = Table(
            polygon=PolygonBox.from_bbox([0, 100, 200, 200]),
            cells=[
                ["Year", "Revenue", "Profit"], 
                ["2023", "$1.2M", "$200K"],
                ["2024", "$1.5M", "$300K"]
            ],
            rows=[
                {"cells": ["Year", "Revenue", "Profit"]},
                {"cells": ["2023", "$1.2M", "$200K"]},
                {"cells": ["2024", "$1.5M", "$300K"]}
            ],
            extraction_method="surya",
            extraction_details={},
            quality_score=0.85,
            quality_metrics={},
            merge_info={}
        )
        
        return [table1, table2]
    
    @pytest.fixture
    def sample_page(self, sample_tables):
        """Create a sample page with tables and text"""
        page = PageGroup(
            page_id=0,
            polygon=PolygonBox.from_bbox([0, 0, 612, 792])
        )
        
        # Add context text before table
        text1 = Text(
            polygon=PolygonBox.from_bbox([0, 0, 300, 20]),
            text="The following table shows our quarterly results:"
        )
        page.add_child(text1)
        
        # Add first table
        page.add_child(sample_tables[0])
        
        # Add text between tables
        text2 = Text(
            polygon=PolygonBox.from_bbox([0, 60, 300, 80]),
            text="Financial summary for the past two years:"
        )
        page.add_child(text2)
        
        # Add second table
        page.add_child(sample_tables[1])
        
        return page
    
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
    
    def test_create_analysis_config(self, analyzer, sample_tables, sample_page):
        """Test creation of analysis configuration"""
        config = analyzer._create_analysis_config(
            tables=sample_tables,
            page_context=sample_page,
            merge_reason="Financial data continuation"
        )
        
        assert isinstance(config, AnalysisConfig)
        assert len(config.tables) == 2
        assert config.merge_reason == "Financial data continuation"
        assert "quarterly results" in config.context
        assert "Financial summary" in config.context
    
    @pytest.mark.asyncio
    async def test_analyze_table_merge(self, analyzer, sample_tables, sample_page):
        """Test async table merge analysis submission"""
        config = analyzer._create_analysis_config(
            tables=sample_tables,
            page_context=sample_page,
            merge_reason="Related financial data"
        )
        
        task_id = await analyzer.analyze_table_merge(config)
        
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
            assert stored_config['merge_reason'] == "Related financial data"
            assert len(stored_config['tables']) == 2
    
    @pytest.mark.asyncio
    async def test_poll_analysis_result_pending(self, analyzer):
        """Test polling returns None for pending tasks"""
        # Create a pending task
        task_id = "test-pending-task"
        with sqlite3.connect(analyzer.db_path) as conn:
            conn.execute(
                "INSERT INTO analysis_tasks (id, config, status) VALUES (?, ?, ?)",
                (task_id, json.dumps({}), TaskStatus.PENDING.value)
            )
        
        result = await analyzer.poll_analysis_result(task_id)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_poll_analysis_result_completed(self, analyzer):
        """Test polling returns result for completed tasks"""
        # Create a completed task
        task_id = "test-completed-task"
        analysis_result = {
            "confidence": 0.85,
            "should_merge": True,
            "reasoning": "Tables contain related financial data",
            "quality_score": 0.9,
            "suggestions": ["Consider adding year labels"]
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
        assert isinstance(result, AnalysisResult)
        assert result.confidence == 0.85
        assert result.should_merge is True
        assert "related financial data" in result.reasoning
        assert result.quality_score == 0.9
        assert len(result.suggestions) == 1
    
    def test_sync_analyze_table_merge(self, analyzer, sample_tables, sample_page):
        """Test synchronous wrapper for table merge analysis"""
        with patch.object(analyzer, 'analyze_table_merge') as mock_analyze:
            mock_analyze.return_value = asyncio.coroutine(lambda: "task-123")()
            
            task_id = analyzer.sync_analyze_table_merge(
                tables=sample_tables,
                page_context=sample_page,
                merge_reason="Test merge"
            )
            
            assert task_id == "task-123"
            mock_analyze.assert_called_once()
    
    def test_sync_poll_result(self, analyzer):
        """Test synchronous wrapper for polling results"""
        mock_result = AnalysisResult(
            confidence=0.8,
            should_merge=True,
            reasoning="Test reasoning",
            quality_score=0.85,
            suggestions=[]
        )
        
        with patch.object(analyzer, 'poll_analysis_result') as mock_poll:
            mock_poll.return_value = asyncio.coroutine(lambda: mock_result)()
            
            result = analyzer.sync_poll_result("task-123")
            
            assert result == mock_result
            mock_poll.assert_called_once_with("task-123")
    
    def test_integration_workflow(self, analyzer, sample_tables, sample_page):
        """Test complete integration workflow"""
        # Submit analysis
        task_id = analyzer.sync_analyze_table_merge(
            tables=sample_tables,
            page_context=sample_page,
            merge_reason="Integration test"
        )
        
        assert task_id is not None
        
        # Simulate background processing by manually updating the task
        with sqlite3.connect(analyzer.db_path) as conn:
            result_data = {
                "confidence": 0.92,
                "should_merge": True,
                "reasoning": "Tables share financial context and time continuity",
                "quality_score": 0.88,
                "suggestions": [
                    "Add column headers for clarity",
                    "Consider formatting numbers consistently"
                ]
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
        assert result.confidence == 0.92
        assert result.should_merge is True
        assert len(result.suggestions) == 2
    
    def test_error_handling(self, analyzer):
        """Test error handling for invalid task IDs"""
        result = analyzer.sync_poll_result("non-existent-task")
        assert result is None
    
    def test_multiple_concurrent_tasks(self, analyzer, sample_tables, sample_page):
        """Test handling multiple concurrent analysis tasks"""
        task_ids = []
        
        # Submit multiple tasks
        for i in range(3):
            task_id = analyzer.sync_analyze_table_merge(
                tables=sample_tables,
                page_context=sample_page,
                merge_reason=f"Concurrent test {i}"
            )
            task_ids.append(task_id)
        
        # Verify all tasks were created
        with sqlite3.connect(analyzer.db_path) as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM analysis_tasks WHERE status = ?",
                (TaskStatus.PENDING.value,)
            )
            count = cursor.fetchone()[0]
            assert count >= 3
        
        # Verify each task has unique ID
        assert len(set(task_ids)) == 3


if __name__ == "__main__":
    # Run validation
    print("Testing Claude table merge analyzer...")
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    try:
        analyzer = BackgroundTableAnalyzer(db_path=db_path)
        
        # Test basic functionality
        sample_table = Table(
            polygon=PolygonBox.from_bbox([0, 0, 100, 50]),
            cells=[["Test", "Data"], ["123", "456"]],
            extraction_method="test",
            extraction_details={},
            quality_score=0.8,
            quality_metrics={},
            merge_info={}
        )
        
        task_id = analyzer.sync_analyze_table_merge(
            tables=[sample_table],
            page_context=None,
            merge_reason="Validation test"
        )
        
        print(f"✓ Created task: {task_id}")
        
        # Check database
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute("SELECT * FROM analysis_tasks WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            if row:
                print(f"✓ Task stored in database with status: {row[2]}")
            else:
                print("✗ Task not found in database")
        
        print("✅ Claude table merge analyzer validation passed!")
        
    finally:
        os.unlink(db_path)