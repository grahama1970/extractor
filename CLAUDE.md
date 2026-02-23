# Extractor CONTEXT — CLAUDE.md

> **Inherits standards from global and workspace CLAUDE.md files with overrides below.**

## Initial Steps
- cd into the project directory
- activate the virtual environment (.venv)
- peruse the .env and pyproject.toml for PYTHONPATH or environment variables
- check for inter-agent messages: `agent-inbox check`

## Project Context
**Purpose:** Advanced multi-format document processing with AI accuracy improvements  
**Type:** Processing Spoke  
**Status:** Active  
**Pipeline Position:** Second step in SPARTA → Extractor → ArangoDB → Unsloth

## Project-Specific Overrides

### Special Dependencies
```toml
# Marker requires document processing libraries
pymupdf = ">=1.26.1"
python-pptx = ">=1.0.2"
python-docx = ">=1.1.2"
pillow = ">=10.1.0,<11.0.0"
opencv-python = ">=4.11.0"
transformers = ">=4.45.2,<5"
camelot-py = ">=1.0.9"
```


### Special Considerations
- **GPU Acceleration:** Optional CUDA support for AI enhancements
- **Large Files:** Memory management for 100MB+ documents
- **MCP Server:** Exposes document processing as MCP service
- **AI Enhancement:** Claude integration for accuracy improvements

---

