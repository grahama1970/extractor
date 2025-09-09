# PDF Extraction Pipeline - Complete Implementation Map

Every step in the pipeline MUST have either:
1. A Python worker implementation (.py file)
2. A prompt file (.md) for sub-agent instructions

## Pipeline Stages with Implementation Status

### ✅ Stage 1: Extract Annotations
- **Code**: `/src/extractor/core/processors/enhanced_annotation_extractor.py`
- **Worker**: `/workers/pdf_annotations_worker.py`
- **Function**: `extract_annotations(pdf_path, analyze_content=True)`

### ✅ Stage 2: Interpret Annotations Semantically  
- **Code**: `/workers/pdf_annotations_worker.py`
- **Prompt**: `/workers/pdf_annotation_interpreter_prompt.md` ✨ NEW
- **Function**: `interpret_annotations(annotations, pdf_path)`

### ✅ Stage 3: Create Clean PDF
- **Code**: `/src/extractor/core/processors/enhanced_annotation_extractor.py`
- **Function**: `create_clean_pdf(pdf_path, output_path)`

### ✅ Stage 4: Check Knowledge Base
- **Code**: `/home/graham/.claude/agents/workers/knowledge_architect_worker.py`
- **Function**: `check_existing_solutions(task_description)`

### ✅ Stage 5: Run Marker Extraction with UUID Assignment
- **Code**: `/workers/pdf_marker_extractor_worker.py` ✨ NEW
- **Function**: `extract_pdf_with_uuids(pdf_path, output_dir)`

### 🔧 Stage 5.5: Create Batches for Suspicious Blocks
- **Code**: `/workers/pdf_block_fixer_worker.py` ✅ EXISTS
- **Prompt**: `/workers/pdf_block_fixer_prompt.md` ✅ EXISTS
- **Function**: `create_suspicious_batches(marker_output_path)`

### ❌ Stage 6: Fix Remaining Suspicious Blocks
- **Code**: MISSING - Need to create `/workers/pdf_suspicious_fixer_worker.py`
- **Prompt**: MISSING - Need to create `/workers/pdf_suspicious_fixer_prompt.md`

### ❌ Stage 7: Create Validation Images
- **Code**: MISSING - Need to create `/workers/pdf_validation_image_worker.py`
- **Prompt**: Not needed (pure code task)

### ❌ Stage 8: Build JSON Nodes from Fixed Blocks
- **Code**: MISSING - Need to create `/workers/pdf_json_builder_worker.py`
- **Prompt**: MISSING - Need to create `/workers/pdf_json_builder_prompt.md`

### ❌ Stage 9: Enhance Sections Semantically
- **Code**: MISSING - Need to create `/workers/pdf_semantic_enhancer_worker.py`
- **Prompt**: MISSING - Need to create `/workers/pdf_semantic_enhancer_prompt.md`

### ❌ Stage 10: Validate Against Gold Standard
- **Code**: MISSING - Need to create `/workers/pdf_gold_validator_worker.py`
- **Prompt**: Not needed (pure comparison task)

### ✅ Stage 11: Store Patterns
- **Code**: `/home/graham/.claude/agents/workers/knowledge_architect_worker.py`
- **Function**: `create_solution_relationships(problem, solution, tool_journey)`

## Implementation Priority

### Must Create Immediately:

1. **Stage 6**: `/workers/pdf_suspicious_fixer_worker.py` + prompt
2. **Stage 7**: `/workers/pdf_validation_image_worker.py`
3. **Stage 8**: `/workers/pdf_json_builder_worker.py` + prompt
4. **Stage 9**: `/workers/pdf_semantic_enhancer_worker.py` + prompt
5. **Stage 10**: `/workers/pdf_gold_validator_worker.py`

### Integration Required:

1. **Main Orchestrator**: Convert `/workers/extract_pdf_worker.py` from markdown to Python
2. **Pipeline Wiring**: Connect all stages in proper sequence
3. **Error Handling**: Add fallbacks for each stage

## Stage Details and Requirements

### Stage 6: Fix Remaining Suspicious Blocks
**Purpose**: Apply final fixes to blocks not handled by batch processing
**Input**: Fixed marker JSON with some remaining suspicious blocks
**Output**: Fully fixed marker JSON
**Logic**: 
- Find remaining suspicious blocks
- Apply pattern-based fixes
- Handle edge cases

### Stage 7: Create Validation Images  
**Purpose**: Generate visual comparisons for quality check
**Input**: Original PDF + Fixed JSON
**Output**: Side-by-side comparison images
**Logic**:
- Render PDF pages
- Overlay block boundaries
- Highlight changes

### Stage 8: Build JSON Nodes
**Purpose**: Convert fixed blocks into hierarchical JSON structure
**Input**: Fixed flat block list
**Output**: Nested JSON with sections/subsections
**Logic**:
- Parse section headers for hierarchy
- Group blocks by sections
- Build tree structure

### Stage 9: Enhance Sections Semantically
**Purpose**: Add semantic metadata to sections
**Input**: Hierarchical JSON structure
**Output**: Enhanced JSON with semantic tags
**Logic**:
- Analyze section content
- Add tags (introduction, methodology, results, etc.)
- Link related sections

### Stage 10: Validate Against Gold Standard
**Purpose**: Measure extraction accuracy
**Input**: Enhanced JSON + Gold standard JSON
**Output**: Validation report with metrics
**Logic**:
- Compare block counts
- Check text accuracy
- Measure structure preservation

## Next Steps

1. Create the missing worker implementations
2. Create the missing prompt files
3. Wire everything together in a proper orchestrator
4. Test with real PDFs
5. Add error handling and logging