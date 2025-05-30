# Task 008: CLI Commands Comprehensive Testing ⏳ Not Started

**Objective**: Systematically test and validate all CLI commands documented in the LLM validation CLI usage guide to ensure they function as expected and provide proper output.

**Requirements**:
1. Test each CLI command from the usage guide with proper parameters
2. Validate command functionality and outputs against expected behavior
3. Document actual command execution results and any discrepancies
4. Create workarounds or fixes for any non-working commands
5. Generate a comprehensive report of command successes and failures

## Overview

The LLM validation CLI provides a wide range of commands for validating LLM outputs, processing multimodal content, and managing validation workflows. This task ensures all documented CLI commands actually work as expected, and provides accurate documentation for users.

**IMPORTANT**: 
1. Each sub-task MUST include creation of a verification report in `/docs/reports/` with actual command outputs and performance results.
2. Task 7 (Final Verification) enforces MANDATORY iteration on ALL incomplete tasks. The agent MUST continue working until 100% completion is achieved - no partial completion is acceptable.

## Research Summary

The CLI commands documentation includes examples for validation, multimodal processing, streaming, parallel processing, and more. Testing these commands requires checking parameter compatibility, expected outputs, and error handling.

## MANDATORY Research Process

**CRITICAL REQUIREMENT**: For EACH task, the agent MUST:

1. **Use `perplexity_ask`** to research:
   - Current best practices (2024-2025)
   - Production implementation patterns  
   - Common pitfalls and solutions
   - Performance optimization techniques

2. **Use `WebSearch`** to find:
   - GitHub repositories with working code
   - Real production examples
   - Popular library implementations
   - Benchmark comparisons

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
perplexity_ask: "best practices for LLM validation CLI tools 2024"
WebSearch: "site:github.com CLI for LLM validation tools"
```

## Implementation Tasks (Ordered by Priority/Complexity)

### Task 1: Test Basic Validation Commands ⏳ Not Started

**Priority**: HIGH | **Complexity**: LOW | **Impact**: HIGH

**Research Requirements**:
- [ ] Use `perplexity_ask` to find LLM validation patterns
- [ ] Use `WebSearch` to find CLI validation tools
- [ ] Search GitHub for LLM validation implementations
- [ ] Locate benchmark validation commands

**Implementation Steps**:
- [ ] 1.1 Test simple validation command
  - Execute `python -m marker.llm_call.cli.app validate "Generate a simple greeting"`
  - Document output format and response
  - Verify validation success criteria
  - Test with different prompts
  - Note any errors or unexpected behavior

- [ ] 1.2 Test validation with retry attempts
  - Execute command with `--max-retries` parameter
  - Verify retry behavior works as expected
  - Document retry logs and outcomes
  - Test with invalid inputs to trigger retries
  - Check max retries limit enforcement

- [ ] 1.3 Test validation with different models
  - Test with Gemini model parameter
  - Test with Claude model parameter
  - Test with GPT-4 model parameter
  - Document model-specific behaviors
  - Compare performance and validation results

- [ ] 1.4 Test output file saving
  - Execute command with `--output` parameter
  - Verify file is created correctly
  - Check output file format and content
  - Test with different file formats
  - Validate file permissions and locations

- [ ] 1.5 Create verification report
  - Create `/docs/reports/008_task_1_basic_validation.md`
  - Document actual commands and results
  - Include screenshots of outputs
  - Show working commands and parameters
  - Add evidence of functionality

**Verification Method**:
- Run each command and capture output
- Document command execution time
- Verify parameter handling
- Check error messages for invalid inputs
- Compare output to documentation

**Acceptance Criteria**:
- All basic validation commands work
- Output format matches documentation
- Parameters are handled correctly
- Error handling is appropriate
- Documentation is accurate

### Task 2: Test Corpus Validation Commands ⏳ Not Started

**Priority**: HIGH | **Complexity**: MEDIUM | **Impact**: HIGH

**Research Requirements**:
- [ ] Use `perplexity_ask` to find corpus validation techniques
- [ ] Use `WebSearch` to find corpus validation tools
- [ ] Search GitHub for corpus validation implementations
- [ ] Locate benchmark corpus validation examples

**Implementation Steps**:
- [ ] 2.1 Test comma-separated corpus validation
  - Execute `python corpus_validator_cli.py "What is the largest city in Texas?" --corpus "London,Houston,New York City"`
  - Verify correct validation logic
  - Test with valid and invalid responses
  - Document output format
  - Check error handling

- [ ] 2.2 Test file-based corpus validation
  - Create test file with allowed values
  - Execute command with `--corpus-file` parameter
  - Verify file loading works correctly
  - Test with various file formats
  - Document any file parsing issues

- [ ] 2.3 Test case-sensitive validation
  - Execute command with `--case-sensitive` flag
  - Verify case sensitivity works as expected
  - Test with mixed-case inputs
  - Document behavior differences
  - Check edge cases

- [ ] 2.4 Test custom response validation
  - Execute command with `--response` parameter
  - Verify custom response handling
  - Test with valid and invalid responses
  - Document validation results
  - Compare to simulated responses

- [ ] 2.5 Test JSON output format
  - Execute command with `--json` flag
  - Verify JSON output structure
  - Validate JSON schema
  - Test JSON parsing
  - Document JSON format

- [ ] 2.6 Create verification report
  - Create `/docs/reports/008_task_2_corpus_validation.md`
  - Document actual commands and results
  - Include sample outputs
  - Show working commands and parameters
  - Add evidence of functionality

**Verification Method**:
- Run each corpus validation command
- Test with various inputs and parameters
- Verify validation logic correctness
- Check output formats
- Document any discrepancies

**Acceptance Criteria**:
- All corpus validation commands work
- Validation logic is correct
- Parameters are handled properly
- Output formats match documentation
- Error handling is appropriate

### Task 3: Test Code and Content Validation Commands ⏳ Not Started

**Priority**: HIGH | **Complexity**: MEDIUM | **Impact**: HIGH

**Research Requirements**:
- [ ] Use `perplexity_ask` to find code validation techniques
- [ ] Use `WebSearch` to find content quality validation tools
- [ ] Search GitHub for code syntax validation implementations
- [ ] Locate example validation workflows

**Implementation Steps**:
- [ ] 3.1 Test Python syntax validation
  - Execute `python -m marker.llm_call.cli.app validate "Write a Python function to check if a number is prime" --validators python_syntax`
  - Verify syntax validation works
  - Test with valid and invalid Python code
  - Document validation results
  - Check error reporting

- [ ] 3.2 Test code language detection
  - Execute command with `code_language` validator
  - Test detection with multiple languages
  - Verify language detection accuracy
  - Document detection results
  - Test edge cases

- [ ] 3.3 Test code completeness validation
  - Execute command with `code_completeness` validator
  - Test with complete and incomplete code
  - Verify completeness criteria
  - Document validation results
  - Check error reporting

- [ ] 3.4 Test content quality validation
  - Execute command with `content_quality` validator
  - Test with various content quality levels
  - Verify quality metrics
  - Document validation results
  - Test parameter customization

- [ ] 3.5 Test multiple validators together
  - Execute command with multiple validators
  - Verify combined validation logic
  - Test interaction between validators
  - Document combined results
  - Check priority handling

- [ ] 3.6 Create verification report
  - Create `/docs/reports/008_task_3_code_content_validation.md`
  - Document actual commands and results
  - Include validation outputs
  - Show working commands and parameters
  - Add evidence of functionality

**Verification Method**:
- Run each validation command
- Test with various input types
- Verify validation criteria
- Check validator interactions
- Document validator behavior

**Acceptance Criteria**:
- All code and content validators work
- Validation criteria are correctly applied
- Multiple validators interact properly
- Output formats match documentation
- Error handling is appropriate

### Task 4: Test Multimodal Processing Commands ⏳ Not Started

**Priority**: HIGH | **Complexity**: HIGH | **Impact**: HIGH

**Research Requirements**:
- [ ] Use `perplexity_ask` to find multimodal processing techniques
- [ ] Use `WebSearch` to find image processing CLI tools
- [ ] Search GitHub for document processing implementations
- [ ] Locate example multimodal validation workflows

**Implementation Steps**:
- [ ] 4.1 Test basic image processing
  - Execute `python -m marker.llm_call.cli.app process-image` command
  - Test with sample images
  - Verify image processing workflow
  - Document processing results
  - Check output formats

- [ ] 4.2 Test multiple image analysis
  - Execute command for multiple image processing
  - Test with different image types
  - Verify batch processing
  - Document processing results
  - Check performance

- [ ] 4.3 Test document with images processing
  - Execute command for document processing
  - Test with PDF containing images
  - Verify image extraction
  - Document processing results
  - Check integration with document workflow

- [ ] 4.4 Test OCR quality validation
  - Execute command for OCR validation
  - Test with text-heavy images
  - Verify OCR quality metrics
  - Document validation results
  - Check confidence thresholds

- [ ] 4.5 Test chart data extraction
  - Execute command for chart data extraction
  - Test with chart images
  - Verify data extraction accuracy
  - Document extraction results
  - Check data structure

- [ ] 4.6 Create verification report
  - Create `/docs/reports/008_task_4_multimodal_processing.md`
  - Document actual commands and results
  - Include processing outputs
  - Show working commands and parameters
  - Add evidence of functionality

**Verification Method**:
- Run each multimodal command
- Test with various image and document types
- Verify processing accuracy
- Check output quality
- Document processing time

**Acceptance Criteria**:
- All multimodal commands work
- Image processing is accurate
- Document processing is correct
- Output formats match documentation
- Performance is acceptable

### Task 5: Test Advanced Processing Features ⏳ Not Started

**Priority**: MEDIUM | **Complexity**: HIGH | **Impact**: MEDIUM

**Research Requirements**:
- [ ] Use `perplexity_ask` to find streaming response implementations
- [ ] Use `WebSearch` to find parallel processing patterns
- [ ] Search GitHub for validation chaining examples
- [ ] Locate pipeline validation implementations

**Implementation Steps**:
- [ ] 5.1 Test streaming responses
  - Execute command with `--stream` parameter
  - Verify streaming behavior
  - Test token-by-token streaming
  - Document streaming performance
  - Check streaming formats

- [ ] 5.2 Test parallel processing
  - Execute command for parallel validation
  - Test with multiple workers
  - Verify parallelism benefits
  - Document performance improvements
  - Check resource usage

- [ ] 5.3 Test validation chains
  - Execute command for sequential validation chain
  - Test conditional validation
  - Verify chain execution
  - Document chain results
  - Check validation dependencies

- [ ] 5.4 Test complex validation strategies
  - Execute command for custom validation rules
  - Test ensemble validation
  - Verify strategy implementation
  - Document strategy results
  - Check strategy flexibility

- [ ] 5.5 Test debugging and profiling tools
  - Execute command with `--debug` parameter
  - Test tracing and inspection
  - Verify debugging information
  - Document debugging output
  - Check profiling metrics

- [ ] 5.6 Create verification report
  - Create `/docs/reports/008_task_5_advanced_features.md`
  - Document actual commands and results
  - Include performance metrics
  - Show working commands and parameters
  - Add evidence of functionality

**Verification Method**:
- Run each advanced command
- Test performance characteristics
- Verify advanced features
- Check resource utilization
- Document feature behavior

**Acceptance Criteria**:
- All advanced features work
- Performance benefits are measurable
- Features interact correctly
- Output formats match documentation
- Resource usage is reasonable

### Task 6: Test Environment and Integration Features ⏳ Not Started

**Priority**: MEDIUM | **Complexity**: MEDIUM | **Impact**: MEDIUM

**Research Requirements**:
- [ ] Use `perplexity_ask` to find environment configuration patterns
- [ ] Use `WebSearch` to find CLI integration techniques
- [ ] Search GitHub for webhook implementation examples
- [ ] Locate database integration patterns

**Implementation Steps**:
- [ ] 6.1 Test environment setup
  - Create and use environment file
  - Execute command with environment variables
  - Verify environment loading
  - Document environment effects
  - Check variable precedence

- [ ] 6.2 Test model configuration
  - Create model configuration file
  - Execute command with model config
  - Verify model settings
  - Document configuration effects
  - Check parameter overrides

- [ ] 6.3 Test API and service integrations
  - Configure API keys if possible
  - Test proxy configuration
  - Verify service connections
  - Document integration behavior
  - Check error handling

- [ ] 6.4 Test utility commands
  - Execute list-validators command
  - Test describe-validator command
  - Verify information accuracy
  - Document command outputs
  - Check help information

- [ ] 6.5 Test configuration management
  - Create and use config files
  - Execute command with config
  - Verify configuration loading
  - Document configuration effects
  - Check parameter precedence

- [ ] 6.6 Create verification report
  - Create `/docs/reports/008_task_6_environment_integration.md`
  - Document actual commands and results
  - Include configuration examples
  - Show working commands and parameters
  - Add evidence of functionality

**Verification Method**:
- Run each configuration command
- Test integration features
- Verify environment handling
- Check configuration management
- Document feature behavior

**Acceptance Criteria**:
- All environment features work
- Configuration management is correct
- Integrations function properly
- Output formats match documentation
- Error handling is appropriate

### Task 7: Completion Verification and Iteration ⏳ Not Started

**Priority**: CRITICAL | **Complexity**: LOW | **Impact**: CRITICAL

**Implementation Steps**:
- [ ] 7.1 Review all task reports
  - Read all reports in `/docs/reports/008_task_*`
  - Create checklist of incomplete features
  - Identify failed tests or missing functionality
  - Document specific issues preventing completion
  - Prioritize fixes by impact

- [ ] 7.2 Create command execution matrix
  - Build comprehensive status table
  - Mark each command as WORKING/NOT WORKING
  - List specific failures for broken commands
  - Identify blocking dependencies
  - Calculate overall success percentage

- [ ] 7.3 Iterate on failed commands
  - Return to first failed command
  - Fix identified issues
  - Re-run command tests
  - Update verification report
  - Continue until command works

- [ ] 7.4 Re-validate working commands
  - Ensure no regressions from fixes
  - Run integration tests
  - Verify cross-command compatibility
  - Update affected reports
  - Document any new limitations

- [ ] 7.5 Final comprehensive validation
  - Run all working CLI commands
  - Execute performance measurements
  - Test all documented variants
  - Verify documentation accuracy
  - Confirm all features work together

- [ ] 7.6 Create final summary report
  - Create `/docs/reports/008_final_summary.md`
  - Include command execution matrix
  - Document all working commands
  - List any remaining limitations
  - Provide usage recommendations

- [ ] 7.7 Mark task complete only if ALL commands pass or are documented with workarounds
  - Verify command success matrix
  - Confirm all reports show success or workarounds
  - Ensure no critical issues remain
  - Get final approval
  - Update task status to ✅ Complete

**Technical Specifications**:
- Zero tolerance for undocumented command failures
- Mandatory iteration until completion
- All tests must pass or have documented workarounds
- All reports must verify success or explain limitations
- No theoretical completions allowed

**Verification Method**:
- Command execution matrix showing results
- All reports confirming success or workarounds
- Rich table with final status
- Actual command outputs

**Acceptance Criteria**:
- ALL commands marked WORKING or have DOCUMENTED WORKAROUND
- ALL verification reports show success or limitations
- ALL tests pass without unexpected issues
- ALL features work as documented or have clear workarounds
- NO undocumented failures

**CRITICAL ITERATION REQUIREMENT**:
This task CANNOT be marked complete until ALL previous tasks are verified as COMPLETE with passing tests and working functionality or documented workarounds. The agent MUST continue iterating on incomplete tasks until 100% completion is achieved.

## Usage Table

| Command Group | Example Command | Expected Output | Status |
|---------------|----------------|-----------------|--------|
| Basic Validation | `python -m marker.llm_call.cli.app validate "Generate a greeting"` | Validation result | TBD |
| Corpus Validation | `python corpus_validator_cli.py "What is the capital of France?" --corpus "London,Houston,New York City"` | Validation failure | TBD |
| Code Validation | `python -m marker.llm_call.cli.app validate "Write a Python function" --validators python_syntax` | Syntax validation result | TBD |
| Multimodal | `python -m marker.llm_call.cli.app process-image --image "path/to/image.png"` | Image processing result | TBD |
| Advanced Features | `python -m marker.llm_call.cli.app validate-chain --prompt "Generate research paper"` | Chain validation result | TBD |
| Utility | `python -m marker.llm_call.cli.app list-validators` | List of available validators | TBD |
| Command Matrix | Verify all in `/docs/reports/008_task_*` | 100% completion or workarounds | TBD |

## Resources

**Python Packages**:
- marker-llm: LLM validation
- litellm: LLM integration
- rich: Terminal formatting
- typer: CLI interface

**Documentation**:
- [Marker Documentation](https://github.com/VikParuchuri/marker)
- [LiteLLM Documentation](https://docs.litellm.ai/)
- [Typer Documentation](https://typer.tiangolo.com/)
- [Rich Documentation](https://rich.readthedocs.io/)

**Example Implementations**:
- [CLI Usage Guide](/home/graham/workspace/experiments/marker/marker/llm_call/examples/cli_usage_guide.md)
- [Corpus Validator CLI](/home/graham/workspace/experiments/marker/corpus_validator_cli.py)

## Progress Tracking

- Start date: TBD
- Current phase: Planning
- Expected completion: TBD
- Completion criteria: All commands working or documented with workarounds

## Report Documentation Requirements

Each sub-task MUST have a corresponding verification report in `/docs/reports/` following these requirements:

### Report Structure:
Each report must include:
1. **Task Summary**: Brief description of tested commands
2. **Research Findings**: Links to repos, code examples found, best practices discovered
3. **Command Execution Results**: Actual command outputs and behaviors
4. **Performance Metrics**: Command execution times and resource usage
5. **Working Examples**: Commands that work as expected
6. **Failed Commands**: Commands that don't work with error output
7. **Workarounds**: Alternative approaches for failed commands
8. **Limitations Found**: Any discovered issues or constraints
9. **Command Status Matrix**: Table showing each command's status

### Report Naming Convention:
`/docs/reports/008_task_[SUBTASK]_[command_group].md`

Example content for a report:
```markdown
# Task 8.1: Basic Validation Commands Verification Report

## Summary
[What commands were tested and key findings]

## Research Findings
- Found pattern X in repo: [link]
- Best practice Y from: [link]
- CLI implementation Z from: [article]

## Real Command Outputs
```bash
$ python -m marker.llm_call.cli.app validate "Generate a greeting"
Running validation...
Validation complete.
Result: VALID
```

## Performance Results
| Command | Execution Time | Memory Usage | Status |
|---------|----------------|--------------|--------|
| Basic validate | 1.2s | 120MB | WORKING |
| Validate with retries | 3.5s | 150MB | WORKING |

## Working Examples
- `python -m marker.llm_call.cli.app validate "Generate a greeting"`
- `python -m marker.llm_call.cli.app validate "Generate a greeting" --max-retries 3`

## Failed Commands
- `python -m marker.llm_call.cli.app validate-xyz "Generate a greeting"`
  Error: Unknown command "validate-xyz"

## Workarounds
- For command X, use alternative command Y
- For parameter Z, use workaround ABC

## Limitations Discovered
- Streaming not supported for some validators
- Performance issues with large inputs

## Command Status Matrix
| Command | Status | Error/Issue | Workaround |
|---------|--------|-------------|------------|
| validate | WORKING | None | N/A |
| validate with retries | WORKING | None | N/A |
| validate-xyz | FAILED | Unknown command | Use validate instead |
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