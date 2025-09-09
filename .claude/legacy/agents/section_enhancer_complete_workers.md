# Complete Section Enhancement Worker List

## All Available Workers for Section Enhancement

### Core Visual Tools
```bash
# Section and table visualization
python semantic_section_processor.py create-image section.json --pdf doc.pdf
python table_image_creator.py create section.json --output table_images/
python pdf_snapshot.py doc.pdf --page 10 --bbox 100,200,500,400 -o region.png
```

### Text Processing Workers
```bash
# Text analysis and cleaning
python text_cleaning.py analyze section.json --show-errors
python text_cleaning.py merge-contiguous section.json
python text_splitter.py split-long-blocks section.json
python block_consolidator.py consolidate section.json
python block_merger.py merge-similar section.json
```

### Table Processing Workers
```bash
# Table analysis and enhancement
python table_merger_worker.py analyze section.json
python table_optimizer.py optimize section.json
python table_header_fixer.py fix-headers section.json
python table_classifier_fixer.py classify section.json
python enhanced_table_validator.py validate section.json
python camelot_fallback.py extract --pdf doc.pdf --page 10

# Advanced table analysis
python llm_table_merge_analyzer.py analyze section.json
python claude_table_merge_analyzer.py deep-analyze section.json
python annotation_guided_table_merger.py merge-with-guidance section.json annotations.json
```

### Content Type Processors
```bash
# Specialized content handlers
python code.py format section.json
python equation.py process section.json
python list.py structure section.json
python footnote.py extract section.json
python blockquote.py format section.json
python reference.py link section.json
```

### Header and Structure Workers
```bash
# Section structure analysis
python sectionheader.py analyze section.json
python header_validator.py validate section.json
python pattern_aware_header.py detect-patterns section.json
python header_pattern_query.py find-similar section.json
python annotation_guided_header_processor.py fix-with-annotations section.json
```

### Annotation Integration
```bash
# Annotation-based enhancement
python annotation_extractor.py find-relevant section.json annotations.json
python annotation_matcher.py find-exact section.json annotations.json
python annotation_search_processor.py search-patterns section.json
python annotation_guided_verifier.py verify section.json annotations.json
python annotation_learner.py learn-patterns annotations.json
```

### Knowledge Base Integration
```bash
# Knowledge-aware processing
python knowledge_architect.py search "similar sections"
python knowledge_aware_sectionheader.py enhance section.json
python knowledge_orchestrator.py coordinate section.json
python simple_annotation_learner.py find-examples section.json
```

### Quality and Validation
```bash
# Validation and confidence scoring
python confidence_standards.py evaluate section.json
python claude_content_validator.py validate section.json
python claude_section_verifier.py verify section.json
python visual_validator.py compare original.png enhanced.png
python corpus_validator.py check-consistency section.json
```

### Multi-Method Extraction
```bash
# Compare different extraction methods
python camelot_extractor.py extract-tables doc.pdf --page 10
python surya_analyzer.py get-layout section.json
python pandas_analyzer.py analyze-tables section.json
cat blocks.json | jq '.blocks[] | select(.page == 10)'
```

### Enhancement Orchestration
```bash
# Final assembly and processing
python claude_post_processor.py enhance section.json
python stage3_transformer.py transform section.json
python section_assembler.py combine enhanced_parts.json
```

## Task List for Complete Enhancement

Given a section to enhance:

### 1. Visual Analysis
☐ Create section image
☐ Create table images for multi-page tables
☐ Extract specific regions for equations/forms/unclear areas

### 2. Annotation Check
☐ Find relevant annotations
☐ Check exact location matches
☐ Search for similar patterns

### 3. Text Enhancement
☐ Analyze text for errors
☐ Merge contiguous blocks
☐ Fix OCR errors
☐ Consolidate related content

### 4. Table Enhancement  
☐ Analyze table structure
☐ Check for merge candidates
☐ Fix headers and alignment
☐ Validate with multiple methods

### 5. Specialized Content
☐ Format code blocks
☐ Convert equations to LaTeX
☐ Structure lists properly
☐ Link footnotes and references

### 6. Structure Enhancement
☐ Validate headers
☐ Detect patterns
☐ Apply annotation guidance
☐ Build proper hierarchy

### 7. Knowledge Integration
☐ Search for similar examples
☐ Apply learned patterns
☐ Store successful enhancements

### 8. Final Validation
☐ Visual comparison
☐ Confidence scoring
☐ Annotation verification
☐ Consistency check

## Remember: You Call ALL Relevant Workers

Don't just use a few tools - use EVERYTHING that applies to your section's content!