# MARKER CONTEXT — CLAUDE.md

> **Inherits standards from global and workspace CLAUDE.md files with overrides below.**

## Project Context
**Purpose:** Advanced multi-format document processing with AI accuracy improvements  
**Type:** Processing Spoke  
**Status:** Active  
**Pipeline Position:** Second step in SPARTA → Marker → ArangoDB → Unsloth

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

### Environment Variables
```bash
# .env additions for Marker
MARKER_DATA_DIR=/home/graham/workspace/data/marker
CLAUDE_API_KEY=your_claude_api_key
ENABLE_AI_ENHANCEMENT=true
MAX_FILE_SIZE_MB=100
PARALLEL_PROCESSING=4
TABLE_EXTRACTION_MODEL=surya
```

### Special Considerations
- **GPU Acceleration:** Optional CUDA support for AI enhancements
- **Large Files:** Memory management for 100MB+ documents
- **MCP Server:** Exposes document processing as MCP service
- **AI Enhancement:** Claude integration for accuracy improvements

---

## License

MIT License — see [LICENSE](LICENSE) for details.