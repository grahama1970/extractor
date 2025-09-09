# Stage 06 Annotation Improvements

## What Was Missing

The original annotation handling was too simplistic:
- Only mapped annotations by single page number
- Didn't include annotation interpretations
- Didn't include annotation images/visual context
- Didn't find similar annotations from elsewhere in the document

## What I Added

### 1. Page-Based Annotation Collection
Now collects ALL annotations from ALL pages that a section covers:
```python
# Get all pages this section covers
section_pages = set()

# Add the section's own page
if "page" in section:
    section_pages.add(section["page"])
    
# Add pages from all blocks in the section
for block in section.get("blocks", []):
    if "page" in block:
        section_pages.add(block["page"])

# Get ALL annotations from these pages
```

### 2. Full Annotation Context
Each annotation now includes:
- `text`: The original annotation text
- `interpretation`: The LLM interpretation of what the annotation means
- `image`: Any visual context/image path associated with the annotation
- `page`: Which page it's from
- `type`: The annotation type
- `bbox`: Bounding box if available

### 3. Similar Annotation Finding
For EACH block in a section, finds similar annotations from other pages based on:

**For Table blocks:**
- Annotations mentioning "table", "merge", "split", "continued", "columns"
- Annotations with similar table content words

**For SectionHeader blocks:**
- Annotations mentioning "header", "section", "title", "mislabeled", "wrong"
- Annotations with similar header text (>2 words in common)

**For Text blocks:**
- Annotations mentioning "merge", "split", "fragmented", "broken"
- Annotations with similar text content (>3 words from first 10 words)

**General patterns:**
- Any annotation mentioning "merge blocks" applies to all block types

### 4. Enhanced Prompt Format
The prompt now includes detailed annotation information:
```
## Annotations from this section's pages (2):

1. Page 1 - comment:
   Text: Merge these tables
   Interpretation: These tables should be merged - they're the same table split across pages. The headers match and the data continues sequentially.
   Visual: tmp/annotations/ann_page1_table_merge.png

## Similar annotations from elsewhere (1):

1. Page 15 - Table-related annotation:
   Interpretation: Similar pattern found on page 15 - tables with matching headers on consecutive pages should be merged into single table
```

## Benefits

1. **Complete Context**: LLM sees ALL annotations relevant to the section, not just exact page matches
2. **Pattern Recognition**: Similar annotations help the LLM understand common patterns in the document
3. **Visual Evidence**: Annotation images provide visual proof of issues
4. **Human Guidance**: Interpretations give clear instructions on what needs to be fixed
5. **Cross-Document Learning**: Patterns from one part of the document can be applied to similar issues elsewhere

## Example Use Case

If a section spans pages 5-7 and contains a split table:
- Gets ALL annotations from pages 5, 6, and 7
- Finds similar table merge annotations from pages 15, 23, etc.
- Includes interpretations like "merge tables with matching headers"
- Shows visual evidence of the split
- LLM can apply the pattern even if this specific table wasn't annotated