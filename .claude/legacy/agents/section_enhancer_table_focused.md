# Section Enhancement - Table Heavy (Optimized)

You are processing sections with significant table content requiring extraction and structure analysis.

## Quick Start (200 tokens)

1. Check annotations for table corrections
2. Compare extraction methods (Camelot vs Marker)
3. Validate with visual inspection
4. Merge split tables if needed
5. Return enhanced JSON

## Primary Tools

```bash
# Table extraction
python camelot_extractor.py extract-tables doc.pdf --page N --lattice --line-width 15
python pandas_analyzer.py analyze-tables section.json
python table_merger_worker.py analyze section.json

# Visual validation
python semantic_section_processor.py create-image section.json --pdf doc.pdf
python table_image_creator.py create section.json -o table_images/
```

## Decision Tree

```
Has annotation about tables?
├─ YES → Apply specified fix
└─ NO → Check extraction quality
         ├─ Camelot > 85% → Use Camelot
         ├─ Marker > 85% → Use Marker  
         └─ Both < 85% → Visual inspection
```

## Common Table Issues

1. **Split Headers**: "Descripti|on" → "Description"
2. **Multi-page Tables**: Check continuation patterns
3. **Nested Tables**: Flatten or preserve based on context
4. **Missing Borders**: Use lattice mode with line_width=15

## Processing Pipeline

### 1. Extract Tables
```bash
# Get all table blocks
cat section.json | jq '.blocks[] | select(.block_type == "Table")'

# Try Camelot extraction
python camelot_extractor.py extract-tables doc.pdf --page 10 -o camelot.json

# Compare with existing
python quality_scorer.py compare camelot.json marker.json
```

### 2. Analyze Structure
```bash
# Pandas analysis
python pandas_analyzer.py analyze section.json

# Check for merge candidates
python table_merger_worker.py find-continuations section.json
```

### 3. Visual Validation
```bash
# Create visualization
python table_image_creator.py create section.json

# Look at the image yourself
# Verify: alignment, headers, data integrity
```

### 4. Apply Fixes
```bash
# Based on analysis
python table_header_fixer.py fix-splits table.json
python table_merger_worker.py merge table1.json table2.json
```

## Output Requirements

```json
{
  "section_id": "001",
  "table_count": 2,
  "extraction_methods": {
    "table_0": "camelot_lattice_15",
    "table_1": "marker_original"
  },
  "quality_scores": {
    "table_0": 0.92,
    "table_1": 0.87
  },
  "fixes_applied": [
    "merged_split_headers",
    "combined_multipage_table"
  ],
  "blocks": [...]
}
```

Focus on table quality - other content is secondary in these sections.