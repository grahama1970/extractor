# Task 101: Setup CLI With Slash MCP

**Goal**: Integrate slash_mcp_mixin into Marker CLI for auto MCP generation

## Current State
- Existing CLI at scripts/cli/cli.py uses Typer
- Has convert commands but needs reorganization
- No MCP server functionality

## Implementation Steps

### Step 1: Create Enhanced CLI File

```python
# FILE: /home/graham/workspace/experiments/marker/scripts/cli/marker_cli_mcp.py
#!/usr/bin/env python3

import sys
from pathlib import Path

# Add paths
sys.path.insert(0, "/home/graham/workspace/experiments/claude_max_proxy/src")
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import typer
from typing import Optional
from enum import Enum

# Import slash_mcp_mixin
from llm_call.cli.slash_mcp_mixin import add_slash_mcp_commands

# Import marker components
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict

app = typer.Typer(name="marker", help="Marker PDF extraction with MCP")

class OutputFormat(str, Enum):
    markdown = "markdown"
    json = "json"
    html = "html"

@app.command()
def extract(
    pdf_path: Path = typer.Argument(..., help="Path to PDF"),
    output_format: OutputFormat = typer.Option(OutputFormat.markdown, "--format", "-f"),
    output_file: Optional[Path] = typer.Option(None, "--output", "-o")
):
    """Extract content from PDF file."""
    # Implementation here
    pass

# Add MCP generation - THIS IS THE KEY LINE
add_slash_mcp_commands(app)

if __name__ == "__main__":
    app()
```

### Step 2: Test CLI Functionality

```bash
cd /home/graham/workspace/experiments/marker
python scripts/cli/marker_cli_mcp.py --help
python scripts/cli/marker_cli_mcp.py extract test.pdf
```

### Step 3: Generate MCP Config

```bash
python scripts/cli/marker_cli_mcp.py generate-mcp-config --output marker_mcp.json
```

Expected output:
```json
{
  "name": "marker",
  "server": {
    "command": "python",
    "args": ["scripts/cli/marker_cli_mcp.py", "serve-mcp"]
  },
  "tools": {
    "extract": {
      "description": "Extract content from PDF file",
      "inputSchema": {
        "type": "object",
        "properties": {
          "pdf_path": {"type": "string"},
          "output_format": {"type": "string", "enum": ["markdown", "json", "html"]}
        }
      }
    }
  }
}
```

### Step 4: Test MCP Server

```bash
python scripts/cli/marker_cli_mcp.py serve-mcp
```

## Validation Checklist

- [ ] CLI runs without import errors
- [ ] extract command processes PDFs
- [ ] generate-mcp-config creates valid JSON
- [ ] serve-mcp starts MCP server
- [ ] MCP server responds to tools/list request

## Common Issues

1. **Import Error for slash_mcp_mixin**
   - Ensure claude_max_proxy path is correct
   - Check PYTHONPATH includes necessary directories

2. **Models fail to load**
   - Run from marker root directory
   - Check GPU/CPU compatibility

3. **MCP server doesn't start**
   - Check no other process on default port
   - Verify all dependencies installed