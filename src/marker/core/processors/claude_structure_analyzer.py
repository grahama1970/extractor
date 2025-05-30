"""
Background Structure Analyzer using Claude Code Instances

Analyzes document organization and structure using Claude.
Provides insights on document flow, organization quality, and improvement suggestions.
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

class StructureInsightType(Enum):
    ORGANIZATION_PATTERN = "organization_pattern"
    FLOW_ANALYSIS = "flow_analysis"
    HIERARCHY_STRUCTURE = "hierarchy_structure"
    CONTENT_DISTRIBUTION = "content_distribution"
    NAVIGATION_QUALITY = "navigation_quality"
    CROSS_REFERENCES = "cross_references"
    METADATA_COMPLETENESS = "metadata_completeness"

@dataclass
class StructureData:
    """Data for document structure analysis."""
    section_hierarchy: List[Dict[str, Any]]  # Nested section structure
    content_distribution: Dict[str, int]  # Distribution of different block types
    page_structure: List[Dict[str, Any]]  # Structure info per page
    cross_references: List[Dict[str, str]]  # Internal references
    navigation_elements: Dict[str, Any]  # TOC, index, etc.
    document_metadata: Optional[Dict[str, Any]] = None
    total_pages: int = 0
    avg_content_per_page: float = 0.0

@dataclass
class AnalysisConfig:
    """Configuration for structure analysis."""
    structure_data: StructureData
    document_type: Optional[str] = None
    analysis_depth: str = "comprehensive"  # basic, moderate, comprehensive
    include_flow_diagram: bool = True
    page_images: Optional[List[Path]] = None
    timeout: int = 240
    confidence_threshold: float = 0.85
    model: str = "claude-3-5-sonnet-20241022"
    max_retries: int = 3

@dataclass
class StructureInsight:
    """Individual insight about document structure."""
    insight_type: StructureInsightType
    category: str  # organization, flow, navigation, quality
    finding: str
    impact: str  # high, medium, low
    recommendation: str
    confidence: float
    evidence: Optional[Dict[str, Any]] = None

@dataclass
class AnalysisResult:
    """Result of structure analysis."""
    task_id: str
    organization_score: float
    flow_score: float
    navigation_score: float
    overall_structure_score: float
    document_pattern: str  # e.g., "hierarchical", "sequential", "modular"
    insights: List[StructureInsight]
    structure_diagram: Optional[str] = None  # ASCII or markdown diagram
    improvement_plan: List[Dict[str, str]] = field(default_factory=list)
    analysis_summary: str = ""
    status: TaskStatus = TaskStatus.COMPLETED
    error: Optional[str] = None

class BackgroundStructureAnalyzer:
    """
    Background Claude Code instance manager for structure analysis.
    Uses patterns from BackgroundTableAnalyzer for robust execution.
    """
    
    def __init__(self, workspace_dir: Optional[Path] = None, db_path: Optional[Path] = None):
        self.workspace_dir = workspace_dir or Path(tempfile.mkdtemp(prefix="structure_analyzer_"))
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
    
    async def analyze_structure(self, config: AnalysisConfig) -> str:
        """
        Submit structure analysis task for background processing.
        Returns task ID immediately for polling.
        """
        task_id = str(uuid.uuid4())
        
        # Convert config to JSON-serializable format
        config_dict = {
            'structure_data': {
                'section_hierarchy': config.structure_data.section_hierarchy,
                'content_distribution': config.structure_data.content_distribution,
                'page_structure': config.structure_data.page_structure[:10],  # Limit for size
                'cross_references': config.structure_data.cross_references,
                'navigation_elements': config.structure_data.navigation_elements,
                'document_metadata': config.structure_data.document_metadata,
                'total_pages': config.structure_data.total_pages,
                'avg_content_per_page': config.structure_data.avg_content_per_page
            },
            'document_type': config.document_type,
            'analysis_depth': config.analysis_depth,
            'include_flow_diagram': config.include_flow_diagram,
            'page_images': [str(p) for p in config.page_images] if config.page_images else None,
            'timeout': config.timeout,
            'confidence_threshold': config.confidence_threshold,
            'model': config.model,
            'max_retries': config.max_retries
        }
        
        # Store task in database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO analysis_tasks (id, config, status) VALUES (?, ?, ?)",
                (task_id, json.dumps(config_dict), TaskStatus.PENDING.value)
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
                
                # Convert insights back to StructureInsight objects
                insights = []
                for insight_dict in result_dict.get('insights', []):
                    insight = StructureInsight(
                        insight_type=StructureInsightType(insight_dict['insight_type']),
                        category=insight_dict['category'],
                        finding=insight_dict['finding'],
                        impact=insight_dict['impact'],
                        recommendation=insight_dict['recommendation'],
                        confidence=insight_dict['confidence'],
                        evidence=insight_dict.get('evidence')
                    )
                    insights.append(insight)
                
                return AnalysisResult(
                    task_id=task_id,
                    status=status_enum,
                    organization_score=result_dict['organization_score'],
                    flow_score=result_dict['flow_score'],
                    navigation_score=result_dict['navigation_score'],
                    overall_structure_score=result_dict['overall_structure_score'],
                    document_pattern=result_dict['document_pattern'],
                    insights=insights,
                    structure_diagram=result_dict.get('structure_diagram'),
                    improvement_plan=result_dict.get('improvement_plan', []),
                    analysis_summary=result_dict.get('analysis_summary', '')
                )
            elif status_enum == TaskStatus.FAILED and result_data:
                error_dict = json.loads(result_data)
                return AnalysisResult(
                    task_id=task_id,
                    status=status_enum,
                    organization_score=0.0,
                    flow_score=0.0,
                    navigation_score=0.0,
                    overall_structure_score=0.0,
                    document_pattern="unknown",
                    insights=[],
                    error=error_dict.get("error", "Unknown error")
                )
            else:
                return AnalysisResult(
                    task_id=task_id,
                    status=status_enum,
                    organization_score=0.0,
                    flow_score=0.0,
                    navigation_score=0.0,
                    overall_structure_score=0.0,
                    document_pattern="unknown",
                    insights=[],
                    analysis_summary="Analysis in progress"
                )
    
    async def _process_tasks(self):
        """Background task processor."""
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
                        
                        # Execute analysis
                        result = await self._execute_claude_analysis(config_dict)
                        
                        # Store result
                        with sqlite3.connect(self.db_path) as conn:
                            conn.execute(
                                "UPDATE analysis_tasks SET status = ?, result = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                                (TaskStatus.COMPLETED.value, json.dumps(result), task_id)
                            )
                            conn.commit()
                            
                        logger.info(f"Completed structure analysis task {task_id}")
                        
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
    
    async def _execute_claude_analysis(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute Claude analysis using background instance.
        Returns structured analysis result.
        """
        
        # Create analysis prompt
        prompt = self._create_analysis_prompt(config)
        
        # Write prompt to temporary file
        prompt_file = self.workspace_dir / f"analysis_prompt_{uuid.uuid4().hex[:8]}.md"
        prompt_file.write_text(prompt)
        
        # Handle page images if provided
        image_args = ""
        if config.get('include_flow_diagram') and config.get('page_images'):
            # Copy sample pages to workspace for Claude to access
            image_paths = []
            for img_path in config['page_images'][:3]:  # First 3 pages for overview
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
            return self._parse_analysis_response(full_response)
            
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
    
    def _create_analysis_prompt(self, config: Dict[str, Any]) -> str:
        """Create comprehensive structure analysis prompt."""
        
        structure_data = config['structure_data']
        
        prompt = f"""# Document Structure Analysis

Perform a {config.get('analysis_depth', 'comprehensive')} analysis of this document's organization and structure.

## Document Overview
- Type: {config.get('document_type', 'Unknown')}
- Total Pages: {structure_data['total_pages']}
- Average Content Per Page: {structure_data['avg_content_per_page']:.1f} blocks

## Section Hierarchy
```json
{json.dumps(structure_data['section_hierarchy'], indent=2)}
```

## Content Distribution
{json.dumps(structure_data['content_distribution'], indent=2)}

## Navigation Elements
{json.dumps(structure_data['navigation_elements'], indent=2)}

## Cross-References Found
Total internal references: {len(structure_data['cross_references'])}

"""
        
        # Add sample page structures
        if structure_data.get('page_structure'):
            prompt += "## Sample Page Structures\n"
            for i, page_info in enumerate(structure_data['page_structure'][:5], 1):
                prompt += f"\nPage {i}: {json.dumps(page_info, indent=2)}\n"
        
        prompt += f"""
## Analysis Framework

Evaluate the document structure across these dimensions:

### 1. Organization Quality (Score: 0.0-1.0)
- **Logical Grouping**: Are related topics grouped together?
- **Hierarchy Clarity**: Is the section hierarchy clear and meaningful?
- **Balance**: Are sections appropriately sized and balanced?
- **Modularity**: Can sections stand alone or are they interdependent?

### 2. Document Flow (Score: 0.0-1.0)
- **Sequential Logic**: Does content flow naturally from section to section?
- **Transitions**: Are there smooth transitions between topics?
- **Progressive Disclosure**: Is information revealed at appropriate times?
- **Narrative Arc**: Does the document tell a coherent story?

### 3. Navigation Quality (Score: 0.0-1.0)
- **Findability**: How easy is it to find specific information?
- **Cross-References**: Are internal references helpful and accurate?
- **TOC/Index Quality**: Are navigation aids comprehensive?
- **Heading Clarity**: Do headings accurately describe content?

### 4. Structural Patterns
Identify the dominant organizational pattern:
- **Hierarchical**: Tree-like structure with clear parent-child relationships
- **Sequential**: Linear progression through topics
- **Modular**: Independent sections that can be read in any order
- **Matrix**: Multiple organizational dimensions
- **Hybrid**: Combination of patterns

## Required Response Format

Provide your analysis in this EXACT JSON format:

```json
{{
    "organization_score": 0.85,
    "flow_score": 0.80,
    "navigation_score": 0.75,
    "overall_structure_score": 0.80,
    "document_pattern": "hierarchical/sequential/modular/matrix/hybrid",
    "analysis_summary": "High-level summary of document structure quality",
    "insights": [
        {{
            "insight_type": "organization_pattern/flow_analysis/hierarchy_structure/content_distribution/navigation_quality/cross_references/metadata_completeness",
            "category": "organization/flow/navigation/quality",
            "finding": "Specific observation about the structure",
            "impact": "high/medium/low",
            "recommendation": "Actionable suggestion for improvement",
            "confidence": 0.90,
            "evidence": {{
                "examples": ["Specific examples from document"],
                "metrics": {{"relevant": "metrics"}}
            }}
        }}
    ],
    "structure_diagram": "Optional ASCII/Markdown diagram showing document structure",
    "improvement_plan": [
        {{
            "priority": "high/medium/low",
            "action": "Specific action to improve structure",
            "expected_impact": "What this will achieve",
            "effort": "low/medium/high"
        }}
    ]
}}
```

## Analysis Guidelines

**Depth Levels**:
- Basic: Focus on high-level organization only
- Moderate: Include flow and basic navigation analysis
- Comprehensive: Full analysis with detailed insights and improvement plan

**Quality Thresholds**:
- Excellent: >= 0.85 overall score
- Good: 0.70-0.84
- Needs Improvement: < 0.70

**Evidence-Based**: All insights must reference specific examples from the document

{f"**Include Visual Diagram**: Create an ASCII or Markdown diagram showing the document's structure" if config.get('include_flow_diagram') else ""}

Please provide a thorough structural analysis following this framework.
"""
        
        return prompt
    
    def _parse_analysis_response(self, response: str) -> Dict[str, Any]:
        """Parse Claude's analysis response."""
        try:
            # First try to parse as direct JSON
            try:
                parsed = json.loads(response.strip())
                
                # Convert insight_type strings to enum values for validation
                insights = []
                for insight in parsed.get('insights', []):
                    insight_dict = {
                        'insight_type': insight.get('insight_type', 'organization_pattern'),
                        'category': insight.get('category', 'organization'),
                        'finding': insight.get('finding', ''),
                        'impact': insight.get('impact', 'medium'),
                        'recommendation': insight.get('recommendation', ''),
                        'confidence': float(insight.get('confidence', 0.8)),
                        'evidence': insight.get('evidence')
                    }
                    insights.append(insight_dict)
                
                result = {
                    "organization_score": float(parsed.get("organization_score", 0.0)),
                    "flow_score": float(parsed.get("flow_score", 0.0)),
                    "navigation_score": float(parsed.get("navigation_score", 0.0)),
                    "overall_structure_score": float(parsed.get("overall_structure_score", 0.0)),
                    "document_pattern": parsed.get("document_pattern", "unknown"),
                    "insights": insights,
                    "structure_diagram": parsed.get("structure_diagram"),
                    "improvement_plan": parsed.get("improvement_plan", []),
                    "analysis_summary": parsed.get("analysis_summary", "")
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
                    insights = []
                    for insight in parsed.get('insights', []):
                        insight_dict = {
                            'insight_type': insight.get('insight_type', 'organization_pattern'),
                            'category': insight.get('category', 'organization'),
                            'finding': insight.get('finding', ''),
                            'impact': insight.get('impact', 'medium'),
                            'recommendation': insight.get('recommendation', ''),
                            'confidence': float(insight.get('confidence', 0.8)),
                            'evidence': insight.get('evidence')
                        }
                        insights.append(insight_dict)
                    
                    result = {
                        "organization_score": float(parsed.get("organization_score", 0.0)),
                        "flow_score": float(parsed.get("flow_score", 0.0)),
                        "navigation_score": float(parsed.get("navigation_score", 0.0)),
                        "overall_structure_score": float(parsed.get("overall_structure_score", 0.0)),
                        "document_pattern": parsed.get("document_pattern", "unknown"),
                        "insights": insights,
                        "structure_diagram": parsed.get("structure_diagram"),
                        "improvement_plan": parsed.get("improvement_plan", []),
                        "analysis_summary": parsed.get("analysis_summary", "")
                    }
                    
                    logger.debug(f"Successfully parsed JSON from markdown block")
                    return result
                else:
                    # Fallback
                    logger.warning("Could not parse Claude response as JSON")
                    return {
                        "organization_score": 0.0,
                        "flow_score": 0.0,
                        "navigation_score": 0.0,
                        "overall_structure_score": 0.0,
                        "document_pattern": "unknown",
                        "insights": [{
                            "insight_type": "organization_pattern",
                            "category": "quality",
                            "finding": "Failed to parse analysis response",
                            "impact": "high",
                            "recommendation": "Manual review required",
                            "confidence": 0.0,
                            "evidence": None
                        }],
                        "analysis_summary": f"Parse error: {response[:500]}..."
                    }
                
        except Exception as e:
            logger.error(f"Failed to parse Claude analysis response: {e}")
            return {
                "organization_score": 0.0,
                "flow_score": 0.0,
                "navigation_score": 0.0,
                "overall_structure_score": 0.0,
                "document_pattern": "unknown",
                "insights": [{
                    "insight_type": "organization_pattern",
                    "category": "quality",
                    "finding": f"Parse error: {e}",
                    "impact": "high",
                    "recommendation": "Check response format",
                    "confidence": 0.0,
                    "evidence": None
                }],
                "analysis_summary": f"Error: {e}"
            }

# High-level interface for integration
class StructureAnalysisEngine:
    """
    High-level interface for structure analysis using background Claude analysis.
    """
    
    def __init__(self, workspace_dir: Optional[Path] = None):
        self.analyzer = BackgroundStructureAnalyzer(workspace_dir)
        self.pending_tasks = {}
    
    async def submit_analysis(self, 
                             structure_data: StructureData,
                             document_type: Optional[str] = None,
                             analysis_depth: str = "comprehensive",
                             page_images: Optional[List[Path]] = None,
                             confidence_threshold: float = 0.85) -> str:
        """Submit document structure for analysis."""
        
        config = AnalysisConfig(
            structure_data=structure_data,
            document_type=document_type,
            analysis_depth=analysis_depth,
            include_flow_diagram=True,
            page_images=page_images,
            confidence_threshold=confidence_threshold
        )
        
        task_id = await self.analyzer.analyze_structure(config)
        self.pending_tasks[task_id] = {
            "submitted_at": time.time(),
            "config": config
        }
        
        return task_id
    
    async def get_analysis_result(self, task_id: str, timeout: float = 300.0) -> Optional[AnalysisResult]:
        """Get analysis result, waiting up to timeout seconds."""
        
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
    
    # Synchronous wrappers for non-async contexts
    def submit_analysis_sync(self, 
                            structure_data: StructureData,
                            document_type: Optional[str] = None,
                            analysis_depth: str = "comprehensive",
                            page_images: Optional[List[Path]] = None,
                            confidence_threshold: float = 0.85) -> str:
        """Synchronous wrapper for submit_analysis."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self.submit_analysis(structure_data, document_type, analysis_depth, page_images, confidence_threshold)
            )
        finally:
            loop.close()
    
    def get_analysis_result_sync(self, task_id: str, timeout: float = 300.0) -> Optional[AnalysisResult]:
        """Synchronous wrapper for get_analysis_result."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self.get_analysis_result(task_id, timeout)
            )
        finally:
            loop.close()

# Example usage and testing
async def test_structure_analyzer():
    """Test the structure analyzer with sample data."""
    
    engine = StructureAnalysisEngine()
    
    # Sample structure data
    structure_data = StructureData(
        section_hierarchy=[
            {
                "title": "Introduction",
                "level": 1,
                "subsections": [
                    {"title": "Background", "level": 2},
                    {"title": "Objectives", "level": 2}
                ]
            },
            {
                "title": "Methodology",
                "level": 1,
                "subsections": [
                    {"title": "Data Collection", "level": 2},
                    {"title": "Analysis Methods", "level": 2}
                ]
            },
            {
                "title": "Results",
                "level": 1,
                "subsections": []
            }
        ],
        content_distribution={
            "text": 150,
            "tables": 10,
            "figures": 8,
            "equations": 5,
            "code": 3
        },
        page_structure=[
            {"page": 1, "blocks": 12, "dominant_type": "text"},
            {"page": 2, "blocks": 15, "dominant_type": "text"},
            {"page": 3, "blocks": 8, "dominant_type": "table"}
        ],
        cross_references=[
            {"from": "Section 2.1", "to": "Figure 3"},
            {"from": "Section 3", "to": "Table 1"}
        ],
        navigation_elements={
            "has_toc": True,
            "has_index": False,
            "has_list_of_figures": True,
            "has_list_of_tables": True
        },
        document_metadata={
            "title": "Sample Research Paper",
            "author": "Dr. Smith",
            "date": "2024"
        },
        total_pages=50,
        avg_content_per_page=8.5
    )
    
    # Submit analysis
    task_id = await engine.submit_analysis(
        structure_data=structure_data,
        document_type="research_paper",
        analysis_depth="comprehensive"
    )
    print(f"Submitted structure analysis task: {task_id}")
    
    # Get result
    result = await engine.get_analysis_result(task_id)
    if result:
        print(f"\nStructure Analysis Results:")
        print(f"Organization score: {result.organization_score:.2f}")
        print(f"Flow score: {result.flow_score:.2f}")
        print(f"Navigation score: {result.navigation_score:.2f}")
        print(f"Overall structure score: {result.overall_structure_score:.2f}")
        print(f"Document pattern: {result.document_pattern}")
        print(f"\nSummary: {result.analysis_summary}")
        
        print(f"\nKey Insights ({len(result.insights)}):")
        for insight in result.insights:
            print(f"- {insight.finding} (Impact: {insight.impact})")
            print(f"  Recommendation: {insight.recommendation}")
        
        if result.structure_diagram:
            print(f"\nStructure Diagram:\n{result.structure_diagram}")
    else:
        print("Analysis failed or timed out")

if __name__ == "__main__":
    asyncio.run(test_structure_analyzer())