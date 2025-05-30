"""Check which processors are being used in the conversion."""
import json
from pathlib import Path
from marker.converters.pdf import PdfConverter
from marker.config.parser import ConfigParser
from marker.models import create_model_dict
from marker.util import classes_to_strings


def main():
    """Check which processors are configured."""
    # Set up CLI args similar to the test
    cli_args = {
        'output_dir': 'test_results/processor_check',
        'output_format': 'json',
        'debug': True,
        'use_llm': False,  # Not using LLM
        'disable_multiprocessing': True,
        'disable_image_extraction': False,
        'page_range': None,
        'languages': None,
        'config_json': None,
        'converter_cls': None,
        'llm_service': None,
        'force_layout_block': None,
        'add_summaries': False,
        'processors': None,  # Using default processors
    }
    
    # Create models and config
    models = create_model_dict()
    config_parser = ConfigParser(cli_args)
    
    # Get converter
    converter_cls = config_parser.get_converter_cls()
    
    # Print default processors
    print("Default processors in PdfConverter:")
    for i, proc in enumerate(converter_cls.default_processors):
        print(f"  {i+1}. {proc.__name__}")
    
    # Create converter instance
    converter = converter_cls(
        config=config_parser.generate_config_dict(),
        artifact_dict=models,
        processor_list=config_parser.get_processors(),
        renderer=config_parser.get_renderer(),
        llm_service=config_parser.get_llm_service()
    )
    
    # Print actual processors being used
    print("\nActual processors configured:")
    for i, proc in enumerate(converter.processor_list):
        print(f"  {i+1}. {proc.__class__.__name__}")
        # Check if it's an LLM processor
        if hasattr(proc, 'llm_service'):
            print(f"     - LLM Service: {proc.llm_service}")
            print(f"     - Should run: {'Yes' if proc.llm_service else 'No'}")


if __name__ == "__main__":
    main()