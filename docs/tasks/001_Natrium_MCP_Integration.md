# Task List: Marker MCP Integration for Natrium

## Overview
This task list defines the necessary changes to make the Marker project easily available as an MCP tool for the Natrium orchestrator.

## Core Principle: Make Marker a Plug-and-Play MCP Tool

The Natrium project needs to call Marker's PDF extraction capabilities through MCP interfaces. This requires proper MCP server setup, clear tool definitions, and reliable endpoints.

## Task 1: Create MCP Server Configuration

**Goal**: Set up a proper MCP server for Marker with clear tool definitions

### Working Code Example

Create :



### Run Command


### Expected Output
Server should start and respond to tool calls with structured JSON.

## Task 2: Add MCP Configuration File

**Goal**: Create .mcp.json configuration for easy integration

### Working Code Example

Create :



### Validation


## Task 3: Fix Import Structure for MCP

**Goal**: Ensure all marker modules can be imported cleanly

### Current Issues
1. Relative imports break when called from MCP context
2. Missing __init__.py files in some directories
3. Circular dependencies between modules

### Working Code Example

Fix imports in :



## Task 4: Create Natrium-Specific Endpoints

**Goal**: Add endpoints specifically for Natrium's needs

### Working Code Example

Add to :



## Task 5: Add Error Handling for MCP Context

**Goal**: Robust error handling when called via MCP

### Working Code Example



## Task 6: Add Integration Tests

**Goal**: Test Marker works correctly when called from Natrium

### Working Code Example

Create :



## Task 7: Document MCP Usage

**Goal**: Clear documentation for Natrium developers

### Working Code Example

Create :

bash
   cd /home/graham/workspace/experiments/marker
   pip install -e .
   bash
   python -m marker.mcp_server
   python
   result = await call_mcp_tool(
       "marker",
       "extract_sections", 
       {"doc_path": "path/to/document.pdf"}
   )
   extract_sectionsparse_code_blocksextract_natrium_requirementsextract_tables_from_pdfjson
{
  "success": true/false,
  "data": {...} or null,
  "error": "ERROR_CODE" or null,
  "message": "Human readable message"
}


## Validation Checklist

- [ ] MCP server starts without errors
- [ ] All imports work from external context
- [ ] Natrium can call extract_sections successfully
- [ ] Error responses are JSON-serializable
- [ ] No hardcoded paths in code
- [ ] All dependencies listed in pyproject.toml
- [ ] Integration tests pass

## Common Issues & Solutions

### Issue 1: Import errors when running as MCP


### Issue 2: File paths not resolving


### Issue 3: Large PDFs timeout

