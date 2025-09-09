# Extractor Module Integration Guide

## Overview

The extractor module is designed to be used as a component in larger systems. This guide explains the best practices for integrating the extractor with other modules.

## Integration Patterns

### 1. Direct Python Import (Recommended)

For Python projects, import the extractor directly:

```python
from extractor.unified_extractor import UnifiedExtractor
from extractor.core.config.parser import ParserConfig

# Initialize extractor
config = ParserConfig()
extractor = UnifiedExtractor(config)

# Process a PDF
result = await extractor.extract(
    pdf_path="path/to/document.pdf",
    output_dir="output/",
    use_llm=True  # Enable AI enhancements
)
```

### 2. MCP Server Integration

The extractor provides an MCP (Model Context Protocol) server for integration with AI systems:

```bash
# Start the MCP server
cd src/extractor/servers
python mcp_marker_pdf.py
```

Use from Claude or other MCP clients:
```python
# Available MCP tools:
- extract_pdf: Extract content from PDF
- extract_pdf_batch: Process multiple PDFs
- get_extraction_status: Check processing status
```

### 3. REST API Wrapper

Create a simple FastAPI wrapper for HTTP integration:

```python
from fastapi import FastAPI, UploadFile
from extractor.unified_extractor import UnifiedExtractor

app = FastAPI()
extractor = UnifiedExtractor()

@app.post("/extract")
async def extract_pdf(file: UploadFile):
    # Save uploaded file
    pdf_path = f"temp/{file.filename}"
    with open(pdf_path, "wb") as f:
        f.write(await file.read())
    
    # Extract
    result = await extractor.extract(pdf_path)
    return result
```

### 4. Queue-Based Integration

For scalable processing, use with Celery or similar:

```python
from celery import Celery
from extractor.unified_extractor import UnifiedExtractor

app = Celery('tasks', broker='redis://localhost:6379')

@app.task
def extract_pdf_task(pdf_path: str):
    extractor = UnifiedExtractor()
    return extractor.extract_sync(pdf_path)
```

## Configuration

### Environment Variables

```bash
# Required
PYTHONPATH=./src
ARANGO_HOST=localhost
ARANGO_PORT=8529
ARANGO_USERNAME=root
ARANGO_PASSWORD=openSesame

# Optional - AI Services
ANTHROPIC_API_KEY=your_key
MOONSHOT_API_KEY=your_key
GOOGLE_APPLICATION_CREDENTIALS=vertex_service_account.json

# Optional - Performance
MAX_WORKERS=4
BATCH_SIZE=10
```

### Configuration Object

```python
from extractor.core.config.parser import ParserConfig

config = ParserConfig(
    # Processing options
    ocr_engine="surya",           # or "tesseract"
    extract_images=True,
    extract_tables=True,
    
    # AI enhancements
    use_llm=True,
    llm_provider="anthropic",     # or "moonshot", "vertex"
    
    # Output options
    output_format="json",         # or "markdown", "html"
    include_metadata=True
)
```

## Key Components

### 1. Pipeline Stages

The extractor uses a multi-stage pipeline:

1. **Annotation Extraction** - Extract human annotations
2. **Block Extraction** - Extract PDF blocks with Marker
3. **Pattern Detection** - Detect suspicious patterns
4. **Section Building** - Build document structure
5. **Table Extraction** - Extract tables with Camelot
6. **Figure Extraction** - Extract figures with AI description
7. **Content Enhancement** - Enhance with LLM
8. **Export** - Export to various formats

### 2. Label Integration

Integrate labeled data for better accuracy:

```python
from extractor.core.processors.simple_knn_classifier import SimpleKNNClassifier

# Use labeled patterns
classifier = SimpleKNNClassifier(
    collection_name="header_patterns",
    k=5,
    use_faiss=True
)

# Process with classification
blocks = classifier.process(blocks, metadata)
```

### 3. Storage Integration

Results are stored in ArangoDB:

```python
from pyarango import ArangoClient

# Query extracted documents
client = ArangoClient(hosts="http://localhost:8529")
db = client.db("_system", username="root", password="openSesame")

# Find documents by content
cursor = db.aql.execute("""
    FOR doc IN extracted_documents
    FILTER doc.content LIKE "%search term%"
    RETURN doc
""")
```

## Best Practices

### 1. Error Handling

```python
from extractor.unified_extractor import UnifiedExtractor
from extractor.core.utils.error_handling import ExtractorError

try:
    result = await extractor.extract(pdf_path)
except ExtractorError as e:
    logger.error(f"Extraction failed: {e}")
    # Handle specific error types
    if e.error_type == "INVALID_PDF":
        return {"error": "Invalid PDF file"}
```

### 2. Batch Processing

```python
from extractor.unified_extractor import UnifiedExtractor
import asyncio

async def process_batch(pdf_paths: List[str]):
    extractor = UnifiedExtractor()
    
    # Process in parallel with concurrency limit
    semaphore = asyncio.Semaphore(4)
    
    async def process_one(path):
        async with semaphore:
            return await extractor.extract(path)
    
    tasks = [process_one(path) for path in pdf_paths]
    return await asyncio.gather(*tasks)
```

### 3. Memory Management

For large PDFs:

```python
config = ParserConfig(
    # Limit concurrent pages
    max_pages_in_memory=10,
    
    # Use streaming for large files
    use_streaming=True,
    
    # Reduce image quality
    image_dpi=150  # Default is 300
)
```

### 4. Monitoring

```python
from extractor.core.utils.monitoring import ExtractionMonitor

monitor = ExtractionMonitor()

# Track extraction
with monitor.track_extraction(pdf_path):
    result = await extractor.extract(pdf_path)

# Get metrics
metrics = monitor.get_metrics()
print(f"Extraction time: {metrics['duration_seconds']}s")
print(f"Pages processed: {metrics['pages_processed']}")
```

## Integration Examples

### With SPARTA (Input Pipeline)

```python
# SPARTA provides PDFs → Extractor processes them
from sparta.output_handler import get_latest_pdfs
from extractor.unified_extractor import UnifiedExtractor

pdfs = get_latest_pdfs()
extractor = UnifiedExtractor()

for pdf in pdfs:
    result = await extractor.extract(pdf.path)
    # Store in ArangoDB
```

### With Unsloth (Training Pipeline)

```python
# Extractor provides structured data → Unsloth trains models
from extractor.core.storage.arango_client import get_training_data

# Get high-quality extracted sections
training_data = get_training_data(
    min_confidence=0.8,
    document_types=["technical", "academic"]
)

# Format for Unsloth
formatted_data = [
    {
        "instruction": section["title"],
        "input": section["context"],
        "output": section["content"]
    }
    for section in training_data
]
```

### With Web UI

```python
# Streamlit example
import streamlit as st
from extractor.unified_extractor import UnifiedExtractor

st.title("PDF Extractor")

uploaded_file = st.file_uploader("Choose a PDF", type="pdf")

if uploaded_file:
    # Save temporarily
    with open("temp.pdf", "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    # Extract
    extractor = UnifiedExtractor()
    result = extractor.extract_sync("temp.pdf")
    
    # Display results
    st.json(result)
```

## Troubleshooting

### Common Issues

1. **Import Errors**
   ```bash
   # Ensure PYTHONPATH is set
   export PYTHONPATH=./src
   ```

2. **Memory Issues**
   ```python
   # Reduce batch size
   config.batch_size = 5
   ```

3. **Slow Processing**
   ```python
   # Disable AI features for speed
   config.use_llm = False
   ```

4. **Connection Errors**
   ```python
   # Check ArangoDB connection
   from extractor.core.utils.db_utils import test_connection
   test_connection()
   ```

## Performance Tips

1. **Use FAISS for large label sets** (>1000 patterns)
2. **Enable GPU for Marker** if available
3. **Cache embeddings** to avoid recomputation
4. **Use async processing** for multiple PDFs
5. **Monitor memory usage** with large documents

## Security Considerations

1. **Validate inputs** - Check PDF files before processing
2. **Sanitize outputs** - Clean extracted content
3. **Limit file sizes** - Set maximum PDF size
4. **Use timeouts** - Prevent hanging on complex PDFs
5. **Secure API keys** - Use environment variables

## Next Steps

- Review the [Label Integration Guide](LABEL_TO_EXTRACTION_INTEGRATION.md)
- Check [Pipeline Documentation](pipeline_docs/)
- See [API Reference](api_reference.md)