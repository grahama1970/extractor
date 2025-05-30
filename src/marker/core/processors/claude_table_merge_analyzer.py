"""
Enhanced Table Merge Analyzer using Background Claude Code Instances

Based on patterns from claude_max_proxy for robust Claude instance management.
Analyzes table structure, content, and context to make intelligent merge decisions.
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
from typing import Dict, List, Optional, Tuple, Any
import threading
from dataclasses import dataclass
from loguru import logger
import time
import os

class TaskStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class AnalysisConfig:
    """Configuration for table merge analysis."""
    table1_data: Dict[str, Any]
    table2_data: Dict[str, Any]
    context: Optional[Dict[str, Any]] = None
    timeout: int = 120
    confidence_threshold: float = 0.7
    model: str = "claude-3-5-sonnet-20241022"
    max_retries: int = 3

@dataclass
class AnalysisResult:
    """Result of table merge analysis."""
    task_id: str
    should_merge: bool
    confidence: float
    reasoning: str
    merge_type: Optional[str] = None
    concerns: List[str] = None
    benefits: List[str] = None
    analysis_factors: Optional[Dict[str, Any]] = None
    evidence: Optional[Dict[str, Any]] = None
    recommendation_strength: Optional[str] = None
    status: TaskStatus = TaskStatus.COMPLETED
    error: Optional[str] = None

class BackgroundTableAnalyzer:
    """
    Background Claude Code instance manager for table merge analysis.
    Uses patterns from claude_max_proxy for robust execution.
    """
    
    def __init__(self, workspace_dir: Optional[Path] = None, db_path: Optional[Path] = None):
        self.workspace_dir = workspace_dir or Path(tempfile.mkdtemp(prefix="table_analyzer_"))
        self.db_path = db_path or self.workspace_dir / "analysis_tasks.db"
        self.executor = None
        self._init_database()
        
    def _init_database(self):
        """Initialize SQLite database for task persistence."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS analysis_tasks (
                    id TEXT PRIMARY KEY,
                    config TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
    
    async def analyze_table_merge(self, config: AnalysisConfig) -> str:
        """
        Submit table merge analysis task for background processing.
        Returns task ID immediately for polling.
        """
        task_id = str(uuid.uuid4())
        
        # Store task in database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO analysis_tasks (id, config, status) VALUES (?, ?, ?)",
                (task_id, json.dumps(config.__dict__, default=str), TaskStatus.PENDING.value)
            )
            conn.commit()
        
        # Schedule background execution
        if self.executor is None:
            self.executor = asyncio.create_task(self._process_tasks())
        
        return task_id
    
    async def get_analysis_result(self, task_id: str) -> Optional[AnalysisResult]:
        """Get analysis result by task ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT config, status, result FROM analysis_tasks WHERE id = ?",
                (task_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                return None
            
            config_data, status, result_data = row
            status_enum = TaskStatus(status)
            
            if status_enum == TaskStatus.COMPLETED and result_data:
                result_dict = json.loads(result_data)
                return AnalysisResult(
                    task_id=task_id,
                    status=status_enum,
                    **result_dict
                )
            elif status_enum == TaskStatus.FAILED and result_data:
                error_dict = json.loads(result_data)
                return AnalysisResult(
                    task_id=task_id,
                    status=status_enum,
                    should_merge=False,
                    confidence=0.0,
                    reasoning="Analysis failed",
                    error=error_dict.get("error", "Unknown error")
                )
            else:
                return AnalysisResult(
                    task_id=task_id,
                    status=status_enum,
                    should_merge=False,
                    confidence=0.0,
                    reasoning="Analysis in progress"
                )
    
    async def _process_tasks(self):
        """Background task processor using claude_max_proxy patterns."""
        while True:
            try:
                # Get pending tasks
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.execute(
                        "SELECT id, config FROM analysis_tasks WHERE status = ? ORDER BY created_at",
                        (TaskStatus.PENDING.value,)
                    )
                    tasks = cursor.fetchall()
                
                for task_id, config_json in tasks:
                    try:
                        # Mark as processing
                        self._update_task_status(task_id, TaskStatus.PROCESSING)
                        
                        # Parse config
                        config_dict = json.loads(config_json)
                        config = AnalysisConfig(**config_dict)
                        
                        # Execute analysis
                        result = await self._execute_claude_analysis(config)
                        
                        # Store result
                        with sqlite3.connect(self.db_path) as conn:
                            conn.execute(
                                "UPDATE analysis_tasks SET status = ?, result = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                                (TaskStatus.COMPLETED.value, json.dumps(result), task_id)
                            )
                            conn.commit()
                            
                        logger.info(f"Completed analysis task {task_id}")
                        
                    except Exception as e:
                        logger.error(f"Failed to process task {task_id}: {e}")
                        error_result = {"error": str(e)}
                        with sqlite3.connect(self.db_path) as conn:
                            conn.execute(
                                "UPDATE analysis_tasks SET status = ?, result = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
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
                "UPDATE analysis_tasks SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status.value, task_id)
            )
            conn.commit()
    
    async def _execute_claude_analysis(self, config: AnalysisConfig) -> Dict[str, Any]:
        """
        Execute Claude analysis using claude_max_proxy patterns.
        Returns structured analysis result.
        """
        
        # Create analysis prompt
        prompt = self._create_detailed_analysis_prompt(config)
        
        # Write prompt to temporary file
        prompt_file = self.workspace_dir / f"analysis_prompt_{uuid.uuid4().hex[:8]}.md"
        prompt_file.write_text(prompt)
        
        try:
            # Execute Claude as a background instance with non-interactive output
            # Use the prompt file to avoid shell escaping issues
            cmd_str = f'''cd {self.workspace_dir} && timeout {config.timeout}s claude \
                --print \
                --output-format json \
                --model {config.model} \
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
                # Claude CLI returns the response in 'result' field
                full_response = response_data.get("result", response_data.get("content", ""))
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSON response, using raw output")
                # Sometimes Claude returns the JSON directly without wrapper
                full_response = stdout
            
            # Parse the structured response
            return self._parse_analysis_response(full_response)
            
        finally:
            # Cleanup
            if prompt_file.exists():
                prompt_file.unlink()
    
    def _create_detailed_analysis_prompt(self, config: AnalysisConfig) -> str:
        """Create comprehensive analysis prompt with all factors."""
        
        prompt = f"""# Advanced Table Merge Analysis

Analyze these two contiguous tables to determine if they should be merged. Consider multiple factors including structure, content, semantics, and context.

## Table 1 Analysis Data

### Structure & Content:
"""
        
        table1 = config.table1_data
        table2 = config.table2_data
        
        # Add detailed table 1 information
        if 'csv' in table1 and table1['csv']:
            prompt += f"**CSV Data:**\n```csv\n{table1['csv']}\n```\n\n"
        
        if 'json_data' in table1 and table1['json_data']:
            prompt += f"**Structured Data:**\n```json\n{json.dumps(table1['json_data'], indent=2)}\n```\n\n"
        
        if 'text' in table1:
            prompt += f"**Raw Text:** {table1['text']}\n\n"
        
        if 'metadata' in table1 and table1['metadata']:
            prompt += f"**Extraction Metadata:** {json.dumps(table1['metadata'], indent=2)}\n\n"
        
        prompt += """## Table 2 Analysis Data

### Structure & Content:
"""
        
        # Add detailed table 2 information
        if 'csv' in table2 and table2['csv']:
            prompt += f"**CSV Data:**\n```csv\n{table2['csv']}\n```\n\n"
        
        if 'json_data' in table2 and table2['json_data']:
            prompt += f"**Structured Data:**\n```json\n{json.dumps(table2['json_data'], indent=2)}\n```\n\n"
        
        if 'text' in table2:
            prompt += f"**Raw Text:** {table2['text']}\n\n"
        
        if 'metadata' in table2 and table2['metadata']:
            prompt += f"**Extraction Metadata:** {json.dumps(table2['metadata'], indent=2)}\n\n"
        
        # Add context
        if config.context:
            prompt += f"## Document Context\n{json.dumps(config.context, indent=2)}\n\n"
        
        prompt += f"""## Analysis Framework

Evaluate these specific factors and provide scores (0.0-1.0) for each:

### 1. Structural Compatibility (0.0-1.0)
- **Column Count Alignment**: Do they have similar number of columns?
- **Column Header Consistency**: Do headers match or complement each other?
- **Data Type Consistency**: Are column data types compatible?
- **Whitespace Patterns**: Are spacing and formatting similar?

### 2. Content Continuity (0.0-1.0)  
- **Data Flow Logic**: Does Table 2 continue the logical sequence from Table 1?
- **Header Repetition**: Does Table 2 repeat headers (indicating continuation) or have new headers?
- **Value Ranges**: Do numeric/date ranges flow logically between tables?
- **Row Count Ratio**: Are row counts reasonable for a single logical table?

### 3. Semantic Relationship (0.0-1.0)
- **Topic Coherence**: Do tables address the same topic/entity?
- **Categorical Alignment**: Do categorical values follow the same scheme?
- **Reference Consistency**: Do ID fields, references maintain consistency?
- **Business Logic**: Do the tables make sense as a unified dataset?

### 4. Layout & Positioning (0.0-1.0)
- **Physical Proximity**: How close are the tables on the page/document?
- **Page Boundaries**: Are they split across pages naturally?
- **Visual Separation**: Is there clear visual separation or natural flow?
- **Document Structure**: Do they appear in logical document sequence?

### 5. Quality & Extraction (0.0-1.0)
- **Extraction Quality**: Were both tables extracted cleanly?
- **OCR Consistency**: If OCR was used, is quality consistent?
- **Missing Data Patterns**: Are null/missing values consistent?
- **Formatting Preservation**: Is original formatting maintained?

## Required Response Format

Provide your analysis in this EXACT JSON format:

```json
{{
    "should_merge": true/false,
    "confidence": 0.85,
    "merge_type": "vertical/horizontal/none",
    "analysis_factors": {{
        "structural_compatibility": 0.90,
        "content_continuity": 0.75,
        "semantic_relationship": 0.80,
        "layout_positioning": 0.70,
        "quality_extraction": 0.95,
        "overall_score": 0.82
    }},
    "reasoning": "Detailed explanation with specific evidence from both tables",
    "concerns": ["Specific concerns about merging"],
    "benefits": ["Specific benefits of merging"],
    "evidence": {{
        "column_structure": "Analysis of column compatibility",
        "data_patterns": "Analysis of data flow and patterns", 
        "content_analysis": "Semantic and topical analysis"
    }},
    "recommendation_strength": "high/medium/low"
}}
```

## Analysis Guidelines

**Conservative Approach**: Only recommend merging if confidence is >= {config.confidence_threshold}. False negatives (keeping separate tables) are generally better than false positives (incorrectly merging).

**Evidence Required**: Base your decision on concrete evidence from the table data, not assumptions.

**Factor Weighting**: 
- Structural compatibility: 25%
- Content continuity: 30% 
- Semantic relationship: 25%
- Layout positioning: 10%
- Quality extraction: 10%

Please provide a thorough analysis following this framework.
"""
        
        return prompt
    
    def _parse_analysis_response(self, response: str) -> Dict[str, Any]:
        """Parse Claude's detailed analysis response."""
        try:
            # First try to parse as direct JSON
            try:
                parsed = json.loads(response.strip())
                # If it's valid JSON, use it directly
                result = {
                    "should_merge": bool(parsed.get("should_merge", False)),
                    "confidence": float(parsed.get("confidence", 0.0)),
                    "reasoning": parsed.get("reasoning", "No reasoning provided"),
                    "merge_type": parsed.get("merge_type", "none"),
                    "concerns": parsed.get("concerns", []),
                    "benefits": parsed.get("benefits", []),
                    "analysis_factors": parsed.get("analysis_factors", {}),
                }
                
                # Add optional fields
                if "evidence" in parsed:
                    result["evidence"] = parsed["evidence"]
                if "recommendation_strength" in parsed:
                    result["recommendation_strength"] = parsed["recommendation_strength"]
                    
                logger.debug(f"Successfully parsed direct JSON response")
                return result
                
            except json.JSONDecodeError:
                # If not direct JSON, try to extract from markdown
                import re
                json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
                
                if json_match:
                    json_str = json_match.group(1)
                    parsed = json.loads(json_str)
                    
                    # Validate required fields
                    result = {
                        "should_merge": bool(parsed.get("should_merge", False)),
                        "confidence": float(parsed.get("confidence", 0.0)),
                        "reasoning": parsed.get("reasoning", "No reasoning provided"),
                        "merge_type": parsed.get("merge_type", "none"),
                        "concerns": parsed.get("concerns", []),
                        "benefits": parsed.get("benefits", []),
                        "analysis_factors": parsed.get("analysis_factors", {}),
                    }
                    
                    # Add optional fields
                    if "evidence" in parsed:
                        result["evidence"] = parsed["evidence"]
                    if "recommendation_strength" in parsed:
                        result["recommendation_strength"] = parsed["recommendation_strength"]
                    
                    logger.debug(f"Successfully parsed JSON from markdown block")
                    return result
                else:
                    # Fallback parsing
                    logger.warning("Could not parse Claude response as JSON")
                    return {
                        "should_merge": False,
                        "confidence": 0.0,
                        "reasoning": f"Failed to parse response: {response[:500]}...",
                        "merge_type": "none",
                        "concerns": ["Parse error"],
                        "benefits": [],
                        "analysis_factors": {}
                    }
                
        except Exception as e:
            logger.error(f"Failed to parse Claude analysis response: {e}")
            return {
                "should_merge": False,
                "confidence": 0.0,
                "reasoning": f"Parse error: {e}",
                "merge_type": "none", 
                "concerns": ["Response parsing failed"],
                "benefits": [],
                "analysis_factors": {}
            }

# High-level interface for integration
class TableMergeDecisionEngine:
    """
    High-level interface for table merge decisions using background Claude analysis.
    """
    
    def __init__(self, workspace_dir: Optional[Path] = None):
        self.analyzer = BackgroundTableAnalyzer(workspace_dir)
        self.pending_tasks = {}
    
    async def submit_merge_analysis(self, 
                                   table1_data: Dict[str, Any],
                                   table2_data: Dict[str, Any], 
                                   context: Optional[Dict[str, Any]] = None,
                                   confidence_threshold: float = 0.75) -> str:
        """Submit table pair for merge analysis."""
        
        config = AnalysisConfig(
            table1_data=table1_data,
            table2_data=table2_data,
            context=context,
            confidence_threshold=confidence_threshold
        )
        
        task_id = await self.analyzer.analyze_table_merge(config)
        self.pending_tasks[task_id] = {
            "submitted_at": time.time(),
            "config": config
        }
        
        return task_id
    
    async def get_merge_decision(self, task_id: str, timeout: float = 300.0) -> Optional[AnalysisResult]:
        """Get merge decision, waiting up to timeout seconds."""
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            result = await self.analyzer.get_analysis_result(task_id)
            
            if result and result.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                # Clean up tracking
                self.pending_tasks.pop(task_id, None)
                return result
            
            await asyncio.sleep(2)
        
        logger.warning(f"Analysis task {task_id} timed out after {timeout}s")
        return None
    
    async def analyze_table_sequence_parallel(self, 
                                            tables_data: List[Dict[str, Any]], 
                                            context: Optional[Dict[str, Any]] = None) -> List[List[int]]:
        """
        Analyze a sequence of tables for merge opportunities using parallel Claude instances.
        Returns groups of table indices that should be merged together.
        """
        
        if len(tables_data) < 2:
            return [[i] for i in range(len(tables_data))]
        
        # Submit all adjacent pairs for analysis
        analysis_tasks = []
        for i in range(len(tables_data) - 1):
            task_id = await self.submit_merge_analysis(
                tables_data[i], 
                tables_data[i + 1], 
                context
            )
            analysis_tasks.append((i, i + 1, task_id))
        
        # Wait for all results
        merge_decisions = []
        for i, j, task_id in analysis_tasks:
            result = await self.get_merge_decision(task_id)
            if result:
                merge_decisions.append((i, j, result.should_merge, result.confidence))
                logger.info(f"Tables {i}-{j}: merge={result.should_merge}, confidence={result.confidence:.2f}")
            else:
                merge_decisions.append((i, j, False, 0.0))
                logger.warning(f"Tables {i}-{j}: analysis failed")
        
        # Build merge groups based on decisions
        merge_groups = []
        current_group = [0]
        
        for i, j, should_merge, confidence in merge_decisions:
            if should_merge and confidence >= 0.7:
                if j not in current_group:
                    current_group.append(j)
            else:
                if len(current_group) > 0:
                    merge_groups.append(current_group)
                current_group = [j]
        
        # Add final group
        if current_group:
            merge_groups.append(current_group)
        
        return merge_groups
    
    # Synchronous wrappers for non-async contexts
    def submit_merge_analysis_sync(self, 
                                  table1_data: Dict[str, Any],
                                  table2_data: Dict[str, Any], 
                                  context: Optional[Dict[str, Any]] = None,
                                  confidence_threshold: float = 0.75) -> str:
        """Synchronous wrapper for submit_merge_analysis."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self.submit_merge_analysis(table1_data, table2_data, context, confidence_threshold)
            )
        finally:
            loop.close()
    
    def get_merge_decision_sync(self, task_id: str, timeout: float = 300.0) -> Optional[AnalysisResult]:
        """Synchronous wrapper for get_merge_decision."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self.get_merge_decision(task_id, timeout)
            )
        finally:
            loop.close()

# Example usage and testing
async def test_table_merge_analyzer():
    """Test the table merge analyzer with sample data."""
    
    engine = TableMergeDecisionEngine()
    
    # Sample table data
    table1_data = {
        'csv': '''Name,Age,Department
John,25,Engineering
Jane,30,Marketing
Bob,35,Sales''',
        'text': 'Employee information table',
        'metadata': {
            'extraction_method': 'surya',
            'page_id': 1,
            'quality_score': 0.95
        }
    }
    
    table2_data = {
        'csv': '''Name,Age,Department  
Alice,28,Engineering
Carol,32,Marketing
Dave,29,Sales''',
        'text': 'Additional employee data',
        'metadata': {
            'extraction_method': 'surya', 
            'page_id': 1,
            'quality_score': 0.92
        }
    }
    
    context = {
        'document_type': 'hr_report',
        'surrounding_text': 'Employee roster continued from previous table...',
        'page_position': 'middle'
    }
    
    # Submit analysis
    task_id = await engine.submit_merge_analysis(table1_data, table2_data, context)
    print(f"Submitted analysis task: {task_id}")
    
    # Get result
    result = await engine.get_merge_decision(task_id)
    if result:
        print(f"Merge decision: {result.should_merge}")
        print(f"Confidence: {result.confidence:.2f}")
        print(f"Reasoning: {result.reasoning}")
        if result.analysis_factors:
            print(f"Analysis factors: {result.analysis_factors}")
    else:
        print("Analysis failed or timed out")

if __name__ == "__main__":
    asyncio.run(test_table_merge_analyzer())