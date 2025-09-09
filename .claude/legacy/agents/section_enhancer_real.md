# Section Enhancement - Using What We Actually Have

You receive a section with messy blocks. Your job: USE ALL OUR EXISTING TOOLS to clean it up.

## Tools You Already Have

### Analysis Tools
- **Pandas analysis** - `semantic_section_processor.py:_analyze_tables_with_pandas()`
- **Table merge decisions** - `table_merger_worker.py`
- **Section images** - `semantic_section_processor.py:create_section_image()`
- **Table images** - `table_image_creator.py`
- **Annotations** - Check if humans left notes about this section

### Cleaning Tools  
- **Text cleaning** - `text_cleaning.py`
- **Table processing** - `llm_table.py`
- **Equation formatting** - `llm_equation.py`
- **Code formatting** - `code.py`

## What To Do

### 1. Merge Contiguous Text Blocks
```python
# BEFORE
blocks = [
    {"type": "Text", "text": "The system uses a predic-"},
    {"type": "Text", "text": "tor to improve performance"},
    {"type": "Text", "text": "by analyzing patterns."}
]

# AFTER  
blocks = [
    {"type": "Text", "text": "The system uses a predictor to improve performance by analyzing patterns."}
]
```

### 2. Add Table Titles
Look at text blocks right before tables:
```python
# If you see:
{"type": "Text", "text": "Table 3: Signal descriptions"},
{"type": "Table", "text": "Signal|Width|Description"}

# Add title to table:
{"type": "Table", 
 "text": "Signal|Width|Description",
 "title": "Table 3: Signal descriptions"}

# If no explicit title but context suggests one:
{"type": "Text", "text": "The following signals are used:"},
{"type": "Table", "text": "Signal|Width|Description"}

# Infer title:
{"type": "Table",
 "text": "Signal|Width|Description", 
 "title": "INFERRED: Signal specifications"}
```

### 3. Fix Split Tables
```python
# Check if tables on same page with similar structure should merge
table1 = {"text": "Signal|Width|Descripti", "page": 5}
table2 = {"text": "on||", "page": 5}

# Use table_merger_worker to decide
# If should merge, combine them
```

### 4. Use Visual Context
```python
# Create section image to see what it looks like
section_image = create_section_image(blocks, page_images)

# If table appears to have header in image but not in text:
# Use visual cues to fix structure
```

### 5. Apply Pandas Analysis
```python
# Run pandas on tables to understand structure
analysis = _analyze_tables_with_pandas(tables)
# Use column info to fix alignment issues
```

## Example Full Process

```bash
# 1. Analyze what's in the section
cat section_001.json | jq '.blocks[] | {type: .block_type, preview: .text[:50]}'

# 2. Merge contiguous text blocks
python -c "
blocks = load_json('section_001.json')['blocks']
merged = merge_contiguous_text_blocks(blocks)
save_json(merged, 'section_001_merged.json')
"

# 3. Find and add table titles
python -c "
for i, block in enumerate(blocks):
    if block['type'] == 'Table' and i > 0:
        prev = blocks[i-1]
        if 'Table' in prev['text'] or 'following' in prev['text']:
            block['title'] = extract_title(prev['text'])
"

# 4. Check for split tables
python table_merger_worker.py analyze section_001_merged.json

# 5. Create visual references
python semantic_section_processor.py create-image section_001_merged.json --pdf doc.pdf
python table_image_creator.py create section_001_merged.json

# 6. Clean text with OCR fixes
python text_cleaning.py process section_001_merged.json

# 7. Enhance tables with structure
python llm_table.py enhance section_001_merged.json
```

## Output

```json
{
    "section_id": 1,
    "blocks": [
        {
            "type": "SectionHeader",
            "text": "4.1.5.4. BHT (Branch History Table) submodule",
            "original_text": "4.1.5.4. BHT (Branch Histoiy Table) submodule"
        },
        {
            "type": "Text",
            "text": "The BHT is implemented as a memory structure with 1024 entries. Each entry contains branch prediction data.",
            "merged_from": 3  // Was 3 separate blocks
        },
        {
            "type": "Table",
            "title": "Table 4.1: BHT Signal Interface",
            "text": "Signal|IO|Description|Connection|Type\nclk|I|Clock signal|BHT|std_logic\nreset|I|Reset signal|BHT|std_logic",
            "original_text": "Signal|IO|Descripti|connexi|Type",
            "pandas_shape": [2, 5],
            "merged_from": 2  // Was 2 split tables
        }
    ],
    "enhancements": [
        "Merged 3 contiguous text blocks",
        "Fixed OCR errors (5 corrections)",
        "Merged split table across 2 blocks",
        "Added table title from preceding text",
        "Fixed table structure using pandas analysis"
    ]
}
```

That's it! Use ALL the tools we built to make sections clean and usable.