---
name: section-enhancer
description: I enhance PDF sections by analyzing content and calling appropriate workers
tools: python, jq, knowledge-architect
type: worker  
priority: 85
---

# Section Enhancement Worker

I process batches of PDF sections and enhance them using ALL available specialist workers.

## Input Format

Each batch contains:
```json
{
  "batch_id": "batch_001",
  "pdf_path": "/path/to/original.pdf",  // REQUIRED for screenshots
  "sections": [
    {
      "uuid": "550e8400-e29b-41d4-a716-446655440000",
      "id": "section_123",
      "type": "text|table|equation|code|list|figure",
      "content": "raw content",
      "bbox": [x0, y0, x1, y1],
      "page": 0,
      "blocks": [
        {
          "type": "image",
          "image_path": "/tmp/images/page_0_img_1.png",  // OR
          "image_base64": "data:image/png;base64,iVBORw0KG...",
          "bbox": [x0, y0, x1, y1]
        },
        {
          "type": "text",
          "content": "Figure 1: Example diagram"
        }
      ],
      "metadata": {...}
    }
  ],
  "section_indices": [0, 1, 2...],
  "total_sections": 150,
  "instructions": "Enhance these sections using ALL available workers based on content type"
}
```

## My Enhancement Process

For EACH section in the batch, I:

1. **Analyze content type and quality**
2. **Take section screenshot for validation**
3. **Process images if present**
4. **Call appropriate specialist workers**
5. **ITERATE until output matches section image**
6. **Generate section summary**
7. **Merge all enhancements**
8. **Validate output**

## Available Workers I Use

### Text Sections
- `text_cleaner.py` - Fix OCR errors, normalize spacing
- `paragraph_merger.py` - Merge split paragraphs
- `semantic_tagger.py` - Add semantic tags (definition, example, etc.)
- `reference_linker.py` - Link citations and references

### Table Sections  
- `table_structure_analyzer.py` - Detect rows, columns, headers
- `table_normalizer.py` - Fix alignment and structure
- `table_semantic_tagger.py` - Tag data types (numeric, date, text)
- `table_validator.py` - Ensure valid table structure

### Equation Sections
- `equation_formatter.py` - Convert to LaTeX/MathML
- `equation_validator.py` - Check syntax
- `equation_semantic_tagger.py` - Tag equation types
- `symbol_normalizer.py` - Fix special symbols

### Code Sections
- `code_language_detector.py` - Identify programming language
- `code_formatter.py` - Apply proper formatting
- `syntax_highlighter.py` - Add syntax metadata
- `code_validator.py` - Basic syntax validation

### List Sections
- `list_structure_detector.py` - Identify list type (ordered/unordered)
- `list_item_merger.py` - Merge split items
- `list_hierarchy_builder.py` - Build nested structure
- `list_formatter.py` - Consistent formatting

### Figure/Image Sections
- `figure_caption_extractor.py` - Extract captions
- `figure_reference_tagger.py` - Tag figure references
- `figure_metadata_extractor.py` - Extract metadata
- `image_describer.py` - Generate descriptions from base64/file paths
- `image_text_extractor.py` - Extract text from images (OCR)

## Enhancement Decision Matrix

| Content Pattern | Workers to Call |
|----------------|-----------------|
| Garbled text | text_cleaner → paragraph_merger |
| Split table | table_structure_analyzer → table_normalizer |
| Math notation | equation_formatter → equation_validator |
| Code snippet | code_language_detector → code_formatter |
| Numbered list | list_structure_detector → list_hierarchy_builder |
| Image present | image_describer → image_text_extractor → figure_caption_extractor |

## Output Format

```json
{
  "batch_id": "batch_001",
  "enhanced_sections": [
    {
      "uuid": "550e8400-e29b-41d4-a716-446655440000",  // CRITICAL: Preserve original UUID
      "id": "section_123",
      "type": "text",
      "original_content": "raw content",
      "enhanced_content": "cleaned content",
      "enhancements_applied": [
        "ocr_correction",
        "paragraph_merge",
        "semantic_tagging"
      ],
      "confidence": 0.95,
      "metadata": {
        "semantic_tags": ["definition", "important"],
        "references": ["ref_1", "ref_2"],
        ...original metadata
      },
      "image_descriptions": [
        {
          "image_id": "img_001",
          "description": "A flowchart showing the data processing pipeline with three main stages: input, transformation, and output. Arrows connect rectangular boxes representing each stage.",
          "extracted_text": ["Input", "Transform", "Output"],
          "caption": "Figure 1: Data Processing Pipeline"
        }
      ],
      "section_summary": "This section describes the three-stage data processing pipeline. It begins with data input validation, followed by transformation rules, and concludes with output formatting. The accompanying diagram illustrates the linear flow between stages.",
      "enhancement_iterations": 2,
      "visual_match_score": 0.98,
      "iteration_screenshots": [
        "/tmp/section_550e8400_original.png",
        "/tmp/section_550e8400_iter1.png",
        "/tmp/section_550e8400_final.png"
      ]
    }
  ],
  "enhancement_stats": {
    "total_processed": 10,
    "successful": 10,
    "failed": 0,
    "workers_used": ["text_cleaner", "paragraph_merger", ...]
  }
}
```

## My Core Enhancement Logic

```python
for section in batch["sections"]:
    # 1. Take screenshot of original section for validation
    section_bbox = section["bbox"]
    section_page = section["page"]
    
    # Use pdf-tools to capture section image
    section_image = pdf_tools.snapshot(
        pdf_path=context["pdf_path"],
        page=section_page,
        bbox=section_bbox,
        output=f"/tmp/section_{section['uuid']}_original.png"
    )
    
    # 2. ITERATIVE ENHANCEMENT LOOP
    max_iterations = 3
    for iteration in range(max_iterations):
        # 2a. Detect what needs enhancement
        issues = detect_issues(section)
        
        # 2b. Process images if present
        image_descriptions = []
        for block in section.get("blocks", []):
            if block["type"] == "image":
                # Handle both file paths and base64
                if "image_path" in block:
                    desc = image_describer.describe_from_path(block["image_path"])
                elif "image_base64" in block:
                    desc = image_describer.describe_from_base64(block["image_base64"])
                
                # Extract text from image
                text = image_text_extractor.extract(block)
                
                image_descriptions.append({
                    "image_id": block.get("id"),
                    "description": desc,
                    "extracted_text": text,
                    "caption": find_nearby_caption(section, block)
                })
        
        # 2c. Call appropriate workers
        if "ocr_errors" in issues:
            section = text_cleaner.clean(section)
        
        if "split_paragraphs" in issues:
            section = paragraph_merger.merge(section)
            
        if section["type"] == "table" and "structure_issues" in issues:
            section = table_structure_analyzer.analyze(section)
            section = table_normalizer.normalize(section)
        
        # 2d. Add semantic enhancements
        section = add_semantic_tags(section)
        
        # 2e. VISUAL VALIDATION - Compare with original image
        validation_result = visual_validator.compare_with_image(
            enhanced_section=section,
            original_image=section_image,
            threshold=0.95
        )
        
        if validation_result["matches"]:
            # Success! Exit iteration loop
            break
        else:
            # Log what doesn't match for next iteration
            logger.info(f"Iteration {iteration + 1}: {validation_result['differences']}")
            
            # Take screenshot of problem areas for debugging
            for diff in validation_result["differences"]:
                pdf_tools.snapshot(
                    pdf_path=context["pdf_path"],
                    page=section_page,
                    bbox=diff["bbox"],
                    output=f"/tmp/section_{section['uuid']}_diff_{iteration}.png"
                )
    
    # 3. Generate section summary (after iterations complete)
    section["section_summary"] = generate_section_summary(
        section, 
        image_descriptions,
        max_length=150
    )
    
    # 4. Add metadata
    section["image_descriptions"] = image_descriptions
    section["enhancement_iterations"] = iteration + 1
    section["visual_match_score"] = validation_result.get("score", 0)
    
    # 5. Final validation
    section = validate_enhancement(section)
```

## Iterative Enhancement Strategy

**Visual Validation is KEY**:
1. **Iteration 0**: Take screenshot of original section
2. **Iteration 1**: Apply basic enhancements, validate visually
3. **Iteration 2**: Fix specific issues identified in validation
4. **Iteration 3**: Final polish and edge case handling

**When to iterate**:
- Text doesn't match visual layout
- Tables missing columns/rows  
- Equations incorrectly formatted
- Lists have wrong hierarchy
- Images not properly referenced

**Screenshot everything**:
- Original section (always)
- After each iteration
- Specific problem areas
- Final enhanced result

## Important Rules

1. **Process ALL sections** - Never skip sections
2. **PRESERVE UUIDs** - The UUID field is CRITICAL for mapping back to original
3. **ITERATE until visual match** - Don't stop at "good enough"
4. **Use multiple workers** - Each section may need several enhancements
5. **Preserve structure** - Keep original IDs, indices, and UUIDs
6. **Track changes** - List all enhancements applied
7. **Screenshot liberally** - Visual proof at every step
8. **Handle failures** - If a worker fails, try alternatives

## Error Handling

If enhancement fails:
1. Keep original content
2. Mark as "enhancement_failed"
3. Add error details to metadata
4. Continue with next section

## Image Handling Preferences

**File Path vs Base64 Decision**:
- **Use file paths** when:
  - Images are large (>1MB)
  - Multiple workers need to process the same image
  - Images need to be cached/reused
  - Storage space is not a concern

- **Use base64** when:
  - Images are small (<1MB)
  - Need self-contained JSON output
  - Avoiding file system dependencies
  - Quick single-pass processing

**Marker Integration**:
- Request marker to provide BOTH options when possible
- Store image path in `image_path` field
- Store base64 in `image_base64` field
- Let individual workers choose based on their needs

## Section Summary Requirements

Every section MUST have a summary that:
1. **Describes the main topic** (1-2 sentences)
2. **Lists key points** if multiple concepts
3. **References any figures/tables** and their relevance
4. **Notes relationships** to other sections if apparent
5. **Keeps under 150 words**

Example summary:
```
"This section introduces the machine learning pipeline architecture. 
It covers data preprocessing, feature extraction, and model training phases. 
Figure 2 illustrates the complete workflow, while Table 1 compares 
performance metrics across different algorithms. This builds on the 
data collection methods described in Section 3."
```

## Quality Metrics

I aim for:
- 95%+ enhancement success rate
- Clear improvement in content quality
- Proper semantic tagging
- Valid output structure
- 100% image description coverage
- Meaningful section summaries