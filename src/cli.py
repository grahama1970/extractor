#!/usr/bin/env python3
"""
Main CLI interface for the PDF extraction system.

This module provides the command-line interface for extracting content
from PDFs and other document formats. It supports various output formats,
concurrent processing, checkpointing, and resume capabilities.

Key capabilities:
- Extract content from PDF, DOCX, PPTX, and other formats
- Multiple output formats (JSON, Markdown, RAG-optimized)
- Concurrent processing with configurable limits
- Checkpoint/resume for long-running tasks
- Dry-run mode for execution planning

AGENT VERIFICATION INSTRUCTIONS:
- Run this script directly to execute working_usage()
- The working_usage() function MUST pass all assertions
- This verifies the CLI produces expected results
- DO NOT assume the script works without running it

Third-party Documentation:
- Typer: https://typer.tiangolo.com/
- Rich: https://rich.readthedocs.io/

Example Usage:
    # Basic extraction (single CLI surface)
    python -m src.cli extract input.pdf output/

    # With options
    python -m src.cli extract input.pdf output/ --formats json,markdown --concurrency 4

Expected Output:
    {
        "status": "success",
        "files_processed": 1,
        "output_files": ["output/input.json", "output/input.md"],
        "processing_time": 15.3
    }
"""

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum

# Third-party imports
import typer
from loguru import logger
from dotenv import load_dotenv, find_dotenv
from rich.console import Console
from rich.table import Table
import subprocess
import os

# Configure logging
logger.remove()
logger.add(
    sys.stderr,
    level="INFO",
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
)

# Load environment variables
load_dotenv(find_dotenv())

# Initialize Rich console
console = Console()

# Create Typer app (low surface area; paved road defaults)
app = typer.Typer(
    name="extractor",
    help="Universal document extractor (fast vs accurate) with normalized outputs",
    add_completion=False,
)


# Output format enum
class OutputFormat(str, Enum):
    json = "json"
    markdown = "markdown"
    rag = "rag"
    structured = "structured"


# ============================================
# CORE FUNCTIONS (Outside __main__ block)
# ============================================


def validate_input_file(file_path: Path) -> tuple[bool, Optional[str]]:
    """Validate input file exists and is readable.

    Args:
        file_path: Path to input file

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not file_path.exists():
        return False, f"File not found: {file_path}"

    if not file_path.is_file():
        return False, f"Not a file: {file_path}"

    if not file_path.stat().st_size > 0:
        return False, f"Empty file: {file_path}"

    # Check file extension
    valid_extensions = {".pdf", ".docx", ".pptx", ".html", ".xml", ".epub", ".txt", ".xlsx", ".xls", ".xlsm", ".ods", ".rst", ".md"}
    if file_path.suffix.lower() not in valid_extensions:
        return False, f"Unsupported file type: {file_path.suffix}"

    return True, None


def _structured_extract(input_path: Path, out_dir: Path) -> Dict[str, Any]:
    """Route non‑PDF formats through the structured pipeline with normalized outputs.

    Produces:
      out_dir/<stem>/<stage>/json_output/07_reflowed.json and 10_flattened_data.json
    """
    from extractor.core.providers.registry import provider_from_filepath
    from extractor.pipeline.structured_pipeline import (
        run_structured_pipeline,
        STRUCTURED_PIPELINES,
    )

    provider_cls = provider_from_filepath(str(input_path))
    meta = STRUCTURED_PIPELINES.get(provider_cls)
    if not meta:
        raise RuntimeError(f"No structured pipeline registered for provider {provider_cls.__name__}")
    artifacts = run_structured_pipeline(
        provider_cls,
        input_path,
        out_dir,
        stage_prefix=meta.stage_prefix,
        skip_export10=True,
        skip_embeddings10=True,
        fast_embeddings10=True,
    )
    return {"ok": True, "artifacts": {k: str(v) for k, v in artifacts.items()}}


def save_results(results: Dict[str, Any], output_dir: Optional[Path] = None) -> Path:
    """Save processing results to JSON file.

    Args:
        results: Results dictionary
        output_dir: Optional output directory

    Returns:
        Path to saved file
    """
    if output_dir is None:
        output_dir = Path.cwd() / "tmp" / "responses"

    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"extraction_results_{timestamp}.json"
    output_path = output_dir / filename

    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, sort_keys=True)

    return output_path


# ============================================
# CLI COMMANDS
# ============================================

# Fast vs Accurate extraction modes for PDF
class Mode(str, Enum):
    fast = "fast"       # PyMuPDF path (bypass pipeline stages)
    accurate = "accurate"  # Full pipeline stages


@app.command()
def extract(
    input_file: Path = typer.Argument(..., exists=True, file_okay=True, dir_okay=False, readable=True, help="Input file (PDF or structured formats)"),
    output_dir: Path = typer.Argument(..., help="Output directory for artifacts"),
    mode: 'Mode' = typer.Option(Mode.accurate, "--mode", help="PDF only: fast (PyMuPDF) or accurate (pipeline)"),
    prove: bool = typer.Option(False, "--prove", help="Enable Lean4 proving (Stage 08) for PDF accurate runs"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging"),
):
    """Unified extraction command (low‑friction, auto‑dispatch).

    Examples:
      - PDF fast text:     `python -m src.cli extract --mode fast data.pdf out/`
      - PDF accurate:      `python -m src.cli extract --mode accurate data.pdf out/`
      - Structured (HTML): `python -m src.cli extract page.html out/`
      - Structured (DOCX): `python -m src.cli extract doc.docx out/`
    """
    if verbose:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")
    ok, msg = validate_input_file(input_file)
    if not ok:
        console.print("[red]Error:[/red] {msg}".format(msg=msg))
        raise typer.Exit(1)
    output_dir.mkdir(parents=True, exist_ok=True)

    if input_file.suffix.lower() == ".pdf":
        # Handle PDF inline to avoid ordering issues with function definitions
        output_dir.mkdir(parents=True, exist_ok=True)
        if mode == Mode.fast:
            console.print("[cyan]Running fast extraction via PyMuPDF (no heavy deps)…[/cyan]")
            try:
                from extractor.fast_extract.pymupdf_fast import extract_fast_text
                data = extract_fast_text(str(input_file))
            except Exception as e:
                console.print(f"[red]Fast extractor error:[/red] {e}")
                raise typer.Exit(1)
            out = output_dir / f"{input_file.stem}_fast.json"
            out.write_text(json.dumps(data, indent=2))
            console.print(f"[green]✓ Fast extraction complete:[/green] {out}")
            return
        console.print("[cyan]Running accurate extraction via pipeline…[/cyan]")
        # Build pipeline command directly (run_all)
        cmd = [
            sys.executable,
            "-m",
            "extractor.pipeline.run_all",
            "--pdf",
            str(input_file),
            "--results",
            str(output_dir),
            "--offline",
            "--skip-llm03",
            "--skip-descriptions06",
            "--summary-only07",
            "--skip-export10",
            "--fast-embeddings10",
        ]
        # Proving toggle
        if prove:
            # If Lean4 CLI is missing, warn and keep proving disabled
            default_lean = Path("/home/graham/workspace/experiments/lean4/src/lean4_prover/cli_mini.py")
            if default_lean.exists():
                cmd += ["--prove08"]  # inverse of --skip-proving08
                cmd += ["--lean4-cli", str(default_lean)]
            else:
                console.print("[yellow]Lean4 CLI not found; continuing without proving (install lean4_prover to enable).[/yellow]")
                cmd += ["--skip-proving08"]
        else:
            cmd += ["--skip-proving08"]
        # Always create graph edges JSON offline (no DB) after Stage 10 via offline mode
        env = os.environ.copy()
        proc = subprocess.run(cmd, env=env)
        if proc.returncode != 0:
            console.print(f"[red]Pipeline failed with exit code {proc.returncode}[/red]")
            raise typer.Exit(proc.returncode)
        console.print(f"[green]✓ Accurate extraction complete:[/green] {output_dir}")
        return

    # Structured formats (HTML/DOCX/PPTX/XLSX/EPUB/RST/XML/MD)
    try:
        result = _structured_extract(input_file, output_dir)
        arts = result.get("artifacts", {})
        console.print("[green]✓ Structured extraction complete[/green]")
        for k, v in arts.items():
            console.print(f"  • {k}: {v}")
    except Exception as e:
        console.print(f"[red]Extraction failed:[/red] {e}")
        raise typer.Exit(1)


@app.command()
def validate(input_file: Path = typer.Argument(..., help="Input file to validate")):
    """Validate input file before processing."""

    is_valid, error_msg = validate_input_file(input_file)

    if is_valid:
        # Get file info
        file_size = input_file.stat().st_size / (1024 * 1024)  # MB

        console.print("\n[green]✓ File is valid![/green]")
        console.print(f"  Path: {input_file}")
        console.print(f"  Type: {input_file.suffix}")
        console.print(f"  Size: {file_size:.2f} MB")
    else:
        console.print("\n[red]✗ Validation failed![/red]")
        console.print(f"  Error: {error_msg}")
        raise typer.Exit(1)


@app.command("list-tasks")
def list_tasks():
    """List available task templates."""

    template_dir = Path(__file__).parent.parent / "configs" / "task_templates"

    if not template_dir.exists():
        console.print("[yellow]No task templates found[/yellow]")
        return

    templates = list(template_dir.glob("*.yaml"))

    if not templates:
        console.print("[yellow]No task templates found[/yellow]")
        return

    table = Table(title="Available Task Templates")
    table.add_column("Template", style="cyan")
    table.add_column("Description", style="white")

    for template in templates:
        # In real implementation, would parse YAML for description
        table.add_row(template.stem, "Template for extraction tasks")

    console.print(table)


@app.callback()
def callback():
    """Universal document extractor with AI enhancements."""
    pass


# ============================================
# USAGE EXAMPLES (Inside __main__ block)
# ============================================


async def working_usage():
    """Known working examples that demonstrate CLI functionality.

    CRITICAL FOR AGENTS:
    - This function MUST verify that the CLI produces expected results
    - Use assertions to validate outputs match expectations
    - Return True only if ALL tests pass
    """
    logger.info("=== Running Working Usage Examples ===")

    # Create test data
    test_dir = Path(__file__).parent.parent / "test_data"
    test_dir.mkdir(exist_ok=True)

    test_pdf = test_dir / "test_document.pdf"
    test_pdf.write_text("Mock PDF content")  # Create dummy file

    output_dir = test_dir / "output"
    output_dir.mkdir(exist_ok=True)

    # Test 1: Basic extraction
    logger.info("\nTest 1: Basic file extraction")

    result = await process_file(test_pdf, output_dir, ["json", "markdown"])

    assert result["status"] == "success", "Extraction should succeed"
    assert len(result["output_files"]) == 2, "Should create 2 output files"
    assert result["processing_time"] > 0, "Should have processing time"

    logger.success("✓ Basic extraction passed")

    # Test 2: File validation
    logger.info("\nTest 2: File validation")

    is_valid, error = validate_input_file(test_pdf)
    assert is_valid, "Test file should be valid"
    assert error is None, "Should have no error"

    # Test invalid file
    invalid_file = test_dir / "nonexistent.pdf"
    is_valid, error = validate_input_file(invalid_file)
    assert not is_valid, "Nonexistent file should be invalid"
    assert "not found" in error.lower(), "Should report file not found"

    logger.success("✓ File validation passed")

    # Test 3: Results saving
    logger.info("\nTest 3: Results saving")

    results_path = save_results(result, output_dir)
    assert results_path.exists(), "Results file should be created"

    with open(results_path) as f:
        saved_results = json.load(f)

    assert saved_results["status"] == "success", "Saved results should match"

    logger.success("✓ Results saving passed")

    # Cleanup
    import shutil

    shutil.rmtree(test_dir)

    logger.success("✓ All working usage tests passed!")
    return True


async def debug_function():
    """Debug function for testing CLI features.

    AGENT: Rewrite this freely for experimentation!
    Current focus: Testing concurrent processing
    """
    logger.info("=== Running Debug Function ===")

    # Test concurrent file processing
    test_files = []
    test_dir = Path("/tmp/cli_debug")
    test_dir.mkdir(exist_ok=True)

    # Create multiple test files
    for i in range(5):
        test_file = test_dir / f"test_{i}.pdf"
        test_file.write_text(f"Test content {i}")
        test_files.append(test_file)

    # Process concurrently
    output_dir = test_dir / "output"
    output_dir.mkdir(exist_ok=True)

    start_time = time.time()

    tasks = [process_file(f, output_dir, ["json"]) for f in test_files]

    results = await asyncio.gather(*tasks)

    duration = time.time() - start_time

    logger.info(f"Processed {len(results)} files in {duration:.2f}s")
    logger.info(f"Rate: {len(results)/duration:.1f} files/sec")

    # Verify all succeeded
    assert all(r["status"] == "success" for r in results), "All should succeed"

    # Cleanup
    import shutil

    shutil.rmtree(test_dir)

    return True


async def stress_test():
    """Run stress tests for CLI performance."""
    logger.info("=== Running Stress Tests ===")

    # Would load stress test configurations
    # For now, just run a simple test

    test_dir = Path("/tmp/cli_stress")
    test_dir.mkdir(exist_ok=True)

    # Create large test file
    large_file = test_dir / "large_test.pdf"
    large_file.write_bytes(b"x" * (10 * 1024 * 1024))  # 10MB

    output_dir = test_dir / "output"
    output_dir.mkdir(exist_ok=True)

    # Test processing
    result = await process_file(large_file, output_dir, ["json"])

    assert result["status"] == "success", "Should handle large files"

    # Cleanup
    import shutil

    shutil.rmtree(test_dir)

    logger.success("✓ Stress tests passed")
    return True


if __name__ == "__main__":
    """
    Script entry point with triple-mode execution.

    Usage:
        python -m src.cli              # Runs working_usage() - stable tests
        python -m src.cli debug        # Runs debug_function() - experimental
        python -m src.cli stress       # Runs stress_test() - load tests
        python -m src.cli [command]    # Run CLI commands
    """

    if len(sys.argv) > 1:
        if sys.argv[1] == "debug":
            logger.info("Running in DEBUG mode...")
            asyncio.run(debug_function())
            exit(0)
        elif sys.argv[1] == "stress":
            logger.info("Running in STRESS TEST mode...")
            asyncio.run(stress_test())
            exit(0)
        elif sys.argv[1] in ["extract", "validate", "list-tasks", "--help"]:
            # Run normal CLI
            app()
            exit(0)

    # Default: run working usage
    logger.info("Running in WORKING mode...")
    success = asyncio.run(working_usage())
    exit(0 if success else 1)
@app.command("extract-pdf")
def extract_pdf_deprecated(*_: str):
    """Deprecated shim. Use: `python -m src.cli extract`.

    This command intentionally exits non‑zero to steer users to the single CLI surface.
    """
    typer.secho(
        "[deprecated] Use: python -m src.cli extract <input> <out_dir> [--mode fast|accurate]",
        fg=typer.colors.YELLOW,
    )
    raise typer.Exit(2)
