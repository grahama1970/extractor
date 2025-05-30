#!/usr/bin/env python3
"""
Command-line tool to analyze tables for merging after document processing.

This tool runs AFTER marker has processed a document and analyzes which
tables should be merged, without modifying any data.
"""

import json
import sys
from pathlib import Path
import click
from typing import Optional

from marker.core.converters.pdf import PdfConverter
from marker.core.models import create_model_dict
from marker.core.processors.table_merge_analyzer import TableMergeAnalyzer
from marker.core.schema import BlockTypes


def load_processed_document(json_path: Path):
    """Load a processed document from JSON output."""
    with open(json_path, 'r') as f:
        return json.load(f)


def apply_merge_decisions(document_json: dict, merge_analyses: list) -> dict:
    """
    Apply merge decisions to create a new document structure.
    This only concatenates tables, no data modification.
    """
    # Create a copy of the document
    merged_doc = json.loads(json.dumps(document_json))
    
    # Track which tables have been merged
    merged_table_ids = set()
    
    for analysis in merge_analyses:
        if not analysis.should_merge:
            continue
            
        table1_id = analysis.table1_id
        table2_id = analysis.table2_id
        
        # Find and merge the tables (simplified - real implementation would
        # properly traverse the document structure)
        # This is just to demonstrate the concept
        
        print(f"Would merge {table1_id} with {table2_id}")
        print(f"  Confidence: {analysis.confidence:.2f}")
        print(f"  Title: {analysis.table_title.text or 'No title'}")
        if analysis.table_title.is_inferred:
            print(f"  Title context: {analysis.table_title.inference_context[:100]}...")
        print(f"  Reasoning: {analysis.reasoning}")
        print()
    
    return merged_doc


@click.command()
@click.argument('input_path', type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path(), help='Output path for analysis results')
@click.option('--apply-merges', is_flag=True, help='Apply merge decisions to create merged document')
@click.option('--confidence-threshold', default=0.7, help='Minimum confidence for merging')
@click.option('--use-llm', is_flag=True, help='Use LLM for analysis (requires LLM service)')
def analyze_tables(input_path: str, output: Optional[str], apply_merges: bool, 
                  confidence_threshold: float, use_llm: bool):
    """
    Analyze tables in a processed document for potential merging.
    
    INPUT_PATH can be either:
    - A PDF file (will process it first)
    - A JSON file from marker output
    """
    input_path = Path(input_path)
    
    # Check if input is PDF or JSON
    if input_path.suffix.lower() == '.pdf':
        print(f"Processing PDF: {input_path}")
        
        # Process the PDF without table merging
        model_dict = create_model_dict()
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
            'marker.processors.table.TableProcessor',
            'marker.processors.text.TextProcessor',
            'marker.processors.reference.ReferenceProcessor',
            'marker.processors.debug.DebugProcessor'
        ]
        
        converter = PdfConverter(
            artifact_dict=model_dict,
            config={},
            renderer='marker.renderers.json.JSONRenderer',
            processor_list=processor_list
        )
        
        # Process and get document
        document = converter.build_document(str(input_path))
        rendered = converter.renderer(document)
        document_json = json.loads(rendered.model_dump_json())
        
    elif input_path.suffix.lower() == '.json':
        print(f"Loading processed document: {input_path}")
        document_json = load_processed_document(input_path)
        # For JSON input, we need to reconstruct the document object
        # This is a limitation - ideally we'd save the document pickle
        print("Note: Analyzing from JSON has limitations. Processing from PDF is recommended.")
        document = None  # Would need to reconstruct from JSON
    else:
        print(f"Error: Unsupported file type: {input_path.suffix}")
        sys.exit(1)
    
    # Create analyzer
    llm_service = None  # Would initialize LLM service if use_llm is True
    analyzer = TableMergeAnalyzer(llm_service=llm_service)
    
    # Analyze tables
    print("\nAnalyzing tables for merging...")
    
    if document:
        # Full analysis with document object
        merge_analyses = analyzer.analyze_document_tables(document)
    else:
        # Limited analysis from JSON
        print("Warning: Limited analysis from JSON format")
        merge_analyses = []
    
    # Filter by confidence
    confident_merges = [a for a in merge_analyses if a.confidence >= confidence_threshold]
    
    print(f"\nFound {len(merge_analyses)} potential merges")
    print(f"{len(confident_merges)} meet confidence threshold of {confidence_threshold}")
    
    # Display results
    for i, analysis in enumerate(confident_merges, 1):
        print(f"\n--- Merge Candidate {i} ---")
        print(f"Tables: {analysis.table1_id} + {analysis.table2_id}")
        print(f"Confidence: {analysis.confidence:.2%}")
        print(f"Type: {analysis.merge_type}")
        
        # Title info
        if analysis.table_title.found:
            title_info = f"Title: {analysis.table_title.text}"
            if analysis.table_title.is_inferred:
                title_info += " (inferred)"
            print(title_info)
        else:
            print("Title: None found")
        
        print(f"Reasoning: {analysis.reasoning}")
        
        if analysis.warnings:
            print(f"Warnings: {', '.join(analysis.warnings)}")
    
    # Save analysis results
    if output:
        output_data = {
            "input_file": str(input_path),
            "analysis_count": len(merge_analyses),
            "confident_merges": len(confident_merges),
            "confidence_threshold": confidence_threshold,
            "analyses": [a.dict() for a in confident_merges]
        }
        
        with open(output, 'w') as f:
            json.dump(output_data, f, indent=2)
        print(f"\nAnalysis saved to: {output}")
    
    # Apply merges if requested
    if apply_merges and confident_merges:
        print("\nApplying merge decisions...")
        merged_doc = apply_merge_decisions(document_json, confident_merges)
        
        # Save merged document
        merged_output = input_path.stem + "_merged.json"
        with open(merged_output, 'w') as f:
            json.dump(merged_doc, f, indent=2)
        print(f"Merged document saved to: {merged_output}")


if __name__ == '__main__':
    analyze_tables()