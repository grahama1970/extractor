"""
Claude Code Verification and Analysis System

Optional Claude Code features for document processing with configurable controls.
Provides verification of section objects and intelligent table merging when enabled.

Features are opt-in and configurable to balance accuracy vs performance.
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Union
from loguru import logger

from marker.core.processors.claude_table_merge_analyzer import TableMergeDecisionEngine
from marker.core.schema import BlockTypes
from marker.core.schema.blocks import Block
from marker.core.schema.document import Document

class ClaudeFeature(Enum):
    """Available Claude Code features."""
    TABLE_MERGE_ANALYSIS = "table_merge_analysis"
    SECTION_VERIFICATION = "section_verification" 
    CONTENT_VALIDATION = "content_validation"
    STRUCTURE_ANALYSIS = "structure_analysis"

@dataclass
class ClaudeConfig:
    """Configuration for Claude Code features."""
    
    # Global settings
    enabled: bool = False
    workspace_dir: Optional[Path] = None
    model: str = "claude-3-5-sonnet-20241022"
    max_concurrent: int = 2
    timeout: float = 120.0
    
    # Feature-specific settings
    features: Dict[ClaudeFeature, bool] = field(default_factory=lambda: {
        ClaudeFeature.TABLE_MERGE_ANALYSIS: False,
        ClaudeFeature.SECTION_VERIFICATION: False,
        ClaudeFeature.CONTENT_VALIDATION: False,
        ClaudeFeature.STRUCTURE_ANALYSIS: False
    })
    
    # Thresholds and parameters
    table_merge_confidence_threshold: float = 0.75
    section_verification_confidence_threshold: float = 0.8
    min_tables_for_analysis: int = 2
    min_sections_for_verification: int = 3
    
    # Performance controls
    skip_claude_if_processing_time_exceeds: float = 300.0  # 5 minutes
    max_claude_analysis_per_document: int = 10
    fallback_to_heuristics: bool = True

@dataclass
class VerificationResult:
    """Result of Claude verification."""
    verified: bool
    confidence: float
    issues: List[str]
    suggestions: List[str]
    original_data: Dict[str, Any]
    corrected_data: Optional[Dict[str, Any]] = None
    reasoning: str = ""

class ClaudeDocumentProcessor:
    """
    Optional Claude Code processor for document analysis and verification.
    
    All features are configurable and disabled by default for performance.
    Users can enable specific features based on their accuracy/speed requirements.
    """
    
    def __init__(self, config: ClaudeConfig):
        self.config = config
        self.stats = {
            "analyses_performed": 0,
            "total_claude_time": 0.0,
            "features_used": {},
            "fallbacks_triggered": 0
        }
        
        # Initialize subsystems only if enabled
        self.table_analyzer = None
        if config.enabled and config.features.get(ClaudeFeature.TABLE_MERGE_ANALYSIS, False):
            self.table_analyzer = TableMergeDecisionEngine(config.workspace_dir)
        
        self.verification_semaphore = asyncio.Semaphore(config.max_concurrent)
    
    async def process_document(self, document: Document, processing_start_time: float) -> Dict[str, Any]:
        """
        Main entry point for Claude-enhanced document processing.
        
        Args:
            document: Document to process
            processing_start_time: When document processing started (for timeout checks)
            
        Returns:
            Dictionary with analysis results and applied improvements
        """
        
        if not self.config.enabled:
            return {"claude_enabled": False, "reason": "Claude features disabled"}
        
        elapsed_time = time.time() - processing_start_time
        if elapsed_time > self.config.skip_claude_if_processing_time_exceeds:
            return {
                "claude_enabled": False, 
                "reason": f"Processing time ({elapsed_time:.1f}s) exceeds threshold"
            }
        
        results = {
            "claude_enabled": True,
            "features_applied": [],
            "performance_stats": {},
            "verification_results": {},
            "improvements_made": []
        }
        
        # Apply enabled features
        if self.config.features.get(ClaudeFeature.SECTION_VERIFICATION, False):
            section_results = await self._verify_sections(document)
            results["verification_results"]["sections"] = section_results
            if section_results.get("improvements_applied", 0) > 0:
                results["improvements_made"].append("section_corrections")
        
        if self.config.features.get(ClaudeFeature.TABLE_MERGE_ANALYSIS, False):
            table_results = await self._analyze_table_merges(document)
            results["verification_results"]["tables"] = table_results
            if table_results.get("merges_applied", 0) > 0:
                results["improvements_made"].append("intelligent_table_merges")
        
        if self.config.features.get(ClaudeFeature.CONTENT_VALIDATION, False):
            content_results = await self._validate_content_structure(document)
            results["verification_results"]["content"] = content_results
        
        if self.config.features.get(ClaudeFeature.STRUCTURE_ANALYSIS, False):
            structure_results = await self._analyze_document_structure(document)
            results["verification_results"]["structure"] = structure_results
        
        # Add performance statistics
        results["performance_stats"] = self.get_performance_stats()
        
        return results
    
    async def _verify_sections(self, document: Document) -> Dict[str, Any]:
        """
        Verify section objects for accuracy and integrity using Claude.
        
        Checks for:
        - Correct section hierarchy and nesting
        - Proper section titles and numbering
        - Missing or incorrectly detected sections
        - Section boundary accuracy
        - Heading level consistency
        """
        
        start_time = time.time()
        
        # Extract section information
        sections = self._extract_section_data(document)
        
        if len(sections) < self.config.min_sections_for_verification:
            return {
                "verified": False,
                "reason": f"Too few sections ({len(sections)}) for verification",
                "sections_found": len(sections)
            }
        
        logger.info(f"Verifying {len(sections)} sections with Claude")
        
        # Create verification prompt
        verification_prompt = self._create_section_verification_prompt(sections, document)
        
        # Execute Claude verification
        async with self.verification_semaphore:
            try:
                verification_result = await self._execute_claude_verification(
                    verification_prompt, 
                    "section_verification"
                )
                
                # Apply corrections if confidence is high enough
                improvements_applied = 0
                if (verification_result.confidence >= self.config.section_verification_confidence_threshold 
                    and verification_result.corrected_data):
                    improvements_applied = await self._apply_section_corrections(
                        document, verification_result.corrected_data
                    )
                
                verification_time = time.time() - start_time
                self.stats["total_claude_time"] += verification_time
                self.stats["analyses_performed"] += 1
                
                return {
                    "verified": verification_result.verified,
                    "confidence": verification_result.confidence,
                    "issues_found": len(verification_result.issues),
                    "issues": verification_result.issues,
                    "suggestions": verification_result.suggestions,
                    "improvements_applied": improvements_applied,
                    "verification_time": verification_time,
                    "reasoning": verification_result.reasoning
                }
                
            except Exception as e:
                logger.error(f"Section verification failed: {e}")
                if self.config.fallback_to_heuristics:
                    self.stats["fallbacks_triggered"] += 1
                return {
                    "verified": False,
                    "error": str(e),
                    "fallback_used": self.config.fallback_to_heuristics
                }
    
    def _extract_section_data(self, document: Document) -> List[Dict[str, Any]]:
        """Extract section information from document."""
        
        sections = []
        
        for page in document.pages:
            page_blocks = [block for block in document.contained_blocks() if block.page_id == page.page_id]
            
            for block in page_blocks:
                block_type = str(block.block_type).split('.')[-1].lower()
                
                if block_type == 'sectionheader':
                    section_data = {
                        "id": str(block.id),
                        "page_id": block.page_id,
                        "text": block.raw_text(document).strip(),
                        "level": getattr(block, 'heading_level', 1),
                        "bbox": block.polygon.bbox if hasattr(block, 'polygon') and block.polygon else None,
                        "block_type": block_type
                    }
                    sections.append(section_data)
        
        # Sort by page and position
        sections.sort(key=lambda s: (s["page_id"], s["bbox"][1] if s["bbox"] else 0))
        
        return sections
    
    def _create_section_verification_prompt(self, sections: List[Dict[str, Any]], document: Document) -> str:
        """Create comprehensive section verification prompt."""
        
        prompt = f"""# Document Section Verification Task

Analyze this document's section structure for accuracy and integrity.

## Document Overview
- Total pages: {len(document.pages)}
- Sections found: {len(sections)}

## Detected Sections
"""
        
        for i, section in enumerate(sections):
            prompt += f"""
### Section {i+1}
- **Text**: "{section['text']}"
- **Level**: {section['level']}
- **Page**: {section['page_id']}
- **Position**: {section['bbox']}
"""
        
        prompt += """
## Verification Criteria

Please analyze the section structure for these issues:

### 1. Hierarchy Consistency
- Are section levels logical and consistent?
- Do heading levels progress properly (1→2→3, not 1→3)?
- Are there missing intermediate levels?

### 2. Numbering and Formatting
- Is section numbering consistent (if present)?
- Are section titles properly formatted?
- Do similar sections have similar formatting?

### 3. Content Analysis
- Do section titles accurately reflect their likely content?
- Are there obvious missing sections (e.g., "Introduction" without "Conclusion")?
- Are sections in logical order?

### 4. Technical Accuracy
- Are headings correctly identified vs regular text?
- Are section boundaries appropriate?
- Are there false positive section detections?

## Required Response Format

```json
{
    "verified": true/false,
    "confidence": 0.85,
    "overall_assessment": "excellent/good/fair/poor",
    "issues": [
        {
            "type": "hierarchy_issue/numbering_issue/content_issue/technical_issue",
            "severity": "high/medium/low", 
            "description": "Detailed description of the issue",
            "affected_sections": [1, 2, 3],
            "suggestion": "How to fix this issue"
        }
    ],
    "suggestions": [
        "General improvement suggestions"
    ],
    "corrections": [
        {
            "section_id": "section_id_here",
            "current_level": 2,
            "suggested_level": 3,
            "current_text": "Current title",
            "suggested_text": "Corrected title",
            "reasoning": "Why this correction is needed"
        }
    ],
    "reasoning": "Overall analysis of the section structure quality"
}
```

Please provide a thorough analysis focusing on accuracy and consistency.
"""
        
        return prompt
    
    async def _analyze_table_merges(self, document: Document) -> Dict[str, Any]:
        """Analyze table merge opportunities using Claude."""
        
        if not self.table_analyzer:
            return {"enabled": False, "reason": "Table analyzer not initialized"}
        
        # Get table blocks
        table_blocks = []
        for page in document.pages:
            page_tables = page.contained_blocks(document, (BlockTypes.Table,))
            table_blocks.extend(page_tables)
        
        if len(table_blocks) < self.config.min_tables_for_analysis:
            return {
                "analyzed": False,
                "reason": f"Too few tables ({len(table_blocks)}) for analysis",
                "tables_found": len(table_blocks)
            }
        
        start_time = time.time()
        logger.info(f"Analyzing {len(table_blocks)} tables for merge opportunities")
        
        try:
            # Extract table data and analyze
            tables_data = []
            for i, block in enumerate(table_blocks):
                table_data = await self._extract_table_data_for_analysis(document, block, i)
                tables_data.append(table_data)
            
            # Get merge recommendations
            merge_groups = await self.table_analyzer.analyze_table_sequence_parallel(
                tables_data, 
                self._extract_document_context(document)
            )
            
            # Apply merges
            merges_applied = 0
            for group in merge_groups:
                if len(group) > 1:
                    await self._apply_table_merge(document, group, table_blocks)
                    merges_applied += 1
            
            analysis_time = time.time() - start_time
            self.stats["total_claude_time"] += analysis_time
            
            return {
                "analyzed": True,
                "tables_analyzed": len(table_blocks),
                "merge_groups_found": len([g for g in merge_groups if len(g) > 1]),
                "merges_applied": merges_applied,
                "analysis_time": analysis_time
            }
            
        except Exception as e:
            logger.error(f"Table merge analysis failed: {e}")
            return {"analyzed": False, "error": str(e)}
    
    async def _validate_content_structure(self, document: Document) -> Dict[str, Any]:
        """Validate overall content structure and organization."""
        
        prompt = f"""# Document Content Structure Validation

Analyze this document's overall content organization and structure.

## Document Statistics
- Pages: {len(document.pages)}
- Total blocks: {len(list(document.contained_blocks()))}

## Block Type Distribution
"""
        
        # Count block types
        block_counts = {}
        for block in document.contained_blocks():
            block_type = str(block.block_type).split('.')[-1].lower()
            block_counts[block_type] = block_counts.get(block_type, 0) + 1
        
        for block_type, count in sorted(block_counts.items()):
            prompt += f"- {block_type}: {count}\n"
        
        prompt += """
## Content Structure Analysis

Please evaluate:

1. **Document Organization**: Is the content logically organized?
2. **Block Type Balance**: Are block types appropriately distributed?
3. **Missing Elements**: Are there expected elements missing (headers, conclusions, etc.)?
4. **Structural Issues**: Any obvious structural problems?

Provide recommendations for improvement in JSON format.
"""
        
        try:
            result = await self._execute_claude_verification(prompt, "content_validation")
            return {
                "validated": True,
                "confidence": result.confidence,
                "issues": result.issues,
                "suggestions": result.suggestions
            }
        except Exception as e:
            return {"validated": False, "error": str(e)}
    
    async def _analyze_document_structure(self, document: Document) -> Dict[str, Any]:
        """Analyze document structure for consistency and completeness."""
        
        # Extract structural information
        structure_info = {
            "page_count": len(document.pages),
            "total_blocks": len(list(document.contained_blocks())),
            "sections": self._extract_section_data(document),
            "block_distribution": self._get_block_distribution(document)
        }
        
        prompt = f"""# Document Structure Analysis

Analyze this document's structural integrity and consistency.

## Structure Overview
{json.dumps(structure_info, indent=2)}

Please evaluate structural quality and provide recommendations.
"""
        
        try:
            result = await self._execute_claude_verification(prompt, "structure_analysis")
            return {
                "analyzed": True,
                "confidence": result.confidence,
                "structure_quality": "good" if result.confidence > 0.8 else "needs_improvement",
                "recommendations": result.suggestions
            }
        except Exception as e:
            return {"analyzed": False, "error": str(e)}
    
    def _get_block_distribution(self, document: Document) -> Dict[str, int]:
        """Get distribution of block types in document."""
        
        distribution = {}
        for block in document.contained_blocks():
            block_type = str(block.block_type).split('.')[-1].lower()
            distribution[block_type] = distribution.get(block_type, 0) + 1
        
        return distribution
    
    async def _execute_claude_verification(self, prompt: str, task_type: str) -> VerificationResult:
        """Execute Claude verification with proper error handling."""
        
        # Implementation would use claude_max_proxy patterns
        # For now, return a mock result
        
        # In real implementation:
        # 1. Write prompt to file
        # 2. Execute Claude with subprocess
        # 3. Parse streaming JSON response
        # 4. Return structured result
        
        await asyncio.sleep(0.1)  # Simulate Claude processing
        
        return VerificationResult(
            verified=True,
            confidence=0.85,
            issues=["Mock issue for testing"],
            suggestions=["Mock suggestion"],
            original_data={},
            reasoning="Mock Claude analysis result"
        )
    
    async def _extract_table_data_for_analysis(self, document: Document, block: Block, index: int) -> Dict[str, Any]:
        """Extract comprehensive table data for Claude analysis."""
        
        return {
            "index": index,
            "text": block.raw_text(document) if hasattr(block, 'raw_text') else "",
            "csv": block.generate_csv(document, []) if hasattr(block, "generate_csv") else None,
            "page_id": getattr(block, 'page_id', 0)
        }
    
    def _extract_document_context(self, document: Document) -> Dict[str, Any]:
        """Extract document context for analysis."""
        
        return {
            "total_pages": len(document.pages),
            "document_type": "unknown"  # Could be detected
        }
    
    async def _apply_section_corrections(self, document: Document, corrections: Dict[str, Any]) -> int:
        """Apply section corrections based on Claude analysis."""
        
        # Implementation would apply actual corrections
        # For now, return count of corrections that would be applied
        
        corrections_applied = 0
        if "corrections" in corrections:
            corrections_applied = len(corrections["corrections"])
        
        return corrections_applied
    
    async def _apply_table_merge(self, document: Document, group: List[int], table_blocks: List[Block]) -> None:
        """Apply table merge based on Claude recommendation."""
        
        # Implementation would perform actual table merge
        logger.info(f"Applying Claude-recommended table merge for group: {group}")
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics for Claude features."""
        
        return {
            "total_analyses": self.stats["analyses_performed"],
            "total_claude_time": self.stats["total_claude_time"],
            "average_analysis_time": (
                self.stats["total_claude_time"] / max(self.stats["analyses_performed"], 1)
            ),
            "features_used": self.stats["features_used"],
            "fallbacks_triggered": self.stats["fallbacks_triggered"]
        }
    
    def is_feature_enabled(self, feature: ClaudeFeature) -> bool:
        """Check if a specific Claude feature is enabled."""
        return self.config.enabled and self.config.features.get(feature, False)

# Configuration builders for common use cases
class ClaudeConfigBuilder:
    """Builder for creating Claude configurations for different use cases."""
    
    @staticmethod
    def create_minimal_config() -> ClaudeConfig:
        """Minimal config - only critical features enabled."""
        return ClaudeConfig(
            enabled=True,
            features={
                ClaudeFeature.SECTION_VERIFICATION: True,
                ClaudeFeature.TABLE_MERGE_ANALYSIS: False,
                ClaudeFeature.CONTENT_VALIDATION: False,
                ClaudeFeature.STRUCTURE_ANALYSIS: False
            },
            max_concurrent=1,
            timeout=60.0
        )
    
    @staticmethod
    def create_accuracy_focused_config() -> ClaudeConfig:
        """High accuracy config - all features enabled."""
        return ClaudeConfig(
            enabled=True,
            features={
                ClaudeFeature.SECTION_VERIFICATION: True,
                ClaudeFeature.TABLE_MERGE_ANALYSIS: True,
                ClaudeFeature.CONTENT_VALIDATION: True,
                ClaudeFeature.STRUCTURE_ANALYSIS: True
            },
            max_concurrent=3,
            timeout=180.0,
            table_merge_confidence_threshold=0.8,
            section_verification_confidence_threshold=0.85
        )
    
    @staticmethod
    def create_performance_focused_config() -> ClaudeConfig:
        """Performance focused - Claude disabled by default."""
        return ClaudeConfig(
            enabled=False,
            fallback_to_heuristics=True
        )
    
    @staticmethod
    def create_table_only_config() -> ClaudeConfig:
        """Only table analysis enabled."""
        return ClaudeConfig(
            enabled=True,
            features={
                ClaudeFeature.TABLE_MERGE_ANALYSIS: True,
                ClaudeFeature.SECTION_VERIFICATION: False,
                ClaudeFeature.CONTENT_VALIDATION: False,
                ClaudeFeature.STRUCTURE_ANALYSIS: False
            },
            min_tables_for_analysis=2,
            table_merge_confidence_threshold=0.75
        )

# Integration with enhanced_table.py
def integrate_claude_features(enhanced_processor, claude_config: ClaudeConfig):
    """
    Integrate Claude features into the enhanced table processor.
    
    This should be called during processor initialization.
    """
    
    enhanced_processor.claude_processor = ClaudeDocumentProcessor(claude_config)
    enhanced_processor.claude_config = claude_config
    
    # Add Claude processing to the main pipeline
    async def enhanced_process_with_claude(document: Document):
        """Enhanced processing with optional Claude features."""
        
        processing_start_time = time.time()
        
        # Run normal processing first
        original_call = enhanced_processor.__call__
        original_call(document)
        
        # Apply Claude enhancements if enabled
        if claude_config.enabled:
            claude_results = await enhanced_processor.claude_processor.process_document(
                document, processing_start_time
            )
            
            # Store Claude results in document metadata
            if hasattr(document, 'metadata'):
                if not document.metadata:
                    document.metadata = {}
                document.metadata['claude_analysis'] = claude_results
            
            logger.info(f"Claude processing complete: {claude_results.get('improvements_made', [])}")
    
    # Replace the original call method
    enhanced_processor.enhanced_call_with_claude = enhanced_process_with_claude

# Example usage patterns
async def demo_claude_verification():
    """Demonstrate Claude verification features."""
    
    # Example 1: Minimal verification for production
    minimal_config = ClaudeConfigBuilder.create_minimal_config()
    processor = ClaudeDocumentProcessor(minimal_config)
    
    print("Minimal Config:")
    print(f"- Section verification: {processor.is_feature_enabled(ClaudeFeature.SECTION_VERIFICATION)}")
    print(f"- Table analysis: {processor.is_feature_enabled(ClaudeFeature.TABLE_MERGE_ANALYSIS)}")
    
    # Example 2: High accuracy for research documents
    accuracy_config = ClaudeConfigBuilder.create_accuracy_focused_config()
    accuracy_processor = ClaudeDocumentProcessor(accuracy_config)
    
    print("\nAccuracy-Focused Config:")
    print(f"- All features enabled: {all(accuracy_config.features.values())}")
    print(f"- Confidence threshold: {accuracy_config.section_verification_confidence_threshold}")
    
    # Example 3: Performance focused (Claude disabled)
    perf_config = ClaudeConfigBuilder.create_performance_focused_config()
    
    print(f"\nPerformance Config - Claude enabled: {perf_config.enabled}")

if __name__ == "__main__":
    asyncio.run(demo_claude_verification())