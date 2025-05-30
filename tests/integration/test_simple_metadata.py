"""Simple test to check if metadata is being set properly."""
import json
from pathlib import Path
from marker.converters.pdf import PdfConverter
from marker.config.parser import ConfigParser
from marker.models import create_model_dict
from marker.processors.table import TableProcessor
from marker.util import classes_to_strings


def main():
    """Test with only table processor."""
    pdf_path = "data/input/2505.03335v2.pdf"
    output_dir = Path("test_results/simple_metadata_test")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Set up CLI args with only table processor
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
        # Use only TableProcessor to avoid merging
        'processors': 'marker.processors.table.TableProcessor',
    }
    
    print("Loading models...")
    models = create_model_dict()
    config_parser = ConfigParser(cli_args)
    
    # Create converter
    converter = PdfConverter(
        config=config_parser.generate_config_dict(),
        artifact_dict=models,
        processor_list=config_parser.get_processors(),
        renderer=config_parser.get_renderer(),
        llm_service=config_parser.get_llm_service()
    )
    
    print(f"\nProcessing {pdf_path}...")
    document = converter.build_document(pdf_path)
    
    # Check table blocks directly
    print("\nChecking document blocks:")
    table_count = 0
    from marker.schema import BlockTypes
    
    # Get all blocks in the document
    all_blocks = []
    for page in document.pages:
        for block in page.children:
            all_blocks.append(block)
    
    for block in all_blocks:
        if hasattr(block, 'block_type') and block.block_type == BlockTypes.Table:
            table_count += 1
            print(f"\nTable {table_count}:")
            print(f"  ID: {block.id}")
            print(f"  Has extraction_method: {hasattr(block, 'extraction_method')}")
            if hasattr(block, 'extraction_method'):
                print(f"  Extraction method: {block.extraction_method}")
            if hasattr(block, 'extraction_details'):
                print(f"  Extraction details: {block.extraction_details}")
            if hasattr(block, 'quality_score'):
                print(f"  Quality score: {block.quality_score}")
    
    print(f"\nTotal tables in document: {table_count}")
    
    # Now render and check JSON
    print("\nRendering to JSON...")
    result = converter.renderer(converter.config)(document)
    
    # Save and analyze
    output_path = output_dir / "output.json"
    # Convert to dict manually
    if hasattr(result, 'children'):
        json_data = {
            'children': result.children,
            'metadata': result.metadata if hasattr(result, 'metadata') else {}
        }
    else:
        json_data = result
    
    with open(output_path, 'w') as f:
        json.dump(json_data, f, indent=2, default=str)
    
    print(f"\nOutput saved to: {output_path}")


if __name__ == "__main__":
    main()