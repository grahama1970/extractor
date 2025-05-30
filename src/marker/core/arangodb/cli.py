"""
CLI commands for ArangoDB-Marker integration.

This module provides CLI commands for ArangoDB-Marker integration, including
document import and QA generation.

Example usage:
    ```bash
    # Import Marker output to ArangoDB
    python -m marker.arangodb.cli import-marker document.json --host localhost --db documents
    
    # Generate QA pairs from Marker output
    python -m marker.arangodb.cli qa-generation from-marker document.json --max-questions 20
    ```
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import List, Optional

import typer
from loguru import logger

from marker.core.arangodb.importers import document_to_arangodb
from marker.core.arangodb.qa_generator import (
    generate_qa_pairs, DEFAULT_MAX_QUESTIONS, DEFAULT_QUESTION_TYPES, 
    DEFAULT_MIN_LENGTH_THRESHOLD, DEFAULT_EXPORT_FORMATS
)
from marker.core.arangodb.validators import (
    validate_qa_pairs, generate_validation_report,
    DEFAULT_VALIDATION_CHECKS, DEFAULT_RELEVANCE_THRESHOLD,
    DEFAULT_ACCURACY_THRESHOLD, DEFAULT_QUESTION_QUALITY_THRESHOLD
)


# Create Typer app
app = typer.Typer(
    name="arangodb",
    help="ArangoDB integration for Marker",
    add_completion=False
)

# Create subcommands
import_app = typer.Typer(
    name="import",
    help="Import commands for ArangoDB"
)

qa_app = typer.Typer(
    name="qa-generation",
    help="QA generation commands for ArangoDB"
)

validate_app = typer.Typer(
    name="validate-qa",
    help="QA validation commands for ArangoDB"
)

# Add subcommands to main app
app.add_typer(import_app, name="import")
app.add_typer(qa_app, name="qa-generation")
app.add_typer(validate_app, name="validate-qa")


@import_app.command("from-marker")
def import_from_marker(
    input_file: str = typer.Argument(..., help="Path to Marker JSON output file"),
    host: str = typer.Option(
        os.environ.get("ARANGO_HOST", "localhost"),
        "--host",
        help="ArangoDB host"
    ),
    port: int = typer.Option(
        int(os.environ.get("ARANGO_PORT", "8529")),
        "--port",
        help="ArangoDB port"
    ),
    db_name: str = typer.Option(
        os.environ.get("ARANGO_DB", "documents"),
        "--db",
        help="ArangoDB database name"
    ),
    username: str = typer.Option(
        os.environ.get("ARANGO_USERNAME", "root"),
        "--user",
        help="ArangoDB username"
    ),
    password: str = typer.Option(
        os.environ.get("ARANGO_PASSWORD", ""),
        "--password",
        help="ArangoDB password"
    ),
    batch_size: int = typer.Option(
        100,
        "--batch-size",
        help="Batch size for imports"
    ),
    skip_graph: bool = typer.Option(
        False,
        "--skip-graph",
        help="Skip graph creation"
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Verbose output"
    )
):
    """
    Import Marker output to ArangoDB.
    
    This command imports Marker output from a JSON file to ArangoDB,
    creating document, page, section, and content nodes, as well as
    relationship edges.
    """
    # Configure logger
    log_level = "DEBUG" if verbose else "INFO"
    logger.remove()
    logger.add(sys.stderr, level=log_level)
    logger.add("arangodb_import.log", rotation="10 MB")
    
    try:
        # Load Marker output
        logger.info(f"Loading Marker output from {input_file}")
        with open(input_file, "r", encoding="utf-8") as f:
            marker_output = json.load(f)
        
        # Import to ArangoDB
        logger.info(f"Importing to ArangoDB ({host}:{port}/{db_name})")
        start_time = time.time()
        doc_id, stats = document_to_arangodb(
            marker_output,
            db_host=host,
            db_port=port,
            db_name=db_name,
            username=username,
            password=password,
            batch_size=batch_size,
            create_graph=not skip_graph
        )
        import_time = time.time() - start_time
        
        # Log results
        logger.success(f"Import completed successfully in {import_time:.2f} seconds")
        logger.info(f"Document ID: {doc_id}")
        logger.info(f"Pages: {stats['page_count']}")
        logger.info(f"Sections: {stats['section_count']}")
        logger.info(f"Content blocks: {stats['content_count']}")
        logger.info(f"Relationships: {stats['relationship_count']}")
        
        # Return success
        return 0
    except Exception as e:
        logger.error(f"Error importing to ArangoDB: {str(e)}")
        if verbose:
            import traceback
            logger.error(traceback.format_exc())
        return 1


@qa_app.command("from-marker")
def qa_from_marker(
    input_file: str = typer.Argument(..., help="Path to Marker JSON output file"),
    output_dir: str = typer.Option(
        "qa_output",
        "--output-dir",
        "-o",
        help="Output directory for QA pairs"
    ),
    max_questions: int = typer.Option(
        DEFAULT_MAX_QUESTIONS,
        "--max-questions",
        "-m",
        help="Maximum number of questions to generate"
    ),
    question_types: str = typer.Option(
        ",".join(DEFAULT_QUESTION_TYPES),
        "--question-types",
        "-t",
        help="Comma-separated question types to generate"
    ),
    min_length: int = typer.Option(
        DEFAULT_MIN_LENGTH_THRESHOLD,
        "--min-length",
        help="Minimum text length for contexts"
    ),
    export_formats: str = typer.Option(
        ",".join(DEFAULT_EXPORT_FORMATS),
        "--export-formats",
        "-f",
        help="Comma-separated export formats"
    ),
    seed: Optional[int] = typer.Option(
        None,
        "--seed",
        help="Random seed for reproducibility"
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Verbose output"
    )
):
    """
    Generate QA pairs from Marker output.
    
    This command generates question-answer pairs from Marker output,
    using the document content, structure, and section context. The
    generated QA pairs are exported to files in various formats.
    """
    # Configure logger
    log_level = "DEBUG" if verbose else "INFO"
    logger.remove()
    logger.add(sys.stderr, level=log_level)
    logger.add("qa_generation.log", rotation="10 MB")
    
    try:
        # Parse question types and export formats
        qt_list = [qt.strip() for qt in question_types.split(",") if qt.strip()]
        fmt_list = [fmt.strip() for fmt in export_formats.split(",") if fmt.strip()]
        
        # Generate QA pairs
        logger.info(f"Generating QA pairs from {input_file}")
        logger.info(f"Max questions: {max_questions}")
        logger.info(f"Question types: {qt_list}")
        logger.info(f"Export formats: {fmt_list}")
        
        start_time = time.time()
        qa_pairs, stats = generate_qa_pairs(
            marker_output_path=input_file,
            output_dir=output_dir,
            max_questions=max_questions,
            question_types=qt_list,
            export_formats=fmt_list,
            min_length=min_length,
            random_seed=seed
        )
        generation_time = time.time() - start_time
        
        # Log results
        logger.success(f"QA generation completed successfully in {generation_time:.2f} seconds")
        logger.info(f"Document: {stats['document_title']} ({stats['document_id']})")
        logger.info(f"Generated {stats['qa_pairs_generated']} QA pairs")
        logger.info(f"Question types: {stats['question_type_counts']}")
        logger.info(f"Source types: {stats['source_type_counts']}")
        
        # Log output files
        for fmt, path in stats['output_files'].items():
            logger.info(f"Output file ({fmt}): {path}")
        
        # Return success
        return 0
    except Exception as e:
        logger.error(f"Error generating QA pairs: {str(e)}")
        if verbose:
            import traceback
            logger.error(traceback.format_exc())
        return 1


@validate_app.command("from-jsonl")
def validate_from_jsonl(
    qa_pairs_file: str = typer.Argument(..., help="Path to QA pairs JSONL file"),
    marker_output: Optional[str] = typer.Option(
        None,
        "--marker-output",
        "-m",
        help="Path to Marker JSON output file for relevance and accuracy checks"
    ),
    output: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Path to write validation results (JSON format)"
    ),
    report: Optional[str] = typer.Option(
        None,
        "--report",
        "-r",
        help="Path to write validation report (Markdown format)"
    ),
    checks: str = typer.Option(
        ",".join(DEFAULT_VALIDATION_CHECKS),
        "--checks",
        "-c",
        help="Comma-separated list of validation checks to perform"
    ),
    relevance_threshold: float = typer.Option(
        DEFAULT_RELEVANCE_THRESHOLD,
        "--relevance-threshold",
        help="Threshold for relevance validation"
    ),
    accuracy_threshold: float = typer.Option(
        DEFAULT_ACCURACY_THRESHOLD,
        "--accuracy-threshold",
        help="Threshold for accuracy validation"
    ),
    quality_threshold: float = typer.Option(
        DEFAULT_QUESTION_QUALITY_THRESHOLD,
        "--quality-threshold",
        help="Threshold for quality validation"
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Verbose output"
    )
):
    """
    Validate QA pairs from a JSONL file.
    
    This command validates QA pairs against various criteria including
    relevance to document content, answer accuracy, question quality,
    and question diversity.
    """
    # Configure logger
    log_level = "DEBUG" if verbose else "INFO"
    logger.remove()
    logger.add(sys.stderr, level=log_level)
    logger.add("qa_validation.log", rotation="10 MB")
    
    try:
        # Parse checks
        checks_list = [check.strip() for check in checks.split(",") if check.strip()]
        
        # Check if marker output is needed but not provided
        if ("relevance" in checks_list or "accuracy" in checks_list) and not marker_output:
            logger.warning("Marker output is required for relevance and accuracy checks")
            logger.warning("These checks will be skipped")
            checks_list = [check for check in checks_list if check not in ["relevance", "accuracy"]]
        
        # Validate QA pairs
        logger.info(f"Validating QA pairs from {qa_pairs_file}")
        logger.info(f"Performing checks: {', '.join(checks_list)}")
        
        start_time = time.time()
        validation_results = validate_qa_pairs(
            qa_pairs_path=qa_pairs_file,
            marker_output_path=marker_output,
            checks=checks_list,
            relevance_threshold=relevance_threshold,
            accuracy_threshold=accuracy_threshold,
            quality_threshold=quality_threshold,
            output_path=output
        )
        validation_time = time.time() - start_time
        
        # Log results
        if validation_results["status"] == "success":
            logger.success("Validation completed successfully")
            logger.info(f"Total QA pairs: {validation_results['total_qa_pairs']}")
            logger.info(f"Passing QA pairs: {validation_results['passing_qa_pairs']} ({validation_results['passing_percentage']:.1f}%)")
            logger.info(f"Failing QA pairs: {validation_results['failing_qa_pairs']}")
            logger.info(f"Validation time: {validation_time:.2f} seconds")
            
            # Log check-specific results
            for check, results in validation_results["results_by_check"].items():
                total = results["passed"] + results["failed"]
                pass_percentage = (results["passed"] / total) * 100 if total > 0 else 0
                logger.info(f"{check.capitalize()}: {results['passed']}/{total} passed ({pass_percentage:.1f}%), avg score: {results['average_score']:.2f}")
            
            # Generate report if requested
            if report:
                report_text = generate_validation_report(validation_results, report)
                logger.info(f"Generated validation report: {report}")
            
            # Return success
            return 0
        else:
            logger.error(f"Validation failed: {validation_results.get('message', 'Unknown error')}")
            return 1
    except Exception as e:
        logger.error(f"Error validating QA pairs: {str(e)}")
        if verbose:
            import traceback
            logger.error(traceback.format_exc())
        return 1


@app.callback()
def main():
    """
    ArangoDB integration for Marker.
    
    This CLI provides commands for integrating Marker with ArangoDB,
    including document import, QA generation, and QA validation.
    """
    pass


if __name__ == "__main__":
    app()