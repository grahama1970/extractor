#!/usr/bin/env python
"""
Test script for demonstrating the combined enhanced features:
1. CSV/JSON table output
2. Section breadcrumb hierarchy
"""
import os
import sys
import argparse
import json
from pathlib import Path

from marker.converters.pdf import PDFConverter
from marker.renderers.markdown import MarkdownRenderer
from marker.renderers.json import JSONRenderer
from marker.config.parser import ParserConfig
from marker.processors.table import TableProcessor
from marker.schema.blocks.basetable import BaseTable
from marker.utils.markdown_extractor import extract_from_markdown
from marker.utils.table_extractor import extract_tables_from_markdown

# Set up feature flags
BaseTable.include_csv = True
BaseTable.include_json = True


def main():
    parser = argparse.ArgumentParser(description="Test enhanced features of Marker")
    parser.add_argument("--input", "-i", help="Input PDF file", default="data/input/2505.03335v2.pdf")
    parser.add_argument("--pages", "-p", help="Page range (e.g., 0-3)", default="0-2")
    parser.add_argument("--output", "-o", help="Output directory", default="data/output")
    parser.add_argument("--no-breadcrumbs", action="store_true", help="Disable section breadcrumbs")
    parser.add_argument("--no-table-csv", action="store_true", help="Disable table CSV output")
    parser.add_argument("--no-table-json", action="store_true", help="Disable table JSON output")
    args = parser.parse_args()

    # Parse page range
    start_page, end_page = map(int, args.pages.split('-'))

    # Set feature flags
    BaseTable.include_csv = not args.no_table_csv
    BaseTable.include_json = not args.no_table_json

    # Configure parser
    config = ParserConfig(
        ocr_engine="surya",
        use_page_structure=True,
        use_camelot_fallback=True,
        camelot_min_cell_threshold=5,
    )

    # Set up converter
    converter = PDFConverter(config=config)

    # Configure renderers
    markdown_renderer = MarkdownRenderer(include_breadcrumbs=not args.no_breadcrumbs)
    json_renderer = JSONRenderer()

    # Convert document
    print(f"Converting {args.input} pages {start_page}-{end_page}...")
    document = converter.convert(args.input, start_page=start_page, end_page=end_page)

    # Create output directory
    input_name = os.path.splitext(os.path.basename(args.input))[0]
    output_dir = Path(args.output) / f"{input_name}_enhanced"
    os.makedirs(output_dir, exist_ok=True)

    # Render to markdown
    markdown_output = markdown_renderer(document)
    markdown_path = output_dir / f"{input_name}_enhanced.md"
    with open(markdown_path, 'w', encoding='utf-8') as f:
        f.write(markdown_output.markdown)
    print(f"Markdown output saved to {markdown_path}")

    # Render to JSON
    json_output = json_renderer(document)
    json_path = output_dir / f"{input_name}_enhanced.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(json_output.dict(), f, indent=2, default=str)
    print(f"JSON output saved to {json_path}")

    # Extract section hierarchy
    if not args.no_breadcrumbs:
        extracted = extract_from_markdown(markdown_output.markdown)
        sections_path = output_dir / f"{input_name}_sections.json"
        with open(sections_path, 'w', encoding='utf-8') as f:
            json.dump(extracted, f, indent=2, ensure_ascii=False)
        print(f"Section hierarchy saved to {sections_path}")

        # Print summary of sections
        print("\nSection Summary:")
        for i, section in enumerate(extracted["sections"]):
            path_str = " > ".join(section.get("section_path", []))
            print(f"{i+1}. [H{section['level']}] {section['title']}")
            print(f"   Path: {path_str}")

    # Extract table data
    tables = extract_tables_from_markdown(markdown_output.markdown)
    tables_path = output_dir / f"{input_name}_tables.json"
    with open(tables_path, 'w', encoding='utf-8') as f:
        json.dump({"tables": tables}, f, indent=2, ensure_ascii=False)
    print(f"Table data saved to {tables_path}")

    # Calculate table stats
    print(f"\nTable Statistics:")
    print(f"Total tables: {len(tables)}")

    tables_with_csv = len([t for t in tables if t.get("csv")])
    tables_with_json = len([t for t in tables if t.get("json")])

    if BaseTable.include_csv:
        print(f"Tables with CSV: {tables_with_csv}")
    if BaseTable.include_json:
        print(f"Tables with JSON: {tables_with_json}")


if __name__ == "__main__":
    main()