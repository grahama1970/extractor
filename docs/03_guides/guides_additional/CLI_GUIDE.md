# Marker Typer-based CLI

This document describes the new Typer-based CLI for the Marker PDF conversion tool.

## Overview

The new CLI provides a more robust and user-friendly interface with multiple output formats, following the patterns established in the ArangoDB companion project.

## Features

### 1. Multiple Output Formats

The CLI supports various output formats for better integration and usability:

- **markdown**: Standard markdown output (default)
- **json**: JSON output with proper formatting
- **html**: HTML output
- **dict**: Python dictionary format (for programmatic use)
- **table**: Rich table format showing document structure
- **summary**: Concise summary panel with key information

### 2. Command Structure

```bash
# Main commands
marker --help                   # Show help
marker version                  # Show version information

# Convert commands
marker convert single <pdf> [options]   # Convert a single PDF
marker convert batch <dir> [options]    # Convert multiple PDFs
```

### 3. Single PDF Conversion

Convert a single PDF with various output options:

```bash
# Basic conversion
marker convert single document.pdf

# JSON output with custom formatting
marker convert single document.pdf --output-format json --json-indent 4

# Table view of document structure
marker convert single document.pdf --output-format table

# Summary view
marker convert single document.pdf --output-format summary

# Dict output (for Python scripts)
marker convert single document.pdf --output-format dict

# With LLM enhancement
marker convert single document.pdf --use-llm --renderer json

# Specify output directory
marker convert single document.pdf --output-dir ./output/

# Extract specific pages
marker convert single document.pdf --page-range "1-5,10,15-20"

# Debug mode
marker convert single document.pdf --debug
```

### 4. Batch Conversion

Process multiple PDFs efficiently:

```bash
# Basic batch conversion
marker convert batch ./pdfs/

# With worker processes
marker convert batch ./pdfs/ --workers 10

# Skip existing files
marker convert batch ./pdfs/ --skip-existing

# Limit number of files
marker convert batch ./pdfs/ --max-files 50

# Summary output
marker convert batch ./pdfs/ --output-format summary
```

### 5. Configuration Options

The CLI preserves all existing Marker functionality while adding new features:

- LLM integration (`--use-llm`)
- Language specification (`--languages`)
- Image extraction control (`--extract-images/--no-extract-images`)
- Table merging options (`--skip-table-merge`)
- Debug mode (`--debug`)

## Usage Examples

### Get Document Structure

```bash
# View document structure in a table
marker convert single report.pdf --output-format table
```

### Export to JSON for Processing

```bash
# Convert to JSON for further processing
marker convert single data.pdf --output-format json > output.json
```

### Quick Summary

```bash
# Get a quick summary of the document
marker convert single thesis.pdf --output-format summary
```

### Batch Processing with Progress

```bash
# Process a directory with summary output
marker convert batch ./documents/ --output-format summary --workers 8
```

## Implementation Details

The new CLI:

1. Uses Typer framework for modern CLI development
2. Provides rich console output with color support
3. Implements error handling and logging
4. Maintains backward compatibility with existing Marker functionality
5. Follows design patterns from the ArangoDB CLI project

## Migration from Click CLI

The existing Click-based CLI is still available through the original entry points:

```bash
# Old CLI (Click-based)
python convert.py input_file.pdf

# New CLI (Typer-based)
python cli.py convert single input_file.pdf
```

## Future Enhancements

Potential additions to the CLI:

1. Interactive mode for step-by-step conversion
2. Configuration file support
3. Export profiles for common use cases
4. Plugin system for custom renderers
5. Web API mode for remote access