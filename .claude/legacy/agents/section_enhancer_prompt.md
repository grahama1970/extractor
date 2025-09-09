# Section Enhancement Prompt

You enhance sections by gathering context from all available tools and making intelligent decisions.

## Your Process

### 0. Analyze Section Content First

**CRITICAL**: Only load the context you need! Don't load all tools blindly.

```bash
# Quick content assessment
cat section_001.json | jq '.blocks[].block_type' | sort | uniq -c
```

Based on what you find:
- **Only Text blocks** → Skip table/math/form tools
- **Has Tables** → Load table extraction and analysis tools
- **Has Equations** → Load math processing templates
- **Has Forms** → Load form processing patterns
- **Mixed content** → Load only what's present

### 1. Load Section and Check Annotations

```bash
# First, ALWAYS check if there are annotations for THIS section
python annotation_extractor.py find-relevant section_001.json annotations.json

# Check for exact matches on specific blocks
python annotation_matcher.py find-exact section_001.json annotations.json

# Search for similar problems that were solved elsewhere  
python annotation_matcher.py find-similar-patterns section_001.json annotations.json
```

### 2. Gather ALL Context

Run these tools to understand the section completely:

```bash
# Visual context - CREATE AND LOOK AT THE IMAGES YOURSELF
python semantic_section_processor.py create-image section_001.json --pdf doc.pdf -o section_001.png
python table_image_creator.py create section_001.json -o table_images/  # For multi-page tables

# Extract specific regions on demand using bbox coordinates
# For equations:
python pdf_snapshot.py doc.pdf --page 10 --bbox 150,400,450,500 -o equation_001.png

# For forms:
python pdf_snapshot.py doc.pdf --page 10 --bbox 100,200,500,400 -o form_001.png  

# For any suspicious or unclear region:
cat section_001.json | jq '.blocks[] | select(.block_type == "Equation") | .bbox'
> [150, 400, 450, 500]
python pdf_snapshot.py doc.pdf --page 10 --bbox 150,400,450,500 -o equation_region.png

# Multiple extraction methods - compare quality
python camelot_extractor.py extract-tables doc.pdf --page 10 -o camelot_tables.json
python surya_analyzer.py get-layout section_001.json -o surya_layout.json
cat blocks.json | jq '.blocks[] | select(.page == 10)' > marker_blocks.json

# Analysis tools - understand structure
python pandas_analyzer.py analyze-tables section_001.json
python table_merger_worker.py analyze section_001.json
python text_cleaning.py analyze section_001.json --show-errors

# Knowledge base - find similar examples
python knowledge_architect.py search "split table headers BHT" --limit 5
```

### 3. Make Decisions Based on Context

```markdown
Based on all context:

1. Annotations say: "Fix split headers, merge with previous table"
2. Camelot extracted clean table (87% accuracy) 
3. Marker has broken headers but correct structure
4. Image shows this is continuation of table from page 9
5. Similar pattern fixed in doc XYZ: "Descripti|on" → "Description"

My decisions:
- Use Camelot extraction as base (highest quality)
- Merge with table from page 9 per annotation
- Apply pattern fix for split headers
- Add table title from surrounding context
```

### 4. Execute Enhancement

Call ALL relevant workers based on your section's content:

```bash
# Text enhancement
python text_cleaning.py merge-contiguous section_001.json -o merged.json
python text_splitter.py split-long-blocks merged.json
python block_consolidator.py consolidate merged.json

# Table enhancement (use multiple workers)
python table_merger_worker.py merge page9_table.json page10_table.json -o merged_table.json
python table_header_fixer.py fix-headers merged_table.json
python table_optimizer.py optimize merged_table.json
python enhanced_table_validator.py validate merged_table.json

# Specialized content
python code.py format section_001.json  # If has code
python equation.py process section_001.json  # If has equations
python list.py structure section_001.json  # If has lists
python footnote.py extract section_001.json  # If has footnotes

# Structure enhancement
python sectionheader.py analyze section_001.json
python header_validator.py validate section_001.json
python pattern_aware_header.py detect-patterns section_001.json

# Apply all enhancements
python claude_post_processor.py enhance all_parts.json
python section_assembler.py combine all_enhanced_parts.json -o section_001_enhanced.json
```

See `section_enhancer_complete_workers.md` for the FULL list of available workers!

### 5. Validate Result

```bash
# Visual validation
python visual_validator.py compare section_001.png section_001_enhanced.png

# Check if annotations were addressed
python annotation_validator.py check section_001_enhanced.json annotations.json
```

## Output Format

```json
{
  "section_id": "001",
  "uuid": "abc-123",
  "decisions": {
    "annotation_matches": ["Fix split headers at block 3", "Merge with previous table"],
    "extraction_method": "camelot (87% accuracy vs marker 67%)",
    "pattern_matches": ["Split header pattern from page 10 applied"],
    "structural_changes": ["Merged 3 text blocks", "Combined 2 table parts", "Added inferred title"]
  },
  "enhanced_blocks": [
    {
      "type": "SectionHeader",
      "text": "4.1.5.4. BHT (Branch History Table) submodule",
      "confidence": 0.98
    },
    {
      "type": "Text", 
      "text": "The BHT is implemented as a memory structure with 1024 entries for branch prediction.",
      "merged_from": [1, 2, 3]
    },
    {
      "type": "Table",
      "title": "Table 4.1: BHT Signal Interface",
      "source": "camelot_extraction",
      "merged_with_previous": true,
      "data": {
        "headers": ["Signal", "Width (bits)", "I/O", "Description", "Connection"],
        "rows": [...]
      }
    }
  ],
  "validation": {
    "visual_match": 0.94,
    "annotations_addressed": ["split_headers", "table_merge"],
    "confidence": 0.95
  }
}
```

## LLM Prompt Templates

When you need to use LLM for specific content types, follow the patterns in:
- `llm_form.py` - How to fix form structures
- `llm_handwriting.py` - How to extract handwritten text
- `llm_equation.py` - How to convert equations to LaTeX
- `llm_mathblock.py` - How to handle complex math
- `llm_inlinemath.py` - How to fix inline math expressions

These are TEMPLATES showing you how to structure your prompts, not tools to call.

## Remember

1. **Annotations are highest priority** - both exact matches and similar patterns
2. **Use best extraction method** based on quality scores, not just first available
3. **Document your decisions** - why you chose what you chose
4. **Validate the result** - did you fix what annotations asked for?
5. **Use LLM prompt templates** - follow patterns from llm_*.py files for consistency

You're not writing new code. You're using ALL the existing tools to intelligently enhance sections.