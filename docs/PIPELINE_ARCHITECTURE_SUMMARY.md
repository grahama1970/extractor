# Pipeline Architecture Summary

## Correct Architecture (per HOW_IT_WORKS.md)

The extraction pipeline has been updated to follow the correct stage order:

### Pipeline Stages

```
1. Extract Annotations → 2. Clean PDF → 3. Marker Extraction → 4. Fix Structure → 5. Create JSON Nodes → 6. Semantic Processing → 7. Output
```

### Critical Architecture Points

1. **Stage 4: Section Fixer** MUST run before any PDF object processing
2. **Stage 5: JSON Nodes** are created based on the fixed section headers
3. **Stage 6: Semantic Processing** works on complete JSON nodes, not raw blocks
4. **Stage 7: Final Output** contains all fixes and enhancements

## Implementation Details

### Stage 4: Section Fixer (BEFORE JSON Creation)

The Section Fixer worker (`section_fixer_worker.py`) handles:
- Merging split headers (e.g., "4.1.5.4. BHT (Branch History" + "Table) submodule")
- Reclassifying misidentified blocks
- Repairing section hierarchy
- Applying annotation-based fixes

Key improvements:
- Added logic to detect parentheses continuations
- Improved header pattern matching
- Better handling of incomplete headers

### Stage 5: Create JSON Nodes

Creates hierarchical structure based on FIXED headers:
- One node per section header
- Maintains parent-child relationships
- Includes all blocks within each section
- Preserves page ranges

### Stage 6: Semantic Section Processing

Processes complete JSON nodes with full context:
- Knowledge Searcher: Finds similar annotated examples
- Text Cleaner: Fixes text issues within sections
- Table Merger: Analyzes tables for merging
- Image Describer: Generates contextual descriptions

## Verification

The pipeline has been tested and verified:

```
✓ Stage 4 applied 2 fixes
  Fix: Reclassified as SectionHeader
  Fix: Merged split header: 4.1.5.4. BHT (Branch History + Table) submodule
✓ Stage 5 created 1 section nodes
✓ Stage 6 semantic processing complete
✓ All pipeline stages working correctly!
✓ Architecture follows HOW_IT_WORKS.md correctly!
```

## Key Files

1. **Pipeline Implementation**: `src/extractor/core/pipeline_stages.py`
   - Implements all 7 stages in correct order
   - Includes working_usage() demonstration

2. **Section Fixer Worker**: `src/core/agents/workers/section_fixer_worker.py`
   - Enhanced to handle split headers with parentheses
   - Improved pattern matching for headers

3. **Architecture Documentation**: `HOW_IT_WORKS.md`
   - Updated to reflect correct stage order
   - Clear that Section Fixer runs BEFORE JSON creation

## Usage Example

```python
from extractor.core.pipeline_stages import PipelineStages

# Initialize pipeline
pipeline = PipelineStages()
await pipeline.initialize()

# Run full pipeline
result = await pipeline.run_full_pipeline("document.pdf")

# Or run individual stages
blocks = await pipeline.stage3_marker_extraction("document.pdf")
fixed = await pipeline.stage4_fix_structure(blocks)  # CRITICAL: Before JSON!
nodes = await pipeline.stage5_create_json_nodes(fixed["blocks"])
processed = await pipeline.stage6_semantic_processing(nodes)
```

## Benefits of Correct Architecture

1. **Early Structure Fixing**: Problems are fixed before creating the document hierarchy
2. **Clean JSON Nodes**: Nodes are created from already-fixed headers
3. **Efficient Processing**: Semantic processing works on clean, complete sections
4. **Better Accuracy**: Split headers and misclassifications are fixed early

This architecture ensures that complex PDFs with split headers, tables spanning pages, and mixed content are extracted accurately and intelligently.