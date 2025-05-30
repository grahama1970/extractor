# Marker Slash Commands Quick Reference

## Overview

Marker supports slash commands for easy integration with Claude Desktop and command-line usage. All commands follow the pattern `/marker-<category> <action> [arguments]`.

## Quick Start

```bash
# List all available commands
marker commands

# Execute a slash command
marker slash /marker-extract document.pdf

# Get help for any command
marker slash /marker-extract --help
```

## Extract Commands

### `/marker-extract`
Extract content from PDF documents.

```bash
# Basic extraction
/marker-extract document.pdf

# With options
/marker-extract document.pdf --output-format json --max-pages 10

# Batch extraction
/marker-extract batch /path/to/pdfs --output-dir /output --parallel

# Extract tables only
/marker-extract tables report.pdf --format excel

# Extract code blocks
/marker-extract code tutorial.pdf --language python --combine
```

## ArangoDB Commands

### `/marker-db`
Database operations for document storage and search.

```bash
# Setup database
/marker-db setup --database marker --create-db

# Import document
/marker-db import-doc output.json --batch-size 500

# Search content
/marker-db search "machine learning" --limit 20

# Export document
/marker-db export doc_123 --format markdown

# Show statistics
/marker-db stats

# Visualize graph
/marker-db visualize --document-id doc_123 --output-path graph.html
```

## Claude AI Commands

### `/marker-claude`
AI-powered analysis and verification.

```bash
# Analyze document
/marker-claude analyze document.json --analysis-type all

# Verify extraction
/marker-claude verify document.json --fix-issues

# Describe images
/marker-claude describe-images document.json --max-images 5

# Analyze table merges
/marker-claude merge-tables document.json --threshold 0.8
```

## QA Commands

### `/marker-qa`
Generate and validate question-answer pairs.

```bash
# Generate QA pairs
/marker-qa generate document.json --num-questions 20

# Validate QA pairs
/marker-qa validate qa_pairs.json --sample-size 50

# Test document with QA
/marker-qa test document.json qa_pairs.json --verbose

# Generate report
/marker-qa report ./test_results/ --include-charts
```

## Workflow Commands

### `/marker-workflow`
Manage document processing workflows.

```bash
# List workflows
/marker-workflow list

# Create workflow
/marker-workflow create research --interactive

# Run workflow
/marker-workflow run standard document.pdf
/marker-workflow run enhanced ./pdfs/ --parallel

# Check status
/marker-workflow status workflow_results.json
```

## Test Commands

### `/marker-test`
Testing and validation with enhanced reporting.

```bash
# Run tests
/marker-test run --coverage --output-format markdown

# Run with iteration
/marker-test iterate --max-iterations 5 --auto-fix

# Validate output
/marker-test validate output.json --strict

# Run benchmark
/marker-test benchmark document.pdf --iterations 5
```

## Server Commands

### `/marker-serve`
MCP server management.

```bash
# Start server
/marker-serve start --port 3000 --background

# Stop server
/marker-serve stop

# Check status
/marker-serve status --check-health

# Generate config
/marker-serve config --output-path ~/.config/Claude/claude_desktop_config.json

# List tools
/marker-serve tools --search extract
```

## Shorthand Commands

For convenience, common operations have shorthand versions:

```bash
# Extract (shorthand for /marker-extract)
marker extract document.pdf -f json -o output.json

# Workflow (shorthand for /marker-workflow)
marker workflow run enhanced ./pdfs/

# Serve (shorthand for /marker-serve)
marker serve start -p 3000 -b
```

## Built-in Workflows

### Standard
Basic PDF extraction with OCR.
```bash
/marker-workflow run standard document.pdf
```

### Enhanced
Extraction with Claude AI analysis.
```bash
/marker-workflow run enhanced document.pdf
```

### QA
Extract and generate QA pairs.
```bash
/marker-workflow run qa document.pdf
```

### ArangoDB
Extract and import to database.
```bash
/marker-workflow run arangodb document.pdf
```

### Research
Extract with citation and reference emphasis.
```bash
/marker-workflow run research paper.pdf
```

## MCP Integration

### Setup for Claude Desktop

1. Generate configuration:
```bash
/marker-serve config > ~/.config/Claude/claude_desktop_config.json
```

2. Start server:
```bash
/marker-serve start --background
```

3. Use in Claude Desktop:
- Commands are available as tools
- Claude can execute marker operations
- Results are returned to the conversation

## Tips and Tricks

1. **Command Discovery**
   ```bash
   # List commands by category
   marker commands -c extraction
   
   # Search for commands
   /marker-serve tools --search table
   ```

2. **Batch Operations**
   ```bash
   # Process multiple PDFs
   /marker-extract batch ./papers/ --parallel --output-format json
   
   # Run workflow on directory
   /marker-workflow run enhanced ./documents/ --parallel
   ```

3. **Chaining Commands**
   ```bash
   # Extract, then import to DB
   /marker-extract doc.pdf -f json -o out.json && \
   /marker-db import-doc out.json
   ```

4. **Custom Workflows**
   ```bash
   # Create custom workflow
   /marker-workflow create my-workflow --interactive
   
   # Use config overrides
   /marker-workflow run standard doc.pdf \
     --config-overrides '{"extract": {"max_pages": 50}}'
   ```

## Environment Variables

- `MARKER_CLAUDE_API_KEY` - Claude API key
- `MARKER_ARANGODB_URL` - ArangoDB URL
- `MARKER_ARANGODB_USERNAME` - Database username
- `MARKER_ARANGODB_DATABASE` - Database name
- `MCP_SERVER_PORT` - MCP server port
- `MCP_SERVER_HOST` - MCP server host

## Error Handling

All commands provide clear error messages and exit codes:
- Exit 0: Success
- Exit 1: General error
- Exit 2: Invalid arguments

Use `--help` with any command for detailed usage information.