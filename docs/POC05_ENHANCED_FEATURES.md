# POC 05 Enhanced: Full Context Integration

## Overview

The enhanced version of POC 05 (`poc_05_fix_section_json_enhanced.py`) provides Claude with comprehensive context when fixing document sections, including:

1. **Relevant Annotations** (NEW)
2. **Table Analysis** (Camelot)
3. **Visual Screenshots**
4. **Specialized Content Detection**
5. **Document Type Classification**

## Annotation Integration

### How Annotations Are Found

The system uses **hybrid search** to find the most relevant annotations:

```python
# 1. Text similarity search on section titles and key blocks
search_terms = []
for section in sections[:5]:
    search_terms.append(section["title"])
for block in blocks[:20]:
    if block["text"]:
        search_terms.append(block["text"][:100])

# 2. ArangoDB query with similarity scoring
FOR ann IN annotation_analyses
    LET similarity = MAX(
        FOR term IN @search_terms
            RETURN SIMILARITY(ann.annotation_text, term, "levenshtein")
    )
    FILTER similarity > 0.6
    SORT similarity DESC
    LIMIT 10
```

### What's Included in Claude's Context

1. **Annotation Text & Context**
   - The highlighted/annotated text
   - Visual context (40% expanded snapshot)
   - Page location

2. **Analysis from Annotations**
   - Issue types identified
   - Suggested corrections
   - Pattern tags
   - Structural issues flagged

3. **Learned Patterns**
   - Pattern tags and recognition rules
   - Confidence scores
   - Application frequency

### Example Prompt Section

```
RELEVANT ANNOTATIONS FROM SIMILAR DOCUMENTS:
(These highlight areas that human reviewers found important or problematic)

1. Page 5: "Table 1: Component Specifications..."
   Issue: table_spans_sections
   Correction: Keep table with its caption in same section
   Patterns: table_caption, section_boundary
   ⚠️ STRUCTURAL ISSUE: Table split from its caption

2. Page 12: "3.2.1 Mathematical Framework..."
   Issue: missing_parent_section
   Patterns: numbered_subsection, orphaned_header
   ⚠️ STRUCTURAL ISSUE: Subsection without parent section

LEARNED PATTERNS THAT MAY APPLY:

- table_caption: 15 instances
  Recognition: Starts with "Table" followed by number and colon
  ⚠️ This pattern often indicates section structure issues

- section_numbering_gap: 8 instances
  Recognition: Section numbers skip (e.g., 3.1 to 3.3)

MOST FREQUENTLY APPLIED PATTERNS:
- misclassified_header: Applied 23 times
- table_as_text: Applied 18 times
```

## Table Analysis Integration

Using Camelot for advanced table extraction:

```python
# Extract tables at specific locations
tables = camelot.read_pdf(
    str(pdf_path),
    pages=str(page_num),
    flavor='lattice',  # For structured tables
    table_areas=[bbox]
)

# Provide to Claude:
- Table dimensions (rows x columns)
- Header detection
- Cell data preview
- Extraction accuracy
```

## Visual Context

The enhanced version provides visual screenshots:

1. **Problematic Sections** - Full page view of sections with issues
2. **Complex Regions** - Expanded views of equations, forms, tables
3. **Annotation Visuals** - Images from annotated regions

## Specialized Content Detection

Categorizes and tracks:
- **Equations** - With numbering patterns
- **Forms** - Interactive elements
- **Complex Regions** - Figures, diagrams
- **Handwriting** - Manual annotations
- **Inline Math** - Mathematical expressions

## Usage

### Basic Version
```bash
python poc_05_fix_section_json.py fix input.json
```

### Enhanced Version
```bash
python poc_05_fix_section_json_enhanced.py fix input.json --pdf document.pdf
```

## Benefits

1. **Context-Aware Fixes** - Claude understands what human reviewers found important
2. **Pattern Application** - Learned patterns guide structure decisions
3. **Visual Verification** - Screenshots help with complex layouts
4. **Table Intelligence** - Proper handling of table boundaries
5. **Specialized Handling** - Different strategies for equations, forms, etc.

## Output

The enhanced version adds annotation context to the output:

```json
{
  "analysis_context": {
    "annotations_used": {
      "count": 10,
      "patterns_available": 25,
      "top_patterns": ["table_caption", "section_numbering", "orphaned_content"]
    },
    "table_analysis": {...},
    "specialized_content": {...}
  }
}
```

## When to Use Enhanced Version

Use the enhanced version when:
- Document has complex structure (tables, equations, forms)
- Previous annotations exist in ArangoDB
- Visual layout affects section boundaries
- High accuracy is required

Use the basic version when:
- Simple text-only documents
- No annotations available
- Speed is priority over accuracy
- Limited system resources