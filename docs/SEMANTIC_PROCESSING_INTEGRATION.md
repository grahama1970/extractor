# Semantic Processing Integration Guide

## Correct Architecture Flow

Based on user clarification, the proper semantic processing flow is:

### Stage 1: Marker Extraction
- Extract PDF with marker
- Identify suspicious headers using `SectionHeaderProcessor`
- Preserve all content exactly as extracted

### Stage 2: Section Creation  
- Run `organize_blocks_into_sections` to create section nodes
- Groups blocks under their section headers
- Creates hierarchical structure

### Stage 3: Semantic Processing (NEW)
- **Search ArangoDB for similar annotated examples FIRST**
- Run all workers on each section to generate full context:
  - Clean up text
  - Clean tables  
  - Merge continuous tables
  - Identify equations and code
  - Describe images based on image + section summary
- Feed entire section with ALL context into Claude sub-agent
- Process sections in batches for efficiency

## Key Implementation Points

### 1. Annotation Learning Loop
```
Extract Annotations → Save Clean PDF → Process → Store Patterns → Learn
```

The system searches for similar annotated sections to learn from past fixes:
- BM25 text search for similar content
- Semantic vector search for conceptual similarity  
- Graph traversal to find sections with similar annotations/fixes

### 2. Context Aggregation
Each section gets comprehensive context:
- Text blocks (cleaned)
- Tables (with merge analysis, pandas stats, Camelot results)
- Figures (with CLIP/vision descriptions)
- Annotations (human guidance)
- Surya predictions (visual model output)
- **Similar examples from knowledge base** (key differentiator)

### 3. Batch Processing
Sections are processed in configurable batches (default: 5) to:
- Optimize LLM API usage
- Enable parallel processing
- Maintain context coherence

## Integration into Pipeline

### Pipeline Configuration Update
```yaml
processors:
  # ... existing processors ...
  
  - name: step5_semantic_processing
    type: semantic_section_processing
    enabled: true
    settings:
      batch_size: 5
      use_knowledge_base: true
      llm_model: claude-3-sonnet-20240229
      search_similar_examples: true
```

### Processor Type Addition
```python
class ProcessorType(Enum):
    # ... existing types ...
    SEMANTIC_SECTION_PROCESSING = "semantic_section_processing"
```

### Pipeline Orchestrator Integration
In `unified_extractor.py`, after section organization:

```python
# After organizing into sections
if processor_config.type == ProcessorType.HIERARCHY_BUILDER:
    all_blocks = processor.process_blocks(all_blocks)
    section_structure = organize_blocks_into_sections(all_blocks)
    result['section_structure'] = section_structure
    
# NEW: Semantic section processing
elif processor_config.type == ProcessorType.SEMANTIC_SECTION_PROCESSING:
    from extractor.core.processors.semantic_section_processor import SemanticSectionProcessor
    
    semantic_processor = SemanticSectionProcessor(
        batch_size=processor_config.settings.get("batch_size", 5)
    )
    
    # Process sections with full semantic understanding
    enhanced_sections = await semantic_processor.process_sections(
        sections=result['section_structure']['sections'],
        annotations=result.get('annotations', {}).get('annotations', []),
        surya_data=result.get('surya_data')
    )
    
    # Update result with enhanced sections
    result['section_structure']['sections'] = enhanced_sections
    result['semantic_processing_applied'] = True
```

## Benefits of This Architecture

1. **Knowledge-First**: Searches for similar problems before processing
2. **Context-Rich**: All information available for intelligent decisions
3. **Learning System**: Stores successful patterns for future use
4. **Batch Efficient**: Processes multiple sections together
5. **Annotation-Guided**: Human annotations directly influence processing

## Example: Table Merge Decision

When the semantic processor encounters split table headers:

1. **Search Knowledge Base**: 
   - "section header: BHT tables: 2 split table headers annotation: Merge Table"
   - Finds similar cases where "Descripti|on" was fixed

2. **Gather Context**:
   - Pandas analysis shows compatible column structure
   - Spatial analysis shows tables at page boundary
   - Annotation says "Merge Table"
   - Similar examples show successful merges

3. **Claude Decision**:
   - Merges tables with high confidence
   - Fixes "Descripti|on" → "Description"
   - Stores pattern for future use

## Testing

```bash
# Test semantic processing
python src/extractor/core/processors/semantic_section_processor.py

# Test with real PDF
python src/extractor/core/processors/semantic_section_processor.py debug
```

## Next Steps

1. Add processor type to enum
2. Register processor in processor registry  
3. Add to pipeline configuration
4. Test with annotated PDFs
5. Monitor knowledge base growth