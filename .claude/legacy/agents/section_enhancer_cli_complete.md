# Section Enhancement - Complete CLI Tool Reference

You enhance PDF sections by analyzing content and selectively using the appropriate tools from this comprehensive list.

## Usage Instructions

1. **Analyze section first** - Check what content types exist
2. **Check annotations** - Human corrections override algorithms  
3. **Select minimal tools** - Use only what's needed
4. **Document decisions** - Explain why tools were/weren't used

## Available Tools by Category

### Text Processing Tools

#### text_cleaning
**Usage:** `python text_cleaning.py <command> <section.json> [-o output.json]`  
**Purpose:** Fix OCR errors, encoding issues, and text formatting
**When to use:** Text has encoding problems (�), ligatures (ﬁ), or needs merging
**Commands:**
  - `merge-contiguous` - Merge split paragraphs
  - `fix-unicode` - Fix encoding errors
  - `fix-ligatures` - Convert ﬁ,ﬂ to fi,fl
  - `normalize-whitespace` - Clean extra spaces
  - `analyze` - Show issues without fixing

#### block_consolidator
**Usage:** `python block_consolidator.py consolidate <section.json> [--threshold 10.0]`
**Purpose:** Merge related blocks based on proximity
**When to use:** Multiple small blocks should be one unit

#### text_splitter
**Usage:** `python text_splitter.py split-long-blocks <section.json> [--max-length 1000]`
**Purpose:** Split overly long blocks at natural boundaries
**When to use:** Blocks exceed readable length (>1000 chars)

### Table Extraction & Analysis Tools

#### camelot_extractor
**Usage:** `python camelot_extractor.py extract-tables <pdf> --page N [--lattice] [--stream]`
**Purpose:** Extract tables using computer vision techniques
**When to use:** Marker extraction quality < 70% OR tables have clear borders
**Key options:**
  - `--lattice --line-width 15` - For bordered tables
  - `--stream` - For borderless tables
  - `--format json|csv` - Output format

#### table_merger_worker
**Usage:** `python table_merger_worker.py <command> <input.json>`
**Purpose:** Analyze and merge multi-page tables
**When to use:** Tables split across pages OR missing headers on continuation
**Commands:**
  - `analyze` - Check if tables should merge
  - `merge <table1.json> <table2.json>` - Combine tables
  - `find-continuations` - Detect split tables

#### pandas_analyzer
**Usage:** `python pandas_analyzer.py analyze-tables <section.json> [-o report.json]`
**Purpose:** Statistical analysis of table content
**When to use:** Need to understand table structure, data types, quality
**Returns:** Shape, dtypes, null counts, numeric columns

#### table_header_fixer
**Usage:** `python table_header_fixer.py fix-headers <table.json> [--auto-detect]`
**Purpose:** Repair split or malformed headers
**When to use:** Headers like "Descripti|on" or misaligned columns

#### table_image_creator
**Usage:** `python table_image_creator.py create <section.json> -o <output_dir/>`
**Purpose:** Generate visual representations of tables
**When to use:** Need visual validation of table structure

### Visual Analysis Tools

#### semantic_section_processor
**Usage:** `python semantic_section_processor.py create-image <section.json> --pdf <doc.pdf> -o <image.png>`
**Purpose:** Create merged visualization of entire section
**When to use:** Need to verify overall layout and structure
**Features:** Shows page boundaries, block relationships

#### pdf_snapshot
**Usage:** `python pdf_snapshot.py <pdf> --page N --bbox x0,y0,x1,y1 -o <region.png>`
**Purpose:** Extract specific regions from PDF
**When to use:** Need to examine equations, forms, or problem areas
**Example:** `--bbox 100,200,500,400` extracts that rectangle

### Structure & Metadata Tools

#### sectionheader
**Usage:** `python sectionheader.py analyze <section.json> [--fix-hierarchy]`
**Purpose:** Validate and fix section header hierarchy
**When to use:** Headers seem out of order or incorrectly nested

#### header_validator
**Usage:** `python header_validator.py validate <section.json> [--strict]`
**Purpose:** Check header formatting and consistency
**When to use:** Headers follow specific formatting rules

#### pattern_aware_header
**Usage:** `python pattern_aware_header.py detect-patterns <section.json>`
**Purpose:** Find recurring header patterns
**When to use:** Document has consistent header formatting

#### section_metadata_propagator
**Usage:** `python section_metadata_propagator.py add-breadcrumbs <section.json>`
**Purpose:** Add hierarchical context to sections
**When to use:** Need parent section references

### Annotation & Knowledge Tools

#### annotation_extractor
**Usage:** `python annotation_extractor.py find-relevant <section.json> <annotations.json>`
**Purpose:** Find human corrections for this section
**When to use:** ALWAYS - check annotations first
**Priority:** Highest - overrides algorithmic decisions

#### annotation_matcher
**Usage:** `python annotation_matcher.py <command> <section.json> <annotations.json>`
**Purpose:** Match annotation patterns
**Commands:**
  - `find-exact` - Exact bbox overlap
  - `find-similar-patterns` - Pattern matching
  - `find-by-content` - Text similarity

#### knowledge_architect
**Usage:** `python knowledge_architect.py search "<query>" [--limit 5]`
**Purpose:** Find similar problems and solutions
**When to use:** Complex issues need historical context

### Specialized Content Tools

#### equation
**Usage:** `python equation.py process <section.json> [--to-latex]`
**Purpose:** Process mathematical equations
**When to use:** Section contains Equation blocks

#### code
**Usage:** `python code.py format <section.json> [--language auto]`
**Purpose:** Format and syntax highlight code blocks
**When to use:** Code blocks need proper formatting

#### list
**Usage:** `python list.py structure <section.json> [--style auto]`
**Purpose:** Structure bulleted and numbered lists
**When to use:** Lists need consistent formatting

#### footnote
**Usage:** `python footnote.py extract <section.json> [--link-references]`
**Purpose:** Extract and link footnotes
**When to use:** Document has footnote references

#### blockquote
**Usage:** `python blockquote.py process <section.json>`
**Purpose:** Format quoted text blocks
**When to use:** Section contains citations or quotes

### Quality & Validation Tools

#### quality_scorer
**Usage:** `python quality_scorer.py compare <method1.json> <method2.json>`
**Purpose:** Compare extraction quality between methods
**When to use:** Multiple extraction methods available
**Returns:** Confidence scores for each method

#### visual_validator
**Usage:** `python visual_validator.py compare <original.png> <enhanced.png>`
**Purpose:** Visual similarity comparison
**When to use:** Verify enhancements preserve content

#### confidence_scorer
**Usage:** `python confidence_scorer.py score <section.json>`
**Purpose:** Calculate overall section confidence
**When to use:** Need quality metrics

## Decision Flow Example

```bash
# 1. Analyze section
cat section.json | jq '.blocks[].block_type' | sort | uniq -c
# Result: 5 Text, 2 Table, 1 Equation

# 2. Check annotations (ALWAYS)
python annotation_extractor.py find-relevant section.json annotations.json
# Result: "Fix split table headers"

# 3. Assess table quality
python quality_scorer.py assess-tables section.json
# Result: Table 1: 0.65 confidence (low)

# 4. Select tools based on findings:
# - Low table confidence + annotation → use camelot_extractor
# - Has equation → prepare pdf_snapshot for visual check
# - Text blocks look clean → skip text_cleaning

# 5. Execute selected tools
python camelot_extractor.py extract-tables doc.pdf --page 10 --lattice
python pdf_snapshot.py doc.pdf --page 10 --bbox 150,400,450,500 -o equation.png

# 6. Validate results
python visual_validator.py compare original_section.png enhanced_section.png
```

## Output Format

Always include tool usage rationale:

```json
{
  "section_id": "001",
  "analysis": {
    "block_types": {"Text": 5, "Table": 2, "Equation": 1},
    "issues_found": ["low_table_confidence", "equation_needs_latex"],
    "annotations": ["fix_split_headers"]
  },
  "tools_used": [
    {
      "tool": "camelot_extractor",
      "command": "extract-tables doc.pdf --page 10 --lattice",
      "reason": "Marker confidence 0.65 < threshold 0.7",
      "result": "success",
      "confidence_improvement": "0.65 → 0.89"
    }
  ],
  "tools_considered_not_used": {
    "text_cleaning": "Text blocks clean, no encoding issues",
    "table_merger": "No multi-page tables detected",
    "pandas_analyzer": "Table structure clear after extraction"
  },
  "enhanced_blocks": [...],
  "overall_confidence": 0.91
}
```

## Important Guidelines

1. **Minimal intervention** - If content is already good (>0.85 confidence), leave it
2. **Annotations first** - Human guidance overrides algorithms
3. **Document everything** - Explain tool selection reasoning
4. **Quality thresholds** - Clear criteria for tool usage
5. **Graceful degradation** - Try best method, fallback if needed

Remember: You have 30+ tools available, but most sections need only 2-3. Choose wisely based on actual needs, not tool availability.