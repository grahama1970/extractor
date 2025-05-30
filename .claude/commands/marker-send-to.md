# Send Extracted Data to Module

Send extracted document data to another module.

## Usage

```bash
marker send-to <target_module> <file_or_data> [--format <format>]
```

## Arguments

- `target_module`: Target module (sparta, arangodb, etc.)
- `file_or_data`: Extracted file path or inline data
- `--format`: Output format (json, markdown, structured)

## Examples

```bash
# Send to SPARTA for processing
/marker-send-to sparta extracted_doc.json

# Send markdown to ArangoDB
/marker-send-to arangodb document.md --format markdown

# Send tables to unsloth
/marker-send-to unsloth tables.json --format structured
```

## Supported Targets

- **sparta**: For cybersecurity processing
- **arangodb**: For storage and graph building
- **unsloth**: For training data preparation
- **llm_proxy**: For enhancement

---
*Marker Extraction Module*
