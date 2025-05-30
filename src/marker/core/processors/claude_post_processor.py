"""
Claude Post-Processing for Complete Documents

This processor runs AFTER initial extraction to:
1. Analyze tables for merging decisions
2. Extract/infer table titles from context
3. Add document-wide improvements using Claude

References:
- Claude Code documentation: https://docs.anthropic.com/claude/docs/
"""

import json
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from loguru import logger

from marker.core.processors import BaseProcessor
from marker.core.processors.claude_table_merge_analyzer import (
    TableMergeDecisionEngine, 
    AnalysisConfig
)
from marker.core.processors.claude_section_verifier import (
    SectionVerificationEngine,
    SectionData
)
from marker.core.processors.claude_content_validator import (
    ContentValidationEngine,
    ContentData
)
from marker.core.processors.claude_structure_analyzer import (
    StructureAnalysisEngine,
    StructureData
)
from marker.core.schema import BlockTypes
from marker.core.schema.blocks import Block
from marker.core.schema.document import Document
from marker.core.config.claude_config import MarkerClaudeSettings
from marker.core.processors.performance_tracker import PerformanceTracker


class ClaudePostProcessor(BaseProcessor):
    """
    Post-processor that uses Claude to enhance already-extracted documents.
    
    This runs AFTER the initial extraction pass when we have a complete
    document object with all tables extracted (via Surya/Camelot).
    """
    
    # Process all block types since we need context
    block_types = tuple(BlockTypes)
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        
        # Get Claude configuration
        self.claude_config = self._get_claude_config(config)
        if not self.claude_config.enable_claude_features:
            logger.info("Claude post-processing disabled")
            return
            
        # Initialize analyzers
        workspace_dir = Path(self.claude_config.claude_workspace_dir or "/tmp/marker_claude")
        workspace_dir.mkdir(parents=True, exist_ok=True)
        
        self.merge_engine = TableMergeDecisionEngine(workspace_dir=workspace_dir)
        self.section_engine = SectionVerificationEngine(workspace_dir=workspace_dir)
        self.content_engine = ContentValidationEngine(workspace_dir=workspace_dir)
        self.structure_engine = StructureAnalysisEngine(workspace_dir=workspace_dir)
        
        # Initialize performance tracker
        self.performance_tracker = PerformanceTracker()
        
        logger.info("Claude post-processor initialized with features: "
                   f"table_merge={self.claude_config.enable_table_merge_analysis}, "
                   f"section_verify={self.claude_config.enable_section_verification}, "
                   f"content_validation={self.claude_config.enable_content_validation}, "
                   f"structure_analysis={self.claude_config.enable_structure_analysis}")
    
    def _get_claude_config(self, config: Dict[str, Any]) -> MarkerClaudeSettings:
        """Extract Claude configuration from config dict."""
        if config and "claude" in config:
            if isinstance(config["claude"], MarkerClaudeSettings):
                return config["claude"]
            elif isinstance(config["claude"], dict):
                return MarkerClaudeSettings(**config["claude"])
        
        # Default: Claude disabled
        return MarkerClaudeSettings(enable_claude_features=False)
    
    def __call__(self, document: Document):
        """Process the complete document with Claude enhancements."""
        if not self.claude_config.enable_claude_features:
            return
            
        logger.info("Starting Claude post-processing")
        self.performance_tracker.start_total_processing()
        
        # Run different enhancements based on configuration
        if self.claude_config.enable_table_merge_analysis:
            self.performance_tracker.start_feature("table_merge_analysis")
            self._analyze_and_merge_tables(document)
            self.performance_tracker.end_feature("table_merge_analysis")
            
        if self.claude_config.enable_section_verification:
            self.performance_tracker.start_feature("section_verification")
            self._verify_sections(document)
            self.performance_tracker.end_feature("section_verification")
            
        if self.claude_config.enable_content_validation:
            self.performance_tracker.start_feature("content_validation")
            self._validate_content(document)
            self.performance_tracker.end_feature("content_validation")
            
        if self.claude_config.enable_structure_analysis:
            self.performance_tracker.start_feature("structure_analysis")
            self._analyze_structure(document)
            self.performance_tracker.end_feature("structure_analysis")
            
        self.performance_tracker.end_total_processing()
        
        # Store performance metrics in document
        if not hasattr(document, 'claude_performance'):
            document.claude_performance = self.performance_tracker.get_metadata()
            
        logger.info("Claude post-processing complete")
    
    def _analyze_and_merge_tables(self, document: Document):
        """Analyze tables for merging and title inference."""
        tables = self._collect_all_tables(document)
        
        if len(tables) < self.claude_config.min_tables_for_claude_analysis:
            logger.info(f"Only {len(tables)} tables found, skipping Claude analysis "
                       f"(min: {self.claude_config.min_tables_for_claude_analysis})")
            return
        
        logger.info(f"Analyzing {len(tables)} tables for merging and titles")
        
        # Analyze consecutive tables for merging
        merge_decisions = self._analyze_table_pairs(tables, document)
        
        # Apply merge decisions
        merged_count = self._apply_merge_decisions(merge_decisions, document)
        
        # Extract/infer titles for all tables
        # TODO: Implement title inference - tables don't have title attribute by default
        # self._infer_table_titles(document)
        
        logger.info(f"Table analysis complete: {merged_count} tables merged")
    
    def _collect_all_tables(self, document: Document) -> List[Tuple[int, Block]]:
        """Collect all tables with their page indices."""
        tables = []
        for page_idx, page in enumerate(document.pages):
            for block in page.contained_blocks(document, [BlockTypes.Table]):
                tables.append((page_idx, block))
        return tables
    
    def _analyze_table_pairs(self, tables: List[Tuple[int, Block]], 
                           document: Document) -> List[Dict[str, Any]]:
        """Analyze consecutive table pairs for merging."""
        merge_decisions = []
        
        for i in range(len(tables) - 1):
            page_idx1, table1 = tables[i]
            page_idx2, table2 = tables[i + 1]
            
            # Only consider tables on same or consecutive pages
            if abs(page_idx2 - page_idx1) > 1:
                continue
                
            # Get surrounding context
            context1 = self._get_table_context(table1, document.pages[page_idx1], document)
            context2 = self._get_table_context(table2, document.pages[page_idx2], document)
            
            # Prepare analysis config
            config = AnalysisConfig(
                table1_data={
                    "html": getattr(table1, 'html', ''),
                    "bbox": table1.polygon.bbox,
                    "page": page_idx1,
                    "context": context1
                },
                table2_data={
                    "html": getattr(table2, 'html', ''), 
                    "bbox": table2.polygon.bbox,
                    "page": page_idx2,
                    "context": context2
                },
                context={
                    "pages_apart": page_idx2 - page_idx1,
                    "extraction_method1": getattr(table1, 'extraction_method', 'unknown'),
                    "extraction_method2": getattr(table2, 'extraction_method', 'unknown')
                },
                confidence_threshold=self.claude_config.table_merge_confidence_threshold
            )
            
            # Submit for analysis using synchronous wrapper
            try:
                task_id = self.merge_engine.submit_merge_analysis_sync(
                    table1_data=config.table1_data,
                    table2_data=config.table2_data,
                    context=config.context,
                    confidence_threshold=self.claude_config.table_merge_confidence_threshold
                )
                result = self.merge_engine.get_merge_decision_sync(task_id, timeout=60)
                
                if result and result.should_merge:
                    merge_decisions.append({
                        "table1": table1,
                        "table2": table2,
                        "page1": page_idx1,
                        "page2": page_idx2,
                        "confidence": result.confidence,
                        "reasoning": result.reasoning,
                        "merge_type": result.merge_type
                    })
                    logger.debug(f"Tables on pages {page_idx1}-{page_idx2} should merge "
                               f"(confidence: {result.confidence:.2f})")
                    
            except Exception as e:
                logger.warning(f"Failed to analyze table pair: {e}")
                
        return merge_decisions
    
    def _get_table_context(self, table: Block, page: Block, document: Document, 
                          context_lines: int = 3) -> Dict[str, Any]:
        """Get surrounding context for a table."""
        context = {
            "before_text": [],
            "after_text": [],
            "section": None
        }
        
        # Find table position in page
        table_idx = None
        page_blocks = list(page.contained_blocks(document))
        for idx, block in enumerate(page_blocks):
            if block.id == table.id:
                table_idx = idx
                break
                
        if table_idx is None:
            return context
            
        # Get text before table
        for i in range(max(0, table_idx - context_lines), table_idx):
            block = page_blocks[i]
            if block.block_type in [BlockTypes.Text, BlockTypes.TextInlineMath]:
                if hasattr(block, 'text'):
                    context["before_text"].append(block.text)
                
        # Get text after table  
        for i in range(table_idx + 1, min(len(page_blocks), table_idx + context_lines + 1)):
            block = page_blocks[i]
            if block.block_type in [BlockTypes.Text, BlockTypes.TextInlineMath]:
                if hasattr(block, 'text'):
                    context["after_text"].append(block.text)
                
        # Get section info
        if hasattr(table, 'section_hierarchy') and table.section_hierarchy:
            # Get the most specific (highest number) section
            deepest_section = max(table.section_hierarchy.items(), 
                                key=lambda x: int(x[0]))[1]
            context["section"] = json.loads(deepest_section)
            
        return context
    
    def _apply_merge_decisions(self, merge_decisions: List[Dict[str, Any]], 
                             document: Document) -> int:
        """Apply merge decisions to document."""
        merged_count = 0
        
        # Sort by first table position to avoid conflicts
        merge_decisions.sort(key=lambda x: (x["page1"], x["table1"].bbox[1]))
        
        # Track tables that have been merged (to avoid double merging)
        merged_tables = set()
        
        for decision in merge_decisions:
            table1 = decision["table1"]
            table2 = decision["table2"]
            
            if table1.id in merged_tables or table2.id in merged_tables:
                continue
                
            # Merge table2 into table1
            self._merge_tables(table1, table2, decision["merge_type"])
            
            # Mark table2 for removal
            table2.merged_into = table1.id
            merged_tables.add(table2.id)
            
            # Add merge metadata
            if not hasattr(table1, 'merge_info'):
                table1.merge_info = []
            table1.merge_info.append({
                "merged_table_id": table2.id,
                "confidence": decision["confidence"],
                "reasoning": decision["reasoning"],
                "merge_type": decision["merge_type"]
            })
            
            merged_count += 1
            
        # Remove merged tables from document
        for page in document.pages:
            if page.children:
                page.children = [b for b in page.children 
                               if not (hasattr(b, 'merged_into') and b.merged_into)]
            
        return merged_count
    
    def _merge_tables(self, table1: Block, table2: Block, merge_type: str):
        """Merge table2 into table1."""
        # For now, simple concatenation of HTML
        # TODO: Implement smarter merging based on merge_type
        
        if merge_type == "vertical_continuation":
            # Append rows from table2 to table1
            if hasattr(table1, 'html') and hasattr(table2, 'html'):
                table1.html = self._merge_html_tables_vertical(table1.html, table2.html)
        else:
            # Default: append with separator
            if hasattr(table1, 'html') and hasattr(table2, 'html'):
                table1.html += "\n<!-- Merged Table -->\n" + table2.html
            
        # Update polygon to encompass both tables
        table1.polygon = table1.polygon.merge([table2.polygon])
    
    def _merge_html_tables_vertical(self, html1: str, html2: str) -> str:
        """Merge two HTML tables vertically."""
        # Simple approach: extract tbody content and combine
        # TODO: Use BeautifulSoup for proper HTML parsing
        
        try:
            # Extract tbody content from second table
            tbody2_start = html2.find("<tbody>")
            tbody2_end = html2.find("</tbody>")
            if tbody2_start > 0 and tbody2_end > tbody2_start:
                tbody2_content = html2[tbody2_start + 7:tbody2_end]
                
                # Insert before closing tbody of first table
                tbody1_end = html1.rfind("</tbody>")
                if tbody1_end > 0:
                    return html1[:tbody1_end] + tbody2_content + html1[tbody1_end:]
                    
        except Exception as e:
            logger.warning(f"Failed to merge HTML tables: {e}")
            
        # Fallback
        return html1 + "\n" + html2
    
    def _infer_table_titles(self, document: Document):
        """Infer titles for tables that don't have them."""
        for page in document.pages:
            for table in page.contained_blocks(document, [BlockTypes.Table]):
                if hasattr(table, 'title') and table.title:
                    continue
                    
                # Get context and infer title
                context = self._get_table_context(table, page, document)
                title = self._infer_single_table_title(table, context)
                
                if title:
                    # Add "Infer:" prefix to indicate this was inferred
                    table.title = f"Infer: {title}"
                    logger.debug(f"Inferred title for table: {title}")
    
    def _infer_single_table_title(self, table: Block, 
                                context: Dict[str, Any]) -> Optional[str]:
        """Infer title for a single table from context."""
        # Simple heuristic: Look for text immediately before table
        # that might be a title (short, possibly formatted)
        
        before_text = context.get("before_text", [])
        if not before_text:
            return None
            
        # Check last few lines before table
        for text in reversed(before_text[-3:]):
            text = text.strip()
            
            # Heuristics for title detection
            if (len(text) < 100 and  # Titles are usually short
                (text.startswith("Table") or 
                 text.startswith("Figure") or
                 text.endswith(":") or
                 text.isupper() or  # All caps
                 any(keyword in text.lower() for keyword in 
                     ["summary", "results", "comparison", "data", "statistics"]))):
                return text.rstrip(":")
                
        # Check section title as fallback
        if context.get("section") and "title" in context["section"]:
            section_title = context["section"]["title"]
            if section_title and len(section_title) < 80:
                return f"{section_title} Data"
                
        return None
    
    def _verify_sections(self, document: Document):
        """Verify section hierarchy using Claude."""
        logger.info("Starting section hierarchy verification")
        
        # Collect all section headers from document
        sections = self._collect_document_sections(document)
        
        if not sections:
            logger.info("No sections found in document, skipping verification")
            return
            
        logger.info(f"Verifying {len(sections)} sections")
        
        # Determine document type
        doc_type = self._infer_document_type(document)
        
        # Get expected structure for document type
        expected_structure = self._get_expected_structure(doc_type)
        
        # Prepare page images if available
        page_images = None
        if hasattr(document, 'page_images') and document.page_images:
            page_images = [Path(img) for img in document.page_images[:5]]  # First 5 pages
        
        # Submit for verification using synchronous wrapper
        try:
            task_id = self.section_engine.submit_verification_sync(
                sections=sections,
                document_type=doc_type,
                expected_structure=expected_structure,
                page_images=page_images,
                confidence_threshold=self.claude_config.section_confidence_threshold
            )
            
            result = self.section_engine.get_verification_result_sync(task_id, timeout=90)
            
            if result:
                logger.info(f"Section verification complete: valid={result.is_valid}, "
                           f"confidence={result.confidence:.2f}")
                
                # Process issues
                if result.issues:
                    logger.warning(f"Found {len(result.issues)} section issues:")
                    for issue in result.issues:
                        logger.warning(f"  - {issue.issue_type.value} ({issue.severity}): {issue.description}")
                        
                    # Add issues to document metadata
                    if not hasattr(document, 'section_issues'):
                        document.section_issues = []
                    document.section_issues.extend([{
                        'type': issue.issue_type.value,
                        'severity': issue.severity,
                        'description': issue.description,
                        'suggestion': issue.suggestion,
                        'confidence': issue.confidence
                    } for issue in result.issues])
                
                # Add verification summary to document
                document.section_verification = {
                    'is_valid': result.is_valid,
                    'confidence': result.confidence,
                    'structural_score': result.structural_score,
                    'completeness_score': result.completeness_score,
                    'hierarchy_score': result.hierarchy_score,
                    'summary': result.analysis_summary
                }
                
                # Apply suggested hierarchy if confidence is high
                if (result.suggested_hierarchy and 
                    result.confidence >= self.claude_config.section_confidence_threshold and
                    self.claude_config.auto_fix_sections):
                    self._apply_section_fixes(document, result.suggested_hierarchy)
                    
        except Exception as e:
            logger.error(f"Section verification failed: {e}")
            
    def _collect_document_sections(self, document: Document) -> List[SectionData]:
        """Collect all section headers from document."""
        sections = []
        section_id_counter = 0
        
        for page_idx, page in enumerate(document.pages):
            for block in page.contained_blocks(document):
                if block.block_type == BlockTypes.SectionHeader:
                    section_id_counter += 1
                    
                    # Extract section data
                    section_data = SectionData(
                        level=getattr(block, 'level', 1),
                        title=getattr(block, 'text', 'Untitled'),
                        content=self._get_section_content(block, page, document),
                        page_number=page_idx + 1,
                        position={
                            'x': block.polygon.bbox[0],
                            'y': block.polygon.bbox[1],
                            'width': block.polygon.bbox[2] - block.polygon.bbox[0],
                            'height': block.polygon.bbox[3] - block.polygon.bbox[1]
                        } if block.polygon else None,
                        section_id=f"section_{section_id_counter}"
                    )
                    sections.append(section_data)
                    
        return sections
    
    def _get_section_content(self, section_block: Block, page: Block, 
                           document: Document, max_blocks: int = 5) -> str:
        """Get content preview for a section."""
        content_blocks = []
        found_section = False
        
        # Look for text content after this section header
        for block in page.contained_blocks(document):
            if block.id == section_block.id:
                found_section = True
                continue
                
            if found_section:
                if block.block_type == BlockTypes.SectionHeader:
                    # Stop at next section
                    break
                elif block.block_type in [BlockTypes.Text, BlockTypes.TextInlineMath]:
                    if hasattr(block, 'text'):
                        content_blocks.append(block.text)
                        if len(content_blocks) >= max_blocks:
                            break
                            
        return ' '.join(content_blocks)
    
    def _infer_document_type(self, document: Document) -> str:
        """Infer document type from content and structure."""
        # Simple heuristics - can be enhanced
        text_content = []
        section_titles = []
        
        for page in document.pages[:3]:  # Check first 3 pages
            for block in page.contained_blocks(document):
                if block.block_type == BlockTypes.Text and hasattr(block, 'text'):
                    text_content.append(block.text.lower())
                elif block.block_type == BlockTypes.SectionHeader and hasattr(block, 'text'):
                    section_titles.append(block.text.lower())
                    
        combined_text = ' '.join(text_content + section_titles)
        
        # Document type detection
        if any(word in combined_text for word in ['abstract', 'methodology', 'conclusion', 'references']):
            return 'research_paper'
        elif any(word in combined_text for word in ['invoice', 'bill', 'payment', 'due date']):
            return 'invoice'
        elif any(word in combined_text for word in ['contract', 'agreement', 'terms', 'parties']):
            return 'legal_contract'
        elif any(word in combined_text for word in ['report', 'executive summary', 'findings']):
            return 'business_report'
        elif any(word in combined_text for word in ['manual', 'installation', 'troubleshooting']):
            return 'technical_manual'
        else:
            return 'general_document'
            
    def _get_expected_structure(self, doc_type: str) -> Optional[List[str]]:
        """Get expected section structure for document type."""
        structures = {
            'research_paper': [
                'Abstract',
                'Introduction',
                'Background/Literature Review',
                'Methodology/Methods',
                'Results',
                'Discussion',
                'Conclusion',
                'References'
            ],
            'business_report': [
                'Executive Summary',
                'Introduction',
                'Analysis/Findings',
                'Recommendations',
                'Conclusion',
                'Appendices'
            ],
            'technical_manual': [
                'Introduction/Overview',
                'System Requirements',
                'Installation',
                'Configuration',
                'Usage/Operations',
                'Troubleshooting',
                'Appendices'
            ],
            'legal_contract': [
                'Parties',
                'Recitals/Background',
                'Terms and Conditions',
                'Payment Terms',
                'Termination',
                'General Provisions',
                'Signatures'
            ]
        }
        
        return structures.get(doc_type)
    
    def _apply_section_fixes(self, document: Document, suggested_hierarchy: List[Dict]):
        """Apply suggested section hierarchy fixes."""
        logger.info("Applying suggested section hierarchy fixes")
        
        # This is a placeholder - actual implementation would need to:
        # 1. Update section header levels
        # 2. Reorder sections if needed
        # 3. Add missing section headers
        # 4. Update document structure
        
        # For now, just log the suggestions
        for suggestion in suggested_hierarchy:
            logger.info(f"Suggested: Level {suggestion.get('level')} - {suggestion.get('title')}")
    
    def _validate_content(self, document: Document):
        """Validate document content quality using Claude."""
        logger.info("Starting content quality validation")
        
        # Collect document content and statistics
        content_data = self._collect_content_data(document)
        
        if not content_data.text_content:
            logger.info("No text content found, skipping validation")
            return
            
        logger.info(f"Validating document with {content_data.page_count} pages, "
                   f"{content_data.section_count} sections")
        
        # Determine document type
        doc_type = self._infer_document_type(document)
        
        # Define validation criteria based on document type
        validation_criteria = self._get_validation_criteria(doc_type)
        
        # Prepare page images if available
        page_images = None
        if hasattr(document, 'page_images') and document.page_images:
            page_images = [Path(img) for img in document.page_images[:3]]  # First 3 pages
        
        # Submit for validation using synchronous wrapper
        try:
            task_id = self.content_engine.submit_validation_sync(
                content_data=content_data,
                document_type=doc_type,
                validation_criteria=validation_criteria,
                page_images=page_images,
                confidence_threshold=self.claude_config.content_confidence_threshold
            )
            
            result = self.content_engine.get_validation_result_sync(task_id, timeout=90)
            
            if result:
                logger.info(f"Content validation complete: valid={result.is_valid}, "
                           f"confidence={result.confidence:.2f}")
                logger.info(f"Quality scores - Overall: {result.quality_score:.2f}, "
                           f"Completeness: {result.completeness_score:.2f}, "
                           f"Coherence: {result.coherence_score:.2f}, "
                           f"Formatting: {result.formatting_score:.2f}")
                
                # Process issues
                if result.issues:
                    logger.warning(f"Found {len(result.issues)} content issues:")
                    for issue in result.issues:
                        logger.warning(f"  - {issue.issue_type.value} ({issue.severity}): {issue.description}")
                        
                    # Add issues to document metadata
                    if not hasattr(document, 'content_issues'):
                        document.content_issues = []
                    document.content_issues.extend([{
                        'type': issue.issue_type.value,
                        'severity': issue.severity,
                        'location': issue.location,
                        'description': issue.description,
                        'suggestion': issue.suggestion,
                        'confidence': issue.confidence
                    } for issue in result.issues])
                
                # Add validation summary to document
                document.content_validation = {
                    'is_valid': result.is_valid,
                    'confidence': result.confidence,
                    'quality_score': result.quality_score,
                    'completeness_score': result.completeness_score,
                    'coherence_score': result.coherence_score,
                    'formatting_score': result.formatting_score,
                    'summary': result.analysis_summary,
                    'recommendations': result.recommendations
                }
                
                # Log recommendations
                if result.recommendations:
                    logger.info("Content improvement recommendations:")
                    for rec in result.recommendations:
                        logger.info(f"  - {rec}")
                        
        except Exception as e:
            logger.error(f"Content validation failed: {e}")
            
    def _collect_content_data(self, document: Document) -> ContentData:
        """Collect document content and statistics."""
        text_blocks = []
        section_count = 0
        table_count = 0
        figure_count = 0
        equation_count = 0
        code_block_count = 0
        sample_sections = []
        
        for page_idx, page in enumerate(document.pages):
            for block in page.contained_blocks(document):
                # Count different block types
                if block.block_type == BlockTypes.SectionHeader:
                    section_count += 1
                    # Collect sample section
                    if len(sample_sections) < 5:  # First 5 sections
                        section_content = self._get_section_content(block, page, document)
                        sample_sections.append({
                            'title': getattr(block, 'text', 'Untitled'),
                            'content': section_content
                        })
                elif block.block_type == BlockTypes.Table:
                    table_count += 1
                elif block.block_type == BlockTypes.Figure:
                    figure_count += 1
                elif block.block_type == BlockTypes.Equation:
                    equation_count += 1
                elif block.block_type == BlockTypes.Code:
                    code_block_count += 1
                
                # Collect text content
                if block.block_type in [BlockTypes.Text, BlockTypes.TextInlineMath]:
                    if hasattr(block, 'text'):
                        text_blocks.append(block.text)
        
        # Combine text content (limit to first 10k chars for API)
        text_content = '\n'.join(text_blocks)[:10000]
        
        # Extract metadata
        metadata = {}
        if hasattr(document, 'metadata'):
            metadata = document.metadata
        
        return ContentData(
            text_content=text_content,
            section_count=section_count,
            table_count=table_count,
            figure_count=figure_count,
            equation_count=equation_count,
            code_block_count=code_block_count,
            page_count=len(document.pages),
            metadata=metadata,
            sample_sections=sample_sections
        )
    
    def _get_validation_criteria(self, doc_type: str) -> List[str]:
        """Get validation criteria for document type."""
        criteria = {
            'research_paper': [
                "Abstract should summarize key findings",
                "Introduction should state research objectives",
                "Methodology should be clearly described",
                "Results should be supported by data",
                "References should be properly formatted",
                "Figures and tables should be referenced in text"
            ],
            'business_report': [
                "Executive summary should be concise and complete",
                "Key findings should be highlighted",
                "Recommendations should be actionable",
                "Data should support conclusions",
                "Professional tone throughout"
            ],
            'technical_manual': [
                "Instructions should be clear and step-by-step",
                "Technical terms should be defined",
                "Troubleshooting section should be comprehensive",
                "Examples should be provided",
                "Safety warnings should be prominent"
            ],
            'legal_contract': [
                "All parties should be clearly identified",
                "Terms should be unambiguous",
                "Obligations should be clearly stated",
                "Termination conditions should be specified",
                "Legal language should be consistent"
            ],
            'general_document': [
                "Content should be well-organized",
                "Sections should flow logically",
                "Formatting should be consistent",
                "Key points should be clear"
            ]
        }
        
        return criteria.get(doc_type, criteria['general_document'])
    
    def _analyze_structure(self, document: Document):
        """Analyze document structure and organization using Claude."""
        logger.info("Starting document structure analysis")
        
        # Collect structure data
        structure_data = self._collect_structure_data(document)
        
        logger.info(f"Analyzing structure: {structure_data.total_pages} pages, "
                   f"{len(structure_data.section_hierarchy)} top-level sections")
        
        # Determine document type
        doc_type = self._infer_document_type(document)
        
        # Determine analysis depth based on document size
        if structure_data.total_pages < 10:
            analysis_depth = "basic"
        elif structure_data.total_pages < 50:
            analysis_depth = "moderate"
        else:
            analysis_depth = "comprehensive"
        
        # Prepare page images if available
        page_images = None
        if hasattr(document, 'page_images') and document.page_images:
            page_images = [Path(img) for img in document.page_images[:3]]  # First 3 pages
        
        # Submit for analysis using synchronous wrapper
        try:
            task_id = self.structure_engine.submit_analysis_sync(
                structure_data=structure_data,
                document_type=doc_type,
                analysis_depth=analysis_depth,
                page_images=page_images,
                confidence_threshold=self.claude_config.structure_confidence_threshold
            )
            
            result = self.structure_engine.get_analysis_result_sync(task_id, timeout=120)
            
            if result:
                logger.info(f"Structure analysis complete:")
                logger.info(f"  - Organization: {result.organization_score:.2f}")
                logger.info(f"  - Flow: {result.flow_score:.2f}")
                logger.info(f"  - Navigation: {result.navigation_score:.2f}")
                logger.info(f"  - Overall: {result.overall_structure_score:.2f}")
                logger.info(f"  - Pattern: {result.document_pattern}")
                
                # Process insights
                if result.insights:
                    logger.info(f"Found {len(result.insights)} structural insights:")
                    for insight in result.insights[:5]:  # First 5 insights
                        logger.info(f"  - {insight.finding} (Impact: {insight.impact})")
                        
                    # Add insights to document metadata
                    if not hasattr(document, 'structure_insights'):
                        document.structure_insights = []
                    document.structure_insights.extend([{
                        'type': insight.insight_type.value,
                        'category': insight.category,
                        'finding': insight.finding,
                        'impact': insight.impact,
                        'recommendation': insight.recommendation,
                        'confidence': insight.confidence
                    } for insight in result.insights])
                
                # Add analysis summary to document
                document.structure_analysis = {
                    'organization_score': result.organization_score,
                    'flow_score': result.flow_score,
                    'navigation_score': result.navigation_score,
                    'overall_score': result.overall_structure_score,
                    'pattern': result.document_pattern,
                    'summary': result.analysis_summary,
                    'improvement_plan': result.improvement_plan
                }
                
                # Add structure diagram if available
                if result.structure_diagram:
                    document.structure_diagram = result.structure_diagram
                    logger.debug("Structure diagram generated")
                    
        except Exception as e:
            logger.error(f"Structure analysis failed: {e}")
            
    def _collect_structure_data(self, document: Document) -> StructureData:
        """Collect document structure data."""
        section_hierarchy = []
        content_distribution = {}
        page_structures = []
        cross_references = []
        navigation_elements = {
            'has_toc': False,
            'has_index': False,
            'has_list_of_figures': False,
            'has_list_of_tables': False
        }
        
        # Build section hierarchy
        current_sections = {}  # Track sections by level
        
        for page_idx, page in enumerate(document.pages):
            page_structure = {
                'page': page_idx + 1,
                'blocks': 0,
                'block_types': {}
            }
            
            for block in page.contained_blocks(document):
                page_structure['blocks'] += 1
                block_type_name = block.block_type.name
                
                # Count block types
                if block_type_name not in content_distribution:
                    content_distribution[block_type_name] = 0
                content_distribution[block_type_name] += 1
                
                if block_type_name not in page_structure['block_types']:
                    page_structure['block_types'][block_type_name] = 0
                page_structure['block_types'][block_type_name] += 1
                
                # Build section hierarchy
                if block.block_type == BlockTypes.SectionHeader:
                    level = getattr(block, 'level', 1)
                    title = getattr(block, 'text', 'Untitled')
                    
                    section_info = {
                        'title': title,
                        'level': level,
                        'page': page_idx + 1,
                        'subsections': []
                    }
                    
                    # Place in hierarchy
                    if level == 1:
                        section_hierarchy.append(section_info)
                        current_sections = {1: section_info}
                    else:
                        # Find parent section
                        parent_level = level - 1
                        if parent_level in current_sections:
                            current_sections[parent_level]['subsections'].append(section_info)
                            current_sections[level] = section_info
                
                # Detect navigation elements
                if block.block_type == BlockTypes.TableOfContents:
                    navigation_elements['has_toc'] = True
                elif hasattr(block, 'text'):
                    text_lower = block.text.lower()
                    if 'list of figures' in text_lower:
                        navigation_elements['has_list_of_figures'] = True
                    elif 'list of tables' in text_lower:
                        navigation_elements['has_list_of_tables'] = True
                    elif 'index' in text_lower and len(text_lower) < 50:
                        navigation_elements['has_index'] = True
                    
                    # Detect cross-references (simple pattern matching)
                    import re
                    ref_patterns = [
                        r'see\s+(section|figure|table|equation)\s+(\d+)',
                        r'refer\s+to\s+(section|figure|table)\s+(\d+)',
                        r'as\s+shown\s+in\s+(figure|table)\s+(\d+)'
                    ]
                    for pattern in ref_patterns:
                        matches = re.findall(pattern, text_lower)
                        for match in matches:
                            cross_references.append({
                                'from': f"Page {page_idx + 1}",
                                'to': f"{match[0].capitalize()} {match[1]}"
                            })
            
            # Determine dominant type for page
            if page_structure['block_types']:
                dominant_type = max(page_structure['block_types'].items(), key=lambda x: x[1])[0]
                page_structure['dominant_type'] = dominant_type
            
            page_structures.append(page_structure)
        
        # Calculate average content per page
        total_blocks = sum(ps['blocks'] for ps in page_structures)
        avg_content_per_page = total_blocks / len(document.pages) if document.pages else 0
        
        # Extract document metadata
        metadata = {}
        if hasattr(document, 'metadata'):
            metadata = document.metadata
        
        return StructureData(
            section_hierarchy=section_hierarchy,
            content_distribution=content_distribution,
            page_structure=page_structures,
            cross_references=cross_references[:20],  # Limit to first 20
            navigation_elements=navigation_elements,
            document_metadata=metadata,
            total_pages=len(document.pages),
            avg_content_per_page=avg_content_per_page
        )


if __name__ == "__main__":
    # Test the post-processor
    from marker.core.converters.pdf import PdfConverter
    from marker.core.builders.document import DocumentBuilder
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python claude_post_processor.py <pdf_file>")
        sys.exit(1)
        
    pdf_path = sys.argv[1]
    
    # Create test configuration with Claude enabled
    claude_config = MarkerClaudeSettings(
        enable_claude_features=True,
        enable_table_merge_analysis=True,
        min_tables_for_claude_analysis=2,
        table_merge_confidence_threshold=0.7
    )
    
    config = {
        "claude": claude_config
    }
    
    # First pass: regular extraction
    print("Running initial extraction...")
    converter = PdfConverter(
        config=config,
        artifact_dict={},
        processor_list=None,  # Use defaults
        renderer="markdown"
    )
    
    document = converter.build_document(pdf_path)
    
    # Second pass: Claude post-processing
    print("Running Claude post-processing...")
    post_processor = ClaudePostProcessor(config)
    post_processor(document)
    
    # Show results
    print(f"Document has {len(document.pages)} pages")
    table_count = sum(len(list(page.contained_blocks(document, [BlockTypes.Table]))) 
                     for page in document.pages)
    print(f"Found {table_count} tables after processing")
    
    # Show table titles
    for page_idx, page in enumerate(document.pages):
        for table in page.contained_blocks(document, [BlockTypes.Table]):
            title = getattr(table, 'title', 'No title')
            merge_info = getattr(table, 'merge_info', [])
            print(f"  Page {page_idx}: {title} (merged {len(merge_info)} tables)")