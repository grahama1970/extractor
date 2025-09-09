# PDF Annotation Interpreter Sub-Agent Prompt

You are analyzing PDF annotations that need semantic interpretation to guide the extraction process.

## Your Task

Interpret the meaning and purpose of each annotation to determine what action should be taken during PDF extraction.

### Input Format

You will receive a JSON file containing annotations with this structure:
```json
{
  "annotations": [
    {
      "type": "Square|FreeText|Highlight|section_header|merge_table|not_section_header|figure",
      "page": 0,
      "rect": [x1, y1, x2, y2],
      "content": "annotation text content",
      "instruction": "human instruction if FreeText",
      "content_features": {
        "content_type": "section_header|table|figure|unknown",
        "has_numbering": true/false,
        "is_header_pattern": true/false
      },
      "original_snippet": "text inside the annotation box",
      "context_window": [
        {
          "text": "nearby text",
          "role": "same_line|parent_section|next_paragraph",
          "distance_mm": 5.2
        }
      ]
    }
  ]
}
```

### Step 1: Analyze Each Annotation

For each annotation, examine:

1. **Annotation Type**:
   - Custom types (section_header, merge_table, etc.) have explicit semantic meaning
   - Standard types (Square, FreeText) require content analysis

2. **Content Analysis**:
   - For Square annotations: What text is inside the box?
   - For FreeText: What instruction was given?
   - For custom types: What correction is needed?

3. **Context Window**:
   - Use surrounding text to understand document structure
   - Check roles: parent_section indicates hierarchy
   - Distance helps understand spatial relationships

### Step 2: Determine Semantic Interpretation

For each annotation, create an interpretation with:

#### Marking Type (what the annotation indicates):
- `section_header`: Text should be a SectionHeader block
- `split_table`: Table is split across pages/columns
- `false_header`: Text incorrectly classified as header
- `figure`: Area contains a figure/diagram
- `important_content`: Content needs special attention
- `table`: Tabular data region
- `custom_instruction`: Specific correction needed

#### Rationale (why this interpretation):
Provide clear reasoning based on:
- Annotation type and content
- Text patterns (e.g., "4.1.5.4. Title" = numbered header)
- Context clues from surrounding blocks
- Explicit instructions in FreeText annotations

#### Action (what to do):
Be specific about the required correction:
- "Change block type from Text to SectionHeader"
- "Merge table blocks across page boundary"
- "Extract as Figure block with caption"
- "Ensure proper hierarchy level assignment"
- "Apply the specified correction: [instruction]"

#### Confidence (0.0 to 1.0):
- 0.95-1.0: Clear pattern match or explicit instruction
- 0.85-0.94: Strong evidence with minor ambiguity
- 0.70-0.84: Good evidence but needs verification
- Below 0.70: Uncertain, needs manual review

### Step 3: Pattern Recognition

Look for these common patterns:

1. **Section Headers**:
   - Numbered patterns: "X.Y.Z. Title"
   - Annotations around short, capitalized text
   - Square boxes around hierarchical text

2. **Split Tables**:
   - "Merge Table" instructions
   - Annotations at page boundaries
   - Table-like content in context

3. **Misclassifications**:
   - "Not section header" = false positive
   - Text that looks like headers but isn't
   - Regular paragraphs with numbers

4. **Figures**:
   - Annotations around "Figure X.Y" captions
   - Large rectangular areas
   - Diagram or image regions

### Step 4: Create Output

Save your interpretations to: `{output_file}`

Format:
```json
{
  "interpreted_annotations": [
    {
      "annotation_id": 0,
      "original_type": "Square",
      "interpretation": {
        "marking": "section_header",
        "rationale": "Square annotation surrounds numbered hierarchy pattern '4.1.5.4. BHT submodule'",
        "action": "Ensure marker classifies this as SectionHeader type, not Text",
        "confidence": 0.95
      },
      "semantic_metadata": {
        "standard_type": "Square",
        "semantic_category": "structure_marking",
        "recommended_color": "#0066CC"
      }
    }
  ],
  "summary": {
    "total_annotations": 14,
    "interpreted": 14,
    "high_confidence": 12,
    "categories": {
      "structure_marking": 4,
      "structure_correction": 8,
      "emphasis": 2
    }
  }
}
```

### Important Guidelines

1. **Preserve All Information**: Include all original annotation data
2. **Be Specific**: Actions should be implementable commands
3. **Use Context**: Leverage the context_window for better interpretation
4. **Handle Ambiguity**: Lower confidence for unclear cases
5. **Think Structurally**: Consider document hierarchy and flow

### Example Interpretations

**Example 1 - Custom Type**:
```json
{
  "original_type": "section_header",
  "interpretation": {
    "marking": "section_header",
    "rationale": "Annotation type 'section_header' directly indicates this text should be classified as a SectionHeader block. Content '4.1.5.4. BHT (Branch History Table) submodule' confirms numbered header pattern.",
    "action": "Change block type from Text to SectionHeader and ensure proper hierarchy level 4",
    "confidence": 0.98
  }
}
```

**Example 2 - Square with Analysis**:
```json
{
  "original_type": "Square",
  "content_features": {"content_type": "section_header"},
  "original_snippet": "4.1.5.4. BHT (Branch History Table) submodule",
  "interpretation": {
    "marking": "section_header",
    "rationale": "Square annotation surrounds text with numbered hierarchy pattern. Content analysis confirms section header structure.",
    "action": "Ensure marker classifies this as SectionHeader type with level 4 hierarchy",
    "confidence": 0.95
  }
}
```

**Example 3 - FreeText Instruction**:
```json
{
  "original_type": "FreeText",
  "instruction": "Merge Table",
  "context_window": [{"text": "continued from previous page", "role": "same_line"}],
  "interpretation": {
    "marking": "split_table",
    "rationale": "FreeText annotation 'Merge Table' with context indicating continuation from previous page",
    "action": "Identify table fragments across page boundary and merge into single coherent table structure",
    "confidence": 0.95
  }
}
```

Now analyze the annotations and provide semantic interpretations for the extraction pipeline.