# Section Enhancement - Comprehensive Tool Reference

You enhance PDF sections by thoroughly analyzing content and selectively using ONLY the tools needed.

## All Available Tools

You have access to these tools. Analyze the section thoroughly and choose only what's needed:

### Text Processing Tools

```bash
$ python text_cleaning.py --help
Usage: text_cleaning.py [OPTIONS] COMMAND [ARGS]...

Fix text encoding, whitespace, and OCR errors in sections.

Commands:
  merge-contiguous      Merge text blocks that should be one paragraph
  fix-unicode          Fix encoding issues (�, â€™, etc.)  
  normalize-whitespace  Remove extra spaces and newlines
  fix-ligatures        Convert ﬁ, ﬂ to fi, fl
  analyze              Show text issues without fixing

Options:
  --input FILE   Input section JSON file
  --output FILE  Output cleaned JSON file
  --help         Show this message and exit
```

```bash
$ python block_consolidator.py --help
Usage: block_consolidator.py [OPTIONS] COMMAND [ARGS]...

Merge related blocks based on proximity and content.

Commands:
  consolidate    Merge blocks that belong together
  analyze        Show consolidation opportunities
  
Options:
  --threshold FLOAT  Proximity threshold (default: 10.0)
  --help            Show this message and exit
```

```bash
$ python text_splitter.py --help  
Usage: text_splitter.py [OPTIONS] COMMAND [ARGS]...

Split overly long text blocks at natural boundaries.

Commands:
  split-long-blocks  Split blocks > 1000 chars at sentence/paragraph breaks
  analyze           Show blocks that need splitting
  
Options:
  --max-length INT  Maximum characters per block (default: 1000)
  --help           Show this message and exit
```

### Table Extraction & Analysis Tools
- **camelot_extractor.py** : `python camelot_extractor.py extract-tables doc.pdf --page N` : Extract tables from PDF
  - `--lattice --line-width 15` : For tables with visible borders
  - `--stream` : For tables without borders
  - Use when: Marker extraction quality < 70%

- **pandas_analyzer.py** : `python pandas_analyzer.py analyze-tables section.json` : Analyze table structure
  - Returns: shape, dtypes, null counts, quality score
  - Use when: Need to understand table content

- **table_merger_worker.py** : `python table_merger_worker.py [command] section.json` : Handle multi-page tables
  - `analyze` : Check if tables should be merged
  - `merge table1.json table2.json` : Combine table parts
  - Use when: Tables split across pages

- **table_header_fixer.py** : `python table_header_fixer.py fix-headers table.json` : Fix split headers
  - Use when: Headers like "Descripti|on" need fixing

- **table_image_creator.py** : `python table_image_creator.py create section.json -o images/` : Create table visualizations
  - Use when: Need visual validation of table structure

### Visual Analysis Tools
- **semantic_section_processor.py** : `python semantic_section_processor.py create-image section.json --pdf doc.pdf` : Full section visualization
  - Creates merged image with page boundaries
  - Use when: Need to see overall section layout

- **pdf_snapshot.py** : `python pdf_snapshot.py doc.pdf --page N --bbox x0,y0,x1,y1 -o region.png` : Extract specific regions
  - Use when: Need to examine equations, forms, or specific areas

### Structure & Header Tools
- **header_validator.py** : `python header_validator.py validate section.json` : Check header hierarchy
  - Use when: Section headers seem out of order

- **pattern_aware_header.py** : `python pattern_aware_header.py detect-patterns section.json` : Find header patterns
  - Use when: Headers follow consistent formatting

- **section_metadata_propagator.py** : `python section_metadata_propagator.py add-breadcrumbs section.json` : Add hierarchical context
  - Use when: Need parent section references

### Annotation & Knowledge Tools
- **annotation_extractor.py** : `python annotation_extractor.py find-relevant section.json annotations.json` : Find human corrections
  - ALWAYS run this first - annotations override algorithms
  
- **annotation_matcher.py** : `python annotation_matcher.py [command] section.json annotations.json` : Match patterns
  - `find-exact` : Exact bbox matches
  - `find-similar-patterns` : Pattern-based matching

- **knowledge_architect.py** : `python knowledge_architect.py search "query"` : Find similar solutions
  - Use when: Complex issues need historical context

### Specialized Content Tools
- **equation.py** : `python equation.py process section.json` : Process mathematical content
  - Use when: Equation blocks present

- **code.py** : `python code.py format section.json` : Format code blocks
  - Use when: Code blocks need syntax handling

- **list.py** : `python list.py structure section.json` : Structure list items
  - Use when: Bulleted/numbered lists need organization

- **footnote.py** : `python footnote.py extract section.json` : Handle footnotes
  - Use when: Footnote references detected

### LLM Templates (Reference Only)
- **llm_table.py** : Template for table correction prompts
- **llm_equation.py** : Template for LaTeX conversion
- **llm_form.py** : Template for form field extraction
- **llm_handwriting.py** : Template for handwritten text

## Selective Tool Usage Process

### Step 1: Analyze Section Content
```bash
# What's in this section?
cat section.json | jq '{
  section_id: .section_id,
  block_types: [.blocks[].block_type] | group_by(.) | map({type: .[0], count: length}),
  total_blocks: .blocks | length,
  has_tables: ([.blocks[].block_type] | contains(["Table"])),
  has_equations: ([.blocks[].block_type] | contains(["Equation"])),
  has_issues: [.blocks[] | select(.confidence < 0.8)]
}'
```

### Step 2: Check Annotations (MANDATORY)
```bash
# Human corrections override everything
python annotation_extractor.py find-relevant section.json annotations.json > relevant_annotations.json
cat relevant_annotations.json | jq '.annotations[] | {content, bbox, confidence}'
```

### Step 3: Determine Required Tasks

Based on analysis, identify specific tasks:

#### Task Categories:
1. **Text Cleaning** - Fix OCR errors, encoding, formatting
2. **Table Enhancement** - Extract, merge, fix headers
3. **Structure Validation** - Headers, hierarchy, metadata
4. **Visual Verification** - Confirm extraction accuracy
5. **Content Specialization** - Equations, code, forms

### Step 4: Select Minimal Tool Set

Choose tools for identified tasks ONLY:

```python
# Example decision logic
tasks_needed = []

if has_encoding_issues(section):
    tasks_needed.append(("text_cleaning.py fix-unicode", "Fix encoding"))

if has_split_table(section):
    tasks_needed.append(("table_merger_worker.py analyze", "Check table continuation"))
    
if annotation_says("merge tables"):
    tasks_needed.append(("table_merger_worker.py merge", "Human requested merge"))

if table_quality < 0.7 and has_borders:
    tasks_needed.append(("camelot_extractor.py --lattice", "Poor extraction, try Camelot"))

# Execute only selected tasks
for tool_cmd, reason in tasks_needed:
    execute_tool(tool_cmd, reason)
```

## Example: Real Section Enhancement

### Input Section (Uncleaned)
```json
{
  "section_id": "004",
  "blocks": [
    {
      "block_type": "SectionHeader",
      "text": "4.1.5.4. BHT (Branch History Table) submodule",
      "confidence": 0.95
    },
    {
      "block_type": "Text",
      "text": "The BHT is implemented as a\nmemory structure with 1024 entries",
      "confidence": 0.92
    },
    {
      "block_type": "Table",
      "text": "Signal|Width|I/O|Descripti|Connection\n||bits||on|",
      "confidence": 0.65,
      "extraction_method": "marker",
      "issues": ["split_header", "missing_cells"]
    },
    {
      "block_type": "Text", 
      "text": "The BHT is never ﬂushed.",
      "confidence": 0.88,
      "issues": ["ligature"]
    }
  ]
}
```

### Analysis & Tool Selection
```bash
# 1. Found issues:
# - Table with split header "Descripti|on" (confidence 0.65)
# - Text with ligature "ﬂ" 
# - Table quality below threshold

# 2. Check annotations:
python annotation_extractor.py find-relevant section_004.json annotations.json
# Result: Annotation says "Fix table header split"

# 3. Select tools:
# - camelot_extractor.py (table quality < 0.7)
# - text_cleaning.py fix-ligatures (for "ﬂ")
# - table_header_fixer.py (if Camelot also has split)

# 4. Execute selectively:
python camelot_extractor.py extract-tables doc.pdf --page 10 --lattice
python text_cleaning.py fix-ligatures section_004.json
# Only run header fixer if Camelot didn't fix the split
```

### Expected Output
```json
{
  "section_id": "004",
  "tools_used": [
    {
      "tool": "camelot_extractor.py",
      "reason": "Marker confidence 0.65 < 0.7 threshold",
      "result": "Extracted with 0.89 confidence"
    },
    {
      "tool": "text_cleaning.py fix-ligatures",
      "reason": "Found ligature 'ﬂ' in text",
      "result": "Converted to 'fl'"
    }
  ],
  "tools_not_used": {
    "table_header_fixer.py": "Camelot extraction already fixed split header",
    "pandas_analyzer.py": "Table structure clear, analysis not needed",
    "semantic_section_processor.py": "No layout issues requiring visual check"
  },
  "blocks": [
    {
      "block_type": "SectionHeader",
      "text": "4.1.5.4. BHT (Branch History Table) submodule",
      "confidence": 0.95,
      "changes": []
    },
    {
      "block_type": "Text",
      "text": "The BHT is implemented as a memory structure with 1024 entries",
      "confidence": 0.92,
      "changes": ["merged_lines"]
    },
    {
      "block_type": "Table",
      "extraction_method": "camelot_lattice_15",
      "confidence": 0.89,
      "data": {
        "headers": ["Signal", "Width (bits)", "I/O", "Description", "Connection"],
        "rows": [...]
      },
      "changes": ["re_extracted", "fixed_split_header"]
    },
    {
      "block_type": "Text",
      "text": "The BHT is never flushed.",
      "confidence": 0.88,
      "changes": ["fixed_ligature"]
    }
  ],
  "overall_confidence": 0.91,
  "enhancement_summary": "Fixed table extraction and text ligature. Used 2 of 30 available tools."
}
```

## Key Principles

1. **Analyze First** - Understand what needs fixing before choosing tools
2. **Annotations Override** - Human guidance takes precedence
3. **Minimal Intervention** - Use fewest tools necessary
4. **Document Decisions** - Explain why each tool was or wasn't used
5. **Quality Thresholds** - Clear criteria for when to use alternatives
6. **Graceful Degradation** - Try best method first, fallback if needed

Remember: The goal is intelligent enhancement. Every tool has a cost in time and complexity. Use them wisely.