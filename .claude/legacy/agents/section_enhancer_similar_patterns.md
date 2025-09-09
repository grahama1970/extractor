# Section Enhancement - Learning from Similar Annotations

## Two Types of Annotation Matching

### 1. Exact Location Match (Direct Hit)
"There's an annotation RIGHT HERE on this block"

### 2. Similar Problem Match (Pattern Recognition)  
"There's an annotation ELSEWHERE that solved this SAME PROBLEM"

## Example: Similar Problem Pattern

```python
# Current block you're analyzing
current_block = {
    "page": 25,
    "bbox": [100, 400, 500, 450],
    "text": "Table 5.2: Memory Interface Sig-\nnals",  # Split title
    "type": "TableTitle"
}

# Search for SIMILAR problems in annotations
similar_annotations = search_annotations_by_pattern(
    pattern="split title",
    problem_type="text split across lines"
)

# Found similar annotation from page 10!
{
    "page": 10,
    "rect": [120, 200, 480, 250],
    "content": "Fix split title: merge 'Sig-' + 'nals' = 'Signals'",
    "problem_pattern": "hyphenated_split",
    "solution_pattern": "merge_and_dehyphenate"
}
```

## Pattern Matching Logic

```python
def find_similar_annotation_patterns(current_block, all_annotations):
    """Find annotations that solved similar problems."""
    
    # Identify the problem type
    current_problems = identify_problems(current_block)
    # e.g., ["split_word", "broken_table", "ocr_error"]
    
    similar_solutions = []
    
    for annotation in all_annotations:
        # Check if annotation describes similar problem
        if has_similar_problem(annotation, current_problems):
            similar_solutions.append({
                "annotation": annotation,
                "similarity_score": calculate_similarity(current_block, annotation),
                "solution_type": extract_solution_type(annotation)
            })
    
    # Sort by relevance
    return sorted(similar_solutions, key=lambda x: x['similarity_score'], reverse=True)

def identify_problems(block):
    """Identify what problems this block has."""
    problems = []
    
    # Check for split words
    if "-\n" in block['text']:
        problems.append("hyphenated_split")
        
    # Check for broken table headers  
    if block['type'] == 'Table' and '|' in block['text']:
        if any(cell.endswith(('ti', 'on', 'ing')) for cell in block['text'].split('|')):
            problems.append("split_table_header")
            
    # Check for OCR errors
    ocr_patterns = ['rn' -> 'm', 'l' -> 'I', '0' -> 'O']
    if has_common_ocr_errors(block['text']):
        problems.append("ocr_errors")
        
    return problems
```

## Learning from Annotation Patterns

```python
# Build a knowledge base of annotation patterns
annotation_patterns = {
    "split_table_header": {
        "examples": [
            {
                "before": "Descripti|on",
                "after": "Description",
                "annotation": "Fix split header"
            },
            {
                "before": "Connec|tion",
                "after": "Connection", 
                "annotation": "Merge split column"
            }
        ],
        "solution": "merge_split_parts"
    },
    
    "hyphenated_split": {
        "examples": [
            {
                "before": "imple-\nmented",
                "after": "implemented",
                "annotation": "Remove hyphen and merge"
            }
        ],
        "solution": "dehyphenate_and_merge"
    },
    
    "table_continuation": {
        "examples": [
            {
                "annotation": "This table continues from previous page",
                "solution": "find_and_merge_previous_table"
            }
        ],
        "solution": "merge_across_pages"
    }
}
```

## Complete Enhancement Decision Process

```python
def enhance_block_with_pattern_matching(block, all_annotations):
    # 1. FIRST: Check exact location match
    exact_match = find_annotation_at_location(block, all_annotations)
    if exact_match:
        return apply_exact_annotation_fix(block, exact_match)
    
    # 2. SECOND: Find similar problems that were annotated
    similar_patterns = find_similar_annotation_patterns(block, all_annotations)
    if similar_patterns:
        best_match = similar_patterns[0]  # Highest similarity
        
        print(f"Found similar problem solved elsewhere:")
        print(f"  Problem: {best_match['annotation']['content']}")
        print(f"  Solution: {best_match['solution_type']}")
        print(f"  Similarity: {best_match['similarity_score']:.2%}")
        
        return apply_pattern_based_fix(block, best_match)
    
    # 3. THIRD: Use general cleaning rules
    return apply_standard_cleaning(block)
```

## Real Example: Pattern-Based Enhancement

```json
{
  "current_block": {
    "text": "Signal|Width|Descripti",
    "page": 25,
    "problem_identified": "split_table_header"
  },
  
  "pattern_search_result": {
    "found_similar": true,
    "similar_annotation": {
      "page": 10,
      "content": "Fix split header: 'Descripti|on' -> 'Description'",
      "problem": "split_table_header",
      "solution": "merge_split_cell"
    },
    "similarity_score": 0.92
  },
  
  "action_taken": {
    "method": "pattern_based_fix",
    "description": "Applied same fix as annotation on page 10",
    "before": "Signal|Width|Descripti",
    "after": "Signal|Width|Description",
    "confidence": 0.92
  }
}
```

## Pattern Library Built from Annotations

```python
# As you process documents, build a library
pattern_library = {
    "split_headers": [
        {"pattern": "Descripti|on", "fix": "Description", "count": 15},
        {"pattern": "Connec|tion", "fix": "Connection", "count": 8},
        {"pattern": "Sig|nal", "fix": "Signal", "count": 12}
    ],
    
    "ocr_corrections": [
        {"pattern": "implernented", "fix": "implemented", "count": 23},
        {"pattern": "mernory", "fix": "memory", "count": 19}
    ],
    
    "merge_instructions": [
        {"pattern": "table continues from", "action": "merge_with_previous", "count": 31}
    ]
}
```

## The Power of Pattern Matching

1. **Direct hits** - Annotation exactly here: "Fix THIS"
2. **Pattern hits** - Similar problem elsewhere: "I've seen this before"
3. **Learning** - Build library of problem→solution patterns
4. **Confidence** - Higher confidence when pattern was human-verified

This way, one human annotation teaching you to fix "Descripti|on" helps you fix similar splits throughout the entire document!