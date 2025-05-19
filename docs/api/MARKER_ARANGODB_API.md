# Marker-ArangoDB API Reference

This document provides comprehensive API reference information for the Marker-ArangoDB integration. It covers function interfaces, parameters, return values, and usage examples for programmatic integration.

## Table of Contents

- [Renderers](#renderers)
  - [ArangoDBRenderer](#arangodbrenderer)
- [Importers](#importers)
  - [document_to_arangodb](#document_to_arangodb)
  - [create_arangodb_client](#create_arangodb_client)
- [Relationship Extraction](#relationship-extraction)
  - [extract_relationships_from_marker](#extract_relationships_from_marker)
  - [extract_section_tree](#extract_section_tree)
- [QA Generation](#qa-generation)
  - [generate_qa_pairs](#generate_qa_pairs)
  - [export_qa_pairs](#export_qa_pairs)
- [QA Validation](#qa-validation)
  - [validate_qa_pairs](#validate_qa_pairs)
  - [generate_validation_report](#generate_validation_report)
- [CLI Commands](#cli-commands)
  - [arangodb import](#arangodb-import)
  - [arangodb qa-generation](#arangodb-qa-generation)
  - [arangodb validate-qa](#arangodb-validate-qa)

## Renderers

### ArangoDBRenderer

Renderer that produces ArangoDB-compatible JSON output from Marker documents.

**Class**: `marker.renderers.arangodb_json.ArangoDBRenderer`

**Constructor Parameters**: None

**Methods**:

```python
def __call__(self, document: Document) -> ArangoDBOutput
```

Converts a Marker document to ArangoDB-compatible JSON format.

**Parameters**:
- `document` (Document): Marker document object

**Returns**:
- `ArangoDBOutput`: Output containing ArangoDB-compatible JSON

**Example**:

```python
from marker.renderers.arangodb_json import ArangoDBRenderer

# Create renderer
renderer = ArangoDBRenderer()

# Process document
output = renderer(document)

# Access fields
doc_id = output.json["document"]["id"]
raw_corpus = output.json["raw_corpus"]["full_text"]
```

## Importers

### document_to_arangodb

Imports Marker document data to ArangoDB.

**Function**: `marker.arangodb.importers.document_to_arangodb`

**Signature**:

```python
def document_to_arangodb(
    marker_output: Dict[str, Any],
    db_host: str = "localhost",
    db_port: int = 8529,
    db_name: str = "documents",
    username: str = "root",
    password: str = "",
    protocol: str = "http",
    batch_size: int = 100,
    create_collections: bool = True,
    create_graph: bool = True,
    extract_relationships: bool = True
) -> Tuple[str, Dict[str, Any]]
```

**Parameters**:
- `marker_output` (Dict[str, Any]): Marker output in ArangoDB-compatible JSON format
- `db_host` (str, optional): ArangoDB host. Defaults to "localhost".
- `db_port` (int, optional): ArangoDB port. Defaults to 8529.
- `db_name` (str, optional): ArangoDB database name. Defaults to "documents".
- `username` (str, optional): ArangoDB username. Defaults to "root".
- `password` (str, optional): ArangoDB password. Defaults to "".
- `protocol` (str, optional): Protocol (http or https). Defaults to "http".
- `batch_size` (int, optional): Batch size for imports. Defaults to 100.
- `create_collections` (bool, optional): Whether to create collections if they don't exist. Defaults to True.
- `create_graph` (bool, optional): Whether to create graph if it doesn't exist. Defaults to True.
- `extract_relationships` (bool, optional): Whether to extract relationships. Defaults to True.

**Returns**:
- `Tuple[str, Dict[str, Any]]`: Tuple of (document key, import statistics)

**Example**:

```python
import json
from marker.arangodb.importers import document_to_arangodb

# Load marker output
with open('document.json', 'r') as f:
    marker_output = json.load(f)

# Import to ArangoDB
doc_key, stats = document_to_arangodb(
    marker_output, 
    db_host='localhost', 
    db_name='documents',
    username='root',
    password='password'
)

print(f"Document imported with key: {doc_key}")
print(f"Import stats: {stats}")
```

### create_arangodb_client

Creates an ArangoDB client instance.

**Function**: `marker.arangodb.importers.create_arangodb_client`

**Signature**:

```python
def create_arangodb_client(
    host: str = "localhost",
    port: int = 8529,
    username: str = "root",
    password: str = "",
    protocol: str = "http"
) -> ArangoClient
```

**Parameters**:
- `host` (str, optional): ArangoDB host. Defaults to "localhost".
- `port` (int, optional): ArangoDB port. Defaults to 8529.
- `username` (str, optional): ArangoDB username. Defaults to "root".
- `password` (str, optional): ArangoDB password. Defaults to "".
- `protocol` (str, optional): Protocol (http or https). Defaults to "http".

**Returns**:
- `ArangoClient`: ArangoDB client instance

**Example**:

```python
from marker.arangodb.importers import create_arangodb_client

# Create client
client = create_arangodb_client(
    host='localhost',
    port=8529,
    username='root',
    password='password'
)

# Connect to database
db = client.db('documents', username='root', password='password')

# Use database
collection = db.collection('documents')
```

## Relationship Extraction

### extract_relationships_from_marker

Extracts relationships from Marker output.

**Function**: `marker.utils.relationship_extractor.extract_relationships_from_marker`

**Signature**:

```python
def extract_relationships_from_marker(marker_output: Dict[str, Any]) -> List[Dict[str, Any]]
```

**Parameters**:
- `marker_output` (Dict[str, Any]): Marker output in ArangoDB-compatible JSON format

**Returns**:
- `List[Dict[str, Any]]`: List of relationships in the format:
  ```python
  [
      {
          "from": "section_123abc",
          "to": "section_456def",
          "type": "CONTAINS"
      }
  ]
  ```

**Example**:

```python
import json
from marker.utils.relationship_extractor import extract_relationships_from_marker

# Load marker output
with open('document.json', 'r') as f:
    marker_output = json.load(f)

# Extract relationships
relationships = extract_relationships_from_marker(marker_output)

print(f"Extracted {len(relationships)} relationships")
for rel in relationships[:5]:  # Show first 5
    print(f"{rel['from']} {rel['type']} {rel['to']}")
```

### extract_section_tree

Extracts a hierarchical section tree from Marker output.

**Function**: `marker.utils.relationship_extractor.extract_section_tree`

**Signature**:

```python
def extract_section_tree(marker_output: Dict[str, Any]) -> Dict[str, Any]
```

**Parameters**:
- `marker_output` (Dict[str, Any]): Marker output in ArangoDB-compatible JSON format

**Returns**:
- `Dict[str, Any]`: Hierarchical section tree structure

**Example**:

```python
import json
from marker.utils.relationship_extractor import extract_section_tree

# Load marker output
with open('document.json', 'r') as f:
    marker_output = json.load(f)

# Extract section tree
tree = extract_section_tree(marker_output)

# Print tree structure
def print_tree(node, depth=0):
    if "text" in node:
        print(f"{'  ' * depth}- {node['text']}")
    for child in node.get("children", []):
        print_tree(child, depth + 1)

print_tree(tree)
```

## QA Generation

### generate_qa_pairs

Generates QA pairs from Marker output.

**Function**: `marker.arangodb.qa_generator.generate_qa_pairs`

**Signature**:

```python
def generate_qa_pairs(
    marker_output_path: Optional[str] = None,
    marker_output: Optional[Dict[str, Any]] = None,
    output_dir: str = "qa_output",
    max_questions: int = DEFAULT_MAX_QUESTIONS,
    question_types: List[str] = None,
    question_distribution: Dict[str, float] = None,
    min_length: int = DEFAULT_MIN_LENGTH_THRESHOLD,
    export_formats: List[str] = DEFAULT_EXPORT_FORMATS,
    random_seed: Optional[int] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]
```

**Parameters**:
- `marker_output_path` (Optional[str], optional): Path to Marker JSON output file. Defaults to None.
- `marker_output` (Optional[Dict[str, Any]], optional): Marker output dictionary. Defaults to None.
- `output_dir` (str, optional): Output directory for QA pairs. Defaults to "qa_output".
- `max_questions` (int, optional): Maximum number of questions to generate. Defaults to DEFAULT_MAX_QUESTIONS.
- `question_types` (List[str], optional): List of question types to generate. Defaults to ["factual", "conceptual", "application"].
- `question_distribution` (Dict[str, float], optional): Distribution of question types. Defaults to {"factual": 0.6, "conceptual": 0.3, "application": 0.1}.
- `min_length` (int, optional): Minimum text length for contexts. Defaults to DEFAULT_MIN_LENGTH_THRESHOLD.
- `export_formats` (List[str], optional): List of export formats. Defaults to ["unsloth"].
- `random_seed` (Optional[int], optional): Random seed for reproducibility. Defaults to None.

**Returns**:
- `Tuple[List[Dict[str, Any]], Dict[str, Any]]`: Tuple of (QA pairs list, stats dictionary)

**Example**:

```python
from marker.arangodb.qa_generator import generate_qa_pairs

# Generate QA pairs from Marker output file
qa_pairs, stats = generate_qa_pairs(
    marker_output_path="document.json",
    output_dir="qa_output",
    max_questions=20,
    question_types=["factual", "conceptual", "application"],
    min_length=100
)

print(f"Generated {len(qa_pairs)} QA pairs")
print(f"Question types: {stats['question_type_counts']}")
print(f"Output files: {stats['output_files']}")
```

### export_qa_pairs

Exports QA pairs to various formats.

**Function**: `marker.arangodb.qa_generator.export_qa_pairs`

**Signature**:

```python
def export_qa_pairs(
    qa_pairs: List[Dict[str, Any]],
    output_dir: str,
    doc_id: str,
    doc_title: str,
    formats: List[str] = DEFAULT_EXPORT_FORMATS
) -> Dict[str, str]
```

**Parameters**:
- `qa_pairs` (List[Dict[str, Any]]): List of QA pair dictionaries
- `output_dir` (str): Output directory
- `doc_id` (str): Document ID
- `doc_title` (str): Document title
- `formats` (List[str], optional): List of export formats. Defaults to ["unsloth"].

**Returns**:
- `Dict[str, str]`: Dictionary mapping format to output file path

**Example**:

```python
from marker.arangodb.qa_generator import generate_qa_pairs, export_qa_pairs

# Generate QA pairs
qa_pairs, stats = generate_qa_pairs(marker_output_path="document.json")

# Export to custom formats
output_files = export_qa_pairs(
    qa_pairs=qa_pairs,
    output_dir="custom_output",
    doc_id=stats["document_id"],
    doc_title=stats["document_title"],
    formats=["unsloth"]
)

print(f"Exported to: {output_files}")
```

## QA Validation

### validate_qa_pairs

Validates QA pairs against various criteria.

**Function**: `marker.arangodb.validators.validate_qa_pairs`

**Signature**:

```python
def validate_qa_pairs(
    qa_pairs_path: str,
    marker_output_path: Optional[str] = None,
    marker_output: Optional[Dict[str, Any]] = None,
    checks: List[str] = DEFAULT_VALIDATION_CHECKS,
    relevance_threshold: float = DEFAULT_RELEVANCE_THRESHOLD,
    accuracy_threshold: float = DEFAULT_ACCURACY_THRESHOLD,
    quality_threshold: float = DEFAULT_QUESTION_QUALITY_THRESHOLD,
    output_path: Optional[str] = None
) -> Dict[str, Any]
```

**Parameters**:
- `qa_pairs_path` (str): Path to QA pairs JSONL file
- `marker_output_path` (Optional[str], optional): Path to Marker output JSON file. Defaults to None.
- `marker_output` (Optional[Dict[str, Any]], optional): Marker output dictionary. Defaults to None.
- `checks` (List[str], optional): List of validation checks to perform. Defaults to ["relevance", "accuracy", "quality", "diversity"].
- `relevance_threshold` (float, optional): Threshold for relevance validation. Defaults to DEFAULT_RELEVANCE_THRESHOLD.
- `accuracy_threshold` (float, optional): Threshold for accuracy validation. Defaults to DEFAULT_ACCURACY_THRESHOLD.
- `quality_threshold` (float, optional): Threshold for quality validation. Defaults to DEFAULT_QUESTION_QUALITY_THRESHOLD.
- `output_path` (Optional[str], optional): Path to write validation results. Defaults to None.

**Returns**:
- `Dict[str, Any]`: Dictionary with validation results

**Example**:

```python
from marker.arangodb.validators import validate_qa_pairs

# Validate QA pairs
validation_results = validate_qa_pairs(
    qa_pairs_path="qa_output/qa_unsloth_20250519_120000.jsonl",
    marker_output_path="document.json",
    checks=["relevance", "accuracy", "quality", "diversity"],
    relevance_threshold=0.7,
    accuracy_threshold=0.6,
    quality_threshold=0.5,
    output_path="validation_results.json"
)

print(f"Total QA pairs: {validation_results['total_qa_pairs']}")
print(f"Passing QA pairs: {validation_results['passing_qa_pairs']} ({validation_results['passing_percentage']:.1f}%)")
print(f"Failing QA pairs: {validation_results['failing_qa_pairs']}")

# Check results by validation type
for check, results in validation_results["results_by_check"].items():
    print(f"{check.capitalize()}: {results['passed']}/{results['passed'] + results['failed']} passed, avg score: {results['average_score']:.2f}")
```

### generate_validation_report

Generates a human-readable validation report.

**Function**: `marker.arangodb.validators.generate_validation_report`

**Signature**:

```python
def generate_validation_report(
    validation_results: Dict[str, Any],
    output_path: Optional[str] = None
) -> str
```

**Parameters**:
- `validation_results` (Dict[str, Any]): Validation results dictionary
- `output_path` (Optional[str], optional): Path to write report. Defaults to None.

**Returns**:
- `str`: Report as string

**Example**:

```python
from marker.arangodb.validators import validate_qa_pairs, generate_validation_report

# Validate QA pairs
validation_results = validate_qa_pairs(
    qa_pairs_path="qa_output/qa_unsloth_20250519_120000.jsonl",
    marker_output_path="document.json"
)

# Generate human-readable report
report = generate_validation_report(
    validation_results,
    output_path="validation_report.md"
)

print(f"Report generated to validation_report.md ({len(report)} characters)")
```

## CLI Commands

### arangodb import

Imports Marker output to ArangoDB.

**Command**: `arangodb import from-marker`

**Usage**:

```bash
arangodb import from-marker INPUT_FILE [OPTIONS]
```

**Arguments**:
- `INPUT_FILE`: Path to Marker JSON output file

**Options**:
- `--host TEXT`: ArangoDB host [default: localhost]
- `--port INTEGER`: ArangoDB port [default: 8529]
- `--db TEXT`: ArangoDB database name [default: documents]
- `--user TEXT`: ArangoDB username [default: root]
- `--password TEXT`: ArangoDB password [default: ]
- `--batch-size INTEGER`: Batch size for imports [default: 100]
- `--skip-graph`: Skip graph creation [default: False]
- `--verbose, -v`: Verbose output [default: False]

**Example**:

```bash
# Basic usage
arangodb import from-marker ./marker_output/document.json

# With custom database and credentials
arangodb import from-marker ./marker_output/document.json --host arangodb.example.com --port 8529 --db my_docs --user myuser --password mypass

# With batch size and verbose output
arangodb import from-marker ./marker_output/document.json --batch-size 200 --verbose
```

### arangodb qa-generation

Generates QA pairs from Marker output.

**Command**: `arangodb qa-generation from-marker`

**Usage**:

```bash
arangodb qa-generation from-marker INPUT_FILE [OPTIONS]
```

**Arguments**:
- `INPUT_FILE`: Path to Marker JSON output file

**Options**:
- `--output-dir, -o TEXT`: Output directory for QA pairs [default: qa_output]
- `--max-questions, -m INTEGER`: Maximum number of questions to generate [default: 20]
- `--question-types, -t TEXT`: Comma-separated question types to generate [default: factual,conceptual,application]
- `--min-length INTEGER`: Minimum text length for contexts [default: 100]
- `--export-formats, -f TEXT`: Comma-separated export formats [default: unsloth]
- `--seed INTEGER`: Random seed for reproducibility
- `--verbose, -v`: Verbose output [default: False]

**Example**:

```bash
# Basic usage
arangodb qa-generation from-marker ./marker_output/document.json

# With custom question types and output directory
arangodb qa-generation from-marker ./marker_output/document.json --question-types factual,application --output-dir ./my_qa_pairs

# With maximum questions and seed
arangodb qa-generation from-marker ./marker_output/document.json --max-questions 50 --seed 42
```

### arangodb validate-qa

Validates QA pairs from a JSONL file.

**Command**: `arangodb validate-qa from-jsonl`

**Usage**:

```bash
arangodb validate-qa from-jsonl QA_PAIRS_FILE [OPTIONS]
```

**Arguments**:
- `QA_PAIRS_FILE`: Path to QA pairs JSONL file

**Options**:
- `--marker-output, -m TEXT`: Path to Marker JSON output file for relevance and accuracy checks
- `--output, -o TEXT`: Path to write validation results (JSON format)
- `--report, -r TEXT`: Path to write validation report (Markdown format)
- `--checks, -c TEXT`: Comma-separated list of validation checks to perform [default: relevance,accuracy,quality,diversity]
- `--relevance-threshold FLOAT`: Threshold for relevance validation [default: 0.7]
- `--accuracy-threshold FLOAT`: Threshold for accuracy validation [default: 0.6]
- `--quality-threshold FLOAT`: Threshold for quality validation [default: 0.5]
- `--verbose, -v`: Verbose output [default: False]

**Example**:

```bash
# Basic usage
arangodb validate-qa from-jsonl ./qa_output/qa_pairs.jsonl --marker-output ./marker_output/document.json

# With custom checks and thresholds
arangodb validate-qa from-jsonl ./qa_output/qa_pairs.jsonl --marker-output ./marker_output/document.json --checks quality,diversity --quality-threshold 0.6

# Generate report and output JSON
arangodb validate-qa from-jsonl ./qa_output/qa_pairs.jsonl --marker-output ./marker_output/document.json --report validation_report.md --output validation_results.json
```

## Data Structures

### ArangoDB Output Format

The exact JSON structure required for ArangoDB:

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

### QA Pair Format

The format of generated QA pairs:

```json
{
  "instruction": "What is the main topic of this document?",
  "input": "",
  "output": "The main topic is ArangoDB integration with Marker.",
  "metadata": {
    "source_doc": "doc_123",
    "doc_title": "ArangoDB Integration Guide",
    "context": "This guide provides instructions for integrating ArangoDB with Marker.",
    "question_type": "factual",
    "source_type": "section",
    "title": "Introduction"
  }
}
```

### Relationship Format

The format of extracted relationships:

```json
{
  "from": "section_123abc",
  "to": "section_456def",
  "type": "CONTAINS"
}
```

### Validation Result Format

The format of validation results:

```json
{
  "status": "success",
  "total_qa_pairs": 20,
  "passing_qa_pairs": 15,
  "failing_qa_pairs": 5,
  "passing_percentage": 75.0,
  "checks_performed": ["relevance", "accuracy", "quality", "diversity"],
  "results_by_check": {
    "relevance": {
      "passed": 18,
      "failed": 2,
      "average_score": 0.82
    },
    "accuracy": {
      "passed": 16,
      "failed": 4,
      "average_score": 0.75
    },
    "quality": {
      "passed": 19,
      "failed": 1,
      "average_score": 0.88
    },
    "diversity": {
      "passed": 20,
      "failed": 0,
      "average_score": 0.95
    }
  },
  "detailed_results": [
    {
      "instruction": "What is the main topic?",
      "check_results": {
        "relevance": {
          "validated": true,
          "score": 0.85,
          "reason": "Relevant to document content"
        },
        "accuracy": {
          "validated": true,
          "score": 0.78,
          "reason": "Answer supported by document content"
        },
        "quality": {
          "validated": true,
          "score": 0.92,
          "reason": "Good quality QA pair"
        },
        "diversity": {
          "validated": true,
          "score": 0.95,
          "reason": "Question is sufficiently diverse"
        }
      },
      "passed_all_checks": true
    }
  ],
  "validation_time": 1.25
}
```

## Error Handling

### Common Error Types

| Error Type | Description | Handling Strategy |
|------------|-------------|-------------------|
| `ConnectionError` | Failed to connect to ArangoDB | Retry with exponential backoff |
| `ValidationError` | Document structure invalid | Check fields against required format |
| `ImportError` | Failed to import to ArangoDB | Check collection permissions and schema |
| `QAGenerationError` | Failed to generate QA pairs | Check min_length and content quality |

### Error Handling Example

```python
from marker.arangodb.importers import document_to_arangodb
import time

def import_with_retry(marker_output, max_retries=3):
    for attempt in range(max_retries):
        try:
            doc_id, stats = document_to_arangodb(marker_output)
            return doc_id, stats
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff
                print(f"Import failed: {e}. Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                print(f"Import failed after {max_retries} attempts: {e}")
                raise
```

## Extension Points

### Custom Renderers

Extend the `ArangoDBRenderer` class to customize the output format:

```python
from marker.renderers.arangodb_json import ArangoDBRenderer

class CustomArangoDBRenderer(ArangoDBRenderer):
    def __call__(self, document):
        output = super().__call__(document)
        
        # Add custom fields
        output.json["custom_field"] = "custom_value"
        
        return output
```

### Custom QA Generation

Extend the QA generation with custom question types:

```python
from marker.arangodb.qa_generator import extract_question_contexts, generate_question_from_context

def generate_custom_qa_pairs(marker_output, question_types=None):
    # Extract contexts
    contexts = extract_question_contexts(marker_output)
    
    # Define custom question generation
    def generate_custom_question(context):
        # Custom question generation logic
        # ...
        return {
            "question": "Custom question?",
            "answer": "Custom answer",
            "context": context["content"],
            "type": "custom",
            "source_type": context["type"],
            "title": context["title"]
        }
    
    # Generate QA pairs
    qa_pairs = []
    for context in contexts:
        qa_pairs.append(generate_custom_question(context))
    
    return qa_pairs
```

### Custom Validation

Implement custom validation checks:

```python
from marker.arangodb.validators import validate_qa_pairs

def custom_validation_check(qa_pair, marker_output, threshold=0.5):
    # Custom validation logic
    # ...
    return {
        "validated": True,
        "score": 0.8,
        "reason": "Custom validation passed"
    }

def validate_with_custom_checks(qa_pairs_path, marker_output_path):
    # Run standard validation
    validation_results = validate_qa_pairs(
        qa_pairs_path=qa_pairs_path,
        marker_output_path=marker_output_path
    )
    
    # Add custom validation
    # Load QA pairs and marker output
    # ...
    # Run custom validation on each pair
    # ...
    
    return validation_results
```

## Conclusion

This API reference provides comprehensive documentation for the Marker-ArangoDB integration. For detailed usage guides and examples, see [MARKER_ARANGODB_INTEGRATION.md](../guides/MARKER_ARANGODB_INTEGRATION.md).