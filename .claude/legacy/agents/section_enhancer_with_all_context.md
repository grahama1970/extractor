# Section Enhancement - With All Extraction Context

You are enhancing a section. Workers provide you with MULTIPLE extraction results and analyses. You decide which is best.

## Context You Receive

### 1. Surya Model Information
```bash
python surya_analyzer.py get-layout section_001.json
```
```json
{
  "layout_blocks": [
    {"type": "Table", "bbox": [100, 200, 500, 400], "confidence": 0.95},
    {"type": "TableCaption", "bbox": [100, 180, 500, 200], "text": "Table 4.1: Signal Interface"}
  ],
  "table_structure": {
    "rows": 10,
    "columns": 5,
    "has_header": true,
    "spans": [[2,3]] // cell at row 2, col 3 spans 2 columns
  }
}
```

### 2. Camelot Extraction
```bash
python camelot_extractor.py extract-tables section_001.pdf --page 10
```
```json
{
  "extraction_report": {
    "accuracy": 87.3,
    "whitespace": 12.4,
    "order": 95.2,
    "parsing_method": "lattice"
  },
  "table": {
    "data": [
      ["Signal", "IO", "Description", "Connection", "Type"],
      ["clk", "I", "Clock signal", "BHT", "std_logic"],
      ["reset", "I", "Reset signal", "BHT", "std_logic"]
    ],
    "shape": [10, 5]
  }
}
```

### 3. Marker Extraction  
```bash
cat blocks.json | jq '.blocks[] | select(.block_type == "Table")'
```
```json
{
  "block_type": "Table",
  "text": "Signal|IO|Descripti|connexi|Type\n||on|on|",  // Split/broken
  "confidence": 0.72,
  "html": "<table>...</table>"
}
```

### 4. Pandas Analysis on Both
```bash
python pandas_analyzer.py compare-tables camelot_table.csv marker_table.csv
```
```json
{
  "camelot_pandas": {
    "shape": [10, 5],
    "dtypes": {"Signal": "object", "IO": "object", "Description": "object"},
    "null_count": 0,
    "numeric_cols": []
  },
  "marker_pandas": {
    "shape": [10, 5],
    "dtypes": "Unable to parse - malformed structure",
    "issues": ["Split headers", "Missing cell boundaries"]
  },
  "recommendation": "Use Camelot extraction - higher quality"
}
```

### 5. Visual Verification
```bash
python visual_compare.py section_001_image.png camelot_render.png marker_render.png
```
```json
{
  "camelot_visual_match": 0.94,
  "marker_visual_match": 0.67,
  "issues": {
    "camelot": "Minor spacing differences",
    "marker": "Missing column boundaries, split headers"
  }
}
```

## YOUR Decision Process

Given ALL this context, you decide:

```markdown
Analysis:
1. Surya correctly identified table location and caption
2. Camelot extracted clean table with 87% accuracy  
3. Marker extraction is broken (split headers, low confidence)
4. Pandas can parse Camelot but not Marker output
5. Visual comparison confirms Camelot is more accurate

My Decision:
- USE Camelot extraction for table data
- USE Surya's table caption detection  
- IGNORE Marker's broken table
- ADD inferred column descriptions based on context
```

## Your Enhanced Output

```json
{
  "section_id": 1,
  "extraction_decisions": {
    "table_source": "camelot",
    "reason": "87% accuracy vs 67% for marker, clean structure",
    "caption_source": "surya", 
    "reason": "Detected caption that Camelot missed"
  },
  "enhanced_blocks": [
    {
      "type": "SectionHeader",
      "text": "4.1.5.4. BHT (Branch History Table) submodule"
    },
    {
      "type": "Text",
      "text": "The BHT module interfaces with the CPU through the following signals:"
    },
    {
      "type": "Table",
      "title": "Table 4.1: Signal Interface", // From Surya
      "source": "camelot_extraction",
      "data": {
        "headers": ["Signal", "IO", "Description", "Connection", "Type"],
        "rows": [
          ["clk", "I", "Clock signal", "BHT", "std_logic"],
          ["reset", "I", "Reset signal", "BHT", "std_logic"],
          ["pc", "I", "Program counter", "CPU", "std_logic_vector(31:0)"],
          ["prediction", "O", "Branch prediction", "CPU", "std_logic"],
          ["update", "I", "Update prediction", "CPU", "std_logic"]
        ]
      },
      "metadata": {
        "extraction_method": "camelot_lattice",
        "accuracy": 87.3,
        "visual_match": 0.94,
        "pandas_validated": true
      }
    }
  ],
  "context_used": [
    "Surya layout detection",
    "Camelot table extraction", 
    "Pandas validation",
    "Visual comparison"
  ]
}
```

## The Key Point

You don't just clean text - you:
1. Compare multiple extraction methods
2. Choose the best based on metrics
3. Combine results (Surya caption + Camelot data)
4. Make intelligent decisions based on quality scores
5. Document why you chose what you chose

This is TRUE section enhancement - using all available data to produce the best possible output.