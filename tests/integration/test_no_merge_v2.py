#!/usr/bin/env python3
"""Test conversion without table merge processors to verify table count."""

import json
from pathlib import Path
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.config.parser import ConfigParser
from marker.util import strings_to_classes

def test_without_merge():
    # Input file
    pdf_path = Path("data/input_test/2505.03335v2.pdf")
    
    # Create model dict (required for artifact_dict)
    model_dict = create_model_dict()
    
    # Explicitly list only processors we want
    processor_list = [
        'marker.processors.blockquote.BlockquoteProcessor',
        'marker.processors.code.CodeProcessor',
        'marker.processors.document_toc.DocumentTOCProcessor',
        'marker.processors.equation.EquationProcessor',
        'marker.processors.footnote.FootnoteProcessor',
        'marker.processors.ignoretext.IgnoreTextProcessor',
        'marker.processors.line_numbers.LineNumbersProcessor',
        'marker.processors.list.ListProcessor',
        'marker.processors.page_header.PageHeaderProcessor',
        'marker.processors.sectionheader.SectionHeaderProcessor',
        'marker.processors.table.TableProcessor',  # Only basic table processor
        'marker.processors.text.TextProcessor',
        'marker.processors.reference.ReferenceProcessor',
        'marker.processors.debug.DebugProcessor'
    ]
    
    # Create converter with JSON renderer and specific processors
    converter = PdfConverter(
        artifact_dict=model_dict,
        config={},
        renderer='marker.renderers.json.JSONRenderer',
        processor_list=processor_list
    )
    
    print(f"Using {len(processor_list)} processors")
    for p in processor_list:
        print(f"  - {p.split('.')[-1]}")
    
    # Convert the document
    rendered = converter(str(pdf_path))
    
    # Convert to JSON string and parse
    json_str = rendered.model_dump_json()
    json_data = json.loads(json_str)
    
    # Count tables
    table_count = 0
    tables_with_metadata = 0
    table_paths = []
    
    def count_tables_recursive(blocks, path="root"):
        nonlocal table_count, tables_with_metadata
        if blocks is None:
            return
        for i, block in enumerate(blocks):
            current_path = f"{path}/children[{i}]"
            if block.get('block_type') == 'Table':  # Note: might be 'block_type' not 'type'
                table_count += 1
                table_paths.append(current_path)
                if block.get('extraction_method'):
                    tables_with_metadata += 1
                    print(f"Table {table_count} at {current_path}:")
                    print(f"  extraction_method: {block.get('extraction_method')}")
                    print(f"  quality_score: {block.get('quality_score')}")
                else:
                    print(f"Table {table_count} at {current_path}: NO METADATA")
            if 'children' in block and block['children']:
                count_tables_recursive(block['children'], current_path)
    
    count_tables_recursive(json_data.get('children', []))
    
    print(f"\nTotal tables found: {table_count}")
    print(f"Tables with metadata: {tables_with_metadata}")
    
    # Save output for inspection
    output_path = Path("data/output/no_merge_test_v2/output.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(json_data, f, indent=2)
    print(f"\nOutput saved to: {output_path}")
    
    return table_count, tables_with_metadata

if __name__ == "__main__":
    tables, with_metadata = test_without_merge()
    expected_tables = 9
    if tables == expected_tables:
        print(f"\n✅ SUCCESS: Found {tables} tables (expected {expected_tables})")
    else:
        print(f"\n❌ FAILED: Found {tables} tables but expected {expected_tables}")
    
    if with_metadata == tables:
        print(f"✅ SUCCESS: All {with_metadata} tables have metadata")
    else:
        print(f"❌ FAILED: Only {with_metadata}/{tables} tables have metadata")