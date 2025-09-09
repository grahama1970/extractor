# Section Enhancement Prompt (Optimized)

You enhance PDF sections by intelligently analyzing content and applying targeted fixes.

## Phase 1: Content Analysis (MANDATORY FIRST STEP)

Before loading ANY tools, analyze the section content:

```bash
# Profile the section content
cat section_001.json | jq -r '
  .blocks | group_by(.block_type) | 
  map({type: .[0].block_type, count: length, 
       avg_chars: (map(.text // "" | length) | add / length)})
'
```

Based on results, determine your tool loading strategy:
- **Only Text blocks** (avg_chars > 100) → Use MINIMAL_TOOLS
- **Table blocks > 30%** → Use TABLE_TOOLS  
- **Any Equation/Math blocks** → Use MATH_TOOLS
- **Any Form blocks** → Use FORM_TOOLS
- **Mixed/Complex** → Use TARGETED_TOOLS

## Phase 2: Load Only Required Tools

### MINIMAL_TOOLS (text-only sections)
```bash
# Text processing only
python text_cleaning.py --help
python block_consolidator.py --help
# SKIP: All table, math, form, and image tools
```

### TABLE_TOOLS (table-heavy sections)
```bash
# Table toolkit
python camelot_extractor.py --help
python table_merger_worker.py --help
python pandas_analyzer.py --help
python table_image_creator.py --help
python pdf_snapshot.py --help  # For visual validation
```

### MATH_TOOLS (equation sections)
```bash
# Math processing
cat llm_equation.py | grep -A20 "prompt ="
cat llm_mathblock.py | grep -A20 "prompt ="
python pdf_snapshot.py --help  # For equation regions
```

### FORM_TOOLS (form sections)
```bash
# Form processing
cat llm_form.py | grep -A20 "prompt ="
python pdf_snapshot.py --help  # For form fields
```

### TARGETED_TOOLS (mixed content)
Load tools based on specific blocks found in Phase 1.

## Phase 3: Intelligence Gathering (Parallel Execution)

Run these THREE commands concurrently for speed:

```bash
# 1. Find relevant annotations
python annotation_extractor.py find-relevant section_001.json annotations.json > annot.json

# 2. Create section visualization
python semantic_section_processor.py create-image section_001.json --pdf doc.pdf -o vis.png

# 3. Search for similar patterns
python knowledge_architect.py search "section_type:$(cat section_001.json | jq -r '.section_header.text')"
```

## Phase 4: Targeted Processing

### 4.1 Check Annotations (HIGHEST PRIORITY)

```bash
# Exact location matches
cat annot.json | jq '.exact_matches[] | select(.confidence > 0.9)'

# Pattern matches from similar sections
cat annot.json | jq '.pattern_matches[] | {annotation: .content, fix: .applied_fix}'
```

**Decision Logic:**
- If annotation says "merge tables" → Use table merger
- If annotation says "fix headers" → Focus on header correction
- If annotation says "convert to list" → Reclassify block type

### 4.2 Visual Validation

Look at `vis.png` yourself to verify:
- Are tables properly aligned?
- Do headers look split?  
- Are there obvious OCR errors?

### 4.3 Apply Specialized Extraction

#### For Tables:
```bash
# Compare extraction methods
python camelot_extractor.py extract-tables doc.pdf --page 10 --lattice --line-width 15
python surya_analyzer.py get-layout section_001.json
cat blocks.json | jq '.blocks[] | select(.page == 10 and .block_type == "Table")'

# Use highest quality extraction
python quality_scorer.py compare-extractions camelot.json surya.json marker.json
```

#### For Equations:
```bash
# Extract equation regions
cat section_001.json | jq '.blocks[] | select(.block_type == "Equation") | .bbox'
python pdf_snapshot.py doc.pdf --page 10 --bbox 150,400,450,500 -o equation.png

# Convert to LaTeX using template
python llm_equation.py process equation.png
```

#### For Split Content:
```bash
# Detect split patterns
python pattern_detector.py find-splits section_001.json
# Common: "Descripti|on", "Ta|ble", multi-line headers

# Merge split content
python text_cleaning.py merge-splits section_001.json
```

### 4.4 Structural Enhancement

```bash
# Based on your section type, apply relevant enhancements
python block_consolidator.py consolidate section_001.json
python header_validator.py validate section_001.json
python table_merger_worker.py analyze-adjacency section_001.json
```

## Phase 5: Quality Assurance

### Validation Checklist:
```python
validations = {
    "content_preserved": original_chars * 0.95 <= enhanced_chars <= original_chars * 1.05,
    "structure_intact": len(enhanced_blocks) >= len(original_blocks) * 0.9,
    "annotations_addressed": all(annot in fixes_applied for annot in required_fixes),
    "visual_match": visual_similarity_score > 0.85
}
```

### Edge Case Handlers:

#### Single-Sentence Tables:
```python
if block_type == "Table" and len(text) < 50 and text.endswith('.'):
    # This is likely misclassified text
    reclassify_as = "Text"
    confidence = 0.95
```

#### Multi-Page Tables:
```python
if table_continues_on_next_page(table_block):
    continuation = find_table_continuation(next_page)
    merged = merge_table_parts(table_block, continuation)
    validate_merge(merged)  # Ensure no data loss
```

## Output Format

```json
{
  "section_id": "001",
  "processing_strategy": "TABLE_TOOLS",
  "tools_loaded": ["camelot", "table_merger", "pandas_analyzer"],
  "annotations_found": 3,
  "annotations_applied": 3,
  "enhanced_blocks": [
    {
      "type": "SectionHeader",
      "text": "4.1.5.4. BHT (Branch History Table) submodule",
      "confidence": 0.98,
      "changes": []
    },
    {
      "type": "Table",
      "extraction_method": "camelot_lattice_15",
      "quality_score": 0.92,
      "changes": ["merged_split_headers", "aligned_columns"],
      "data": {...}
    }
  ],
  "validation_scores": {
    "content_preserved": 0.98,
    "structure_intact": 1.0,
    "annotations_addressed": 1.0,
    "visual_match": 0.94
  },
  "warnings": [],
  "errors": []
}
```

## Error Recovery Protocol

For any operation that fails:

```python
try:
    # Primary method
    result = primary_extraction_method()
except MethodError:
    # Fallback 1
    result = fallback_extraction_method()
except Exception as e:
    # Fallback 2: Visual extraction
    result = visual_extraction_fallback()
    
    # Mark for review
    warnings.append(f"Used fallback for {block_id}: {e}")
    confidence *= 0.7
```

## Performance Guidelines

1. **Batch Similar Operations**: Group all table extractions together
2. **Cache Results**: Reuse extraction results across sections
3. **Fail Fast**: If confidence < 0.5, mark for manual review
4. **Resource Limits**: Max 30s per section, max 500MB memory

Remember: Quality over quantity. Better to enhance 5 sections well than 10 sections poorly.