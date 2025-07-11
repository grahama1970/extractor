# Extractor (formerly Marker) Purpose

Advanced document processing hub supporting multiple formats with optional AI-powered accuracy improvements. Part of the Granger ecosystem for intelligent document and code analysis.

## Core Functionality

1. **Multi-format document extraction** - Convert PDF, PPTX, DOCX, XML, HTML to unified markdown
2. **Table extraction** - Multiple methods including Surya ML and Camelot heuristic
3. **Section detection** - Hierarchy extraction and structure preservation
4. **Image/figure extraction** - With AI-powered descriptions
5. **Mathematical equation processing** - LaTeX and MathML support
6. **Multi-language support** - Automatic language detection
7. **ArangoDB integration** - Store extracted content in knowledge graphs

## AI-Powered Enhancements (Optional)

- **Claude Code Integration** - Intelligent content analysis
- **Smart Table Merging** - Content-based table combination
- **Section Verification** - Accuracy and consistency checks
- **Content Validation** - Structure and quality analysis

## Integration Points

- **Input**: Documents (PDF, PPTX, DOCX, XML, HTML)
- **Output**: Structured markdown, JSON, or ArangoDB storage
- **Dependencies**: Surya OCR, Camelot, Claude API (optional)
- **Consumers**: ArangoDB, fine_tuning, other Granger modules

## Key Features

- Unified output format across all document types
- Performance tracking and optimization
- Extensible processor pipeline
- Quality assurance integration
- Batch processing support