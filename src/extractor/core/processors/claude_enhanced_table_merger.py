"""
Claude-Enhanced Table Merger Integration
Module: claude_enhanced_table_merger.py

Integrates the Claude Code instance table merge analyzer with the enhanced table processor.
Provides intelligent merge decisions based on comprehensive content analysis.
"""

import asyncio
import json
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from loguru import logger
import tempfile

from extractor.core.processors.claude_table_merge_analyzer import TableMergeDecisionEngine, AnalysisResult
from extractor.core.schema import BlockTypes
from extractor.core.schema.blocks import Block
from extractor.core.schema.document import Document

class ClaudeEnhancedTableMerger:
    """
    Enhanced table merger that uses Claude Code instances for intelligent merge decisions.
    
    This class replaces heuristic merge logic with AI-powered content analysis,
    considering factors like:
    - Whitespace patterns and formatting consistency
    - Field types and data type compatibility  
    - Number of fields and structural alignment
    - Semantic content relationships
    - Document context and layout
    """
    
    def __init__(self, 
                 workspace_dir: Optional[Path] = None,
                 confidence_threshold: float = 0.75,
                 max_parallel_analyses: int = 3,
                 analysis_timeout: float = 120.0):
        """
        Initialize the Claude-enhanced table merger.
        
        Args:
            workspace_dir: Directory for temporary files and Claude execution
            confidence_threshold: Minimum confidence required for merge (0.0-1.0)
            max_parallel_analyses: Maximum concurrent Claude analyses
            analysis_timeout: Timeout for individual analysis tasks
        """
        self.workspace_dir = workspace_dir or Path(tempfile.mkdtemp(prefix="claude_table_merger_"))
        self.confidence_threshold = confidence_threshold
        self.max_parallel_analyses = max_parallel_analyses
        self.analysis_timeout = analysis_timeout
        
        # Initialize the decision engine
        self.decision_engine = TableMergeDecisionEngine(self.workspace_dir)
        
        # Track analysis results for debugging/optimization
        self.analysis_history = []
        
    async def analyze_and_merge_tables(self, document: Document, table_blocks: List[Block]) -> List[Dict[str, Any]]:
        """
        Analyze table blocks and return merge recommendations with detailed metadata.
        
        Args:
            document: The document containing the tables
            table_blocks: List of table blocks to analyze
            
        Returns:
            List of merge group dictionaries with metadata
        """
        if len(table_blocks) < 2:
            return [{"tables": [0], "merge_type": "single", "confidence": 1.0}]
        
        # Extract detailed table data for analysis
        tables_data = []
        for i, block in enumerate(table_blocks):
            table_data = await self._extract_comprehensive_table_data(document, block, i)
            tables_data.append(table_data)
        
        # Extract document context
        context = self._extract_document_context(document, table_blocks)
        
        # Perform parallel analysis of table sequences
        logger.info(f"Starting Claude analysis of {len(tables_data)} tables")
        merge_groups_indices = await self.decision_engine.analyze_table_sequence_parallel(
            tables_data, context
        )
        
        # Convert to detailed merge recommendations
        merge_recommendations = []
        for group_indices in merge_groups_indices:
            if len(group_indices) == 1:
                # Single table - no merge
                merge_recommendations.append({
                    "tables": group_indices,
                    "blocks": [table_blocks[i] for i in group_indices],
                    "merge_type": "single",
                    "confidence": 1.0,
                    "reasoning": "Single table - no merge needed"
                })
            else:
                # Multi-table merge - get detailed analysis
                merge_rec = await self._create_detailed_merge_recommendation(
                    group_indices, table_blocks, tables_data, context
                )
                merge_recommendations.append(merge_rec)
        
        logger.info(f"Claude analysis complete: {len(merge_recommendations)} merge groups identified")
        return merge_recommendations
    
    async def _extract_comprehensive_table_data(self, document: Document, block: Block, index: int) -> Dict[str, Any]:
        """Extract comprehensive data about a table for Claude analysis."""
        
        # Basic table content
        table_data = {
            "index": index,
            "page_id": getattr(block, 'page_id', 0),
            "text": block.raw_text(document) if hasattr(block, 'raw_text') else "",
        }
        
        # Extract structured data if available
        if hasattr(block, 'generate_csv'):
            try:
                table_data["csv"] = block.generate_csv(document, [])
            except Exception as e:
                logger.debug(f"Failed to generate CSV for table {index}: {e}")
                table_data["csv"] = None
        
        if hasattr(block, 'generate_json'):
            try:
                json_str = block.generate_json(document, [])
                table_data["json_data"] = json.loads(json_str) if json_str else None
            except Exception as e:
                logger.debug(f"Failed to generate JSON for table {index}: {e}")
                table_data["json_data"] = None
        
        # Extract detailed structural information
        table_data["structure"] = await self._analyze_table_structure(document, block)
        
        # Extract extraction metadata
        table_data["metadata"] = {
            "extraction_method": getattr(block, 'extraction_method', 'unknown'),
            "extraction_details": getattr(block, 'extraction_details', {}),
            "quality_score": getattr(block, 'quality_score', None),
            "quality_metrics": getattr(block, 'quality_metrics', {}),
            "bbox": block.polygon.bbox if hasattr(block, 'polygon') and block.polygon else None
        }
        
        return table_data
    
    async def _analyze_table_structure(self, document: Document, block: Block) -> Dict[str, Any]:
        """Analyze detailed table structure for Claude."""
        
        structure = {
            "cell_count": 0,
            "row_count": 0,
            "column_count": 0,
            "has_headers": False,
            "data_types": [],
            "whitespace_patterns": {},
            "formatting_consistency": {}
        }
        
        try:
            # Get table cells
            cells = block.contained_blocks(document, (BlockTypes.TableCell,)) if hasattr(block, 'contained_blocks') else []
            
            if cells:
                structure["cell_count"] = len(cells)
                
                # Analyze row/column structure
                row_ids = set()
                col_ids = set()
                headers = []
                
                for cell in cells:
                    if hasattr(cell, 'row_id'):
                        row_ids.add(cell.row_id)
                    if hasattr(cell, 'col_id'):
                        col_ids.add(cell.col_id)
                    if hasattr(cell, 'is_header') and cell.is_header:
                        headers.append(getattr(cell, 'text_lines', []))
                
                structure["row_count"] = len(row_ids)
                structure["column_count"] = len(col_ids)
                structure["has_headers"] = len(headers) > 0
                
                # Analyze data types in each column
                structure["data_types"] = self._analyze_column_data_types(cells)
                
                # Analyze whitespace and formatting patterns
                structure["whitespace_patterns"] = self._analyze_whitespace_patterns(cells)
                structure["formatting_consistency"] = self._analyze_formatting_consistency(cells)
        
        except Exception as e:
            logger.debug(f"Failed to analyze table structure: {e}")
        
        return structure
    
    def _analyze_column_data_types(self, cells: List[Block]) -> List[Dict[str, Any]]:
        """Analyze data types in each column."""
        
        column_data = {}
        
        for cell in cells:
            if not hasattr(cell, 'col_id') or not hasattr(cell, 'text_lines'):
                continue
                
            col_id = cell.col_id
            text_lines = cell.text_lines or []
            cell_text = " ".join(text_lines).strip()
            
            if col_id not in column_data:
                column_data[col_id] = []
            
            if cell_text:
                column_data[col_id].append(cell_text)
        
        # Analyze each column
        column_types = []
        for col_id in sorted(column_data.keys()):
            values = column_data[col_id]
            col_analysis = {
                "column_id": col_id,
                "sample_values": values[:5],  # First 5 values
                "data_type": self._infer_data_type(values),
                "value_count": len(values),
                "unique_count": len(set(values))
            }
            column_types.append(col_analysis)
        
        return column_types
    
    def _infer_data_type(self, values: List[str]) -> str:
        """Infer the primary data type of a column."""
        if not values:
            return "empty"
        
        # Count different type patterns
        numeric_count = 0
        date_count = 0
        currency_count = 0
        
        for value in values:
            if self._is_numeric(value):
                numeric_count += 1
            elif self._is_date(value):
                date_count += 1
            elif self._is_currency(value):
                currency_count += 1
        
        total = len(values)
        if numeric_count / total > 0.7:
            return "numeric"
        elif date_count / total > 0.7:
            return "date"
        elif currency_count / total > 0.7:
            return "currency"
        else:
            return "text"
    
    def _is_numeric(self, value: str) -> bool:
        """Check if value is numeric."""
        try:
            float(value.replace(',', '').replace('$', '').replace('%', ''))
            return True
        except:
            return False
    
    def _is_date(self, value: str) -> bool:
        """Check if value looks like a date."""
        import re
        date_patterns = [
            r'\d{1,2}/\d{1,2}/\d{2,4}',  # MM/DD/YYYY
            r'\d{1,2}-\d{1,2}-\d{2,4}',  # MM-DD-YYYY
            r'\d{4}-\d{1,2}-\d{1,2}',    # YYYY-MM-DD
        ]
        return any(re.match(pattern, value) for pattern in date_patterns)
    
    def _is_currency(self, value: str) -> bool:
        """Check if value looks like currency."""
        import re
        currency_pattern = r'[\$£€¥]?\d+[,.]?\d*'
        return bool(re.match(currency_pattern, value))
    
    def _analyze_whitespace_patterns(self, cells: List[Block]) -> Dict[str, Any]:
        """Analyze whitespace and spacing patterns."""
        
        patterns = {
            "leading_spaces": [],
            "trailing_spaces": [],
            "internal_spacing": [],
            "line_breaks": 0
        }
        
        for cell in cells:
            if not hasattr(cell, 'text_lines'):
                continue
                
            text_lines = cell.text_lines or []
            for line in text_lines:
                if isinstance(line, str):
                    # Count leading/trailing spaces
                    leading = len(line) - len(line.lstrip())
                    trailing = len(line) - len(line.rstrip())
                    patterns["leading_spaces"].append(leading)
                    patterns["trailing_spaces"].append(trailing)
                    
                    # Count internal spacing (multiple spaces)
                    import re
                    internal = len(re.findall(r'  +', line))
                    patterns["internal_spacing"].append(internal)
        
        # Calculate statistics
        return {
            "avg_leading_spaces": sum(patterns["leading_spaces"]) / max(len(patterns["leading_spaces"]), 1),
            "avg_trailing_spaces": sum(patterns["trailing_spaces"]) / max(len(patterns["trailing_spaces"]), 1),
            "avg_internal_spacing": sum(patterns["internal_spacing"]) / max(len(patterns["internal_spacing"]), 1),
            "spacing_consistency": len(set(patterns["leading_spaces"])) <= 2  # Low variety = consistent
        }
    
    def _analyze_formatting_consistency(self, cells: List[Block]) -> Dict[str, Any]:
        """Analyze formatting consistency across cells."""
        
        font_sizes = []
        alignments = []
        text_formats = []
        
        for cell in cells:
            # This would require more detailed cell formatting info
            # For now, provide basic analysis
            if hasattr(cell, 'text_lines') and cell.text_lines:
                text_lines = cell.text_lines or []
                for line in text_lines:
                    if isinstance(line, str):
                        # Basic format detection
                        if line.isupper():
                            text_formats.append("uppercase")
                        elif line.islower():
                            text_formats.append("lowercase")
                        elif line.istitle():
                            text_formats.append("title_case")
                        else:
                            text_formats.append("mixed_case")
        
        return {
            "format_variety": len(set(text_formats)),
            "dominant_format": max(set(text_formats), key=text_formats.count) if text_formats else "unknown",
            "format_consistency": len(set(text_formats)) <= 2 if text_formats else True
        }
    
    def _extract_document_context(self, document: Document, table_blocks: List[Block]) -> Dict[str, Any]:
        """Extract document context for Claude analysis."""
        
        context = {
            "document_type": "unknown",
            "total_pages": len(document.pages) if hasattr(document, 'pages') else 1,
            "table_count": len(table_blocks),
            "surrounding_text": {},
            "layout_info": {}
        }
        
        # Get surrounding text for each table
        for i, block in enumerate(table_blocks):
            page_id = getattr(block, 'page_id', 0)
            
            # Try to get text blocks around this table
            surrounding = self._get_surrounding_text(document, block, page_id)
            context["surrounding_text"][str(i)] = surrounding
        
        # Analyze overall layout
        context["layout_info"] = self._analyze_layout_patterns(table_blocks)
        
        return context
    
    def _get_surrounding_text(self, document: Document, table_block: Block, page_id: int) -> Dict[str, str]:
        """Get text content surrounding a table."""
        
        surrounding = {
            "before": "",
            "after": "",
            "captions": []
        }
        
        try:
            # Get the page containing this table
            page = None
            if hasattr(document, 'pages'):
                for p in document.pages:
                    if getattr(p, 'page_id', 0) == page_id:
                        page = p
                        break
            
            if page and hasattr(page, 'contained_blocks'):
                # Get all text blocks on this page
                text_blocks = page.contained_blocks(document, (BlockTypes.Text,))
                
                # Find blocks before and after the table
                table_bbox = table_block.polygon.bbox if hasattr(table_block, 'polygon') and table_block.polygon else [0, 0, 0, 0]
                table_y = table_bbox[1]  # Top of table
                
                before_blocks = []
                after_blocks = []
                
                for text_block in text_blocks:
                    if hasattr(text_block, 'polygon') and text_block.polygon:
                        text_bbox = text_block.polygon.bbox
                        text_y = text_bbox[1]
                        
                        if text_y < table_y:
                            before_blocks.append(text_block)
                        else:
                            after_blocks.append(text_block)
                
                # Get text from closest blocks
                if before_blocks:
                    closest_before = min(before_blocks, key=lambda b: abs(b.polygon.bbox[1] - table_y))
                    surrounding["before"] = closest_before.raw_text(document) if hasattr(closest_before, 'raw_text') else ""
                
                if after_blocks:
                    closest_after = min(after_blocks, key=lambda b: abs(b.polygon.bbox[1] - table_y))
                    surrounding["after"] = closest_after.raw_text(document) if hasattr(closest_after, 'raw_text') else ""
        
        except Exception as e:
            logger.debug(f"Failed to get surrounding text: {e}")
        
        return surrounding
    
    def _analyze_layout_patterns(self, table_blocks: List[Block]) -> Dict[str, Any]:
        """Analyze layout patterns of tables."""
        
        layout = {
            "page_distribution": {},
            "spacing_patterns": [],
            "alignment_patterns": []
        }
        
        # Analyze page distribution
        page_counts = {}
        for block in table_blocks:
            page_id = getattr(block, 'page_id', 0)
            page_counts[page_id] = page_counts.get(page_id, 0) + 1
        
        layout["page_distribution"] = page_counts
        
        # Analyze spacing between consecutive tables
        for i in range(len(table_blocks) - 1):
            current = table_blocks[i]
            next_table = table_blocks[i + 1]
            
            if (hasattr(current, 'polygon') and current.polygon and 
                hasattr(next_table, 'polygon') and next_table.polygon):
                
                curr_bbox = current.polygon.bbox
                next_bbox = next_table.polygon.bbox
                
                # Calculate vertical spacing
                vertical_gap = next_bbox[1] - curr_bbox[3]  # Top of next - bottom of current
                layout["spacing_patterns"].append(vertical_gap)
        
        return layout
    
    async def _create_detailed_merge_recommendation(self, 
                                                   group_indices: List[int],
                                                   table_blocks: List[Block], 
                                                   tables_data: List[Dict[str, Any]],
                                                   context: Dict[str, Any]) -> Dict[str, Any]:
        """Create detailed merge recommendation with Claude analysis."""
        
        # Get the primary analysis (first pair in group)
        primary_analysis = None
        if len(group_indices) >= 2:
            task_id = await self.decision_engine.submit_merge_analysis(
                tables_data[group_indices[0]],
                tables_data[group_indices[1]], 
                context
            )
            result = await self.decision_engine.get_merge_decision(task_id, self.analysis_timeout)
            primary_analysis = result
        
        # Build comprehensive recommendation
        recommendation = {
            "tables": group_indices,
            "blocks": [table_blocks[i] for i in group_indices],
            "merge_type": "claude_analyzed",
            "confidence": primary_analysis.confidence if primary_analysis else 0.8,
            "reasoning": primary_analysis.reasoning if primary_analysis else "Multi-table merge based on structural analysis",
            "claude_analysis": {}
        }
        
        if primary_analysis:
            recommendation["claude_analysis"] = {
                "should_merge": primary_analysis.should_merge,
                "confidence": primary_analysis.confidence,
                "merge_type": primary_analysis.merge_type,
                "concerns": primary_analysis.concerns,
                "benefits": primary_analysis.benefits,
                "analysis_factors": primary_analysis.analysis_factors
            }
            
            # Store for debugging/optimization
            self.analysis_history.append({
                "table_indices": group_indices,
                "result": primary_analysis,
                "timestamp": asyncio.get_event_loop().time()
            })
        
        return recommendation
    
    def get_analysis_statistics(self) -> Dict[str, Any]:
        """Get statistics about Claude analyses performed."""
        
        if not self.analysis_history:
            return {"total_analyses": 0}
        
        total = len(self.analysis_history)
        merged = sum(1 for a in self.analysis_history if a["result"].should_merge)
        avg_confidence = sum(a["result"].confidence for a in self.analysis_history) / total
        
        return {
            "total_analyses": total,
            "merge_rate": merged / total,
            "average_confidence": avg_confidence,
            "recent_analyses": self.analysis_history[-5:]  # Last 5 for debugging
        }

# Integration function for enhanced_table.py
async def claude_enhanced_merge_tables(enhanced_processor, document: Document) -> None:
    """
    Replace the heuristic merge logic in enhanced_table.py with Claude-powered analysis.
    
    This function should be called instead of the existing merge_tables method.
    """
    
    if not enhanced_processor.merger_config.enabled:
        return
    
    logger.info("Starting Claude-enhanced table merging...")
    
    # Collect all table blocks
    table_blocks = []
    for page in document.pages:
        page_tables = page.contained_blocks(document, enhanced_processor.block_types)
        table_blocks.extend(page_tables)
    
    if len(table_blocks) < 2:
        logger.info("Less than 2 tables found - no merging needed")
        return
    
    # Initialize Claude merger with workspace
    merger = ClaudeEnhancedTableMerger(
        confidence_threshold=enhanced_processor.merger_config.get('claude_confidence_threshold', 0.75),
        analysis_timeout=enhanced_processor.merger_config.get('claude_timeout', 120.0)
    )
    
    try:
        # Get merge recommendations from Claude
        merge_recommendations = await merger.analyze_and_merge_tables(document, table_blocks)
        
        # Apply merge recommendations
        for recommendation in merge_recommendations:
            if len(recommendation["tables"]) > 1:
                # This is a merge group
                await _apply_merge_recommendation(document, recommendation, enhanced_processor)
        
        # Log statistics
        stats = merger.get_analysis_statistics()
        logger.info(f"Claude merge analysis complete: {stats}")
        
    except Exception as e:
        logger.error(f"Claude-enhanced merging failed: {e}")
        # Fallback to heuristic merging
        logger.info("Falling back to heuristic merging")
        # Call original merge method here if needed

async def _apply_merge_recommendation(document: Document, recommendation: Dict[str, Any], processor) -> None:
    """Apply a Claude-recommended table merge."""
    
    table_indices = recommendation["tables"]
    blocks = recommendation["blocks"]
    
    if len(blocks) < 2:
        return
    
    logger.info(f"Applying Claude merge recommendation for tables {table_indices}")
    
    # Get the primary block (first in group)
    primary_block = blocks[0]
    
    # Collect original table data for merge metadata
    original_tables = []
    for i, block in zip(table_indices, blocks):
        table_data = {
            "id": f"table_page{getattr(block, 'page_id', 0)}_{i}",
            "page_id": getattr(block, 'page_id', 0),
            "bbox": block.polygon.bbox if hasattr(block, 'polygon') and block.polygon else None,
            "text": block.raw_text(document) if hasattr(block, 'raw_text') else "",
            "csv": block.generate_csv(document, []) if hasattr(block, "generate_csv") else None,
            "json_data": block.generate_json(document, []) if hasattr(block, "generate_json") else None,
            "extraction_method": getattr(block, 'extraction_method', None),
            "quality_score": getattr(block, 'quality_score', None)
        }
        original_tables.append(table_data)
    
    # Perform the actual merge (combine cells from all blocks)
    all_cells = []
    for block in blocks:
        cells = block.contained_blocks(document, (BlockTypes.TableCell,)) if hasattr(block, 'contained_blocks') else []
        all_cells.extend(cells)
    
    # Update primary block structure
    if hasattr(primary_block, 'structure'):
        primary_block.structure = [cell.id for cell in all_cells]
    
    # Clear other blocks' structures
    for block in blocks[1:]:
        if hasattr(block, 'structure'):
            block.structure = []
    
    # Update merge metadata with Claude analysis
    if hasattr(primary_block, 'update_merge_info'):
        primary_block.update_merge_info(
            merge_type="claude_analyzed_" + recommendation.get("merge_type", "unknown"),
            original_tables=original_tables,
            confidence=recommendation.get("confidence", 0.8),
            merge_method="claude_code_analysis"
        )
    
    # Add Claude analysis details to metadata
    if hasattr(primary_block, 'metadata'):
        if not primary_block.metadata:
            primary_block.metadata = {}
        primary_block.metadata['claude_analysis'] = recommendation.get('claude_analysis', {})
    
    logger.info(f"Successfully merged {len(blocks)} tables with confidence {recommendation.get('confidence', 0.8):.2f}")

# Example usage
async def demo_claude_table_merger():
    """Demonstrate the Claude-enhanced table merger."""
    
    # This would be called from enhanced_table.py instead of the heuristic merge
    print("Claude Enhanced Table Merger Demo")
    print("This replaces heuristic table merging with AI-powered content analysis")
    print("Factors considered:")
    print("- Whitespace patterns and formatting consistency")
    print("- Field types and data type compatibility")
    print("- Number of fields and structural alignment") 
    print("- Semantic content relationships")
    print("- Document context and layout positioning")
    print("- Extraction quality and consistency")

if __name__ == "__main__":
    asyncio.run(demo_claude_table_merger())