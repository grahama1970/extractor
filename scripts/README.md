# Scripts Directory

This directory contains utility scripts for the extractor project.

## Directory Structure

### analysis/
Analysis and inspection tools for examining extracted documents:
- `analyze_nested_json.py` - Analyze nested JSON structures
- `analyze_table_count.py` - Count and analyze tables
- `check_missing_paths.py` - Check for missing file paths
- `check_processors_used.py` - Check which processors were used
- `check_table_metadata.py` - Inspect table metadata
- `count_blocks.py` - Count document blocks
- `inspect_metrics.py` - Inspect extraction metrics
- `quick_table_count.py` - Quick table counting utility
- `show_compact_structure.py` - Show compact document structure
- `show_section_structure.py` - Display section hierarchy
- `string_replace.py` - String replacement utility
- `trace_table_processing.py` - Trace table processing steps

### cli/
Command-line interface tools:
- `cli.py` - Main CLI entry point
- `marker_app.py` - Marker application interface
- `marker_cli_mcp.py` - MCP-enabled CLI
- `marker_mcp_cli.py` - Alternative MCP CLI
- `marker_server.py` - Marker server implementation

### comparison/
Tools for comparing different extraction methods:
- `marker_extractor_comparison.py` - Compare marker vs extractor
- `original_marker_isolated.py` - Isolated original marker
- `test_original_marker.py` - Test original marker
- `use_original_marker_simple.py` - Simple marker wrapper

### debug/
Debugging and diagnostic tools:
- `debug_and_fix_extractor.py` - Debug extraction issues
- `diagnose_extractor_import.py` - Diagnose import problems
- `fix_surya_dependencies.py` - Fix Surya dependencies
- `fix_surya_models.py` - Fix Surya model issues

### demo/
Demonstration scripts showing various features:
- `add_section_breadcrumbs.py` - Add breadcrumbs to sections
- `arango_flattening_example.py` - ArangoDB flattening demo
- `create_test_pdf.py` - Create test PDFs
- `demo_existing_breadcrumbs.py` - Demo with existing breadcrumbs
- `demo_summarizer.py` - Summarization demo
- `extract_table_driver.py` - Table extraction demo
- `minimal_table_test.py` - Minimal table test
- `simple_table_extract.py` - Simple table extraction

### utils/
General utility scripts (currently empty after cleanup)

## Usage

Most scripts can be run directly with Python:

```bash
python scripts/analysis/analyze_table_count.py /path/to/document.pdf
```

For CLI tools, use:

```bash
python scripts/cli/cli.py [command] [options]
```

## Note

Many obsolete, duplicate, or one-off scripts have been archived. If you need historical scripts, check `archive/scripts_archive_20250721/`.