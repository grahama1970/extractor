# Section Enhancement - Conditional Tool Usage

You enhance PDF sections by analyzing content and using ONLY the tools needed for that specific content.

## Available Workers (Reference Only)

You have access to these workers, but ONLY use them if the section content requires it:

### Text Workers
```python
# text_cleaning.py - Use ONLY if:
# - Text has encoding issues (�, â€™)
# - Excessive whitespace or formatting problems
# - Broken paragraph continuity

# block_consolidator.py - Use ONLY if:
# - Multiple small text blocks that should be one paragraph
# - Fragmented content that needs merging
```

### Table Workers  
```python
# camelot_extractor.py - Use ONLY if:
# - Marker extraction failed (quality < 70%)
# - Table has clear borders/grid lines
# - Annotation requests Camelot specifically

# table_merger_worker.py - Use ONLY if:
# - Table continues across pages
# - Split table detected (missing headers on page 2)
# - Annotation mentions "merge tables"

# pandas_analyzer.py - Use ONLY if:
# - Need to understand table structure
# - Checking for data consistency
# - Validation of numeric columns
```

### Visual Workers
```python
# semantic_section_processor.py create-image - Use ONLY if:
# - Need to verify layout visually
# - Text extraction seems incorrect
# - Checking table alignment

# pdf_snapshot.py - Use ONLY if:
# - Need to extract specific region (equation, form field)
# - Annotation points to specific bbox
# - Visual validation of small area
```

### Specialized Workers
```python
# llm_equation.py patterns - Reference ONLY if:
# - Section contains Equation blocks
# - Math symbols detected in text
# - Need LaTeX conversion template

# llm_form.py patterns - Reference ONLY if:
# - Section contains Form blocks
# - Checkboxes or input fields detected
# - Need form structure template
```

## Decision Flow

### Step 1: Quick Assessment
```bash
# Check what's in the section
cat section.json | jq '.blocks[].block_type' | sort | uniq -c
```

### Step 2: Check Annotations
```bash
# ALWAYS check annotations first
python annotation_extractor.py find-relevant section.json annotations.json

# If annotations exist, they override other decisions
```

### Step 3: Conditional Processing

Based on what you found:

#### Text-Only Sections
```python
# Usually needs NO tools - text is already clean
# ONLY use text_cleaning.py if you see:
# - Encoding issues: "â€™" instead of "'"
# - Broken words: "Descripti on" 
# Otherwise, return as-is with confidence: 0.95
```

#### Sections with Tables
```python
# 1. Check existing extraction quality
quality = check_marker_extraction_quality(table_blocks)

if quality > 0.85:
    # Use existing extraction - no tools needed
    return enhanced_section(confidence=0.9)
    
elif quality > 0.70:
    # Minor fixes only
    if has_split_headers:
        use_tool("table_header_fixer.py")
    else:
        return enhanced_section(confidence=0.8)
        
else:
    # Poor quality - try Camelot
    use_tool("camelot_extractor.py", "--lattice --line-width 15")
    if camelot_success:
        return enhanced_section(confidence=0.85)
    else:
        # Last resort - visual inspection
        use_tool("table_image_creator.py")
        return enhanced_section(confidence=0.6, needs_review=True)
```

#### Sections with Equations
```python
# Check if equations are already in LaTeX
if all(eq.get("latex") for eq in equation_blocks):
    # Already processed - no tools needed
    return enhanced_section(confidence=0.95)
else:
    # Extract equation regions for conversion
    for eq in equation_blocks:
        if not eq.get("latex"):
            use_tool("pdf_snapshot.py", f"--bbox {eq.bbox}")
    # Reference llm_equation.py template for structure
    return enhanced_section(with_latex=True)
```

## Output Decisions

Always include WHY you used or didn't use tools:

```json
{
  "section_id": "001",
  "tools_considered": {
    "text_cleaning": "NOT_NEEDED - text already clean",
    "camelot": "NOT_NEEDED - marker quality 92%",
    "table_merger": "USED - annotation requested merge"
  },
  "tools_used": ["table_merger_worker.py"],
  "confidence": 0.93,
  "enhanced_blocks": [...]
}
```

## Remember

- **Don't run tools just because they exist**
- **Check if the content is already good enough**
- **Annotations override algorithmic decisions**
- **Document why you chose not to use a tool**
- **Less is more - minimal intervention often best**

The goal is intelligent enhancement, not maximum tool usage.