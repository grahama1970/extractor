# Marker Extraction Indexing Strategy

## Overview

During Stage 3 (Marker Extraction), we add comprehensive indexing metadata to each PDF block to ensure reliable tracking and ordering throughout the pipeline.

## Index Fields Added During Extraction

Each block receives the following metadata:

### 1. **UUID** (Universally Unique Identifier)
- **Format**: Standard UUID v4 (e.g., `"62ad602a-6e16-4846-89fb-4348c61008e0"`)
- **Purpose**: Unique tracking through entire pipeline
- **Usage**: Primary key for all block operations, merges, and fixes

### 2. **Page** (Page Number)
- **Format**: 0-based integer (e.g., `0` for first page)
- **Purpose**: Document structure and context
- **Usage**: Grouping blocks by page, maintaining reading order

### 3. **Page Index** (Position Within Page)
- **Format**: 0-based integer within each page
- **Purpose**: Preserve block order within a page
- **Usage**: Reconstructing exact page layout

### 4. **Block ID** (Global Sequential ID)
- **Format**: Sequential integer across entire document
- **Purpose**: Global ordering and reference
- **Usage**: Quick lookups, maintaining document-wide sequence

### 5. **Original Index** (Preservation Field)
- **Format**: Same as block_id initially
- **Purpose**: Preserve original extraction order
- **Usage**: Debugging, tracking transformations

### 6. **Sort Key** (Composite Sorting Field)
- **Format**: `"PPPP_BBBB"` where P=page (4 digits), B=block_index (4 digits)
- **Example**: `"0001_0003"` = Page 2, Block 4
- **Purpose**: Easy sorting to maintain document order
- **Usage**: `blocks.sort(key=lambda x: x['sort_key'])`

## Example Block with Full Indexing

```json
{
  "uuid": "62ad602a-6e16-4846-89fb-4348c61008e0",
  "page": 0,
  "page_index": 3,
  "block_id": 15,
  "original_index": 15,
  "sort_key": "0000_0003",
  "type": "Text",
  "text": "4.1.5.4. BHT (Branch History",
  "bbox": [72, 234, 540, 258],
  "suspicious": true,
  "issues": ["incomplete_sentence"]
}
```

## Benefits of This Approach

1. **UUID Stability**: Blocks can be referenced reliably even after merges/deletes
2. **Multiple Sort Options**: Can sort by page, position, or global order
3. **Transformation Tracking**: Original_index preserves extraction order
4. **Page Context**: Easy to get all blocks from a specific page
5. **Efficient Operations**: Sort_key enables fast ordering without complex comparisons

## Usage in Pipeline

### Stage 4 (Suspicious Block Analysis)
- Reference blocks by UUID in decisions
- Use page/page_index for context analysis
- Sort_key maintains reading order in batches

### Stage 5 (Structure Building)
- Use page grouping for section boundaries
- Sort_key ensures proper hierarchical construction
- UUID links preserve relationships

### Stage 6 (Fixes and Merges)
- UUID-based operations (no index shifting issues)
- Original_index shows transformation history
- Page/page_index for layout reconstruction

## Best Practices

1. **Always preserve UUID** through all transformations
2. **Update block_id** when renumbering after merges
3. **Keep original_index** unchanged for audit trail
4. **Use sort_key** for any ordering operations
5. **Include page context** in analysis prompts

## Implementation Example

```python
# Sort blocks in document order
blocks_sorted = sorted(blocks, key=lambda x: x['sort_key'])

# Get all blocks from page 5
page_5_blocks = [b for b in blocks if b['page'] == 5]

# Find a specific block by UUID
block = next((b for b in blocks if b['uuid'] == target_uuid), None)

# Renumber blocks after merge
for idx, block in enumerate(blocks_sorted):
    block['block_id'] = idx  # Update global ID
    # Keep original_index unchanged
```

This comprehensive indexing strategy ensures robust block tracking and manipulation throughout the PDF extraction pipeline.