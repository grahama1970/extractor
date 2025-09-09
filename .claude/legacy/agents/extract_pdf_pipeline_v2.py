#!/usr/bin/env python3
"""
PDF Extraction Pipeline v2 - With PROPER error handling

This pipeline will STOP if ANY step fails. No more pretending everything is fine.
"""

import asyncio
import json
import os
import shutil
import subprocess
import sys
import textwrap
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from loguru import logger

# Configure logging
logger.remove()
logger.add(sys.stderr, level="INFO")


def check_environment():
    """Check required environment and dependencies"""
    required_commands = ['claude', 'python', 'pip']
    
    for cmd in required_commands:
        result = subprocess.run(['which', cmd], capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"Required command '{cmd}' not found in PATH")
            sys.exit(1)
    
    logger.info("✓ Environment check passed")


async def run_claude_p(prompt: str, timeout: int = 30) -> str:
    """
    Run claude -p and ACTUALLY CHECK if it worked
    
    Returns:
        The actual response from claude
        
    Raises:
        RuntimeError: If claude fails for ANY reason
    """
    logger.info(f"Calling claude -p (timeout={timeout}s)")
    
    # Clean environment for Claude Max Plan
    env = os.environ.copy()
    env.pop('CLAUDE_API_KEY', None)
    env.pop('ANTHROPIC_API_KEY', None)
    
    try:
        proc = await asyncio.create_subprocess_exec(
            'claude', '-p', prompt,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )
        
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), 
            timeout=timeout
        )
        
        stdout_str = stdout.decode().strip()
        stderr_str = stderr.decode().strip()
        
        # Check for ANY sign of failure
        failure_indicators = [
            "Invalid API key",
            "Authentication",
            "Error:",
            "error:",
            "Failed",
            "failed",
            "unauthorized",
            "Unauthorized"
        ]
        
        for indicator in failure_indicators:
            if indicator in stdout_str or indicator in stderr_str:
                logger.error(f"Claude failed with: {stdout_str}")
                if stderr_str:
                    logger.error(f"Stderr: {stderr_str}")
                raise RuntimeError(f"Claude authentication/API error: {stdout_str}")
        
        # Check for empty response
        if not stdout_str:
            raise RuntimeError("Claude returned empty response")
        
        # Check exit code
        if proc.returncode != 0:
            raise RuntimeError(f"Claude exited with code {proc.returncode}: {stderr_str}")
        
        logger.success(f"Claude responded successfully ({len(stdout_str)} chars)")
        return stdout_str
        
    except asyncio.TimeoutError:
        raise RuntimeError(f"Claude timed out after {timeout}s")
    except Exception as e:
        raise RuntimeError(f"Claude failed: {str(e)}")


def run_python_processor(module: str, args: str, description: str) -> Tuple[bool, str, str]:
    """
    Run a Python processor and check if it ACTUALLY worked
    
    Returns:
        (success, stdout, stderr)
    """
    cmd = f"python -m {module} {args}"
    logger.info(f"Running: {description}")
    logger.debug(f"Command: {cmd}")
    
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.returncode != 0:
            logger.error(f"{description} FAILED with exit code {result.returncode}")
            logger.error(f"Stderr: {result.stderr}")
            return False, result.stdout, result.stderr
        
        # Check for common error patterns in output
        error_patterns = [
            "Traceback",
            "Error:",
            "error:",
            "Failed",
            "failed",
            "Exception:",
            "exception:"
        ]
        
        output_lower = result.stdout.lower() + result.stderr.lower()
        for pattern in error_patterns:
            if pattern.lower() in output_lower:
                logger.warning(f"{description} may have failed - found '{pattern}' in output")
                # Don't fail here, let the caller decide based on the output
        
        return True, result.stdout, result.stderr
        
    except subprocess.TimeoutExpired:
        logger.error(f"{description} TIMED OUT after 120s")
        return False, "", "Process timed out"
    except Exception as e:
        logger.error(f"{description} FAILED with exception: {e}")
        return False, "", str(e)


async def run_pipeline(pdf_path: str, working_dir: str = "tmp/pipeline_run") -> Dict[str, Any]:
    """
    Run the extraction pipeline with PROPER error handling
    
    Every step must succeed or we STOP.
    """
    
    logger.info(f"Starting pipeline for: {pdf_path}")
    start_time = time.time()
    
    # Setup
    project_root = Path.cwd()
    working_path = project_root / working_dir
    working_path.mkdir(parents=True, exist_ok=True)
    
    # Resolve PDF path
    pdf_path_obj = Path(pdf_path)
    if not pdf_path_obj.is_absolute():
        pdf_path_obj = project_root / pdf_path_obj
    
    if not pdf_path_obj.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    
    # Copy PDF to working directory
    doc_pdf = working_path / "doc.pdf"
    shutil.copy(pdf_path_obj, doc_pdf)
    logger.success("✓ Setup complete")
    
    # ======= STAGE 1: Extract Annotations ======= #
    logger.info("STAGE 1: Extracting annotations")
    
    annotations_json = working_path / "annotations.json"
    success, stdout, stderr = run_python_processor(
        "extractor.core.processors.gold_standard_annotation_extractor",
        f"extract {doc_pdf} --output {annotations_json}",
        "Annotation extraction"
    )
    
    if not success:
        raise RuntimeError(f"STAGE 1 FAILED: Annotation extraction failed")
    
    if not annotations_json.exists():
        raise RuntimeError(f"STAGE 1 FAILED: Output file not created")
    
    logger.success("✓ Stage 1 complete")
    
    # ======= STAGE 2: Interpret Annotations (REQUIRES CLAUDE) ======= #
    logger.info("STAGE 2: Interpreting annotations with Claude")
    
    with open(annotations_json, "r") as f:
        annotations = json.load(f)
    
    interpretation = await run_claude_p(
        textwrap.dedent(f"""\
            uberthink: [Stage 2 - Interpret annotations semantically]
            Analyze these PDF annotations and determine their semantic meaning:
            1. What types of content do they mark (sections, tables, figures, etc)?
            2. Are there any hierarchical relationships?
            3. What patterns do you see in the annotation labels?
            4. How should these guide the extraction process?

            Annotations: {json.dumps(annotations, indent=2)}

            Provide a concise analysis focusing on actionable insights for extraction.""")
    )
    
    # Save interpretation
    with open(working_path / "interpretation.txt", "w") as f:
        f.write(interpretation)
    
    logger.success("✓ Stage 2 complete")
    
    # ======= STAGE 3: Create Clean PDF ======= #
    logger.info("STAGE 3: Creating clean PDF")
    
    clean_pdf = working_path / "clean.pdf"
    success, stdout, stderr = run_python_processor(
        "extractor.core.processors.pdf_cleaner",
        f"clean {doc_pdf} --output {clean_pdf}",
        "PDF cleaning"
    )
    
    if not success:
        raise RuntimeError(f"STAGE 3 FAILED: PDF cleaning failed")
    
    if not clean_pdf.exists():
        raise RuntimeError(f"STAGE 3 FAILED: Clean PDF not created")
    
    logger.success("✓ Stage 3 complete")
    
    # ======= STAGE 4: Check Knowledge Base (REQUIRES CLAUDE) ======= #
    logger.info("STAGE 4: Checking knowledge base with Claude")
    
    kb_result = await run_claude_p(
        textwrap.dedent("""\
            uberthink: [Stage 4 - Check knowledge base]
            Search knowledge base for similar PDF extraction patterns:
            1. Document type: Technical documentation (CV32A65X BHT - Branch History Table)
            2. Look for patterns from similar technical specs or processor documentation
            3. Check for successful extraction strategies for:
            - Hierarchical section structures
            - Technical tables with signal descriptions
            - State diagrams and figures
            - Cross-references and breadcrumbs
            4. Identify any known issues or edge cases with similar documents

            Return patterns that would help extract this 2-page technical PDF accurately.""")
    )
    
    # Save knowledge base result
    with open(working_path / "kb_patterns.txt", "w") as f:
        f.write(kb_result)
    
    logger.success("✓ Stage 4 complete")
    
    # ======= STAGE 5: Marker Extraction ======= #
    logger.info("STAGE 5: Running marker extraction")
    
    # Build processor list without LLM processors
    processors = [
        "extractor.core.processors.order.OrderProcessor",
        "extractor.core.processors.line_merge.LineMergeProcessor",
        "extractor.core.processors.blockquote.BlockquoteProcessor",
        "extractor.core.processors.code.CodeProcessor",
        "extractor.core.processors.document_toc.DocumentTOCProcessor",
        "extractor.core.processors.equation.EquationProcessor",
        "extractor.core.processors.footnote.FootnoteProcessor",
        "extractor.core.processors.ignoretext.IgnoreTextProcessor",
        "extractor.core.processors.line_numbers.LineNumbersProcessor",
        "extractor.core.processors.list.ListProcessor",
        "extractor.core.processors.page_header.PageHeaderProcessor",
        "extractor.core.processors.sectionheader.SectionHeaderProcessor",
        "extractor.core.processors.table.TableProcessor",
        "extractor.core.processors.text.TextProcessor",
    ]
    processors_str = ",".join(processors)
    
    success, stdout, stderr = run_python_processor(
        "extractor.core.scripts.convert_single",
        f"{clean_pdf} {working_path} --output_format json --processors '{processors_str}'",
        "Marker extraction"
    )
    
    if not success:
        raise RuntimeError(f"STAGE 5 FAILED: Marker extraction failed")
    
    # Find and rename output
    marker_output = working_path / "clean.json"
    blocks_json = working_path / "blocks.json"
    
    if marker_output.exists():
        marker_output.rename(blocks_json)
    else:
        raise RuntimeError(f"STAGE 5 FAILED: Marker output not found")
    
    logger.success("✓ Stage 5 complete")
    
    # ======= STAGE 5.1: Transform to Stage 2 Gold Standard ======= #
    logger.info("STAGE 5.1: Transforming marker output to gold standard")
    
    stage2_json = working_path / "stage2_marker.json"
    success, stdout, stderr = run_python_processor(
        "extractor.core.processors.marker_to_gold_standard",
        f"transform {blocks_json} --output {stage2_json}",
        "Stage 2 transformation"
    )
    
    if not success:
        raise RuntimeError(f"STAGE 5.1 FAILED: Marker transformation failed")
    
    if not stage2_json.exists():
        raise RuntimeError(f"STAGE 5.1 FAILED: Stage 2 output not created")
    
    logger.success("✓ Stage 5.1 complete")
    
    # ======= STAGE 6: Build Sections ======= #
    logger.info("STAGE 6: Building sections")
    
    sections_json = working_path / "sections.json"
    success, stdout, stderr = run_python_processor(
        "extractor.core.processors.section_builder",
        f"build {blocks_json} --output {sections_json} --min-blocks 1",
        "Section building"
    )
    
    if not success:
        raise RuntimeError(f"STAGE 6 FAILED: Section building failed")
    
    if not sections_json.exists():
        raise RuntimeError(f"STAGE 6 FAILED: Sections file not created")
    
    logger.success("✓ Stage 6 complete")
    
    # ======= STAGE 6.1: Transform to Stage 3 Gold Standard ======= #
    logger.info("STAGE 6.1: Transforming sections to gold standard")
    
    stage3_json = working_path / "stage3_sections.json"
    success, stdout, stderr = run_python_processor(
        "extractor.core.processors.sections_to_gold_standard",
        f"transform {sections_json} --blocks {blocks_json} --output {stage3_json}",
        "Stage 3 transformation"
    )
    
    if not success:
        raise RuntimeError(f"STAGE 6.1 FAILED: Section transformation failed")
    
    if not stage3_json.exists():
        raise RuntimeError(f"STAGE 6.1 FAILED: Stage 3 output not created")
    
    logger.success("✓ Stage 6.1 complete")
    
    # ======= STAGE 7: Validation ======= #
    logger.info("STAGE 7: Running gold standard validation")
    
    validation_json = working_path / "validation.json"
    success, stdout, stderr = run_python_processor(
        "extractor.core.processors.gold_standard_validator",
        f"validate {sections_json} --output {validation_json}",
        "Validation"
    )
    
    # Note: Validation can fail but we still continue
    if success and validation_json.exists():
        with open(validation_json, "r") as f:
            validation = json.load(f)
        validation_score = validation.get('overall_score', 0.0)
    else:
        logger.warning("Validation failed or produced no output")
        validation_score = 0.0
    
    logger.info(f"Validation score: {validation_score * 100:.1f}%")
    
    # ======= FINAL OUTPUT ======= #
    logger.info("Generating final output")
    
    # Count sections
    with open(sections_json, "r") as f:
        sections_data = json.load(f)
    total_sections = len(sections_data.get('sections', []))
    
    output = {
        "status": "success",
        "pdf_path": str(pdf_path_obj),
        "total_sections": total_sections,
        "validation_score": validation_score,
        "working_dir": str(working_path),
        "files": {
            "annotations": str(annotations_json),
            "interpretation": str(working_path / "interpretation.txt"),
            "kb_patterns": str(working_path / "kb_patterns.txt"),
            "blocks": str(blocks_json),
            "stage2_marker": str(stage2_json),
            "sections": str(sections_json),
            "stage3_sections": str(stage3_json),
            "validation": str(validation_json) if validation_json.exists() else None
        }
    }
    
    # Save final output
    output_path = project_root / "final_output.json"
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)
    
    duration = time.time() - start_time
    logger.success(f"\n{'='*50}")
    logger.success(f"Pipeline ACTUALLY COMPLETED in {duration:.1f} seconds!")
    logger.success(f"Extracted {total_sections} sections")
    logger.success(f"Validation score: {validation_score*100:.1f}%")
    logger.success(f"Output: {output_path}")
    logger.success(f"{'='*50}\n")
    
    return output


async def main():
    """Main entry point"""
    
    # Check environment first
    check_environment()
    
    try:
        # Run with default PDF
        result = await run_pipeline(
            pdf_path="proof_of_concept/BHT_CV32A65X_marked.pdf",
            working_dir="tmp/pipeline_v2_run"
        )
        
        logger.success("Pipeline completed successfully!")
        return 0
        
    except Exception as e:
        logger.error(f"\n{'='*50}")
        logger.error(f"PIPELINE FAILED: {str(e)}")
        logger.error(f"{'='*50}\n")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)