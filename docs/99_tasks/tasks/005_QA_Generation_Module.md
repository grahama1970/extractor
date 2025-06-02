# Task 005: Q&A Generation Module for LoRA Fine-tuning ⏳ Not Started

**Objective**: Create a comprehensive Q&A generation module within Marker that generates high-quality question-answer pairs from document hierarchies, including reversal questions, multi-hop reasoning, and cross-section relationships with citation validation.

**Requirements**:
1. Generate multiple types of Q&A pairs (factual, reversal curse, multi-hop, hierarchical)
2. Use temperature variation for questions (diverse) and low temperature for answers (factual)
3. Validate all answers with citation checking using RapidFuzz (97% partial match)
4. Create relational Q&A pairs combining text, tables, and images
5. Support async batch processing with progress tracking
6. Use LiteLLM with vertex_ai/gemini-2.5-flash-preview-04-17
7. Export in OpenAI message format for LoRA fine-tuning

## Overview

This module will post-process Marker Document objects to generate synthetic Q&A pairs for LoRA fine-tuning. It will leverage section hierarchies, semantic relationships, and cross-references to create comprehensive training data that includes reversal questions to address the reversal curse in LLMs.

**IMPORTANT**: 
1. Each sub-task MUST include creation of a verification report in `/docs/reports/` with actual command outputs and performance results.
2. Task 8 (Final Verification) enforces MANDATORY iteration on ALL incomplete tasks. The agent MUST continue working until 100% completion is achieved - no partial completion is acceptable.

## Research Summary

Based on research into the reversal curse, multi-hop Q&A generation, and citation validation, the module will implement proven techniques from projects like MulQG and HotpotQA while addressing the reversal curse limitations identified in recent research.

## MANDATORY Research Process

**CRITICAL REQUIREMENT**: For EACH task, the agent MUST:

1. **Use `perplexity_ask`** to research:
   - Q&A generation best practices for LoRA fine-tuning (2024-2025)
   - Reversal curse mitigation strategies
   - Multi-hop question generation techniques
   - Citation validation approaches

2. **Use `WebSearch`** to find:
   - GitHub repositories with Q&A generation code
   - RapidFuzz citation validation examples
   - OpenAI format exporters for fine-tuning
   - Async batch processing patterns

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
perplexity_ask: "synthetic Q&A generation for LoRA fine-tuning reversal curse 2024"
WebSearch: "site:github.com rapidfuzz citation validation llm training data"
WebSearch: "site:github.com multi-hop question generation hierarchical documents"
```

## Implementation Tasks (Ordered by Priority/Complexity)

### Task 1: Core Q&A Generator Implementation ⏳ Not Started

**Priority**: HIGH | **Complexity**: HIGH | **Impact**: HIGH

**Research Requirements**:
- [ ] Use `perplexity_ask` to find Q&A generation patterns for fine-tuning
- [ ] Use `WebSearch` to find production Q&A generators on GitHub
- [ ] Search for "reversal curse mitigation" examples
- [ ] Find multi-hop question generation strategies
- [ ] Locate OpenAI format conversion code

**Example Starting Code** (to be found via research):
```python
# Agent MUST use perplexity_ask and WebSearch to find:
# 1. Q&A generation with temperature control
# 2. Reversal question generation patterns
# 3. Multi-hop question creation
# 4. Citation validation with RapidFuzz
# Example search queries:
# - "site:github.com synthetic question generation LoRA temperature control"
# - "rapidfuzz citation validation 97 percent match"
# - "reversal curse question answer generation LLM"
```

**Working Starting Code** (if available):
```python
# Basic structure based on research
from marker.processors.base import BaseProcessor
from litellm import acompletion
from rapidfuzz import fuzz
import asyncio
from tqdm.asyncio import tqdm

class QAGenerator(BaseProcessor):
    def __init__(self, config=None):
        super().__init__(config)
        self.model = "vertex_ai/gemini-2.5-flash-preview-04-17"
        self.question_temp = 0.8
        self.answer_temp = 0.1
    
    async def generate_qa_pair(self, section, context):
        # Generate diverse questions
        # Generate factual answers
        # Create reversal questions
        # Validate citations
        pass
```

**Implementation Steps**:
- [ ] 1.1 Create infrastructure
  - Create `/marker/processors/qa_generator/` directory
  - Create `__init__.py` files
  - Create main `qa_generator.py` file
  - Add dependencies (litellm, rapidfuzz) to pyproject.toml

- [ ] 1.2 Implement core Q&A generation
  - Define Q&A types enum (factual, reversal, multi-hop, hierarchical)
  - Implement temperature-controlled generation
  - Create reversal question generator
  - Add citation validation with RapidFuzz
  - Include logging and monitoring

- [ ] 1.3 Add section processing
  - Extract content from section blocks
  - Combine text, tables, and images
  - Preserve section hierarchy context
  - Handle nested subsections
  - Generate contextual Q&A pairs

- [ ] 1.4 Create prompt templates
  - Factual question prompts
  - Reversal question prompts
  - Multi-hop question prompts
  - Answer generation prompts
  - Validation prompts

- [ ] 1.5 Implement citation validation
  - Extract potential citations from answers
  - Use RapidFuzz partial_ratio with 97% threshold
  - Link citations to source blocks
  - Store citation metadata
  - Handle validation failures

- [ ] 1.6 Create async batch processing
  - Implement asyncio.gather for parallel processing
  - Add tqdm progress bar
  - Handle rate limiting
  - Implement error recovery
  - Add memory management

- [ ] 1.7 Add tests and validation
  - Create test documents with known content
  - Generate Q&A pairs
  - Validate citation accuracy
  - Test reversal questions
  - Verify temperature effects

- [ ] 1.8 Git commit feature

**Technical Specifications**:
- Temperature: 0.8 for questions, 0.1 for answers
- Citation threshold: 97% RapidFuzz partial match
- Batch size: Configurable (default 10)
- Async concurrency: 5 simultaneous requests
- Memory limit: Track GPU/CPU usage

**Verification Method**:
- Generate Q&A pairs from test documents
- Validate citation accuracy
- Test reversal question quality
- Measure generation speed
- Check memory usage

**CLI Testing Requirements** (MANDATORY FOR ALL TASKS):
- [ ] Execute actual CLI commands, not just unit tests
  - Run `marker qa-generate` with test PDFs
  - Test temperature variations
  - Verify citation validation
  - Test batch processing
  - Monitor progress bars
- [ ] Test end-to-end functionality
  - Start with Document object
  - Generate all Q&A types
  - Validate citations
  - Export to correct format
- [ ] Document all CLI tests in report

**Acceptance Criteria**:
- All Q&A types generated successfully
- Citation validation at 97% accuracy
- Reversal questions properly formed
- Async batch processing working
- Progress tracking functional

### Task 2: Semantic Search Integration ⏳ Not Started

**Priority**: HIGH | **Complexity**: MEDIUM | **Impact**: HIGH

**Research Requirements**:
- [ ] Use `perplexity_ask` to find section similarity algorithms
- [ ] Use `WebSearch` to find ArangoDB semantic search examples
- [ ] Search for "cross-document section matching" patterns
- [ ] Find embedding-based section comparison code
- [ ] Locate multi-hop relationship extraction

**Implementation Steps**:
- [ ] 2.1 Create search adapter
  - Interface with ArangoDB search capabilities
  - Implement section embedding generation
  - Add similarity scoring
  - Create fallback for missing ArangoDB

- [ ] 2.2 Implement related section finder
  - Find semantically similar sections
  - Identify parent-child relationships
  - Discover cross-references
  - Calculate relationship scores
  - Store relationship metadata

- [ ] 2.3 Add multi-hop logic
  - Create relationship graphs
  - Find multi-hop paths
  - Generate connecting questions
  - Validate path coherence
  - Score path reliability

- [ ] 2.4 Create cross-section Q&A
  - Combine related sections
  - Generate bridging questions
  - Create comparison questions
  - Add contradiction detection
  - Include relationship context

- [ ] 2.5 Add caching layer
  - Cache section embeddings
  - Store relationship scores
  - Implement TTL logic
  - Add cache invalidation
  - Monitor cache performance

- [ ] 2.6 Create verification report
- [ ] 2.7 Git commit feature

**Technical Specifications**:
- Embedding model: Use existing Marker embeddings
- Similarity threshold: 0.75 cosine similarity
- Max relationship depth: 3 hops
- Cache size: 1000 section pairs
- Fallback: Local embeddings if no ArangoDB

**Verification Method**:
- Test section similarity scoring
- Validate multi-hop paths
- Check cache hit rates
- Measure search performance

### Task 3: Table and Image Integration ⏳ Not Started

**Priority**: MEDIUM | **Complexity**: MEDIUM | **Impact**: HIGH

**Research Requirements**:
- [ ] Use `perplexity_ask` to find table Q&A generation
- [ ] Use `WebSearch` to find image description Q&A examples
- [ ] Search for "multimodal question generation" patterns
- [ ] Find table-text alignment code
- [ ] Locate image-text Q&A generators

**Implementation Steps**:
- [ ] 3.1 Create table Q&A generator
  - Extract table structure
  - Generate table-specific questions
  - Create cell reference questions
  - Add aggregation questions
  - Include comparison questions

- [ ] 3.2 Implement image Q&A
  - Use existing image descriptions
  - Generate description-based questions
  - Create visual reasoning questions
  - Add image-text alignment
  - Handle missing descriptions

- [ ] 3.3 Add multimodal fusion
  - Combine table-text content
  - Merge image-text context
  - Create cross-modal questions
  - Add reference validation
  - Include layout context

- [ ] 3.4 Create specialized prompts
  - Table interpretation prompts
  - Image description prompts
  - Multimodal reasoning prompts
  - Reference generation prompts
  - Validation prompts

- [ ] 3.5 Add quality checks
  - Validate table references
  - Check image descriptions
  - Verify cross-references
  - Score question quality
  - Filter low-quality pairs

- [ ] 3.6 Create verification report
- [ ] 3.7 Git commit feature

**Technical Specifications**:
- Table formats: Support all Marker table types
- Image types: All supported by Marker
- Question diversity: Min 3 per table/image
- Quality threshold: 0.7 confidence
- Reference accuracy: 95%

### Task 4: Export Formatter ⏳ Not Started

**Priority**: MEDIUM | **Complexity**: LOW | **Impact**: HIGH

**Research Requirements**:
- [ ] Use `perplexity_ask` to find OpenAI fine-tuning formats
- [ ] Use `WebSearch` to find LoRA training data formats
- [ ] Search for "conversation format fine-tuning" examples
- [ ] Find JSONL exporters for LLM training
- [ ] Locate format validation tools

**Implementation Steps**:
- [ ] 4.1 Create format converter
  - Implement OpenAI message format
  - Add system/user/assistant roles
  - Include thinking/reasoning steps
  - Format metadata properly
  - Support multiple formats

- [ ] 4.2 Add export renderers
  - Create JSONL renderer
  - Add CSV export option
  - Implement Parquet format
  - Include HuggingFace format
  - Support custom formats

- [ ] 4.3 Implement validation
  - Check format compliance
  - Validate required fields
  - Verify JSON structure
  - Test with training tools
  - Add error reporting

- [ ] 4.4 Create batch export
  - Handle large datasets
  - Split into train/val/test
  - Add stratified sampling
  - Include metadata files
  - Generate statistics

- [ ] 4.5 Add compression
  - Compress large exports
  - Create archive structure
  - Include documentation
  - Add checksums
  - Support streaming

- [ ] 4.6 Create verification report
- [ ] 4.7 Git commit feature

**Technical Specifications**:
- Primary format: OpenAI conversation JSONL
- Compression: gzip for large files
- Split ratio: 80/10/10 train/val/test
- Metadata: Include generation params
- Validation: Schema compliance

### Task 5: Performance Optimization ⏳ Not Started

**Priority**: LOW | **Complexity**: MEDIUM | **Impact**: MEDIUM

**Research Requirements**:
- [ ] Use `perplexity_ask` to find async LLM optimization
- [ ] Use `WebSearch` to find batching strategies
- [ ] Search for "LiteLLM performance tuning"
- [ ] Find memory optimization patterns
- [ ] Locate GPU utilization tools

**Implementation Steps**:
- [ ] 5.1 Optimize batching
  - Dynamic batch sizing
  - Memory-aware batching
  - Request coalescing
  - Priority queuing
  - Load balancing

- [ ] 5.2 Add caching layers
  - Prompt caching
  - Response caching
  - Embedding caching
  - Relationship caching
  - TTL management

- [ ] 5.3 Implement monitoring
  - Request latency tracking
  - Token usage monitoring
  - Memory profiling
  - GPU utilization
  - Error rate tracking

- [ ] 5.4 Add rate limiting
  - API rate management
  - Backoff strategies
  - Quota tracking
  - Cost monitoring
  - Fallback handling

- [ ] 5.5 Memory optimization
  - Streaming responses
  - Garbage collection
  - Buffer management
  - Cache eviction
  - Memory pooling

- [ ] 5.6 Create verification report
- [ ] 5.7 Git commit feature

**Technical Specifications**:
- Target latency: <2s per Q&A pair
- Memory limit: 8GB peak usage
- Batch efficiency: >80% GPU utilization
- Cache hit rate: >60%
- Error rate: <1%

### Task 6: CLI Integration ⏳ Not Started

**Priority**: MEDIUM | **Complexity**: LOW | **Impact**: MEDIUM

**Research Requirements**:
- [ ] Use `perplexity_ask` to find CLI best practices
- [ ] Use `WebSearch` to find Typer examples
- [ ] Search for "progress bar CLI Python"
- [ ] Find config file parsers
- [ ] Locate CLI testing patterns

**Implementation Steps**:
- [ ] 6.1 Create CLI commands
  - `marker qa-generate` main command
  - Add subcommands for types
  - Include config options
  - Add output formats
  - Support batch mode

- [ ] 6.2 Add progress tracking
  - Integrate tqdm bars
  - Show generation stats
  - Display time estimates
  - Track token usage
  - Monitor errors

- [ ] 6.3 Implement config files
  - YAML configuration
  - JSON config support
  - Environment variables
  - Default templates
  - Profile management

- [ ] 6.4 Add validation
  - Input file checks
  - Output path validation
  - Config verification
  - Model availability
  - Resource checks

- [ ] 6.5 Create help docs
  - Command documentation
  - Example usage
  - Config templates
  - Troubleshooting
  - Best practices

- [ ] 6.6 Create verification report
- [ ] 6.7 Git commit feature

**Technical Specifications**:
- CLI framework: Typer
- Config formats: YAML, JSON
- Progress: tqdm with async
- Output: Multiple formats
- Logging: Structured logs

### Task 7: Documentation and Examples ⏳ Not Started

**Priority**: LOW | **Complexity**: LOW | **Impact**: MEDIUM

**Research Requirements**:
- [ ] Use `perplexity_ask` to find documentation standards
- [ ] Use `WebSearch` to find example repositories
- [ ] Search for "LLM fine-tuning examples"
- [ ] Find tutorial structures
- [ ] Locate best practices guides

**Implementation Steps**:
- [ ] 7.1 Create user guide
  - Getting started
  - Configuration guide
  - Q&A type explanations
  - Output format docs
  - Troubleshooting

- [ ] 7.2 Add code examples
  - Basic usage
  - Advanced configuration
  - Custom processors
  - Integration examples
  - Performance tuning

- [ ] 7.3 Create tutorials
  - PDF to Q&A pipeline
  - Multi-document processing
  - Custom question types
  - Fine-tuning workflow
  - Result analysis

- [ ] 7.4 Add API docs
  - Class documentation
  - Method signatures
  - Parameter descriptions
  - Return values
  - Exception handling

- [ ] 7.5 Create samples
  - Sample PDFs
  - Generated Q&A sets
  - Config templates
  - Export examples
  - Analysis scripts

- [ ] 7.6 Create verification report
- [ ] 7.7 Git commit feature

**Technical Specifications**:
- Doc format: Markdown
- API docs: Sphinx/mkdocs
- Examples: Jupyter notebooks
- Samples: Real PDF data
- Coverage: >90% of features

### Task 8: Completion Verification and Iteration ⏳ Not Started

**Priority**: CRITICAL | **Complexity**: LOW | **Impact**: CRITICAL

**Implementation Steps**:
- [ ] 8.1 Review all task reports
  - Read all reports in `/docs/reports/005_*`
  - Create checklist of incomplete features
  - Identify failed tests or missing functionality
  - Document specific issues preventing completion
  - Prioritize fixes by impact

- [ ] 8.2 Create task completion matrix
  - Build comprehensive status table
  - Mark each sub-task as COMPLETE/INCOMPLETE
  - List specific failures for incomplete tasks
  - Identify blocking dependencies
  - Calculate overall completion percentage

- [ ] 8.3 Iterate on incomplete tasks
  - Return to first incomplete task
  - Fix identified issues
  - Re-run validation tests
  - Update verification report
  - Continue until task passes

- [ ] 8.4 Re-validate completed tasks
  - Ensure no regressions from fixes
  - Run integration tests
  - Verify cross-task compatibility
  - Update affected reports
  - Document any new limitations

- [ ] 8.5 Final comprehensive validation
  - Run all CLI commands
  - Execute performance benchmarks
  - Test all Q&A types
  - Verify export formats
  - Confirm citation validation

- [ ] 8.6 Create final summary report
  - Create `/docs/reports/005_final_summary.md`
  - Include completion matrix
  - Document all working features
  - List any remaining limitations
  - Provide usage recommendations

- [ ] 8.7 Mark task complete only if ALL sub-tasks pass
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
| `marker qa-generate` | Generate Q&A from document | `marker qa-generate input.pdf -o qa.jsonl` | Q&A pairs in JSONL |
| `marker qa-generate --type reversal` | Generate reversal questions | `marker qa-generate input.pdf --type reversal` | Reversal Q&A pairs |
| `marker qa-generate --validate` | With citation validation | `marker qa-generate input.pdf --validate` | Validated Q&A pairs |
| `marker qa-batch` | Batch process documents | `marker qa-batch *.pdf -o dataset/` | Multiple Q&A files |
| Task Matrix | Verify completion | Review `/docs/reports/005_*` | 100% completion required |

## Version Control Plan

- **Initial Commit**: Create task-005-start tag before implementation
- **Feature Commits**: After each major feature
- **Integration Commits**: After component integration
- **Test Commits**: After test suite completion
- **Final Tag**: Create task-005-complete after all tests pass

## Resources

**Python Packages**:
- litellm: LLM integration
- rapidfuzz: Citation validation
- asyncio: Async processing
- tqdm: Progress bars
- pydantic: Data validation

**Documentation**:
- [LiteLLM Docs](https://docs.litellm.ai/)
- [RapidFuzz Documentation](https://rapidfuzz.github.io/RapidFuzz/)
- [OpenAI Fine-tuning Format](https://platform.openai.com/docs/guides/fine-tuning)
- [Vertex AI Documentation](https://cloud.google.com/vertex-ai/docs)

**Example Implementations**:
- [MulQG - Multi-hop Question Generation](https://github.com/HLTCHKUST/MulQG)
- [Synthetic Q&A Dataset Generator](https://github.com/nalinrajendran/synthetic-LLM-QA-dataset-generator)
- [Unsupervised Multi-hop Q&A](https://github.com/teacherpeterpan/Unsupervised-Multi-hop-QA)

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
# Task 5.1: Core Q&A Generator Verification Report

## Summary
Implemented temperature-controlled Q&A generation with reversal questions

## Research Findings
- Found reversal curse mitigation in: [link]
- Temperature control patterns from: [link]
- RapidFuzz citation validation: [example]

## Real Command Outputs
```bash
$ marker qa-generate test.pdf -o output.jsonl
Generating Q&A pairs...
Progress: 100%|████████| 50/50 [00:32<00:00,  1.56it/s]
Generated: 50 Q&A pairs
Reversal: 25 pairs
Citations validated: 48/50 (96%)
Output: output.jsonl
```

## Actual Performance Results
| Operation | Metric | Result | Target | Status |
|-----------|--------|--------|--------|--------|
| Q&A Generation | Speed | 1.56/s | >1/s | PASS |
| Citation Match | Accuracy | 96% | >95% | PASS |

## Working Code Example
```python
# Actual tested code
from marker.processors.qa_generator import QAGenerator

generator = QAGenerator(config={"model": "vertex_ai/gemini-2.5-flash"})
qa_pairs = await generator.generate(document)
print(f"Generated: {len(qa_pairs)} pairs")
# Output:
# Generated: 50 pairs
```

## Verification Evidence
- CLI command executed successfully
- Citation validation working
- Temperature variation confirmed
- Async processing functional

## Limitations Discovered
- Rate limiting at 100 requests/minute
- Memory usage spikes with large documents

## External Resources Used
- [RapidFuzz Examples](link) - Citation matching
- [LiteLLM Async Guide](link) - Batching
- [OpenAI Format Spec](link) - Export format
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