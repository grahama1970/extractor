# BHT Example Addition to HOW_IT_WORKS.md

## Summary

I've added a comprehensive BHT PDF extraction example to HOW_IT_WORKS.md that shows the complete transformation of a real document section through all 7 pipeline stages. This provides agents (like myself) with a concrete reference implementation showing exactly what should happen at each stage.

## What Was Added

### 1. Complete Stage-by-Stage Example (Lines 243-678)

The example follows a real BHT (Branch History Table) section from CV32A65X technical specification through:

- **Stage 1**: Annotation extraction with exact coordinates
- **Stage 2**: Clean PDF creation showing file size changes
- **Stage 3**: Marker extraction showing common issues (split headers, misclassifications)
- **Stage 4**: Section Fixer showing exactly how fixes are applied
- **Stage 5**: JSON node creation with hierarchy
- **Stage 6**: Semantic processing with Claude iterations
- **Stage 7**: Final structured output

### 2. Gold Standard Validation at Each Stage

Each stage shows:
- **Input**: What goes in
- **Processing**: What happens (with code snippets)
- **Output**: What comes out
- **Validation**: ✅ Pass or ❌ Issues with specific details

### 3. Real Issues and Fixes

The example demonstrates common real-world problems:
- Header split: `"4.1.5.4. BHT (Branch History"` + `"Table) submodule"`
- Word split: `"Descripti|on"`
- Table continuation not recognized
- Headers misclassified as Text blocks

### 4. Visual Validation Example

Shows how Claude's first attempt didn't match the PDF visually, requiring a second iteration with feedback to get the table structure correct.

### 5. Knowledge Base Integration

Demonstrates how the system searches for similar sections and applies learned patterns with 0.92 confidence.

## Why This Is Important

1. **Concrete Reference**: Agents can see exactly what "merge split headers" means in practice
2. **Debugging Guide**: Shows what issues to look for at each stage
3. **Validation Criteria**: Clear pass/fail criteria for each gold standard
4. **Real Data**: Uses actual PDF content, not hypothetical examples
5. **Complete Flow**: Shows how fixes cascade through the pipeline

## Key Insights for Agents

The example clearly shows:
- Stage 4 (Section Fixer) MUST run before Stage 5 (JSON nodes)
- Annotations are critical for guiding fixes
- Visual validation catches subtle alignment issues
- Knowledge base provides confidence from previous fixes
- The pipeline is iterative and self-correcting

## Usage

When implementing or debugging the extractor, agents should:
1. Compare their output at each stage to this example
2. Use the validation criteria to check their work
3. Look for the same types of issues (split headers, misclassifications)
4. Ensure fixes are applied in the correct order
5. Validate that the final output matches the PDF visually

This comprehensive example ensures that any agent working on the extractor understands not just the theory but the practical reality of how PDF extraction should work.