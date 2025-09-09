# Section Enhancement - Annotation Matching

## The Critical Check: Is There an Annotation HERE?

When analyzing any block or section, FIRST check if there's an annotation at this EXACT location:

```python
# For each block in the section
block = {
    "page": 10,
    "bbox": [100, 200, 500, 300],  # x0, y0, x1, y1
    "text": "Broken content here"
}

# Find annotations that overlap this EXACT region
matching_annotations = find_annotations_at_location(
    page=block["page"],
    bbox=block["bbox"],
    annotations=all_annotations
)
```

## Example: Direct Annotation Match

```json
// Block being analyzed
{
  "block_id": "block_045",
  "page": 10,
  "bbox": [150, 250, 450, 280],
  "text": "Signal|IO|Descripti",
  "type": "Table"
}

// Annotation at SAME location
{
  "type": "highlight",
  "page": 10,
  "rect": [148, 248, 452, 282],  // Almost exact same bbox!
  "content": "Fix this broken header - should be 'Description'",
  "author": "human_reviewer"
}
```

**This is a DIRECT HIT!** The human specifically marked THIS table header for fixing.

## How to Use Direct Annotation Matches

```python
def enhance_block(block, annotations):
    # 1. Check for direct annotation match
    direct_annotations = find_exact_match(block, annotations)
    
    if direct_annotations:
        # Human specifically marked THIS block
        for ann in direct_annotations:
            if "Fix this broken header" in ann['content']:
                # Apply the EXACT fix the human requested
                block['text'] = block['text'].replace('Descripti', 'Description')
                block['enhancement_note'] = f"Fixed per annotation: {ann['content']}"
                
            elif "merge with next" in ann['content']:
                # Human wants THIS block merged
                block['merge_with_next'] = True
                
            elif "this is actually code" in ann['content']:
                # Human says marker got the type wrong
                block['type'] = 'Code'
                block['enhancement_note'] = "Reclassified per human annotation"
```

## Annotation Location Matching Logic

```python
def annotations_match_location(block, annotation):
    """Check if annotation is at same location as block."""
    
    # Must be same page
    if block['page'] != annotation['page']:
        return False
        
    # Calculate bbox overlap
    block_bbox = block['bbox']
    ann_rect = annotation['rect']
    
    # Convert to same format
    b_x0, b_y0, b_x1, b_y1 = block_bbox
    a_x0, a_y0, a_x1, a_y1 = ann_rect
    
    # Calculate intersection
    x_overlap = max(0, min(b_x1, a_x1) - max(b_x0, a_x0))
    y_overlap = max(0, min(b_y1, a_y1) - max(b_y0, a_y0))
    
    intersection_area = x_overlap * y_overlap
    
    # Calculate union
    block_area = (b_x1 - b_x0) * (b_y1 - b_y0)
    ann_area = (a_x1 - a_x0) * (a_y1 - a_y0)
    union_area = block_area + ann_area - intersection_area
    
    # IoU (Intersection over Union)
    iou = intersection_area / union_area if union_area > 0 else 0
    
    # Match if IoU > 0.8 (80% overlap)
    return iou > 0.8
```

## Priority Order for Enhancement

1. **HIGHEST PRIORITY: Direct annotation matches**
   - Human specifically marked THIS content
   - Follow their instructions EXACTLY

2. **MEDIUM PRIORITY: Nearby annotations**  
   - Annotations on same page but different location
   - May provide context

3. **LOW PRIORITY: General patterns**
   - No specific annotation
   - Use standard cleaning rules

## Example Enhancement Decision Tree

```python
def enhance_section(section, all_annotations):
    for block in section['blocks']:
        # 1. Check for direct match
        direct_matches = find_annotations_at_exact_location(block, all_annotations)
        
        if direct_matches:
            # Human marked THIS specific block
            priority = "CRITICAL"
            action = parse_human_instruction(direct_matches[0])
            apply_human_requested_fix(block, action)
            
        else:
            # 2. Check for nearby annotations  
            nearby = find_annotations_same_page(block, all_annotations)
            
            if nearby:
                # Human marked something on this page
                priority = "HIGH"
                context = extract_context_from_nearby(nearby)
                apply_contextual_fix(block, context)
                
            else:
                # 3. No annotations - use standard rules
                priority = "NORMAL"
                apply_standard_cleaning(block)
```

## Real Example

```json
{
  "section_id": 5,
  "enhancement_log": [
    {
      "block_id": "block_045",
      "annotation_match": {
        "found": true,
        "iou": 0.95,
        "annotation": "Fix header: Description",
        "location_match": "EXACT"
      },
      "action_taken": "Fixed 'Descripti' → 'Description' per human annotation",
      "priority": "CRITICAL"
    },
    {
      "block_id": "block_046", 
      "annotation_match": {
        "found": false,
        "nearest_annotation": "2 blocks away"
      },
      "action_taken": "Standard OCR cleaning",
      "priority": "NORMAL"
    }
  ]
}
```

The key is: **Always check if there's an annotation at the EXACT location first!** That's your highest priority instruction from the human.