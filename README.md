# Marker

Advanced document processing hub supporting multiple formats with optional AI-powered accuracy improvements. Part of the Granger ecosystem for intelligent document and code analysis.

## Quick Start

```bash
# Basic PDF processing (fast)
marker document.pdf

# Process PowerPoint presentation
marker presentation.pptx

# Extract from Word document
marker report.docx

# Parse XML with security features
marker data.xml

# With AI-powered improvements (slower but more accurate)
marker --claude-config accuracy document.pdf
```

## Supported Formats

### Native Extractors (New!)
- **PDF**: Advanced extraction with table/image support
- **PowerPoint (PPTX)**: Direct extraction preserving speaker notes
- **Word (DOCX)**: Enhanced extraction with comments/revisions
- **XML**: Secure parsing with namespace support
- **HTML**: Web content extraction with structure preservation

### Core Features
- **Unified output format** across all document types
- **Table extraction** with multiple methods (Surya ML, Camelot heuristic)
- **Section detection** and hierarchy extraction
- **Image and figure extraction** with descriptions
- **Mathematical equation** processing
- **Multi-language support** with automatic detection
- **ArangoDB integration** for knowledge graphs

### AI-Powered Enhancements (Optional)
- **🤖 Claude Code Integration** for intelligent analysis
- **📊 Smart Table Merging** based on content analysis
- **📑 Section Verification** for accuracy and consistency
- **🔍 Content Validation** and structure analysis

## AI-Powered Features (Claude Integration)

Marker uses a unified Claude service architecture for all AI-powered enhancements. **All Claude features are disabled by default** to maintain performance.

### Available Features

| Feature | Purpose | Performance Impact | When to Use |
|---------|---------|-------------------|-------------|
| `section_verification` | Verify section hierarchy and titles | +2-5s per document | Academic papers, reports |
| `table_merge_analysis` | Intelligent table merging using content analysis | +1-3s per table pair | Documents with complex tables |
| `content_validation` | Overall document structure validation | +2-4s per document | Quality-critical processing |
| `structure_analysis` | Document organization analysis | +1-3s per document | Research documents |
| `image_description` | Generate descriptions for images and figures | +2-4s per image | Accessibility, search |

**Note**: Performance times are significantly improved with the new unified Claude service architecture.

### Configuration Presets

```bash
# No Claude features (default - fastest)
marker document.pdf

# Minimal Claude (production balanced)
marker --claude-config minimal document.pdf

# Table analysis only (focused improvement)
marker --claude-config tables_only document.pdf  

# High accuracy (research quality)
marker --claude-config accuracy document.pdf

# Maximum quality (slowest)
marker --claude-config research document.pdf
```

### Environment Configuration

```bash
# Enable Claude features
export MARKER_CLAUDE_ENABLED=true
export MARKER_CLAUDE_SECTION_VERIFICATION=true
export MARKER_CLAUDE_TABLE_ANALYSIS=true
export MARKER_CLAUDE_CONTENT_VALIDATION=true
export MARKER_CLAUDE_STRUCTURE_ANALYSIS=true

# Performance controls
export MARKER_CLAUDE_TIMEOUT=120
export MARKER_CLAUDE_TABLE_CONFIDENCE=0.75
export MARKER_CLAUDE_SECTION_CONFIDENCE=0.8
export MARKER_CLAUDE_WORKSPACE=/tmp/marker_claude

# Run with environment config
marker document.pdf
```

### System Requirements for AI Features

**Minimum:**
- 8GB RAM, 4 CPU cores
- Anthropic API key
- Internet connection for API calls

**Recommended:**  
- 16GB RAM, 8 CPU cores
- SSD storage for faster processing
- ArangoDB for graph database features

**GPU:** Not required (uses Anthropic API for inference)

### Performance vs Accuracy Trade-offs

```
Processing Speed:     ████████████████████ (Fastest)
Heuristic only:       ████████████████████ 

+ Section verification: ███████████████░░░░░ 
+ Table analysis:       ██████████░░░░░░░░░░
+ All features:         ████░░░░░░░░░░░░░░░░ (Slowest)

Accuracy Improvement:
Heuristic only:       ████████████████░░░░ 
+ Section verification: ███████████████████░
+ Table analysis:       ████████████████████
+ All features:         ████████████████████ (Best)
```

## Installation

```bash
# Install Marker
pip install marker-pdf

# Optional: For AI-powered features, ensure you have an Anthropic API key
export ANTHROPIC_API_KEY="your-api-key"
```

## Usage Examples

### Basic Processing
```python
from marker import convert_pdf

# Fast processing with heuristics
result = convert_pdf("document.pdf")
print(result.markdown)
```

### With Claude Enhancements
```python
from marker import convert_pdf
from marker.config.claude_config import CLAUDE_ACCURACY_FOCUSED

# High accuracy with AI analysis
result = convert_pdf("document.pdf", claude_config=CLAUDE_ACCURACY_FOCUSED)
print(f"Claude improvements: {result.metadata['claude_analysis']['improvements_made']}")
```

### Custom Configuration
```python
from marker.config.claude_config import MarkerClaudeSettings

claude_config = MarkerClaudeSettings(
    enable_claude_features=True,
    enable_table_merge_analysis=True,  # Only table improvements
    table_merge_confidence_threshold=0.8,
    analysis_timeout_seconds=60.0
)

result = convert_pdf("document.pdf", claude_config=claude_config)
```

## API Reference

### Core Functions
- `convert_pdf(file_path, claude_config=None)` - Main conversion function
- `convert_pdf_with_config(file_path, marker_config, claude_config)` - Advanced usage

### Configuration
- `marker.config.claude_config.MarkerClaudeSettings` - Claude configuration
- `marker.config.claude_config.get_recommended_config_for_use_case(use_case)` - Preset configs

## MCP Server Integration

Marker provides an MCP (Model Context Protocol) server for agent integration:

```typescript
// Available MCP tools
{
  "convert_pdf": {
    "description": "Convert PDF with optional Claude enhancements",
    "parameters": {
      "file_path": "string",
      "claude_config": "minimal|tables_only|accuracy|research|disabled",
      "extraction_method": "marker|pymupdf4llm",
      "check_system_resources": "boolean"
    }
  },
  "get_system_resources": {
    "description": "Check system resources for Claude feature recommendations"
  },
  "validate_claude_config": {
    "description": "Validate Claude configuration and get performance estimates"
  },
  "recommend_extraction_strategy": {
    "description": "Get intelligent recommendations based on speed/accuracy requirements",
    "parameters": {
      "speed_priority": "fastest|fast|normal|slow",
      "accuracy_priority": "basic|normal|high|research", 
      "content_types": ["text", "tables", "images", "equations"]
    }
  }
}
```

### Agent Usage Examples

#### Example 1: Speed-Priority Request
**User:** *"Check system stats and determine optimum settings for quick PDF download. I only need to download the pdf quickly...so I should probably just use pymupdf4llm"*

```python
# Step 1: Check system resources
resources = await mcp_server.get_system_resources()
# Result: {cpu: {count: 48, usage: 10.7%}, memory: {available_gb: 116.5}, ...}

# Step 2: Get strategy recommendation
strategy = await mcp_server.recommend_extraction_strategy({
    "speed_priority": "fastest",
    "accuracy_priority": "basic", 
    "content_types": ["text"]
})
# Result: {
#   "extraction_method": "pymupdf4llm",
#   "claude_config": "disabled", 
#   "reasoning": ["Fastest text extraction using PyMuPDF4LLM"],
#   "trade_offs": ["No table/image extraction, no Claude enhancements"]
# }

# Step 3: Execute with optimal settings
result = await mcp_server.convert_pdf("document.pdf", 
    extraction_method="pymupdf4llm",
    claude_config="disabled"
)
# Estimated time: 2.0s vs 80s for full Marker+Claude (40x faster!)
```

#### Example 2: Research-Quality Request
**User:** *"I need accurate table extraction for a research paper"*

```python
strategy = await mcp_server.recommend_extraction_strategy({
    "speed_priority": "normal",
    "accuracy_priority": "research",
    "content_types": ["text", "tables", "equations"]
})
# Result: extraction_method="marker", claude_config="research" (if system allows)
```

#### Example 3: Balanced Processing
**User:** *"Extract tables but keep it reasonably fast"*

```python
strategy = await mcp_server.recommend_extraction_strategy({
    "speed_priority": "fast", 
    "accuracy_priority": "normal",
    "content_types": ["text", "tables"]
})
# Result: extraction_method="marker", claude_config="tables_only"
```

## ArangoDB Integration

Marker can export documents to ArangoDB as a graph structure, preserving relationships and enabling powerful graph queries:

### Export to ArangoDB
```python
from marker.renderers.arangodb_enhanced import ArangoDBEnhancedRenderer
from marker.arangodb.pipeline import ArangoDBPipeline

# Convert PDF with graph structure
result = convert_pdf("document.pdf")

# Render as graph
renderer = ArangoDBEnhancedRenderer({
    "extract_entities": True,
    "extract_relationships": True
})
graph_data = renderer(result.document)

# Import to ArangoDB
pipeline = ArangoDBPipeline({
    "host": "localhost",
    "database": "marker_docs"
})
stats = pipeline.import_marker_output(graph_data)
```

### Query Documents
```python
# Find all documents with specific sections
docs = pipeline.query_documents({"title": "Introduction"})

# Get complete document structure
structure = pipeline.get_document_structure("documents/doc_123")

# Execute custom AQL queries
results = pipeline._execute_query("""
    FOR doc IN documents
    FOR section IN OUTBOUND doc contains
    FILTER section.level == 1
    RETURN {document: doc.title, sections: section.title}
""")
```

## Granger Ecosystem Integration

Marker is a spoke module in the Granger hub-and-spoke architecture, designed to work seamlessly with other modules:

### Architecture
```
┌─────────────────────────────┐
│  claude-module-communicator │ ← Central orchestrator
└──────────┬──────────────────┘
           │
    ┌──────┴──────┬──────────┬─────────┐
    │             │          │         │
┌───▼───┐   ┌────▼────┐ ┌───▼───┐ ┌──▼──┐
│Marker │   │ GitGet  │ │SPARTA │ │... │
└───────┘   └─────────┘ └───────┘ └────┘
```

### Cross-Module Workflows

#### Example: Analyze Project Documentation
```python
# The HUB orchestrates multiple modules
workflow = {
    "gitget": "Clone and analyze repository code",
    "marker": "Extract PDFs and docs from repo",
    "arangodb": "Store unified knowledge graph"
}
```

### Planned Integrations
- **GitGet**: Code repository analysis (coming soon)
- **SPARTA**: Security document processing
- **ArXiv**: Research paper extraction

## Performance

### Native Extractor Performance
Native extractors avoid lossy conversions and provide significant speed improvements:

| Format | Traditional Method | Native Extractor | Speed Improvement |
|--------|-------------------|------------------|-------------------|
| DOCX   | Convert to PDF    | < 0.01s         | 100x faster       |
| PPTX   | HTML → PDF        | < 0.1s          | 20x faster        |
| XML    | Not supported     | < 0.05s         | New capability    |

### Claude Enhancement Performance
When AI features are enabled, Marker provides detailed metrics:

```json
{
  "processing_time": 45.2,
  "claude_analysis": {
    "features_used": ["section_verification", "table_merge_analysis"],
    "total_claude_time": 23.1,
    "improvements_made": ["section_corrections", "intelligent_table_merges"],
    "performance_stats": {
      "total_analyses": 3,
      "average_analysis_time": 7.7,
      "fallbacks_triggered": 0
    }
  }
}
```

## Contributing

See [DEVELOPER_GUIDE.md](docs/guides/DEVELOPER_GUIDE.md) for development setup and guidelines.

## License

Apache License 2.0 - See [LICENSE](LICENSE) file for details
