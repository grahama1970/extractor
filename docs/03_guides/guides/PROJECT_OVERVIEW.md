# Marker Documentation

Documentation for the enhanced Marker PDF converter.

## Contents

1. **[MARKER_INTERNALS.md](MARKER_INTERNALS.md)** - Comprehensive technical guide to Marker's internal operations
   - PDF to Marker block conversion
   - Text extraction from blocks
   - Section hierarchy and metadata
   - Surya model integration
   - LLM usage
   - Fork enhancements
   - Image processing pipeline
   - Enhanced table extraction with Camelot
   - Async operations and caching

2. **[DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)** - Complete developer documentation
   - Architecture overview
   - Extension points
   - Configuration system
   - Testing guide
   - Performance optimization
   - Debugging tips
   - Best practices
   - API reference

3. **[FORK_CHANGES_SUMMARY.md](FORK_CHANGES_SUMMARY.md)** - Complete list of changes
   - All new features
   - Modified files
   - Configuration options
   - CLI enhancements
   - Performance improvements

4. **[feature_documentation.md](feature_documentation.md)** - User guide for enhanced features
   - Section breadcrumbs
   - LLM model selection
   - Document hierarchy
   - Section summaries

5. **[ENHANCEMENTS.md](../ENHANCEMENTS.md)** - Summary of fork enhancements
   - Quick start guide
   - Performance impact
   - Configuration options

## Architecture Overview

```
PDF Input
    ↓
Provider (PDF loading)
    ↓
Builders (Layout, OCR, Structure)
    ↓
Processors (Text, Tables, Headers)
    ↓
Enhancements (Hierarchy, Summaries)
    ↓
Renderers (Markdown, JSON, HTML)
    ↓
Output
```

## Key Concepts

- **Blocks**: Basic units of document content (text, images, tables)
- **Processors**: Transform and enhance blocks
- **Builders**: Convert PDF elements to blocks
- **Renderers**: Convert blocks to output formats

## For Developers

See [MARKER_INTERNALS.md](MARKER_INTERNALS.md) for detailed technical information about:
- Code organization
- Key functions and their locations
- Processing pipeline
- Extension points