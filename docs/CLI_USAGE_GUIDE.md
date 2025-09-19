# PDF Extraction Pipeline CLI Usage Guide

Note: Prefer the single minimal CLI surface for all extractions:

```bash
python -m src.cli extract <input> <out_dir> [--mode fast|accurate]
```

- PDF: use `--mode fast` (PyMuPDF text) or `--mode accurate` (full pipeline).
- Structured formats (HTML/DOCX/PPTX/XLSX/EPUB/RST/XML/MD) do not need `--mode`.

The legacy command groups below are retained for reference and operator/advanced workflows.

## Available CLIs

### 1. `extract-pipeline` - Main Pipeline Commands

Full extraction pipeline operations:

```bash
# List all available stages
extract-pipeline list-stages

# Stage 1: Extract annotations 
extract-pipeline extract-annotations doc.pdf -o annotations.json

# Stage 3: Create clean PDF
extract-pipeline create-clean-pdf marked.pdf -o clean.pdf  

# Stage 5.5a: Create batches for suspicious blocks
extract-pipeline create-batches blocks.json -d /tmp/batches/

# Stage 5.5c: Apply fixes from sub-agents
extract-pipeline apply-fixes blocks.json decisions.json -o fixed.json

# Stage 6: Build section nodes
extract-pipeline build-sections fixed_blocks.json -o sections.json

# Stage 8: Enhance sections semantically
extract-pipeline enhance-sections sections.json doc.pdf -o enhanced.json

# Stage 9: Validate extraction
extract-pipeline validate-extraction enhanced.json --gold gold.json
```

### 2. `pdf-tools` - Image Operations

PDF image manipulation and snapshots:

```bash
# List all commands
pdf-tools list-commands

# Take single region snapshot
pdf-tools snapshot doc.pdf --page 0 --x0 100 --y0 200 --x1 500 --y1 400 -o region.png

# Take multiple region snapshots
pdf-tools snapshot-multi doc.pdf '[{"page":0,"bbox":[100,200,500,400]}]' -o multi.png

# Create merged table image
pdf-tools table-image doc.pdf table_blocks.json -o table.png

# Create merged section image  
pdf-tools section-image doc.pdf section_blocks.json -o section.png

# Quick view entire page
pdf-tools quick-view doc.pdf 0 -o page_0.png
```

## Complete Pipeline Example

Here's how to run the full extraction pipeline:

```bash
# 1. Extract annotations
extract-pipeline extract-annotations input.pdf -o /tmp/annotations.json

# 2. Create clean PDF
extract-pipeline create-clean-pdf input.pdf -o /tmp/clean.pdf

# 3. Run marker (external tool)
marker-pdf /tmp/clean.pdf --output /tmp/marker_output.json

# 4. Check for suspicious blocks and batch them
extract-pipeline create-batches /tmp/marker_output.json -d /tmp/batches/

# 5. (Manual) Run sub-agents on batches to get decisions.json

# 6. Apply fixes
extract-pipeline apply-fixes /tmp/marker_output.json /tmp/decisions.json -o /tmp/fixed.json

# 7. Build sections
extract-pipeline build-sections /tmp/fixed.json -o /tmp/sections.json

# 8. Create validation images
pdf-tools section-image input.pdf /tmp/sections.json -o /tmp/section_validation.png
pdf-tools table-image input.pdf /tmp/fixed.json -o /tmp/table_validation.png

# 9. Enhance sections
extract-pipeline enhance-sections /tmp/sections.json input.pdf -o /tmp/enhanced.json

# 10. Validate against gold standard (if available)
extract-pipeline validate-extraction /tmp/enhanced.json --gold /tmp/gold_standard.json
```

## Tips for Agents

1. **Always use absolute paths** - The tools expect absolute paths for file arguments
2. **Check help** - Use `--help` on any command for detailed options
3. **Output defaults** - Most commands save to `/tmp/` if no output specified
4. **JSON formats** - Many commands accept either JSON strings or file paths
5. **Verbose mode** - Add `-v` or `--verbose` for detailed output

## Integration Notes

- Historical docs and transcripts may reference an `extract-pdf` agent/orchestrator. That flow is deprecated in favor of the unified `python -m src.cli extract` command.
- Operator utilities (`pipeline-run`, `pipeline-run-all`) remain available; prefer the unified CLI for day‑to‑day usage.

## Installation

After installing the package with `uv sync`, the CLIs will be available:
```bash
# Check they're installed
which extract-pipeline
which pdf-tools
```
