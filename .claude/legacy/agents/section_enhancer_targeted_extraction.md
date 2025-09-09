# Section Enhancement - Targeted Visual Extraction

## You Have Every Block's Exact Location

Every block in the section JSON has bbox coordinates: `[x0, y0, x1, y1]`

## Extract Any Region On Demand

### When Annotations Point to Specific Areas

```bash
# Annotation says: "Fix equation at bottom of page 10"
# Find the equation block:
cat section_001.json | jq '.blocks[] | select(.page == 10 and .block_type == "Equation")'
> {"block_id": "eq_001", "bbox": [100, 600, 500, 700], "text": "E = mc2"}

# Extract JUST that equation:
python pdf_snapshot.py doc.pdf --page 10 --bbox 100,600,500,700 -o equation_fix.png

# Now you can see exactly what needs fixing
```

### When Text Extraction is Unclear

```bash
# OCR gave you: "implernented memoiy struc-\nture"
# But you want to see the original:
cat section_001.json | jq '.blocks[] | select(.text | contains("implernented"))'
> {"block_id": "text_003", "bbox": [50, 300, 550, 350], "page": 5}

# Look at the original:
python pdf_snapshot.py doc.pdf --page 5 --bbox 50,300,550,350 -o text_region.png

# You see: "implemented memory structure" (clear in image, OCR failed)
```

### When Forms Need Analysis

```bash
# Block marked as "Form" but structure unclear:
cat section_001.json | jq '.blocks[] | select(.block_type == "Form")'
> {"block_id": "form_001", "bbox": [100, 200, 500, 500], "page": 12}

# Extract the form region:
python pdf_snapshot.py doc.pdf --page 12 --bbox 100,200,500,500 -o form_region.png

# You see: 3 input fields with labels above them, not beside them
# Decision: Restructure to show correct label-input relationships
```

### When Handwriting is Detected

```bash
# Found handwritten annotation:
cat annotations.json | jq '.annotations[] | select(.type == "ink")'
> {"page": 8, "rect": [400, 100, 550, 150], "content": "handwritten note"}

# Extract that specific region:
python pdf_snapshot.py doc.pdf --page 8 --bbox 400,100,550,150 -o handwriting.png

# You can read: "Table continues on next page"
```

## Smart Extraction Patterns

### Pattern 1: Suspicious Block Investigation

```python
# For any suspicious block
suspicious = [b for b in blocks if b.get('is_suspicious')]
for block in suspicious:
    # Extract just that block's region
    snapshot = extract_region(
        page=block['page'],
        bbox=block['bbox']
    )
    # Analyze what's really there vs. what was extracted
```

### Pattern 2: Equation Collection

```python
# Get all equations for batch analysis
equations = [b for b in blocks if b['block_type'] == 'Equation']
for i, eq in enumerate(equations):
    extract_region(
        page=eq['page'],
        bbox=eq['bbox'],
        output=f'equation_{i:03d}.png'
    )
# Now you can see all equations and ensure consistent formatting
```

### Pattern 3: Table Structure Verification

```python
# When table extraction seems wrong
table = get_table_block()
# Extract wider region to see context
expanded_bbox = [
    table['bbox'][0] - 20,  # 20px padding
    table['bbox'][1] - 20,
    table['bbox'][2] + 20,
    table['bbox'][3] + 20
]
extract_region(page=table['page'], bbox=expanded_bbox)
# See if there's a caption above or continuation below
```

## Decision Making Based on Targeted Views

```markdown
Looking at equation_001.png (extracted from bbox [150,400,450,500]):
- The equation is actually: E = mc²  (superscript clearly visible)
- Current text has "E = mc2" (missing superscript)
- There's also a subscript: E₀ that was extracted as "E0"

Decision: Fix all super/subscripts in this equation block
```

## Remember

- You don't need to process the entire page
- Extract EXACTLY what you need to see
- Use bbox coordinates to surgical precision
- Expand regions slightly if you need context
- This is especially powerful for fixing specific issues

Every bbox is a window into the original PDF. Use them!