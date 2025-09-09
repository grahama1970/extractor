# PDF Extraction Sub-Agent Architecture

## Overview

This document outlines a sub-agent architecture for PDF extraction validation, replacing the embedded validation approach with specialized sub-agents that analyze PDF blocks after marker extraction.

## Architecture Benefits

### Current Approach Limitations
1. **Schema Constraints**: Marker's strict Pydantic models limit validation data storage
2. **Monolithic Processing**: All validation logic embedded in processors
3. **Limited Analysis**: Can't do deep analysis without blocking extraction
4. **Difficult Maintenance**: Validation logic scattered across processors

### Sub-Agent Approach Benefits
1. **Decoupled Analysis**: Deep analysis without blocking extraction pipeline
2. **Specialized Expertise**: Each agent excels at one block type
3. **Parallel Processing**: Analyze multiple blocks concurrently
4. **Easy Extension**: Add new agents without modifying core processors
5. **Better LLM Usage**: Use appropriate models for each task

## The Agent Chain

```
PDF Input
    ↓
Stage 1: Annotation Learning
    ↓
Stage 2: Marker Extraction (minimal tweaks)
    ↓
Filter & Categorize Blocks
    ↓
Parallel Sub-Agent Analysis:
    ├─→ Table Analyzer Agent
    ├─→ Figure Describer Agent
    ├─→ Section Validator Agent
    ├─→ Text Quality Agent
    └─→ List Structure Agent
    ↓
Merge Analysis Results
    ↓
Stage 3: Structural Corrections
    ↓
ArangoDB Import
```

## Sub-Agent Specifications

### 1. Table Analyzer Agent
**Purpose**: Deep analysis of table blocks
**Input**: List of table blocks from marker
**Analysis**:
- Table structure validation
- Cell content classification
- Missing data detection
- Header row identification
- Column type inference
- Relationship to surrounding text
**Output**: Enhanced table metadata with confidence scores

### 2. Figure Describer Agent
**Purpose**: Generate descriptions and validate figure blocks
**Input**: List of figure blocks with image data
**Analysis**:
- Generate detailed figure descriptions
- Identify figure type (chart, diagram, photo, etc.)
- Extract text from figures (OCR)
- Validate caption associations
- Detect mislabeled tables as figures
**Output**: Figure descriptions and validation results

### 3. Section Validator Agent
**Purpose**: Validate section hierarchy and structure
**Input**: List of section headers and their content blocks
**Analysis**:
- Validate section numbering consistency
- Check hierarchy depth
- Detect orphaned headers
- Identify missing sections
- Validate content-header relationships
**Output**: Section hierarchy validation report

### 4. Text Quality Agent
**Purpose**: Assess text block quality and coherence
**Input**: List of text blocks
**Analysis**:
- Detect truncated sentences
- Identify OCR errors
- Check paragraph coherence
- Detect page boundary issues
- Language consistency
**Output**: Text quality scores and correction suggestions

### 5. List Structure Agent
**Purpose**: Validate list structures and relationships
**Input**: List blocks and surrounding context
**Analysis**:
- Validate list continuity
- Check numbering/bullet consistency
- Detect split lists
- Identify nested list issues
- Validate list-to-text transitions
**Output**: List structure validation and merge suggestions

## JSON Handoff Format

### Marker → Agent Orchestrator
```json
{
  "document_id": "QB50_1978.pdf",
  "extraction_timestamp": "2024-01-15T10:30:00Z",
  "blocks": [
    {
      "block_id": "block_001",
      "type": "Table",
      "page": 1,
      "bbox": [100, 200, 500, 400],
      "content": {...},
      "metadata": {...}
    },
    {
      "block_id": "block_002",
      "type": "Figure",
      "page": 1,
      "bbox": [100, 450, 500, 650],
      "image_path": "/tmp/figure_001.png",
      "metadata": {...}
    }
  ],
  "annotations": {
    "learned_patterns": [...],
    "gold_standard_hints": [...]
  }
}
```

### Agent → Orchestrator
```json
{
  "agent": "table_analyzer",
  "block_id": "block_001",
  "analysis": {
    "structure_valid": true,
    "confidence": 0.85,
    "issues": [
      {
        "type": "missing_header",
        "severity": "medium",
        "suggestion": "First row appears to be headers"
      }
    ],
    "enhanced_metadata": {
      "column_count": 4,
      "row_count": 10,
      "has_headers": false,
      "column_types": ["string", "number", "date", "string"]
    }
  },
  "processing_time_ms": 150
}
```

### Final Merged Result
```json
{
  "document_id": "QB50_1978.pdf",
  "blocks_analyzed": 45,
  "agent_results": {
    "table_analyzer": {...},
    "figure_describer": {...},
    "section_validator": {...}
  },
  "quality_summary": {
    "overall_confidence": 0.78,
    "critical_issues": 2,
    "warnings": 8,
    "suggestions": 15
  },
  "structural_corrections": [
    {
      "action": "merge_blocks",
      "block_ids": ["block_003", "block_004"],
      "reason": "Split paragraph detected"
    }
  ]
}
```

## Implementation Plan

### Phase 1: Core Infrastructure
1. Create base agent class with standard interface
2. Implement agent orchestrator
3. Create block filtering and routing logic
4. Set up parallel processing framework

### Phase 2: Essential Agents
1. Implement Table Analyzer (highest impact)
2. Implement Figure Describer (addresses misclassification)
3. Implement Section Validator (for hierarchy)

### Phase 3: Quality Agents
1. Implement Text Quality Agent
2. Implement List Structure Agent
3. Add specialized agents as needed

### Phase 4: Integration
1. Integrate with existing pipeline
2. Update gold standard validation
3. Performance optimization
4. Add monitoring and metrics

## Agent Communication Protocol

### Agent Invocation
```python
# Example orchestrator code
async def analyze_document(marker_output: dict) -> dict:
    # Filter blocks by type
    table_blocks = [b for b in marker_output["blocks"] if b["type"] == "Table"]
    figure_blocks = [b for b in marker_output["blocks"] if b["type"] == "Figure"]
    
    # Create analysis tasks
    tasks = []
    if table_blocks:
        tasks.append(invoke_agent("table_analyzer", table_blocks))
    if figure_blocks:
        tasks.append(invoke_agent("figure_describer", figure_blocks))
    
    # Run agents in parallel
    results = await asyncio.gather(*tasks)
    
    # Merge results
    return merge_agent_results(results)
```

### Agent Interface
```python
class PDFAnalysisAgent:
    """Base class for PDF analysis sub-agents"""
    
    async def analyze(self, blocks: List[dict], context: dict) -> dict:
        """Analyze blocks and return enhanced metadata"""
        raise NotImplementedError
    
    def get_capabilities(self) -> dict:
        """Return agent capabilities for routing"""
        return {
            "block_types": [],
            "max_blocks": 100,
            "requires_gpu": False
        }
```

## Performance Considerations

1. **Parallel Processing**: Analyze multiple blocks concurrently
2. **Batching**: Group similar blocks for efficient LLM usage
3. **Caching**: Cache repeated patterns (e.g., table structures)
4. **Model Selection**: Use appropriate models for each task
   - Small models for structure validation
   - Vision models for figure description
   - Larger models for complex analysis

## Monitoring and Metrics

Track per agent:
- Processing time
- Success rate
- Confidence distribution
- Error types
- Resource usage

## Future Extensions

1. **Learning Agents**: Agents that improve from corrections
2. **Domain-Specific Agents**: Legal, medical, scientific specialists
3. **Cross-Document Agents**: Consistency across document sets
4. **Interactive Agents**: Request human input for ambiguous cases
5. **Synthesis Agent**: Combine all analyses into actionable insights

## Conclusion

The sub-agent architecture provides a flexible, scalable approach to PDF validation that:
- Works around marker's schema limitations
- Enables deep, specialized analysis
- Allows parallel processing
- Facilitates easy extension and maintenance
- Provides better visibility into the validation process

This approach aligns with the successful pattern demonstrated in cc_executor while addressing the specific needs of PDF extraction validation.