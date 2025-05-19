# 3-Layer Architecture Refactoring Guide

This guide documents the process for refactoring Python modules into a clean 3-layer architecture. Use this as a reference when restructuring existing modules or creating new ones.

## Architecture Overview

The 3-layer architecture separates code into distinct layers:

```
module_name/
├── core/           # Pure business logic, independently testable functions
│   └── functions.py
├── cli/            # Command-line interface with typer and rich formatting
│   ├── app.py
│   ├── formatters.py
│   ├── validators.py
│   └── schemas.py
└── mcp/            # MCP integration
    ├── schema.py   # MCP-compliant schemas
    └── wrapper.py  # FastMCP wrapper
```

### Layer Responsibilities

1. **Core Layer**
   - Contains pure business logic with no UI or framework dependencies
   - Functions are independently testable
   - No imports from CLI or MCP layers
   - Minimal external dependencies

2. **CLI Layer**
   - User interface built with Typer
   - Rich formatting for console output
   - Input validation and error handling
   - Calls core layer functions

3. **MCP Layer**
   - FastMCP integration for Claude tools
   - JSON schema definitions
   - Request/response handling
   - Adapters between CLI and MCP

## Refactoring Steps

### 1. Analyze Existing Code

Before refactoring:
- Identify core functionality
- Map dependencies between functions
- Note external library usage
- Identify presentation/UI code
- Document current CLI interface

### 2. Create Directory Structure

```bash
mkdir -p module_name/{core,cli,mcp}
touch module_name/{core,cli,mcp}/__init__.py
```

### 3. Implement Core Layer

For each core functionality:

1. Create appropriate module files
2. Focus on pure business logic
3. Ensure all functions are independently testable
4. Add comprehensive docstrings with:
   - Function purpose
   - Links to third-party documentation
   - Sample input/output
5. Include validation in main block with real test data

### 4. Implement CLI Layer

1. **app.py**: Create Typer application with commands
   - Map each CLI command to core functions
   - Structure commands logically
   - Include detailed help text

2. **formatters.py**: Rich-based formatting functions
   - Create consistent output formatting
   - Support tables, panels, trees
   - Include error/warning/success formatting

3. **validators.py**: Input validation functions
   - Validate all user inputs
   - Return helpful error messages
   - Use Typer's callback system for validation

4. **schemas.py**: Pydantic models for input/output
   - Define data structures
   - Include validation rules
   - Use for both CLI and MCP layers

### 5. Implement MCP Layer

1. **schema.py**: JSON schema definitions
   - Define input/output formats for each command
   - Match CLI parameters
   - Include type information and descriptions

2. **wrapper.py**: FastMCP integration
   - Create handler functions for each command
   - Map between MCP and core functions
   - Handle serialization/deserialization

### 6. Update Module Exports

In the main `__init__.py`:
- Import and export core functionality
- Include version information
- Document high-level usage examples

## Validation Requirements

Each file should include a main block that:
1. Tests functionality with real data
2. Verifies expected results
3. Reports success/failure
4. Exits with appropriate code

Example validation pattern:

```python
if __name__ == "__main__":
    import sys
    
    # List to track all validation failures
    all_validation_failures = []
    total_tests = 0
    
    # Test 1: Basic functionality
    total_tests += 1
    try:
        # Test code
        result = test_function(test_input)
        expected = expected_output
        
        if result != expected:
            all_validation_failures.append(f"Expected {expected}, got {result}")
    except Exception as e:
        all_validation_failures.append(f"Unexpected exception: {str(e)}")
    
    # More tests...
    
    # Final validation result
    if all_validation_failures:
        print(f"❌ VALIDATION FAILED - {len(all_validation_failures)} of {total_tests} tests failed:")
        for failure in all_validation_failures:
            print(f"  - {failure}")
        sys.exit(1)
    else:
        print(f"✅ VALIDATION PASSED - All {total_tests} tests produced expected results")
        print("Function is validated and formal tests can now be written")
        sys.exit(0)
```

## Example Refactoring Process

### Sample Refactoring Plan

1. Create directory structure
2. Implement core functionality
3. Create CLI layer with Typer app and formatters
4. Create MCP layer with FastMCP integration
5. Update module __init__.py with proper imports

### Refactoring Example: Module "gitget"

This example demonstrates refactoring a Git repo processing tool:

1. **Core Layer**: Created functions for repo operations, text chunking
   - `repo_operations.py`: sparse_clone, find_files, process_repository
   - `directory_manager.py`: Repository directory management
   - `text_chunker.py`: Text chunking with token awareness
   - `utils.py`: Common utilities for path and file handling

2. **CLI Layer**: Built Typer app with commands
   - `app.py`: Commands for clone, process, extract, info
   - `formatters.py`: Rich formatting for tables, trees, etc.
   - `validators.py`: Validation for Git URLs, paths, etc.
   - `schemas.py`: Pydantic models for data structures

3. **MCP Layer**: Added FastMCP integration
   - `schema.py`: JSON schema for MCP commands
   - `wrapper.py`: FastMCP wrapper and handlers

## Best Practices

- Maintain separation of concerns between layers
- Make core functions independently testable
- Use rich formatting consistently in CLI
- Validate all inputs with helpful error messages
- Document all functions comprehensively
- Test with real data in validation functions
- Follow type hinting throughout the codebase
- Structure error handling consistently
- Keep files under 500 lines
- Use environment-independent paths