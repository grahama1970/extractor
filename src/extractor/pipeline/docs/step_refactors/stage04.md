Yes, **Stage 04** is another excellent candidate for refactoring.

Currently, it mixes **Parsing Logic** (regex for section numbers), **Structural Logic** (building the tree/hierarchy), and **IO/Visuals** (PyMuPDF image extraction) into one file.

I recommend creating a dedicated utility package: `extractor/pipeline/utils/sections/`.

### Recommended Directory Structure

```text
extractor/pipeline/
├── steps/
│   └── 04_section_builder.py      <-- Coordinator (Configuration & Flow)
└── utils/
    └── sections/
        ├── __init__.py
        ├── parsing.py             <-- Regex, numbering analysis, title cleaning
        ├── hierarchy.py           <-- The core logic: Flat blocks -> Nested Sections
        ├── visuals.py             <-- PyMuPDF image extraction & compositing
        └── reporting.py           <-- Summaries and diagnostics
```

---

### 1\. `parsing.py` (Text & Numbering)

Move all logic related to understanding _what_ a string represents (header vs text, depth level, cleaning).

- **Move:** `analyze_section_numbering`
- **Move:** `derive_section_depth`
- **Move:** `extract_section_title`
- **Move:** `clean_section_title`
- **Move:** `detect_header_level`
- **Move:** `_looks_like_header_text`
- **Move:** `SECTION_NUMBER_PATTERNS` (and related constants like `LARGE_FONT_THRESHOLD`)

### 2\. `hierarchy.py` (Structure Builder)

This module contains the "heavy lifting" algorithms that convert a flat list of blocks into a tree structure.

- **Move:** `build_sections_from_blocks` (This is the largest function and belongs here).
- **Move:** `find_parent_section_advanced`
- **Move:** `_prepare_section_hierarchy`
- **Move:** Any logic related to "merging continued sections" or "demoting wrappers" should be encapsulated here.

### 3\. `visuals.py` (Image Extraction)

Isolate the `fitz` (PyMuPDF) and `PIL` dependencies here. This keeps the rest of your pipeline lightweight if visuals are disabled.

- **Move:** `extract_section_visual_enhanced`
- **Configuration:** Move `MAX_VISUAL_PAGES_DEFAULT` here or pass it as an argument.

### 4\. `reporting.py` (Diagnostics)

- **Move:** `summarize_suspicious_from_verified`
- **Move:** `_append_diag`

---

### The New `04_section_builder.py`

The main script should essentially look like this:

```python
# ... imports ...
from extractor.pipeline.utils.sections.hierarchy import build_sections_from_blocks
from extractor.pipeline.utils.sections.visuals import extract_section_visual_enhanced
from extractor.pipeline.utils.sections.reporting import summarize_suspicious_from_verified

# ... Standard CLI setup ...

async def process_sections_comprehensive(blocks, pdf_path, ...):
    # 1. Build Hierarchy
    sections = build_sections_from_blocks(blocks, fallback_heuristics=True)

    # 2. Extract Visuals (if enabled)
    if pdf_path:
        for section in sections:
            extract_section_visual_enhanced(pdf_path, section, ...)

    # 3. Report
    stats = summarize_suspicious_from_verified(blocks, sections)

    return {
        "sections": sections,
        "statistics": stats
    }

# ... run() and __main__ ...
```

### Next Step

Would you like me to generate the code for **`hierarchy.py`**? That is the most complex piece (transforming the list to a tree) and moving it clears up the most logical debt.
