# Directory Assessment Report - 2025-07-21

## Overview
Assessment of directories in `/src/extractor/` to determine which should be kept, updated, or deprecated.

## Directory Analysis

### 1. `/src/extractor/handlers/` - **KEEP**
**Contents**: 
- `MarkerPDFHandler` - Adapter for marker integration
- Backup files from November 2025

**Decision**: KEEP
**Reasoning**: 
- Contains active integration code for marker
- Part of the core extraction pipeline
- Recently used (November 2025)

---

### 2. `/src/extractor/integrations/` - **DEPRECATE**
**Contents**: 
- `marker_module.py` with backup files

**Decision**: DEPRECATE
**Reasoning**: 
- Appears to be superseded by the handlers directory
- Contains only backup files from November
- Functionality likely moved to handlers/MarkerPDFHandler

---

### 3. `/src/extractor/logs/` - **DEPRECATE**
**Contents**: 
- Empty log files from today
- `extractor.log` (0 bytes)
- `surya.log` (0 bytes) 
- `marker.log` (0 bytes)

**Decision**: DEPRECATE
**Reasoning**: 
- Empty log files
- Logs should be in project-level logs directory or tmp/
- No active logging happening here

---

### 4. `/src/extractor/mcp/` - **DEPRECATE**
**Contents**: 
- `marker_pdf_server.py` - Old MCP implementation
- Contains old decorator patterns without response_utils

**Decision**: DEPRECATE
**Reasoning**: 
- Superseded by new MCP server in `/src/extractor/servers/`
- Uses outdated patterns (no response_utils)
- New implementation follows MCP checklist standards

---

### 5. `/src/extractor/rl_integration/` - **ARCHIVE**
**Contents**: 
- Reinforcement Learning strategy selection
- `strategy_selector.py` - DQN agent for processing strategy
- `feature_extractor.py` - Document feature extraction
- `deployment.py` - RL deployment utilities

**Decision**: ARCHIVE (not actively used but valuable reference)
**Reasoning**: 
- Experimental RL-based processing optimization
- Depends on `graham_rl_commons` (external dependency)
- Not integrated into current extraction pipeline
- May be valuable for future AI-enhanced extraction

---

### 6. `/src/extractor/processors/` - **KEEP & UPDATE**
**Contents**: 
- `claude_hybrid_processor.py` - Intelligent routing processor
- `claude_math_processor.py` - Math extraction with Claude
- `claude_table_analyzer.py` - Table analysis with Claude
- `surya_direct_pipeline.py` - Direct Surya integration

**Decision**: KEEP & UPDATE
**Reasoning**: 
- Active processors for AI-enhanced extraction
- Core to the extraction pipeline
- Should be integrated with the new MCP server
- May need updates to work with current architecture

---

### 7. `/src/extractor/cli/` - **KEEP**
**Contents**: (per user: "cli will be useful to use extractor as a terminal command")

**Decision**: KEEP
**Reasoning**: 
- User explicitly wants to keep for terminal usage
- Provides command-line interface to extraction tools
- Useful for standalone operation

---

### 8. `/src/extractor/utils/` - **DEPRECATE**
**Contents**: Empty directory

**Decision**: DEPRECATE
**Reasoning**: 
- Completely empty
- No utility functions present
- Utils needed by MCP are in servers/utils/

---

### 9. `scratch.md` - **DELETE**
**Contents**: Incomplete fragment "do we need to update/de"

**Decision**: DELETE
**Reasoning**: 
- Contains only an incomplete thought
- No useful content
- Appears to be accidental file

---

## Summary of Actions

### KEEP (Active Use):
1. **handlers/** - Core marker integration
2. **cli/** - Terminal interface (user requested)
3. **processors/** - AI enhancement processors (needs integration)

### DEPRECATE (Remove):
1. **integrations/** - Superseded by handlers
2. **logs/** - Empty, wrong location
3. **mcp/** - Old MCP implementation
4. **utils/** - Empty directory
5. **scratch.md** - Incomplete fragment

### ARCHIVE (Reference):
1. **rl_integration/** - Experimental RL optimization

## Recommended Next Steps

1. **Move to deprecated/**:
   - integrations/
   - logs/
   - mcp/
   - utils/

2. **Delete**:
   - scratch.md (no value)

3. **Archive to archive/**:
   - rl_integration/ (with timestamp)

4. **Future Work**:
   - Integrate processors/ with new MCP server
   - Update processors to use response_utils
   - Document processor capabilities in MCP server

## Current Clean Structure
```
src/extractor/
├── core/           # Core extraction library
├── handlers/       # Integration adapters
├── processors/     # AI enhancement processors
├── cli/           # Terminal interface
└── servers/       # MCP server implementation
```

This maintains a clean separation of concerns with only actively used directories.