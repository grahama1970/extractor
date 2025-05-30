"""
Test module for the enhanced table processor.
"""

import pytest
from unittest.mock import Mock, patch

from marker.processors.enhanced_camelot import EnhancedTableProcessor
from marker.schema import BlockTypes


@pytest.mark.config({"page_range": [5], "use_enhanced_camelot": True, "use_table_merging": True})
def test_enhanced_table_processor_init(pdf_document, detection_model, recognition_model, table_rec_model):
    """Test that the enhanced table processor initializes correctly."""
    processor = EnhancedTableProcessor(detection_model, recognition_model, table_rec_model)
    assert processor.use_enhanced_camelot is True
    assert processor.use_table_merging is True
    assert hasattr(processor, "quality_evaluator")
    assert hasattr(processor, "table_merger")


@pytest.mark.config({"page_range": [5], "use_enhanced_camelot": True, "use_table_merging": False})
def test_enhanced_table_processor_without_merging(pdf_document, detection_model, recognition_model, table_rec_model):
    """Test that the enhanced table processor works without table merging."""
    processor = EnhancedTableProcessor(detection_model, recognition_model, table_rec_model)
    assert processor.use_enhanced_camelot is True
    assert processor.use_table_merging is False
    assert hasattr(processor, "quality_evaluator")
    assert not hasattr(processor, "table_merger")


@pytest.mark.config({"page_range": [5], "use_enhanced_camelot": False, "use_table_merging": False})
def test_enhanced_table_processor_without_enhanced_camelot(pdf_document, detection_model, recognition_model, table_rec_model):
    """Test that the enhanced table processor works without enhanced Camelot."""
    processor = EnhancedTableProcessor(detection_model, recognition_model, table_rec_model)
    assert processor.use_enhanced_camelot is False
    assert processor.use_table_merging is False
    assert not hasattr(processor, "quality_evaluator")
    assert not hasattr(processor, "table_merger")


@pytest.mark.config({"page_range": [5]})
@patch("marker.utils.table_merger.TableMerger.merge_document_tables")
def test_enhanced_table_processor_calls_merge_document_tables(
    mock_merge_document_tables, pdf_document, detection_model, recognition_model, table_rec_model
):
    """Test that the enhanced table processor calls merge_document_tables when table merging is enabled."""
    processor = EnhancedTableProcessor(
        detection_model, recognition_model, table_rec_model, 
        {"use_enhanced_camelot": True, "use_table_merging": True}
    )
    processor(pdf_document)
    mock_merge_document_tables.assert_called_once_with(pdf_document)


@pytest.mark.config({"page_range": [5]})
@patch("marker.processors.enhanced_camelot.processor.EnhancedTableProcessor._process_with_enhanced_camelot")
def test_enhanced_table_processor_calls_enhanced_camelot(
    mock_process_with_enhanced_camelot, pdf_document, detection_model, recognition_model, table_rec_model
):
    """Test that the enhanced table processor calls _process_with_enhanced_camelot when enhanced Camelot is enabled."""
    processor = EnhancedTableProcessor(
        detection_model, recognition_model, table_rec_model, 
        {"use_enhanced_camelot": True, "use_table_merging": True}
    )
    
    # Create a mock table to trigger fallback
    mock_fallback_tables = [{
        "page": Mock(),
        "block": Mock(),
        "page_idx": 0
    }]
    
    processor.process_with_camelot_fallback(pdf_document, pdf_document.filepath, mock_fallback_tables)
    mock_process_with_enhanced_camelot.assert_called_once_with(pdf_document, pdf_document.filepath, mock_fallback_tables)


@pytest.mark.config({"page_range": [5]})
@patch("marker.processors.table.TableProcessor.process_with_camelot_fallback")
def test_enhanced_table_processor_calls_parent_fallback(
    mock_parent_fallback, pdf_document, detection_model, recognition_model, table_rec_model
):
    """Test that the enhanced table processor calls parent fallback when enhanced Camelot is disabled."""
    processor = EnhancedTableProcessor(
        detection_model, recognition_model, table_rec_model, 
        {"use_enhanced_camelot": False, "use_table_merging": True}
    )
    
    # Create a mock table to trigger fallback
    mock_fallback_tables = [{
        "page": Mock(),
        "block": Mock(),
        "page_idx": 0
    }]
    
    processor.process_with_camelot_fallback(pdf_document, pdf_document.filepath, mock_fallback_tables)
    mock_parent_fallback.assert_called_once_with(pdf_document, pdf_document.filepath, mock_fallback_tables)