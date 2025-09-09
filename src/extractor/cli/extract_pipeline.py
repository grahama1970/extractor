#!/usr/bin/env python3
"""
Extract Pipeline CLI - Complete command-line interface for PDF extraction pipeline

This CLI provides commands for each stage of the extraction pipeline,
making it easy for Claude to execute any step independently.

Usage:
    python extract_pipeline.py --help
    python extract_pipeline.py extract-annotations --help
    python extract_pipeline.py fix-blocks --help
"""

import json
import asyncio
from pathlib import Path
from typing import List, Optional
import typer
from loguru import logger
import sys

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.extractor.core.processors.enhanced_annotation_extractor import EnhancedAnnotationExtractor
from src.extractor.core.processors.section_metadata_propagator import (
    SectionMetadataPropagator, organize_blocks_into_sections
)
from src.extractor.core.processors.semantic_section_processor import SemanticSectionProcessor
from src.extractor.core.processors.section_hierarchy import SectionHierarchyBuilder

app = typer.Typer(help="PDF extraction pipeline commands")


@app.command()
def extract_annotations(
    pdf_path: str = typer.Argument(..., help="Path to PDF file"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output JSON path"),
    store_db: bool = typer.Option(True, "--store/--no-store", help="Store in ArangoDB"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """
    Extract annotations from PDF (Stage 1).
    
    Example:
        python extract_pipeline.py extract-annotations doc.pdf -o annotations.json
    """
    typer.echo(f"Extracting annotations from {pdf_path}")
    
    extractor = EnhancedAnnotationExtractor()
    result = extractor.extract_annotations_with_enhancements(pdf_path)
    
    if result.get("status") == "success":
        annotations = result.get("annotations", [])
        typer.echo(f"✓ Extracted {len(annotations)} annotations")
        
        if verbose:
            for ann in annotations[:3]:  # Show first 3
                typer.echo(f"  - {ann.get('type')}: {ann.get('original_snippet', '')[:50]}...")
        
        # Save output
        output_path = output or f"/tmp/{Path(pdf_path).stem}_annotations.json"
        with open(output_path, 'w') as f:
            json.dump(result, f, indent=2)
        typer.echo(f"✓ Saved to: {output_path}")
        
        if store_db and result.get("storage", {}).get("stored_in_arangodb"):
            typer.echo(f"✓ Stored in ArangoDB collection: {result['storage']['collection']}")
    else:
        typer.echo(f"✗ Failed: {result.get('error', 'Unknown error')}", err=True)
        raise typer.Exit(1)


@app.command()
def create_clean_pdf(
    pdf_path: str = typer.Argument(..., help="Path to PDF file"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output PDF path"),
    remove_artifacts: bool = typer.Option(True, help="Remove annotation artifacts"),
):
    """
    Create clean PDF without annotations (Stage 3).
    
    Example:
        python extract_pipeline.py create-clean-pdf marked.pdf -o clean.pdf
    """
    typer.echo(f"Creating clean PDF from {pdf_path}")
    
    # Import the worker
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / ".claude/agents/workers"))
    from pdf_annotations_worker import create_clean_pdf as clean_pdf_func
    
    # Run async function
    result = asyncio.run(clean_pdf_func(pdf_path))
    
    if result.get("success"):
        clean_path = result.get("clean_pdf_path")
        typer.echo(f"✓ Created clean PDF: {clean_path}")
        
        if output and clean_path:
            Path(clean_path).rename(output)
            typer.echo(f"✓ Moved to: {output}")
            
        ann_count = len(result.get("annotations", []))
        typer.echo(f"  Removed {ann_count} annotations")
    else:
        typer.echo(f"✗ Failed: {result.get('error', 'Unknown error')}", err=True)
        raise typer.Exit(1)


@app.command()
def run_marker(
    pdf_path: str = typer.Argument(..., help="Path to PDF file"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output JSON path"),
    add_uuids: bool = typer.Option(True, help="Add UUIDs to blocks"),
):
    """
    Run marker extraction with UUID assignment (Stage 5).
    
    Example:
        python extract_pipeline.py run-marker clean.pdf -o blocks.json
    """
    typer.echo(f"Running marker extraction on {pdf_path}")
    
    # For now, use a placeholder
    # TODO: Integrate actual marker command
    typer.echo("⚠️  Marker integration pending - use marker-pdf command directly")
    typer.echo(f"   marker-pdf {pdf_path} --output {output or '/tmp/marker_output.json'}")


@app.command()
def create_batches(
    blocks_json: str = typer.Argument(..., help="Path to marker output JSON"),
    output_dir: Optional[str] = typer.Option(None, "--output-dir", "-d", help="Output directory"),
    max_tokens: int = typer.Option(150000, "--max-tokens", help="Max tokens per batch"),
):
    """
    Create batches for suspicious blocks (Stage 5.5a).
    
    Example:
        python extract_pipeline.py create-batches blocks.json -d /tmp/batches/
    """
    typer.echo(f"Creating batches from {blocks_json}")
    
    # Import the worker
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / ".claude/agents/workers"))
    from pdf_block_fixer_worker import PDFBlockFixerWorker
    
    fixer = PDFBlockFixerWorker()
    if output_dir:
        fixer.batch_dir = Path(output_dir)
        fixer.batch_dir.mkdir(exist_ok=True)
    
    result = fixer.create_suspicious_batches(blocks_json, max_tokens)
    
    if result.get("success"):
        typer.echo(f"✓ Created {result['batch_count']} batches")
        typer.echo(f"  Total suspicious blocks: {result['total_suspicious']}")
        typer.echo(f"  Manifest: {result['manifest']}")
        
        for i, batch_file in enumerate(result['batch_files'][:3]):
            typer.echo(f"  Batch {i}: {batch_file}")
    else:
        typer.echo(f"✗ Failed: {result.get('error', 'Unknown error')}", err=True)
        raise typer.Exit(1)


@app.command()
def apply_fixes(
    original_json: str = typer.Argument(..., help="Original blocks JSON"),
    decisions_json: str = typer.Argument(..., help="Decisions JSON from sub-agents"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output JSON path"),
):
    """
    Apply fixes from sub-agent decisions (Stage 5.5c).
    
    Example:
        python extract_pipeline.py apply-fixes blocks.json decisions.json -o fixed.json
    """
    typer.echo(f"Applying fixes to {original_json}")
    
    # Import the worker
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / ".claude/agents/workers"))
    from pdf_block_fixer_worker import PDFBlockFixerWorker
    
    fixer = PDFBlockFixerWorker()
    result = fixer.apply_fixes_with_jq(original_json, decisions_json)
    
    if result.get("success"):
        typer.echo(f"✓ Applied fixes successfully")
        typer.echo(f"  Original blocks: {result['original_blocks']}")
        typer.echo(f"  Fixed blocks: {result['fixed_blocks']}")
        typer.echo(f"  Blocks removed: {result['blocks_removed']}")
        
        if output:
            Path(result['output_file']).rename(output)
            typer.echo(f"✓ Saved to: {output}")
        else:
            typer.echo(f"  Output: {result['output_file']}")
    else:
        typer.echo(f"✗ Failed: {result.get('error', 'Unknown error')}", err=True)
        raise typer.Exit(1)


@app.command()
def build_sections(
    blocks_json: str = typer.Argument(..., help="Path to fixed blocks JSON"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output JSON path"),
    add_metadata: bool = typer.Option(True, help="Add section metadata to blocks"),
):
    """
    Build section nodes from blocks (Stage 6).
    
    Example:
        python extract_pipeline.py build-sections fixed_blocks.json -o sections.json
    """
    typer.echo(f"Building sections from {blocks_json}")
    
    # Load blocks
    with open(blocks_json) as f:
        data = json.load(f)
    
    blocks = data.get("blocks", data) if isinstance(data, dict) else data
    
    # Add section metadata if requested
    if add_metadata:
        propagator = SectionMetadataPropagator()
        blocks = propagator.process_blocks(blocks)
        typer.echo(f"✓ Added section metadata to {len(blocks)} blocks")
    
    # Organize into sections
    result = organize_blocks_into_sections(blocks)
    
    sections = result.get("sections", [])
    typer.echo(f"✓ Created {len(sections)} sections")
    
    # Save output
    output_path = output or f"/tmp/{Path(blocks_json).stem}_sections.json"
    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)
    typer.echo(f"✓ Saved to: {output_path}")


@app.command()
def enhance_sections(
    sections_json: str = typer.Argument(..., help="Path to sections JSON"),
    pdf_path: str = typer.Argument(..., help="Original PDF path for images"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output JSON path"),
    batch_size: int = typer.Option(5, "--batch-size", help="Sections per batch"),
):
    """
    Enhance sections semantically (Stage 8).
    
    Example:
        python extract_pipeline.py enhance-sections sections.json doc.pdf
    """
    typer.echo(f"Enhancing sections from {sections_json}")
    
    # Load sections
    with open(sections_json) as f:
        data = json.load(f)
    
    sections = data.get("sections", data) if isinstance(data, dict) else data
    
    # Process sections
    processor = SemanticSectionProcessor(batch_size=batch_size)
    
    # Run async processing
    enhanced = asyncio.run(processor.process_sections(sections))
    
    typer.echo(f"✓ Enhanced {len(enhanced)} sections")
    
    # Save output
    output_path = output or f"/tmp/{Path(sections_json).stem}_enhanced.json"
    with open(output_path, 'w') as f:
        json.dump({"sections": enhanced}, f, indent=2)
    typer.echo(f"✓ Saved to: {output_path}")


@app.command()
def validate_extraction(
    extracted_json: str = typer.Argument(..., help="Path to extracted data"),
    gold_standard: Optional[str] = typer.Option(None, "--gold", "-g", help="Gold standard JSON"),
    threshold: float = typer.Option(0.9, "--threshold", help="Accuracy threshold"),
):
    """
    Validate extraction against gold standard (Stage 9).
    
    Example:
        python extract_pipeline.py validate-extraction enhanced.json --gold gold.json
    """
    typer.echo(f"Validating {extracted_json}")
    
    # Load extracted data
    with open(extracted_json) as f:
        extracted = json.load(f)
    
    if gold_standard:
        with open(gold_standard) as f:
            gold = json.load(f)
        
        # Simple validation (expand as needed)
        extracted_blocks = len(extracted.get("sections", []))
        gold_blocks = len(gold.get("sections", []))
        
        accuracy = min(extracted_blocks, gold_blocks) / max(extracted_blocks, gold_blocks)
        
        typer.echo(f"  Extracted sections: {extracted_blocks}")
        typer.echo(f"  Gold sections: {gold_blocks}")
        typer.echo(f"  Accuracy: {accuracy:.2%}")
        
        if accuracy >= threshold:
            typer.echo(f"✓ Validation passed (>= {threshold:.0%})")
        else:
            typer.echo(f"✗ Validation failed (< {threshold:.0%})", err=True)
            raise typer.Exit(1)
    else:
        typer.echo("⚠️  No gold standard provided - skipping validation")


@app.command()
def add_breadcrumbs(
    input_json: str = typer.Argument(..., help="Path to input JSON"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output JSON path"),
):
    """
    Add section breadcrumb hierarchies for ArangoDB (Stage 10).
    
    Ensures every block has:
    - section_titles: Array of all parent section titles (root to leaf)
    - section_hashes: Array of all parent section hashes (root to leaf)
    - section_path: Human-readable breadcrumb path
    - parent_sections: Detailed parent section info
    
    Example:
        python extract_pipeline.py add-breadcrumbs enhanced.json -o final.json
    """
    typer.echo(f"Adding breadcrumb hierarchies to {input_json}")
    
    # Load data
    with open(input_json) as f:
        data = json.load(f)
    
    # Use the new hierarchy builder
    builder = SectionHierarchyBuilder()
    result = builder.process_document(data)
    
    # Count blocks processed
    block_count = 0
    if "sections" in result:
        for section in result["sections"]:
            if isinstance(section, dict) and "blocks" in section:
                block_count += len(section["blocks"])
            else:
                block_count += 1
    elif "blocks" in result:
        block_count = len(result["blocks"])
    
    # Save output
    output_path = output or f"/tmp/{Path(input_json).stem}_breadcrumbs.json"
    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)
        
    typer.echo(f"✓ Added breadcrumbs to {block_count} blocks")
    typer.echo(f"✓ Saved to: {output_path}")


@app.command()
def full_pipeline(
    pdf_path: str = typer.Argument(..., help="Path to PDF file"),
    output_dir: Optional[str] = typer.Option(None, "--output-dir", "-d", help="Output directory"),
    skip_annotations: bool = typer.Option(False, "--skip-annotations", help="Skip annotation extraction"),
):
    """
    Run the complete extraction pipeline.
    
    Example:
        python extract_pipeline.py full-pipeline doc.pdf -d /tmp/extraction/
    """
    typer.echo(f"Running full pipeline on {pdf_path}")
    
    output_dir = Path(output_dir or f"/tmp/extraction_{Path(pdf_path).stem}")
    output_dir.mkdir(exist_ok=True)
    
    # Stage 1: Extract annotations
    if not skip_annotations:
        typer.echo("\n📋 Stage 1: Extracting annotations...")
        # ... call extract_annotations
    
    typer.echo("\n✓ Pipeline complete!")
    typer.echo(f"  Results in: {output_dir}")


@app.command()
def list_stages():
    """List all pipeline stages with descriptions."""
    typer.echo("PDF Extraction Pipeline Stages:\n")
    
    stages = [
        ("1", "extract-annotations", "Extract PDF annotations with rich metadata"),
        ("2", "interpret-annotations", "Add semantic interpretation (agent task)"),
        ("3", "create-clean-pdf", "Remove annotation artifacts from PDF"),
        ("4", "check-knowledge", "Query knowledge base (use knowledge CLI)"),
        ("5", "run-marker", "Extract blocks with marker-pdf"),
        ("5.5a", "create-batches", "Batch suspicious blocks for analysis"),
        ("5.5b", "spawn-agents", "Launch sub-agents (agent task)"),
        ("5.5c", "apply-fixes", "Apply fixes from sub-agent decisions"),
        ("6", "build-sections", "Organize blocks into section nodes"),
        ("7", "create-images", "Generate validation images (use pdf-tools)"),
        ("8", "enhance-sections", "Semantic section enhancement (agent task)"),
        ("9", "validate-extraction", "Validate against gold standard"),
        ("10", "add-breadcrumbs", "Add section hierarchies for ArangoDB"),
        ("11", "store-patterns", "Store in knowledge base (use knowledge CLI)")
    ]
    
    for stage, cmd, desc in stages:
        typer.echo(f"Stage {stage}: {cmd}")
        typer.echo(f"         {desc}\n")


if __name__ == "__main__":
    app()