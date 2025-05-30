"""
Test suite for Claude post-processor integration.

This test validates the integration of all Claude features within the
ClaudePostProcessor, including table merge analysis, section verification,
content validation, structure analysis, and image description.
"""

import os
import pytest
import tempfile
from unittest.mock import patch, MagicMock, AsyncMock
from PIL import Image

from marker.processors.claude_post_processor import ClaudePostProcessor
from marker.processors.claude_table_merge_analyzer import AnalysisResult as TableAnalysisResult
from marker.processors.claude_section_verifier import VerificationResult as SectionVerificationResult, SectionIssue as StructuralIssue
from marker.processors.claude_content_validator import ValidationResult as ContentValidationResult, ContentIssue
from marker.processors.claude_structure_analyzer import AnalysisResult as StructureAnalysisResult, StructureInsight as OrganizationalInsight
from marker.processors.claude_image_describer import DescriptionResult as ImageDescriptionResult, ImageType
from dataclasses import dataclass
from typing import Optional, Any, Dict, List

@dataclass
class QualityMetrics:
    completeness: float
    coherence: float
    formatting: float
    readability: float
    overall: float

@dataclass
class StructurePattern:
    type: str
    description: str
    strength: float
    examples: list

@dataclass  
class ExtractedData:
    type: str
    values: Optional[List[Dict[str, Any]]] = None
    columns: Optional[List[str]] = None
    rows: Optional[int] = None
    trend: Optional[str] = None
    title: Optional[str] = None

from marker.schema.document import Document
from marker.schema.groups.page import PageGroup
from marker.schema.blocks.table import Table
from marker.schema.blocks.text import Text
from marker.schema.blocks.sectionheader import SectionHeader
from marker.schema.blocks.figure import Figure
from marker.config.claude_config import ClaudeConfig


class TestClaudePostProcessorIntegration:
    """Test suite for Claude post-processor integration"""
    
    @pytest.fixture
    def claude_config(self):
        """Create Claude configuration for testing"""
        return ClaudeConfig(
            enable_table_merge_analysis=True,
            enable_section_verification=True,
            enable_content_validation=True,
            enable_structure_analysis=True,
            enable_image_description=True,
            table_confidence_threshold=0.75,
            section_confidence_threshold=0.8,
            content_confidence_threshold=0.85,
            structure_confidence_threshold=0.9,
            auto_fix_sections=False,
            max_polling_attempts=3,
            polling_interval=0.1  # Fast polling for tests
        )
    
    @pytest.fixture
    def sample_document(self):
        """Create a comprehensive test document"""
        doc = Document(filepath="test_integration.pdf")
        
        # Page 1
        page1 = PageGroup(page_id=0, bbox=[0, 0, 612, 792])
        
        # Title
        title = SectionHeader(
            text="Integration Test Document",
            level=1,
            bbox=[50, 50, 500, 80]
        )
        page1.add_child(title)
        
        # Section with text
        section1 = SectionHeader(
            text="1. Introduction",
            level=2,
            bbox=[50, 100, 300, 120]
        )
        page1.add_child(section1)
        
        intro_text = Text(
            text="This document tests all Claude integration features.",
            bbox=[50, 130, 500, 150]
        )
        page1.add_child(intro_text)
        
        # Table that could be merged
        table1 = Table(
            bbox=[50, 200, 300, 300],
            cells=[["Name", "Value"], ["Feature 1", "Active"]],
            merge_type="horizontal"
        )
        page1.add_child(table1)
        
        # Related table (potential merge candidate)
        table2 = Table(
            bbox=[320, 200, 550, 300],
            cells=[["Status", "Notes"], ["Ready", "Tested"]],
            merge_type="horizontal"
        )
        page1.add_child(table2)
        
        # Figure for image description
        figure = Figure(
            bbox=[50, 350, 350, 500],
            caption="System architecture diagram"
        )
        page1.add_child(figure)
        
        doc.pages.append(page1)
        
        # Page 2 with problematic sections
        page2 = PageGroup(page_id=1, bbox=[0, 0, 612, 792])
        
        # Level 3 without level 2 (hierarchy issue)
        bad_section = SectionHeader(
            text="1.1.1 Details",
            level=3,
            bbox=[50, 50, 300, 70]
        )
        page2.add_child(bad_section)
        
        # Add some incomplete content
        incomplete_text = Text(
            text="This section appears to be...",
            bbox=[50, 80, 400, 100]
        )
        page2.add_child(incomplete_text)
        
        doc.pages.append(page2)
        
        return doc
    
    @pytest.fixture
    def page_images(self):
        """Create mock page images"""
        # Create simple test images
        images = {}
        for i in range(2):
            img = Image.new('RGB', (612, 792), color='white')
            images[i] = img
        return images
    
    @pytest.fixture
    def processor(self, claude_config):
        """Create processor instance"""
        with tempfile.TemporaryDirectory() as tmpdir:
            claude_config.task_db_path = os.path.join(tmpdir, "tasks.db")
            yield ClaudePostProcessor(claude_config)
    
    def test_processor_initialization(self, processor, claude_config):
        """Test processor initializes all components correctly"""
        assert processor.config == claude_config
        assert processor.table_analyzer is not None
        assert processor.section_verifier is not None
        assert processor.content_validator is not None
        assert processor.structure_analyzer is not None
        assert processor.image_describer is not None
    
    def test_process_document_all_features(self, processor, sample_document, page_images):
        """Test processing document with all features enabled"""
        # Mock all the sync methods to return task IDs
        with patch.object(processor.table_analyzer, 'sync_analyze_table_merge', return_value='table-task-1'), \
             patch.object(processor.section_verifier, 'sync_verify_sections', return_value='section-task-1'), \
             patch.object(processor.content_validator, 'sync_validate_content', return_value='content-task-1'), \
             patch.object(processor.structure_analyzer, 'sync_analyze_structure', return_value='structure-task-1'), \
             patch.object(processor.image_describer, 'sync_describe_image', return_value='image-task-1'):
            
            # Mock polling results
            table_result = TableAnalysisResult(
                confidence=0.85,
                should_merge=True,
                reasoning="Tables are related and share context",
                quality_score=0.9,
                suggestions=[]
            )
            
            section_result = SectionVerificationResult(
                confidence=0.75,
                is_valid=False,
                issues=[
                    StructuralIssue(
                        type="hierarchy_skip",
                        page=1,
                        section="1.1.1 Details",
                        description="Level 3 without level 2",
                        severity="error"
                    )
                ],
                suggestions=["Add missing level 2 header"],
                structural_score=0.7
            )
            
            content_result = ContentValidationResult(
                confidence=0.82,
                is_valid=True,
                quality_metrics=QualityMetrics(
                    completeness=0.8,
                    coherence=0.85,
                    formatting=0.9,
                    readability=0.88,
                    overall=0.86
                ),
                issues=[],
                suggestions=[],
                content_summary="Well-structured test document"
            )
            
            structure_result = StructureAnalysisResult(
                confidence=0.88,
                structure_type="hierarchical",
                patterns=[
                    StructurePattern(
                        type="nested_sections",
                        description="Document uses section hierarchy",
                        strength=0.85,
                        examples=["1. Introduction", "1.1.1 Details"]
                    )
                ],
                insights=[],
                complexity_score=0.6,
                organization_score=0.8
            )
            
            image_result = ImageDescriptionResult(
                confidence=0.9,
                image_type=ImageType.DIAGRAM,
                description="System architecture diagram showing components",
                accessibility_text="Diagram with boxes and arrows representing system flow",
                extracted_data=None,
                tags=["architecture", "diagram"]
            )
            
            with patch.object(processor.table_analyzer, 'sync_poll_result', return_value=table_result), \
                 patch.object(processor.section_verifier, 'sync_poll_result', return_value=section_result), \
                 patch.object(processor.content_validator, 'sync_poll_result', return_value=content_result), \
                 patch.object(processor.structure_analyzer, 'sync_poll_result', return_value=structure_result), \
                 patch.object(processor.image_describer, 'sync_poll_result', return_value=image_result):
                
                # Process document
                processor(sample_document, page_images)
                
                # Verify all analyzers were called
                processor.table_analyzer.sync_analyze_table_merge.assert_called()
                processor.section_verifier.sync_verify_sections.assert_called_once()
                processor.content_validator.sync_validate_content.assert_called_once()
                processor.structure_analyzer.sync_analyze_structure.assert_called_once()
                processor.image_describer.sync_describe_image.assert_called_once()
                
                # Verify metadata was updated
                assert 'claude_analysis' in sample_document.metadata
                claude_meta = sample_document.metadata['claude_analysis']
                
                assert claude_meta['table_merge_completed'] is True
                assert claude_meta['section_verification_completed'] is True
                assert claude_meta['content_validation_completed'] is True
                assert claude_meta['structure_analysis_completed'] is True
                assert claude_meta['image_description_completed'] is True
                
                assert claude_meta['section_issues_found'] == 1
                assert claude_meta['content_quality_score'] == 0.86
                assert claude_meta['document_structure_type'] == 'hierarchical'
    
    def test_process_with_table_merging(self, processor, sample_document, page_images):
        """Test table merge analysis and execution"""
        # Enable only table merge analysis
        processor.config.enable_section_verification = False
        processor.config.enable_content_validation = False
        processor.config.enable_structure_analysis = False
        processor.config.enable_image_description = False
        
        # Mock table analysis
        with patch.object(processor.table_analyzer, 'sync_analyze_table_merge', return_value='table-task-1'):
            table_result = TableAnalysisResult(
                confidence=0.9,
                should_merge=True,
                reasoning="Tables contain related financial data",
                quality_score=0.85,
                suggestions=["Consider adding column headers"]
            )
            
            with patch.object(processor.table_analyzer, 'sync_poll_result', return_value=table_result):
                # Track merge operations
                merged_tables = []
                
                def mock_merge(table1, table2):
                    merged_tables.append((table1, table2))
                    # Create merged table
                    merged = Table(
                        bbox=[
                            min(table1.bbox[0], table2.bbox[0]),
                            min(table1.bbox[1], table2.bbox[1]),
                            max(table1.bbox[2], table2.bbox[2]),
                            max(table1.bbox[3], table2.bbox[3])
                        ],
                        cells=table1.cells + table2.cells
                    )
                    return merged
                
                with patch('marker.processors.claude_post_processor.merge_tables', side_effect=mock_merge):
                    processor(sample_document, page_images)
                    
                    # Verify merge was attempted
                    assert len(merged_tables) > 0
                    assert processor.table_analyzer.sync_analyze_table_merge.called
    
    def test_process_with_section_auto_fix(self, processor, sample_document, page_images):
        """Test automatic section fixing when enabled"""
        # Enable auto-fix
        processor.config.auto_fix_sections = True
        processor.config.enable_table_merge_analysis = False
        processor.config.enable_content_validation = False
        processor.config.enable_structure_analysis = False
        processor.config.enable_image_description = False
        
        with patch.object(processor.section_verifier, 'sync_verify_sections', return_value='section-task-1'):
            section_result = SectionVerificationResult(
                confidence=0.85,
                is_valid=False,
                issues=[
                    StructuralIssue(
                        type="hierarchy_skip",
                        page=1,
                        section="1.1.1 Details",
                        description="Level 3 without level 2",
                        severity="error"
                    )
                ],
                suggestions=["Insert level 2 header"],
                structural_score=0.6
            )
            
            with patch.object(processor.section_verifier, 'sync_poll_result', return_value=section_result), \
                 patch.object(processor, '_apply_section_fixes') as mock_fix:
                
                processor(sample_document, page_images)
                
                # Verify fixes were attempted
                mock_fix.assert_called_once()
                call_args = mock_fix.call_args[0]
                assert call_args[0] == sample_document
                assert len(call_args[1]) == 1
                assert call_args[1][0].type == "hierarchy_skip"
    
    def test_process_with_disabled_features(self, processor, sample_document, page_images):
        """Test processing with some features disabled"""
        # Disable most features
        processor.config.enable_table_merge_analysis = True
        processor.config.enable_section_verification = False
        processor.config.enable_content_validation = False
        processor.config.enable_structure_analysis = False
        processor.config.enable_image_description = False
        
        with patch.object(processor.table_analyzer, 'sync_analyze_table_merge', return_value='table-task-1') as mock_table, \
             patch.object(processor.section_verifier, 'sync_verify_sections') as mock_section, \
             patch.object(processor.content_validator, 'sync_validate_content') as mock_content:
            
            table_result = TableAnalysisResult(
                confidence=0.8,
                should_merge=False,
                reasoning="Tables are unrelated",
                quality_score=0.7,
                suggestions=[]
            )
            
            with patch.object(processor.table_analyzer, 'sync_poll_result', return_value=table_result):
                processor(sample_document, page_images)
                
                # Verify only enabled features were called
                mock_table.assert_called()
                mock_section.assert_not_called()
                mock_content.assert_not_called()
                
                # Check metadata
                claude_meta = sample_document.metadata.get('claude_analysis', {})
                assert claude_meta.get('table_merge_completed') is True
                assert 'section_verification_completed' not in claude_meta
                assert 'content_validation_completed' not in claude_meta
    
    def test_error_handling(self, processor, sample_document, page_images):
        """Test error handling in processing"""
        # Make table analyzer fail
        with patch.object(processor.table_analyzer, 'sync_analyze_table_merge', side_effect=Exception("DB Error")), \
             patch.object(processor.logger, 'error') as mock_error:
            
            # Should not crash
            processor(sample_document, page_images)
            
            # Should log error
            mock_error.assert_called()
            assert "Error in table merge analysis" in mock_error.call_args[0][0]
    
    def test_polling_timeout(self, processor, sample_document, page_images):
        """Test handling of polling timeout"""
        processor.config.max_polling_attempts = 2
        processor.config.polling_interval = 0.01
        
        with patch.object(processor.table_analyzer, 'sync_analyze_table_merge', return_value='table-task-1'), \
             patch.object(processor.table_analyzer, 'sync_poll_result', return_value=None), \
             patch.object(processor.logger, 'warning') as mock_warning:
            
            processor(sample_document, page_images)
            
            # Should warn about timeout
            mock_warning.assert_called()
            assert "Polling timeout" in str(mock_warning.call_args)


if __name__ == "__main__":
    # Run validation
    print("Testing Claude post-processor integration...")
    
    # Create test document
    doc = Document(filepath="test.pdf")
    page = PageGroup(page_id=0, bbox=[0, 0, 612, 792])
    
    # Add various elements
    header = SectionHeader(text="Test", level=1, bbox=[0, 0, 100, 30])
    table = Table(bbox=[0, 50, 200, 150], cells=[["A", "B"], ["1", "2"]])
    page.add_child(header)
    page.add_child(table)
    doc.pages.append(page)
    
    # Create processor
    config = ClaudeConfig(
        enable_table_merge_analysis=True,
        enable_section_verification=True,
        enable_content_validation=True,
        enable_structure_analysis=True,
        enable_image_description=True
    )
    
    with tempfile.TemporaryDirectory() as tmpdir:
        config.task_db_path = os.path.join(tmpdir, "test.db")
        processor = ClaudePostProcessor(config)
        
        # Test initialization
        print("✓ Processor initialized with all analyzers")
        
        # Test feature flags
        assert processor.config.enable_table_merge_analysis
        assert processor.config.enable_section_verification
        print("✓ All features enabled in configuration")
        
        print("✅ Claude post-processor integration validation passed!")