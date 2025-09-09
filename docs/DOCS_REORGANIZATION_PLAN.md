# Documentation Reorganization Plan

## Current State Analysis

The docs directory currently contains 50+ files with mixed organizational patterns:
- Weekly summaries (WEEK1-5)
- Feature-specific docs (ANNOTATION_*, TABLE_*, etc.)
- Architecture docs mixed with implementation summaries
- Code review documents scattered throughout
- Deprecated/outdated content mixed with current docs

## Proposed New Structure

```
docs/
├── 01_architecture/          # Core architecture docs
│   ├── README.md            # Architecture overview
│   ├── knowledge_first.md   # Knowledge-first architecture
│   ├── pipeline_stages.md   # Pipeline stage details
│   ├── sub_agents.md        # Sub-agent architecture
│   └── validation.md        # Gold standard validation
│
├── 02_implementation/        # Implementation details
│   ├── processors/          # Processor documentation
│   │   ├── knowledge_aware.md
│   │   ├── section_header.md
│   │   ├── table_processing.md
│   │   └── llm_processors.md
│   ├── integration/         # Integration patterns
│   │   ├── arangodb.md
│   │   ├── litellm.md
│   │   └── marker_pdf.md
│   └── learning/           # Learning systems
│       ├── annotation_learning.md
│       └── pattern_recognition.md
│
├── 03_guides/              # User and developer guides
│   ├── quick_start.md      # Getting started
│   ├── configuration.md    # Pipeline configuration
│   ├── troubleshooting.md  # Common issues
│   └── api_reference.md    # API documentation
│
├── 04_progress/            # Development progress
│   ├── completed/          # Completed features
│   │   ├── gold_standard_validation.md
│   │   ├── knowledge_first_implementation.md
│   │   └── annotation_extraction.md
│   ├── in_progress/        # Current work
│   │   └── sub_agent_creation.md
│   └── planned/            # Future work
│       └── native_extractors.md
│
├── 05_testing/             # Testing and validation
│   ├── gold_standards.md   # Gold standard documentation
│   ├── test_results/       # Test execution results
│   └── benchmarks.md       # Performance benchmarks
│
├── 06_legacy/              # Deprecated/historical docs
│   ├── weekly_summaries/   # WEEK1-5 summaries
│   ├── old_architecture/   # Previous designs
│   └── deprecated/         # No longer relevant
│
└── README.md               # Docs overview and navigation
```

## Files to Move/Reorganize

### To 01_architecture/
- COMPLETE_PIPELINE_ARCHITECTURE.md → pipeline_stages.md
- KNOWLEDGE_FIRST_ARCHITECTURE.md → knowledge_first.md
- SUBAGENT_ARCHITECTURE_COMPLETE.md → sub_agents.md
- GOLD_STANDARD_VALIDATION_IMPLEMENTATION.md → validation.md

### To 02_implementation/processors/
- SECTION_HEADER_PATTERN_INTEGRATION.md
- TABLE_PROCESSING_PIPELINE_ANALYSIS.md
- PROCESSOR_IMPROVEMENT_PLAN.md
- BERT_SECTION_HEADER_PROPOSAL.md

### To 02_implementation/integration/
- REAL_ARANGODB_IMPLEMENTATION.md
- LITELLM_INTEGRATION.md
- MARKER_PDF_FLOW_ANALYSIS.md

### To 02_implementation/learning/
- ANNOTATION_SYSTEM_ARCHITECTURE.md
- ANNOTATION_PIPELINE_RESULTS.md
- AGENT_SELF_LEARNING_ANALYSIS.md

### To 04_progress/completed/
- GOLD_STANDARD_VALIDATION_IMPLEMENTATION.md
- KNOWLEDGE_FIRST_IMPLEMENTATION_SUMMARY.md
- BHT_EXTRACTION_FIX_SUMMARY.md
- TABLE_PIPELINE_INTEGRATION_COMPLETE.md

### To 06_legacy/weekly_summaries/
- WEEK1_IMPLEMENTATION_SUMMARY.md
- WEEK2_ARCHITECTURE_SUMMARY.md
- WEEK3_TYPE_CONFUSION_SUMMARY.md
- WEEK4_BOUNDARY_VALIDATION_SUMMARY.md
- WEEK5_CONFIDENCE_STANDARDS_SUMMARY.md

### To 06_legacy/deprecated/
- MCP_TO_SUBAGENT_CONVERSION_PLAN.md (outdated approach)
- EDGE_CASES_AND_MISSING_LOGIC.md (issues now fixed)
- PIPELINE_IMPLEMENTATION_GAPS.md (gaps now filled)

## New Documentation to Create

### 01_architecture/README.md
- Overview of the complete extraction system
- Key architectural decisions
- System components and interactions

### 03_guides/quick_start.md
- Installation instructions
- Basic usage examples
- Common workflows

### 03_guides/configuration.md
- Pipeline configuration options
- Processor settings
- Performance tuning

### 05_testing/gold_standards.md
- How to create gold standards
- Validation thresholds
- Quality metrics

## Implementation Steps

1. Create new directory structure
2. Move files to appropriate locations
3. Update file references in code
4. Create new overview documents
5. Add navigation README in each directory
6. Archive truly deprecated content
7. Update main README.md with new docs structure