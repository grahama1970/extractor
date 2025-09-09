#!/usr/bin/env python3
"""
PDF Extraction Pipeline - Fast execution with claude -p for semantic tasks.

This script converts the extract-pdf.md agent pipeline into direct Python execution,
eliminating agent overhead while preserving semantic reasoning capabilities through
batched claude -p calls.

Key features:
- Direct command execution (no agent overhead)
- Batched claude -p requests with asyncio and tqdm progress
- Timeout protection and fallback behavior
- Comprehensive logging for debugging

AGENT VERIFICATION INSTRUCTIONS:
- Run this script directly to execute working_usage()
- The working_usage() function MUST pass all assertions
- This verifies the pipeline produces expected results
- DO NOT assume the script works without running it

Third-party Documentation:
- [PyMuPDF]: https://pymupdf.readthedocs.io/
- [Marker PDF]: https://github.com/VikParuchuri/marker
- [Claude CLI]: https://docs.anthropic.com/claude/docs/claude-cli

Example Input:
    python extract_pdf_pipeline.py --pdf proof_of_concept/BHT_CV32A65X_marked.pdf

Expected Output:
    {
        "source_pdf": "proof_of_concept/BHT_CV32A65X_marked.pdf",
        "sections": [...],
        "validation_score": 0.85,
        "total_sections": 3,
        "duration_seconds": 45.2
    }
"""

import asyncio
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
import shutil
from datetime import datetime

# Third-party imports
import textwrap
from loguru import logger
from tqdm.asyncio import tqdm

# Configure logging
logger.remove()  # Remove default handler
logger.add(
    sys.stderr, 
    level="INFO", 
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)

# Environment setup
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())  # Automatically finds .env file

# Optional: Add file logging with rotation
log_dir = Path(__file__).parent / "logs"
log_dir.mkdir(exist_ok=True)
logger.add(
    log_dir / "extract_pipeline_{time}.log",
    rotation="10 MB",
    retention=5,
    level="DEBUG"
)


async def claude_p_with_timeout(
    prompt: str, 
    timeout: int = 30, 
    log_dir: str = "logs/claude_p"
) -> str:
    """Execute claude -p with timeout and logging"""
    
    # Create log directory
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    
    # Generate unique log file
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    log_file = f"{log_dir}/claude_p_{timestamp}.log"
    start_time = time.time()
    
    logger.info(f"Calling claude -p with timeout={timeout}s")
    logger.debug(f"Prompt: {prompt[:100]}...")
    
    try:
        # Copy current environment - this is the working pattern!
        env = os.environ.copy()
        
        # Ensure node is in PATH - add NVM node location
        env['PATH'] = '/home/graham/.nvm/versions/node/v22.15.0/bin:/usr/bin:/usr/local/bin:' + env.get('PATH', '')
        
        # CRITICAL: Unset ANTHROPIC_API_KEY for Claude Max Plan authentication
        if 'ANTHROPIC_API_KEY' in env:
            del env['ANTHROPIC_API_KEY']
        
        # Use the exact path to claude
        claude_path = '/home/graham/.bun/bin/claude'
        
        # Create subprocess with prompt as argument (claude -p expects this)
        proc = await asyncio.create_subprocess_exec(
            claude_path, '-p', prompt,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            preexec_fn=os.setsid if os.name != 'nt' else None
        )
        
        # Wait with timeout
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), 
            timeout=timeout
        )
        
        duration = time.time() - start_time
        
        # Log success
        with open(log_file, 'w') as f:
            json.dump({
                'timestamp': timestamp,
                'prompt': prompt,
                'status': 'success',
                'stdout': stdout.decode(),
                'stderr': stderr.decode(),
                'duration': duration
            }, f, indent=2)
        
        logger.success(f"Claude completed in {duration:.1f}s")
        return stdout.decode()
        
    except asyncio.TimeoutError:
        # Kill the process group
        if os.name != 'nt':
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        else:
            proc.terminate()
            
        # Log timeout
        with open(log_file, 'w') as f:
            json.dump({
                'timestamp': timestamp,
                'prompt': prompt,
                'status': 'timeout',
                'timeout_seconds': timeout,
                'fallback': 'Using default response'
            }, f, indent=2)
        
        logger.warning(f"Claude timed out after {timeout}s, using fallback")
        return "TIMEOUT: Using fallback response"
        
    except Exception as e:
        # Log error
        with open(log_file, 'w') as f:
            json.dump({
                'timestamp': timestamp,
                'prompt': prompt,
                'status': 'error',
                'error': str(e)
            }, f, indent=2)
        
        logger.error(f"Claude error: {e}")
        return f"ERROR: {str(e)}"


async def batch_claude_p_requests(
    prompts: List[Dict[str, Any]], 
    max_concurrent: int = 5,
    timeout: int = 30,
    desc: str = "Processing"
) -> List[Dict[str, Any]]:
    """
    Batch process multiple claude -p requests with progress bar
    
    Args:
        prompts: List of dicts with 'id' and 'prompt' keys
        max_concurrent: Maximum concurrent requests
        timeout: Timeout per request
        desc: Description for progress bar
        
    Returns:
        List of results with 'id' and 'result' keys
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process_one(item: Dict[str, Any]) -> Dict[str, Any]:
        async with semaphore:
            result = await claude_p_with_timeout(
                item['prompt'],
                timeout=timeout,
                log_dir=f"logs/{item.get('log_dir', 'batch')}"
            )
            return {'id': item['id'], 'result': result}
    
    # Create tasks
    tasks = [process_one(item) for item in prompts]
    
    # Process with progress bar
    results = []
    for future in tqdm.as_completed(tasks, desc=desc, total=len(tasks)):
        result = await future
        results.append(result)
    
    # Sort by original ID to maintain order
    results.sort(key=lambda x: x['id'])
    return results


def run_command(cmd: str, description: str = "", cwd: Optional[Path] = None, timeout: int = 120) -> tuple[int, str, str]:
    """Run a shell command and return exit code, stdout, stderr"""
    logger.info(f"Running: {description or cmd}")
    
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout
        )
        
        if result.returncode != 0:
            logger.error(f"Command failed with code {result.returncode}")
            logger.error(f"stderr: {result.stderr}")
        
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        logger.error(f"Command timed out after {timeout}s: {description or cmd}")
        return -1, "", f"Timeout after {timeout}s"


def run_processor(module: str, args: str, description: str, project_root: Path) -> tuple[int, str, str]:
    """Helper to run a Python processor module with proper paths"""
    # Use venv python if available, otherwise current executable
    venv_python = project_root / ".venv" / "bin" / "python"
    if venv_python.exists():
        python_path = str(venv_python)
    else:
        python_path = sys.executable or "/usr/bin/python3"
    cmd = f"{python_path} -m {module} {args}"
    return run_command(cmd, description, cwd=project_root)


async def run_extraction_pipeline(
    pdf_path: str = "proof_of_concept/BHT_CV32A65X_marked.pdf",
    working_dir: str = "tmp/pipeline_run"
) -> Dict[str, Any]:
    """
    Run the complete PDF extraction pipeline
    
    Args:
        pdf_path: Path to input PDF
        working_dir: Working directory for pipeline
        
    Returns:
        Dictionary with extraction results
    """
    
    logger.info(f"Starting PDF extraction pipeline for: {pdf_path}")
    start_time = time.time()
    
    # Get project root (where this script is located)
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent  # Go up to extractor root
    
    # Setup
    logger.info("Setting up working directory")
    working_path = project_root / working_dir
    working_path.mkdir(parents=True, exist_ok=True)
    
    # Handle PDF path resolution
    pdf_path_obj = Path(pdf_path)
    if not pdf_path_obj.is_absolute():
        # Try relative to project root first
        pdf_path_obj = project_root / pdf_path_obj
    
    if not pdf_path_obj.exists():
        logger.error(f"Input PDF not found: {pdf_path_obj}")
        raise FileNotFoundError(f"Input PDF not found: {pdf_path}")
    
    # Copy PDF to working directory
    doc_pdf = working_path / "doc.pdf"
    shutil.copy(pdf_path_obj, doc_pdf)
    logger.success("✓ Setup complete")
    
    # ======= Stage 1: Extract annotations ======= #
    logger.info("Stage 1: Extracting annotations")
    
    annotations_json = working_path / "annotations.json"
    exit_code, stdout, stderr = run_processor(
        "extractor.core.processors.gold_standard_annotation_extractor",
        f"extract {doc_pdf} --output {annotations_json}",
        "Extract annotations",
        project_root
    )
    
    if exit_code != 0:
        logger.error("Stage 1 FAILED - cannot continue without annotations")
        raise RuntimeError(f"Stage 1 FAILED: Annotation extraction failed: {stderr}")
    
    if not annotations_json.exists():
        logger.error("Stage 1 produced no output file")
        raise RuntimeError("Stage 1 FAILED: No annotations.json file created")
    
    logger.success("✓ Stage 1 complete")
    
    # ======= Stage 2: Interpret annotations semantically ======= #
    logger.info("Stage 2: Interpreting annotations")
    
    if not annotations_json.exists():
        logger.error("No annotations file found - Stage 1 must have failed")
        raise RuntimeError("Stage 2 FAILED: No annotations file from Stage 1")
    
    with open(annotations_json, "r") as f:
        annotations = json.load(f)
        
        interpretation = await claude_p_with_timeout(
            textwrap.dedent(f"""\
                uberthink: [Stage 2 - Interpret annotations semantically]
                Analyze these PDF annotations and determine their semantic meaning:
                1. What types of content do they mark (sections, tables, figures, etc)?
                2. Are there any hierarchical relationships?
                3. What patterns do you see in the annotation labels?
                4. How should these guide the extraction process?

                Annotations: {json.dumps(annotations, indent=2)}

                Provide a concise analysis focusing on actionable insights for extraction."""),
            timeout=30,
            log_dir="logs/stage2"
        )
        
        # Check for API key errors or other failures
        if interpretation.startswith(("TIMEOUT:", "ERROR:", "Invalid API key", "Authentication")):
            logger.error(f"Claude -p failed: {interpretation}")
            raise RuntimeError(f"Stage 2 FAILED: Claude authentication error - {interpretation}")
        elif not interpretation.strip():
            logger.error("Stage 2 FAILED - empty response from claude")
            raise RuntimeError("Stage 2 FAILED: Empty response from Claude")
        else:
            logger.info(f"Interpretation: {interpretation[:200]}...")
    
    logger.success("✓ Stage 2 complete")
    
    # ======= Stage 3: Create clean PDF ======= #
    logger.info("Stage 3: Creating clean PDF")
    exit_code, stdout, stderr = run_processor(
        "extractor.core.processors.pdf_cleaner",
        f"clean {doc_pdf} --output {working_path / 'clean.pdf'}",
        "Clean PDF",
        project_root
    )
    
    if exit_code != 0:
        logger.error("PDF cleaning failed")
        raise RuntimeError(f"Stage 3 FAILED: PDF cleaning failed - {stderr}")
    
    logger.success("✓ Stage 3 complete")
    
    # ======= Stage 4: Check knowledge base ======= #
    logger.info("Stage 4: Checking knowledge base")
    
    kb_result = await claude_p_with_timeout(
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

            Return patterns that would help extract this 2-page technical PDF accurately."""),
        timeout=30,  # Increased timeout
        log_dir="logs/stage4"
    )
    
    # Check for API key errors or other failures
    if kb_result.startswith(("TIMEOUT:", "ERROR:", "Invalid API key", "Authentication")):
        logger.error(f"Stage 4 claude -p failed: {kb_result}")
        raise RuntimeError(f"Stage 4 FAILED: Claude error - {kb_result}")
    elif not kb_result.strip():
        logger.error("Stage 4 FAILED - empty response from claude")
        raise RuntimeError("Stage 4 FAILED: Empty response from Claude")
    else:
        logger.info(f"Knowledge base result: {kb_result[:200]}...")
        logger.success("✓ Stage 4 complete")
    
    # ======= Stage 5: Run marker extraction ======= #
    logger.info("Stage 5: Running marker extraction")
    
    # Check if blocks.json already exists
    blocks_json = working_path / "blocks.json"
    if blocks_json.exists():
        logger.info("Using existing blocks.json")
    else:
        # Run marker extraction without disable_tqdm (not a valid option)
        # Create a custom processor list without LLM processors
        non_llm_processors = [
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
            "extractor.core.processors.reference.ReferenceProcessor",
            "extractor.core.processors.debug.DebugProcessor",
        ]
        processors_str = ",".join(non_llm_processors)
        
        # Use venv python if available
        venv_python = project_root / ".venv" / "bin" / "python"
        if venv_python.exists():
            python_path = str(venv_python)
        else:
            python_path = sys.executable or "/usr/bin/python3"
        
        exit_code, stdout, stderr = run_command(
            f"cd {project_root} && {python_path} -m extractor.core.scripts.convert_single {working_path / 'clean.pdf'} --output_dir {working_path} --output_format json --disable_multiprocessing --processors '{processors_str}'",
            "Marker extraction",
            cwd=project_root,
            timeout=300
        )
        
        # Handle marker output renaming
        clean_json = working_path / "clean.json"
        if clean_json.exists():
            shutil.move(clean_json, blocks_json)
            logger.info("Renamed clean.json to blocks.json")
        
        if not blocks_json.exists():
            logger.error("Marker extraction failed")
            raise RuntimeError("Stage 5 FAILED: Marker extraction produced no output")
    
    logger.success("✓ Stage 5 complete")
    
    # ======= Stage 5.1: Transform to Stage 2 Gold Standard Format ======= #
    logger.info("Stage 5.1: Transforming marker output to gold standard format")
    
    stage2_json = working_path / "stage2_marker.json"
    exit_code, stdout, stderr = run_processor(
        "extractor.core.processors.marker_to_gold_standard",
        f"transform {blocks_json} --output {stage2_json}",
        "Transform to Stage 2 format",
        project_root
    )
    
    if exit_code == 0:
        logger.success("✓ Stage 5.1 complete - Stage 2 gold standard format created")
    else:
        logger.error("Stage 5.1 transformation failed")
        raise RuntimeError(f"Stage 5.1 FAILED: Transformation failed - {stderr}")
    
    # ======= Stage 5.5: Fix suspicious blocks ======= #
    logger.info("Stage 5.5: Analyzing suspicious blocks")
    
    exit_code, stdout, stderr = run_processor(
        "extractor.core.processors.suspicious_block_analyzer",
        f"analyze {blocks_json} --output {working_path / 'suspicious_analysis.json'}",
        "Analyze suspicious blocks",
        project_root
    )
    
    suspicious_analysis = working_path / "suspicious_analysis.json"
    if exit_code == 0 and suspicious_analysis.exists():
        # Create batches
        run_processor(
            "extractor.core.processors.suspicious_block_batcher",
            f"batch {suspicious_analysis} --output {working_path / 'batches.json'} --batch-size 5",
            "Create batches",
            project_root
        )
        
        # Process batches with claude -p
        batches_json = working_path / "batches.json"
        if batches_json.exists():
            with open(batches_json, "r") as f:
                batches_data = json.load(f)
            
            if batches_data.get("batches"):
                # Create prompts for each batch
                batch_prompts = []
                for i, batch in enumerate(batches_data["batches"]):
                    batch_prompts.append({
                        'id': i,
                        'prompt': textwrap.dedent(f"""\
                            uberthink: [Stage 5.5c - Fix suspicious blocks batch {i}]
                            Analyze and fix these suspicious PDF blocks from marker extraction:

                            Common issues to fix:
                            1. Broken table structures (missing headers, misaligned cells)
                            2. Code blocks misidentified as text
                            3. Mathematical expressions broken across blocks
                            4. Section headers with incorrect hierarchy
                            5. Figure captions separated from figures

                            Blocks to fix:
                            {json.dumps(batch, indent=2)}

                            Return corrected blocks maintaining the same structure but with fixed content."""),
                        'log_dir': f'stage5.5c/batch_{i}'
                    })
                
                # Process all batches concurrently
                logger.info(f"Processing {len(batch_prompts)} suspicious block batches")
                batch_results = await batch_claude_p_requests(
                    batch_prompts,
                    max_concurrent=3,
                    timeout=20,
                    desc="Fixing suspicious blocks"
                )
                
                # Save results
                with open(working_path / "fixed_blocks.json", "w") as f:
                    json.dump(batch_results, f, indent=2)
    
    logger.success("✓ Stage 5.5 complete")
    
    # ======= Stage 6: Build section nodes ======= #
    logger.info("Stage 6: Building section nodes")
    
    exit_code, stdout, stderr = run_processor(
        "extractor.core.processors.section_builder",
        f"build {blocks_json} --output {working_path / 'sections.json'} -m 1",
        "Build sections",
        project_root
    )
    
    if exit_code != 0:
        logger.error("Section building failed")
        raise RuntimeError(f"Stage 6 FAILED: Section building failed - {stderr}")
    
    logger.success("✓ Stage 6 complete")
    
    # ======= Stage 6.1: Transform to Stage 3 Gold Standard Format ======= #
    logger.info("Stage 6.1: Transforming sections to gold standard format")
    
    sections_json = working_path / 'sections.json'
    stage3_json = working_path / "stage3_sections.json"
    exit_code, stdout, stderr = run_processor(
        "extractor.core.processors.sections_to_gold_standard",
        f"transform {sections_json} --blocks {blocks_json} --output {stage3_json}",
        "Transform to Stage 3 format",
        project_root
    )
    
    if exit_code == 0:
        logger.success("✓ Stage 6.1 complete - Stage 3 gold standard format created")
    else:
        logger.warning("Stage 6.1 transformation failed, continuing with original format")
    
    # ======= Stage 7: Create validation images ======= #
    logger.info("Stage 7: Creating validation images")
    
    # Section snapshots
    run_processor(
        "extractor.core.processors.pdf_snapshot",
        f"create {working_path / 'clean.pdf'} --sections {working_path / 'sections.json'} --output-dir {working_path / 'snapshots'}",
        "Create snapshots",
        project_root
    )
    
    # Table images
    run_processor(
        "extractor.core.processors.table_image_creator",
        f"create {working_path / 'clean.pdf'} --sections {working_path / 'sections.json'} --output-dir {working_path / 'table_images'}",
        "Create table images",
        project_root
    )
    
    logger.success("✓ Stage 7 complete")
    
    # ======= Stage 8: Enrich sections ======= #
    logger.info("Stage 8: Enriching sections")
    
    sections_json = working_path / "sections.json"
    exit_code, stdout, stderr = run_processor(
        "extractor.core.processors.stage7_enrichment_orchestrator",
        f"enrich {sections_json} --pdf {working_path / 'clean.pdf'} --marker-output {blocks_json} --annotations {annotations_json} --output {working_path / 'enriched_sections.json'}",
        "Enrich sections",
        project_root
    )
    
    if exit_code != 0:
        logger.error("Enrichment failed")
        raise RuntimeError(f"Stage 8 FAILED: Enrichment failed - {stderr}")
    
    logger.success("✓ Stage 8 complete")
    
    # ======= Stage 9: Enhance sections ======= #
    logger.info("Stage 9: Enhancing sections")
    
    # Create section files
    enriched_sections_json = working_path / "enriched_sections.json"
    section_files_dir = working_path / "section_files"
    exit_code, stdout, stderr = run_processor(
        "extractor.core.processors.section_batcher",
        f"batch {enriched_sections_json} --output-dir {section_files_dir}",
        "Batch sections",
        project_root
    )
    
    # Process section files with claude -p and pdf-section-cleaner agent
    section_dir = section_files_dir
    enhanced_dir = working_path / "enhanced_sections"
    enhanced_dir.mkdir(exist_ok=True)
    
    if section_dir.exists() and exit_code == 0:
        section_files = list(section_dir.glob("*.json"))
        
        if section_files:
            logger.info(f"Enhancing {len(section_files)} sections with pdf-section-cleaner agent")
            
            # Create prompts for concurrent processing
            section_prompts = []
            for i, section_file in enumerate(section_files):
                with open(section_file, "r") as f:
                    section_data = json.load(f)
                
                # Load annotations for this section if available
                all_annotations = {}
                if annotations_json.exists():
                    with open(annotations_json, "r") as f:
                        all_annotations = json.load(f)
                
                # Build comprehensive metadata context
                metadata_context = {
                    "available_tools": [
                        "pdf_section_cleaner_worker.py - Comprehensive section cleaning",
                        "llm_table.py - Table reconstruction and analysis", 
                        "llm_equation.py - Mathematical expression processing",
                        "llm_handwriting.py - Handwritten text extraction",
                        "llm_form.py - Form field detection",
                        "semantic_section_processor.py - Semantic analysis",
                        "table_image_creator.py - Visual table validation"
                    ],
                    "section_metrics": {
                        "total_blocks": len(section_data.get("blocks", [])),
                        "text_blocks": sum(1 for b in section_data.get("blocks", []) if b.get("block_type") == "Text"),
                        "table_blocks": sum(1 for b in section_data.get("blocks", []) if b.get("block_type") == "Table"),
                        "figure_blocks": sum(1 for b in section_data.get("blocks", []) if b.get("block_type") == "Figure"),
                        "section_level": section_data.get("level", 0)
                    }
                }
                
                # Add table images if they exist
                table_images_context = ""
                table_img_dir = working_path / "table_images"
                if table_img_dir.exists():
                    table_imgs = list(table_img_dir.glob(f"*section_{i}_*.png"))
                    if table_imgs:
                        metadata_context["table_images"] = [str(img) for img in table_imgs]
                        table_images_context = f"\nTable images available: {', '.join(img.name for img in table_imgs)}"
                
                # Add section snapshot if it exists
                snapshot_context = ""
                snapshot_dir = working_path / "snapshots"
                if snapshot_dir.exists():
                    snapshots = list(snapshot_dir.glob(f"section_{i}_*.png"))
                    if snapshots:
                        metadata_context["section_snapshots"] = [str(snap) for snap in snapshots]
                        snapshot_context = f"\nSection snapshot available: {snapshots[0].name}"
                
                section_prompts.append({
                    'id': i,
                    'prompt': textwrap.dedent(f"""\
                        uberthink: You are a PDF section cleaning specialist. Process section '{section_data.get('title', f'Section {i}')}' comprehensively.

                        ## Section Analysis Checklist:
                        ☐ Inventory all blocks by type and confidence level
                        ☐ Apply reviewer annotations to guide corrections
                        ☐ Fix text spacing (e.g., 'BHT   (Branch' → 'BHT (Branch')
                        ☐ Merge fragmented text blocks based on proximity and formatting
                        ☐ Reconstruct tables from separated cells using spatial analysis
                        ☐ Validate suspicious headers with semantic context
                        ☐ Process mathematical equations preserving LaTeX notation
                        ☐ Extract form fields with labels and values
                        ☐ Generate descriptive captions for figures
                        ☐ Build coherent section structure

                        ## Available Resources:
                        - PDF Blocks: {metadata_context['section_metrics']['total_blocks']} total \
                        ({metadata_context['section_metrics']['text_blocks']} text, \
                        {metadata_context['section_metrics']['table_blocks']} tables, \
                        {metadata_context['section_metrics']['figure_blocks']} figures)
                        - Section Level: {metadata_context['section_metrics']['section_level']}
                        {table_images_context}{snapshot_context}

                        ## Section Data to Clean:
                        ```json
                        {json.dumps(section_data, indent=2)}
                        ```

                        ## Reviewer Annotations:
                        ```json
                        {json.dumps(all_annotations, indent=2)}
                        ```

                        ## Your Task:
                        1. Analyze all blocks and identify issues
                        2. Apply comprehensive cleaning using the checklist
                        3. Validate against visual resources if available
                        4. Return ONLY the cleaned JSON structure

                        ## Required Output Format:
                        ```json
                        {{
                        "section_id": {i},
                        "header": "cleaned section header",
                        "cleaned_blocks": [
                            {{
                            "type": "Text|Table|Figure|...",
                            "content": "cleaned content",
                            "merged_from": [list of original block ids if merged],
                            "confidence": 0.95
                            }}
                        ],
                        "processing_stats": {{
                            "original_blocks": number,
                            "cleaned_blocks": number,
                            "merged_text_blocks": number,
                            "reconstructed_tables": number,
                            "fixed_headers": number
                        }}
                        }}
                        ```
                        Output ONLY the JSON, no explanations."""),
                    'log_dir': f'stage9b/section_{i}',
                    'file': section_file,
                    'output_file': enhanced_dir / f"enhanced_{section_file.stem}.json"
                })
            # Process all sections concurrently
            logger.info(f"Processing {len(section_prompts)} sections concurrently")
            enhanced_results = await batch_claude_p_requests(
                section_prompts,
                max_concurrent=3,  # Limit concurrent requests
                timeout=45,  # Longer timeout for complex cleaning
                desc="Cleaning sections"
            )
            
            # Save enhanced sections
            for i, result in enumerate(enhanced_results):
                prompt_data = section_prompts[result['id']]
                output_file = prompt_data['output_file']
                
                if not result['result'].startswith(("TIMEOUT:", "ERROR:")):
                    try:
                        # Try to parse the result as JSON
                        cleaned_data = json.loads(result['result'])
                        with open(output_file, "w") as f:
                            json.dump(cleaned_data, f, indent=2)
                        logger.success(f"✓ Enhanced section {i+1}/{len(section_files)}")
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON response for {prompt_data['file'].name}, using original")
                        shutil.copy(prompt_data['file'], output_file)
                else:
                    logger.warning(f"Failed to enhance {prompt_data['file'].name}: {result['result'][:50]}...")
                    shutil.copy(prompt_data['file'], output_file)
    
    # Merge enhanced sections (workaround for missing module)
    logger.info("Merging enhanced sections")
    merged_sections = {"sections": []}
    merged_enhanced_json = working_path / "merged_enhanced_sections.json"
    
    # Try to merge enhanced sections if they exist
    enhanced_files = list(enhanced_dir.glob("enhanced_*.json")) if enhanced_dir.exists() else []
    if enhanced_files:
        for idx, ef in enumerate(sorted(enhanced_files)):
            with open(ef, "r") as f:
                data = json.load(f)
                # The pdf_section_cleaner agent outputs cleaned section data
                if isinstance(data, dict) and "cleaned_blocks" in data:
                    # Convert cleaned_blocks format to standard section format
                    section = {
                        "id": data.get("section_id", idx),
                        "title": data.get("header", ""),
                        "blocks": data.get("cleaned_blocks", []),
                        "processing_stats": data.get("processing_stats", {})
                    }
                    merged_sections["sections"].append(section)
                elif isinstance(data, dict) and "blocks" in data:
                    # Fallback for standard format
                    merged_sections["sections"].append(data)
                else:
                    logger.warning(f"Unexpected format in {ef.name}")
    
    # If no enhanced sections, use enriched_sections as fallback
    if not merged_sections["sections"]:
        shutil.copy(enriched_sections_json, merged_enhanced_json)
    else:
        with open(merged_enhanced_json, "w") as f:
            json.dump(merged_sections, f, indent=2)
    
    logger.success("✓ Stage 9 complete")
    
    # ======= Stage 10: Validate ======= #
    logger.info("Stage 10: Validating against gold standard")
    
    gold_standard = project_root / "gold_standards/gold_standard_section_json.json"
    if gold_standard.exists():
        merged_enhanced_json = working_path / "merged_enhanced_sections.json"
        validation_json = working_path / "validation.json"
        exit_code, stdout, stderr = run_processor(
            "extractor.core.processors.gold_validator",
            f"validate {merged_enhanced_json} {gold_standard} --output {validation_json}",
            "Validate",
            project_root
        )
    else:
        logger.warning("Gold standard not found, skipping validation")
        validation_json = working_path / "validation.json"
        with open(validation_json, "w") as f:
            json.dump({"metrics": {"overall_accuracy": 0}}, f)
    
    logger.success("✓ Stage 10 complete")
    
    # ======= Stage 11: Add breadcrumbs ======= #
    logger.info("Stage 11: Adding section breadcrumbs")
    
    exit_code, stdout, stderr = run_processor(
        "extractor.core.processors.section_hierarchy",
        f"{merged_enhanced_json} {working_path / 'final_sections.json'}",
        "Add breadcrumbs",
        project_root
    )
    
    if exit_code != 0:
        shutil.copy(merged_enhanced_json, working_path / "final_sections.json")
    
    logger.success("✓ Stage 11 complete")
    
    # ======= Stage 12: Generate final output ======= #
    logger.info("Stage 12: Generating final output")
    
    # Load results
    final_sections_json = working_path / "final_sections.json"
    with open(final_sections_json, "r") as f:
        sections = json.load(f)
    
    with open(validation_json, "r") as f:
        validation = json.load(f)
    
    output = {
        "source_pdf": str(pdf_path),
        "sections": sections,
        "validation_score": validation.get("metrics", {}).get("overall_accuracy", 0),
        "total_sections": len(sections) if isinstance(sections, list) else len(sections.get("sections", [])),
        "duration_seconds": time.time() - start_time
    }
    
    final_output_json = working_path / "final_output.json"
    with open(final_output_json, "w") as f:
        json.dump(output, f, indent=2)
    
    logger.success("✓ Stage 12 complete")
    
    # ======= Stage 13: Store patterns ======= #
    logger.info("Stage 13: Storing patterns")
    
    patterns = await claude_p_with_timeout(
        textwrap.dedent(f"""\
            uberthink: [Stage 13 - Store extraction patterns]
            Analyze what we learned from extracting this PDF:

            Document: CV32A65X BHT (Branch History Table) technical specification
            Results: {output['total_sections']} sections extracted, {output['validation_score']*100:.1f}% validation accuracy

            Identify reusable patterns for future extractions:
            1. Successful annotation interpretation strategies
            2. Effective section boundary detection methods
            3. Table extraction patterns that worked well
            4. Figure and caption association techniques
            5. Hierarchical structure preservation approaches
            6. Any challenges encountered and how they were resolved

            Format as knowledge base entries for similar technical PDFs."""),
        timeout=20,
        log_dir="logs/stage13"
    )
    
    # Check for API key errors or other failures
    if patterns.startswith(("TIMEOUT:", "ERROR:", "Invalid API key", "Authentication")):
        logger.error(f"Claude -p failed: {patterns}")
        raise RuntimeError(f"Stage 13 FAILED: Claude error - {patterns}")
    elif not patterns.strip():
        logger.error("Stage 13 FAILED - empty response from claude")
        raise RuntimeError("Stage 13 FAILED: Empty response from Claude")
    else:
        logger.info(f"Patterns stored: {patterns[:200]}...")
        logger.success("✓ Stage 13 complete")
    
    # Summary
    duration = time.time() - start_time
    logger.success(f"\n{'='*50}")
    logger.success(f"Pipeline complete in {duration:.1f} seconds!")
    logger.success(f"Extracted {output['total_sections']} sections")
    logger.success(f"Validation score: {output['validation_score']*100:.1f}%")
    logger.success(f"Output: {Path.cwd()}/final_output.json")
    logger.success(f"{'='*50}\n")
    
    return output


async def working_usage():
    """
    Known working examples that demonstrate pipeline functionality.
    This function contains stable, tested code that reliably works.
    
    CRITICAL FOR AGENTS:
    - This function MUST verify that the pipeline produces expected results
    - Use assertions to validate outputs match expectations
    - Return True only if ALL tests pass
    - This is how agents verify the script actually works
    """
    logger.info("=== Running Working Usage Examples ===")
    
    # Test with default BHT PDF
    test_pdf = "proof_of_concept/BHT_CV32A65X_marked.pdf"
    working_dir = "tmp/pipeline_test"
    
    # Clean up previous test
    if Path(working_dir).exists():
        shutil.rmtree(working_dir)
    
    try:
        # Run the pipeline
        result = await run_extraction_pipeline(test_pdf, working_dir)
        
        # VERIFY EXPECTED RESULTS - THIS IS CRITICAL!
        assert "error" not in result, f"Pipeline failed: {result.get('error')}"
        assert result["total_sections"] > 0, "No sections extracted"
        assert result["source_pdf"] == test_pdf, "Wrong source PDF"
        assert "duration_seconds" in result, "Missing duration"
        assert result["duration_seconds"] < 120, "Pipeline too slow (>2 minutes)"
        
        # Verify output files exist
        output_dir = Path(working_dir)
        assert (output_dir / "final_output.json").exists(), "Missing final output"
        assert (output_dir / "annotations.json").exists(), "Missing annotations"
        assert (output_dir / "clean.pdf").exists(), "Missing clean PDF"
        assert (output_dir / "blocks.json").exists(), "Missing blocks"
        assert (output_dir / "sections.json").exists(), "Missing sections"
        
        # Log success
        logger.success(f"✓ Pipeline completed in {result['duration_seconds']:.1f}s")
        logger.info(f"✓ Extracted {result['total_sections']} sections")
        logger.info(f"✓ Validation score: {result['validation_score']*100:.1f}%")
        
        logger.success("✓ All working_usage tests passed!")
        return True
        
    except AssertionError as e:
        logger.error(f"Test failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        logger.exception("Full traceback:")
        return False


async def debug_function():
    """
    Debug function for testing new features or debugging issues.
    Update this frequently while developing/debugging.
    """
    logger.info("=== Running Debug Function ===")
    
    # Current debugging focus: Test claude -p batching
    test_prompts = [
        {
            'id': 0,
            'prompt': 'uberthink: What is 2+2?',
            'log_dir': 'debug/test1'
        },
        {
            'id': 1, 
            'prompt': 'uberthink: What is the capital of France?',
            'log_dir': 'debug/test2'
        },
        {
            'id': 2,
            'prompt': 'uberthink: Explain photosynthesis in one sentence.',
            'log_dir': 'debug/test3'
        }
    ]
    
    # Test batch processing
    logger.info("Testing batch claude -p requests...")
    results = await batch_claude_p_requests(
        test_prompts,
        max_concurrent=2,
        timeout=10,
        desc="Debug batch test"
    )
    
    for result in results:
        logger.debug(f"Result {result['id']}: {result['result'][:50]}...")
    
    return True


if __name__ == "__main__":
    """
    Script entry point with triple-mode execution.
    
    Usage:
        python extract_pdf_pipeline.py              # Runs working_usage() - stable tests
        python extract_pdf_pipeline.py debug        # Runs debug_function() - experimental
        python extract_pdf_pipeline.py --pdf path/to/file.pdf  # Run specific PDF
    
    This pattern provides:
    1. Stable working examples that always run
    2. Debug playground for testing without breaking working code
    3. CLI interface for production use
    """
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="PDF Extraction Pipeline")
    parser.add_argument("mode", nargs="?", default="working", choices=["working", "debug"])
    parser.add_argument("--pdf", help="Path to input PDF")
    parser.add_argument("--working-dir", default="tmp/pipeline_run", help="Working directory")
    
    args = parser.parse_args()
    
    async def main():
        """Main async entry point."""
        if args.mode == "debug":
            logger.info("Running in DEBUG mode...")
            success = await debug_function()
        elif args.pdf:
            logger.info(f"Running pipeline for: {args.pdf}")
            result = await run_extraction_pipeline(args.pdf, args.working_dir)
            success = "error" not in result
            if success:
                logger.success("Pipeline completed successfully")
            else:
                logger.error(f"Pipeline failed: {result.get('error')}")
        else:
            logger.info("Running in WORKING mode...")
            success = await working_usage()
        
        return success
    
    # Single asyncio.run() call
    success = asyncio.run(main())
    exit(0 if success else 1)