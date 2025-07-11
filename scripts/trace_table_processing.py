"""
Module: trace_table_processing.py

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

import json
from pathlib import Path
from marker.converters.pdf import PdfConverter
from marker.config.parser import ConfigParser
from marker.models import create_model_dict
from marker.schema import BlockTypes


def trace_tables(document):
    """Trace all tables in the document."""
    tables = []
    for i, block in enumerate(document.blocks):
        if block.block_type == BlockTypes.Table:
            tables.append({
                'index': i,
                'id': block.id,
                'page': block.page_id,
                'bbox': block.bbox,
                'polygon': str(block.polygon) if block.polygon else None,
                'children': len(block.structure) if block.structure else 0,
                'metadata': block.metadata if hasattr(block, 'metadata') else {},
            })
    return tables


def main():
    """Run conversion and trace table processing."""
    pdf_path = "data/input/2505.03335v2.pdf"
    
    # Set up CLI args
    cli_args = {
        'output_dir': 'test_results/trace_tables',
        'output_format': 'json',
        'debug': True,
        'use_llm': False,
        'disable_multiprocessing': True,
        'disable_image_extraction': False,
        'page_range': None,
        'languages': None,
        'config_json': None,
        'converter_cls': None,
        'llm_service': None,
        'force_layout_block': None,
        'add_summaries': False,
        'processors': None,  # Use default processors
    }
    
    # Create models and config
    print("Loading models...")
    models = create_model_dict()
    config_parser = ConfigParser(cli_args)
    
    # Get converter
    converter_cls = config_parser.get_converter_cls()
    
    # Create converter WITHOUT table merge processor
    # Convert processor classes to strings
    from marker.util import classes_to_strings
    custom_processors = [p for p in converter_cls.default_processors if p.__name__ != 'LLMTableMergeProcessor']
    custom_processor_strings = classes_to_strings(custom_processors)
    
    print(f"\nProcessors being used ({len(custom_processors)}):")
    for p in custom_processors:
        print(f"  - {p.__name__}")
    
    converter = converter_cls(
        config=config_parser.generate_config_dict(),
        artifact_dict=models,
        processor_list=custom_processor_strings,
        renderer=config_parser.get_renderer(),
        llm_service=config_parser.get_llm_service()
    )
    
    # Build document
    print(f"\nProcessing {pdf_path}...")
    document = converter.build_document(pdf_path)
    
    # Trace tables before processing
    print("\nTables after initial extraction:")
    initial_tables = trace_tables(document)
    print(f"Found {len(initial_tables)} tables")
    
    # Run processors
    print("\nRunning processors...")
    for processor in converter.processor_list:
        processor_name = processor.__class__.__name__
        if processor_name == 'TableProcessor':
            print(f"  Running {processor_name}...")
            tables_before = trace_tables(document)
            processor(document)
            tables_after = trace_tables(document)
            print(f"    Tables before: {len(tables_before)}")
            print(f"    Tables after: {len(tables_after)}")
        else:
            processor(document)
    
    # Final table count
    final_tables = trace_tables(document)
    print(f"\nFinal table count: {len(final_tables)}")
    
    # Save detailed table info
    output_dir = Path(cli_args['output_dir'])
    output_dir.mkdir(parents=True, exist_ok=True)
    
    with open(output_dir / "table_trace.json", "w") as f:
        json.dump({
            'initial_tables': initial_tables,
            'final_tables': final_tables,
            'processors_used': [p.__name__ for p in custom_processors],
        }, f, indent=2)
    
    # Also render the output
    rendered = converter.renderer(converter.config)(document)
    output_path = output_dir / "output.json"
    rendered.save(output_path)
    
    print(f"\nResults saved to: {output_dir}")
    print(f"  - Table trace: table_trace.json")
    print(f"  - Full output: output.json")


if __name__ == "__main__":
    main()