"""Test table metadata in JSON output without table merge processor."""
import json
from pathlib import Path
from marker.converters.pdf import PdfConverter
from marker.config.parser import ConfigParser
from marker.models import create_model_dict
from marker.util import classes_to_strings


def run_extraction_without_merge():
    """Run extraction without table merge processor."""
    pdf_path = "data/input/2505.03335v2.pdf"
    output_dir = Path("test_results/no_merge_test")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Set up CLI args
    cli_args = {
        'output_dir': str(output_dir),
        'output_format': 'json',
        'debug': False,
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
        'processors': None,  # Will customize this
    }
    
    print("Loading models...")
    models = create_model_dict()
    config_parser = ConfigParser(cli_args)
    
    # Get default processors and remove LLMTableMergeProcessor
    converter_cls = config_parser.get_converter_cls()
    custom_processors = [p for p in converter_cls.default_processors if p.__name__ != 'LLMTableMergeProcessor']
    processor_strings = classes_to_strings(custom_processors)
    
    print(f"\nUsing {len(custom_processors)} processors (removed LLMTableMergeProcessor)")
    
    # Create converter
    converter = converter_cls(
        config=config_parser.generate_config_dict(),
        artifact_dict=models,
        processor_list=processor_strings,
        renderer=config_parser.get_renderer(),
        llm_service=config_parser.get_llm_service()
    )
    
    print(f"\nProcessing {pdf_path}...")
    result = converter(pdf_path)
    
    # Save output
    output_path = output_dir / "output.json"
    with open(output_path, 'w') as f:
        json.dump(result.model_dump(), f, indent=2)
    
    # Analyze tables
    with open(output_path, 'r') as f:
        data = json.load(f)
    
    def analyze_tables(d, tables=None):
        if tables is None:
            tables = []
        
        if isinstance(d, dict):
            if d.get('block_type') == 'Table':
                tables.append({
                    'bbox': d.get('bbox'),
                    'page_idx': d.get('page_idx'),
                    'extraction_method': d.get('extraction_method'),
                    'extraction_details': d.get('extraction_details'),
                    'quality_score': d.get('quality_score'),
                    'quality_metrics': d.get('quality_metrics'),
                    'merge_info': d.get('merge_info'),
                })
            
            for v in d.values():
                if isinstance(v, (dict, list)):
                    analyze_tables(v, tables)
                    
        elif isinstance(d, list):
            for item in d:
                analyze_tables(item, tables)
        
        return tables
    
    tables = analyze_tables(data)
    print(f"\nTables found: {len(tables)}")
    print("\nTable metadata:")
    for i, table in enumerate(tables):
        print(f"\nTable {i+1}:")
        print(f"  Page: {table['page_idx']}")
        print(f"  Extraction method: {table['extraction_method']}")
        print(f"  Details: {table['extraction_details']}")
        print(f"  Quality score: {table['quality_score']}")
    
    return len(tables)


if __name__ == "__main__":
    table_count = run_extraction_without_merge()
    print(f"\nFinal table count: {table_count}")
    if table_count == 9:
        print("✅ SUCCESS: All 9 tables detected!")
    else:
        print(f"❌ ISSUE: Only {table_count} tables detected instead of 9")