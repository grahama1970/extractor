#!/usr/bin/env python3
"""
Simplified PDF extraction pipeline that bypasses marker issues
"""

import sys
import json
import asyncio
import subprocess
import os
from pathlib import Path
from datetime import datetime
import tempfile
import shutil
from typing import List, Dict, Any, Optional

# Set up paths
script_dir = Path(__file__).parent
project_root = script_dir.parent.parent  # Go up to extractor root
sys.path.insert(0, str(project_root / 'src'))

# Imports
from loguru import logger
from tqdm import tqdm

# Configure logging
logger.remove()
logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level} | {message}")

def run_command(cmd: str, timeout: int = 120, cwd: Optional[str] = None) -> tuple[int, str, str]:
    """Run a command with timeout"""
    logger.info(f"Running: {cmd}")
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd
        )
        if result.returncode != 0:
            logger.warning(f"Command failed with code {result.returncode}: {result.stderr}")
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        logger.error(f"Command timed out after {timeout}s: {cmd}")
        return -1, "", "Timeout"

async def run_claude_prompt(prompt: str, timeout: int = 60) -> str:
    """Run claude -p with a prompt"""
    # Save prompt to temp file to avoid shell escaping issues
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(prompt)
        prompt_file = f.name
    
    try:
        cmd = f"claude -p \"$(cat {prompt_file})\""
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(project_root)
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            if proc.returncode != 0:
                logger.warning(f"Claude failed with code {proc.returncode}: {stderr.decode()}")
                return ""
            return stdout.decode()
        except asyncio.TimeoutError:
            proc.kill()
            logger.warning(f"Claude timeout after {timeout}s")
            return ""
    finally:
        os.unlink(prompt_file)

def create_simple_blocks(pdf_path: str) -> dict:
    """Create simplified block structure using PyMuPDF extraction"""
    logger.info("Using simplified PyMuPDF extraction instead of marker")
    
    try:
        import fitz  # PyMuPDF
        
        doc = fitz.open(pdf_path)
        blocks = []
        
        for page_num, page in enumerate(doc):
            # Extract text blocks
            text_blocks = page.get_text("blocks")
            
            for block_idx, block in enumerate(text_blocks):
                x0, y0, x1, y1, text, block_no, block_type = block
                
                # Skip empty blocks
                if not text.strip():
                    continue
                
                # Determine block type based on text patterns
                text_clean = text.strip()
                block_type = "Text"
                
                # Simple heuristics for block types
                if text_clean.startswith(("Figure", "Fig.", "Table")):
                    block_type = "FigureCaption" if "Figure" in text_clean or "Fig." in text_clean else "TableCaption"
                elif len(text_clean) < 100 and any(text_clean.startswith(f"{i}.") for i in range(1, 10)):
                    block_type = "SectionHeader"
                elif "|" in text_clean or "\t" in text_clean:
                    block_type = "Table"
                
                blocks.append({
                    "type": block_type,
                    "text": text_clean,
                    "page": page_num,
                    "bbox": [x0, y0, x1, y1],
                    "block_idx": block_idx,
                    "confidence": 0.9  # High confidence for direct extraction
                })
        
        doc.close()
        
        return {
            "metadata": {
                "source_file": pdf_path,
                "total_pages": len(doc),
                "extraction_method": "pymupdf_simplified"
            },
            "blocks": blocks
        }
        
    except Exception as e:
        logger.error(f"PyMuPDF extraction failed: {e}")
        # Return minimal fallback
        return {
            "metadata": {"source_file": pdf_path, "error": str(e)},
            "blocks": [{
                "type": "Text",
                "text": "Failed to extract content",
                "page": 0,
                "bbox": [0, 0, 100, 100]
            }]
        }

async def process_section_batch(sections: List[Dict], pdf_path: str, annotations: Dict) -> List[Dict]:
    """Process a batch of sections with claude -p"""
    enhanced_sections = []
    
    for i, section in enumerate(sections):
        logger.info(f"Processing section {i}: {section.get('title', 'Untitled')}")
        
        # Create comprehensive prompt for section cleaning
        prompt = f"""You are a PDF section cleaning specialist. Process this section comprehensively.

## Section: {section.get('title', f'Section {i}')}

## Blocks in this section:
{json.dumps(section.get('blocks', []), indent=2)}

## Available annotations:
{json.dumps(annotations.get('annotations', []), indent=2)}

## Task:
1. Clean and fix text spacing issues (e.g., "BHT   (Branch" → "BHT (Branch")
2. Merge split text blocks that belong together
3. Reconstruct tables from fragments if present
4. Apply relevant annotations to blocks
5. Return cleaned blocks in JSON format

Output the cleaned blocks as a JSON array."""

        result = await run_claude_prompt(prompt, timeout=45)
        
        if result:
            try:
                # Parse claude's response
                # Try to extract JSON from the response
                import re
                json_match = re.search(r'\[.*\]', result, re.DOTALL)
                if json_match:
                    cleaned_blocks = json.loads(json_match.group())
                    section['blocks'] = cleaned_blocks
                    section['enhanced'] = True
            except Exception as e:
                logger.warning(f"Failed to parse claude response for section {i}: {e}")
                section['enhanced'] = False
        else:
            section['enhanced'] = False
        
        enhanced_sections.append(section)
    
    return enhanced_sections

async def main():
    """Run simplified pipeline"""
    logger.info("Starting simplified PDF extraction pipeline")
    
    # Setup paths
    input_pdf = project_root / "proof_of_concept" / "BHT_CV32A65X_marked.pdf"
    output_dir = project_root / "tmp" / "pipeline_simple_run"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy PDF to working directory
    work_pdf = output_dir / "doc.pdf"
    shutil.copy(input_pdf, work_pdf)
    
    # ======= Stage 1: Extract annotations ======= #
    logger.info("Stage 1: Extracting annotations")
    cmd = f"cd {project_root} && python -m extractor.core.processors.enhanced_annotation_extractor extract {work_pdf} --output {output_dir}/annotations.json"
    ret, stdout, stderr = run_command(cmd, timeout=30)
    
    if ret != 0 or not (output_dir / "annotations.json").exists():
        logger.warning("Annotation extraction failed, using empty annotations")
        annotations = {"annotations": []}
        with open(output_dir / "annotations.json", 'w') as f:
            json.dump(annotations, f)
    else:
        with open(output_dir / "annotations.json") as f:
            annotations = json.load(f)
    
    # ======= Stage 2: Create clean PDF ======= #
    logger.info("Stage 2: Creating clean PDF")
    clean_pdf = output_dir / "clean.pdf"
    shutil.copy(work_pdf, clean_pdf)  # For now, just copy
    
    # ======= Stage 3: Extract blocks (simplified) ======= #
    logger.info("Stage 3: Extracting blocks using simplified method")
    blocks_data = create_simple_blocks(str(clean_pdf))
    
    with open(output_dir / "blocks.json", 'w') as f:
        json.dump(blocks_data, f, indent=2)
    
    logger.info(f"Extracted {len(blocks_data['blocks'])} blocks")
    
    # ======= Stage 4: Build sections ======= #
    logger.info("Stage 4: Building sections from blocks")
    
    # Simple section building
    sections = []
    current_section = None
    
    for block in blocks_data['blocks']:
        if block['type'] == 'SectionHeader':
            # Start new section
            if current_section:
                sections.append(current_section)
            current_section = {
                'title': block['text'],
                'blocks': [],
                'metadata': {
                    'start_page': block['page'],
                    'header_bbox': block['bbox']
                }
            }
        elif current_section:
            current_section['blocks'].append(block)
        else:
            # No section yet, create default
            if not sections:
                current_section = {
                    'title': 'Introduction',
                    'blocks': [],
                    'metadata': {'start_page': 0}
                }
            current_section['blocks'].append(block)
    
    # Add last section
    if current_section:
        sections.append(current_section)
    
    with open(output_dir / "sections.json", 'w') as f:
        json.dump({'sections': sections}, f, indent=2)
    
    logger.info(f"Created {len(sections)} sections")
    
    # ======= Stage 5: Enhance sections with Claude ======= #
    if sections:
        logger.info("Stage 5: Enhancing sections with Claude")
        
        # Process in batches
        batch_size = 5
        all_enhanced = []
        
        for i in range(0, len(sections), batch_size):
            batch = sections[i:i+batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}/{(len(sections) + batch_size - 1)//batch_size}")
            enhanced_batch = await process_section_batch(batch, str(clean_pdf), annotations)
            all_enhanced.extend(enhanced_batch)
        
        with open(output_dir / "enhanced_sections.json", 'w') as f:
            json.dump({'sections': all_enhanced}, f, indent=2)
    
    # ======= Stage 6: Final validation ======= #
    logger.info("Stage 6: Final validation")
    
    # Simple validation metrics
    total_blocks = sum(len(s.get('blocks', [])) for s in sections)
    enhanced_count = sum(1 for s in sections if s.get('enhanced', False))
    
    validation = {
        'total_sections': len(sections),
        'total_blocks': total_blocks,
        'enhanced_sections': enhanced_count,
        'success_rate': enhanced_count / len(sections) if sections else 0
    }
    
    with open(output_dir / "validation.json", 'w') as f:
        json.dump(validation, f, indent=2)
    
    # ======= Final output ======= #
    final_output = {
        'source_pdf': str(input_pdf),
        'output_dir': str(output_dir),
        'sections': sections,
        'validation': validation,
        'timestamp': datetime.now().isoformat()
    }
    
    with open(output_dir / "final_output.json", 'w') as f:
        json.dump(final_output, f, indent=2)
    
    logger.success(f"Pipeline complete! Processed {len(sections)} sections with {validation['success_rate']*100:.0f}% enhancement rate")
    logger.info(f"Results saved to: {output_dir}")
    
    return True

async def working_usage():
    """Stable example that works"""
    logger.info("Running working usage example")
    return await main()

async def debug_function():
    """Debug function for testing"""
    logger.info("Running debug mode - testing individual components")
    
    # Test PyMuPDF extraction
    pdf_path = "/home/graham/workspace/experiments/extractor/proof_of_concept/BHT_CV32A65X_marked.pdf"
    blocks = create_simple_blocks(pdf_path)
    
    logger.info(f"Extracted {len(blocks['blocks'])} blocks")
    for i, block in enumerate(blocks['blocks'][:5]):
        logger.info(f"Block {i}: {block['type']} - {block['text'][:50]}...")
    
    return True

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "working"
    
    if mode == "debug":
        asyncio.run(debug_function())
    else:
        asyncio.run(working_usage())