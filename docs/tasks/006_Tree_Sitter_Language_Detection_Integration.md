# Task 006: Tree-Sitter Language Detection Integration for Code Blocks ⏳ Not Started

**Objective**: Integrate the existing tree-sitter utilities into Marker's code block processing pipeline to automatically detect and set programming language attributes on all code blocks during PDF conversion.

**Requirements**:
1. Automatically detect programming language for all code blocks using tree-sitter
2. Fallback to heuristic detection when tree-sitter fails
3. Support all languages available in tree-sitter-language-pack
4. Set the `language` attribute on `Code` blocks
5. Ensure markdown renderer includes language in code fence blocks
6. Maintain backwards compatibility with manually set languages
7. Add configuration option to enable/disable language detection

## Overview

Currently, Marker has tree-sitter language detection utilities (`tree_sitter_utils.py`) but they are not integrated into the main code block processing pipeline. This task will connect these utilities to the `CodeProcessor` so that all code blocks automatically get their programming language detected and set.

**IMPORTANT**: 
1. Each sub-task MUST include creation of a verification report in `/docs/reports/` with actual command outputs and performance results.
2. Task 8 (Final Verification) enforces MANDATORY iteration on ALL incomplete tasks. The agent MUST continue working until 100% completion is achieved - no partial completion is acceptable.

## Research Summary

Tree-sitter provides robust language detection through syntax parsing, supporting 100+ programming languages. The utilities are already available in Marker but need to be integrated into the processing pipeline.

## MANDATORY Research Process

**CRITICAL REQUIREMENT**: For EACH task, the agent MUST:

1. **Use `perplexity_ask`** to research:
   - Tree-sitter language detection best practices (2024-2025)
   - Performance optimization for syntax parsing
   - Fallback strategies for unknown languages
   - Language detection accuracy benchmarks

2. **Use `WebSearch`** to find:
   - GitHub repositories using tree-sitter for language detection
   - Code block language detection implementations
   - Performance benchmarks for tree-sitter
   - Language heuristic detection algorithms

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
perplexity_ask: "tree-sitter language detection performance optimization 2024"
WebSearch: "site:github.com tree-sitter detect programming language code blocks"
WebSearch: "site:github.com markdown code fence language detection tree-sitter"
```

## Implementation Tasks (Ordered by Priority/Complexity)

### Task 1: Enhance CodeProcessor with Language Detection ⏳ Not Started

**Priority**: HIGH | **Complexity**: MEDIUM | **Impact**: HIGH

**Research Requirements**:
- [ ] Use `perplexity_ask` to find code language detection patterns
- [ ] Use `WebSearch` to find tree-sitter integration examples
- [ ] Search for "code block language detection" implementations
- [ ] Find fallback heuristic detection algorithms
- [ ] Locate performance optimization techniques

**Example Starting Code** (to be found via research):
```python
# Agent MUST use perplexity_ask and WebSearch to find:
# 1. Tree-sitter language detection integration patterns
# 2. Fallback heuristic detection methods
# 3. Performance optimization techniques
# 4. Language confidence scoring
# Example search queries:
# - "site:github.com tree-sitter detect language code block"
# - "programming language detection heuristics 2024"
# - "tree-sitter performance optimization language detection"
```

**Working Starting Code** (if available):
```python
from marker.processors import BaseProcessor
from marker.schema import BlockTypes
from marker.schema.blocks import Code
from marker.services.utils.tree_sitter_utils import extract_code_metadata, get_supported_language

class CodeProcessor(BaseProcessor):
    """
    Enhanced processor for formatting and language detection of code blocks.
    """
    block_types = (BlockTypes.Code, )
    
    def __init__(self, config=None):
        super().__init__(config)
        self.enable_language_detection = self.config.get('enable_language_detection', True)
    
    def __call__(self, document: Document):
        for page in document.pages:
            for block in page.contained_blocks(document, self.block_types):
                self.format_block(document, block)
                if self.enable_language_detection:
                    self.detect_language(block)
```

**Implementation Steps**:
- [ ] 1.1 Modify CodeProcessor class
  - Add `detect_language` method
  - Import tree-sitter utilities
  - Add configuration options
  - Handle existing language attributes

- [ ] 1.2 Implement language detection
  - Call `extract_code_metadata` from tree-sitter utils
  - Handle success/failure cases
  - Store detected language in block
  - Add confidence scoring

- [ ] 1.3 Add fallback heuristics
  - Implement keyword-based detection
  - Check file extensions if available
  - Use statistical analysis
  - Pattern matching for common languages

- [ ] 1.4 Performance optimization
  - Cache detection results
  - Add early exit for obvious languages
  - Batch processing for multiple blocks
  - Timeout handling for complex code

- [ ] 1.5 Error handling
  - Handle tree-sitter failures gracefully
  - Log detection attempts
  - Default to "text" for unknown
  - Preserve manual overrides

- [ ] 1.6 Create tests
  - Test various language detection
  - Verify fallback behavior
  - Check performance metrics
  - Test error scenarios

- [ ] 1.7 Create verification report
- [ ] 1.8 Git commit feature

**Technical Specifications**:
- Detection timeout: 1 second per block
- Minimum confidence: 0.7
- Supported languages: 100+ (from tree-sitter)
- Fallback: Heuristic + keyword matching
- Cache size: 1000 blocks

**Verification Method**:
- Process test PDFs with various code
- Measure detection accuracy
- Check performance metrics
- Verify language attributes set

**CLI Testing Requirements** (MANDATORY FOR ALL TASKS):
- [ ] Execute actual CLI commands, not just unit tests
  - Run `marker convert` with code-heavy PDFs
  - Test language detection toggle
  - Verify markdown output includes languages
  - Test performance impact
- [ ] Test end-to-end functionality
  - Check PDF to markdown conversion
  - Verify code fence languages
  - Test with various file types
  - Check error handling
- [ ] Document all CLI tests in report

**Acceptance Criteria**:
- All code blocks have language detected
- Accuracy >90% for common languages
- Performance impact <5% on conversion
- Fallback works for unknown languages
- Configuration option functional

### Task 2: Create Language Heuristics Module ⏳ Not Started

**Priority**: HIGH | **Complexity**: MEDIUM | **Impact**: MEDIUM

**Research Requirements**:
- [ ] Use `perplexity_ask` to find heuristic detection algorithms
- [ ] Use `WebSearch` to find language pattern databases
- [ ] Search for "programming language keywords" lists
- [ ] Find statistical language detection methods
- [ ] Locate existing heuristic implementations

**Implementation Steps**:
- [ ] 2.1 Create heuristics module
  - Create `marker/processors/utils/language_heuristics.py`
  - Define heuristic detection interface
  - Add pattern databases
  - Include keyword lists

- [ ] 2.2 Implement pattern matching
  - Language-specific keywords
  - Syntax patterns
  - Comment styles
  - String delimiters

- [ ] 2.3 Add statistical analysis
  - Character frequency analysis
  - Token distribution
  - Indentation patterns
  - Line structure analysis

- [ ] 2.4 Create confidence scoring
  - Weight different indicators
  - Combine multiple signals
  - Return confidence percentage
  - Handle ambiguous cases

- [ ] 2.5 Optimize performance
  - Early exit strategies
  - Efficient pattern matching
  - Caching mechanisms
  - Parallel processing

- [ ] 2.6 Create comprehensive tests
  - Test each language
  - Verify edge cases
  - Check performance
  - Test confidence scores

- [ ] 2.7 Create verification report
- [ ] 2.8 Git commit feature

**Technical Specifications**:
- Minimum patterns per language: 10
- Confidence threshold: 0.6
- Max detection time: 100ms
- Languages supported: 50+
- Pattern cache size: 500

### Task 3: Update Markdown Renderer ⏳ Not Started

**Priority**: MEDIUM | **Complexity**: LOW | **Impact**: HIGH

**Research Requirements**:
- [ ] Use `perplexity_ask` to find markdown code fence standards
- [ ] Use `WebSearch` to find renderer implementations
- [ ] Search for "markdown code language" examples
- [ ] Find rendering best practices
- [ ] Locate language mapping standards

**Implementation Steps**:
- [ ] 3.1 Update markdown renderer
  - Modify `convert_code` method
  - Check for language attribute
  - Format code fences correctly
  - Handle missing languages

- [ ] 3.2 Add language mapping
  - Map internal names to markdown
  - Handle language aliases
  - Support common variations
  - Default for unknown

- [ ] 3.3 Test rendering output
  - Verify fence formatting
  - Check language inclusion
  - Test special characters
  - Validate markdown syntax

- [ ] 3.4 Update HTML renderer
  - Add language classes
  - Support syntax highlighting
  - Test HTML output
  - Maintain compatibility

- [ ] 3.5 Create examples
  - Various language outputs
  - Edge case handling
  - Before/after comparisons
  - Documentation

- [ ] 3.6 Create verification report
- [ ] 3.7 Git commit feature

**Technical Specifications**:
- Fence format: ```language
- Default language: "text"
- HTML class: language-{name}
- Escape special characters
- Preserve whitespace

### Task 4: Add Configuration Options ⏳ Not Started

**Priority**: MEDIUM | **Complexity**: LOW | **Impact**: MEDIUM

**Research Requirements**:
- [ ] Use `perplexity_ask` to find configuration patterns
- [ ] Use `WebSearch` to find config schema examples
- [ ] Search for "feature toggle" implementations
- [ ] Find default configuration strategies
- [ ] Locate config validation patterns

**Implementation Steps**:
- [ ] 4.1 Update ParserConfig
  - Add language detection options
  - Set default values
  - Add validation rules
  - Document options

- [ ] 4.2 Add CLI arguments
  - `--detect-code-language` flag
  - `--language-detection-timeout`
  - `--fallback-language`
  - Help text updates

- [ ] 4.3 Update configuration docs
  - Document new options
  - Provide examples
  - Explain performance impact
  - Show use cases

- [ ] 4.4 Test configuration
  - Verify CLI parsing
  - Test config files
  - Check defaults
  - Validate inputs

- [ ] 4.5 Create examples
  - Config file samples
  - CLI usage examples
  - Common scenarios
  - Performance tuning

- [ ] 4.6 Create verification report
- [ ] 4.7 Git commit feature

**Technical Specifications**:
- Default: enabled
- Timeout range: 0.1-5 seconds
- Config key: language_detection
- Validation: type checking
- Documentation: comprehensive

### Task 5: Performance Optimization ⏳ Not Started

**Priority**: LOW | **Complexity**: MEDIUM | **Impact**: MEDIUM

**Research Requirements**:
- [ ] Use `perplexity_ask` to find tree-sitter optimization
- [ ] Use `WebSearch` to find caching strategies
- [ ] Search for "syntax parser performance"
- [ ] Find profiling techniques
- [ ] Locate benchmarking tools

**Implementation Steps**:
- [ ] 5.1 Profile current performance
  - Measure detection times
  - Identify bottlenecks
  - Check memory usage
  - Monitor CPU usage

- [ ] 5.2 Implement caching
  - Cache detection results
  - Store parsed trees
  - LRU cache implementation
  - Persistence options

- [ ] 5.3 Optimize tree-sitter usage
  - Reuse parsers
  - Batch processing
  - Early termination
  - Memory management

- [ ] 5.4 Add performance metrics
  - Detection time tracking
  - Success rate monitoring
  - Cache hit rates
  - Resource usage

- [ ] 5.5 Create benchmarks
  - Various PDF types
  - Different code densities
  - Multiple languages
  - Performance reports

- [ ] 5.6 Create verification report
- [ ] 5.7 Git commit feature

**Technical Specifications**:
- Target: <5% overhead
- Cache size: 1MB
- Max detection time: 1s
- Batch size: 10 blocks
- Memory limit: 100MB

### Task 6: Add Language Statistics ⏳ Not Started

**Priority**: LOW | **Complexity**: LOW | **Impact**: LOW

**Research Requirements**:
- [ ] Use `perplexity_ask` to find document statistics
- [ ] Use `WebSearch` to find metrics examples
- [ ] Search for "code language statistics"
- [ ] Find visualization patterns
- [ ] Locate reporting formats

**Implementation Steps**:
- [ ] 6.1 Create statistics module
  - Track detected languages
  - Count code blocks
  - Calculate confidence
  - Time measurements

- [ ] 6.2 Add to document metadata
  - Language distribution
  - Detection success rate
  - Performance metrics
  - Error counts

- [ ] 6.3 Create reporting
  - Summary statistics
  - Language breakdown
  - Performance report
  - JSON export

- [ ] 6.4 Add CLI output
  - Optional statistics flag
  - Summary display
  - Detailed report
  - Export options

- [ ] 6.5 Create visualizations
  - Language pie chart
  - Confidence histogram
  - Performance graphs
  - Error analysis

- [ ] 6.6 Create verification report
- [ ] 6.7 Git commit feature

**Technical Specifications**:
- Metrics tracked: 10+
- Report format: JSON
- CLI flag: --language-stats
- Visualization: optional
- Export: multiple formats

### Task 7: Documentation and Examples ⏳ Not Started

**Priority**: LOW | **Complexity**: LOW | **Impact**: MEDIUM

**Research Requirements**:
- [ ] Use `perplexity_ask` to find documentation standards
- [ ] Use `WebSearch` to find example structures
- [ ] Search for "feature documentation" templates
- [ ] Find tutorial formats
- [ ] Locate best practices

**Implementation Steps**:
- [ ] 7.1 Create user documentation
  - Feature overview
  - Configuration guide
  - Usage examples
  - Troubleshooting

- [ ] 7.2 Add API documentation
  - Method signatures
  - Parameter descriptions
  - Return values
  - Code examples

- [ ] 7.3 Create tutorials
  - Basic usage
  - Advanced configuration
  - Performance tuning
  - Custom languages

- [ ] 7.4 Add examples
  - Sample PDFs
  - Output comparisons
  - Config files
  - Scripts

- [ ] 7.5 Update existing docs
  - README updates
  - Configuration guide
  - API reference
  - FAQ sections

- [ ] 7.6 Create verification report
- [ ] 7.7 Git commit feature

**Technical Specifications**:
- Documentation: Markdown
- Examples: working code
- Tutorials: step-by-step
- Coverage: comprehensive
- Updates: all relevant docs

### Task 8: Completion Verification and Iteration ⏳ Not Started

**Priority**: CRITICAL | **Complexity**: LOW | **Impact**: CRITICAL

**Implementation Steps**:
- [ ] 8.1 Review all task reports
  - Read all reports in `/docs/reports/006_*`
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
  - Test all language detection
  - Verify configuration options
  - Confirm documentation accuracy

- [ ] 8.6 Create final summary report
  - Create `/docs/reports/006_final_summary.md`
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
| `marker convert` | Convert PDF with language detection | `marker convert input.pdf -o output.md` | Markdown with language tags |
| `marker convert --no-detect-language` | Disable language detection | `marker convert input.pdf --no-detect-language` | Plain code blocks |
| `code_processor.detect_language()` | Detect language of code block | `processor.detect_language(block)` | Sets block.language |
| `language_heuristics.detect()` | Fallback detection | `detect(code_text)` | {"language": "python", "confidence": 0.9} |
| Task Matrix | Verify completion | Review `/docs/reports/006_*` | 100% completion required |

## Version Control Plan

- **Initial Commit**: Create task-006-start tag before implementation
- **Feature Commits**: After each major feature
- **Integration Commits**: After component integration
- **Test Commits**: After test suite completion
- **Final Tag**: Create task-006-complete after all tests pass

## Resources

**Python Packages**:
- tree-sitter: Core parser
- tree-sitter-language-pack: Language support
- rapidfuzz: String matching

**Documentation**:
- [Tree-sitter Documentation](https://tree-sitter.github.io/tree-sitter/)
- [Language Detection Papers](https://arxiv.org/search/?query=programming+language+detection)
- [Marker Documentation](https://github.com/VikParuchuri/marker)

**Example Implementations**:
- [GitHub Linguist](https://github.com/github/linguist)
- [Pygments Language Detection](https://github.com/pygments/pygments)
- [Tree-sitter Language Detection Examples](https://github.com/tree-sitter/tree-sitter/tree/master/cli/src)

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
`/docs/reports/006_task_[SUBTASK]_[feature_name].md`

Example content for a report:
```markdown
# Task 6.1: CodeProcessor Language Detection Verification Report

## Summary
Enhanced CodeProcessor with automatic language detection using tree-sitter

## Research Findings
- Found tree-sitter integration pattern in: [link]
- Heuristic fallback example from: [link]
- Performance optimization from: [article]

## Real Command Outputs
```bash
$ marker convert test.pdf -o test.md
Processing test.pdf...
Detecting code languages...
- Python: 5 blocks (95% confidence)
- JavaScript: 3 blocks (88% confidence)
- Unknown: 1 block (fallback)
Conversion complete: test.md
Time: 4.2s
```

## Actual Performance Results
| Operation | Metric | Result | Target | Status |
|-----------|--------|--------|--------|--------|
| Detection overhead | Time | 0.8s | <1s | PASS |
| Language accuracy | Accuracy | 92% | >90% | PASS |

## Working Code Example
```python
# Actual tested code
from marker.processors.code import CodeProcessor

processor = CodeProcessor(config={"enable_language_detection": True})
processor(document)
# All code blocks now have language attribute set
```

## Verification Evidence
- CLI command executed successfully
- Languages correctly detected
- Performance within targets
- Fallback working

## Limitations Discovered
- Exotic languages need better patterns
- Large code blocks slightly slower

## External Resources Used
- [Tree-sitter Guide](link) - Integration pattern
- [Linguist](link) - Heuristic patterns
- [Performance Blog](link) - Optimization tips
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