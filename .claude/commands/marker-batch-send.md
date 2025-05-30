# Batch Send Extracted Documents

Send multiple extracted documents to other modules.

## Usage

```bash
marker batch-send <target_module> <directory> [--pattern <glob>] [--parallel]
```

## Arguments

- `target_module`: Target module name
- `directory`: Directory containing extractions
- `--pattern`: File pattern (default: *.json)
- `--parallel`: Send in parallel

## Examples

```bash
# Send all JSON extractions
/marker-batch-send sparta ./extractions/

# Send specific pattern
/marker-batch-send arangodb ./output/ --pattern "cyber_*.json"

# Parallel sending
/marker-batch-send unsloth ./processed/ --parallel
```

---
*Marker Extraction Module*
