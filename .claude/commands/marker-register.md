# Register Marker Module

Register the Marker extraction module with the Module Communicator.

## Usage

```bash
marker register [--name <name>] [--capabilities <list>]
```

## Arguments

- `--name`: Module name (default: marker_extractor)
- `--capabilities`: Override default capabilities

## Examples

```bash
# Basic registration
/marker-register

# Custom registration
/marker-register --name pdf_extractor --capabilities "pdf,docx,tables"
```

## Default Capabilities

- pdf_extraction
- text_extraction
- table_extraction
- section_detection
- batch_processing

---
*Marker Extraction Module*
