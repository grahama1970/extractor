# Marker Enhanced Features Documentation

This document describes the enhanced features added to the Marker PDF converter.

## Overview

The enhanced Marker includes four main feature additions:

1. **Section Breadcrumbs** - For hierarchical document navigation
2. **LLM Model Selection** - Flexible model provider support
3. **Document Hierarchy** - Sections as parent nodes
4. **Section Summaries** - Automatic summarization

## Features

### 1. Section Breadcrumbs

Section breadcrumbs provide hierarchical navigation through documents.

**Purpose**: Enable proper parent-child relationships for database insertion (e.g., ArangoDB)

**Implementation**:
- Added `section_hierarchy_titles` and `section_hierarchy_hashes` to `SectionHeader`
- Tracks full path from root to current section
- Essential for maintaining document structure in graph databases

**Usage**:
```python
section.metadata.section_hierarchy_titles  # ["1. Introduction", "1.1 Background"]
section.metadata.section_hierarchy_hashes  # ["hash1", "hash2"]
```

### 2. LLM Model Selection

Unified interface for multiple LLM providers through LiteLLM.

**Purpose**: Allow cost/performance optimization by choosing different models

**Supported Providers**:
- Google Gemini
- OpenAI
- Anthropic Claude
- Local models (Ollama)
- Custom endpoints

**Usage**:
```bash
marker_single file.pdf --use_llm --llm_service marker.services.litellm.LiteLLMService --model "claude-3-sonnet"
```

### 3. Document Hierarchy

Transforms flat document structure into hierarchical with sections as containers.

**Purpose**: Preserve logical document structure with proper nesting

**Features**:
- Sections contain their content blocks
- Maintains reading order within sections
- Supports nested subsections

**Structure**:
```
Document
├── Section 1
│   ├── Text blocks
│   ├── Tables
│   └── Section 1.1
│       └── Content
└── Section 2
    └── Content
```

### 4. Section Summaries

Automatic LLM-generated summaries for each section and overall document.

**Purpose**: Provide quick overview of document content

**Features**:
- Per-section summaries
- Overall document summary from section summaries
- Configurable model and parameters

**Configuration**:
```python
config = {
    'model_name': 'gemini-2.0-flash-exp',
    'temperature': 0.3,
    'max_section_length': 3000
}
```

## Usage Examples

### Basic Usage with All Features

```bash
marker_single document.pdf \
  --add-summaries \
  --enable-breadcrumbs \
  --use_llm \
  --output_format hierarchical_json
```

### Python API Usage

```python
from marker.converters.pdf import PdfConverter
from marker.processors.simple_summarizer import SimpleSectionSummarizer
from marker.processors.hierarchy_builder import HierarchyBuilder

# Configure processors
processors = [
    SimpleSectionSummarizer({'model_name': 'gemini-2.0-flash-exp'}),
    HierarchyBuilder()
]

# Create converter
converter = PdfConverter(
    processor_list=processors,
    artifact_dict=create_model_dict()
)

# Convert document
result = converter("document.pdf")
```

## Configuration Guide

### Summary Configuration

```python
{
    'model_name': 'gemini-2.0-flash-exp',  # LLM model to use
    'temperature': 0.3,                    # Lower = more consistent
    'max_section_length': 3000            # Truncate long sections
}
```

### Table Configuration

Use simplified presets:
```python
from marker.config.table_simple import PRESET_BALANCED

config = {
    'table_config': PRESET_BALANCED
}
```

## Performance Considerations

1. **Summaries** add LLM latency (~0.5-2s per section)
2. **Breadcrumbs** have minimal impact
3. **Hierarchy** slightly increases memory usage
4. **Enhanced tables** may add processing time

## Best Practices

1. Use summaries only when needed (adds latency)
2. Enable breadcrumbs for database storage
3. Choose appropriate LLM model for cost/quality balance
4. Use table enhancement selectively

## Troubleshooting

### Common Issues

1. **Summaries failing**: Check LLM API keys and model availability
2. **Missing breadcrumbs**: Ensure sections have proper heading levels
3. **Hierarchy issues**: Verify document has clear section structure

### Debug Mode

```bash
marker_single document.pdf --debug --add-summaries
```

This will output detailed processing information for troubleshooting.