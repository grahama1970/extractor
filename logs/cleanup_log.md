# Cleanup Log

**Date**: 2024-01-18

## Files Organized

### Moved to `/logs/`
- `output.log` - Application output log
- `poetry-installer-error-dtzr6zmi.log` - Poetry installation error log

### Moved to `/docs/archive/`
- `CLEANUP_SUMMARY.md` - Previous cleanup documentation
- `ENHANCEMENTS.md` - Enhancement documentation

## Remaining Root Files

The following files remain in the root as they are standard project files:

- **Configuration Files**: `.env`, `.gitignore`, `.pre-commit-config.yaml`
- **Project Files**: `pyproject.toml`, `pytest.ini`, `uv.lock`
- **Documentation**: `README.md`, `CHANGELOG.md`, `CLA.md`, `LICENSE`

## Directory Structure

```
marker/
├── docs/           # All documentation
│   └── archive/    # Archived/superseded docs
├── logs/           # Log files
├── marker/         # Source code
├── tests/          # Test files
└── [root files]    # Standard project files
```

All stray files have been organized into appropriate directories.