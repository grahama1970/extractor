# Marker Project Structure

This document explains the organization of the Marker codebase.

## Directory Structure

```
marker/
├── conf/                  # Configuration files
│   └── allowed_cities.txt  # City names for validation corpus
│
├── docs/                  # Documentation
│   ├── api/               # API reference docs
│   ├── architecture/      # Architecture docs
│   ├── guides/            # User and developer guides
│   ├── integration/       # Integration docs
│   └── tasks/             # Task documentation
│
├── marker/                # Main package source code
│   ├── builders/          # Document builder modules
│   ├── cli/               # Command-line interfaces
│   ├── config/            # Configuration modules
│   ├── converters/        # File format converters
│   ├── llm_call/          # LLM validation module
│   ├── processors/        # Document processors
│   ├── providers/         # Document provider interfaces
│   ├── renderers/         # Output renderers
│   ├── schema/            # Document schema definitions
│   ├── scripts/           # Package scripts
│   ├── services/          # External service interfaces
│   └── utils/             # Utility functions
│
├── scripts/               # Standalone scripts
│   ├── demos/             # Demo applications
│   └── validation/        # Validation scripts
│
├── tests/                 # Test suite
│   ├── arangodb/          # ArangoDB integration tests
│   ├── builders/          # Builder unit tests
│   ├── cli/               # CLI tests
│   ├── code/              # Code detection tests
│   ├── metadata/          # Metadata tests
│   ├── package/           # Package build tests
│   ├── pdf/               # PDF processing tests
│   └── validation/        # Validation tests
│
├── utils/                 # Utility scripts
│   ├── debug_python_type_hints.py  # Type hinting debug tool
│   ├── examine_code_blocks.py      # Code block examination tool
│   └── show_code_blocks.py         # Code block visualization
│
├── CHANGELOG.md           # Version changelog
├── CLA.md                 # Contributor License Agreement
├── CLAUDE.md              # Claude AI instructions
├── INTEGRATION.md         # Integration overview
├── LICENSE                # Project license
├── PROJECT_STRUCTURE.md   # This file
├── README.md              # Project overview
├── pyproject.toml         # Project dependencies and metadata
└── pytest.ini             # Pytest configuration
```

## Key Components

### Core Libraries

- **builders**: Document building and layout detection
- **processors**: Document processing and content analysis
- **renderers**: Output generation (Markdown, JSON, HTML)
- **schema**: Document structure definitions

### Integration Components

- **llm_call**: LLM validation module for integration with LiteLLM
- **arangodb**: ArangoDB integration for document storage and search

### Script Categories

- **demos**: Demonstration scripts showing features
- **validation**: Data validation scripts

### Testing Organization

Tests are organized by functional area in the `tests/` directory. Each subdirectory corresponds to a specific component or feature.

## Development Conventions

1. **Package Management**: All dependencies are managed with `uv` and defined in `pyproject.toml`
2. **Documentation**: Features are documented in the `docs/` directory
3. **Testing**: Tests follow pytest conventions and are organized by feature
4. **Scripts**: Standalone scripts are kept in the `scripts/` directory
5. **Configuration**: Configuration files are kept in the `conf/` directory

## Further References

- [Developer Guide](docs/guides/DEVELOPER_GUIDE.md)
- [Project Overview](docs/guides/PROJECT_OVERVIEW.md)
- [Integration Guide](INTEGRATION.md)