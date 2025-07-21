# MCP Extractor Tools

MCP server providing document extraction capabilities to AI agents.

## Features

- **PDF to JSON**: Extract structured content from PDFs
- **PDF to Markdown**: Convert PDFs to clean Markdown
- **Table Extraction**: Extract tables from specific pages
- **Metadata Extraction**: Get document metadata
- **Code Detection**: Identify and extract code blocks
- **Section Hierarchy**: Analyze document structure

## Installation

```bash
# Using uv (recommended)
uv pip install -e .

# Or with pip
pip install -e .
```

## Usage

### As MCP Server

Add to your Claude Desktop configuration (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "extractor-tools": {
      "command": "uv",
      "args": ["run", "--script", "/path/to/mcp_extractor_tools.py"],
      "env": {
        "PYTHONPATH": "/path/to/extractor/src"
      }
    }
  }
}
```

### Direct Usage

```python
# Run working examples
python mcp_extractor_tools.py

# Run debug/test mode
python mcp_extractor_tools.py debug

# Start as server
python mcp_extractor_tools.py server
```

## Available Tools

### extract_pdf_to_json
Extract PDF content to structured JSON format.

**Arguments:**
- `pdf_path` (str): Path to the PDF file
- `extract_tables` (bool): Whether to extract tables (default: true)
- `extract_images` (bool): Whether to extract images (default: false)
- `extract_code` (bool): Whether to detect code blocks (default: true)
- `max_pages` (int, optional): Maximum pages to process

### extract_pdf_to_markdown
Convert PDF to Markdown format.

**Arguments:**
- `pdf_path` (str): Path to the PDF file
- `preserve_formatting` (bool): Preserve text formatting (default: true)
- `include_page_breaks` (bool): Include page breaks (default: false)
- `max_pages` (int, optional): Maximum pages to process

### extract_document_metadata
Extract metadata from a PDF document.

**Arguments:**
- `pdf_path` (str): Path to the PDF file

### extract_tables_from_pdf
Extract tables from specific pages of a PDF.

**Arguments:**
- `pdf_path` (str): Path to the PDF file
- `output_format` (str): Format for tables ('json', 'csv', 'html')
- `page_numbers` (list, optional): Specific pages to extract from

## Examples

```python
# Extract complete document structure
result = await extract_pdf_to_json(
    "/path/to/document.pdf",
    extract_tables=True,
    extract_code=True
)

# Convert to Markdown
result = await extract_pdf_to_markdown(
    "/path/to/document.pdf",
    preserve_formatting=True
)

# Extract only tables from pages 1 and 2
result = await extract_tables_from_pdf(
    "/path/to/document.pdf",
    page_numbers=[1, 2],
    output_format="json"
)
```

## Environment Variables

- `PYTHONPATH`: Should include the extractor src directory
- `ARANGO_URL`: (Optional) For future ArangoDB integration
- `ARANGO_DATABASE`: (Optional) Database name
- `ARANGO_USERNAME`: (Optional) Database username
- `ARANGO_PASSWORD`: (Optional) Database password

## Testing

The script includes built-in verification:

```bash
# Run verification tests
python mcp_extractor_tools.py

# Run debug experiments
python mcp_extractor_tools.py debug
```

## Integration

This MCP server integrates with:
- **Extractor Core**: Uses the unified extractor and PDF converters
- **MCP Logger**: Provides operation logging and debugging
- **Response Utils**: Standardized response formatting

## Troubleshooting

1. **Import Errors**: Ensure PYTHONPATH includes the extractor src directory
2. **PDF Errors**: Verify PDF file exists and is readable
3. **Memory Issues**: Use `max_pages` parameter for large PDFs
4. **Missing Dependencies**: Run `uv sync` or `pip install -e .`