# Archived Source Code - 2025-07-21

This directory contains source code that was archived on July 21, 2025, as part of a project cleanup effort.

## Archived Items

### 1. granger_common/
**Reason for archival:** This appears to be Granger-specific common utilities that should be in a separate Granger project, not in the extractor project.
**Contents:**
- Security middleware
- PDF handler
- Rate limiter
- Schema manager
- Implementation guides

### 2. marker/
**Reason for archival:** Nearly empty directory with only `__init__.py`, likely legacy code or abandoned integration.
**Contents:**
- `__init__.py`
- `__pycache__/`

### 3. marker_ground_truth/
**Reason for archival:** Empty directory, possibly intended for ground truth data but never implemented.

### 4. messages/
**Reason for archival:** Message handling for various integrations (CLI, MCP, ArangoDB) that appears to be experimental or should be part of specific integration packages.
**Contents:**
- cli/
- from_arangodb/
- mcp/
- to_arangodb/

### 5. granger_security_middleware_simple.py
**Reason for archival:** Duplicate file that was already moved to src/granger_common/ (now also archived).

## Notes

These directories and files were moved out of the main `src/` directory to:
1. Keep the source tree focused on the core extractor functionality
2. Remove experimental or abandoned code
3. Separate project-specific code (Granger) from the general-purpose extractor library

If any of this code needs to be restored, it can be found here or in the Git history.