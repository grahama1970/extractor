"""
Table Merge Analyzer - Post-processing analysis for table merging decisions.
Module: table_merge_analyzer.py

This module analyzes tables AFTER document processing is complete to determine
if adjacent tables should be merged. It uses Claude or other LLMs to make
intelligent decisions while maintaining data integrity.
"""

import json
from typing import Dict, List, Optional, Tuple, Any, Union
from pydantic import BaseModel, Field
from loguru import logger

from extractor.core.schema import BlockTypes
from extractor.core.schema.blocks import Block
from extractor.core.schema.document import Document


class TableTitle(BaseModel):
    """Represents a table title, either explicit or inferred."""
    found: bool = Field(description="Whether a title was found or inferred")
    text: Optional[str] = Field(default=None, description="The title text, prefixed with 'Inferred:' if inferred")
    source: str = Field(description="Source of the title (e.g., 'caption_above', 'inferred_from_paragraph')")
    is_inferred: bool = Field(description="Whether the title was inferred from context")
    inference_context: Optional[str] = Field(default=None, description="The context used for inference if applicable")


class TableAnalysis(BaseModel):
    """Analysis result for table merge decision."""
    table1_id: str
    table2_id: str
    should_merge: bool
    confidence: float = Field(ge=0.0, le=1.0)
    merge_type: str = Field(description="Type of merge: 'vertical_append', 'horizontal_join', etc.")
    table_title: TableTitle
    column_analysis: Dict[str, Any]
    content_analysis: Dict[str, Any]
    reasoning: str
    warnings: List[str] = Field(default_factory=list)
    merge_instructions: Dict[str, Any]


class TableMergeAnalyzer:
    """
    Analyzes tables for merge compatibility after document processing.
    This is a READ-ONLY analyzer that does not modify any data.
    """
    
    def __init__(self, llm_service=None):
        """
        Initialize the analyzer.
        
        Args:
            llm_service: Optional LLM service for analysis. If None, uses heuristics.
        """
        self.llm_service = llm_service
    
    def analyze_document_tables(self, document: Document) -> List[TableAnalysis]:
        """
        Analyze all tables in a document for potential merging.
        
        Args:
            document: Complete processed document
            
        Returns:
            List of merge analyses for candidate table pairs
        """
        merge_candidates = []
        
        # Collect all tables with their page context
        tables_by_page = self._collect_tables_by_page(document)
        
        # Analyze within-page adjacent tables
        for page_num, tables in tables_by_page.items():
            if len(tables) < 2:
                continue
                
            for i in range(len(tables) - 1):
                analysis = self._analyze_table_pair(
                    document, tables[i], tables[i + 1], 
                    context_type="same_page"
                )
                if analysis and analysis.confidence > 0.7:
                    merge_candidates.append(analysis)
        
        # Analyze cross-page tables (last table of page N with first of page N+1)
        page_nums = sorted(tables_by_page.keys())
        for i in range(len(page_nums) - 1):
            curr_page = page_nums[i]
            next_page = page_nums[i + 1]
            
            if next_page - curr_page == 1:  # Consecutive pages
                curr_tables = tables_by_page[curr_page]
                next_tables = tables_by_page[next_page]
                
                if curr_tables and next_tables:
                    analysis = self._analyze_table_pair(
                        document, curr_tables[-1], next_tables[0],
                        context_type="cross_page"
                    )
                    if analysis and analysis.confidence > 0.8:  # Higher threshold for cross-page
                        merge_candidates.append(analysis)
        
        return merge_candidates
    
    def _collect_tables_by_page(self, document: Document) -> Dict[int, List[Block]]:
        """Collect all tables organized by page number."""
        tables_by_page = {}
        
        for page in document.pages:
            page_tables = []
            for block in page.children:
                if block.block_type == BlockTypes.Table:
                    page_tables.append(block)
                # Also check within groups (like TableGroup)
                elif hasattr(block, 'children'):
                    for child in block.children:
                        if child.block_type == BlockTypes.Table:
                            page_tables.append(child)
            
            if page_tables:
                tables_by_page[page.page_id] = page_tables
        
        return tables_by_page
    
    def _analyze_table_pair(self, document: Document, table1: Block, table2: Block, 
                           context_type: str = "same_page") -> Optional[TableAnalysis]:
        """
        Analyze a pair of tables for merge compatibility.
        
        Args:
            document: The complete document
            table1: First table block
            table2: Second table block
            context_type: "same_page" or "cross_page"
            
        Returns:
            TableAnalysis if tables are merge candidates, None otherwise
        """
        # Extract table data (READ ONLY)
        t1_data = self._extract_table_data(table1)
        t2_data = self._extract_table_data(table2)
        
        # Get surrounding context
        context = self._get_table_context(document, table1, table2)
        
        # Find or infer table title
        table_title = self._determine_table_title(document, table1, table2, context)
        
        if self.llm_service:
            # Use LLM for intelligent analysis
            analysis = self._llm_analyze(t1_data, t2_data, context, table_title)
        else:
            # Use heuristic analysis
            analysis = self._heuristic_analyze(
                table1, table2, t1_data, t2_data, context, table_title
            )
        
        return analysis
    
    def _determine_table_title(self, document: Document, table1: Block, 
                              table2: Block, context: Dict[str, Any]) -> TableTitle:
        """
        Determine table title from explicit captions or infer from context.
        """
        # First, look for explicit titles
        explicit_title = self._find_explicit_title(document, table1, table2, context)
        if explicit_title:
            return explicit_title
        
        # If no explicit title, try to infer
        inferred_title = self._infer_title_from_context(context)
        if inferred_title:
            return inferred_title
        
        # No title found
        return TableTitle(
            found=False,
            text=None,
            source="none",
            is_inferred=False
        )
    
    def _find_explicit_title(self, document: Document, table1: Block, 
                            table2: Block, context: Dict[str, Any]) -> Optional[TableTitle]:
        """Look for explicit table titles in captions or nearby text."""
        # Check for caption blocks before/after tables
        for source, text in [
            ("caption_above_table1", context.get("text_before_table1", "")),
            ("caption_below_table2", context.get("text_after_table2", "")),
            ("section_header", context.get("section_header", ""))
        ]:
            if text and any(marker in text.lower() for marker in ["table", "exhibit", "figure"]):
                # Found likely table caption
                title_text = text.strip()
                if len(title_text) < 200:  # Reasonable title length
                    return TableTitle(
                        found=True,
                        text=title_text,
                        source=source,
                        is_inferred=False
                    )
        
        return None
    
    def _infer_title_from_context(self, context: Dict[str, Any]) -> Optional[TableTitle]:
        """Infer table title from surrounding context."""
        # Look at preceding and following paragraphs
        inference_sources = []
        
        # Check preceding paragraph
        preceding = context.get("preceding_paragraph", "").strip()
        if preceding:
            # Look for data-related keywords
            keywords = ["data", "results", "statistics", "analysis", "comparison", 
                       "summary", "breakdown", "distribution", "metrics", "performance"]
            
            for keyword in keywords:
                if keyword in preceding.lower():
                    # Extract relevant phrase
                    sentences = preceding.split('.')
                    for sent in sentences:
                        if keyword in sent.lower():
                            inference_sources.append((sent.strip(), "preceding_paragraph"))
                            break
        
        # Check section header
        section = context.get("section_header", "").strip()
        if section and len(section) < 100:
            inference_sources.append((section, "section_header"))
        
        # Choose best inference
        if inference_sources:
            # Use the first good inference source
            inferred_text, source = inference_sources[0]
            
            # Clean up and format
            inferred_text = inferred_text.strip()
            if len(inferred_text) > 80:
                # Truncate long text
                inferred_text = inferred_text[:77] + "..."
            
            return TableTitle(
                found=True,
                text=f"Inferred: {inferred_text}",
                source=f"inferred_from_{source}",
                is_inferred=True,
                inference_context=preceding if source == "preceding_paragraph" else section
            )
        
        return None
    
    def _extract_table_data(self, table: Block) -> Dict[str, Any]:
        """Extract table data for analysis (READ ONLY - no modifications)."""
        cells = []
        if hasattr(table, 'children'):
            for cell in table.children:
                if hasattr(cell, 'row_id') and hasattr(cell, 'col_id'):
                    cells.append({
                        "row": cell.row_id,
                        "col": cell.col_id,
                        "text": cell.text if hasattr(cell, 'text') else "",
                        "rowspan": getattr(cell, 'rowspan', 1),
                        "colspan": getattr(cell, 'colspan', 1),
                        "is_header": getattr(cell, 'is_header', False)
                    })
        
        return {
            "id": str(table.id) if hasattr(table, 'id') else "",
            "cells": cells,
            "num_rows": max([c["row"] for c in cells], default=0) + 1,
            "num_cols": max([c["col"] for c in cells], default=0) + 1,
            "extraction_method": getattr(table, 'extraction_method', 'unknown')
        }
    
    def _get_table_context(self, document: Document, table1: Block, 
                          table2: Block) -> Dict[str, Any]:
        """Get surrounding context for the tables."""
        context = {
            "text_before_table1": "",
            "text_between_tables": "",
            "text_after_table2": "",
            "section_header": "",
            "preceding_paragraph": ""
        }
        
        # Find the tables in document structure and get surrounding blocks
        # This is a simplified version - real implementation would traverse
        # the document structure more thoroughly
        
        return context
    
    def _heuristic_analyze(self, table1: Block, table2: Block,
                          t1_data: Dict[str, Any], t2_data: Dict[str, Any],
                          context: Dict[str, Any], table_title: TableTitle) -> TableAnalysis:
        """Perform heuristic analysis when no LLM is available."""
        # Check basic compatibility
        same_cols = t1_data["num_cols"] == t2_data["num_cols"]
        
        # Calculate confidence based on various factors
        confidence = 0.5  # Base confidence
        if same_cols:
            confidence += 0.3
        
        # Check if tables are adjacent
        if self._are_tables_adjacent(table1, table2):
            confidence += 0.1
        
        # Check for continuation patterns (simplified)
        appears_continuous = self._check_continuation(t1_data, t2_data)
        if appears_continuous:
            confidence += 0.1
        
        should_merge = confidence > 0.7 and same_cols
        
        return TableAnalysis(
            table1_id=str(table1.id),
            table2_id=str(table2.id),
            should_merge=should_merge,
            confidence=min(confidence, 1.0),
            merge_type="vertical_append" if should_merge else "none",
            table_title=table_title,
            column_analysis={
                "table1_columns": t1_data["num_cols"],
                "table2_columns": t2_data["num_cols"],
                "columns_match": same_cols
            },
            content_analysis={
                "appears_continuous": appears_continuous,
                "extraction_methods": [t1_data["extraction_method"], t2_data["extraction_method"]]
            },
            reasoning=f"Heuristic analysis: {'Same' if same_cols else 'Different'} column count, "
                     f"{'appears' if appears_continuous else 'does not appear'} continuous",
            warnings=[],
            merge_instructions={
                "operation": "append_rows" if should_merge else "none",
                "preserve_headers": "from_table1",
                "data_modification": "NONE"
            }
        )
    
    def _are_tables_adjacent(self, table1: Block, table2: Block) -> bool:
        """Check if tables are spatially adjacent."""
        # Simplified check - real implementation would use bounding boxes
        return True  # Placeholder
    
    def _check_continuation(self, t1_data: Dict[str, Any], 
                           t2_data: Dict[str, Any]) -> bool:
        """Check if table2 appears to be a continuation of table1."""
        # Simplified check - look for patterns like continued row numbers
        return False  # Placeholder
    
    def _llm_analyze(self, t1_data: Dict[str, Any], t2_data: Dict[str, Any],
                    context: Dict[str, Any], table_title: TableTitle) -> TableAnalysis:
        """Use LLM service for intelligent analysis."""
        # This would call the LLM service with appropriate prompts
        # For now, return a placeholder
        return self._heuristic_analyze(None, None, t1_data, t2_data, context, table_title)