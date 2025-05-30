# Receive Documents from Module

Receive documents for extraction from other modules.

## Usage

```bash
marker receive-from <source_module> [--auto-extract] [--output <path>]
```

## Arguments

- `source_module`: Source module name
- `--auto-extract`: Automatically extract upon receipt
- `--output`: Output directory for extractions

## Examples

```bash
# Receive from a module
/marker-receive-from document_collector

# Auto-extract received documents
/marker-receive-from sparta --auto-extract

# Specify output location
/marker-receive-from crawler --auto-extract --output ./extractions/
```

---
*Marker Extraction Module*
