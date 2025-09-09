# 008 PDF Sub-Agent Implementation Tasks

## Overview
Transform the current code-based PDF extraction pipeline to a sub-agent orchestrated architecture that can achieve semantic understanding and meet the 90% gold standard validation threshold.

## Current State Analysis
- **Current Architecture**: Code-based processors with pattern matching
- **Current Stage 3 Score**: 77.9% (failing to meet 90% threshold)
- **Root Cause**: Lack of semantic understanding in code-based approach
- **Solution**: Implement LLM-powered sub-agents for intelligent processing

## Implementation Tasks

### Phase 1: Core Sub-Agent Infrastructure
- [ ] **Task 1.1**: Create base PDF sub-agent template
  - [ ] Create `/home/graham/.claude/agents/pdf_base.md` with common PDF processing patterns
  - [ ] Create `/home/graham/.claude/agents/workers/pdf_base_worker.py` with shared utilities
  - [ ] Include ArangoDB knowledge-first pattern
  - [ ] Add gold standard validation hooks
  - [ ] Implement error learning and storage

- [ ] **Task 1.2**: Create PDF dispatcher sub-agent
  - [ ] Create `/home/graham/.claude/agents/pdf_dispatcher.md`
  - [ ] Create `/home/graham/.claude/agents/workers/pdf_dispatcher_worker.py`
  - [ ] Implement concurrent Claude instance management
  - [ ] Add rate limiting and error handling
  - [ ] Create batch processing capabilities

### Phase 2: Annotation Processing Sub-Agents
- [ ] **Task 2.1**: Create annotation extractor sub-agent
  - [ ] Create `/home/graham/.claude/agents/pdf_annotation_extractor.md`
  - [ ] Create `/home/graham/.claude/agents/workers/pdf_annotation_extractor_worker.py`
  - [ ] Port existing `AnnotationExtractor` logic
  - [ ] Add knowledge storage for annotation patterns
  - [ ] Implement visual categorization without interpretation

- [ ] **Task 2.2**: Create annotation interpreter sub-agent
  - [ ] Create `/home/graham/.claude/agents/pdf_annotation_interpreter.md`
  - [ ] Create `/home/graham/.claude/agents/workers/pdf_annotation_interpreter_worker.py`
  - [ ] Implement LLM-based annotation understanding
  - [ ] Create pattern learning from annotations
  - [ ] Store learned patterns in ArangoDB

### Phase 3: Block Analysis Sub-Agents
- [ ] **Task 3.1**: Create section header validator sub-agent
  - [ ] Create `/home/graham/.claude/agents/pdf_section_header.md`
  - [ ] Create `/home/graham/.claude/agents/workers/pdf_section_header_worker.py`
  - [ ] Implement semantic header validation using LLM
  - [ ] Query historical header patterns from ArangoDB
  - [ ] Handle edge cases (commas, "As", "For", split headers)
  - [ ] Return confidence scores for each header

- [ ] **Task 3.2**: Create table analyzer sub-agent
  - [ ] Create `/home/graham/.claude/agents/pdf_table_analyzer.md`
  - [ ] Create `/home/graham/.claude/agents/workers/pdf_table_analyzer_worker.py`
  - [ ] Implement deep table structure analysis
  - [ ] Detect table headers, cells, and relationships
  - [ ] Handle complex table layouts
  - [ ] Store table patterns for future use

- [ ] **Task 3.3**: Create table merge decision sub-agent
  - [ ] Create `/home/graham/.claude/agents/pdf_table_merge.md`
  - [ ] Create `/home/graham/.claude/agents/workers/pdf_table_merge_worker.py`
  - [ ] Analyze split tables for merge candidates
  - [ ] Use LLM to understand table continuity
  - [ ] Apply annotation guidance for merging
  - [ ] Return merge recommendations with confidence

- [ ] **Task 3.4**: Create content categorizer sub-agent
  - [ ] Create `/home/graham/.claude/agents/pdf_content_categorizer.md`
  - [ ] Create `/home/graham/.claude/agents/workers/pdf_content_categorizer_worker.py`
  - [ ] Implement semantic content grouping
  - [ ] Categories: overview, technical_details, operation, interface, configuration_notes
  - [ ] Use LLM to understand content relationships
  - [ ] Build nested content structures

### Phase 4: Gold Standard Validation Sub-Agent
- [ ] **Task 4.1**: Create gold standard validator sub-agent
  - [ ] Create `/home/graham/.claude/agents/pdf_gold_standard.md`
  - [ ] Create `/home/graham/.claude/agents/workers/pdf_gold_standard_worker.py`
  - [ ] Implement multi-stage validation (Stage 1-6)
  - [ ] Calculate similarity scores
  - [ ] Generate detailed validation reports
  - [ ] Store validation results for learning

### Phase 5: Pipeline Integration (DAG-Based)
- [ ] **Task 5.1**: Implement DAG execution engine
  - [ ] Create `/home/graham/workspace/experiments/extractor/src/extractor/dag_engine.py`
  - [ ] Implement DAGNode and PDFProcessingDAG classes
  - [ ] Add dependency resolution and parallel execution
  - [ ] Implement retry logic for failed nodes
  - [ ] Add progress tracking and visualization

- [ ] **Task 5.2**: Create DAG-based sub-agent orchestrator
  - [ ] Create `/home/graham/workspace/experiments/extractor/src/extractor/subagent_dag_orchestrator.py`
  - [ ] Build dynamic DAG based on PDF content
  - [ ] Implement parallel node execution with asyncio
  - [ ] Add resource pooling (max 10 concurrent LLM calls)
  - [ ] Implement caching at node level
  - [ ] Add real-time progress monitoring

- [ ] **Task 5.3**: Update unified_extractor.py for DAG architecture
  - [ ] Add DAG mode flag (--use-dag)
  - [ ] Replace sequential processing with DAG execution
  - [ ] Implement result aggregation from DAG nodes
  - [ ] Maintain backward compatibility
  - [ ] Add performance metrics collection

- [ ] **Task 5.3**: Update pipeline configuration
  - [ ] Add sub-agent enable/disable flags to PipelineConfig
  - [ ] Create sub-agent presets (fast, balanced, quality)
  - [ ] Add sub-agent specific parameters
  - [ ] Update CLI arguments in pipeline_orchestrator.py

### Phase 6: Testing and Validation
- [ ] **Task 6.1**: Create sub-agent test harness
  - [ ] Create `/home/graham/workspace/experiments/extractor/tests/test_subagents.py`
  - [ ] Test each sub-agent individually
  - [ ] Test sub-agent orchestration
  - [ ] Verify gold standard validation passes 90%

- [ ] **Task 6.2**: Update gold standards for sub-agent outputs
  - [ ] Create Stage 2 gold standard with sub-agent corrections
  - [ ] Create Stage 3 gold standard with semantic grouping
  - [ ] Create Stage 5 gold standard with LLM enhancements
  - [ ] Document gold standard update process

### Phase 7: Documentation and Deployment
- [ ] **Task 7.1**: Update documentation
  - [ ] Update README_PIPELINE.md with sub-agent architecture
  - [ ] Create sub-agent usage guide
  - [ ] Document sub-agent debugging procedures
  - [ ] Add performance benchmarks

- [ ] **Task 7.2**: Create migration guide
  - [ ] Document migration from processor to sub-agent architecture
  - [ ] Create compatibility layer for existing code
  - [ ] Add rollback procedures
  - [ ] Document known limitations

## Code Implementation Examples

### Example: pdf_section_header_worker.py
```python
import asyncio
from typing import Dict, List, Optional
from pathlib import Path
import typer
from loguru import logger
from rich import print as rprint
from rich.panel import Panel
from rich.syntax import Syntax
import json

# ArangoDB integration
from arango_tools_worker import semantic_search, upsert, get_client

# LLM integration  
from litellm import acompletion

app = typer.Typer(
    name="pdf_section_header",
    help="PDF Section Header Validator - Semantic understanding of headers"
)

class PDFSectionHeaderWorker:
    """Validates and classifies PDF section headers using semantic understanding."""
    
    def __init__(self):
        self.collection = "pdf_section_headers"
        self.patterns_collection = "section_header_patterns"
        
    async def validate_header(self, block: Dict, context: List[Dict]) -> Dict:
        """Validate if a block is truly a section header.
        
        Args:
            block: The block to validate
            context: Surrounding blocks for context
            
        Returns:
            Dict with validation result and confidence
        """
        # First check knowledge base
        similar_headers = await self._search_similar_headers(block['text'])
        
        if similar_headers and similar_headers[0]['confidence'] > 0.9:
            logger.info(f"Found high-confidence match in knowledge base")
            return similar_headers[0]
            
        # Use LLM for semantic validation
        result = await self._llm_validate_header(block, context)
        
        # Store result for future use
        await self._store_validation_result(block, result)
        
        return result
        
    async def _search_similar_headers(self, text: str) -> List[Dict]:
        """Search for similar headers in knowledge base."""
        results = semantic_search(
            collection=self.patterns_collection,
            query=text,
            text_field='header_text',
            top_k=5
        )
        return results.get('results', [])
        
    async def _llm_validate_header(self, block: Dict, context: List[Dict]) -> Dict:
        """Use LLM to validate header semantically."""
        prompt = f"""Analyze if this text block is a section header in a technical document.

Block to analyze:
Text: {block['text']}
Font size: {block.get('font_size', 'unknown')}
Font weight: {block.get('font_weight', 'unknown')}

Context (surrounding blocks):
{json.dumps(context, indent=2)}

Consider:
1. Does it introduce a new section/topic?
2. Is it a complete thought or fragment?
3. Headers ending with commas are usually NOT headers
4. Phrases starting with "As" or "For" are often NOT headers
5. Look for semantic markers of headers vs regular text

Respond with JSON:
{{
    "is_header": true/false,
    "confidence": 0.0-1.0,
    "reasoning": "explanation",
    "suggested_type": "SectionHeader" or "Text"
}}"""

        response = await acompletion(
            model="claude-3-5-sonnet-20241022",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        return json.loads(response.choices[0].message.content)
        
    async def _store_validation_result(self, block: Dict, result: Dict):
        """Store validation result in knowledge base."""
        doc = {
            "header_text": block['text'],
            "is_header": result['is_header'],
            "confidence": result['confidence'],
            "reasoning": result['reasoning'],
            "font_size": block.get('font_size'),
            "font_weight": block.get('font_weight'),
            "timestamp": datetime.now().isoformat()
        }
        
        upsert(
            collection=self.patterns_collection,
            search={"header_text": block['text']},
            update={"usage_count": 1},
            create=doc
        )

async def working_usage():
    """Demonstrate proper usage of the section header validator."""
    worker = PDFSectionHeaderWorker()
    
    # Example blocks
    test_blocks = [
        {"text": "1. INTRODUCTION", "font_size": 14, "font_weight": "bold"},
        {"text": "For any HW configuration,", "font_size": 12},
        {"text": "As shown in the diagram", "font_size": 12},
        {"text": "2.3 Technical Implementation", "font_size": 13, "font_weight": "bold"}
    ]
    
    for block in test_blocks:
        result = await worker.validate_header(block, test_blocks)
        rprint(Panel(
            f"Text: {block['text']}\n"
            f"Is Header: {result['is_header']}\n"
            f"Confidence: {result['confidence']:.2f}\n"
            f"Reasoning: {result['reasoning']}",
            title="Validation Result"
        ))

async def debug_function():
    """Debug function for testing edge cases."""
    worker = PDFSectionHeaderWorker()
    
    # Test edge cases
    edge_cases = [
        {"text": "TABLE 1: System Configuration", "font_size": 12},
        {"text": "Figure 3.2: Block Diagram", "font_size": 11},
        {"text": "Note:", "font_size": 12, "font_weight": "bold"},
        {"text": "APPENDIX A", "font_size": 14, "font_weight": "bold"}
    ]
    
    for block in edge_cases:
        result = await worker.validate_header(block, [])
        print(f"\nEdge case: '{block['text']}'")
        print(f"Result: {json.dumps(result, indent=2)}")

if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "working"
    
    if mode == "debug":
        print("Running debug mode...")
        asyncio.run(debug_function())
    else:
        print("Running working usage mode...")
        asyncio.run(working_usage())
```

### Example: pdf_content_categorizer_worker.py
```python
import asyncio
from typing import Dict, List, Optional
from pathlib import Path
import typer
from loguru import logger
from rich import print as rprint
import json

# ArangoDB integration
from arango_tools_worker import semantic_search, graph_search, upsert

# LLM integration
from litellm import acompletion

app = typer.Typer(
    name="pdf_content_categorizer",
    help="Categorize PDF content into semantic groups"
)

class PDFContentCategorizerWorker:
    """Categorizes PDF content blocks into semantic groups."""
    
    CATEGORIES = [
        "overview",
        "technical_details", 
        "operation",
        "interface",
        "configuration_notes"
    ]
    
    async def categorize_section_content(self, 
                                       section_header: Dict,
                                       content_blocks: List[Dict]) -> Dict:
        """Categorize content blocks under a section into semantic groups.
        
        Args:
            section_header: The section header block
            content_blocks: List of content blocks in the section
            
        Returns:
            Dict with categorized content structure
        """
        # Check knowledge base for similar sections
        similar_sections = await self._find_similar_sections(section_header['text'])
        
        if similar_sections:
            logger.info(f"Found {len(similar_sections)} similar sections in KB")
            # Use most similar section's structure as template
            template = similar_sections[0]
        else:
            template = None
            
        # Categorize content using LLM
        categorized = await self._llm_categorize_content(
            section_header, 
            content_blocks,
            template
        )
        
        # Store categorization for learning
        await self._store_categorization(section_header, categorized)
        
        return categorized
        
    async def _llm_categorize_content(self, 
                                    header: Dict,
                                    blocks: List[Dict],
                                    template: Optional[Dict]) -> Dict:
        """Use LLM to semantically categorize content."""
        
        # Prepare blocks for analysis
        block_texts = []
        for i, block in enumerate(blocks):
            block_texts.append(f"{i}. [{block['type']}] {block.get('text', '')[:200]}...")
            
        template_str = ""
        if template:
            template_str = f"\nSimilar section structure found:\n{json.dumps(template['structure'], indent=2)}"
            
        prompt = f"""Categorize the following content blocks from section "{header['text']}" into semantic groups.

Available categories:
- overview: High-level description, introduction, purpose
- technical_details: Implementation details, algorithms, specifications  
- operation: How it works, procedures, operational notes
- interface: APIs, tables, data structures, interfaces
- configuration_notes: Setup, configuration, parameters

Content blocks:
{chr(10).join(block_texts)}
{template_str}

Analyze the semantic meaning of each block and group them appropriately.
Return JSON with the structure:
{{
    "overview": [<list of block indices>],
    "technical_details": [<list of block indices>],
    "operation": [<list of block indices>],
    "interface": <index if single table, null otherwise>,
    "configuration_notes": [<list of block indices>]
}}"""

        response = await acompletion(
            model="claude-3-5-sonnet-20241022",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        
        categorization = json.loads(response.choices[0].message.content)
        
        # Build the final structure
        result = {
            "type": "section",
            "header": header,
            "content": {}
        }
        
        for category in self.CATEGORIES:
            if category == "interface" and categorization.get(category) is not None:
                # Single interface element
                idx = categorization[category]
                result["content"][category] = blocks[idx]
            elif category in categorization and categorization[category]:
                # List of elements
                items = []
                for idx in categorization[category]:
                    if idx < len(blocks):
                        items.append(blocks[idx])
                if items:
                    result["content"][category] = items
                    
        return result

async def working_usage():
    """Demonstrate content categorization."""
    worker = PDFContentCategorizerWorker()
    
    # Example section
    header = {"type": "SectionHeader", "text": "3.1 BHT Implementation", "level": 2}
    blocks = [
        {"type": "Text", "text": "BHT is implemented as a direct-mapped cache..."},
        {"type": "Text", "text": "The implementation uses a 2-bit saturating counter..."},
        {"type": "Figure", "text": "Figure 3.1: BHT Block Diagram"},
        {"type": "Text", "text": "During operation, the BHT indexes using lower PC bits..."},
        {"type": "Table", "text": "TABLE I\nBHT INTERFACE SIGNALS", "cells": [...]},
        {"type": "Text", "text": "Configuration requires setting BHT_SIZE parameter..."}
    ]
    
    result = await worker.categorize_section_content(header, blocks)
    rprint(Panel(
        json.dumps(result, indent=2),
        title="Categorization Result"
    ))

if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "working"
    
    if mode == "debug":
        print("Running debug mode...")
        asyncio.run(debug_function())
    else:
        print("Running working usage mode...")
        asyncio.run(working_usage())
```

## Expected Outcomes

1. **Stage 1 Validation**: 100% match (already achieved)
2. **Stage 2 Validation**: >90% match with sub-agent enhanced extraction
3. **Stage 3 Validation**: >90% match with semantic content grouping
4. **Stage 5 Validation**: >95% match with full LLM enhancement

## Success Metrics

- [ ] All sub-agents implemented and tested
- [ ] Gold standard validation passes 90% for all stages
- [ ] Sub-agent orchestration handles concurrent processing
- [ ] Knowledge base captures and reuses patterns
- [ ] Performance acceptable (<5 seconds per page)
- [ ] Error recovery handles sub-agent failures gracefully

## Timeline Estimate

- Phase 1-2: 2 days (Infrastructure and annotation agents)
- Phase 3: 3 days (Block analysis agents) 
- Phase 4: 1 day (Gold standard validator)
- Phase 5: 2 days (Pipeline integration)
- Phase 6-7: 2 days (Testing and documentation)

**Total: ~10 days of focused development**

## Risk Mitigation

1. **LLM Rate Limits**: Implement caching and batching
2. **Latency**: Use concurrent processing and knowledge base
3. **Accuracy**: Iterative testing with gold standards
4. **Complexity**: Start with MVP, add features incrementally
5. **Fallback**: Maintain processor-based pipeline as fallback