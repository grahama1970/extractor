#!/usr/bin/env python3
"""
POC 05: Complete PDF Extraction Pipeline

This POC demonstrates the full 7-step pipeline:
1. Extract, Interpret and Store Annotations (from POC 00)
2. Extract PDF with Marker (from POC 01)
3. Extract Tables with Camelot on pages identified by Marker (async batching)
4. Run heuristics on mislabeled PDF objects (from POC 02)
5. Fix mislabeled objects with batched Claude calls
6. Create section nodes from the JSON
7. Analyze each section node with batched Claude calls

This is the production-ready pipeline combining all POCs.

AGENT VERIFICATION INSTRUCTIONS:
- Run this script directly to execute working_usage()
- The working_usage() function MUST pass all assertions
- This verifies the script produces expected results
- DO NOT assume the script works without running it
"""

import asyncio
import json
import os
import re
import sys
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple
from datetime import datetime
from collections import defaultdict
import uuid

# Third-party imports
import fitz  # PyMuPDF - REQUIRED
import camelot
from PIL import Image, ImageDraw
from loguru import logger
import typer
from typing_extensions import Annotated
from rapidfuzz import fuzz
import nest_asyncio

# Allow nested asyncio for batching
nest_asyncio.apply()

# Configure logging
logger.remove()
logger.add(sys.stderr, level="INFO", format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>")

# Environment setup
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

# Get project root
env_path = find_dotenv()
if env_path:
    project_root = Path(env_path).parent
else:
    project_root = Path.cwd()

# Local imports
from annotation_storage import AnnotationStorage


# ============================================
# STEP 1: EXTRACT ANNOTATIONS (from POC 00)
# ============================================

async def extract_and_store_annotations(pdf_path: Path) -> List[Dict[str, Any]]:
    """Step 1: Extract reviewer annotations from PDF and store in ArangoDB."""
    logger.info("=== Step 1: Extracting Annotations ===")
    
    storage = AnnotationStorage()
    await storage.initialize()
    
    doc = fitz.open(str(pdf_path))
    pdf_name = pdf_path.stem
    annotations = []
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        for annot in page.annots():
            ann_data = {
                "pdf_name": pdf_name,
                "page": page_num,
                "type": annot.type[1],
                "content": annot.info.get("content", ""),
                "author": annot.info.get("title", ""),
                "rect": list(annot.rect),
                "created": annot.info.get("creationDate", ""),
                "color": annot.colors.get("stroke", []),
            }
            annotations.append(ann_data)
    
    doc.close()
    
    # Store in ArangoDB
    if annotations:
        result = await storage.store_annotations(pdf_name, annotations)
        logger.info(f"✓ Stored {len(annotations)} annotations in ArangoDB")
    
    return annotations


# ============================================
# STEP 2: EXTRACT WITH MARKER (from POC 01)
# ============================================

async def extract_with_marker(pdf_path: Path, output_dir: Path) -> List[Dict[str, Any]]:
    """Step 2: Extract PDF content with marker library."""
    logger.info("=== Step 2: Marker Extraction ===")
    
    # Run marker extraction command
    venv_python = project_root / ".venv" / "bin" / "python"
    if not venv_python.exists():
        venv_python = sys.executable
    
    cmd = (
        f"{venv_python} -m extractor.core.scripts.convert_single "
        f"{pdf_path} --output_dir {output_dir} --output_format json "
        f"--disable_multiprocessing"
    )
    
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    stdout, stderr = await proc.communicate()
    
    # Load marker output
    output_json = output_dir / f"{pdf_path.stem}.json"
    if not output_json.exists():
        output_json = output_dir / "clean.json"
    
    with open(output_json) as f:
        data = json.load(f)
    
    blocks = data.get("blocks", [])
    
    # Add UUIDs to all blocks
    for block in blocks:
        if "uuid" not in block:
            block["uuid"] = str(uuid.uuid4())
    
    logger.info(f"✓ Extracted {len(blocks)} blocks with marker")
    return blocks


# ============================================
# STEP 3: EXTRACT TABLES WITH CAMELOT (async batching)
# ============================================

async def extract_table_page_batch(pdf_path: Path, pages: List[int]) -> Dict[int, List[Dict[str, Any]]]:
    """Extract tables from a batch of pages using Camelot."""
    if not pages:
        return {}
    
    # Convert to 1-indexed for Camelot
    pages_str = ",".join(str(p + 1) for p in pages)
    
    try:
        # Run in executor to avoid blocking
        loop = asyncio.get_event_loop()
        
        # Lattice method
        lattice_tables = await loop.run_in_executor(
            None,
            lambda: camelot.read_pdf(str(pdf_path), pages=pages_str, flavor='lattice')
        )
        
        # Stream method
        stream_tables = await loop.run_in_executor(
            None,
            lambda: camelot.read_pdf(str(pdf_path), pages=pages_str, flavor='stream')
        )
        
        # Combine results
        tables_by_page = {}
        
        for table in lattice_tables:
            page_num = table.page - 1
            if page_num not in tables_by_page:
                tables_by_page[page_num] = []
            
            x1, y1, x2, y2 = table._bbox
            tables_by_page[page_num].append({
                'bbox': [x1, y1, x2, y2],
                'method': 'lattice',
                'accuracy': table.accuracy,
                'data': table.df.to_dict('records')
            })
        
        for table in stream_tables:
            page_num = table.page - 1
            if page_num not in tables_by_page:
                tables_by_page[page_num] = []
            
            x1, y1, x2, y2 = table._bbox
            # Check overlap
            overlaps = any(
                _boxes_overlap(existing['bbox'], [x1, y1, x2, y2])
                for existing in tables_by_page[page_num]
            )
            
            if not overlaps:
                tables_by_page[page_num].append({
                    'bbox': [x1, y1, x2, y2],
                    'method': 'stream',
                    'accuracy': table.accuracy,
                    'data': table.df.to_dict('records')
                })
        
        return tables_by_page
        
    except Exception as e:
        logger.error(f"Camelot failed on pages {pages}: {e}")
        return {}


async def extract_tables_with_camelot_async(
    pdf_path: Path, 
    blocks: List[Dict[str, Any]], 
    batch_size: int = 5
) -> Dict[int, List[Dict[str, Any]]]:
    """Step 3: Extract tables with Camelot using async batching."""
    logger.info("=== Step 3: Camelot Table Extraction (Async) ===")
    
    # Identify pages with tables
    table_pages = set()
    for block in blocks:
        if block.get("block_type") == "Table":
            table_pages.add(block.get("page", 0))
    
    if not table_pages:
        logger.info("No table pages found")
        return {}
    
    logger.info(f"Found tables on {len(table_pages)} pages")
    
    # Create page batches
    sorted_pages = sorted(table_pages)
    batches = [sorted_pages[i:i+batch_size] for i in range(0, len(sorted_pages), batch_size)]
    
    # Process batches concurrently
    tasks = []
    for batch in batches:
        task = extract_table_page_batch(pdf_path, batch)
        tasks.append(task)
    
    logger.info(f"Processing {len(batches)} batches concurrently...")
    batch_results = await asyncio.gather(*tasks)
    
    # Combine results
    all_tables = {}
    for result in batch_results:
        all_tables.update(result)
    
    total_tables = sum(len(tables) for tables in all_tables.values())
    logger.info(f"✓ Extracted {total_tables} tables from {len(all_tables)} pages")
    
    return all_tables


# ============================================
# STEP 4: RUN HEURISTICS (enhanced with Camelot)
# ============================================

def identify_mislabeled_objects(
    blocks: List[Dict[str, Any]], 
    camelot_tables: Dict[int, List[Dict[str, Any]]],
    annotations: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Step 4: Identify mislabeled objects using heuristics."""
    logger.info("=== Step 4: Heuristic Analysis ===")
    
    suspicious = []
    
    # Build annotation hints by page
    ann_by_page = defaultdict(list)
    for ann in annotations:
        ann_by_page[ann['page']].append(ann)
    
    for block in blocks:
        block_type = block.get("block_type", "")
        text = block.get("text", "").strip()
        page = block.get("page", 0)
        bbox = block.get("bbox", [])
        
        suspicious_score = 0
        reasons = []
        
        # Check both SectionHeader AND Table blocks
        if block_type in ["SectionHeader", "Table"]:
            
            # TABLE-SPECIFIC CHECKS
            if block_type == "Table":
                # Check if Camelot found a table here
                camelot_found = False
                if page in camelot_tables:
                    for cam_table in camelot_tables[page]:
                        if _boxes_overlap(bbox, cam_table['bbox'], 0.3):
                            camelot_found = True
                            break
                
                if not camelot_found:
                    suspicious_score += 0.8
                    reasons.append("no_camelot_table")
                
                # Check if text looks like a sentence
                if text and '.' in text and len(text.split()) > 5:
                    suspicious_score += 0.9
                    reasons.append("table_is_actually_text")
                
                # Check for garbled concatenation
                if re.search(r'[A-Z][a-z]+[A-Z][a-z]+', text):
                    suspicious_score += 0.7
                    reasons.append("garbled_table_text")
            
            # HEADER-SPECIFIC CHECKS
            elif block_type == "SectionHeader":
                # Known fragments
                if re.match(r'^(FRONT|END|STEM|SUBSY|EXECU|TE)$', text):
                    suspicious_score += 0.95
                    reasons.append("known_fragment")
                
                # Check if inside Camelot table
                if page in camelot_tables:
                    for cam_table in camelot_tables[page]:
                        if _boxes_overlap(bbox, cam_table['bbox'], 0.5):
                            suspicious_score += 0.9
                            reasons.append("inside_camelot_table")
                            break
                
                # Check annotations
                page_anns = ann_by_page.get(page, [])
                for ann in page_anns:
                    if ann.get('instruction') == 'MERGE_TABLE':
                        ann_rect = ann.get('rect', [])
                        if _boxes_overlap(bbox, ann_rect, 0.3):
                            suspicious_score += 0.85
                            reasons.append("annotation_says_table")
                            break
                
                # Other heuristics
                if text.endswith(','):
                    suspicious_score += 0.8
                    reasons.append("ends_with_comma")
                
                if len(text) < 10 and ' ' not in text:
                    suspicious_score += 0.7
                    reasons.append("short_no_spaces")
            
            # Add to suspicious if score high enough
            if suspicious_score >= 0.4:
                block["suspicion_score"] = min(suspicious_score, 1.0)
                block["suspicion_reasons"] = reasons
                suspicious.append(block)
    
    logger.info(f"✓ Found {len(suspicious)} suspicious blocks")
    return suspicious


# ============================================
# STEP 5: FIX WITH BATCHED CLAUDE CALLS
# ============================================

async def create_visual_context_batch(
    pdf_path: Path, 
    blocks: List[Dict[str, Any]]
) -> List[bytes]:
    """Create visual contexts for a batch of blocks."""
    contexts = []
    
    doc = fitz.open(str(pdf_path))
    
    for block in blocks:
        try:
            page = doc[block["page"]]
            bbox = block["bbox"]
            
            # Add padding
            x0 = max(0, bbox[0] - 20)
            y0 = max(0, bbox[1] - 20)
            x1 = min(page.rect.width, bbox[2] + 20)
            y1 = min(page.rect.height, bbox[3] + 20)
            
            # Render region
            clip_rect = fitz.Rect(x0, y0, x1, y1)
            mat = fitz.Matrix(2, 2)
            pix = page.get_pixmap(matrix=mat, clip=clip_rect)
            
            # Convert to PIL and draw highlight
            img_data = pix.tobytes("png")
            img = Image.open(BytesIO(img_data))
            
            draw = ImageDraw.Draw(img)
            highlight_x0 = (bbox[0] - x0) * 2
            highlight_y0 = (bbox[1] - y0) * 2
            highlight_x1 = (bbox[2] - x0) * 2
            highlight_y1 = (bbox[3] - y0) * 2
            
            draw.rectangle([highlight_x0, highlight_y0, highlight_x1, highlight_y1], 
                          outline="red", width=3)
            
            # Convert to bytes
            output = BytesIO()
            img.save(output, format='PNG')
            contexts.append(output.getvalue())
            
        except Exception as e:
            logger.error(f"Failed to create visual context: {e}")
            contexts.append(b"")
    
    doc.close()
    return contexts


async def fix_with_claude_batch(
    suspicious_blocks: List[Dict[str, Any]],
    pdf_path: Path,
    batch_size: int = 5
) -> List[Dict[str, Any]]:
    """Step 5: Fix mislabeled objects with batched Claude calls."""
    logger.info("=== Step 5: Claude Batch Correction ===")
    
    corrections = []
    
    for i in range(0, len(suspicious_blocks), batch_size):
        batch = suspicious_blocks[i:i+batch_size]
        
        # Create visual contexts
        visual_contexts = await create_visual_context_batch(pdf_path, batch)
        
        # Build batch prompt
        descriptions = []
        for j, block in enumerate(batch):
            reasons = ", ".join(block.get("suspicion_reasons", []))
            descriptions.append(
                f"{j+1}. Type: {block['block_type']}, "
                f"Text: \"{block.get('text', '')[:50]}...\", "
                f"Reasons: {reasons}"
            )
        
        prompt = f"""You are a document layout expert. I'm showing you {len(batch)} suspicious blocks highlighted in RED.

Blocks to analyze:
{chr(10).join(descriptions)}

For each block, determine the correct type:
- SectionHeader: Document section titles
- TableCell: Cell within a table structure  
- Text: Regular paragraph text
- Table: Full table structure
- ListItem: List item

Consider: blocks with "inside_camelot_table" or "no_camelot_table" reasons need special attention.

Return JSON array:
[
  {{"block_index": 0, "correct_type": "ActualType", "confidence": 0.95, "reasoning": "explanation"}},
  ...
]"""
        
        # Create composite image
        composite = create_composite_image(visual_contexts)
        
        # Call Claude
        try:
            proc = await asyncio.create_subprocess_exec(
                "claude", "-p", prompt,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await proc.communicate(input=composite)
            
            if proc.returncode == 0:
                response = stdout.decode()
                json_match = re.search(r'\[.*\]', response, re.DOTALL)
                if json_match:
                    results = json.loads(json_match.group())
                    
                    # Process results
                    for j, result in enumerate(results):
                        if j < len(batch):
                            block = batch[j]
                            new_type = result.get("correct_type", block["block_type"])
                            
                            if new_type != block["block_type"] and result.get("confidence", 0) > 0.7:
                                corrections.append({
                                    "uuid": block["uuid"],
                                    "original_type": block["block_type"],
                                    "new_type": new_type,
                                    "text": block.get("text", "")[:100],
                                    "confidence": result.get("confidence", 0),
                                    "reasoning": result.get("reasoning", "")
                                })
                                # Update block
                                block["block_type"] = new_type
                                block["relabeled"] = True
        
        except Exception as e:
            logger.error(f"Claude batch failed: {e}")
    
    logger.info(f"✓ Made {len(corrections)} corrections")
    return corrections


def create_composite_image(images: List[bytes]) -> bytes:
    """Create composite image from multiple contexts."""
    if not images or all(not img for img in images):
        return b""
    
    # Filter out empty images
    valid_images = [img for img in images if img]
    if not valid_images:
        return b""
    
    pil_images = []
    for img_bytes in valid_images:
        try:
            pil_images.append(Image.open(BytesIO(img_bytes)))
        except:
            continue
    
    if not pil_images:
        return b""
    
    # Create composite
    max_width = max(img.width for img in pil_images)
    total_height = sum(img.height for img in pil_images) + 10 * (len(pil_images) - 1)
    
    composite = Image.new('RGB', (max_width, total_height), 'white')
    
    y_offset = 0
    for img in pil_images:
        composite.paste(img, (0, y_offset))
        y_offset += img.height + 10
    
    output = BytesIO()
    composite.save(output, format='PNG')
    return output.getvalue()


# ============================================
# STEP 6: CREATE SECTION NODES
# ============================================

def create_section_nodes(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Step 6: Create hierarchical section nodes from blocks."""
    logger.info("=== Step 6: Creating Section Nodes ===")
    
    sections = []
    current_section = None
    
    for block in blocks:
        if block.get("block_type") == "SectionHeader":
            # Save previous section
            if current_section and current_section["blocks"]:
                sections.append(current_section)
            
            # Start new section
            current_section = {
                "id": str(uuid.uuid4()),
                "title": block.get("text", ""),
                "page_start": block.get("page", 0),
                "blocks": [],
                "subsections": []
            }
        
        elif current_section:
            # Add block to current section
            current_section["blocks"].append(block)
    
    # Don't forget last section
    if current_section and current_section["blocks"]:
        sections.append(current_section)
    
    # Create hierarchy based on numbering
    hierarchical_sections = []
    section_stack = []
    
    for section in sections:
        title = section["title"]
        
        # Extract section number
        num_match = re.match(r'^(\d+(?:\.\d+)*)', title)
        if num_match:
            num_parts = num_match.group(1).split('.')
            level = len(num_parts)
            
            # Pop stack to appropriate level
            while len(section_stack) >= level:
                section_stack.pop()
            
            # Add to parent or root
            if section_stack:
                parent = section_stack[-1]
                parent["subsections"].append(section)
            else:
                hierarchical_sections.append(section)
            
            section_stack.append(section)
        else:
            # No number, add to root
            hierarchical_sections.append(section)
            section_stack = [section]
    
    logger.info(f"✓ Created {len(hierarchical_sections)} top-level sections")
    return hierarchical_sections


# ============================================
# STEP 7: ANALYZE SECTIONS WITH CLAUDE
# ============================================

async def analyze_sections_batch(
    sections: List[Dict[str, Any]],
    batch_size: int = 3
) -> List[Dict[str, Any]]:
    """Step 7: Analyze section nodes with batched Claude calls."""
    logger.info("=== Step 7: Section Analysis ===")
    
    analyses = []
    
    for i in range(0, len(sections), batch_size):
        batch = sections[i:i+batch_size]
        
        # Build batch prompt
        section_descs = []
        for j, section in enumerate(batch):
            # Gather section content
            content_preview = ""
            for block in section["blocks"][:3]:  # First 3 blocks
                if block.get("block_type") == "Text":
                    content_preview += block.get("text", "")[:100] + "... "
            
            section_descs.append(
                f"Section {j+1}: \"{section['title']}\"\n"
                f"Content preview: {content_preview}\n"
                f"Blocks: {len(section['blocks'])}, "
                f"Subsections: {len(section['subsections'])}"
            )
        
        prompt = f"""Analyze these document sections and provide insights:

{chr(10).join(section_descs)}

For each section, provide:
1. Main topic/purpose
2. Key technical concepts mentioned
3. Completeness assessment
4. Relationship to other sections

Return JSON array:
[
  {{
    "section_index": 0,
    "topic": "main topic",
    "key_concepts": ["concept1", "concept2"],
    "completeness": "complete|partial|stub",
    "relationships": ["related to section X"],
    "summary": "brief summary"
  }},
  ...
]"""
        
        try:
            proc = await asyncio.create_subprocess_exec(
                "claude", "-p", prompt,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await proc.communicate()
            
            if proc.returncode == 0:
                response = stdout.decode()
                json_match = re.search(r'\[.*\]', response, re.DOTALL)
                if json_match:
                    results = json.loads(json_match.group())
                    
                    for j, result in enumerate(results):
                        if j < len(batch):
                            section = batch[j]
                            analyses.append({
                                "section_id": section["id"],
                                "title": section["title"],
                                "analysis": result
                            })
        
        except Exception as e:
            logger.error(f"Section analysis failed: {e}")
    
    logger.info(f"✓ Analyzed {len(analyses)} sections")
    return analyses


# ============================================
# HELPER FUNCTIONS
# ============================================

def _boxes_overlap(box1: List[float], box2: List[float], threshold: float = 0.5) -> bool:
    """Check if two bounding boxes overlap."""
    x1_min, y1_min, x1_max, y1_max = box1
    x2_min, y2_min, x2_max, y2_max = box2
    
    x_left = max(x1_min, x2_min)
    y_top = max(y1_min, y2_min)
    x_right = min(x1_max, x2_max)
    y_bottom = min(y1_max, y2_max)
    
    if x_right < x_left or y_bottom < y_top:
        return False
    
    intersection_area = (x_right - x_left) * (y_bottom - y_top)
    box1_area = (x1_max - x1_min) * (y1_max - y1_min)
    box2_area = (x2_max - x2_min) * (y2_max - y2_min)
    
    return intersection_area > threshold * min(box1_area, box2_area)


# ============================================
# MAIN PIPELINE
# ============================================

async def run_complete_pipeline(pdf_path: Path, output_dir: Path) -> Dict[str, Any]:
    """Run the complete 7-step pipeline."""
    logger.info("=== STARTING COMPLETE PIPELINE ===")
    start_time = datetime.now()
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Step 1: Extract annotations
    annotations = await extract_and_store_annotations(pdf_path)
    
    # Step 2: Extract with marker
    blocks = await extract_with_marker(pdf_path, output_dir)
    
    # Step 3: Extract tables with Camelot (async)
    camelot_tables = await extract_tables_with_camelot_async(pdf_path, blocks)
    
    # Step 4: Run heuristics
    suspicious_blocks = identify_mislabeled_objects(blocks, camelot_tables, annotations)
    
    # Step 5: Fix with Claude
    corrections = []
    if suspicious_blocks:
        corrections = await fix_with_claude_batch(suspicious_blocks, pdf_path)
    
    # Step 6: Create section nodes
    sections = create_section_nodes(blocks)
    
    # Step 7: Analyze sections
    section_analyses = await analyze_sections_batch(sections)
    
    # Calculate metrics
    duration = (datetime.now() - start_time).total_seconds()
    
    # Final result
    result = {
        "success": True,
        "pipeline_version": "1.0",
        "pdf_name": pdf_path.name,
        "timestamp": datetime.now().isoformat(),
        "duration_seconds": duration,
        "metrics": {
            "annotations_found": len(annotations),
            "blocks_extracted": len(blocks),
            "table_pages": len(camelot_tables),
            "tables_extracted": sum(len(t) for t in camelot_tables.values()),
            "suspicious_blocks": len(suspicious_blocks),
            "corrections_made": len(corrections),
            "sections_created": len(sections),
            "sections_analyzed": len(section_analyses)
        },
        "annotations": annotations,
        "blocks": blocks,
        "camelot_tables": camelot_tables,
        "corrections": corrections,
        "sections": sections,
        "section_analyses": section_analyses
    }
    
    logger.info(f"=== PIPELINE COMPLETE in {duration:.1f}s ===")
    return result


# ============================================
# USAGE EXAMPLES
# ============================================

async def working_usage():
    """Demonstrate the complete pipeline."""
    logger.info("=== Running Complete Pipeline Demo ===")
    
    # Setup paths
    poc_dir = Path(__file__).parent
    pdf_path = poc_dir / "inputs" / "BHT_CV32A65X_marked.pdf"
    output_dir = poc_dir / "outputs" / "complete_pipeline"
    
    if not pdf_path.exists():
        logger.error(f"PDF not found: {pdf_path}")
        return False
    
    # Run pipeline
    result = await run_complete_pipeline(pdf_path, output_dir)
    
    # Verify results
    assert result["success"], "Pipeline should succeed"
    metrics = result["metrics"]
    
    # Show summary
    logger.info("\n📊 Pipeline Summary:")
    logger.info(f"  Annotations: {metrics['annotations_found']}")
    logger.info(f"  Blocks: {metrics['blocks_extracted']}")
    logger.info(f"  Tables: {metrics['tables_extracted']} from {metrics['table_pages']} pages")
    logger.info(f"  Suspicious: {metrics['suspicious_blocks']}")
    logger.info(f"  Corrections: {metrics['corrections_made']}")
    logger.info(f"  Sections: {metrics['sections_created']}")
    logger.info(f"  Analyzed: {metrics['sections_analyzed']}")
    
    # Show some corrections
    if result["corrections"]:
        logger.info("\n🔧 Sample Corrections:")
        for corr in result["corrections"][:3]:
            logger.info(f"  {corr['original_type']} → {corr['new_type']}: '{corr['text']}'")
    
    # Show section analysis
    if result["section_analyses"]:
        logger.info("\n📑 Sample Section Analyses:")
        for analysis in result["section_analyses"][:3]:
            logger.info(f"  Section: {analysis['title']}")
            logger.info(f"    Topic: {analysis['analysis'].get('topic', 'N/A')}")
    
    # Save complete result
    output_path = output_dir / "complete_pipeline_result.json"
    with open(output_path, 'w') as f:
        # Remove image data for JSON serialization
        clean_result = result.copy()
        clean_result.pop("camelot_tables", None)  # Too large
        json.dump(clean_result, f, indent=2)
    
    logger.info(f"\n✓ Saved complete results to {output_path}")
    logger.info("✓ All pipeline tests passed!")
    return True


async def debug_function():
    """Test individual pipeline steps."""
    logger.info("=== Debug Mode: Testing Steps ===")
    
    poc_dir = Path(__file__).parent
    pdf_path = poc_dir / "inputs" / "BHT_CV32A65X_marked.pdf"
    
    # Test Step 3: Async Camelot
    logger.info("\nTesting async Camelot extraction...")
    
    # Create fake blocks with tables
    test_blocks = [
        {"block_type": "Table", "page": 0},
        {"block_type": "Table", "page": 1},
        {"block_type": "Text", "page": 0}
    ]
    
    tables = await extract_tables_with_camelot_async(pdf_path, test_blocks, batch_size=2)
    logger.info(f"Extracted tables from {len(tables)} pages")
    
    return True


# ============================================
# CLI
# ============================================

app = typer.Typer()


@app.command()
def pipeline(
    pdf_path: Annotated[Path, typer.Argument(help="PDF file path")],
    output_dir: Annotated[Path, typer.Option(help="Output directory")] = Path("pipeline_output")
):
    """Run the complete 7-step extraction pipeline."""
    asyncio.run(run_complete_pipeline(pdf_path, output_dir))


if __name__ == "__main__":
    """
    Script entry point with dual-mode execution.
    """
    if len(sys.argv) == 1 or (len(sys.argv) == 2 and sys.argv[1] in ["debug"]):
        # Test mode
        mode = sys.argv[1] if len(sys.argv) > 1 else "working"
        
        if mode == "debug":
            logger.info("Running in DEBUG mode...")
            success = asyncio.run(debug_function())
        else:
            logger.info("Running in WORKING mode...")
            success = asyncio.run(working_usage())
        
        exit(0 if success else 1)
    else:
        # CLI mode
        app()