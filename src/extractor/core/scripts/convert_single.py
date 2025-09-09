#!/usr/bin/env python3
"""
Marker conversion script for PDF extraction
This is the script called by extract-pdf.md pipeline
"""

import os
import sys
import json
import click
from pathlib import Path

# Add the parent directory to the path so we can import from src
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from extractor.core.converters.pdf import PdfConverter
from extractor.core.config.parser import ConfigParser
from extractor.core.models import create_model_dict


@ConfigParser.common_options
@click.command()
@click.argument("pdf_path", type=click.Path(exists=True))
@click.option("--extract_fonts", is_flag=True, default=False, help="Extract font metrics for first span in each block")
def main(pdf_path, **kwargs):
    """Convert a single PDF file using marker."""
    try:
        # Create config parser
        config_parser = ConfigParser(kwargs)
        config = config_parser.generate_config_dict()
        
        # Set default output directory if not specified
        if 'output_dir' not in kwargs or not kwargs['output_dir']:
            kwargs['output_dir'] = '.'
            
        output_dir = kwargs['output_dir']
        os.makedirs(output_dir, exist_ok=True)
        
        # Create models
        print(f"Loading ML models...")
        # Let models auto-detect device/dtype for better compatibility
        models = create_model_dict()
        
        # Get processors
        processors = config_parser.get_processors()
        
        # Create converter
        print(f"Creating PDF converter...")
        converter = PdfConverter(
            config=config,
            artifact_dict=models,
            processor_list=processors,
            renderer=config_parser.get_renderer(),
            llm_service=config_parser.get_llm_service()
        )
        
        # Convert PDF
        print(f"Processing {pdf_path}...")
        result = converter(pdf_path)
        
        # Extract font metrics if requested (currently limited by marker's JSON output)
        if kwargs.get('extract_fonts', False):
            print(f"Note: Font extraction requested but marker JSON output doesn't include font/span data")
            print(f"Font data is only available in marker's internal Document object, not in JSON export")
            
            # Add metadata note about font extraction limitation
            if hasattr(result, 'metadata'):
                if not hasattr(result.metadata, 'update'):
                    # Convert to dict if needed
                    meta_dict = result.metadata if isinstance(result.metadata, dict) else {}
                    meta_dict['font_extraction_note'] = "Font data not available in marker JSON output - only in internal Document object"
                    result.metadata = meta_dict
        
        # Save result
        pdf_name = Path(pdf_path).stem
        output_format = kwargs.get('output_format', 'json')
        
        if output_format == 'json':
            output_file = os.path.join(output_dir, f"{pdf_name}.json")
            with open(output_file, 'w') as f:
                # Convert Pydantic model to JSON
                if hasattr(result, 'model_dump_json'):
                    f.write(result.model_dump_json(indent=2))
                else:
                    f.write(json.dumps(result, indent=2))
        else:
            output_file = os.path.join(output_dir, f"{pdf_name}.{output_format}")
            with open(output_file, 'w') as f:
                f.write(str(result))
                
        print(f"✓ Saved to {output_file}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()