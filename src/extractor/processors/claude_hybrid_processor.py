"""
Claude Hybrid Processor - Intelligent routing between Marker, Surya, and Claude.
Module: claude_hybrid_processor.py

This processor demonstrates how to optimally use each component:
- Marker: Pipeline and basic structure
- Surya: Specialized vision models  
- Claude: Complex reasoning and enhancement
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import numpy as np
from loguru import logger

from extractor.processors import BaseProcessor
from extractor.schema import BlockTypes
from extractor.schema.blocks import Block, Equation, Table, Code
from extractor.schema.document import Document


class ComplexityLevel(Enum):
    """Complexity levels for routing decisions."""
    SIMPLE = "simple"      # Use Marker/Surya
    MODERATE = "moderate"  # Use Surya + verification
    COMPLEX = "complex"    # Use Claude primary
    CRITICAL = "critical"  # Use Claude with iteration


@dataclass
class ProcessingRoute:
    """Routing decision for a block."""
    block_id: str
    complexity: ComplexityLevel
    processor: str
    confidence: float
    reasoning: str


class ClaudeHybridProcessor(BaseProcessor):
    """
    Intelligent processor that routes tasks between Marker, Surya, and Claude
    based on complexity and task requirements.
    """
    
    # Complexity thresholds
    MATH_COMPLEXITY_THRESHOLD = 0.7
    TABLE_COMPLEXITY_THRESHOLD = 0.6
    CODE_COMPLEXITY_THRESHOLD = 0.8
    
    def __init__(
        self,
        use_claude_for_math: bool = True,
        use_claude_for_complex_tables: bool = True,
        use_claude_for_code_completion: bool = True,
        claude_service: Optional[Any] = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.use_claude_for_math = use_claude_for_math
        self.use_claude_for_complex_tables = use_claude_for_complex_tables
        self.use_claude_for_code_completion = use_claude_for_code_completion
        self.claude_service = claude_service
        self.routing_decisions: List[ProcessingRoute] = []
    
    def __call__(self, document: Document):
        """Process document with intelligent routing."""
        # Analyze document complexity
        complexity_map = self._analyze_document_complexity(document)
        
        # Route each block to appropriate processor
        for page in document.pages:
            for block in page.contained_blocks(document):
                route = self._determine_route(block, complexity_map)
                self.routing_decisions.append(route)
                
                if route.complexity in [ComplexityLevel.COMPLEX, ComplexityLevel.CRITICAL]:
                    self._process_with_claude(block, document, route)
                elif route.complexity == ComplexityLevel.MODERATE:
                    self._process_with_verification(block, document)
                # SIMPLE blocks use default Marker processing
        
        # Log routing statistics
        self._log_routing_stats()
    
    def _analyze_document_complexity(self, document: Document) -> Dict[str, float]:
        """Analyze overall document complexity for routing decisions."""
        complexity_map = {}
        
        for page in document.pages:
            for block in page.contained_blocks(document):
                if block.block_type == BlockTypes.Equation:
                    complexity_map[block.id] = self._calculate_math_complexity(block)
                elif block.block_type == BlockTypes.Table:
                    complexity_map[block.id] = self._calculate_table_complexity(block)
                elif block.block_type == BlockTypes.Code:
                    complexity_map[block.id] = self._calculate_code_complexity(block)
                else:
                    complexity_map[block.id] = 0.0
        
        return complexity_map
    
    def _calculate_math_complexity(self, equation: Equation) -> float:
        """Calculate complexity score for math equations."""
        complexity = 0.0
        
        # Check for complex patterns
        if hasattr(equation, 'text'):
            text = equation.text
            # Multi-line equations
            if '\n' in text:
                complexity += 0.3
            # Matrix/array notation
            if any(pattern in text for pattern in ['\\begin{', '\\matrix', '\\array']):
                complexity += 0.4
            # Integrals, summations
            if any(pattern in text for pattern in ['\\int', '\\sum', '\\prod']):
                complexity += 0.3
            # Custom commands
            if '\\newcommand' in text or '\\def' in text:
                complexity += 0.5
        
        # Check confidence from Texify
        if hasattr(equation, 'confidence') and equation.confidence < 0.8:
            complexity += 0.3
        
        return min(complexity, 1.0)
    
    def _calculate_table_complexity(self, table: Table) -> float:
        """Calculate complexity score for tables."""
        complexity = 0.0
        
        if hasattr(table, 'cells'):
            # Merged cells
            if hasattr(table, 'merged_cells') and table.merged_cells:
                complexity += 0.4
            
            # Large tables
            if len(table.cells) > 10:
                complexity += 0.2
            
            # Nested structure indicators
            cell_texts = [str(cell) for row in table.cells for cell in row]
            if any('<' in text or '>' in text for text in cell_texts):
                complexity += 0.3
            
            # Multi-line cells
            if any('\n' in text for text in cell_texts):
                complexity += 0.2
        
        return min(complexity, 1.0)
    
    def _calculate_code_complexity(self, code: Code) -> float:
        """Calculate complexity score for code blocks."""
        complexity = 0.0
        
        if hasattr(code, 'text'):
            text = code.text
            lines = text.split('\n')
            
            # Incomplete code (no proper ending)
            if not text.strip().endswith(('}', ')', ';', ':')):
                complexity += 0.4
            
            # Syntax errors detected
            if hasattr(code, 'syntax_errors') and code.syntax_errors:
                complexity += 0.5
            
            # Missing imports/dependencies
            if 'NameError' in text or 'ImportError' in text:
                complexity += 0.3
            
            # Large code blocks
            if len(lines) > 50:
                complexity += 0.2
        
        return min(complexity, 1.0)
    
    def _determine_route(
        self, 
        block: Block, 
        complexity_map: Dict[str, float]
    ) -> ProcessingRoute:
        """Determine the optimal processing route for a block."""
        block_complexity = complexity_map.get(str(block.id), 0.0)
        
        # Math routing
        if block.block_type == BlockTypes.Equation and self.use_claude_for_math:
            if block_complexity >= self.MATH_COMPLEXITY_THRESHOLD:
                return ProcessingRoute(
                    block_id=str(block.id),
                    complexity=ComplexityLevel.COMPLEX,
                    processor="claude",
                    confidence=0.9,
                    reasoning=f"Complex math equation (score: {block_complexity:.2f})"
                )
        
        # Table routing
        elif block.block_type == BlockTypes.Table and self.use_claude_for_complex_tables:
            if block_complexity >= self.TABLE_COMPLEXITY_THRESHOLD:
                return ProcessingRoute(
                    block_id=str(block.id),
                    complexity=ComplexityLevel.COMPLEX,
                    processor="claude",
                    confidence=0.85,
                    reasoning=f"Complex table structure (score: {block_complexity:.2f})"
                )
        
        # Code routing
        elif block.block_type == BlockTypes.Code and self.use_claude_for_code_completion:
            if block_complexity >= self.CODE_COMPLEXITY_THRESHOLD:
                return ProcessingRoute(
                    block_id=str(block.id),
                    complexity=ComplexityLevel.CRITICAL,
                    processor="claude_iterative",
                    confidence=0.95,
                    reasoning=f"Incomplete/complex code (score: {block_complexity:.2f})"
                )
        
        # Default to simple processing
        return ProcessingRoute(
            block_id=str(block.id),
            complexity=ComplexityLevel.SIMPLE,
            processor="marker",
            confidence=0.7,
            reasoning="Standard complexity, use default processing"
        )
    
    def _process_with_claude(
        self, 
        block: Block, 
        document: Document, 
        route: ProcessingRoute
    ):
        """Process a block using Claude for enhanced understanding."""
        if not self.claude_service:
            logger.warning("Claude service not available, skipping enhancement")
            return
        
        logger.info(f"Processing {block.block_type} with Claude: {route.reasoning}")
        
        if block.block_type == BlockTypes.Equation:
            self._enhance_equation_with_claude(block, document)
        elif block.block_type == BlockTypes.Table:
            self._enhance_table_with_claude(block, document)
        elif block.block_type == BlockTypes.Code:
            self._enhance_code_with_claude(block, document, 
                                         iterative=route.complexity == ComplexityLevel.CRITICAL)
    
    def _enhance_equation_with_claude(self, equation: Equation, document: Document):
        """Use Claude to enhance equation understanding."""
        # Example implementation
        context = self._get_surrounding_context(equation, document)
        
        prompt = f"""
        Analyze this mathematical equation and provide:
        1. Corrected LaTeX if there are errors
        2. Explanation of what the equation represents
        3. Variable definitions from context
        
        Equation: {equation.text}
        Context: {context}
        """
        
        # This would call Claude service
        # enhanced = self.claude_service.process(prompt)
        # equation.enhanced_latex = enhanced.latex
        # equation.explanation = enhanced.explanation
        
    def _enhance_table_with_claude(self, table: Table, document: Document):
        """Use Claude to understand table semantics."""
        prompt = f"""
        Analyze this table structure and provide:
        1. Column relationships and data types
        2. Identify if it's a data table, comparison table, or other type'
        3. Extract key insights
        4. Suggest better structure if applicable
        
        Table data: {table.cells}
        """
        
        # This would call Claude service
        # understanding = self.claude_service.process(prompt)
        # table.semantic_type = understanding.table_type
        # table.column_types = understanding.column_types
        
    def _enhance_code_with_claude(
        self, 
        code: Code, 
        document: Document, 
        iterative: bool = False
    ):
        """Use Claude to complete and fix code."""
        context = self._get_surrounding_context(code, document)
        
        prompt = f"""
        Analyze this code block:
        1. Identify the programming language
        2. Complete any truncated portions
        3. Fix syntax errors
        4. Add missing imports
        5. Provide explanation of functionality
        
        Code: {code.text}
        Context: {context}
        """
        
        # This would call Claude service
        # if iterative:
        #     # Multiple rounds for complex code
        #     enhanced = self.claude_service.iterative_process(prompt, max_rounds=3)
        # else:
        #     enhanced = self.claude_service.process(prompt)
        
    def _process_with_verification(self, block: Block, document: Document):
        """Process with Surya/Marker but verify with Claude."""
        # Use default processing first
        # Then quick Claude verification
        pass
    
    def _get_surrounding_context(
        self, 
        block: Block, 
        document: Document, 
        before: int = 2, 
        after: int = 2
    ) -> str:
        """Get text context around a block."""
        page = document.get_page(block.page_id)
        blocks = page.contained_blocks(document)
        
        # Find block index
        block_idx = None
        for i, b in enumerate(blocks):
            if b.id == block.id:
                block_idx = i
                break
        
        if block_idx is None:
            return ""
        
        # Get surrounding blocks
        start = max(0, block_idx - before)
        end = min(len(blocks), block_idx + after + 1)
        
        context_blocks = blocks[start:end]
        context_text = "\n".join([
            b.raw_text(document) for b in context_blocks 
            if b.id != block.id and b.block_type == BlockTypes.Text
        ])
        
        return context_text[:1000]  # Limit context size
    
    def _log_routing_stats(self):
        """Log statistics about routing decisions."""
        total = len(self.routing_decisions)
        if total == 0:
            return
        
        by_complexity = {}
        by_processor = {}
        
        for route in self.routing_decisions:
            by_complexity[route.complexity.value] = by_complexity.get(route.complexity.value, 0) + 1
            by_processor[route.processor] = by_processor.get(route.processor, 0) + 1
        
        logger.info("Routing Statistics:")
        logger.info(f"  Total blocks: {total}")
        logger.info("  By complexity:")
        for level, count in by_complexity.items():
            logger.info(f"    {level}: {count} ({count/total*100:.1f}%)")
        logger.info("  By processor:")
        for proc, count in by_processor.items():
            logger.info(f"    {proc}: {count} ({count/total*100:.1f}%)")


# Example usage configuration
def create_optimized_processor(**kwargs):
    """Create an optimized processor with Claude enhancement."""
    return ClaudeHybridProcessor(
        use_claude_for_math=True,
        use_claude_for_complex_tables=True,
        use_claude_for_code_completion=True,
        # These thresholds can be tuned based on your needs
        math_complexity_threshold=0.7,
        table_complexity_threshold=0.6,
        code_complexity_threshold=0.8,
        **kwargs
    )