# Task 033: CLI-Based Module Communication System with Claude Code Agents ⏳ Not Started

**Objective**: Implement a streamlined module communication system that enables Marker and ArangoDB modules to communicate, request changes, and adapt to each other's interfaces using CLI commands, Claude Code agents, and file-based message exchange.

**Requirements**:
1. Create CLI command system for inter-module communication between Marker and ArangoDB
2. Implement standardized JSON message format for module communication
3. Develop Claude Code integration mechanisms for each module to interpret and act upon messages
4. Create file-based message exchange system with designated message directories
5. Implement customized system prompts for module-specific Claude instances
6. Implement validation and error handling for module communications
7. Develop testing framework to verify message exchange and processing
8. Create comprehensive documentation of the communication protocol

## Overview

The Marker ecosystem consists of multiple modules (primarily Marker and ArangoDB) that need to communicate, adapt to interface changes, and coordinate functionality. Currently, these modules operate in silos, requiring manual intervention to modify interfaces and adapt to changes. This task implements a unified communication system using CLI commands, Claude Code agents, and file-based messaging to enable modules to communicate needs and implement required changes autonomously.

**IMPORTANT**: 
1. Each sub-task MUST include creation of a verification report in `/docs/reports/` with actual command outputs and performance results.
2. Task 8 (Final Verification) enforces MANDATORY iteration on ALL incomplete tasks. The agent MUST continue working until 100% completion is achieved - no partial completion is acceptable.

## Research Summary

This task is based on the proposed architecture outlined in the module_communication.md document, which suggests a simplified "agenticity" approach between ArangoDB and Marker modules. The proposed system leverages CLI commands as entry points for inter-module interaction, Claude Code for intelligent codebase understanding and modification, and file-based message exchange for simplicity. The approach focuses on simplicity, minimal infrastructure requirements, and leveraging the capabilities of Claude Code to understand codebases and make targeted modifications.

## MANDATORY Research Process

**CRITICAL REQUIREMENT**: For EACH task, the agent MUST:

1. **Use `perplexity_ask`** to research:
   - Current best practices (2024-2025) for module communication in Python
   - Production implementation patterns for CLI-based communication systems
   - Common pitfalls and solutions in inter-process communication
   - Performance optimization techniques for file-based messaging

2. **Use `WebSearch`** to find:
   - GitHub repositories with working code for CLI-based module communication
   - Real production examples of agent-based systems
   - Popular library implementations for inter-process messaging
   - Benchmark comparisons of different message exchange methods

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
perplexity_ask: "python CLI-based module communication best practices 2024"
WebSearch: "site:github.com python inter-process communication file-based messaging"
perplexity_ask: "LLM agent integration with CLI applications 2024 python"
WebSearch: "site:github.com claude code agent integration python cli"
```

## Implementation Tasks (Ordered by Priority/Complexity)

### Task 1: Message Format and Exchange System ⏳ Not Started

**Priority**: HIGH | **Complexity**: MEDIUM | **Impact**: HIGH

**Research Requirements**:
- [ ] Use `perplexity_ask` to find JSON messaging formats for Python inter-process communication
- [ ] Use `WebSearch` to find production message exchange implementations
- [ ] Search GitHub for "Python file-based messaging" examples
- [ ] Find real-world strategies for handling message directories
- [ ] Locate file-based message exchange patterns
- [ ] Research best practices for message schema design

**Implementation Steps**:
- [ ] 1.1 Create message directory infrastructure
  - Define dedicated message directories for each module
  - Create utilities for directory management
  - Implement path resolution for cross-module messaging
  - Add automatic directory creation if missing
  - Set appropriate permissions

- [ ] 1.2 Define standard message format
  - Create JSON schema for messages
  - Include fields for source, target, type, content, timestamp
  - Add support for metadata and attachments
  - Implement validation for message format
  - Create message serialization/deserialization utilities

- [ ] 1.3 Implement message exchange utilities
  - Create utility functions for writing messages
  - Implement functions for reading messages
  - Add message validation
  - Create message history tracking
  - Implement automatic cleanup of old messages

- [ ] 1.4 Add error handling
  - Implement retry mechanisms for failed message delivery
  - Add validation for message integrity
  - Create error reporting for message exchange issues
  - Implement logging for message activities
  - Add recovery mechanisms for interrupted exchanges

- [ ] 1.5 Create verification methods
  - Test message creation with sample data
  - Verify message serialization/deserialization
  - Validate directory permissions
  - Test message exchange between modules
  - Verify error handling scenarios

- [ ] 1.6 Create verification report
  - Create `/docs/reports/033_task_1_message_exchange.md`
  - Document actual commands and results
  - Include real performance benchmarks
  - Show working code examples
  - Add evidence of functionality

- [ ] 1.7 Git commit feature

**Technical Specifications**:
- Message size limit: < 10MB per message
- Latency target: < 100ms for message exchange
- Format: JSON with UTF-8 encoding
- Directory structure: `/messages/{module_name}/`
- Message naming convention: `{source}_{timestamp}_{type}.json`

**Verification Method**:
- Create test messages
- Verify message format integrity
- Test cross-module message exchange
- Validate error handling
- Verify message history tracking

**Acceptance Criteria**:
- Messages can be created, validated, and exchanged
- Error handling works for common failure scenarios
- Message directories are properly managed
- All utilities function as expected
- Performance meets target metrics

### Task 2: CLI Command System for Marker Module ⏳ Not Started

**Priority**: HIGH | **Complexity**: MEDIUM | **Impact**: HIGH

**Research Requirements**:
- [ ] Use `perplexity_ask` to find Python CLI command patterns
- [ ] Use `WebSearch` to find production Typer CLI implementations
- [ ] Search GitHub for "Python CLI inter-module communication" examples
- [ ] Find real-world CLI command patterns
- [ ] Research command argument validation techniques

**Implementation Steps**:
- [ ] 2.1 Create base CLI structure
  - Create `/marker/cli/agent_commands.py`
  - Set up Typer application
  - Create command entry points
  - Add command-line argument parsing
  - Implement help documentation

- [ ] 2.2 Implement `process-message` command
  - Create command to process messages from other modules
  - Add message file path argument
  - Implement message loading and validation
  - Add basic message processing logic
  - Implement response generation

- [ ] 2.3 Implement `send-message` command
  - Create command to send messages to other modules
  - Add arguments for message content and type
  - Implement message creation
  - Add target module selection
  - Create command execution for target module

- [ ] 2.4 Add integration with message exchange system
  - Connect CLI commands to message utilities
  - Implement file path resolution
  - Add validation for message paths
  - Create error handling for file operations
  - Implement logging for command activities

- [ ] 2.5 Create verification methods
  - Test CLI commands with sample messages
  - Verify command argument parsing
  - Test error handling scenarios
  - Validate help documentation
  - Verify integration with message exchange

- [ ] 2.6 Create verification report
  - Create `/docs/reports/033_task_2_marker_cli.md`
  - Document actual commands and results
  - Include command execution examples
  - Show error handling scenarios
  - Add evidence of functionality

- [ ] 2.7 Git commit feature

**Technical Specifications**:
- CLI framework: Typer
- Command prefix: `agent-`
- Argument validation: Required for all inputs
- Error handling: Detailed error messages
- Help documentation: Comprehensive examples

**Verification Method**:
- Execute CLI commands with various arguments
- Test error scenarios
- Verify help documentation
- Check integration with message system
- Validate command output format

**Acceptance Criteria**:
- CLI commands are executable and functional
- Arguments are properly validated
- Error handling works for common failure scenarios
- Help documentation is comprehensive
- Commands integrate with message exchange system

### Task 3: CLI Command System for ArangoDB Module ⏳ Not Started

**Priority**: HIGH | **Complexity**: MEDIUM | **Impact**: HIGH

**Research Requirements**:
- [ ] Use `perplexity_ask` to find ArangoDB CLI integration patterns
- [ ] Use `WebSearch` to find production ArangoDB Python CLI examples
- [ ] Search GitHub for "ArangoDB CLI Python" examples
- [ ] Research ArangoDB module structure
- [ ] Find examples of ArangoDB CLI tools

**Implementation Steps**:
- [ ] 3.1 Create base CLI structure
  - Create `/arangodb/cli/agent_commands.py`
  - Set up Typer application
  - Create command entry points
  - Add command-line argument parsing
  - Implement help documentation

- [ ] 3.2 Implement `process-message` command
  - Create command to process messages from other modules
  - Add message file path argument
  - Implement message loading and validation
  - Add basic message processing logic
  - Implement response generation

- [ ] 3.3 Implement `send-message` command
  - Create command to send messages to other modules
  - Add arguments for message content and type
  - Implement message creation
  - Add target module selection
  - Create command execution for target module

- [ ] 3.4 Add integration with message exchange system
  - Connect CLI commands to message utilities
  - Implement file path resolution
  - Add validation for message paths
  - Create error handling for file operations
  - Implement logging for command activities

- [ ] 3.5 Create verification methods
  - Test CLI commands with sample messages
  - Verify command argument parsing
  - Test error handling scenarios
  - Validate help documentation
  - Verify integration with message exchange

- [ ] 3.6 Create verification report
  - Create `/docs/reports/033_task_3_arangodb_cli.md`
  - Document actual commands and results
  - Include command execution examples
  - Show error handling scenarios
  - Add evidence of functionality

- [ ] 3.7 Git commit feature

**Technical Specifications**:
- CLI framework: Typer
- Command prefix: `agent-`
- Argument validation: Required for all inputs
- Error handling: Detailed error messages
- Help documentation: Comprehensive examples

**Verification Method**:
- Execute CLI commands with various arguments
- Test error scenarios
- Verify help documentation
- Check integration with message system
- Validate command output format

**Acceptance Criteria**:
- CLI commands are executable and functional
- Arguments are properly validated
- Error handling works for common failure scenarios
- Help documentation is comprehensive
- Commands integrate with message exchange system

### Task 4: Claude Code Integration for Marker ⏳ Not Started

**Priority**: HIGH | **Complexity**: HIGH | **Impact**: HIGH

**Research Requirements**:
- [ ] Use `perplexity_ask` to find patterns for Claude Code integration
- [ ] Use `WebSearch` to find examples of Claude Code execution
- [ ] Search GitHub for "Claude Code Python integration" examples
- [ ] Research script template patterns
- [ ] Find Claude Code best practices
- [ ] Research effective system prompts for Claude instances
- [ ] Find examples of customized Claude system prompts for domain-specific tasks

**Implementation Steps**:
- [ ] 4.1 Create script template infrastructure
  - Create templates directory
  - Implement script template for Marker
  - Add dynamic variable substitution
  - Create template loading utilities
  - Implement script generation logic

- [ ] 4.2 Develop module-specific system prompts
  - Create Marker-specific system prompt templates
  - Include domain knowledge about Marker's architecture
  - Add context about Marker's codebase organization
  - Implement template variables for dynamic context
  - Create system prompt management utilities

- [ ] 4.3 Implement Claude Code execution mechanism
  - Create function to spawn Claude Code instances with custom system prompts
  - Add script path and system prompt arguments
  - Implement process execution with appropriate flags
  - Add output capture
  - Create error handling for execution failures

- [ ] 4.4 Develop message processing script
  - Create script template for processing messages
  - Implement code analysis logic
  - Add dynamic code modification capabilities
  - Create response generation
  - Implement error handling

- [ ] 4.5 Add codebase context functionality
  - Implement directory context for Claude Code
  - Add relevant file pattern matching
  - Create code search utilities
  - Implement context loading
  - Add dynamic context generation

- [ ] 4.6 Create verification methods
  - Test script generation with sample data
  - Verify Claude Code execution with custom system prompts
  - Test message processing capabilities
  - Validate code modification abilities
  - Verify error handling
  - Test system prompt effectiveness

- [ ] 4.7 Create verification report
  - Create `/docs/reports/033_task_4_marker_claude.md`
  - Document actual script generation and execution
  - Include Claude Code interaction examples
  - Show code modification scenarios
  - Add evidence of functionality

- [ ] 4.8 Git commit feature

**Technical Specifications**:
- Script template format: Python with placeholders
- Claude Code command: `claude-code`
- System prompt flag: `--system-prompt`
- Script timeout: 60 seconds
- Workspace directory: Marker repository root
- Context generation: Relevant files only
- System prompt length: < 10,000 characters

**Verification Method**:
- Generate script templates
- Execute Claude Code with customized system prompts
- Test message processing
- Verify code modification capabilities
- Validate error handling
- Test system prompt effectiveness

**Acceptance Criteria**:
- Script templates can be generated and executed
- Claude Code can process messages with customized system prompts
- Code modification capabilities work as expected
- Context generation provides relevant files
- System prompts effectively guide Claude's behavior
- Error handling works for execution failures

### Task 5: Claude Code Integration for ArangoDB ⏳ Not Started

**Priority**: HIGH | **Complexity**: HIGH | **Impact**: HIGH

**Research Requirements**:
- [ ] Use `perplexity_ask` to find patterns for ArangoDB code analysis
- [ ] Use `WebSearch` to find examples of ArangoDB code structure
- [ ] Search GitHub for "ArangoDB Python code" examples
- [ ] Research ArangoDB code organization
- [ ] Find Claude Code ArangoDB integration examples
- [ ] Research effective system prompts for database-related code
- [ ] Find examples of customized system prompts for database operations

**Implementation Steps**:
- [ ] 5.1 Create script template infrastructure
  - Create templates directory
  - Implement script template for ArangoDB
  - Add dynamic variable substitution
  - Create template loading utilities
  - Implement script generation logic

- [ ] 5.2 Develop module-specific system prompts
  - Create ArangoDB-specific system prompt templates
  - Include domain knowledge about ArangoDB's architecture
  - Add context about database queries and operations
  - Implement template variables for dynamic context
  - Create system prompt management utilities

- [ ] 5.3 Implement Claude Code execution mechanism
  - Create function to spawn Claude Code instances with custom system prompts
  - Add script path and system prompt arguments
  - Implement process execution with appropriate flags
  - Add output capture
  - Create error handling for execution failures

- [ ] 5.4 Develop message processing script
  - Create script template for processing messages
  - Implement code analysis logic
  - Add dynamic code modification capabilities
  - Create response generation
  - Implement error handling

- [ ] 5.5 Add codebase context functionality
  - Implement directory context for Claude Code
  - Add relevant file pattern matching
  - Create code search utilities
  - Implement context loading
  - Add dynamic context generation

- [ ] 5.6 Create verification methods
  - Test script generation with sample data
  - Verify Claude Code execution with custom system prompts
  - Test message processing capabilities
  - Validate code modification abilities
  - Verify error handling
  - Test system prompt effectiveness

- [ ] 5.7 Create verification report
  - Create `/docs/reports/033_task_5_arangodb_claude.md`
  - Document actual script generation and execution
  - Include Claude Code interaction examples
  - Show code modification scenarios
  - Add evidence of functionality

- [ ] 5.8 Git commit feature

**Technical Specifications**:
- Script template format: Python with placeholders
- Claude Code command: `claude-code`
- System prompt flag: `--system-prompt`
- Script timeout: 60 seconds
- Workspace directory: ArangoDB repository root
- Context generation: Relevant files only
- System prompt length: < 10,000 characters

**Verification Method**:
- Generate script templates
- Execute Claude Code with customized system prompts
- Test message processing
- Verify code modification capabilities
- Validate error handling
- Test system prompt effectiveness

**Acceptance Criteria**:
- Script templates can be generated and executed
- Claude Code can process messages with customized system prompts
- Code modification capabilities work as expected
- Context generation provides relevant files
- System prompts effectively guide Claude's behavior
- Error handling works for execution failures

### Task 6: Message Processing and Response Handling ⏳ Not Started

**Priority**: MEDIUM | **Complexity**: HIGH | **Impact**: HIGH

**Research Requirements**:
- [ ] Use `perplexity_ask` to find patterns for message processing in Python
- [ ] Use `WebSearch` to find production examples of message response systems
- [ ] Search GitHub for "Python message handler patterns" examples
- [ ] Research response tracking systems
- [ ] Find error handling patterns for messaging systems

**Implementation Steps**:
- [ ] 6.1 Create message processing infrastructure
  - Implement message handler registry
  - Create base message processor class
  - Define message processing pipeline
  - Add message validation
  - Implement message routing

- [ ] 6.2 Develop response generation system
  - Create response message structure
  - Implement response generation utilities
  - Add status tracking
  - Create response validation
  - Implement response delivery

- [ ] 6.3 Add message type handlers
  - Implement handlers for different message types
  - Create specialized processors
  - Add custom validators
  - Implement type-specific logic
  - Create handler registration system

- [ ] 6.4 Implement error handling
  - Create error response generation
  - Add retry mechanisms
  - Implement fallback handlers
  - Create error reporting
  - Add logging for processing errors

- [ ] 6.5 Create verification methods
  - Test message processing with sample messages
  - Verify response generation
  - Test handler registration
  - Validate error handling
  - Verify pipeline execution

- [ ] 6.6 Create verification report
  - Create `/docs/reports/033_task_6_message_processing.md`
  - Document actual message processing
  - Include response generation examples
  - Show error handling scenarios
  - Add evidence of functionality

- [ ] 6.7 Git commit feature

**Technical Specifications**:
- Handler registry: Dynamic discovery
- Processing timeout: 30 seconds per message
- Response format: Standardized JSON
- Error handling: Automatic retries (3x)
- Logging: Detailed processing events

**Verification Method**:
- Process sample messages
- Verify response generation
- Test handler registration
- Validate error handling
- Verify pipeline execution

**Acceptance Criteria**:
- Messages can be processed by appropriate handlers
- Responses are generated correctly
- Error handling works for processing failures
- Handlers can be registered dynamically
- Processing pipeline executes correctly

### Task 7: Integration and Testing Framework ⏳ Not Started

**Priority**: MEDIUM | **Complexity**: MEDIUM | **Impact**: HIGH

**Research Requirements**:
- [ ] Use `perplexity_ask` to find Python testing patterns for messaging systems
- [ ] Use `WebSearch` to find production examples of messaging system tests
- [ ] Search GitHub for "Python message testing" examples
- [ ] Research integration testing approaches
- [ ] Find performance testing patterns

**Implementation Steps**:
- [ ] 7.1 Create testing infrastructure
  - Implement test message generation
  - Create test harness for message exchange
  - Add test case framework
  - Implement test runners
  - Create result validation utilities

- [ ] 7.2 Develop integration tests
  - Create end-to-end test scenarios
  - Implement module communication tests
  - Add cross-module functionality tests
  - Create error scenario tests
  - Implement performance tests

- [ ] 7.3 Add test automation
  - Create test scripts
  - Implement CI integration
  - Add automated test execution
  - Create test reporting
  - Implement test metrics collection

- [ ] 7.4 Develop testing documentation
  - Create test plan
  - Add test case documentation
  - Implement test result reporting
  - Create test coverage analysis
  - Add test execution guide

- [ ] 7.5 Create verification methods
  - Run test suite
  - Verify test coverage
  - Test error scenarios
  - Validate performance metrics
  - Verify test reporting

- [ ] 7.6 Create verification report
  - Create `/docs/reports/033_task_7_testing.md`
  - Document actual test execution
  - Include test results
  - Show performance metrics
  - Add evidence of functionality

- [ ] 7.7 Git commit feature

**Technical Specifications**:
- Test framework: pytest
- Test coverage target: >90%
- Performance test metrics: latency, throughput
- Test scenarios: normal operation, error handling
- Test reporting: HTML, JSON

**Verification Method**:
- Run test suite
- Verify test coverage
- Test error scenarios
- Validate performance metrics
- Check test reporting

**Acceptance Criteria**:
- Test suite executes successfully
- Coverage meets target
- Error scenarios are properly tested
- Performance meets requirements
- Test reporting is comprehensive

### Task 8: Completion Verification and Iteration ⏳ Not Started

**Priority**: CRITICAL | **Complexity**: LOW | **Impact**: CRITICAL

**Implementation Steps**:
- [ ] 8.1 Review all task reports
  - Read all reports in `/docs/reports/033_task_*`
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
  - Test all integrations
  - Verify documentation accuracy
  - Confirm all features work together

- [ ] 8.6 Create final summary report
  - Create `/docs/reports/033_final_summary.md`
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
| `marker agent_commands process-message` | Process a message from another module | `python -m marker.cli.agent_commands process-message /path/to/message.json` | Message processed, response created |
| `marker agent_commands send-message` | Send a message to another module | `python -m marker.cli.agent_commands send-message "Change format to include metadata" --message-type request` | Message sent to target module |
| `arangodb agent_commands process-message` | Process a message from Marker | `python -m arangodb.cli.agent_commands process-message /path/to/message.json` | Message processed, response created |
| `arangodb agent_commands send-message` | Send a message to Marker | `python -m arangodb.cli.agent_commands send-message "Updated QA format as requested" --message-type response` | Message sent to Marker |
| `claude-code` | Execute Claude with custom system prompt | `claude-code script.py --system-prompt "You are a Marker module expert"` | Code executed with customized behavior |
| Task Matrix | Verify completion | Review `/docs/reports/033_task_*` | 100% completion required |

## Version Control Plan

- **Initial Commit**: Create task-033-start tag before implementation
- **Feature Commits**: After each major feature
- **Integration Commits**: After component integration  
- **Test Commits**: After test suite completion
- **Final Tag**: Create task-033-complete after all tests pass

## Resources

**Python Packages**:
- typer: CLI command framework
- pydantic: Message validation
- loguru: Logging
- pytest: Testing framework

**Documentation**:
- [Marker Documentation](https://github.com/VikParuchuri/marker)
- [ArangoDB Documentation](https://www.arangodb.com/docs/)
- [Claude Code Documentation](https://docs.anthropic.com/claude/docs/claude-code)
- [Typer Documentation](https://typer.tiangolo.com/)
- [Claude System Prompts Guide](https://docs.anthropic.com/claude/docs/system-prompts)

**Example Implementations**:
- [Python CLI Applications](https://github.com/topics/cli-app)
- [Inter-Process Communication](https://github.com/topics/ipc)
- [Message Exchange Systems](https://github.com/topics/messaging)
- [Claude System Prompt Examples](https://github.com/topics/claude-prompts)

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
`/docs/reports/033_task_[SUBTASK]_[feature_name].md`

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