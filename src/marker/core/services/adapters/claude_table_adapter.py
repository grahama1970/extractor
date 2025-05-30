"""
Adapter for migrating existing table merge analyzer to unified Claude service.

This adapter maintains backwards compatibility while internally using the new
unified Claude service with claude-module-communicator.

Links:
- Original implementation: marker/processors/claude_table_merge_analyzer.py
- Migration plan: docs/tasks/034_Claude_Module_Communicator_Integration.md

Sample Input (existing format):
{
    "table1": {"cells": [...], "bbox": [...]},
    "table2": {"cells": [...], "bbox": [...]},
    "config": AnalysisConfig(...)
}

Expected Output (existing format):
{
    "task_id": "uuid-string",
    "status": "pending"
}
"""

import asyncio
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import json
import sqlite3
from enum import Enum

from loguru import logger

from marker.core.services.claude_unified import unified_claude_service


class TaskStatus(Enum):
    """Task status matching original implementation."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ClaudeTableMergeAdapter:
    """
    Adapter that maintains the original ClaudeTableMergeAnalyzer interface
    while using the new unified Claude service internally.
    """
    
    def __init__(self, db_path: str = None):
        """Initialize adapter with optional legacy database path."""
        self.db_path = db_path or Path.home() / ".marker_claude" / "table_merge.db"
        self.claude = unified_claude_service
        
        # Keep legacy database for status tracking during migration
        self._init_legacy_database()
        
        logger.info("Initialized ClaudeTableMergeAdapter with unified service")
    
    def _init_legacy_database(self):
        """Initialize legacy database for backwards compatibility."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(str(self.db_path))
        conn.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                config TEXT NOT NULL,
                result TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
    
    def analyze_tables_async(self, config: Dict[str, Any]) -> str:
        """
        Analyze tables asynchronously - maintains original interface.
        
        Args:
            config: Analysis configuration dict
            
        Returns:
            task_id: String UUID for tracking the task
        """
        task_id = str(uuid.uuid4())
        
        # Store in legacy database for compatibility
        conn = sqlite3.connect(str(self.db_path))
        conn.execute(
            "INSERT INTO tasks (task_id, status, config, result) VALUES (?, ?, ?, ?)",
            (task_id, TaskStatus.PENDING.value, json.dumps(config), None)
        )
        conn.commit()
        conn.close()
        
        # Start async processing in background
        asyncio.create_task(self._process_task(task_id, config))
        
        return task_id
    
    async def _process_task(self, task_id: str, config: Dict[str, Any]):
        """Process task using unified Claude service."""
        try:
            # Update status to processing
            self._update_task_status(task_id, TaskStatus.PROCESSING)
            
            # Convert config to new format
            table1_data = config.get("table1", {})
            table2_data = config.get("table2", {})
            context = {
                "confidence_threshold": config.get("confidence_threshold", 0.7),
                "document_type": config.get("document_type", "unknown"),
                "page_numbers": config.get("page_numbers", [])
            }
            
            # Use unified service
            result = await self.claude.analyze_tables(
                table1_data=table1_data,
                table2_data=table2_data,
                context=context
            )
            
            # Store result and update status
            conn = sqlite3.connect(str(self.db_path))
            conn.execute(
                "UPDATE tasks SET status = ?, result = ?, updated_at = ? WHERE task_id = ?",
                (TaskStatus.COMPLETED.value, json.dumps(result), datetime.now(), task_id)
            )
            conn.commit()
            conn.close()
            
            logger.info(f"Task {task_id} completed successfully")
            
        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            self._update_task_status(task_id, TaskStatus.FAILED, str(e))
    
    def _update_task_status(self, task_id: str, status: TaskStatus, error: str = None):
        """Update task status in legacy database."""
        conn = sqlite3.connect(str(self.db_path))
        
        if error:
            result = json.dumps({"error": error})
            conn.execute(
                "UPDATE tasks SET status = ?, result = ?, updated_at = ? WHERE task_id = ?",
                (status.value, result, datetime.now(), task_id)
            )
        else:
            conn.execute(
                "UPDATE tasks SET status = ?, updated_at = ? WHERE task_id = ?",
                (status.value, datetime.now(), task_id)
            )
        
        conn.commit()
        conn.close()
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get task status - maintains original interface."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.execute(
            "SELECT status, result, created_at, updated_at FROM tasks WHERE task_id = ?",
            (task_id,)
        )
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return {"status": "not_found", "error": "Task not found"}
        
        status, result, created_at, updated_at = row
        
        response = {
            "task_id": task_id,
            "status": status,
            "created_at": created_at,
            "updated_at": updated_at
        }
        
        if result:
            response["result"] = json.loads(result)
        
        return response
    
    def wait_for_completion(self, task_id: str, timeout: float = 300) -> Dict[str, Any]:
        """Wait for task completion - synchronous wrapper."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self._wait_for_completion_async(task_id, timeout)
            )
        finally:
            loop.close()
    
    async def _wait_for_completion_async(self, task_id: str, timeout: float) -> Dict[str, Any]:
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
            
            await asyncio.sleep(0.5)
    
    # Direct compatibility methods for drop-in replacement
    def analyze_and_wait(self, config: Dict[str, Any], timeout: float = 60) -> Dict[str, Any]:
        """Analyze tables and wait for result - convenience method."""
        task_id = self.analyze_tables_async(config)
        return self.wait_for_completion(task_id, timeout)
    
    def get_all_tasks(self, status: Optional[TaskStatus] = None) -> List[Dict[str, Any]]:
        """Get all tasks, optionally filtered by status."""
        conn = sqlite3.connect(str(self.db_path))
        
        if status:
            cursor = conn.execute(
                "SELECT task_id, status, created_at, updated_at FROM tasks WHERE status = ? ORDER BY created_at DESC",
                (status.value,)
            )
        else:
            cursor = conn.execute(
                "SELECT task_id, status, created_at, updated_at FROM tasks ORDER BY created_at DESC"
            )
        
        tasks = []
        for row in cursor:
            tasks.append({
                "task_id": row[0],
                "status": row[1],
                "created_at": row[2],
                "updated_at": row[3]
            })
        
        conn.close()
        return tasks
    
    def cleanup_old_tasks(self, days: int = 7):
        """Clean up tasks older than specified days."""
        conn = sqlite3.connect(str(self.db_path))
        conn.execute(
            "DELETE FROM tasks WHERE created_at < datetime('now', ?)",
            (f'-{days} days',)
        )
        deleted = conn.total_changes
        conn.commit()
        conn.close()
        
        logger.info(f"Cleaned up {deleted} old tasks")
        return deleted


# Drop-in replacement class name
ClaudeTableMergeAnalyzer = ClaudeTableMergeAdapter


# Validation and testing
if __name__ == "__main__":
    def test_adapter():
        """Test the adapter functionality."""
        adapter = ClaudeTableMergeAdapter()
        
        # Test async analysis
        config = {
            "table1": {
                "cells": [["Header1", "Header2"], ["Data1", "Data2"]],
                "bbox": [0, 0, 100, 50]
            },
            "table2": {
                "cells": [["Data3", "Data4"], ["Data5", "Data6"]],
                "bbox": [0, 60, 100, 110]
            },
            "confidence_threshold": 0.8,
            "document_type": "pdf"
        }
        
        print("Starting table analysis...")
        task_id = adapter.analyze_tables_async(config)
        print(f"Task ID: {task_id}")
        
        # Check status
        status = adapter.get_task_status(task_id)
        print(f"Initial status: {status}")
        
        # Wait for completion
        print("Waiting for completion...")
        result = adapter.wait_for_completion(task_id, timeout=30)
        print(f"Final result: {json.dumps(result, indent=2)}")
        
        # Test convenience method
        print("\nTesting analyze_and_wait...")
        direct_result = adapter.analyze_and_wait(config, timeout=30)
        print(f"Direct result: {json.dumps(direct_result, indent=2)}")
        
        # List all tasks
        print("\nAll tasks:")
        all_tasks = adapter.get_all_tasks()
        for task in all_tasks[:5]:  # Show first 5
            print(f"  - {task['task_id']}: {task['status']}")
        
        # Cleanup test
        print("\nCleaning up old tasks...")
        cleaned = adapter.cleanup_old_tasks(days=0)  # Clean all for testing
        print(f"Cleaned up {cleaned} tasks")
        
        print("\n✅ Adapter tests completed!")
    
    test_adapter()