# Marker-ArangoDB Integration Guide

## Overview

This guide provides comprehensive instructions for integrating Marker's PDF processing capabilities with ArangoDB for document storage, relationship tracking, and QA pair generation. The integration enables a complete workflow from PDF document extraction to fine-tuning-ready QA pairs with proper validation.

**Key Benefits:**
- Extract structured content from PDF documents using Marker
- Store document content with hierarchical relationships in ArangoDB
- Generate high-quality QA pairs suitable for language model fine-tuning
- Validate QA pairs for relevance, accuracy, and quality

**Prerequisites:**
- Python 3.8+
- Marker installed (`pip install marker-pdf`)
- Access to an ArangoDB instance (local or remote)
- Basic understanding of PDF structure and QA generation concepts

## Quick Start

```bash
# Step 1: Extract PDF with Marker QA-optimized settings
marker convert document.pdf --renderer arangodb_json --output-dir ./marker_output

# Step 2: Import to ArangoDB and generate QA pairs
arangodb import from-marker ./marker_output/document.json
arangodb qa-generation from-marker ./marker_output/document.json --max-questions 20

# Step 3: Validate QA pairs
arangodb validate-qa from-jsonl ./qa_output/qa_unsloth_*.jsonl --marker-output ./marker_output/document.json

# Step 4: View validation report (optional)
cat qa_validation_report.md
```

## Architectural Overview

The Marker-ArangoDB integration follows a clean separation of concerns:

1. **Marker**: Handles PDF processing, content extraction, and corpus validation
2. **ArangoDB**: Handles relationship tracking, QA generation, and data storage

This division creates a modular, maintainable system where each component focuses on its strengths:

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│    PDF      │─────▶│   Marker    │─────▶│  ArangoDB   │
│  Document   │      │ Processing  │      │  Database   │
└─────────────┘      └─────────────┘      └─────────────┘
                           │                    │
                           ▼                    ▼
                    ┌─────────────┐      ┌─────────────┐
                    │ ArangoDB    │      │    QA       │
                    │  JSON       │─────▶│ Generation  │
                    └─────────────┘      └─────────────┘
                                               │
                                               ▼
                                        ┌─────────────┐
                                        │  QA Pair    │
                                        │ Validation  │
                                        └─────────────┘
                                               │
                                               ▼
                                        ┌─────────────┐
                                        │ Fine-Tuning │
                                        │   Format    │
                                        └─────────────┘
```

## Component Responsibilities

### Marker Responsibilities
- PDF content extraction
- Document structure identification
- Block type classification (section headers, text, code, etc.)
- Corpus validation and quality assurance
- Generation of ArangoDB-compatible JSON

### ArangoDB Responsibilities
- Document storage and relationship tracking
- Hierarchical structure representation
- Section summarization (optional)
- QA pair generation
- Context extraction for questions
- Export to fine-tuning formats

## Required Data Format

Marker must output JSON with this exact structure for ArangoDB compatibility:

```json
{
  "document": {
    "id": "unique_document_id",
    "pages": [
      {
        "blocks": [
          {
            "type": "section_header",
            "text": "Introduction to Topic",
            "level": 1
          },
          {
            "type": "text",
            "text": "This is the content text."
          }
        ]
      }
    ]
  },
  "metadata": {
    "title": "Document Title",
    "processing_time": 1.2
  },
  "validation": {
    "corpus_validation": {
      "performed": true,
      "threshold": 97,
      "raw_corpus_length": 5000
    }
  },
  "raw_corpus": {
    "full_text": "Complete document text content...",
    "pages": [
      {
        "page_num": 0,
        "text": "Page content...",
        "tables": []
      }
    ],
    "total_pages": 1
  }
}
```

### Critical Fields

These fields are **absolutely required** for proper integration:

| Field | Description | Purpose |
|-------|-------------|---------|
| `document.id` | Unique document identifier | Used for database references and relationship tracking |
| `raw_corpus.full_text` | Complete validated text | Used for answer validation and QA generation |
| `document.pages[].blocks[]` | Structured content blocks | Used for extracting relationships and context |

### Block Type Definitions

| Block Type | Description | Purpose in QA Generation |
|------------|-------------|--------------------------|
| `section_header` | Section title with level | Used for context and hierarchy |
| `text` | Regular paragraph text | Used for answer content |
| `code` | Programming code snippets | Used for code-related QA pairs |
| `table` | Tabular data | Used for data-related QA pairs |
| `equation` | Mathematical equations | Used for math-related QA pairs |

## Step-by-Step Integration

### 1. Generate ArangoDB-Compatible JSON

Use Marker with the ArangoDB JSON renderer to extract content from PDFs:

```bash
marker convert document.pdf --renderer arangodb_json --output-dir ./marker_output
```

Configuration options for optimal extraction:

```bash
# Enable corpus validation with high threshold
marker convert document.pdf --renderer arangodb_json --validation-threshold 0.97 --output-dir ./marker_output

# Enable enhanced table extraction
marker convert document.pdf --renderer arangodb_json --enhanced-tables --output-dir ./marker_output

# Use QA-optimized settings
marker-qa convert document.pdf --output-dir ./marker_output
```

### 2. Import to ArangoDB

Import the Marker output into ArangoDB:

```bash
arangodb import from-marker ./marker_output/document.json --host localhost --db documents
```

Configuration options:

```bash
# Specify custom database and credentials
arangodb import from-marker ./marker_output/document.json --host arangodb.example.com --port 8529 --db my_documents --user username --password password

# Control batch size for large documents
arangodb import from-marker ./marker_output/document.json --batch-size 200

# Skip graph creation (collections only)
arangodb import from-marker ./marker_output/document.json --skip-graph
```

### 3. Generate QA Pairs

Generate QA pairs from the imported document:

```bash
arangodb qa-generation from-marker ./marker_output/document.json --max-questions 20
```

Configuration options:

```bash
# Specify question types and output directory
arangodb qa-generation from-marker ./marker_output/document.json --question-types factual,conceptual,application --output-dir ./my_qa_pairs

# Set minimum context length for questions
arangodb qa-generation from-marker ./marker_output/document.json --min-length 150

# Specify random seed for reproducibility
arangodb qa-generation from-marker ./marker_output/document.json --seed 42
```

### 4. Validate QA Pairs

Validate the generated QA pairs against the source document:

```bash
arangodb validate-qa from-jsonl ./qa_output/qa_unsloth_*.jsonl --marker-output ./marker_output/document.json
```

Configuration options:

```bash
# Specify validation checks and thresholds
arangodb validate-qa from-jsonl ./qa_output/qa_pairs.jsonl --marker-output ./marker_output/document.json --checks relevance,accuracy,quality --relevance-threshold 0.8

# Generate validation report
arangodb validate-qa from-jsonl ./qa_output/qa_pairs.jsonl --marker-output ./marker_output/document.json --report validation_report.md

# Save validation results to JSON
arangodb validate-qa from-jsonl ./qa_output/qa_pairs.jsonl --marker-output ./marker_output/document.json --output validation_results.json
```

## Complete End-to-End Workflow

This workflow processes a PDF document and generates validated QA pairs ready for fine-tuning:

```bash
# Step 1: Extract PDF with Marker QA-optimized settings
marker-qa convert document.pdf --output-dir ./marker_output

# Step 2: Generate QA pairs from Marker output
arangodb qa-generation from-marker ./marker_output/document.json --max-questions 20

# Step 3: Validate QA pairs
arangodb validate-qa from-jsonl ./qa_output/qa_unsloth_*.jsonl --marker-output ./marker_output/document.json --report qa_validation_report.md
```

## Relationship Extraction

A critical component of the integration is extracting relationships from the Marker document structure. This is handled by the `extract_relationships_from_marker` function:

```python
def extract_relationships_from_marker(marker_output):
    document = marker_output.get("document", {})
    relationships = []

    # Extract section relationships (hierarchy)
    section_map = {}
    for page in document.get("pages", []):
        current_section = None
        for block in page.get("blocks", []):
            if block.get("type") == "section_header":
                # Store section with level
                section_id = f"section_{hash(block['text'])}"
                section_map[section_id] = {
                    "text": block["text"],
                    "level": block.get("level", 1)
                }

                # Link to parent section if exists
                if current_section and current_section["level"] < block.get("level", 1):
                    relationships.append({
                        "from": current_section["id"],
                        "to": section_id,
                        "type": "CONTAINS"
                    })

                current_section = {"id": section_id, "level": block.get("level", 1)}
            elif current_section:
                # Content belongs to current section
                block_id = f"block_{hash(block['text'])}"
                relationships.append({
                    "from": current_section["id"],
                    "to": block_id,
                    "type": "CONTAINS"
                })

    return relationships
```

## Configuration Best Practices

### Marker Configuration

For optimal results when generating ArangoDB-compatible JSON:

| Setting | Recommended Value | Description |
|---------|------------------|-------------|
| `validation_threshold` | 0.97 | Ensures high-quality corpus extraction |
| `include_raw_corpus` | true | Essential for QA validation |
| `enhanced_tables` | true | Improves table extraction for QA |
| `parser` | "qa_optimized" | Configures settings for QA generation |

### ArangoDB Configuration

For optimal ArangoDB performance:

| Setting | Recommended Value | Description |
|---------|------------------|-------------|
| `batch_size` | 100-200 | Balances performance and memory usage |
| `create_graph` | true | Enables relationship traversal |

### QA Generation Configuration

For high-quality QA pairs:

| Setting | Recommended Value | Description |
|---------|------------------|-------------|
| `max_questions` | 20-50 | Reasonable number per document |
| `question_types` | "factual,conceptual,application" | Diverse question types |
| `min_length` | 100 | Minimum context length for questions |

### Validation Configuration

For effective QA validation:

| Setting | Recommended Value | Description |
|---------|------------------|-------------|
| `checks` | "relevance,accuracy,quality,diversity" | Comprehensive validation |
| `relevance_threshold` | 0.7 | Balance between strictness and recall |
| `accuracy_threshold` | 0.6 | Reasonable threshold for factual accuracy |
| `quality_threshold` | 0.5 | Basic quality requirements |

## Troubleshooting

### Common Issues

| Problem | Possible Cause | Solution |
|---------|----------------|----------|
| Missing `raw_corpus.full_text` | Marker configuration issue | Ensure `include_raw_corpus: true` in configuration |
| Relationships not extracted | Block identification issue | Check document structure and block types |
| QA generation produces few questions | Insufficient context length | Increase context with `--min-length` parameter |
| Low relevance scores in validation | Mismatch between questions and context | Adjust relevance threshold or improve context extraction |
| ArangoDB import errors | Connection issues | Verify database credentials and connectivity |

### Specific Error Messages

#### "Failed to extract relationships - document structure invalid"

**Cause**: Document structure doesn't match expected format for relationship extraction.

**Solution**:
1. Verify document.pages[].blocks[] structure in JSON
2. Ensure section_header blocks have level attribute
3. Check for proper nesting of section headers

#### "QA generation found no suitable contexts"

**Cause**: Insufficient content length or missing section headers.

**Solution**:
1. Lower the min_length threshold
2. Improve document structure with proper section headers
3. Check raw_corpus.full_text existence and length

#### "Validation failed - marker_output not found"

**Cause**: Original marker output not available for validation.

**Solution**:
1. Ensure marker_output_path points to valid Marker output file
2. Regenerate Marker output if necessary
3. Use correct path format (relative or absolute)

## Performance Considerations

### For Large Documents

Processing large documents requires attention to resource usage:

1. **Batch Processing**: Use `--batch-size` parameter for ArangoDB imports
2. **Memory Management**: Monitor RAM usage during extraction and QA generation
3. **Page Limiting**: Consider processing documents in page ranges for very large PDFs

### Database Optimization

For large-scale deployments:

1. **Indexing**: Create indexes on frequently queried fields
2. **Query Optimization**: Use AQL optimization techniques for complex queries
3. **Connection Pooling**: Configure connection pooling for concurrent access

## Advanced Features

### Section Summarization

Enable section summarization for enhanced QA generation:

```bash
marker convert document.pdf --renderer arangodb_json --enable-summarization --output-dir ./marker_output
```

### Enhanced Relationship Extraction

For complex document structures, use the enhanced relationship extractor:

```python
from marker.utils.relationship_extractor import extract_section_tree
tree = extract_section_tree(marker_output)
```

### Custom QA Generation

Implement custom QA generation strategies by extending the base generator:

```python
from marker.arangodb.qa_generator import generate_qa_pairs

# Custom distribution of question types
custom_distribution = {
    "factual": 0.5,
    "conceptual": 0.3,
    "application": 0.2
}

qa_pairs, stats = generate_qa_pairs(
    marker_output_path="document.json",
    question_distribution=custom_distribution
)
```

## Conclusion

The Marker-ArangoDB integration provides a powerful pipeline for extracting content from PDF documents, storing it with proper structure and relationships, and generating high-quality QA pairs for language model fine-tuning. By following the guidelines in this document, you can implement a robust document processing system with proper separation of concerns.

For detailed API reference information, see [MARKER_ARANGODB_API.md](../api/MARKER_ARANGODB_API.md).