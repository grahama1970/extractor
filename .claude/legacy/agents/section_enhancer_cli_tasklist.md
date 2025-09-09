# Section Enhancement CLI Task List

You are enhancing sections. Here are ALL the CLI tools available to you:

## Available CLI Workers

### Core Pipeline CLI (`extract-pipeline`)
```bash
extract-pipeline extract-annotations doc.pdf -o annotations.json
extract-pipeline create-clean-pdf marked.pdf -o clean.pdf  
extract-pipeline run-marker clean.pdf -o blocks.json
extract-pipeline create-batches blocks.json -d /tmp/batches/
extract-pipeline apply-fixes blocks.json decisions.json -o fixed.json
extract-pipeline build-sections fixed_blocks.json -o sections.json
extract-pipeline enhance-sections sections.json doc.pdf -o enhanced.json
extract-pipeline validate-extraction enhanced.json --gold gold.json
extract-pipeline add-breadcrumbs enhanced.json -o final.json
```

### PDF Tools CLI (`pdf-tools`)
```bash
pdf-tools extract-images doc.pdf -o /tmp/images/
pdf-tools section-image doc.pdf sections.json -o section_001.png
pdf-tools table-image doc.pdf tables.json -o table_001.png  
pdf-tools snapshot doc.pdf --page 5 --x0 100 --y0 200 --x1 500 --y1 400 -o region.png
pdf-tools merge-images image1.png image2.png -o merged.png --divider red
```

### Worker CLIs

#### Text Processing
```bash
python text_cleaning.py process section_001.json -o section_001_clean.json
python text_cleaning.py merge-contiguous section_001.json  # Merges split paragraphs
```

#### Table Processing  
```bash
python table_merger_worker.py analyze section_001.json  # Analyze if tables should merge
python table_merger_worker.py merge table1.json table2.json -o merged_table.json
python table_image_creator.py create section_001.json -o table_images/
python llm_table.py enhance section_001.json  # Fix table structure
python llm_table_merge.py process section_001.json  # Smart table merging
```

#### Math & Equations
```bash
python llm_equation.py process section_001.json
python llm_mathblock.py process section_001.json  
python llm_inlinemath.py process section_001.json
```

#### Code Processing
```bash
python code.py format section_001.json
python code.py detect-language section_001.json
```

#### Image Processing
```bash
python llm_claude_image_description.py describe section_001_image.png
python semantic_section_processor.py create-image section_001.json --pdf doc.pdf
```

#### Other Processors
```bash
python llm_form.py process section_001.json
python llm_handwriting.py process section_001.json  
python llm_complex.py enhance section_001.json
python blockquote.py process section_001.json
python footnote.py process section_001.json
python list.py process section_001.json
```

#### Analysis Tools
```bash
python semantic_section_processor.py analyze-pandas section_001.json  # Pandas table analysis
python annotation_extractor.py find-relevant section_001.json annotations.json
```

## Task List for Section Batch

Given: `/tmp/section_batches/batch_001.json` with 10 sections

### Section 001 - Technical spec with tables
☐ `python text_cleaning.py merge-contiguous section_001.json`
☐ `python semantic_section_processor.py create-image section_001.json --pdf doc.pdf`
☐ `python table_merger_worker.py analyze section_001.json`
☐ `python llm_table.py enhance section_001.json`
☐ `python llm_claude_image_description.py describe section_001_image.png`

### Section 002 - Math content
☐ `python text_cleaning.py process section_002.json`
☐ `python llm_equation.py process section_002.json`
☐ `python llm_mathblock.py process section_002.json`

### Section 003 - Code blocks
☐ `python code.py detect-language section_003.json`
☐ `python code.py format section_003.json`
☐ `python text_cleaning.py process section_003.json`

### Section 004 - Complex table across pages
☐ `python table_merger_worker.py analyze section_004.json`
☐ `python table_image_creator.py create section_004.json`
☐ `python llm_table_merge.py process section_004.json`
☐ `pdf-tools snapshot doc.pdf --page 10 --x0 100 --y0 300 --x1 500 --y1 700`

### Section 005 - Lists and footnotes
☐ `python list.py process section_005.json`
☐ `python footnote.py process section_005.json`
☐ `python text_cleaning.py merge-contiguous section_005.json`

[... continue for all 10 sections ...]

## After All Complete
☐ `python section_enhancer_orchestrator.py apply-enhancements original_sections.json`