"""
Module: marker_cli.py
Description: Functions for marker cli operations

External Dependencies:
- click: [Documentation URL]
- marker: [Documentation URL]
- loguru: [Documentation URL]
- traceback: [Documentation URL]

Sample Input:
>>> # Add specific examples based on module functionality

Expected Output:
>>> # Add expected output examples

Example Usage:
>>> # Add usage examples
"""

#!/usr/bin/env python3
"""Main marker CLI entry point that matches README examples.

This provides the main 'marker' command as shown in the README.
"""

import click
from pathlib import Path
from extractor import convert_pdf
from extractor.core.config.parser import ConfigParser
from extractor.core.config.claude_config import get_recommended_config_for_use_case
from extractor.core.settings import settings
import json
from loguru import logger
import sys


@click.command()
@click.argument('input_path', type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path(), help='Output file path')
@click.option('--format', '-f', type=click.Choice(['markdown', 'json', 'html']), default='markdown', help='Output format')
@click.option('--claude-config', type=click.Choice(['disabled', 'minimal', 'tables_only', 'accuracy', 'research']), 
              default='disabled', help='Claude configuration preset')
@click.option('--claude-workspace', type=click.Path(), help='Claude workspace directory')
@click.option('--max-pages', type=int, help='Maximum pages to process')
@click.option('--page-range', type=str, help='Page range (e.g., "1-5,10,15-20")')
@click.option('--debug', is_flag=True, help='Enable debug mode')
@click.option('--disable-ocr', is_flag=True, help='Disable OCR')
@click.option('--languages', type=str, help='Comma-separated list of languages for OCR')
@click.option('--use-llm', is_flag=True, help='Enable LLM processing')
@click.option('--add-summaries', is_flag=True, help='Add AI-generated summaries')
@click.option('--version', is_flag=True, help='Show version')
def main(input_path, output, format, claude_config, claude_workspace, max_pages, 
         page_range, debug, disable_ocr, languages, use_llm, add_summaries, version):
    """Convert PDF documents to markdown with optional AI enhancements.
    
    Examples:
        marker document.pdf
        marker --claude-config accuracy document.pdf
        marker --format json --output output.json document.pdf
    """
    if version:
        from extractor import __version__
        click.echo(f"Marker version {__version__}")
        return
    
    if debug:
        logger.add(sys.stderr, level="DEBUG")
    
    # Build configuration
    config = {}
    
    if max_pages:
        config['max_pages'] = max_pages
        
    if page_range:
        from extractor.core.util import parse_range_str
        config['page_range'] = parse_range_str(page_range)
        
    if disable_ocr:
        config['ocr_all_pages'] = False
        
    if languages:
        config['languages'] = languages.split(',')
        
    if claude_workspace:
        config['claude_workspace'] = claude_workspace
        
    if add_summaries:
        config['add_summaries'] = True
    
    # Convert PDF
    try:
        # Fix tables_only to match code
        config_name = claude_config
        if config_name == "tables_only":
            config_name = "table_analysis_only"
            
        result = convert_pdf(
            input_path,
            output_format=format,
            claude_config=config_name if claude_config != 'disabled' else None,
            use_llm=use_llm,
            **config
        )
        
        # Determine output path
        if not output:
            input_file = Path(input_path)
            output = input_file.parent / f"{input_file.stem}.{format}"
        
        # Save output
        output_path = Path(output)
        if format == 'json':
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result.json or {}, f, indent=2, ensure_ascii=False)
        elif format == 'html':
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(result.html or '')
        else:  # markdown
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(result.markdown)
        
        # Print summary
        click.echo(f"✅ Conversion complete: {output_path}")
        
        if debug or claude_config != 'disabled':
            click.echo(f"\nMetadata:")
            click.echo(json.dumps(result.metadata, indent=2))
            
    except Exception as e:
        logger.error(f"Conversion failed: {e}")
        if debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()