# Extractor CONTEXT — CLAUDE.md

> **Inherits standards from global and workspace CLAUDE.md files with overrides below.**

## Intitial Steps
- cd into the project directory
- activate the virtual environment (.venv)
- peruse the .env and pyproject.toml for PYTHONPATH or environment variables

## Project Context
**Purpose:** Advanced multi-format document processing with AI accuracy improvements  
**Type:** Processing Spoke  
**Status:** Active  
**Pipeline Position:** Second step in SPARTA → Extractor → ArangoDB → Unsloth

## Project-Specific Overrides

### Special Dependencies
```toml
# Marker requires document processing libraries
pymupdf = "^1.23.0"
python-pptx = "^0.6.21"
python-docx = "^1.1.0"
pillow = "^10.0.0"
opencv-python = "^4.8.0"
transformers = "^4.35.0"
```


### Special Considerations
- **GPU Acceleration:** Optional CUDA support for AI enhancements
- **Large Files:** Memory management for 100MB+ documents
- **MCP Server:** Exposes document processing as MCP service
- **AI Enhancement:** Claude integration for accuracy improvements

---

