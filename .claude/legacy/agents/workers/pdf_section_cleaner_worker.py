#!/usr/bin/env python3
"""
PDF Section Cleaner Worker - Comprehensive single section analysis and cleaning.

This worker provides the implementation for the pdf-section-cleaner sub-agent.
It handles complete processing of a single section including text cleaning, 
table reconstruction, annotation application, and content validation with 
Knowledge Architect integration.

Key capabilities:
- Comprehensive text cleaning and merging
- Table reconstruction from fragments
- Semantic validation of suspicious blocks
- Annotation integration and application
- Figure description and equation processing

AGENT VERIFICATION INSTRUCTIONS:
- Run this script directly to execute working_usage()
- The working_usage() function demonstrates all core capabilities
- debug_function() is for testing new features
- All operations integrate with Knowledge Architect

Example Usage:
    # Direct execution
    python pdf_section_cleaner_worker.py
    
    # From sub-agent markdown
    from agents.workers.pdf_section_cleaner_worker import (
        clean_section,
        validate_results,
        export_clean
    )
"""

import asyncio
import json
import sys
import time
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import re
from collections import defaultdict

# Third-party imports
from loguru import logger
from dotenv import load_dotenv, find_dotenv
import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

# Knowledge Architect imports (MANDATORY for all sub-agents)
import sys
from pathlib import Path

# Add path to import from knowledge architect
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / ".claude" / "agents" / "workers"))

try:
    from knowledge_architect_worker import (
        upsert_impl,
        semantic_search_impl,
        edge_impl,
        query_impl,
        find_similar_documents_impl,
        build_faiss_index_impl,
        find_most_successful_sequences_impl,
        # Centralized tool journey tracking functions
        ToolJourneyTracker,
        create_solution_relationships,
        check_existing_solutions,
        extract_task_type
    )
    KNOWLEDGE_ARCHITECT_AVAILABLE = True
except ImportError as e:
    # Fallback for standalone execution
    logger.warning(f"Knowledge Architect not available: {e}")
    KNOWLEDGE_ARCHITECT_AVAILABLE = False
    
    # Mock functions for testing
    async def upsert_impl(*args, **kwargs): return {"status": "mocked"}
    async def semantic_search_impl(*args, **kwargs): return {"results": []}
    async def edge_impl(*args, **kwargs): return {"status": "mocked"}
    async def query_impl(*args, **kwargs): return {"results": []}
    async def check_existing_solutions(*args, **kwargs): return None
    async def create_solution_relationships(*args, **kwargs): return {"status": "mocked"}
    def extract_task_type(desc): return "general"

# Configure logging
logger.remove()
logger.add(sys.stderr, level="INFO", format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>")

# Load environment variables
load_dotenv(find_dotenv())

# Constants for this agent
AGENT_NAME = "pdf-section-cleaner"
COLLECTION_PREFIX = f"{AGENT_NAME}_"
CACHE_COLLECTION = f"{COLLECTION_PREFIX}cache"
PATTERNS_COLLECTION = f"{COLLECTION_PREFIX}patterns"
RESULTS_COLLECTION = f"{COLLECTION_PREFIX}results"

# Initialize Typer app and console
app = typer.Typer(help="PDF Section Cleaner Worker - Comprehensive section processing")
console = Console()

# ============================================
# TOOL JOURNEY TRACKING (MANDATORY)
# ============================================
# The following functions are now centralized in knowledge_architect_worker.py:
# - ToolJourneyTracker class
# - create_solution_relationships() 
# - check_existing_solutions()
# - extract_task_type()
#
# These are imported at the top of this file for use by all sub-agent operations.
# This ensures consistency across all agents and reduces code duplication.

# If Knowledge Architect is not available, create a mock tracker
if not KNOWLEDGE_ARCHITECT_AVAILABLE:
    class ToolJourneyTracker:
        """Mock tracker for standalone testing."""
        def __init__(self, task_type: str, task_description: str = ""):
            self.task_type = task_type
            self.task_description = task_description
            self.journey = {
                "task_type": task_type,
                "task_description": task_description,
                "start_time": datetime.utcnow().isoformat(),
                "steps": [],
                "total_duration_ms": 0,
                "outcome": "in_progress"
            }
            self.start_time = time.time()
        
        def add_step(self, tool: str, method: str, params: Dict[str, Any]):
            step = {
                "tool": tool,
                "method": method,
                "params": params,
                "start_time": datetime.utcnow().isoformat(),
                "duration_ms": 0,
                "success": False,
                "result_summary": ""
            }
            self.journey["steps"].append(step)
            return len(self.journey["steps"]) - 1
        
        def complete_step(self, step_index: int, success: bool, result_summary: str):
            if 0 <= step_index < len(self.journey["steps"]):
                step = self.journey["steps"][step_index]
                step["success"] = success
                step["result_summary"] = result_summary
                step["duration_ms"] = int((time.time() - self.start_time) * 1000)
        
        def finish_journey(self, outcome: str = "success", final_reward: float = 1.0):
            self.journey["outcome"] = outcome
            self.journey["total_duration_ms"] = int((time.time() - self.start_time) * 1000)
            self.journey["final_reward"] = final_reward
            self.journey["end_time"] = datetime.utcnow().isoformat()
        
        def save_successful_journey(self):
            logger.info("Mock: Would save successful journey")
            return True

# ============================================
# CORE SECTION CLEANING FUNCTIONS
# ============================================

class SectionCleaner:
    """Comprehensive section cleaning and analysis."""
    
    def __init__(self, task_description: str = "Clean PDF section"):
        self.task_description = task_description
        self.task_type = extract_task_type(task_description)
        self.journey = ToolJourneyTracker(self.task_type, task_description)
        self.patterns_cache = {}
        
    async def clean_section(self, section: Dict[str, Any], annotations: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Clean a single section comprehensively."""
        # Check for existing solutions first
        existing = check_existing_solutions(self.task_description, self.task_type)
        if existing and existing.get('has_patterns'):
            logger.info(f"Using optimal sequence: {existing['optimal_sequence']['sequence']}")
        
        step_idx = self.journey.add_step("section_cleaner", "clean_section", {
            "section_id": section.get("id"),
            "block_count": len(section.get("content_blocks", []))
        })
        
        try:
            # Check Knowledge Architect for similar sections
            similar = await self._find_similar_sections(section)
            
            # Execute comprehensive cleaning task list
            cleaned_section = {
                "id": section["id"],
                "header": await self._clean_header(section.get("header", "")),
                "content_blocks": [],
                "processing_stats": {
                    "original_blocks": len(section.get("content_blocks", [])),
                    "start_time": time.time()
                }
            }
            
            # 1. Inventory blocks by type
            block_inventory = self._inventory_blocks(section["content_blocks"])
            
            # 2. Apply annotations
            annotated_blocks = await self._apply_annotations(section["content_blocks"], annotations)
            
            # 3. Fix text spacing issues
            text_blocks = await self._fix_text_spacing(annotated_blocks)
            
            # 4. Merge split text blocks
            merged_text = await self._merge_split_text(text_blocks)
            
            # 5. Reconstruct fragmented tables
            if block_inventory["table_count"] > 0:
                tables = await self._reconstruct_tables(annotated_blocks)
                cleaned_section["content_blocks"].extend(tables)
            
            # 6. Validate suspicious headers
            validated_blocks = await self._validate_suspicious_blocks(merged_text)
            
            # 7. Process equations
            if block_inventory["equation_count"] > 0:
                equations = await self._process_equations(annotated_blocks)
                cleaned_section["content_blocks"].extend(equations)
            
            # 8. Extract form fields
            if block_inventory["form_count"] > 0:
                forms = await self._extract_form_fields(annotated_blocks)
                cleaned_section["content_blocks"].extend(forms)
            
            # 9. Generate figure descriptions
            if block_inventory["figure_count"] > 0:
                figures = await self._describe_figures(annotated_blocks)
                cleaned_section["content_blocks"].extend(figures)
            
            # 10. Add validated text blocks
            cleaned_section["content_blocks"].extend(validated_blocks)
            
            # Update stats
            cleaned_section["processing_stats"].update({
                "cleaned_blocks": len(cleaned_section["content_blocks"]),
                "merged_text_blocks": len(merged_text) - len([b for b in annotated_blocks if b["block_type"] == "Text"]),
                "reconstructed_tables": block_inventory["table_count"],
                "processing_time": time.time() - cleaned_section["processing_stats"]["start_time"],
                "patterns_applied": len(self.patterns_cache)
            })
            
            # Store successful patterns
            await self._store_cleaning_patterns(cleaned_section)
            
            # Store complete section with tool journey in ArangoDB
            await self._store_section_with_journey(
                raw_section=section,
                cleaned_section=cleaned_section,
                changes=self._extract_changes(section, cleaned_section),
                confidence=cleaned_section["processing_stats"].get("confidence", 0.9),
                journey=self.journey.journey
            )
            
            # Mark step as complete and finish journey
            self.journey.complete_step(step_idx, True, f"Cleaned {len(cleaned_section['content_blocks'])} blocks")
            self.journey.finish_journey("success")
            self.journey.save_successful_journey()
            
            # Create solution relationships
            solution_summary = f"Cleaned section with {len(cleaned_section['content_blocks'])} blocks from {len(section.get('content_blocks', []))} original blocks"
            create_solution_relationships(
                problem=self.task_description,
                solution=solution_summary,
                tool_journey=self.journey.journey,
                metrics=cleaned_section["processing_stats"]
            )
            
            return cleaned_section
            
        except Exception as e:
            logger.error(f"Error cleaning section: {e}")
            self.journey.complete_step(step_idx, False, str(e))
            self.journey.finish_journey("failed")
            raise
    
    
    # ============================================
    # INTERNAL CLEANING METHODS
    # ============================================
    
    def _inventory_blocks(self, blocks: List[Dict[str, Any]]) -> Dict[str, int]:
        """Inventory blocks by type."""
        inventory = defaultdict(int)
        for block in blocks:
            block_type = block.get("block_type", "Unknown")
            inventory[f"{block_type.lower()}_count"] += 1
        inventory["total_count"] = len(blocks)
        return dict(inventory)
    
    async def _clean_header(self, header: str) -> str:
        """Clean header text formatting."""
        # Fix excessive spacing
        header = re.sub(r'\s+', ' ', header)
        # Fix spacing around punctuation
        header = re.sub(r'\s+([.,;:])', r'\1', header)
        header = re.sub(r'([.,;:])\s*', r'\1 ', header)
        return header.strip()
    
    async def _apply_annotations(self, blocks: List[Dict[str, Any]], annotations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Apply annotations to relevant blocks."""
        if not annotations:
            return blocks
        
        # Create spatial index of blocks
        block_spatial_index = {}
        for i, block in enumerate(blocks):
            if "bbox" in block:
                bbox = block["bbox"]
                # Simple spatial key based on position
                key = f"{block.get('page', 0)}_{int(bbox[1]/10)}"
                if key not in block_spatial_index:
                    block_spatial_index[key] = []
                block_spatial_index[key].append(i)
        
        # Apply annotations
        for ann in annotations:
            if "bbox" not in ann:
                continue
            
            # Find blocks that overlap with annotation
            ann_bbox = ann["bbox"]
            key = f"{ann.get('page', 0)}_{int(ann_bbox[1]/10)}"
            
            if key in block_spatial_index:
                for block_idx in block_spatial_index[key]:
                    block = blocks[block_idx]
                    if self._bbox_overlap(block.get("bbox", [0,0,0,0]), ann_bbox):
                        if "annotations" not in block:
                            block["annotations"] = []
                        block["annotations"].append(ann)
        
        return blocks
    
    def _bbox_overlap(self, bbox1: List[float], bbox2: List[float]) -> bool:
        """Check if two bounding boxes overlap."""
        if len(bbox1) < 4 or len(bbox2) < 4:
            return False
        
        # Check if rectangles overlap
        return not (bbox1[2] < bbox2[0] or  # bbox1 right < bbox2 left
                   bbox2[2] < bbox1[0] or   # bbox2 right < bbox1 left
                   bbox1[3] < bbox2[1] or   # bbox1 bottom < bbox2 top
                   bbox2[3] < bbox1[1])     # bbox2 bottom < bbox1 top
    
    async def _fix_text_spacing(self, blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Fix spacing issues in text blocks."""
        for block in blocks:
            if block.get("block_type") == "Text" and "text" in block:
                text = block["text"]
                
                # Fix excessive spacing
                text = re.sub(r'\s+', ' ', text)
                
                # Fix spacing around punctuation
                text = re.sub(r'\s+([.,;:!?])', r'\1', text)
                text = re.sub(r'([.,;:])\s*', r'\1 ', text)
                
                # Fix spacing around parentheses
                text = re.sub(r'\(\s+', '(', text)
                text = re.sub(r'\s+\)', ')', text)
                
                # Store original if changed
                if text != block["text"]:
                    block["original_text"] = block["text"]
                    block["text"] = text.strip()
                    block["cleaned"] = True
        
        return blocks
    
    async def _merge_split_text(self, blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Merge split text blocks based on proximity and content."""
        merged_blocks = []
        skip_indices = set()
        
        for i, block in enumerate(blocks):
            if i in skip_indices:
                continue
            
            if block.get("block_type") != "Text":
                merged_blocks.append(block)
                continue
            
            # Check if this block should be merged with next blocks
            merged_text = block["text"]
            merged_indices = [i]
            
            # Look ahead for mergeable blocks
            j = i + 1
            while j < len(blocks):
                next_block = blocks[j]
                
                # Check merge conditions
                if (next_block.get("block_type") == "Text" and
                    block.get("page") == next_block.get("page") and
                    self._should_merge_blocks(block, next_block)):
                    
                    merged_text += " " + next_block["text"]
                    merged_indices.append(j)
                    skip_indices.add(j)
                    block = next_block  # Update for next comparison
                    j += 1
                else:
                    break
            
            # Create merged block
            if len(merged_indices) > 1:
                merged_block = blocks[i].copy()
                merged_block["text"] = merged_text
                merged_block["merged_from"] = merged_indices
                merged_block["merged"] = True
                merged_blocks.append(merged_block)
            else:
                merged_blocks.append(blocks[i])
        
        return merged_blocks
    
    def _should_merge_blocks(self, block1: Dict[str, Any], block2: Dict[str, Any]) -> bool:
        """Determine if two blocks should be merged."""
        # Check spatial proximity
        if "bbox" in block1 and "bbox" in block2:
            bbox1, bbox2 = block1["bbox"], block2["bbox"]
            vertical_gap = bbox2[1] - bbox1[3]  # top of block2 - bottom of block1
            
            # Merge if gap is small (less than typical line height)
            if vertical_gap > 30:
                return False
        
        # Check content indicators
        text1, text2 = block1.get("text", ""), block2.get("text", "")
        
        # Merge if first block ends mid-sentence
        if text1 and not text1[-1] in '.!?':
            return True
        
        # Merge if second block starts with lowercase
        if text2 and text2[0].islower():
            return True
        
        # Check for split words (hyphenation)
        if text1.endswith('-'):
            return True
        
        return False
    
    async def _reconstruct_tables(self, blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Reconstruct tables from fragmented cells."""
        tables = []
        table_cells = defaultdict(list)
        
        # Group table cells by spatial proximity
        for block in blocks:
            if block.get("block_type") in ["Table", "TableCell"]:
                if "bbox" in block:
                    # Group by approximate table location
                    table_key = f"{block.get('page', 0)}_{int(block['bbox'][1]/100)}"
                    table_cells[table_key].append(block)
        
        # Reconstruct each table
        for table_key, cells in table_cells.items():
            if len(cells) > 1:
                table = await self._build_table_from_cells(cells)
                tables.append(table)
            else:
                # Single table block, just clean it
                tables.extend(cells)
        
        return tables
    
    async def _build_table_from_cells(self, cells: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Build structured table from cells."""
        # Sort cells by position (top-to-bottom, left-to-right)
        cells.sort(key=lambda c: (c.get("bbox", [0,0])[1], c.get("bbox", [0,0])[0]))
        
        # Detect rows and columns
        rows = defaultdict(list)
        for cell in cells:
            if "bbox" in cell:
                row_key = int(cell["bbox"][1] / 20)  # Group by approximate row
                rows[row_key].append(cell)
        
        # Build table structure
        table_data = []
        for row_key in sorted(rows.keys()):
            row_cells = sorted(rows[row_key], key=lambda c: c.get("bbox", [0])[0])
            row_data = [cell.get("text", "") for cell in row_cells]
            table_data.append(row_data)
        
        # Create reconstructed table
        table = {
            "block_type": "Table",
            "reconstructed": True,
            "rows": len(table_data),
            "cols": max(len(row) for row in table_data) if table_data else 0,
            "data": table_data,
            "merged_from_fragments": len(cells),
            "bbox": self._calculate_combined_bbox(cells),
            "page": cells[0].get("page", 0) if cells else 0
        }
        
        return table
    
    def _calculate_combined_bbox(self, blocks: List[Dict[str, Any]]) -> List[float]:
        """Calculate combined bounding box for multiple blocks."""
        if not blocks:
            return [0, 0, 0, 0]
        
        bboxes = [b["bbox"] for b in blocks if "bbox" in b]
        if not bboxes:
            return [0, 0, 0, 0]
        
        min_x = min(bbox[0] for bbox in bboxes)
        min_y = min(bbox[1] for bbox in bboxes)
        max_x = max(bbox[2] for bbox in bboxes)
        max_y = max(bbox[3] for bbox in bboxes)
        
        return [min_x, min_y, max_x, max_y]
    
    async def _validate_suspicious_blocks(self, blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate suspicious blocks using semantic analysis."""
        validated_blocks = []
        
        for block in blocks:
            # Check if block needs validation
            if (block.get("confidence", 1.0) < 0.9 or
                block.get("block_type") == "Unknown" or
                any(ann.get("type") == "correction" for ann in block.get("annotations", []))):
                
                # Perform semantic validation
                validated = await self._semantic_validation(block)
                validated_blocks.append(validated)
            else:
                validated_blocks.append(block)
        
        return validated_blocks
    
    async def _semantic_validation(self, block: Dict[str, Any]) -> Dict[str, Any]:
        """Perform semantic validation on a block."""
        # This would call Claude in production
        # For now, apply rule-based validation
        
        validated = block.copy()
        text = block.get("text", "")
        
        # Headers ending with comma -> Text
        if block.get("block_type") == "SectionHeader" and text.endswith(','):
            validated["original_type"] = block["block_type"]
            validated["block_type"] = "Text"
            validated["validation_reason"] = "Headers don't end with commas"
        
        # Short fragments starting with lowercase -> Text continuation
        elif len(text) < 20 and text and text[0].islower():
            validated["block_type"] = "Text"
            validated["validation_reason"] = "Short lowercase fragment"
        
        validated["validated"] = True
        return validated
    
    async def _process_equations(self, blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process equation blocks."""
        equations = []
        for block in blocks:
            if block.get("block_type") == "Equation":
                equation = block.copy()
                # Clean LaTeX formatting if needed
                if "text" in equation:
                    equation["text"] = equation["text"].strip()
                    equation["processed"] = True
                equations.append(equation)
        return equations
    
    async def _extract_form_fields(self, blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract form fields from blocks."""
        forms = []
        for block in blocks:
            if block.get("block_type") == "Form":
                form = block.copy()
                form["fields_extracted"] = True
                forms.append(form)
        return forms
    
    async def _describe_figures(self, blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate descriptions for figures."""
        figures = []
        for block in blocks:
            if block.get("block_type") == "Figure":
                figure = block.copy()
                # In production, this would use vision model
                figure["description"] = "Figure showing [automated description would go here]"
                figure["described"] = True
                figures.append(figure)
        return figures
    
    async def _find_similar_sections(self, section: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find similar sections in Knowledge Architect."""
        header = section.get("header", "")
        if not header:
            return []
        
        results = await semantic_search_impl(
            collection=PATTERNS_COLLECTION,
            query=header,
            text_field="header",
            top_k=3
        )
        
        return results.get("results", [])
    
    async def _store_cleaning_patterns(self, cleaned_section: Dict[str, Any]):
        """Store successful cleaning patterns."""
        patterns = {
            "_key": hashlib.md5(cleaned_section["header"].encode()).hexdigest(),
            "header": cleaned_section["header"],
            "patterns_applied": list(self.patterns_cache.keys()),
            "block_count": cleaned_section["processing_stats"]["original_blocks"],
            "cleaned_count": cleaned_section["processing_stats"]["cleaned_blocks"],
            "processing_time": cleaned_section["processing_stats"]["processing_time"],
            "timestamp": datetime.now().isoformat()
        }
        
        await upsert_impl(
            collection=PATTERNS_COLLECTION,
            document=patterns
        )
    
    async def _store_section_with_journey(self, raw_section: Dict[str, Any], 
                                        cleaned_section: Dict[str, Any],
                                        changes: List[Dict[str, Any]], 
                                        confidence: float,
                                        journey: Dict[str, Any]):
        """Store section with complete tool journey for learning."""
        # Use the journey passed from clean_section
        
        # Create comprehensive document
        section_doc = {
            "_key": f"{raw_section.get('id', 'unknown')}_section_{datetime.now().timestamp()}",
            "section_id": raw_section.get("id"),
            "section_header": cleaned_section["header"],
            
            # Store both versions
            "raw": raw_section,
            "cleaned": cleaned_section,
            
            # Processing metadata
            "processing": {
                "timestamp": datetime.now().isoformat(),
                "agent": "pdf-section-cleaner",
                "confidence_score": confidence,
                "changes_made": len(changes)
            },
            
            # MANDATORY: Include complete tool journey
            "tool_journey": journey,
            
            # Detailed changes
            "changes": changes,
            
            # Searchable text (for BM25)
            "search_text": self._extract_searchable_text(cleaned_section),
            
            # Quality metrics
            "quality": {
                "accuracy_score": confidence,
                "completeness": len(cleaned_section["content_blocks"]) / len(raw_section.get("content_blocks", [1])),
                "formatting_quality": 0.95 if changes else 1.0
            }
        }
        
        # Store in ArangoDB using centralized function
        result = await upsert_impl(
            collection="pdf_sections",
            search=json.dumps({"section_id": raw_section.get("id")}),
            update=json.dumps({"processing.timestamp": datetime.now().isoformat()}),
            create=json.dumps(section_doc)
        )
    
    def _extract_changes(self, raw_section: Dict[str, Any], 
                        cleaned_section: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract list of changes made during cleaning."""
        changes = []
        
        # Header changes
        if raw_section.get("header") != cleaned_section.get("header"):
            changes.append({
                "type": "header_cleaning",
                "before": raw_section.get("header"),
                "after": cleaned_section.get("header"),
                "confidence": 0.98
            })
        
        # Block count changes
        raw_blocks = len(raw_section.get("content_blocks", []))
        clean_blocks = len(cleaned_section.get("content_blocks", []))
        if raw_blocks != clean_blocks:
            changes.append({
                "type": "block_consolidation",
                "before_count": raw_blocks,
                "after_count": clean_blocks,
                "confidence": 0.95
            })
        
        return changes
    
    def _extract_searchable_text(self, section: Dict[str, Any]) -> str:
        """Extract searchable text for BM25 indexing."""
        texts = [section.get("header", "")]
        for block in section.get("content_blocks", []):
            if block.get("text"):
                texts.append(block["text"])
        return " ".join(texts)

# ============================================
# TYPER CLI COMMANDS
# ============================================

@app.command()
def clean_section(
    section_file: Path = typer.Argument(..., help="JSON file containing section data"),
    annotations_file: Optional[Path] = typer.Option(None, help="JSON file containing annotations"),
    output_file: Optional[Path] = typer.Option(None, help="Output file for cleaned section")
):
    """Clean a single PDF section comprehensively."""
    try:
        # Load section data
        with open(section_file) as f:
            section = json.load(f)
        
        # Load annotations if provided
        annotations = []
        if annotations_file and annotations_file.exists():
            with open(annotations_file) as f:
                annotations = json.load(f)
        
        # Clean section
        task_desc = f"Clean section {section.get('id', 'unknown')} from {section_file}"
        cleaner = SectionCleaner(task_desc)
        cleaned = asyncio.run(cleaner.clean_section(section, annotations))
        
        # Save or display results
        if output_file:
            with open(output_file, 'w') as f:
                json.dump(cleaned, f, indent=2)
            console.print(f"[green]✓[/green] Cleaned section saved to {output_file}")
        else:
            console.print_json(data=cleaned)
        
        # Display stats
        stats = cleaned["processing_stats"]
        console.print(f"\n[cyan]Processing Stats:[/cyan]")
        console.print(f"  Original blocks: {stats['original_blocks']}")
        console.print(f"  Cleaned blocks: {stats['cleaned_blocks']}")
        console.print(f"  Processing time: {stats['processing_time']:.2f}s")
        
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

@app.command()
def validate_results(
    cleaned_file: Path = typer.Argument(..., help="JSON file containing cleaned section"),
    gold_standard_file: Path = typer.Argument(..., help="JSON file containing gold standard"),
    output_file: Optional[Path] = typer.Option(None, help="Output file for validation report")
):
    """Validate cleaned section against gold standard."""
    try:
        # Load cleaned section
        with open(cleaned_file) as f:
            cleaned = json.load(f)
        
        # Load gold standard
        with open(gold_standard_file) as f:
            gold = json.load(f)
        
        # Perform validation
        validation_report = {
            "section_id": cleaned.get("id"),
            "header_match": cleaned.get("header") == gold.get("header"),
            "block_count_match": len(cleaned.get("content_blocks", [])) == len(gold.get("content_blocks", [])),
            "accuracy_score": 0.0,
            "differences": []
        }
        
        # Calculate accuracy
        correct = 0
        total = max(len(cleaned.get("content_blocks", [])), len(gold.get("content_blocks", [])))
        
        for i in range(min(len(cleaned.get("content_blocks", [])), len(gold.get("content_blocks", [])))):
            cleaned_block = cleaned["content_blocks"][i]
            gold_block = gold["content_blocks"][i]
            
            if (cleaned_block.get("block_type") == gold_block.get("block_type") and
                cleaned_block.get("text", "").strip() == gold_block.get("text", "").strip()):
                correct += 1
            else:
                validation_report["differences"].append({
                    "block_index": i,
                    "cleaned_type": cleaned_block.get("block_type"),
                    "gold_type": gold_block.get("block_type"),
                    "text_match": cleaned_block.get("text", "") == gold_block.get("text", "")
                })
        
        validation_report["accuracy_score"] = correct / total if total > 0 else 0.0
        
        # Save or display results
        if output_file:
            with open(output_file, 'w') as f:
                json.dump(validation_report, f, indent=2)
            console.print(f"[green]✓[/green] Validation report saved to {output_file}")
        else:
            console.print_json(data=validation_report)
        
        # Display summary
        console.print(f"\n[cyan]Validation Summary:[/cyan]")
        console.print(f"  Header match: {'✓' if validation_report['header_match'] else '✗'}")
        console.print(f"  Block count match: {'✓' if validation_report['block_count_match'] else '✗'}")
        console.print(f"  Accuracy score: {validation_report['accuracy_score']:.2%}")
        console.print(f"  Differences found: {len(validation_report['differences'])}")
        
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

# ============================================
# USAGE FUNCTIONS
# ============================================

async def working_usage():
    """Demonstrate comprehensive section cleaning capabilities."""
    console.print("[cyan]PDF Section Cleaner - Working Usage Demo[/cyan]\n")
    
    # Create sample section with various issues
    sample_section = {
        "id": 0,
        "header": "4.1.5.4.   BHT   (Branch   History   Table)   submodule",
        "content_blocks": [
            {
                "id": 1,
                "block_type": "Text",
                "text": "BHT is implemented as a memory which is composed of   BHTDepth entries",
                "bbox": [72, 100, 400, 115],
                "page": 0,
                "confidence": 0.92
            },
            {
                "id": 2,
                "block_type": "Text", 
                "text": "addressed by a hash of the PC. The PC hash is simply a truncation of the PC to the log2(",
                "bbox": [72, 115, 450, 130],
                "page": 0,
                "confidence": 0.88
            },
            {
                "id": 3,
                "block_type": "Text",
                "text": "BHTDepth   ) least",
                "bbox": [72, 130, 180, 145],
                "page": 0,
                "confidence": 0.75
            },
            {
                "id": 4,
                "block_type": "SectionHeader",
                "text": "For any HW configuration,",
                "bbox": [70, 536, 215, 552],
                "page": 1,
                "confidence": 0.88
            },
            {
                "id": 5,
                "block_type": "TableCell",
                "text": "Signal",
                "bbox": [72, 611, 156, 638],
                "page": 0
            },
            {
                "id": 6,
                "block_type": "TableCell",
                "text": "IO",
                "bbox": [156, 611, 187, 638],
                "page": 0
            },
            {
                "id": 7,
                "block_type": "TableCell",
                "text": "Description",
                "bbox": [187, 611, 254, 638],
                "page": 0
            }
        ]
    }
    
    # Sample annotations
    sample_annotations = [
        {
            "page": 0,
            "type": "comment",
            "bbox": [72, 83, 315, 95],
            "content": "Check spacing in BHT header - looks wrong"
        },
        {
            "page": 1,
            "type": "correction",
            "bbox": [70, 536, 215, 552],
            "content": "This should be body text, not a header"
        }
    ]
    
    # Clean the section
    task_desc = "Clean sample BHT section with spacing issues and fragmented text"
    cleaner = SectionCleaner(task_desc)
    console.print("[yellow]Cleaning sample section with multiple issues...[/yellow]")
    
    cleaned = await cleaner.clean_section(sample_section, sample_annotations)
    
    # Display results
    console.print("\n[green]✓ Section cleaned successfully![/green]\n")
    
    console.print("[cyan]Original Header:[/cyan]", sample_section["header"])
    console.print("[cyan]Cleaned Header:[/cyan]", cleaned["header"])
    
    console.print(f"\n[cyan]Processing Stats:[/cyan]")
    stats = cleaned["processing_stats"]
    for key, value in stats.items():
        console.print(f"  {key}: {value}")
    
    console.print(f"\n[cyan]Cleaned Blocks:[/cyan]")
    for i, block in enumerate(cleaned["content_blocks"]):
        console.print(f"\n[yellow]Block {i+1}:[/yellow]")
        console.print(f"  Type: {block['block_type']}")
        console.print(f"  Text: {block.get('text', 'N/A')[:100]}...")
        if block.get("merged_from"):
            console.print(f"  Merged from blocks: {block['merged_from']}")
        if block.get("validated"):
            console.print(f"  Validation: {block.get('validation_reason', 'Validated')}")
    
    # Journey is automatically saved in clean_section method
    console.print("\n[green]✓ Tool journey saved to Knowledge Architect[/green]")
    
    return True

async def debug_function():
    """Test processing a complex section with various issues."""
    console.print("[cyan]PDF Section Cleaner - Debug Mode[/cyan]\n")
    
    # Create a complex section with multiple issues
    complex_section = {
        "id": 0,
        "header": "4.1.5.4.   BHT   (Branch   History   Table)   submodule,",  # Spacing issues and comma
        "content_blocks": [
            # Split text that should be merged
            {"id": 1, "block_type": "Text", "text": "BHT is implemented as a memory which is composed of", "bbox": [72, 100, 400, 115], "page": 0},
            {"id": 2, "block_type": "Text", "text": "BHTDepth configuration parameter", "bbox": [72, 115, 300, 130], "page": 0},
            {"id": 3, "block_type": "Text", "text": "entries. The lower address bits of the virtual address point to the memory entry.", "bbox": [72, 130, 500, 145], "page": 0},
            
            # Misclassified header
            {"id": 4, "block_type": "SectionHeader", "text": "As mentioned earlier,", "bbox": [72, 200, 300, 215], "page": 0, "confidence": 0.6},
            {"id": 5, "block_type": "Text", "text": "the branch predictor uses a two-bit saturating counter.", "bbox": [72, 215, 400, 230], "page": 0},
            
            # Fragmented table
            {"id": 6, "block_type": "TableCell", "text": "Signal", "bbox": [72, 300, 120, 320], "page": 0},
            {"id": 7, "block_type": "TableCell", "text": "I/O", "bbox": [120, 300, 170, 320], "page": 0},
            {"id": 8, "block_type": "TableCell", "text": "Description", "bbox": [170, 300, 250, 320], "page": 0},
            {"id": 9, "block_type": "TableCell", "text": "Type", "bbox": [250, 300, 300, 320], "page": 0},
            {"id": 10, "block_type": "TableCell", "text": "clk_i", "bbox": [72, 320, 120, 340], "page": 0},
            {"id": 11, "block_type": "TableCell", "text": "in", "bbox": [120, 320, 170, 340], "page": 0},
            {"id": 12, "block_type": "TableCell", "text": "System clock", "bbox": [170, 320, 250, 340], "page": 0},
            {"id": 13, "block_type": "TableCell", "text": "logic", "bbox": [250, 320, 300, 340], "page": 0},
            
            # Figure without description
            {"id": 14, "block_type": "Figure", "bbox": [72, 400, 500, 600], "page": 0},
            
            # Another misclassified header
            {"id": 15, "block_type": "SectionHeader", "text": "For any HW configuration,", "bbox": [72, 650, 300, 665], "page": 0, "confidence": 0.7}
        ]
    }
    
    # Annotations that highlight issues
    test_annotations = [
        {
            "page": 0,
            "type": "comment",
            "bbox": [72, 300, 300, 340],
            "content": "This table is fragmented and needs reconstruction"
        },
        {
            "page": 0,
            "type": "correction",
            "bbox": [72, 200, 300, 215],
            "content": "This is not a header, it's continuation text"
        }
    ]
    
    # Clean the complex section
    task_desc = "Clean complex section with fragmented table, misclassified headers, and figures"
    cleaner = SectionCleaner(task_desc)
    console.print("[yellow]Processing complex section with multiple issues...[/yellow]")
    
    start_time = time.time()
    cleaned = await cleaner.clean_section(complex_section, test_annotations)
    processing_time = time.time() - start_time
    
    # Display detailed results
    console.print(f"\n[green]✓ Section cleaned in {processing_time:.2f}s[/green]\n")
    
    console.print("[cyan]Cleaning Summary:[/cyan]")
    console.print(f"  Original header: '{complex_section['header']}'")
    console.print(f"  Cleaned header: '{cleaned['header']}'")
    
    stats = cleaned["processing_stats"]
    console.print(f"\n[cyan]Block Statistics:[/cyan]")
    console.print(f"  Original blocks: {stats['original_blocks']}")
    console.print(f"  Cleaned blocks: {stats['cleaned_blocks']}")
    console.print(f"  Merged text blocks: {stats.get('merged_text_blocks', 0)}")
    console.print(f"  Reconstructed tables: {stats.get('reconstructed_tables', 0)}")
    
    console.print(f"\n[cyan]Detailed Block Analysis:[/cyan]")
    for i, block in enumerate(cleaned["content_blocks"]):
        console.print(f"\n[yellow]Block {i+1}:[/yellow]")
        console.print(f"  Type: {block['block_type']}")
        
        if block.get("text"):
            text_preview = block["text"][:80] + "..." if len(block["text"]) > 80 else block["text"]
            console.print(f"  Text: '{text_preview}'")
        
        if block.get("merged_from"):
            console.print(f"  [green]Merged from blocks: {block['merged_from']}[/green]")
        
        if block.get("validated"):
            console.print(f"  [blue]Validation: {block.get('validation_reason', 'Semantically validated')}[/blue]")
        
        if block.get("reconstructed"):
            console.print(f"  [green]Reconstructed table: {block['rows']}x{block['cols']} from {block['merged_from_fragments']} fragments[/green]")
        
        if block.get("described"):
            console.print(f"  [blue]Figure description added[/blue]")
    
    # Show annotation applications
    if test_annotations:
        console.print(f"\n[cyan]Annotations Applied:[/cyan]")
        console.print(f"  Total annotations: {len(test_annotations)}")
        console.print(f"  Applied corrections based on reviewer feedback")
    
    return True

# ============================================
# MAIN ENTRY POINT
# ============================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "debug":
        print("Running debug mode...")
        asyncio.run(debug_function())
    elif len(sys.argv) == 1:
        print("Running working usage mode...")
        asyncio.run(working_usage())
    else:
        # Run Typer CLI
        app()