#!/usr/bin/env python3
"""Debug why table metadata isn't being set."""

import json
from pathlib import Path
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.schema import BlockTypes

def test_metadata_debug():
    # Input file
    pdf_path = Path("data/input_test/2505.03335v2.pdf")
    
    # Create model dict
    model_dict = create_model_dict()
    
    # Use only table processor
    processor_list = [
        'marker.processors.table.TableProcessor',
    ]
    
    # Create converter
    converter = PdfConverter(
        artifact_dict=model_dict,
        config={},
        renderer='marker.renderers.json.JSONRenderer',
        processor_list=processor_list
    )
    
    print("Converting document with only TableProcessor...")
    
    # Get the document object before rendering
    doc = converter.parse(str(pdf_path))
    
    # Check if table blocks have metadata
    table_count = 0
    for page in doc.pages:
        for block in page.children:
            if block.id.block_type == BlockTypes.Table:
                table_count += 1
                print(f"\nTable {table_count}:")
                print(f"  Type: {type(block)}")
                print(f"  Has extraction_method: {hasattr(block, 'extraction_method')}")
                if hasattr(block, 'extraction_method'):
                    print(f"  extraction_method: {block.extraction_method}")
                print(f"  Has metadata dict: {hasattr(block, 'metadata')}")
                if hasattr(block, 'metadata'):
                    print(f"  metadata dict: {block.metadata}")
                
                # Check __dict__ to see all attributes
                if hasattr(block, '__dict__'):
                    attrs = [a for a in block.__dict__ if not a.startswith('_')]
                    print(f"  All attributes: {attrs}")
    
    print(f"\nTotal tables found in document: {table_count}")
    
    # Now render to JSON
    rendered = converter.render(doc)
    json_str = rendered.model_dump_json()
    json_data = json.loads(json_str)
    
    # Count tables in JSON
    json_table_count = 0
    def count_json_tables(blocks):
        nonlocal json_table_count
        if blocks is None:
            return
        for block in blocks:
            if block.get('block_type') == 'Table':
                json_table_count += 1
                print(f"\nJSON Table {json_table_count}:")
                print(f"  Has extraction_method: {'extraction_method' in block}")
                if 'extraction_method' in block:
                    print(f"  extraction_method: {block['extraction_method']}")
            if 'children' in block and block['children']:
                count_json_tables(block['children'])
    
    count_json_tables(json_data.get('children', []))
    
    print(f"\nTotal tables in JSON: {json_table_count}")

if __name__ == "__main__":
    test_metadata_debug()