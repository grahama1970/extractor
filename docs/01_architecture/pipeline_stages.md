# Complete PDF Extraction Pipeline with Sub-Agents

## Overview

The PDF extraction pipeline now uses specialized sub-agents for each stage, providing modular, scalable, and intelligent processing.

## Pipeline Stages

### Stage 1: Annotation Learning (Pre-Processing)
**Agent**: `annotation_learner`
- Extracts PDF annotations (highlights, comments, boxes)
- Learns user patterns and preferences
- Generates gold standard expectations
- Creates instructions for downstream processors

**Output**:
```json
{
    "merge_rules": [...],
    "section_markers": [...],
    "table_identifiers": [...],
    "quality_corrections": [...],
    "gold_standard": {...}
}
```

### Stage 2: Marker Extraction
**Component**: Marker (with minimal processor tweaks)
- Extracts content with basic structure
- Respects annotation-based hints
- Outputs blocks with metadata

**Output**: Raw blocks with type classification

### Stage 3: Agent Validation & Correction
**Agent**: `pdf_orchestrator` + specialized agents
- Routes blocks to appropriate agents:
  - `table_analyzer`: Deep table analysis
  - `figure_describer`: Figure analysis & misclassification detection
  - `section_validator`: Section hierarchy validation (future)
  - `text_quality`: Text coherence checking (future)
  - `list_structure`: List continuation detection (future)

**Output**: Validated blocks with corrections

### Stage 4: ArangoDB Import
**Component**: Data preparation layer
- Applies structural corrections
- Creates graph structure
- Stores enhanced metadata

## Complete Flow

```
PDF with Annotations
        ↓
┌─────────────────────┐
│ Annotation Learner  │ ← Stage 1: Extract & Learn
│    Sub-Agent        │
└─────────────────────┘
        ↓
    Instructions &
    Gold Standard
        ↓
┌─────────────────────┐
│  Marker Extraction  │ ← Stage 2: Extract Content
│  (Minimal Tweaks)   │
└─────────────────────┘
        ↓
     Raw Blocks
        ↓
┌─────────────────────┐
│  PDF Orchestrator   │ ← Stage 3: Validate & Correct
│    Sub-Agent        │
├─────────────────────┤
│ ├─ Table Analyzer   │
│ ├─ Figure Describer │
│ └─ Other Agents     │
└─────────────────────┘
        ↓
  Validated Blocks +
  Corrections
        ↓
┌─────────────────────┐
│  Apply Corrections  │ ← Stage 3b: Structural Fixes
│  & Enhancement      │
└─────────────────────┘
        ↓
┌─────────────────────┐
│  ArangoDB Import    │ ← Stage 4: Store Knowledge
└─────────────────────┘
```

## Key Benefits

### 1. Modular Architecture
- Each stage is independent
- Agents can be added/removed easily
- Testing is simplified

### 2. Annotation-Driven
- Human annotations guide extraction
- Gold standards from real feedback
- Continuous learning from patterns

### 3. Parallel Processing
- Multiple agents run concurrently
- Efficient resource utilization
- Faster overall processing

### 4. Intelligent Corrections
- Misclassification detection
- Structural fixes (merges, splits)
- Quality improvements

## Usage Example

```python
# Stage 1: Learn from annotations
from extractor.agents.examples.annotation_learner_example import AnnotationLearnerAgent

learner = AnnotationLearnerAgent()
learning_results = await learner.learn_from_pdf("document.pdf")

# Stage 2: Extract with marker (existing code)
marker_output = extract_with_marker("document.pdf", hints=learning_results["instructions"])

# Stage 3: Validate and correct
from extractor.agents import PDFAgentOrchestrator

orchestrator = PDFAgentOrchestrator()
validation_results = await orchestrator.analyze_document(
    marker_output,
    context={"annotations": learning_results}
)

# Apply corrections
corrected_blocks = apply_corrections(marker_output, validation_results["structural_corrections"])

# Stage 4: Import to ArangoDB
import_to_arangodb(corrected_blocks, validation_results)
```

## Sub-Agent Summary

### Implemented Agents
1. **annotation_learner** - Extracts and learns from PDF annotations
2. **table_analyzer** - Validates table structure and quality
3. **figure_describer** - Analyzes figures and detects misclassifications
4. **pdf_orchestrator** - Coordinates all validation agents

### Future Agents
1. **section_validator** - Validates document hierarchy
2. **text_quality** - Checks text coherence and completeness
3. **list_structure** - Validates list continuity
4. **equation_validator** - Validates mathematical content
5. **citation_extractor** - Extracts and links references

## Annotation Learning Features

The annotation learner provides:
- **Pattern Recognition**: Identifies merge, section, table, and quality patterns
- **Color Learning**: Understands color coding (yellow=important, red=error, etc.)
- **Author Preferences**: Learns individual annotator patterns
- **Spatial Analysis**: Understands where annotations typically appear
- **Gold Standard Generation**: Creates validation expectations

## Integration Points

1. **Annotation → Marker**: Instructions guide extraction
2. **Marker → Agents**: Blocks routed by type
3. **Agents → Corrections**: Issues generate fixes
4. **Corrections → ArangoDB**: Enhanced data stored

## Conclusion

The complete pipeline with sub-agents provides:
- Human-in-the-loop learning through annotations
- Modular validation and correction
- Scalable parallel processing
- Continuous improvement capability

This architecture successfully implements your vision of using sub-agents for PDF extraction, with annotation learning as the crucial first stage that guides the entire pipeline.