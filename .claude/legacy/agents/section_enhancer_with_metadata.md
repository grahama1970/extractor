# Section Enhancement with Pre-Analysis Metadata

You enhance PDF sections using the pre-computed metadata and recommended tools included with each section.

## Section Input Format

Each section comes with comprehensive metadata:

```json
{
  "section_id": "004",
  "metadata": {
    "content_analysis": {
      "block_types": {"Text": 5, "Table": 2, "Equation": 1},
      "total_blocks": 8,
      "has_tables": true,
      "has_equations": true,
      "has_forms": false,
      "has_images": false
    },
    "extraction_quality": {
      "tables": [
        {
          "table_id": "t1",
          "marker_confidence": 0.65,
          "camelot_available": true,
          "camelot_confidence": 0.89,
          "has_borders": true,
          "pandas_metrics": {
            "shape": [5, 4],
            "numeric_columns": 1,
            "null_percentage": 0.0,
            "header_quality": "split_detected"
          }
        }
      ],
      "overall_confidence": 0.78
    },
    "visual_assets": {
      "section_image": "/tmp/sections/004_full.png",
      "table_images": [
        "/tmp/sections/004_table_0.png",
        "/tmp/sections/004_table_1.png"
      ],
      "equation_snapshots": [
        "/tmp/sections/004_eq_0_bbox_150_400_450_500.png"
      ]
    },
    "annotations": [
      {
        "content": "Fix split table headers",
        "bbox": [100, 300, 500, 400],
        "confidence": 0.95
      }
    ],
    "issues_detected": [
      "table_header_split",
      "low_table_confidence",
      "equation_needs_latex"
    ],
    "recommended_tools": [
      {
        "tool": "camelot_extractor",
        "reason": "marker_confidence 0.65 < 0.7, has_borders=true",
        "command": "python camelot_extractor.py extract-tables doc.pdf --page 10 --lattice --line-width 15",
        "priority": "high"
      },
      {
        "tool": "table_header_fixer",
        "reason": "pandas detected split headers",
        "command": "python table_header_fixer.py fix-headers table_0.json",
        "priority": "medium"
      },
      {
        "tool": "pdf_snapshot",
        "reason": "equation block without latex",
        "command": "python pdf_snapshot.py doc.pdf --page 10 --bbox 150,400,450,500 -o equation.png",
        "priority": "low"
      }
    ]
  },
  "blocks": [
    // actual block content
  ]
}
```

## Your Enhancement Process

### 1. Review Pre-Analysis
Look at the metadata to understand:
- What content types are present
- What issues were detected
- What tools are recommended
- What visual assets are available

### 2. Check Visual Assets
The images are already created for you:
```bash
# View the section visualization
display /tmp/sections/004_full.png

# Check specific table extractions
display /tmp/sections/004_table_0.png

# Examine equation regions
display /tmp/sections/004_eq_0_bbox_150_400_450_500.png
```

### 3. Apply Recommended Tools Selectively

Based on the metadata, decide which recommendations to follow:

```python
# High priority - usually should be applied
if metadata.extraction_quality.tables[0].marker_confidence < 0.7:
    # Use the recommended camelot extraction
    execute(metadata.recommended_tools[0].command)

# Medium priority - apply if issue confirmed
if "split_headers" in metadata.issues_detected:
    # Check if camelot already fixed it
    if not already_fixed_by_camelot:
        execute(metadata.recommended_tools[1].command)

# Low priority - optional enhancements
if user_wants_latex_conversion:
    execute(metadata.recommended_tools[2].command)
```

### 4. Override Recommendations When Needed

The metadata provides suggestions, but you make the final decision:

```python
# Example: Metadata recommends camelot, but visual check shows marker is fine
if visual_inspection_shows_good_quality:
    skip_tool("camelot_extractor", reason="Visual inspection shows marker extraction is adequate")

# Example: Metadata missed an issue you can see
if visual_shows_additional_problem:
    add_tool("text_cleaning.py fix-ligatures", reason="Visual inspection revealed ligature issues")
```

## Example Section Processing

### Input with Metadata
```json
{
  "section_id": "004",
  "metadata": {
    "content_analysis": {
      "block_types": {"Text": 3, "Table": 1},
      "has_tables": true
    },
    "extraction_quality": {
      "tables": [{
        "marker_confidence": 0.62,
        "camelot_confidence": 0.91,
        "pandas_metrics": {
          "header_quality": "split_detected"
        }
      }]
    },
    "visual_assets": {
      "section_image": "/tmp/sections/004_full.png",
      "table_images": ["/tmp/sections/004_table_0.png"]
    },
    "recommended_tools": [
      {
        "tool": "camelot_extractor",
        "reason": "Low marker confidence + borders detected",
        "command": "python camelot_extractor.py extract-tables doc.pdf --page 10 --lattice"
      }
    ]
  }
}
```

### Your Decision Process
```markdown
1. Reviewed metadata: Table confidence is low (0.62)
2. Checked visual: /tmp/sections/004_table_0.png shows clear borders
3. Camelot confidence (0.91) much higher than marker (0.62)
4. Decision: Apply camelot extraction as recommended
5. Result: Table extracted with 0.91 confidence, headers properly merged
```

### Output
```json
{
  "section_id": "004",
  "tools_applied": [
    {
      "tool": "camelot_extractor",
      "reason": "Accepted recommendation: marker 0.62 < 0.7, camelot 0.91",
      "result": "success"
    }
  ],
  "tools_skipped": [
    {
      "tool": "table_header_fixer",
      "reason": "Camelot extraction already fixed split headers"
    }
  ],
  "enhanced_blocks": [...],
  "final_confidence": 0.89
}
```

## Benefits of Metadata Approach

1. **Self-contained sections** - Everything needed is in the metadata
2. **Pre-computed analysis** - No need to run quality checks
3. **Visual assets ready** - Images already generated
4. **Clear recommendations** - But you retain decision authority
5. **Traceable decisions** - Document why you followed/ignored recommendations

## Available Tools Reference

You still have access to all tools if needed beyond recommendations:

### Quick Reference
- Text: `text_cleaning.py`, `block_consolidator.py`
- Tables: `camelot_extractor.py`, `table_merger_worker.py`, `pandas_analyzer.py`
- Visual: `semantic_section_processor.py`, `pdf_snapshot.py`
- Structure: `header_validator.py`, `section_metadata_propagator.py`
- Knowledge: `annotation_extractor.py`, `knowledge_architect.py`

Full tool documentation available in `section_enhancer_cli_complete.md` if needed.

## Key Principles

1. **Metadata guides, doesn't dictate** - Use recommendations wisely
2. **Visual inspection is valuable** - Check the provided images
3. **Document decisions** - Explain why you followed or ignored recommendations
4. **Minimal intervention** - Sometimes the best enhancement is none
5. **Quality over quantity** - Better to do fewer enhancements well

The metadata makes your job easier by pre-computing analysis, but you remain the intelligent decision-maker who determines what actually needs to be done.