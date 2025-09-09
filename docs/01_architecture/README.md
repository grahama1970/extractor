# Extractor Architecture Overview

## System Philosophy

The Extractor is not just a document processing tool - it's a **learning system** that gets smarter with every document. At its core is a revolutionary approach: **Knowledge-First Processing**.

## Core Principles

### 1. Knowledge-First, Not AI-First
Traditional approach: "Ask AI what to do"
Our approach: "Check what worked before, then decide"

Every processing decision:
1. Queries historical patterns in ArangoDB
2. Uses multiple search strategies (BM25, semantic, graph, CLIP)
3. Makes evidence-based decisions
4. Validates against gold standards
5. Learns from the outcome

### 2. Direct Database Integration
- **No abstraction layers**: Processors write AQL queries directly
- **No generic prompts**: Sub-agents use specific, targeted queries
- **Real evidence**: Every decision backed by historical data

Example from table merging:
```aql
FOR doc IN pdf_objects
  FILTER doc.object_type == 'table_merge_pattern'
  LET similarity = BM25(doc.table1_text, @current_table_text)
  FILTER similarity > 0.3
  SORT similarity DESC
  RETURN {
    pattern: doc,
    should_merge: doc.merge_decision,
    reasoning: doc.merge_reasoning
  }
```

### 3. Continuous Learning
- Extracts annotations from PDFs to learn human corrections
- Stores successful patterns in ArangoDB
- Applies learned patterns to future documents
- Each document processed improves the system

### 4. Rigorous Validation
- Gold standard validation at 4 pipeline stages
- 90% accuracy threshold required
- Detailed pipeline reports with metrics
- Fail fast with clear error messages

## Architecture Components

### Core Engine
- **unified_extractor.py**: Main extraction engine with stage validation
- **pipeline_orchestrator.py**: High-level orchestration and CLI
- **pipeline_config.py**: Configuration and processor management

### Knowledge Layer
- **knowledge_aware_base.py**: Base class for knowledge-aware processors
- **arango_tools_worker.py**: Direct ArangoDB interface (no abstractions)
- Pattern storage in ArangoDB with multiple search capabilities

### Processing Pipeline
1. **Annotation Extraction**: Learn from human markup
2. **Enhanced Marker Processing**: Custom processors with validation
3. **Section Organization**: Hierarchical structure building
4. **Advanced Processing**: Cleaning, merging, recovery
5. **LLM Enhancement**: Optional AI when knowledge insufficient
6. **Output Generation**: Multiple formats with validation

### Quality Assurance
- **stage_validator.py**: Validates each pipeline stage
- **Gold standards**: Benchmark files for each stage
- **Suspicious block detection**: Identifies edge cases
- **Pipeline reports**: Detailed processing metrics

## What Makes This Architecture Special

### 1. Evidence-Based Processing
Instead of guessing or asking AI, the system asks: "What did we do with similar content before?"

### 2. Transparent Decision Making
Every decision can be traced back to specific database queries and historical patterns.

### 3. Compound Learning
The system learns from:
- Human annotations in PDFs
- Processing outcomes
- Validation results
- Error patterns

### 4. Specialized Sub-Agents
Not generic AI assistants, but specialized workers with specific queries:
- Table merge decisions based on historical patterns
- Section header validation using learned rules
- Figure/equation classification from visual similarity

## Integration Points

### ArangoDB
- Central knowledge repository
- Stores patterns, decisions, outcomes
- Enables BM25, vector, graph, and CLIP searches
- No ORM or abstraction - direct AQL queries

### Marker-PDF
- Base extraction engine
- Enhanced with custom processors
- Integrated with knowledge queries
- Fallback strategies (Camelot, PyMuPDF)

### LiteLLM
- Unified interface to Claude/Gemini
- Used only when historical knowledge insufficient
- Results fed back into knowledge base

## Current Implementation Status

### ✅ Fully Implemented
- Knowledge-first base architecture
- Direct ArangoDB integration (no abstractions)
- Gold standard validation at all stages
- Annotation extraction and learning
- Custom processors with validation
- CLIP embedding integration
- Table merge knowledge queries
- Section header validation (rejects false positives)

### 🚧 In Development
- pdf_object_identifier_worker
- equation_processor_worker
- form_processor_worker
- image_description_worker

### 📋 Planned Enhancements
- Real-time learning from user corrections
- Cross-document pattern recognition
- Industry-specific knowledge bases
- Distributed knowledge sharing

## Key Files

See individual architecture documents:
- [Knowledge-First Architecture](knowledge_first.md)
- [Pipeline Stages](pipeline_stages.md)
- [Sub-Agent Design](sub_agents.md)
- [Validation System](validation.md)