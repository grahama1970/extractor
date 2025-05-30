# Task 001: Integrate slash_mcp_mixin into Marker CLI

**Goal**: Add auto MCP generation to existing Marker CLI

## Current State
- Marker has a Typer-based CLI in scripts/cli/cli.py
- No MCP server implementation exists
- Need to integrate slash_mcp_mixin for auto-generation

## Working Code Example

```python
# FILE: /home/graham/workspace/experiments/marker/scripts/cli/marker_cli.py
#!/usr/bin/env python3
"""
Enhanced Marker CLI with MCP Auto-Generation
"""

import sys
from pathlib import Path
import typer
from typing import Optional, List
from enum import Enum

# Add claude_max_proxy to path for slash_mcp_mixin
sys.path.insert(0, "/home/graham/workspace/experiments/claude_max_proxy/src")
from llm_call.cli.slash_mcp_mixin import add_slash_mcp_commands

# Add marker to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered

# Output formats
class OutputFormat(str, Enum):
    MARKDOWN = "markdown"
    JSON = "json"
    HTML = "html"
    TEXT = "text"

# Create app
app = typer.Typer(
    name="marker",
    help="Marker PDF extraction tool with MCP support"
)

# Global models storage
models = None

def get_models():
    """Get or create models."""
    global models
    if models is None:
        models = create_model_dict()
    return models

@app.command()
def extract(
    pdf_path: Path = typer.Argument(..., help="Path to PDF file"),
    output_format: OutputFormat = typer.Option(OutputFormat.MARKDOWN, "--format", "-f", help="Output format"),
    output_file: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
    max_pages: Optional[int] = typer.Option(None, "--max-pages", help="Maximum pages to process")
):
    """Extract content from a PDF file."""
    
    if not pdf_path.exists():
        typer.echo(f"Error: PDF file not found: {pdf_path}", err=True)
        raise typer.Exit(1)
    
    # Get models
    model_dict = get_models()
    
    # Create converter
    converter = PdfConverter(artifact_dict=model_dict)
    
    # Convert PDF
    typer.echo(f"Processing {pdf_path.name}...")
    rendered = converter(str(pdf_path))
    
    # Format output
    if output_format == OutputFormat.MARKDOWN:
        content = rendered.markdown
    elif output_format == OutputFormat.JSON:
        content = rendered.model_dump_json(indent=2)
    elif output_format == OutputFormat.HTML:
        content = rendered.html
    elif output_format == OutputFormat.TEXT:
        content = text_from_rendered(rendered)
    
    # Output
    if output_file:
        output_file.write_text(content)
        typer.echo(f"Saved to {output_file}")
    else:
        typer.echo(content)

# Add MCP generation commands
add_slash_mcp_commands(app)

if __name__ == "__main__":
    app()
```

## Test Commands

```bash
# Test CLI functionality
cd /home/graham/workspace/experiments/marker
python scripts/cli/marker_cli.py extract test.pdf --format markdown

# Generate Claude slash commands
python scripts/cli/marker_cli.py generate-claude --output .claude/commands

# Generate MCP configuration
python scripts/cli/marker_cli.py generate-mcp-config --output marker_mcp.json

# Test MCP server
python scripts/cli/marker_cli.py serve-mcp
```

## Expected Output

MCP configuration should be auto-generated with all CLI commands available as tools.

## Validation

- [ ] CLI commands work normally
- [ ] generate-claude creates slash commands
- [ ] generate-mcp-config creates valid MCP config
- [ ] serve-mcp starts an MCP server
EOFDOC'