# CLI Reference

The `marker-llm-call` CLI provides commands to validate content using various validators.

## Installation

```bash
pip install marker-llm-call
```

## Basic Usage

```bash
# Validate a file using table validator
marker-llm-call validate file.json --validator table

# Validate text directly
marker-llm-call validate-text "Some text to validate" --validator citation

# List available validators
marker-llm-call list-validators
```

## Commands

### `validate`

Validate a file using the specified validator.

**Usage:**
```bash
marker-llm-call validate [OPTIONS] FILE_PATH
```

**Arguments:**
- `FILE_PATH`: Path to the file to validate (required)

**Options:**
- `--validator TEXT`: Validator type to use [default: table]
- `--params TEXT`: Additional validator parameters as KEY=VALUE pairs
- `--output-format [json|text]`: Output format [default: json]
- `--verbose`: Enable verbose output
- `--help`: Show this message and exit

**Examples:**
```bash
# Validate a table with custom parameters
marker-llm-call validate data.json --validator table --params min_rows=3 --params min_cols=2

# Validate an image description
marker-llm-call validate image.json --validator image --verbose

# Get JSON output
marker-llm-call validate document.json --validator general --output-format json
```

### `validate-text`

Validate text content directly without a file.

**Usage:**
```bash
marker-llm-call validate-text [OPTIONS] TEXT
```

**Arguments:**
- `TEXT`: Text content to validate (required)

**Options:**
- `--validator TEXT`: Validator type to use [default: citation]
- `--params TEXT`: Additional validator parameters as KEY=VALUE pairs
- `--output-format [json|text]`: Output format [default: text]
- `--verbose`: Enable verbose output
- `--help`: Show this message and exit

**Examples:**
```bash
# Validate a citation
marker-llm-call validate-text "Smith et al. (2023) found that..." --validator citation

# Validate code with language specification
marker-llm-call validate-text "def hello(): print('world')" --validator code --params language=python

# Validate math equation
marker-llm-call validate-text "E = mc^2" --validator math --params format=latex
```

### `list-validators`

List all available validators and their descriptions.

**Usage:**
```bash
marker-llm-call list-validators [OPTIONS]
```

**Options:**
- `--verbose`: Show detailed information about each validator
- `--help`: Show this message and exit

**Example:**
```bash
# List all validators
marker-llm-call list-validators

# Show detailed information
marker-llm-call list-validators --verbose
```

## Validator Types

### Table Validator
Validates table data structures.

**Parameters:**
- `min_rows`: Minimum number of rows (default: 1)
- `min_cols`: Minimum number of columns (default: 2)
- `max_rows`: Maximum number of rows (optional)
- `max_cols`: Maximum number of columns (optional)
- `check_headers`: Whether to check for headers (default: true)

### Image Validator
Validates image descriptions and metadata.

**Parameters:**
- `min_description_length`: Minimum description length (default: 10)
- `required_fields`: Required metadata fields (default: ["alt_text"])
- `check_dimensions`: Whether to check image dimensions (default: false)

### Math Validator
Validates mathematical expressions and equations.

**Parameters:**
- `format`: Expected format (latex, mathml, ascii) (default: latex)
- `check_balanced`: Check balanced delimiters (default: true)
- `allow_empty`: Allow empty expressions (default: false)

### Code Validator
Validates code snippets and syntax.

**Parameters:**
- `language`: Programming language (required)
- `check_syntax`: Whether to check syntax (default: true)
- `max_lines`: Maximum number of lines (optional)
- `style_guide`: Style guide to follow (optional)

### Citation Validator
Validates academic citations and references.

**Parameters:**
- `min_score`: Minimum fuzzy match score (default: 80)
- `format`: Citation format (apa, mla, chicago) (default: apa)
- `check_year`: Whether to check year format (default: true)

### General Content Validator
General purpose content validation.

**Parameters:**
- `min_length`: Minimum content length (default: 1)
- `max_length`: Maximum content length (optional)
- `required_sections`: Required sections (optional)
- `forbidden_patterns`: Patterns to avoid (optional)

## Environment Variables

- `MARKER_LLM_CACHE_TYPE`: Cache backend type (redis, in-memory) [default: redis]
- `MARKER_LLM_REDIS_HOST`: Redis host for caching [default: localhost]
- `MARKER_LLM_REDIS_PORT`: Redis port [default: 6379]
- `MARKER_LLM_LOG_LEVEL`: Logging level [default: INFO]

## Exit Codes

- `0`: Validation successful
- `1`: Validation failed
- `2`: Invalid arguments or configuration error
- `3`: File not found or access error

## Advanced Usage

### Custom Output Formats

The CLI supports both JSON and text output formats:

```bash
# JSON output (for programmatic use)
marker-llm-call validate data.json --output-format json | jq .

# Text output (for human reading)
marker-llm-call validate data.json --output-format text
```

### Piping and Integration

The CLI can be integrated into pipelines:

```bash
# Validate all JSON files in a directory
find . -name "*.json" -exec marker-llm-call validate {} --validator table \;

# Validate output from another command
some-command | marker-llm-call validate-text - --validator general
```

### Debug Mode

Enable verbose output for debugging:

```bash
# See detailed validation steps
marker-llm-call validate file.json --verbose

# Set debug log level
MARKER_LLM_LOG_LEVEL=DEBUG marker-llm-call validate file.json
```

## Examples

### Table Validation
```bash
# Validate a CSV file converted to JSON
marker-llm-call validate sales_data.json --validator table --params min_rows=10 --params check_headers=true
```

### Multi-file Validation
```bash
# Validate multiple files with a script
#!/bin/bash
for file in *.json; do
    echo "Validating $file..."
    marker-llm-call validate "$file" --validator general
done
```

### CI/CD Integration
```bash
# Use in GitHub Actions or other CI
- name: Validate Output
  run: |
    marker-llm-call validate output.json --validator table --params min_rows=1
    if [ $? -ne 0 ]; then
      echo "Validation failed"
      exit 1
    fi
```

## See Also

- [Getting Started Guide](getting_started.md)
- [API Reference](api_reference.md)
- [Examples](examples.md)
- [Architecture](architecture.md)