# PDF Extraction Pipeline - Actual Implementation Flow

## Overview

The extractor pipeline is designed to handle PDFs with annotations and complex layouts by combining multiple extraction strategies in a specific sequence.

## Pipeline Steps

### Step 1: PyMuPDF Annotation Cleaning
**Purpose:** Remove annotations that would contaminate OCR results
**Implementation:** `extract_with_pymupdf()` in `unified_extractor.py`

```python
# Process each page to remove annotations
for page_num, page in enumerate(doc):
    # Remove all annotations (FreeText, highlights, etc.)
    for annot in page.annots():
        page.delete_annot(annot)
    
    # Render clean page as high-res image
    mat = fitz.Matrix(300/72, 300/72)  # 300 DPI
    pix = page.get_pixmap(matrix=mat)
    pix.save(f"page_{page_num}.png")
```

**Why:** Marker's OCR would otherwise merge annotation text with document content, corrupting extraction.

### Step 2: Marker OCR Layout Detection
**Purpose:** Identify layout elements (tables, figures, text regions)
**Implementation:** Via marker library with Surya models

```python
# Marker processes clean page images
# Identifies bounding boxes for:
# - Text regions
# - Tables
# - Figures
# - Equations
# - Section headers
```

### Step 3: Marker Table Extraction
**Purpose:** Extract table content using Marker's table detection
**Implementation:** Built into marker processing

```python
# Marker attempts to extract table structure
# Produces HTML representation:
# <table><tr><th>Signal</th><th>IO</th>...</tr></table>
```

### Step 4: Camelot Fallback for Failed Tables
**Purpose:** Re-extract tables when Marker fails
**Implementation:** Camelot integration (when available)

```python
# If table extraction confidence is low or corrupted:
tables = camelot.read_pdf(
    pdf_path,
    pages=str(page_num + 1),  # Camelot uses 1-based indexing
    flavor='lattice',         # For bordered tables
    line_scale=15,           # Fine-tune line detection
    table_areas=[bbox_str]   # Use Marker's detected bbox
)
```

### Step 5: Block Type Verification
**Purpose:** Fix mislabeled blocks, especially section headers
**Implementation:** `block_verification.py` and `sectionheader.py`

```python
# Identify suspicious headers that are mislabeled as Text
suspicious_patterns = [
    r'^\d+\.',                    # "1. Introduction"
    r'^\d+\.\d+',                 # "1.2 Background"
    r'^Chapter \d+',              # "Chapter 1"
    r'^Section \d+',              # "Section 2"
    r'^[A-Z][A-Z\s]+$',          # "INTRODUCTION"
]

# Convert mislabeled Text blocks to SectionHeader
if matches_pattern and not is_false_positive:
    block['block_type'] = 'SectionHeader'
```

### Step 6: Hierarchical Section Building
**Purpose:** Organize blocks into section nodes
**Implementation:** `hierarchy_builder.py`

```python
# Create section hierarchy
sections = []
current_section = None

for block in blocks:
    if block['block_type'] == 'SectionHeader':
        # Start new section
        current_section = {
            'title': block['text'],
            'blocks': [],
            'section_number': calculate_number(block['text']),
            'section_level': calculate_level(block['text'])
        }
        sections.append(current_section)
    elif current_section:
        # Add block to current section
        current_section['blocks'].append(block)
```

Each section node contains:
- Section header
- All blocks within that section (text, tables, figures)
- Section metadata (number, level, hash)

### Step 7: Contiguous Block Merging
**Purpose:** Merge adjacent blocks of same type within sections
**Implementation:** `merge_contiguous_text_blocks()` in orchestrator

```python
# Within each section, merge contiguous text blocks
for section in sections:
    merged_blocks = []
    current_text = None
    
    for block in section['blocks']:
        if block['block_type'] == 'Text' and current_text:
            # Merge with previous text block
            current_text['text'] += '\n\n' + block['text']
        else:
            # Start new block or different type
            if current_text:
                merged_blocks.append(current_text)
            current_text = block if block['block_type'] == 'Text' else None
            if block['block_type'] != 'Text':
                merged_blocks.append(block)
```

### Step 8: Text Cleaning and Normalization
**Purpose:** Clean PDF-specific encoding issues
**Implementation:** `text.py` processor

```python
# Clean text issues
text = text.replace('\u00AD', '')  # Remove soft hyphens
text = text.replace('\u200B', '')  # Remove zero-width spaces
text = normalize_whitespace(text)   # Fix spacing
text = fix_ligatures(text)          # fi, fl, etc.
text = fix_encoding_issues(text)    # Smart quotes, dashes
```

### Step 9: Export Formats
**Purpose:** Generate requested output format
**Implementation:** Output renderers

#### Gold Standard Format
```json
{
  "sections": [{
    "section_id": 0,
    "blocks": [
      {
        "block_type": "SectionHeader",
        "text": "4.1.5.4. BHT (Branch History Table) submodule",
        "section_titles": ["BHT (Branch History Table) submodule"],
        "section_number": "4.1.5.4",
        "section_level": 3
      },
      {
        "block_type": "Text",
        "text": "Merged contiguous text content..."
      },
      {
        "block_type": "Table",
        "text": "[{\"Signal\":\"clk_i\",\"IO\":\"in\",...}]"
      }
    ]
  }]
}
```

#### ArangoDB Format
```json
{
  "vertices": {
    "documents": [{...}],
    "sections": [{...}],
    "blocks": [{...}]
  },
  "edges": {
    "contains": [
      {"_from": "documents/doc1", "_to": "sections/sec1"},
      {"_from": "sections/sec1", "_to": "blocks/block1"}
    ]
  }
}
```

#### Original Block Order Format
Preserves the exact order blocks were extracted, without section grouping.

## Key Design Decisions

1. **Annotation Removal First**: Critical for clean OCR results
2. **Page-by-Page Processing**: Maintains spatial relationships
3. **Multiple Table Strategies**: Marker → Camelot fallback
4. **Late-Stage Text Cleaning**: Preserves structure during processing
5. **Section-Based Organization**: Logical document structure
6. **Format Flexibility**: Multiple output formats for different use cases

## Error Handling

Each step has fallback strategies:
- PyMuPDF fails → Try direct Marker
- Marker table fails → Try Camelot
- Camelot unavailable → Keep Marker result with low confidence flag
- Section detection fails → Flat block list

This pipeline ensures robust extraction even with challenging PDFs containing annotations, complex tables, and varied layouts.