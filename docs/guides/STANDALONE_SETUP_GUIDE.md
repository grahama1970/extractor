# Standalone Setup Guide for Extractor

This guide shows how to use extractor's PDF to JSON conversion in another project.

## Dependencies

Add these to your `pyproject.toml` or `requirements.txt`:

```toml
pymupdf>=1.23.0
pydantic>=2.0.0
pillow>=10.0.0
surya-ocr>=0.4.0
torch>=2.0.0
transformers>=4.35.0
```

## Installation Options

### Option A: Install as Package
```bash
pip install git+https://github.com/grahama1970/extractor.git
```

### Option B: Copy Source Code
Copy the `src/extractor` directory to your project.

## Minimal Usage Example

```python
import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from pathlib import Path
import json

# Option A: If installed as package
from extractor.core.convert import convert_pdf_to_json

# Option B: If copied directly
from your_project.extractor.core.convert import convert_pdf_to_json

def extract_pdf(pdf_path: str) -> dict:
    """Extract PDF to structured JSON."""
    return convert_pdf_to_json(
        pdf_path,
        disable_multiprocessing=True,
        disable_tqdm=True,
        use_ocr=False  # Set True if you need OCR
    )

# Usage
if __name__ == "__main__":
    pdf_path = "path/to/your.pdf"
    result = extract_pdf(pdf_path)
    
    # Save to JSON
    with open("output.json", "w") as f:
        json.dump(result, f, indent=2)
    
    # Access extracted text
    for block in result.get("blocks", []):
        if block["type"] == "text":
            print(block["content"])
```

## Common Issues and Solutions

### 1. CUDA/GPU Issues
If you don't have CUDA:
```python
import os
os.environ["CUDA_VISIBLE_DEVICES"] = ""  # Force CPU usage
```

### 2. Memory Issues with Large PDFs
```python
result = convert_pdf_to_json(
    pdf_path,
    max_pages=10,  # Limit pages
    disable_multiprocessing=True
)
```

### 3. Import Errors
Make sure to set PYTHONPATH if copying source:
```bash
export PYTHONPATH="${PYTHONPATH}:/path/to/your/project"
```

## Advanced Configuration

For more control over extraction:

```python
from extractor.core.config.settings import ExtractorSettings

settings = ExtractorSettings(
    enable_table_extraction=True,
    enable_code_extraction=True,
    enable_image_extraction=False,
    max_file_size_mb=50
)

result = convert_pdf_to_json(
    pdf_path,
    settings=settings
)
```

## Output Format

The JSON output contains:
- `blocks`: Array of content blocks
- `metadata`: Document metadata
- `pages`: Page-level information
- `tables`: Extracted tables (if enabled)
- `code_blocks`: Extracted code (if enabled)

Each block has:
- `type`: "text", "table", "code", "image", etc.
- `content`: The extracted content
- `page_number`: Source page
- `bbox`: Bounding box coordinates

## Need Help?

- Check the [examples directory](../../examples/) for more usage patterns
- See the [main README](../../README.md) for full documentation
- Report issues at: https://github.com/grahama1970/extractor/issues