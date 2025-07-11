"""
Background Content Validator using Claude Code Instances
Module: claude_content_validator.py
Description: Implementation of claude content validator functionality

Validates overall document structure and content quality using Claude.
Checks for completeness, coherence, and structural integrity.
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

class TaskStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class ContentIssueType(Enum):
    INCOMPLETE_CONTENT = "incomplete_content"
    INCONSISTENT_FORMATTING = "inconsistent_formatting"
    MISSING_REFERENCES = "missing_references"
    BROKEN_LINKS = "broken_links"
    DUPLICATE_CONTENT = "duplicate_content"
    QUALITY_ISSUES = "quality_issues"
    STRUCTURAL_GAPS = "structural_gaps"

@dataclass
class ContentData:
    """Data for document content validation."""
    text_content: str
    section_count: int
    table_count: int
    figure_count: int
    equation_count: int
    code_block_count: int
    page_count: int
    metadata: Optional[Dict[str, Any]] = None
    sample_sections: Optional[List[Dict[str, str]]] = None  # Sample of sections for analysis

@dataclass
class ValidationConfig:
    """Configuration for content validation."""
    content_data: ContentData
    document_type: Optional[str] = None
    validation_criteria: Optional[List[str]] = None
    include_quality_analysis: bool = True
    page_images: Optional[List[Path]] = None
    timeout: int = 180
    confidence_threshold: float = 0.8
    model: str = "claude-3-5-sonnet-20241022"
    max_retries: int = 3

@dataclass
class ContentIssue:
    """Identified issue with document content."""
    issue_type: ContentIssueType
    severity: str  # high, medium, low
    location: Optional[str]  # Page/section where issue found
    description: str
    suggestion: str
    confidence: float
    evidence: Optional[Dict[str, Any]] = None

@dataclass
class ValidationResult:
    """Result of content validation."""
    task_id: str
    is_valid: bool
    confidence: float
    issues: List[ContentIssue]
    quality_score: float = 0.0
    completeness_score: float = 0.0
    coherence_score: float = 0.0
    formatting_score: float = 0.0
    analysis_summary: str = ""
    recommendations: List[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.COMPLETED
    error: Optional[str] = None

class BackgroundContentValidator:
    """
    Background Claude Code instance manager for content validation.
    Uses patterns from BackgroundTableAnalyzer for robust execution.
    """
    
    def __init__(self, workspace_dir: Optional[Path] = None, db_path: Optional[Path] = None):
        self.workspace_dir = workspace_dir or Path(tempfile.mkdtemp(prefix="content_validator_"))
        self.db_path = db_path or self.workspace_dir / "validation_tasks.db"
        self.executor = None
        self._init_database()
        
    def _init_database(self):
        """Initialize SQLite database for task persistence."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS validation_tasks (
                    id TEXT PRIMARY KEY,
                    config TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
    
    async def validate_content(self, config: ValidationConfig) -> str:
        """
        Submit content validation task for background processing.
        Returns task ID immediately for polling.
        """
        task_id = str(uuid.uuid4())
        
        # Convert config to JSON-serializable format
        config_dict = {
            'content_data': {
                'text_content': config.content_data.text_content[:10000],  # Limit size
                'section_count': config.content_data.section_count,
                'table_count': config.content_data.table_count,
                'figure_count': config.content_data.figure_count,
                'equation_count': config.content_data.equation_count,
                'code_block_count': config.content_data.code_block_count,
                'page_count': config.content_data.page_count,
                'metadata': config.content_data.metadata,
                'sample_sections': config.content_data.sample_sections
            },
            'document_type': config.document_type,
            'validation_criteria': config.validation_criteria,
            'include_quality_analysis': config.include_quality_analysis,
            'page_images': [str(p) for p in config.page_images] if config.page_images else None,
            'timeout': config.timeout,
            'confidence_threshold': config.confidence_threshold,
            'model': config.model,
            'max_retries': config.max_retries
        }
        
        # Store task in database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO validation_tasks (id, config, status) VALUES (?, ?, ?)",
                (task_id, json.dumps(config_dict), TaskStatus.PENDING.value)
            )
            conn.commit()
        
        # Schedule background execution
        if self.executor is None:
            self.executor = asyncio.create_task(self._process_tasks())
        
        return task_id
    
    async def get_validation_result(self, task_id: str) -> Optional[ValidationResult]:
        """Get validation result by task ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT config, status, result FROM validation_tasks WHERE id = ?",
                (task_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                return None
            
            config_data, status, result_data = row
            status_enum = TaskStatus(status)
            
            if status_enum == TaskStatus.COMPLETED and result_data:
                result_dict = json.loads(result_data)
                
                # Convert issues back to ContentIssue objects
                issues = []
                for issue_dict in result_dict.get('issues', []):
                    issue = ContentIssue(
                        issue_type=ContentIssueType(issue_dict['issue_type']),
                        severity=issue_dict['severity'],
                        location=issue_dict.get('location'),
                        description=issue_dict['description'],
                        suggestion=issue_dict['suggestion'],
                        confidence=issue_dict['confidence'],
                        evidence=issue_dict.get('evidence')
                    )
                    issues.append(issue)
                
                return ValidationResult(
                    task_id=task_id,
                    status=status_enum,
                    is_valid=result_dict['is_valid'],
                    confidence=result_dict['confidence'],
                    issues=issues,
                    quality_score=result_dict.get('quality_score', 0.0),
                    completeness_score=result_dict.get('completeness_score', 0.0),
                    coherence_score=result_dict.get('coherence_score', 0.0),
                    formatting_score=result_dict.get('formatting_score', 0.0),
                    analysis_summary=result_dict.get('analysis_summary', ''),
                    recommendations=result_dict.get('recommendations', [])
                )
            elif status_enum == TaskStatus.FAILED and result_data:
                error_dict = json.loads(result_data)
                return ValidationResult(
                    task_id=task_id,
                    status=status_enum,
                    is_valid=False,
                    confidence=0.0,
                    issues=[],
                    error=error_dict.get("error", "Unknown error")
                )
            else:
                return ValidationResult(
                    task_id=task_id,
                    status=status_enum,
                    is_valid=False,
                    confidence=0.0,
                    issues=[],
                    analysis_summary="Validation in progress"
                )
    
    async def _process_tasks(self):
        """Background task processor."""
        while True:
            try:
                # Get pending tasks
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.execute(
                        "SELECT id, config FROM validation_tasks WHERE status = ? ORDER BY created_at",
                        (TaskStatus.PENDING.value,)
                    )
                    tasks = cursor.fetchall()
                
                for task_id, config_json in tasks:
                    try:
                        # Mark as processing
                        self._update_task_status(task_id, TaskStatus.PROCESSING)
                        
                        # Parse config
                        config_dict = json.loads(config_json)
                        
                        # Execute validation
                        result = await self._execute_claude_validation(config_dict)
                        
                        # Store result
                        with sqlite3.connect(self.db_path) as conn:
                            conn.execute(
                                "UPDATE validation_tasks SET status = ?, result = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                                (TaskStatus.COMPLETED.value, json.dumps(result), task_id)
                            )
                            conn.commit()
                            
                        logger.info(f"Completed validation task {task_id}")
                        
                    except Exception as e:
                        logger.error(f"Failed to process task {task_id}: {e}")
                        error_result = {"error": str(e)}
                        with sqlite3.connect(self.db_path) as conn:
                            conn.execute(
                                "UPDATE validation_tasks SET status = ?, result = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
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
                "UPDATE validation_tasks SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status.value, task_id)
            )
            conn.commit()
    
    async def _execute_claude_validation(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute Claude validation using background instance.
        Returns structured validation result.
        """
        
        # Create validation prompt
        prompt = self._create_validation_prompt(config)
        
        # Write prompt to temporary file
        prompt_file = self.workspace_dir / f"validation_prompt_{uuid.uuid4().hex[:8]}.md"
        prompt_file.write_text(prompt)
        
        # Handle page images if provided
        image_args = ""
        if config.get('include_quality_analysis') and config.get('page_images'):
            # Copy images to workspace for Claude to access
            image_paths = []
            for img_path in config['page_images'][:3]:  # Limit to first 3 pages for sampling
                if Path(img_path).exists():
                    dest_path = self.workspace_dir / Path(img_path).name
                    subprocess.run(['cp', str(img_path), str(dest_path)], check=True)
                    image_paths.append(dest_path.name)
            
            if image_paths:
                image_args = " ".join([f"--image {img}" for img in image_paths])
        
        try:
            # Execute Claude with multimodal analysis if images provided
            cmd_str = f'''cd {self.workspace_dir} && timeout {config['timeout']}s claude \
                --print \
                --output-format json \
                --model {config['model']} \
                {image_args} \
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
            return self._parse_validation_response(full_response)
            
        finally:
            # Cleanup
            if prompt_file.exists():
                prompt_file.unlink()
            
            # Clean up copied images
            if config.get('page_images'):
                for img_file in self.workspace_dir.glob("*.png"):
                    img_file.unlink()
                for img_file in self.workspace_dir.glob("*.jpg"):
                    img_file.unlink()
    
    def _create_validation_prompt(self, config: Dict[str, Any]) -> str:
        """Create comprehensive validation prompt."""
        
        content_data = config['content_data']
        
        prompt = f"""# Document Content Validation Analysis

Analyze this document's content for completeness, quality, and structural integrity.

## Document Overview
- Type: {config.get('document_type', 'Unknown')}
- Pages: {content_data['page_count']}
- Sections: {content_data['section_count']}
- Tables: {content_data['table_count']}
- Figures: {content_data['figure_count']}
- Equations: {content_data['equation_count']}
- Code Blocks: {content_data['code_block_count']}

## Content Sample
{content_data['text_content']}

"""
        
        # Add sample sections if provided
        if content_data.get('sample_sections'):
            prompt += "## Sample Sections for Analysis\n\n"
            for i, section in enumerate(content_data['sample_sections'][:5], 1):
                prompt += f"### Section {i}: {section.get('title', 'Untitled')}\n"
                prompt += f"{section.get('content', '')[:500]}...\n\n"
        
        # Add metadata if available
        if content_data.get('metadata'):
            prompt += f"## Document Metadata\n{json.dumps(content_data['metadata'], indent=2)}\n\n"
        
        # Add validation criteria
        if config.get('validation_criteria'):
            prompt += "## Custom Validation Criteria\n"
            for criterion in config['validation_criteria']:
                prompt += f"- {criterion}\n"
            prompt += "\n"
        
        prompt += f"""
## Validation Framework

Evaluate these aspects of the document:

### 1. Content Completeness (Score: 0.0-1.0)
- **Section Coverage**: Are all expected sections present?
- **Content Depth**: Is each section sufficiently detailed?
- **Missing Elements**: Are there gaps in the content?
- **Reference Integrity**: Are all referenced items present?

### 2. Content Quality (Score: 0.0-1.0)
- **Clarity**: Is the content clear and understandable?
- **Accuracy**: Does the content appear accurate and consistent?
- **Relevance**: Is all content relevant to the document purpose?
- **Professional Level**: Does it meet professional standards?

### 3. Structural Coherence (Score: 0.0-1.0)
- **Logical Flow**: Does content flow logically between sections?
- **Consistency**: Are formatting and style consistent?
- **Cross-references**: Do internal references work correctly?
- **Organization**: Is the document well-organized?

### 4. Formatting Consistency (Score: 0.0-1.0)
- **Style Uniformity**: Are headings, lists, etc. formatted consistently?
- **Table/Figure Formatting**: Are visual elements consistent?
- **Citation Style**: Are citations/references formatted consistently?
- **Layout Quality**: Is the overall layout professional?

## Issue Detection

Identify these specific issue types:
1. **Incomplete Content**: Missing sections, partial information
2. **Inconsistent Formatting**: Style variations, formatting errors
3. **Missing References**: Broken cross-references, missing citations
4. **Broken Links**: Invalid internal/external references
5. **Duplicate Content**: Repeated sections or information
6. **Quality Issues**: Poor writing, unclear explanations
7. **Structural Gaps**: Missing connections between sections

## Required Response Format

Provide your analysis in this EXACT JSON format:

```json
{{
    "is_valid": true/false,
    "confidence": 0.85,
    "quality_score": 0.90,
    "completeness_score": 0.85,
    "coherence_score": 0.80,
    "formatting_score": 0.75,
    "analysis_summary": "Overall assessment of document content quality",
    "issues": [
        {{
            "issue_type": "incomplete_content/inconsistent_formatting/missing_references/broken_links/duplicate_content/quality_issues/structural_gaps",
            "severity": "high/medium/low",
            "location": "Page X, Section Y",
            "description": "Detailed description of the issue",
            "suggestion": "Specific suggestion to fix the issue",
            "confidence": 0.90,
            "evidence": {{
                "examples": ["Example 1", "Example 2"],
                "impact": "How this affects document quality"
            }}
        }}
    ],
    "recommendations": [
        "High-level recommendation 1",
        "High-level recommendation 2"
    ]
}}
```

## Analysis Guidelines

**Confidence Threshold**: Only mark as valid if confidence >= {config.get('confidence_threshold', 0.8)}

**Quality Standards**:
- Professional documents should score >= 0.8 on all metrics
- Academic papers need high completeness and coherence scores
- Technical documents require accuracy and clarity

**Evidence-Based**: All issues must have concrete evidence from the document

Please provide a thorough content quality analysis following this framework.
"""
        
        return prompt
    
    def _parse_validation_response(self, response: str) -> Dict[str, Any]:
        """Parse Claude's validation response."""
        try:
            # First try to parse as direct JSON
            try:
                parsed = json.loads(response.strip())
                
                # Convert issue_type strings to enum values for validation
                issues = []
                for issue in parsed.get('issues', []):
                    issue_dict = {
                        'issue_type': issue.get('issue_type', 'quality_issues'),
                        'severity': issue.get('severity', 'medium'),
                        'location': issue.get('location'),
                        'description': issue.get('description', ''),
                        'suggestion': issue.get('suggestion', ''),
                        'confidence': float(issue.get('confidence', 0.8)),
                        'evidence': issue.get('evidence')
                    }
                    issues.append(issue_dict)
                
                result = {
                    "is_valid": bool(parsed.get("is_valid", False)),
                    "confidence": float(parsed.get("confidence", 0.0)),
                    "issues": issues,
                    "quality_score": float(parsed.get("quality_score", 0.0)),
                    "completeness_score": float(parsed.get("completeness_score", 0.0)),
                    "coherence_score": float(parsed.get("coherence_score", 0.0)),
                    "formatting_score": float(parsed.get("formatting_score", 0.0)),
                    "analysis_summary": parsed.get("analysis_summary", ""),
                    "recommendations": parsed.get("recommendations", [])
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
                    
                    # Process as above
                    issues = []
                    for issue in parsed.get('issues', []):
                        issue_dict = {
                            'issue_type': issue.get('issue_type', 'quality_issues'),
                            'severity': issue.get('severity', 'medium'),
                            'location': issue.get('location'),
                            'description': issue.get('description', ''),
                            'suggestion': issue.get('suggestion', ''),
                            'confidence': float(issue.get('confidence', 0.8)),
                            'evidence': issue.get('evidence')
                        }
                        issues.append(issue_dict)
                    
                    result = {
                        "is_valid": bool(parsed.get("is_valid", False)),
                        "confidence": float(parsed.get("confidence", 0.0)),
                        "issues": issues,
                        "quality_score": float(parsed.get("quality_score", 0.0)),
                        "completeness_score": float(parsed.get("completeness_score", 0.0)),
                        "coherence_score": float(parsed.get("coherence_score", 0.0)),
                        "formatting_score": float(parsed.get("formatting_score", 0.0)),
                        "analysis_summary": parsed.get("analysis_summary", ""),
                        "recommendations": parsed.get("recommendations", [])
                    }
                    
                    logger.debug(f"Successfully parsed JSON from markdown block")
                    return result
                else:
                    # Fallback
                    logger.warning("Could not parse Claude response as JSON")
                    return {
                        "is_valid": False,
                        "confidence": 0.0,
                        "issues": [{
                            "issue_type": "quality_issues",
                            "severity": "high",
                            "location": None,
                            "description": "Failed to parse validation response",
                            "suggestion": "Manual review required",
                            "confidence": 0.0,
                            "evidence": None
                        }],
                        "quality_score": 0.0,
                        "completeness_score": 0.0,
                        "coherence_score": 0.0,
                        "formatting_score": 0.0,
                        "analysis_summary": f"Parse error: {response[:500]}...",
                        "recommendations": []
                    }
                
        except Exception as e:
            logger.error(f"Failed to parse Claude validation response: {e}")
            return {
                "is_valid": False,
                "confidence": 0.0,
                "issues": [{
                    "issue_type": "quality_issues",
                    "severity": "high",
                    "location": None,
                    "description": f"Parse error: {e}",
                    "suggestion": "Check response format",
                    "confidence": 0.0,
                    "evidence": None
                }],
                "quality_score": 0.0,
                "completeness_score": 0.0,
                "coherence_score": 0.0,
                "formatting_score": 0.0,
                "analysis_summary": f"Error: {e}",
                "recommendations": []
            }

# High-level interface for integration
class ContentValidationEngine:
    """
    High-level interface for content validation using background Claude analysis.
    """
    
    def __init__(self, workspace_dir: Optional[Path] = None):
        self.validator = BackgroundContentValidator(workspace_dir)
        self.pending_tasks = {}
    
    async def submit_validation(self, 
                               content_data: ContentData,
                               document_type: Optional[str] = None,
                               validation_criteria: Optional[List[str]] = None,
                               page_images: Optional[List[Path]] = None,
                               confidence_threshold: float = 0.8) -> str:
        """Submit document content for validation."""
        
        config = ValidationConfig(
            content_data=content_data,
            document_type=document_type,
            validation_criteria=validation_criteria,
            include_quality_analysis=bool(page_images),
            page_images=page_images,
            confidence_threshold=confidence_threshold
        )
        
        task_id = await self.validator.validate_content(config)
        self.pending_tasks[task_id] = {
            "submitted_at": time.time(),
            "config": config
        }
        
        return task_id
    
    async def get_validation_result(self, task_id: str, timeout: float = 300.0) -> Optional[ValidationResult]:
        """Get validation result, waiting up to timeout seconds."""
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            result = await self.validator.get_validation_result(task_id)
            
            if result and result.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                # Clean up tracking
                self.pending_tasks.pop(task_id, None)
                return result
            
            await asyncio.sleep(2)
        
        logger.warning(f"Validation task {task_id} timed out after {timeout}s")
        return None
    
    # Synchronous wrappers for non-async contexts
    def submit_validation_sync(self, 
                              content_data: ContentData,
                              document_type: Optional[str] = None,
                              validation_criteria: Optional[List[str]] = None,
                              page_images: Optional[List[Path]] = None,
                              confidence_threshold: float = 0.8) -> str:
        """Synchronous wrapper for submit_validation."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self.submit_validation(content_data, document_type, validation_criteria, page_images, confidence_threshold)
            )
        finally:
            loop.close()
    
    def get_validation_result_sync(self, task_id: str, timeout: float = 300.0) -> Optional[ValidationResult]:
        """Synchronous wrapper for get_validation_result."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self.get_validation_result(task_id, timeout)
            )
        finally:
            loop.close()

# Example usage and testing
async def test_content_validator():
    """Test the content validator with sample data."""
    
    engine = ContentValidationEngine()
    
    # Sample content data
    content_data = ContentData(
        text_content="""
# Introduction
This document provides an overview of our new product features.

## Background
Previous versions of the product had limited functionality...

## Features
### Feature 1: Enhanced Performance
We have improved performance by 50%...

### Feature 2: New User Interface
The new UI provides better user experience...

## Conclusion
In summary, these new features provide significant value...
        """,
        section_count=5,
        table_count=2,
        figure_count=3,
        equation_count=0,
        code_block_count=1,
        page_count=10,
        metadata={
            'author': 'John Doe',
            'date': '2024-01-01',
            'version': '1.0'
        },
        sample_sections=[
            {
                'title': 'Introduction',
                'content': 'This document provides an overview...'
            },
            {
                'title': 'Features',
                'content': 'We have added several new features...'
            }
        ]
    )
    
    validation_criteria = [
        "Document should have clear introduction and conclusion",
        "All features should be thoroughly documented",
        "Technical specifications should be included",
        "References should be properly cited"
    ]
    
    # Submit validation
    task_id = await engine.submit_validation(
        content_data=content_data,
        document_type="product_documentation",
        validation_criteria=validation_criteria
    )
    print(f"Submitted validation task: {task_id}")
    
    # Get result
    result = await engine.get_validation_result(task_id)
    if result:
        print(f"Document valid: {result.is_valid}")
        print(f"Confidence: {result.confidence:.2f}")
        print(f"Quality score: {result.quality_score:.2f}")
        print(f"Summary: {result.analysis_summary}")
        print(f"\nIssues found: {len(result.issues)}")
        for issue in result.issues:
            print(f"- {issue.issue_type.value} ({issue.severity}): {issue.description}")
    else:
        print("Validation failed or timed out")

if __name__ == "__main__":
    asyncio.run(test_content_validator())