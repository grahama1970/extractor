# Knowledge-First Sub-Agent Architecture

## Core Principle: ALL Sub-Agents MUST Be Knowledge-First

Every sub-agent in the extractor system follows a mandatory knowledge-first pattern enforced by the `BaseWorker` class.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     BaseWorker (Abstract)                    │
│                                                              │
│  Enforces Knowledge-First Pattern:                          │
│  1. ALWAYS check knowledge_architect first                  │
│  2. Look for PDF annotations                                │
│  3. Use high-confidence matches (>0.85) directly           │
│  4. Process only when no match exists                      │
│  5. Store successful results back                          │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │ Inherits
    ┌─────────────────────────┴─────────────────────────┐
    │                                                   │
┌───────────────────┐                        ┌──────────────────┐
│ TableAnalyzerWorker│                        │ TableFixerWorker │
│                   │                        │                  │
│ • Checks for      │                        │ • Checks for     │
│   similar tables  │                        │   corruption     │
│ • Uses Camelot    │                        │   patterns       │
│ • Captures        │                        │ • Applies known  │
│   screenshots     │                        │   fixes          │
└───────────────────┘                        └──────────────────┘
    ┌─────────────────────────┴─────────────────────────┐
    │                                                   │
┌───────────────────┐                        ┌──────────────────┐
│ EquationProcessor │                        │  FormProcessor   │
│    (Pending)      │                        │   (Pending)      │
└───────────────────┘                        └──────────────────┘
```

## Knowledge-First Flow

```
Input Data
    │
    ▼
┌─────────────────────┐
│ BaseWorker.process()│
└─────────────────────┘
    │
    ▼
┌─────────────────────┐     ┌──────────────────┐
│ Check Knowledge DB  │────▶│ High Confidence? │
└─────────────────────┘     └──────────────────┘
                                  │ Yes (>0.85)
                                  ▼
                            ┌──────────────────┐
                            │ Return Historical│
                            │     Result       │
                            └──────────────────┘
                                  │ No
                                  ▼
┌─────────────────────┐     ┌──────────────────┐
│ Check Annotations   │────▶│ Found Correction?│
└─────────────────────┘     └──────────────────┘
                                  │ Yes
                                  ▼
                            ┌──────────────────┐
                            │ Apply Annotation │
                            └──────────────────┘
                                  │ No
                                  ▼
┌─────────────────────┐     ┌──────────────────┐
│ Process Data        │────▶│ Validate Result  │
└─────────────────────┘     └──────────────────┘
                                  │ Valid
                                  ▼
                            ┌──────────────────┐
                            │ Store to KB      │
                            └──────────────────┘
```

## Implementation Requirements

### 1. Every Worker MUST Inherit from BaseWorker

```python
from .base_worker import BaseWorker, KnowledgeMatch

class MyWorker(BaseWorker):
    def __init__(self, knowledge_architect=None):
        super().__init__(knowledge_architect)  # REQUIRED
```

### 2. Implement ALL Abstract Methods

```python
def get_worker_type(self) -> str:
    """Unique identifier for this worker type"""
    return "my_worker"

def extract_features(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract features for knowledge matching"""
    return {...}

def apply_knowledge_match(self, match: KnowledgeMatch, input_data: Dict[str, Any]) -> Any:
    """Apply historical result"""
    return match.result

async def process_without_knowledge(self, input_data: Dict[str, Any]) -> Any:
    """Process only when no knowledge exists"""
    return await self._actual_processing(input_data)

def validate_result(self, result: Any) -> bool:
    """Check if result should be stored"""
    return result.confidence > 0.8
```

### 3. ALWAYS Use BaseWorker.process()

```python
# WRONG - bypasses knowledge-first
result = await worker.my_custom_method(data)

# CORRECT - enforces knowledge-first
result = await worker.process(
    input_data=data,
    context={'pdf_name': 'doc.pdf', 'page': 1}
)
```

## Knowledge Storage Schema

Each worker stores cases with:
- **case_id**: Unique identifier
- **worker_type**: Which worker created it
- **input_features**: Extracted features
- **result**: The successful result
- **context**: PDF name, page, etc.
- **confidence**: Quality score
- **usage_count**: How often it's been used
- **success_rate**: How well it works

## Benefits

1. **Performance**: 85%+ cases resolved instantly from knowledge
2. **Consistency**: Same inputs always produce same outputs
3. **Learning**: System improves with each document
4. **Debugging**: Can trace decisions back to specific cases
5. **Annotation Support**: Manual corrections automatically applied

## Current Workers

### ✅ Implemented
- **TableAnalyzerWorker**: Analyzes table structure, quality, and type
- **TableFixerWorker**: Fixes corrupted tables using multiple sources

### 🚧 Pending
- **PDFObjectIdentifierWorker**: Identifies misclassified objects
- **EquationProcessorWorker**: Processes mathematical equations
- **FormProcessorWorker**: Handles form fields and structure
- **ImageDescriptionWorker**: Generates image descriptions

## Usage Example

```python
# Initialize with knowledge architect
kb = KnowledgeArchitect(arangodb_connection)
table_analyzer = TableAnalyzerWorker(knowledge_architect=kb)
table_fixer = TableFixerWorker(knowledge_architect=kb)

# Process with automatic knowledge-first flow
analysis = await table_analyzer.process(
    input_data={
        'text': 'Descripti\non',
        'cells': [...],
        'pdf_path': '/path/to/pdf'
    },
    context={
        'pdf_name': 'technical_doc.pdf',
        'page': 5,
        'annotations': [...]
    }
)

# First time: Processes and stores
# Second time: Returns instantly from knowledge
```

## Key Rules

1. **NO DIRECT PROCESSING**: Never call processing methods directly
2. **ALWAYS USE process()**: This enforces the knowledge-first pattern
3. **STORE GOOD RESULTS**: Validate and store successful results
4. **CHECK ANNOTATIONS**: PDF annotations override everything
5. **TRUST HIGH CONFIDENCE**: >0.85 confidence means use it

This architecture ensures that every sub-agent learns from experience and provides consistent, fast results.