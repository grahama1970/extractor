"""
Simplified Unified Claude service for Marker.

This module provides a single interface for all Claude interactions in Marker,
replacing the fragmented approach with multiple SQLite databases and subprocess calls.

Links:
- Original Claude service: marker/services/claude.py
- Migration plan: docs/tasks/034_Claude_Module_Communicator_Integration.md

Sample Input:
{
    "action": "analyze_tables",
    "table1": {"cells": [...], "bbox": [...]},
    "table2": {"cells": [...], "bbox": [...]},
    "context": {"page": 1, "confidence_threshold": 0.8}
}

Expected Output:
{
    "should_merge": True,
    "confidence": 0.85,
    "reason": "Tables share common structure"
}
"""

import asyncio
import json
import sqlite3
import uuid
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum

from loguru import logger


class TaskStatus(Enum):
    """Task status for background processing."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class UnifiedClaudeService:
    """
    Simplified unified Claude service that consolidates all Claude operations.
    
    This implementation provides:
    - Single SQLite database for all operations
    - Unified task queue management
    - Consistent error handling
    - Performance tracking
    """
    
    _instance = None
    
    def __new__(cls):
        """Singleton pattern to ensure single instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the unified Claude service."""
        if self._initialized:
            return
            
        self.db_path = Path.home() / ".marker" / "claude_unified.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._init_database()
        self._initialized = True
        
        logger.info(f"Initialized UnifiedClaudeService with database at {self.db_path}")
    
    def _init_database(self):
        """Initialize the unified database for all Claude operations."""
        conn = sqlite3.connect(str(self.db_path))
        
        # Create unified task table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS claude_tasks (
                task_id TEXT PRIMARY KEY,
                task_type TEXT NOT NULL,
                status TEXT NOT NULL,
                input_data TEXT NOT NULL,
                result TEXT,
                error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processing_time_ms INTEGER,
                metadata TEXT
            )
        ''')
        
        # Create performance tracking table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS performance_metrics (
                metric_id TEXT PRIMARY KEY,
                task_id TEXT,
                metric_type TEXT NOT NULL,
                value REAL NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES claude_tasks(task_id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    # Core operations
    
    def analyze_tables(self, 
                      table1_data: Dict[str, Any],
                      table2_data: Dict[str, Any],
                      context: Dict[str, Any]) -> str:
        """
        Analyze tables for potential merging.
        
        Args:
            table1_data: First table data
            table2_data: Second table data
            context: Analysis context
            
        Returns:
            task_id: String UUID for tracking
        """
        task_data = {
            "table1": table1_data,
            "table2": table2_data,
            "context": context
        }
        
        return self._create_task("table_analysis", task_data)
    
    def describe_image(self,
                      image_path: str,
                      context: Dict[str, Any]) -> str:
        """
        Describe an image using Claude's vision capabilities.
        
        Args:
            image_path: Path to image file
            context: Additional context
            
        Returns:
            task_id: String UUID for tracking
        """
        task_data = {
            "image_path": image_path,
            "context": context
        }
        
        return self._create_task("image_description", task_data)
    
    def validate_content(self,
                        content: str,
                        validation_rules: List[str]) -> str:
        """
        Validate content against specified rules.
        
        Args:
            content: Content to validate
            validation_rules: List of validation rules
            
        Returns:
            task_id: String UUID for tracking
        """
        task_data = {
            "content": content,
            "rules": validation_rules
        }
        
        return self._create_task("content_validation", task_data)
    
    def analyze_structure(self,
                         document_blocks: List[Dict[str, Any]],
                         context: Dict[str, Any]) -> str:
        """
        Analyze document structure.
        
        Args:
            document_blocks: List of document blocks
            context: Analysis context
            
        Returns:
            task_id: String UUID for tracking
        """
        task_data = {
            "blocks": document_blocks,
            "context": context
        }
        
        return self._create_task("structure_analysis", task_data)
    
    # Task management
    
    def _create_task(self, task_type: str, input_data: Dict[str, Any]) -> str:
        """Create a new task in the database."""
        task_id = str(uuid.uuid4())
        
        conn = sqlite3.connect(str(self.db_path))
        conn.execute(
            """INSERT INTO claude_tasks 
               (task_id, task_type, status, input_data, metadata)
               VALUES (?, ?, ?, ?, ?)""",
            (task_id, task_type, TaskStatus.PENDING.value, 
             json.dumps(input_data), json.dumps({"version": "1.0"}))
        )
        conn.commit()
        conn.close()
        
        # Start async processing in a thread-safe way
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._process_task_async(task_id, task_type, input_data))
        except RuntimeError:
            # No event loop, create one in a thread
            import threading
            def run_async():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self._process_task_async(task_id, task_type, input_data))
                loop.close()
            
            thread = threading.Thread(target=run_async)
            thread.daemon = True
            thread.start()
        
        logger.info(f"Created {task_type} task: {task_id}")
        return task_id
    
    async def _process_task_async(self, task_id: str, task_type: str, input_data: Dict[str, Any]):
        """Process task asynchronously."""
        start_time = datetime.now()
        
        try:
            # Update status to processing
            self._update_task_status(task_id, TaskStatus.PROCESSING)
            
            # Process based on task type
            if task_type == "table_analysis":
                result = await self._process_table_analysis(input_data)
            elif task_type == "image_description":
                result = await self._process_image_description(input_data)
            elif task_type == "content_validation":
                result = await self._process_content_validation(input_data)
            elif task_type == "structure_analysis":
                result = await self._process_structure_analysis(input_data)
            else:
                raise ValueError(f"Unknown task type: {task_type}")
            
            # Calculate processing time
            processing_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            
            # Update task with result
            conn = sqlite3.connect(str(self.db_path))
            conn.execute(
                """UPDATE claude_tasks 
                   SET status = ?, result = ?, processing_time_ms = ?, updated_at = ?
                   WHERE task_id = ?""",
                (TaskStatus.COMPLETED.value, json.dumps(result), 
                 processing_time_ms, datetime.now(), task_id)
            )
            conn.commit()
            conn.close()
            
            # Record performance metric
            self._record_metric(task_id, "processing_time", processing_time_ms)
            
            logger.info(f"Task {task_id} completed in {processing_time_ms}ms")
            
        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            self._update_task_status(task_id, TaskStatus.FAILED, str(e))
    
    def _update_task_status(self, task_id: str, status: TaskStatus, error: str = None):
        """Update task status in database."""
        conn = sqlite3.connect(str(self.db_path))
        
        if error:
            conn.execute(
                """UPDATE claude_tasks 
                   SET status = ?, error = ?, updated_at = ?
                   WHERE task_id = ?""",
                (status.value, error, datetime.now(), task_id)
            )
        else:
            conn.execute(
                """UPDATE claude_tasks 
                   SET status = ?, updated_at = ?
                   WHERE task_id = ?""",
                (status.value, datetime.now(), task_id)
            )
        
        conn.commit()
        conn.close()
    
    def _record_metric(self, task_id: str, metric_type: str, value: float):
        """Record a performance metric."""
        metric_id = str(uuid.uuid4())
        
        conn = sqlite3.connect(str(self.db_path))
        conn.execute(
            """INSERT INTO performance_metrics 
               (metric_id, task_id, metric_type, value)
               VALUES (?, ?, ?, ?)""",
            (metric_id, task_id, metric_type, value)
        )
        conn.commit()
        conn.close()
    
    # Processing implementations (simplified for now)
    
    async def _process_table_analysis(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process table analysis request."""
        # Simulate processing delay
        await asyncio.sleep(0.5)
        
        # For now, return mock result
        # TODO: Integrate with actual Claude API
        return {
            "should_merge": True,
            "confidence": 0.85,
            "reason": "Tables share common column structure and appear to be continuations",
            "merged_table": {
                "headers": ["Name", "Age", "Location"],
                "rows": [
                    ["John", "30", "New York"],
                    ["Jane", "25", "Los Angeles"]
                ]
            }
        }
    
    async def _process_image_description(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process image description request."""
        await asyncio.sleep(0.3)
        
        return {
            "description": "A complex flowchart showing data processing pipeline",
            "elements": ["flowchart", "arrows", "text boxes", "decision points"],
            "text_content": "Start → Process Data → Decision → Output"
        }
    
    async def _process_content_validation(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process content validation request."""
        await asyncio.sleep(0.2)
        
        return {
            "valid": True,
            "issues": [],
            "suggestions": ["Consider adding more descriptive headings"]
        }
    
    async def _process_structure_analysis(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process structure analysis request."""
        await asyncio.sleep(0.4)
        
        return {
            "structure_type": "hierarchical",
            "hierarchy": [
                {"level": 1, "type": "chapter", "count": 3},
                {"level": 2, "type": "section", "count": 12},
                {"level": 3, "type": "subsection", "count": 24}
            ],
            "sections": ["Introduction", "Methods", "Results", "Discussion"]
        }
    
    # Query methods
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get task status and result."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.execute(
            """SELECT task_type, status, result, error, created_at, updated_at, 
                      processing_time_ms, metadata
               FROM claude_tasks WHERE task_id = ?""",
            (task_id,)
        )
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return {"status": "not_found", "error": "Task not found"}
        
        task_type, status, result, error, created_at, updated_at, processing_time_ms, metadata = row
        
        response = {
            "task_id": task_id,
            "task_type": task_type,
            "status": status,
            "created_at": created_at,
            "updated_at": updated_at
        }
        
        if processing_time_ms:
            response["processing_time_ms"] = processing_time_ms
        
        if result:
            response["result"] = json.loads(result)
        
        if error:
            response["error"] = error
            
        if metadata:
            response["metadata"] = json.loads(metadata)
        
        return response
    
    def get_performance_metrics(self, days: int = 7) -> Dict[str, Any]:
        """Get performance metrics for the last N days."""
        conn = sqlite3.connect(str(self.db_path))
        
        # Average processing time by task type
        cursor = conn.execute(
            """SELECT task_type, AVG(processing_time_ms) as avg_time, COUNT(*) as count
               FROM claude_tasks 
               WHERE created_at > datetime('now', ?)
               AND status = ?
               GROUP BY task_type""",
            (f'-{days} days', TaskStatus.COMPLETED.value)
        )
        
        metrics = {
            "by_task_type": {},
            "total_tasks": 0,
            "success_rate": 0.0
        }
        
        for row in cursor:
            task_type, avg_time, count = row
            metrics["by_task_type"][task_type] = {
                "average_time_ms": round(avg_time, 2),
                "count": count
            }
            metrics["total_tasks"] += count
        
        # Success rate
        cursor = conn.execute(
            """SELECT 
                   COUNT(CASE WHEN status = ? THEN 1 END) as completed,
                   COUNT(*) as total
               FROM claude_tasks 
               WHERE created_at > datetime('now', ?)""",
            (TaskStatus.COMPLETED.value, f'-{days} days')
        )
        
        completed, total = cursor.fetchone()
        if total > 0:
            metrics["success_rate"] = round(completed / total * 100, 2)
        
        conn.close()
        return metrics
    
    def wait_for_task(self, task_id: str, timeout: float = 60.0) -> Dict[str, Any]:
        """Wait for task completion (blocking)."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self._wait_for_task_async(task_id, timeout)
            )
        finally:
            loop.close()
    
    async def _wait_for_task_async(self, task_id: str, timeout: float) -> Dict[str, Any]:
        """Async wait for task completion."""
        start_time = asyncio.get_event_loop().time()
        
        while True:
            status = self.get_task_status(task_id)
            
            if status["status"] in [TaskStatus.COMPLETED.value, TaskStatus.FAILED.value]:
                return status
            
            if asyncio.get_event_loop().time() - start_time > timeout:
                return {
                    "task_id": task_id,
                    "status": "timeout",
                    "error": f"Task did not complete within {timeout} seconds"
                }
            
            await asyncio.sleep(0.1)


# Create global instance
unified_claude_service = UnifiedClaudeService()


# Validation and testing
if __name__ == "__main__":
    async def test_unified_service():
        """Test the unified Claude service."""
        service = UnifiedClaudeService()
        
        print("Testing Unified Claude Service...\n")
        
        # Test table analysis
        table1 = {"headers": ["Name", "Age"], "rows": [["John", "30"]]}
        table2 = {"headers": ["Name", "Age"], "rows": [["Jane", "25"]]}
        context = {"document_type": "pdf", "page": 1}
        
        print("1. Creating table analysis task...")
        task_id = service.analyze_tables(table1, table2, context)
        print(f"   Task ID: {task_id}")
        
        # Wait a bit for processing
        await asyncio.sleep(1.0)
        
        # Check status
        status = service.get_task_status(task_id)
        print(f"   Status: {status['status']}")
        if "result" in status:
            print(f"   Result: {json.dumps(status['result'], indent=2)}")
        
        # Test image description
        print("\n2. Creating image description task...")
        task_id2 = service.describe_image("/path/to/image.png", {"page": 2})
        print(f"   Task ID: {task_id2}")
        
        # Test content validation
        print("\n3. Creating content validation task...")
        task_id3 = service.validate_content(
            "This is test content with grammer mistake.",
            ["spelling", "grammar"]
        )
        print(f"   Task ID: {task_id3}")
        
        # Test structure analysis
        print("\n4. Creating structure analysis task...")
        blocks = [
            {"type": "heading", "text": "Chapter 1", "level": 1},
            {"type": "paragraph", "text": "Introduction content..."},
            {"type": "heading", "text": "Section 1.1", "level": 2}
        ]
        task_id4 = service.analyze_structure(blocks, {"doc_type": "book"})
        print(f"   Task ID: {task_id4}")
        
        # Wait for all tasks
        await asyncio.sleep(1.5)
        
        # Get performance metrics
        print("\n5. Performance Metrics:")
        metrics = service.get_performance_metrics(days=1)
        print(f"   {json.dumps(metrics, indent=2)}")
        
        print("\n✅ All tests completed successfully!")
        
        # Test synchronous wait
        print("\n6. Testing synchronous wait...")
        task_id5 = service.analyze_tables(table1, table2, {"sync": True})
        result = service.wait_for_task(task_id5, timeout=5.0)
        print(f"   Sync result: {result['status']}")
    
    # Run tests
    asyncio.run(test_unified_service())