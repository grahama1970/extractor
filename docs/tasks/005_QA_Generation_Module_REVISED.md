# Task 005: Q&A Generation Module - ArangoDB Hybrid Approach ⏳ Not Started

**Objective**: Create a Q&A generation system that leverages ArangoDB's graph relationships to generate high-quality question-answer pairs from documents processed by Marker, including reversal questions, multi-hop reasoning, and cross-section relationships with citation validation.

**Requirements**:
1. Extend ArangoDB with Q&A collections and schemas
2. Build relationship-aware Q&A generator in ArangoDB
3. Generate multiple types of Q&A pairs (factual, reversal curse, multi-hop, hierarchical)
4. Use temperature variation for questions (diverse) and low temperature for answers (factual)
5. Validate all answers with citation checking using ArangoDB's search (RapidFuzz 97% partial match)
6. Create minimal Marker processor for triggering Q&A generation
7. Support async batch processing with progress tracking
8. Use LiteLLM with vertex_ai/gemini-2.5-flash-preview-04-17
9. Export in OpenAI message format for LoRA fine-tuning with Unsloth

## Overview

This module implements a hybrid approach where:
- Marker processes PDFs into structured documents
- ArangoDB stores documents with relationships
- Q&A generation leverages the relationship graph
- Marker has a minimal processor to trigger the pipeline

The Q&A generator will be primarily in ArangoDB, utilizing its graph traversal and search capabilities for intelligent question generation.

**IMPORTANT**: 
1. Each sub-task MUST include creation of a verification report in `/docs/reports/` with actual command outputs and performance results.
2. Task 9 (Final Verification) enforces MANDATORY iteration on ALL incomplete tasks. The agent MUST continue working until 100% completion is achieved - no partial completion is acceptable.

## Research Summary

Based on analysis of both projects, ArangoDB has sophisticated graph and relationship capabilities that can enhance Q&A quality through multi-hop reasoning and semantic relationships. The hybrid approach maximizes both projects' strengths.

## MANDATORY Research Process

**CRITICAL REQUIREMENT**: For EACH task, the agent MUST:

1. **Use `perplexity_ask`** to research:
   - Graph-based Q&A generation techniques (2024-2025)
   - ArangoDB best practices for relationship traversal
   - Reversal curse mitigation in graph contexts
   - Multi-hop reasoning with knowledge graphs

2. **Use `WebSearch`** to find:
   - GitHub repos with graph-based Q&A generation
   - ArangoDB schema design for Q&A systems
   - LiteLLM + ArangoDB integration examples
   - Unsloth fine-tuning data formats

3. **Document all findings** in task reports:
   - Links to source repositories
   - Code snippets that work
   - Performance characteristics
   - Integration patterns

4. **DO NOT proceed without research**:
   - No theoretical implementations
   - No guessing at patterns
   - Must have real code examples
   - Must verify current best practices

Example Research Queries:
```
perplexity_ask: "knowledge graph Q&A generation ArangoDB 2024"
WebSearch: "site:github.com arangodb question answer generation graph traversal"
WebSearch: "site:github.com multi-hop reasoning knowledge graph"
```

## Implementation Tasks (Ordered by Priority/Complexity)

### Task 1: ArangoDB Q&A Schema Design ⏳ Not Started

**Priority**: HIGH | **Complexity**: MEDIUM | **Impact**: HIGH

**Research Requirements**:
- [ ] Use `perplexity_ask` to find Q&A schemas for graph databases
- [ ] Use `WebSearch` to find ArangoDB collection best practices
- [ ] Search for "question answer graph schema" examples
- [ ] Find edge collection patterns for Q&A
- [ ] Locate metadata standards for training data

**Example Starting Code** (to be found via research):
```python
# Agent MUST use perplexity_ask and WebSearch to find:
# 1. Graph database Q&A schemas
# 2. ArangoDB collection design patterns
# 3. Edge collection for Q&A relationships
# 4. Metadata structure for fine-tuning
# Example search queries:
# - "site:github.com arangodb schema question answer"
# - "knowledge graph Q&A collection design"
# - "fine-tuning metadata schema arangodb"
```

**Working Starting Code** (if available):
```python
# Q&A collections schema
qa_pairs_schema = {
    "_key": "qa_001",
    "question": "What is the relationship between...",
    "thinking": "Chain of thought reasoning...",
    "answer": "Based on the document...",
    "metadata": {
        "type": "relationship",
        "difficulty": "medium",
        "temperature": {"question": 0.8, "answer": 0.1},
        "source_sections": ["sec_123", "sec_456"],
        "relationship_ids": ["rel_789"],
        "confidence": 0.95,
        "reversal_of": None  # For reversal questions
    }
}

qa_relationships_schema = {
    "_from": "qa_pairs/qa_001",
    "_to": "document_objects/text_123",
    "relationship_type": "SOURCED_FROM",
    "confidence": 0.95
}
```

**Implementation Steps**:
- [ ] 1.1 Create Q&A collections in ArangoDB
  - Design qa_pairs collection schema
  - Design qa_relationships edge collection
  - Create qa_validation collection for tracking
  - Add appropriate indexes

- [ ] 1.2 Implement data models
  - Create Pydantic models for Q&A pairs
  - Add validation for required fields
  - Include metadata structures
  - Support for reversal tracking

- [ ] 1.3 Create migration scripts
  - Schema creation scripts
  - Index creation for performance
  - Sample data insertion
  - Rollback procedures

- [ ] 1.4 Add Q&A to existing renderer
  - Extend ArangoDBRenderer for Q&A
  - Handle Q&A relationships
  - Preserve source references
  - Support batch operations

- [ ] 1.5 Create verification tests
  - Test schema creation
  - Validate relationships
  - Check index performance
  - Verify data integrity

- [ ] 1.6 Create verification report
- [ ] 1.7 Git commit feature

**Technical Specifications**:
- Collections: qa_pairs, qa_relationships, qa_validation
- Indexes: Hash on doc_id, type, difficulty
- Relationships: SOURCED_FROM, REVERSAL_OF, VALIDATES
- Schema version: 1.0

**Verification Method**:
- Create test collections
- Insert sample Q&A data
- Query performance tests
- Relationship traversal tests

### Task 2: Relationship-Aware Q&A Generator ⏳ Not Started

**Priority**: HIGH | **Complexity**: HIGH | **Impact**: HIGH

**Research Requirements**:
- [ ] Use `perplexity_ask` to find graph-based Q&A generation
- [ ] Use `WebSearch` to find ArangoDB graph traversal patterns
- [ ] Search for "multi-hop question generation" code
- [ ] Find relationship type to question mapping
- [ ] Locate temperature control examples

**Implementation Steps**:
- [ ] 2.1 Create Q&A generator class
  - Initialize with ArangoDB connection
  - Configure LiteLLM client
  - Set temperature parameters
  - Add progress tracking

- [ ] 2.2 Implement relationship traversal
  - Query content relationships
  - Group by relationship type
  - Extract connected elements
  - Build context windows

- [ ] 2.3 Generate questions by type
  - Factual from single elements
  - Relationship-based from edges
  - Multi-hop from graph paths
  - Hierarchical from structure

- [ ] 2.4 Add reversal generation
  - Create inverse Q&A pairs
  - Track original references
  - Maintain context consistency
  - Validate reversals

- [ ] 2.5 Implement answer generation
  - Low temperature (0.1) for accuracy
  - Include thinking process
  - Add source citations
  - Validate against content

- [ ] 2.6 Create async batch processor
  - Use asyncio.gather
  - Add tqdm progress bar
  - Handle rate limiting
  - Implement retries

- [ ] 2.7 Create verification report
- [ ] 2.8 Git commit feature

**Technical Specifications**:
- LLM: vertex_ai/gemini-2.5-flash-preview-04-17
- Question temperature: 0.8
- Answer temperature: 0.1
- Batch size: 10 concurrent
- Timeout: 30s per Q&A

### Task 3: Citation Validation System ⏳ Not Started

**Priority**: HIGH | **Complexity**: MEDIUM | **Impact**: HIGH

**Research Requirements**:
- [ ] Use `perplexity_ask` to find citation validation techniques
- [ ] Use `WebSearch` to find RapidFuzz + ArangoDB examples
- [ ] Search for "answer validation knowledge graph"
- [ ] Find partial matching algorithms
- [ ] Locate confidence scoring methods

**Implementation Steps**:
- [ ] 3.1 Create validation module
  - Integrate RapidFuzz
  - Configure 97% threshold
  - Support partial matching
  - Add confidence scoring

- [ ] 3.2 Implement ArangoDB search
  - Use existing text search
  - Add fuzzy matching layer
  - Query source documents
  - Return match locations

- [ ] 3.3 Add validation pipeline
  - Extract answer segments
  - Search in source content
  - Calculate match scores
  - Flag low-confidence pairs

- [ ] 3.4 Create citation metadata
  - Store match locations
  - Track confidence scores
  - Link to source blocks
  - Add validation status

- [ ] 3.5 Implement bulk validation
  - Batch process Q&A pairs
  - Parallel validation
  - Progress tracking
  - Error handling

- [ ] 3.6 Create validation report
- [ ] 3.7 Git commit feature

**Technical Specifications**:
- RapidFuzz threshold: 97% partial_ratio
- Validation batch size: 100
- Parallel workers: 5
- Confidence levels: high/medium/low
- Source tracking: block IDs

### Task 4: Multi-hop Q&A Generation ⏳ Not Started

**Priority**: MEDIUM | **Complexity**: HIGH | **Impact**: HIGH

**Research Requirements**:
- [ ] Use `perplexity_ask` to find multi-hop reasoning
- [ ] Use `WebSearch` to find graph path algorithms
- [ ] Search for "knowledge graph traversal Q&A"
- [ ] Find path ranking methods
- [ ] Locate context aggregation patterns

**Implementation Steps**:
- [ ] 4.1 Create path finder
  - Implement graph traversal
  - Find multi-hop paths
  - Rank by relevance
  - Limit path length

- [ ] 4.2 Build context aggregator
  - Collect path elements
  - Merge related content
  - Preserve relationships
  - Order by relevance

- [ ] 4.3 Generate complex questions
  - Create templates by path type
  - Vary complexity levels
  - Include reasoning steps
  - Add prerequisite info

- [ ] 4.4 Implement answer synthesis
  - Combine multiple sources
  - Show reasoning chain
  - Include path evidence
  - Validate completeness

- [ ] 4.5 Add difficulty scoring
  - Calculate based on hops
  - Consider concept complexity
  - Assess reasoning depth
  - Tag difficulty level

- [ ] 4.6 Create verification report
- [ ] 4.7 Git commit feature

**Technical Specifications**:
- Max path length: 3 hops
- Context window: 4000 tokens
- Difficulty levels: easy/medium/hard
- Path ranking: confidence-based
- Aggregation method: weighted merge

### Task 5: Export and Format Module ⏳ Not Started

**Priority**: MEDIUM | **Complexity**: LOW | **Impact**: HIGH

**Research Requirements**:
- [ ] Use `perplexity_ask` to find Unsloth data formats
- [ ] Use `WebSearch` to find OpenAI fine-tuning schemas
- [ ] Search for "LoRA training data format"
- [ ] Find JSONL best practices
- [ ] Locate train/val/test splitting

**Implementation Steps**:
- [ ] 5.1 Create formatters
  - OpenAI conversation format
  - JSONL exporter
  - CSV alternative
  - Metadata inclusion

- [ ] 5.2 Implement data splitter
  - 80/10/10 train/val/test
  - Stratified by type
  - Balanced difficulty
  - Preserve relationships

- [ ] 5.3 Add compression
  - Gzip large files
  - Create archives
  - Include manifest
  - Generate checksums

- [ ] 5.4 Create export pipeline
  - Query Q&A pairs
  - Apply formatting
  - Split datasets
  - Compress output

- [ ] 5.5 Add validation
  - Check format compliance
  - Verify completeness
  - Test with Unsloth
  - Generate statistics

- [ ] 5.6 Create verification report
- [ ] 5.7 Git commit feature

**Technical Specifications**:
- Primary format: OpenAI JSONL
- Compression: gzip
- Split ratio: 80/10/10
- Batch export: 1000 Q&A/file
- Validation: schema compliance

### Task 6: Marker Integration Processor ⏳ Not Started

**Priority**: MEDIUM | **Complexity**: LOW | **Impact**: MEDIUM

**Research Requirements**:
- [ ] Use `perplexity_ask` to find Marker processor patterns
- [ ] Use `WebSearch` to find async processor examples
- [ ] Search for "marker custom processor"
- [ ] Find ArangoDB client patterns
- [ ] Locate pipeline integration

**Implementation Steps**:
- [ ] 6.1 Create QA processor
  - Extend BaseProcessor
  - Add ArangoDB config
  - Configure async client
  - Set processing options

- [ ] 6.2 Implement trigger logic
  - Detect document completion
  - Send to ArangoDB
  - Trigger Q&A generation
  - Wait for completion

- [ ] 6.3 Add progress tracking
  - Monitor generation status
  - Update progress bar
  - Handle timeouts
  - Report completion

- [ ] 6.4 Create CLI integration
  - Add qa-generate command
  - Configure options
  - Support batch mode
  - Enable monitoring

- [ ] 6.5 Add error handling
  - Catch connection errors
  - Handle generation failures
  - Implement retries
  - Log issues

- [ ] 6.6 Create verification report
- [ ] 6.7 Git commit feature

**Technical Specifications**:
- Processor type: async
- Timeout: 5 minutes/document
- Retry attempts: 3
- Progress update: 1s interval
- CLI command: marker qa-generate

### Task 7: Performance Optimization ⏳ Not Started

**Priority**: LOW | **Complexity**: MEDIUM | **Impact**: MEDIUM

**Research Requirements**:
- [ ] Use `perplexity_ask` to find ArangoDB optimization
- [ ] Use `WebSearch` to find async performance patterns
- [ ] Search for "graph query optimization"
- [ ] Find caching strategies
- [ ] Locate batch processing examples

**Implementation Steps**:
- [ ] 7.1 Optimize queries
  - Add query profiling
  - Create optimal indexes
  - Use query caching
  - Implement pagination

- [ ] 7.2 Add caching layers
  - Cache embeddings
  - Store LLM responses
  - Cache relationships
  - TTL management

- [ ] 7.3 Implement monitoring
  - Track query times
  - Monitor memory usage
  - Log token consumption
  - Performance metrics

- [ ] 7.4 Optimize batching
  - Dynamic batch sizing
  - Memory-aware processing
  - Parallel execution
  - Load balancing

- [ ] 7.5 Add benchmarks
  - Create test suite
  - Measure throughput
  - Track latencies
  - Compare approaches

- [ ] 7.6 Create verification report
- [ ] 7.7 Git commit feature

**Technical Specifications**:
- Target: <2s per Q&A pair
- Cache TTL: 1 hour
- Batch size: adaptive
- Memory limit: 8GB
- Query timeout: 10s

### Task 8: Documentation and Testing ⏳ Not Started

**Priority**: LOW | **Complexity**: LOW | **Impact**: MEDIUM

**Research Requirements**:
- [ ] Use `perplexity_ask` to find documentation standards
- [ ] Use `WebSearch` to find test suite examples
- [ ] Search for "integration test patterns"
- [ ] Find API documentation tools
- [ ] Locate example repositories

**Implementation Steps**:
- [ ] 8.1 Create user guide
  - Installation steps
  - Configuration guide
  - Usage examples
  - Troubleshooting

- [ ] 8.2 Add API documentation
  - Document schemas
  - API endpoints
  - Query examples
  - Response formats

- [ ] 8.3 Create test suite
  - Unit tests
  - Integration tests
  - Performance tests
  - End-to-end tests

- [ ] 8.4 Add examples
  - Sample documents
  - Generated Q&A sets
  - Config templates
  - Query examples

- [ ] 8.5 Create tutorials
  - Quick start guide
  - Advanced usage
  - Optimization tips
  - Best practices

- [ ] 8.6 Create verification report
- [ ] 8.7 Git commit feature

**Technical Specifications**:
- Test coverage: >80%
- Doc format: Markdown
- Examples: Jupyter notebooks
- API docs: OpenAPI/Swagger
- Tutorials: Step-by-step

### Task 9: Completion Verification and Iteration ⏳ Not Started

**Priority**: CRITICAL | **Complexity**: LOW | **Impact**: CRITICAL

**Implementation Steps**:
- [ ] 9.1 Review all task reports
  - Read all reports in `/docs/reports/005_*`
  - Create checklist of incomplete features
  - Identify failed tests or missing functionality
  - Document specific issues preventing completion
  - Prioritize fixes by impact

- [ ] 9.2 Create task completion matrix
  - Build comprehensive status table
  - Mark each sub-task as COMPLETE/INCOMPLETE
  - List specific failures for incomplete tasks
  - Identify blocking dependencies
  - Calculate overall completion percentage

- [ ] 9.3 Iterate on incomplete tasks
  - Return to first incomplete task
  - Fix identified issues
  - Re-run validation tests
  - Update verification report
  - Continue until task passes

- [ ] 9.4 Re-validate completed tasks
  - Ensure no regressions from fixes
  - Run integration tests
  - Verify cross-task compatibility
  - Update affected reports
  - Document any new limitations

- [ ] 9.5 Final comprehensive validation
  - Run all CLI commands
  - Execute performance benchmarks
  - Test complete pipeline
  - Verify export formats
  - Confirm Unsloth compatibility

- [ ] 9.6 Create final summary report
  - Create `/docs/reports/005_final_summary.md`
  - Include completion matrix
  - Document all working features
  - List any remaining limitations
  - Provide usage recommendations

- [ ] 9.7 Mark task complete only if ALL sub-tasks pass
  - Verify 100% task completion
  - Confirm all reports show success
  - Ensure no critical issues remain
  - Get final approval
  - Update task status to ✅ Complete

**Technical Specifications**:
- Zero tolerance for incomplete features
- Mandatory iteration until completion
- All tests must pass
- All reports must verify success
- No theoretical completions allowed

**Verification Method**:
- Task completion matrix showing 100%
- All reports confirming success
- Rich table with final status

**Acceptance Criteria**:
- ALL tasks marked COMPLETE
- ALL verification reports show success
- ALL tests pass without issues
- ALL features work in production
- NO incomplete functionality

**CRITICAL ITERATION REQUIREMENT**:
This task CANNOT be marked complete until ALL previous tasks are verified as COMPLETE with passing tests and working functionality. The agent MUST continue iterating on incomplete tasks until 100% completion is achieved.

## Usage Table

| Command / Function | Description | Example Usage | Expected Output |
|-------------------|-------------|---------------|-----------------|
| `arangodb qa-generate` | Generate Q&A from document | `arangodb qa-generate --doc-id paper_2024` | Q&A pairs created |
| `marker qa-generate` | Process PDF and generate Q&A | `marker qa-generate input.pdf` | Q&A export path |
| `arangodb qa-export` | Export Q&A for training | `arangodb qa-export --format jsonl` | Training data file |
| `arangodb qa-validate` | Validate Q&A citations | `arangodb qa-validate --threshold 0.97` | Validation report |
| Task Matrix | Verify completion | Review `/docs/reports/005_*` | 100% completion |

## Version Control Plan

- **Initial Commit**: Create task-005-start tag before implementation
- **Feature Commits**: After each major feature
- **Integration Commits**: After component integration
- **Test Commits**: After test suite completion
- **Final Tag**: Create task-005-complete after all tests pass

## Resources

**Python Packages**:
- python-arango: ArangoDB client
- litellm: LLM integration
- rapidfuzz: Citation validation
- asyncio: Async processing
- tqdm: Progress bars
- pydantic: Data validation

**Documentation**:
- [ArangoDB Documentation](https://www.arangodb.com/docs/)
- [LiteLLM Docs](https://docs.litellm.ai/)
- [RapidFuzz Documentation](https://rapidfuzz.github.io/RapidFuzz/)
- [Unsloth Documentation](https://github.com/unslothai/unsloth)

**Example Implementations**:
- [Knowledge Graph Q&A](https://github.com/topics/knowledge-graph-question-answering)
- [ArangoDB Examples](https://github.com/arangodb/arangodb)
- [Multi-hop Reasoning](https://github.com/topics/multi-hop-reasoning)

## Progress Tracking

- Start date: TBD
- Current phase: Planning
- Expected completion: TBD
- Completion criteria: All features working, tests passing, documented

## Report Documentation Requirements

Each sub-task MUST have a corresponding verification report in `/docs/reports/` following these requirements:

### Report Structure:
Each report must include:
1. **Task Summary**: Brief description of what was implemented
2. **Research Findings**: Links to repos, code examples found, best practices discovered
3. **Non-Mocked Results**: Real command outputs and performance metrics
4. **Performance Metrics**: Actual benchmarks with real data
5. **Code Examples**: Working code with verified output
6. **Verification Evidence**: Logs or metrics proving functionality
7. **Limitations Found**: Any discovered issues or constraints
8. **External Resources Used**: All GitHub repos, articles, and examples referenced

### Report Naming Convention:
`/docs/reports/005_task_[SUBTASK]_[feature_name].md`

Example content for a report:
```markdown
# Task 5.1: ArangoDB Q&A Schema Verification Report

## Summary
Implemented Q&A collections and relationships in ArangoDB

## Research Findings
- Found graph Q&A schema in: [link]
- Best practices from: [link]
- Edge collection patterns: [article]

## Real Command Outputs
```bash
$ arangodb qa-generate --doc-id test_doc
Creating Q&A collections...
Generating Q&A pairs...
Progress: 100%|████████| 50/50 [00:45<00:00,  1.11it/s]
Generated: 50 Q&A pairs
Citations validated: 48/50 (96%)
Export path: /data/qa/test_doc_qa.jsonl
```

## Actual Performance Results
| Operation | Metric | Result | Target | Status |
|-----------|--------|--------|--------|--------|
| Schema creation | Time | 0.5s | <1s | PASS |
| Q&A generation | Speed | 1.11/s | >1/s | PASS |
| Citation validation | Accuracy | 96% | >95% | PASS |

## Working Code Example
```python
# Actual tested code
from arangodb.qa import QAGenerator

generator = QAGenerator(db, litellm_client)
qa_pairs = await generator.generate_qa_pairs("doc_123")
print(f"Generated: {len(qa_pairs)} pairs")
# Output:
# Generated: 50 pairs
```

## Verification Evidence
- Collections created successfully
- Indexes performing well
- Q&A generation working
- Citation validation functional

## Limitations Discovered
- Large documents need chunking
- Rate limiting on LLM calls

## External Resources Used
- [ArangoDB Schema Design](link) - Collection structure
- [Graph Q&A Generation](link) - Algorithm patterns
- [Multi-hop Examples](link) - Path traversal
```

## Context Management

When context length is running low during implementation, use the following approach to compact and resume work:

1. Issue the `/compact` command to create a concise summary of current progress
2. The summary will include:
   - Completed tasks and key functionality
   - Current task in progress with specific subtask
   - Known issues or blockers
   - Next steps to resume work
   - Key decisions made or patterns established

---

This task document serves as the comprehensive implementation guide. Update status emojis and checkboxes as tasks are completed to maintain progress tracking.