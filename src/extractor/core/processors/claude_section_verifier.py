"""
Background Section Verifier using Claude Code Instances
Module: claude_section_verifier.py
Description: Implementation of claude section verifier functionality

Verifies document section hierarchy using Claude's multimodal capabilities.
Detects misplaced headings, validates document organization, and suggests improvements.
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

class SectionIssueType(Enum):
    MISSING_SECTION = "missing_section"
    MISPLACED_HEADING = "misplaced_heading"
    INCONSISTENT_HIERARCHY = "inconsistent_hierarchy"
    DUPLICATE_SECTION = "duplicate_section"
    ORPHANED_CONTENT = "orphaned_content"
    INCORRECT_NESTING = "incorrect_nesting"

@dataclass
class SectionData:
    """Data for a document section."""
    level: int
    title: str
    content: str
    page_number: Optional[int] = None
    position: Optional[Dict[str, float]] = None  # bbox info
    parent_id: Optional[str] = None
    section_id: Optional[str] = None
    subsections: List['SectionData'] = field(default_factory=list)

@dataclass 
class VerificationConfig:
    """Configuration for section verification."""
    sections: List[SectionData]
    document_type: Optional[str] = None
    expected_structure: Optional[List[str]] = None
    include_visual_analysis: bool = True
    page_images: Optional[List[Path]] = None
    timeout: int = 180
    confidence_threshold: float = 0.75
    model: str = "claude-3-5-sonnet-20241022"
    max_retries: int = 3

@dataclass
class SectionIssue:
    """Identified issue with document sections."""
    issue_type: SectionIssueType
    severity: str  # high, medium, low
    section_id: Optional[str]
    description: str
    suggestion: str
    confidence: float
    evidence: Optional[Dict[str, Any]] = None

@dataclass
class VerificationResult:
    """Result of section verification."""
    task_id: str
    is_valid: bool
    confidence: float
    issues: List[SectionIssue]
    suggested_hierarchy: Optional[List[SectionData]] = None
    analysis_summary: str = ""
    structural_score: float = 0.0
    completeness_score: float = 0.0
    hierarchy_score: float = 0.0
    status: TaskStatus = TaskStatus.COMPLETED
    error: Optional[str] = None

class BackgroundSectionVerifier:
    """
    Background Claude Code instance manager for section verification.
    Uses patterns from BackgroundTableAnalyzer for robust execution.
    """
    
    def __init__(self, workspace_dir: Optional[Path] = None, db_path: Optional[Path] = None):
        self.workspace_dir = workspace_dir or Path(tempfile.mkdtemp(prefix="section_verifier_"))
        self.db_path = db_path or self.workspace_dir / "verification_tasks.db"
        self.executor = None
        self._init_database()
        
    def _init_database(self):
        """Initialize SQLite database for task persistence."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS verification_tasks (
                    id TEXT PRIMARY KEY,
                    config TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
    
    async def verify_sections(self, config: VerificationConfig) -> str:
        """
        Submit section verification task for background processing.
        Returns task ID immediately for polling.
        """
        task_id = str(uuid.uuid4())
        
        # Convert config to JSON-serializable format
        config_dict = {
            'sections': self._sections_to_dict(config.sections),
            'document_type': config.document_type,
            'expected_structure': config.expected_structure,
            'include_visual_analysis': config.include_visual_analysis,
            'page_images': [str(p) for p in config.page_images] if config.page_images else None,
            'timeout': config.timeout,
            'confidence_threshold': config.confidence_threshold,
            'model': config.model,
            'max_retries': config.max_retries
        }
        
        # Store task in database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO verification_tasks (id, config, status) VALUES (?, ?, ?)",
                (task_id, json.dumps(config_dict), TaskStatus.PENDING.value)
            )
            conn.commit()
        
        # Schedule background execution
        if self.executor is None:
            self.executor = asyncio.create_task(self._process_tasks())
        
        return task_id
    
    def _sections_to_dict(self, sections: List[SectionData]) -> List[Dict]:
        """Convert SectionData objects to dictionaries."""
        result = []
        for section in sections:
            section_dict = {
                'level': section.level,
                'title': section.title,
                'content': section.content[:500] if len(section.content) > 500 else section.content,  # Limit content size
                'page_number': section.page_number,
                'position': section.position,
                'parent_id': section.parent_id,
                'section_id': section.section_id,
                'subsections': self._sections_to_dict(section.subsections)
            }
            result.append(section_dict)
        return result
    
    async def get_verification_result(self, task_id: str) -> Optional[VerificationResult]:
        """Get verification result by task ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT config, status, result FROM verification_tasks WHERE id = ?",
                (task_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                return None
            
            config_data, status, result_data = row
            status_enum = TaskStatus(status)
            
            if status_enum == TaskStatus.COMPLETED and result_data:
                result_dict = json.loads(result_data)
                
                # Convert issues back to SectionIssue objects
                issues = []
                for issue_dict in result_dict.get('issues', []):
                    issue = SectionIssue(
                        issue_type=SectionIssueType(issue_dict['issue_type']),
                        severity=issue_dict['severity'],
                        section_id=issue_dict.get('section_id'),
                        description=issue_dict['description'],
                        suggestion=issue_dict['suggestion'],
                        confidence=issue_dict['confidence'],
                        evidence=issue_dict.get('evidence')
                    )
                    issues.append(issue)
                
                return VerificationResult(
                    task_id=task_id,
                    status=status_enum,
                    is_valid=result_dict['is_valid'],
                    confidence=result_dict['confidence'],
                    issues=issues,
                    suggested_hierarchy=result_dict.get('suggested_hierarchy'),
                    analysis_summary=result_dict.get('analysis_summary', ''),
                    structural_score=result_dict.get('structural_score', 0.0),
                    completeness_score=result_dict.get('completeness_score', 0.0),
                    hierarchy_score=result_dict.get('hierarchy_score', 0.0)
                )
            elif status_enum == TaskStatus.FAILED and result_data:
                error_dict = json.loads(result_data)
                return VerificationResult(
                    task_id=task_id,
                    status=status_enum,
                    is_valid=False,
                    confidence=0.0,
                    issues=[],
                    error=error_dict.get("error", "Unknown error")
                )
            else:
                return VerificationResult(
                    task_id=task_id,
                    status=status_enum,
                    is_valid=False,
                    confidence=0.0,
                    issues=[],
                    analysis_summary="Verification in progress"
                )
    
    async def _process_tasks(self):
        """Background task processor."""
        while True:
            try:
                # Get pending tasks
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.execute(
                        "SELECT id, config FROM verification_tasks WHERE status = ? ORDER BY created_at",
                        (TaskStatus.PENDING.value,)
                    )
                    tasks = cursor.fetchall()
                
                for task_id, config_json in tasks:
                    try:
                        # Mark as processing
                        self._update_task_status(task_id, TaskStatus.PROCESSING)
                        
                        # Parse config
                        config_dict = json.loads(config_json)
                        
                        # Execute verification
                        result = await self._execute_claude_verification(config_dict)
                        
                        # Store result
                        with sqlite3.connect(self.db_path) as conn:
                            conn.execute(
                                "UPDATE verification_tasks SET status = ?, result = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                                (TaskStatus.COMPLETED.value, json.dumps(result), task_id)
                            )
                            conn.commit()
                            
                        logger.info(f"Completed verification task {task_id}")
                        
                    except Exception as e:
                        logger.error(f"Failed to process task {task_id}: {e}")
                        error_result = {"error": str(e)}
                        with sqlite3.connect(self.db_path) as conn:
                            conn.execute(
                                "UPDATE verification_tasks SET status = ?, result = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
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
                "UPDATE verification_tasks SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status.value, task_id)
            )
            conn.commit()
    
    async def _execute_claude_verification(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute Claude verification using background instance.
        Returns structured verification result.
        """
        
        # Create verification prompt
        prompt = self._create_verification_prompt(config)
        
        # Write prompt to temporary file
        prompt_file = self.workspace_dir / f"verification_prompt_{uuid.uuid4().hex[:8]}.md"
        prompt_file.write_text(prompt)
        
        # Handle page images if provided
        image_args = ""
        if config.get('include_visual_analysis') and config.get('page_images'):
            # Copy images to workspace for Claude to access
            image_paths = []
            for img_path in config['page_images'][:5]:  # Limit to first 5 pages
                if Path(img_path).exists():
                    dest_path = self.workspace_dir / Path(img_path).name
                    subprocess.run(['cp', str(img_path), str(dest_path)], check=True)
                    image_paths.append(dest_path.name)
            
            if image_paths:
                # Claude can process multiple images
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
            return self._parse_verification_response(full_response)
            
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
    
    def _create_verification_prompt(self, config: Dict[str, Any]) -> str:
        """Create comprehensive verification prompt."""
        
        prompt = f"""# Document Section Hierarchy Verification

Analyze the document section structure to identify issues and validate organization.

## Document Information
- Type: {config.get('document_type', 'Unknown')}
- Total Sections: {len(config['sections'])}
- Visual Analysis: {'Enabled - analyzing page layouts' if config.get('include_visual_analysis') else 'Text-only analysis'}

## Current Section Hierarchy

"""
        
        # Build hierarchy tree
        def format_section(section, indent=0):
            result = "  " * indent + f"[L{section['level']}] {section['title']}"
            if section.get('page_number'):
                result += f" (Page {section['page_number']})"
            result += "\n"
            
            # Add brief content preview
            if section.get('content'):
                preview = section['content'][:100].replace('\n', ' ')
                if len(section['content']) > 100:
                    preview += "..."
                result += "  " * (indent + 1) + f"Content: {preview}\n"
            
            # Process subsections
            for subsection in section.get('subsections', []):
                result += format_section(subsection, indent + 1)
            
            return result
        
        for section in config['sections']:
            prompt += format_section(section)
        
        # Add expected structure if provided
        if config.get('expected_structure'):
            prompt += f"\n## Expected Document Structure\n"
            for i, expected in enumerate(config['expected_structure'], 1):
                prompt += f"{i}. {expected}\n"
        
        prompt += f"""
## Analysis Framework

Evaluate these aspects and identify issues:

### 1. Hierarchy Consistency (Score: 0.0-1.0)
- **Level Progression**: Do heading levels follow logical order (H1 → H2 → H3)?
- **Nesting Rules**: Are subsections properly nested under parent sections?
- **Skip Detection**: Are there skipped levels (e.g., H1 → H3)?
- **Orphaned Content**: Is there content without proper section headers?

### 2. Structural Completeness (Score: 0.0-1.0)
- **Required Sections**: Are all expected sections present?
- **Section Order**: Do sections appear in logical order?
- **Missing Elements**: Are there gaps in the document structure?
- **Duplicate Detection**: Are there repeated section titles at the same level?

### 3. Content Organization (Score: 0.0-1.0)
- **Content Placement**: Is content under appropriate sections?
- **Section Length**: Are sections reasonably balanced?
- **Topic Coherence**: Does content match section titles?
- **Flow Logic**: Does the document flow logically?

### 4. Visual Layout Analysis (if images provided)
- **Physical Positioning**: Are headings visually distinct?
- **Spacing Patterns**: Is there consistent spacing between sections?
- **Typography**: Do heading styles match hierarchy levels?
- **Page Breaks**: Are sections split appropriately across pages?

## Issue Detection

Identify these specific issue types:
1. **Missing Sections**: Expected sections not found
2. **Misplaced Headings**: Headings at wrong hierarchy level
3. **Inconsistent Hierarchy**: Broken parent-child relationships
4. **Duplicate Sections**: Same section appearing multiple times
5. **Orphaned Content**: Content without proper section context
6. **Incorrect Nesting**: Subsections at wrong levels

## Required Response Format

Provide your analysis in this EXACT JSON format:

```json
{{
    "is_valid": true/false,
    "confidence": 0.85,
    "structural_score": 0.90,
    "completeness_score": 0.80,
    "hierarchy_score": 0.75,
    "analysis_summary": "Overall assessment of document structure",
    "issues": [
        {{
            "issue_type": "missing_section/misplaced_heading/inconsistent_hierarchy/duplicate_section/orphaned_content/incorrect_nesting",
            "severity": "high/medium/low",
            "section_id": "section identifier if applicable",
            "description": "Detailed description of the issue",
            "suggestion": "Specific suggestion to fix the issue",
            "confidence": 0.90,
            "evidence": {{
                "current_state": "What exists now",
                "expected_state": "What should exist",
                "visual_cues": "Any visual evidence (if images analyzed)"
            }}
        }}
    ],
    "suggested_hierarchy": [
        {{
            "level": 1,
            "title": "Suggested section title",
            "reason": "Why this change is suggested"
        }}
    ]
}}
```

## Analysis Guidelines

**Confidence Threshold**: Only mark as valid if confidence >= {config.get('confidence_threshold', 0.75)}

**Severity Levels**:
- High: Critical structural issues affecting document usability
- Medium: Issues affecting readability or navigation
- Low: Minor inconsistencies or style issues

**Evidence-Based**: All issues must have concrete evidence from the document

Please provide a thorough structural analysis following this framework.
"""
        
        return prompt
    
    def _parse_verification_response(self, response: str) -> Dict[str, Any]:
        """Parse Claude's verification response."""
        try:
            # First try to parse as direct JSON
            try:
                parsed = json.loads(response.strip())
                
                # Convert issue_type strings to enum values for validation
                issues = []
                for issue in parsed.get('issues', []):
                    issue_dict = {
                        'issue_type': issue.get('issue_type', 'missing_section'),
                        'severity': issue.get('severity', 'medium'),
                        'section_id': issue.get('section_id'),
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
                    "suggested_hierarchy": parsed.get("suggested_hierarchy"),
                    "analysis_summary": parsed.get("analysis_summary", ""),
                    "structural_score": float(parsed.get("structural_score", 0.0)),
                    "completeness_score": float(parsed.get("completeness_score", 0.0)),
                    "hierarchy_score": float(parsed.get("hierarchy_score", 0.0))
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
                            'issue_type': issue.get('issue_type', 'missing_section'),
                            'severity': issue.get('severity', 'medium'),
                            'section_id': issue.get('section_id'),
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
                        "suggested_hierarchy": parsed.get("suggested_hierarchy"),
                        "analysis_summary": parsed.get("analysis_summary", ""),
                        "structural_score": float(parsed.get("structural_score", 0.0)),
                        "completeness_score": float(parsed.get("completeness_score", 0.0)),
                        "hierarchy_score": float(parsed.get("hierarchy_score", 0.0))
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
                            "issue_type": "missing_section",
                            "severity": "high",
                            "section_id": None,
                            "description": "Failed to parse verification response",
                            "suggestion": "Manual review required",
                            "confidence": 0.0,
                            "evidence": None
                        }],
                        "analysis_summary": f"Parse error: {response[:500]}..."
                    }
                
        except Exception as e:
            logger.error(f"Failed to parse Claude verification response: {e}")
            return {
                "is_valid": False,
                "confidence": 0.0,
                "issues": [{
                    "issue_type": "missing_section",
                    "severity": "high", 
                    "section_id": None,
                    "description": f"Parse error: {e}",
                    "suggestion": "Check response format",
                    "confidence": 0.0,
                    "evidence": None
                }],
                "analysis_summary": f"Error: {e}"
            }

# High-level interface for integration
class SectionVerificationEngine:
    """
    High-level interface for section verification using background Claude analysis.
    """
    
    def __init__(self, workspace_dir: Optional[Path] = None):
        self.verifier = BackgroundSectionVerifier(workspace_dir)
        self.pending_tasks = {}
    
    async def submit_verification(self, 
                                 sections: List[SectionData],
                                 document_type: Optional[str] = None,
                                 expected_structure: Optional[List[str]] = None,
                                 page_images: Optional[List[Path]] = None,
                                 confidence_threshold: float = 0.75) -> str:
        """Submit document sections for verification."""
        
        config = VerificationConfig(
            sections=sections,
            document_type=document_type,
            expected_structure=expected_structure,
            include_visual_analysis=bool(page_images),
            page_images=page_images,
            confidence_threshold=confidence_threshold
        )
        
        task_id = await self.verifier.verify_sections(config)
        self.pending_tasks[task_id] = {
            "submitted_at": time.time(),
            "config": config
        }
        
        return task_id
    
    async def get_verification_result(self, task_id: str, timeout: float = 300.0) -> Optional[VerificationResult]:
        """Get verification result, waiting up to timeout seconds."""
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            result = await self.verifier.get_verification_result(task_id)
            
            if result and result.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                # Clean up tracking
                self.pending_tasks.pop(task_id, None)
                return result
            
            await asyncio.sleep(2)
        
        logger.warning(f"Verification task {task_id} timed out after {timeout}s")
        return None
    
    # Synchronous wrappers for non-async contexts
    def submit_verification_sync(self, 
                                sections: List[SectionData],
                                document_type: Optional[str] = None,
                                expected_structure: Optional[List[str]] = None,
                                page_images: Optional[List[Path]] = None,
                                confidence_threshold: float = 0.75) -> str:
        """Synchronous wrapper for submit_verification."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self.submit_verification(sections, document_type, expected_structure, page_images, confidence_threshold)
            )
        finally:
            loop.close()
    
    def get_verification_result_sync(self, task_id: str, timeout: float = 300.0) -> Optional[VerificationResult]:
        """Synchronous wrapper for get_verification_result."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self.get_verification_result(task_id, timeout)
            )
        finally:
            loop.close()

# Example usage and testing
async def test_section_verifier():
    """Test the section verifier with sample data."""
    
    engine = SectionVerificationEngine()
    
    # Sample section data
    sections = [
        SectionData(
            level=1,
            title="Introduction",
            content="This document provides an overview of our system architecture...",
            page_number=1,
            section_id="intro"
        ),
        SectionData(
            level=3,  # Wrong level - should be 2
            title="Background",
            content="Previous work in this area includes...",
            page_number=2,
            section_id="background"
        ),
        SectionData(
            level=2,
            title="Methodology", 
            content="Our approach consists of three main steps...",
            page_number=3,
            section_id="method"
        ),
        SectionData(
            level=2,
            title="Methodology",  # Duplicate
            content="The experimental setup was as follows...",
            page_number=4,
            section_id="method2"
        ),
        SectionData(
            level=1,
            title="Conclusion",
            content="In summary, our findings show...",
            page_number=10,
            section_id="conclusion"
        )
    ]
    
    expected_structure = [
        "Introduction",
        "Background/Literature Review", 
        "Methodology",
        "Results",
        "Discussion",
        "Conclusion"
    ]
    
    # Submit verification
    task_id = await engine.submit_verification(
        sections=sections,
        document_type="research_paper",
        expected_structure=expected_structure
    )
    print(f"Submitted verification task: {task_id}")
    
    # Get result
    result = await engine.get_verification_result(task_id)
    if result:
        print(f"Document valid: {result.is_valid}")
        print(f"Confidence: {result.confidence:.2f}")
        print(f"Summary: {result.analysis_summary}")
        print(f"\nIssues found: {len(result.issues)}")
        for issue in result.issues:
            print(f"- {issue.issue_type.value} ({issue.severity}): {issue.description}")
            print(f"  Suggestion: {issue.suggestion}")
    else:
        print("Verification failed or timed out")

if __name__ == "__main__":
    asyncio.run(test_section_verifier())