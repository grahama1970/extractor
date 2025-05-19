"""
Enhanced table processor with improved Camelot fallback for table extraction.

This module provides an enhanced TableProcessor that uses advanced quality evaluation,
parameter optimization, and table merging for improved table extraction. It handles
complex tables and tables that span multiple pages, producing higher-quality output.

References:
- Camelot documentation: https://camelot-py.readthedocs.io/en/master/
- pandas documentation: https://pandas.pydata.org/docs/

Sample input:
- Document object containing tables
- PDF filepath for extraction

Expected output:
- Document with accurately extracted tables, including those that required Camelot fallback
- Properly merged tables that span multiple pages
"""

import os
from typing import Annotated, Dict, List, Optional, Any
from loguru import logger

# Import camelot for heuristic table extraction fallback
try:
    import camelot
    import cv2
    CAMELOT_AVAILABLE = True
except ImportError:
    CAMELOT_AVAILABLE = False

from marker.processors.table import TableProcessor
from marker.schema import BlockTypes
from marker.schema.blocks.tablecell import TableCell
from marker.schema.document import Document
from marker.schema.polygon import PolygonBox
from marker.utils.table_quality_evaluator import TableQualityEvaluator
from marker.utils.table_merger import TableMerger
from marker.config.table import (
    TableConfig, 
    CamelotConfig,
    TableOptimizerConfig,
    TableQualityEvaluatorConfig,
    TableMergerConfig,
    PRESET_BALANCED
)


class EnhancedTableProcessor(TableProcessor):
    """
    Enhanced processor for table extraction with improved Camelot fallback and table merging.
    
    This processor extends the base TableProcessor with advanced quality evaluation,
    parameter optimization, and table merging for improved table extraction.
    """
    
    def __init__(self, detection_model, recognition_model, table_rec_model, config=None):
        """
        Initialize the EnhancedTableProcessor.
        
        Args:
            detection_model: The detection model for OCR
            recognition_model: The recognition model for OCR
            table_rec_model: The table recognition model
            config: Optional configuration dictionary
        """
        super().__init__(detection_model, recognition_model, table_rec_model, config)
        
        # Get the table configuration
        table_config = None
        if config and "table" in config:
            # If table config is provided as a dict, convert it to a TableConfig object
            if isinstance(config["table"], dict):
                from marker.config.table_parser import table_config_from_dict
                table_config = table_config_from_dict(config["table"])
            elif isinstance(config["table"], TableConfig):
                table_config = config["table"]
        
        # If no table config was provided or conversion failed, use the balanced preset
        if not table_config:
            table_config = PRESET_BALANCED
        
        # Store the configuration for later use
        self.table_config = table_config
        
        # Initialize quality evaluator if enabled
        if table_config.quality_evaluator.enabled and CAMELOT_AVAILABLE:
            evaluator_config = {
                'confidence_threshold': table_config.quality_evaluator.min_quality_score * 100,
                'max_search_iterations': table_config.optimizer.iterations if table_config.optimizer.enabled else 1,
                'metrics': table_config.quality_evaluator.evaluation_metrics,
                'weights': table_config.quality_evaluator.weights
            }
            self.quality_evaluator = TableQualityEvaluator(evaluator_config)
        
        # Initialize table merger if enabled
        if table_config.merger.enabled:
            merger_config = {
                'merge_thresholds': {
                    'table_height_threshold': table_config.merger.table_height_threshold,
                    'table_start_threshold': table_config.merger.table_start_threshold,
                    'vertical_table_height_threshold': table_config.merger.vertical_table_height_threshold,
                    'vertical_table_distance_threshold': table_config.merger.vertical_table_distance_threshold,
                    'horizontal_table_width_threshold': table_config.merger.horizontal_table_width_threshold,
                    'horizontal_table_distance_threshold': table_config.merger.horizontal_table_distance_threshold,
                    'column_gap_threshold': table_config.merger.column_gap_threshold,
                    'row_split_threshold': table_config.merger.row_split_threshold
                },
                'use_llm': table_config.merger.use_llm_for_merge_decisions
            }
            self.table_merger = TableMerger(merger_config)
    
    def __call__(self, document: Document):
        """
        Process the document to extract tables, with enhanced Camelot fallback if needed.
        
        Args:
            document: The document object to process
        """
        filepath = document.filepath
        
        # Call the parent method for basic table extraction
        super().__call__(document)
        
        # Post-process document for table merging if enabled
        if self.table_config.merger.enabled:
            self._merge_document_tables(document)
    
    def _merge_document_tables(self, document: Document):
        """
        Detect and merge tables in the document.
        
        Args:
            document: The document object
        """
        try:
            if self.table_config.merger.enabled:
                logger.info("Checking for tables to merge")
                self.table_merger.merge_document_tables(document)
                logger.info("Table merging complete")
        except Exception as e:
            logger.error(f"Error merging tables: {str(e)}")
    
    def process_with_camelot_fallback(self, document: Document, filepath: str, fallback_tables: List[dict]):
        """
        Process tables using enhanced Camelot fallback with quality evaluation and parameter optimization.
        
        Args:
            document: The document object
            filepath: Path to the original PDF file
            fallback_tables: List of tables that need fallback processing
        """
        if not CAMELOT_AVAILABLE or not fallback_tables:
            return
        
        # Use enhanced Camelot extraction if enabled and quality evaluator is available
        if self.table_config.quality_evaluator.enabled and hasattr(self, 'quality_evaluator'):
            self._process_with_enhanced_camelot(document, filepath, fallback_tables)
        else:
            super().process_with_camelot_fallback(document, filepath, fallback_tables)
    
    def _process_with_enhanced_camelot(self, document: Document, filepath: str, fallback_tables: List[dict]):
        """
        Process tables using enhanced Camelot extraction with quality evaluation and parameter optimization.
        
        Args:
            document: The document object
            filepath: Path to the original PDF file
            fallback_tables: List of tables that need fallback processing
        """
        try:
            # Track extracted tables for potential merging
            extracted_tables = []
            
            for table_info in fallback_tables:
                page = table_info["page"]
                block = table_info["block"]
                page_idx = table_info["page_idx"]
                
                # Camelot is 1-indexed for pages
                camelot_page_idx = page_idx + 1
                
                # Get the bbox coordinates in PDF coordinates
                bbox = block.polygon.bbox
                page_height = page.polygon.height
                page_width = page.polygon.width
                
                # Convert to Camelot format [left, top, right, bottom] in normalized coordinates
                camelot_bbox = [
                    bbox[0] / page_width,
                    (page_height - bbox[3]) / page_height,  # Flip Y coordinate (PDF origin is bottom-left)
                    bbox[2] / page_width,
                    (page_height - bbox[1]) / page_height,  # Flip Y coordinate
                ]
                
                # Use the quality evaluator to find the best parameters
                best_tables, best_params = self.quality_evaluator.find_best_table_extraction(
                    page_idx,
                    filepath,
                    camelot_bbox
                )
                
                # Process the extracted table if we found a good one
                if best_tables and len(best_tables) > 0 and not best_tables[0].df.empty:
                    # Calculate quality metrics for the best table
                    camelot_table = best_tables[0]
                    quality_metrics = self.quality_evaluator.calculate_table_quality([camelot_table])
                    avg_quality = quality_metrics.get('average_table_extraction_quality', 0.0)
                    
                    # Get the quality threshold from configuration
                    quality_threshold = self.table_config.quality_evaluator.min_quality_score * 100
                    
                    # Only use the table if it meets the quality threshold
                    if avg_quality * 100 >= quality_threshold:
                        logger.info(f"Using Camelot extraction with confidence {avg_quality * 100:.2f}% (threshold: {quality_threshold}%)")
                        self.camelot_table_to_cells(document, page, block, camelot_table)
                        
                        # Update metadata with extraction method and quality metrics
                        metadata = {
                            "extraction_method": "enhanced_camelot",
                            "extraction_params": best_params,
                            "quality_score": avg_quality * 100,
                            "config_preset": getattr(self.table_config, 'preset_name', 'custom')
                        }
                        block.update_metadata(**metadata)
                        
                        # Add to extracted tables for potential merging
                        extracted_tables.append({
                            "block_id": block.id,
                            "page": page_idx,
                            "bbox": bbox,
                            "table_data": camelot_table.df.to_dict('records'),
                            "quality_score": avg_quality * 100
                        })
                    else:
                        logger.warning(f"Camelot extraction quality ({avg_quality * 100:.2f}%) below threshold ({quality_threshold}%), skipping table")
                else:
                    logger.warning(f"No suitable Camelot extraction found for table on page {page_idx + 1}")
                
        except Exception as e:
            logger.error(f"Enhanced Camelot processing error: {str(e)}")
            
        # Check for tables to merge if we have multiple tables and merging is enabled
        if self.table_config.merger.enabled and len(extracted_tables) > 1:
            try:
                # Get page heights for the document
                page_heights = {
                    page.page_id: page.polygon.height
                    for page in document.pages
                }
                
                # Check for tables to merge
                merged_tables = self.table_merger.check_tables_for_merges(extracted_tables, page_heights)
                
                # Apply merges to the document if we found any
                if any(table.get('merged', False) for table in merged_tables):
                    logger.info("Found tables to merge from Camelot extraction")
                    self.table_merger._apply_merges_to_document(document, merged_tables)
                    
                    # Update metadata with merging information
                    for block in document.blocks:
                        if block.type == "table" and block.metadata.get("merged_from"):
                            block.update_metadata(
                                merger_config={
                                    "enabled": self.table_config.merger.enabled,
                                    "use_llm": self.table_config.merger.use_llm_for_merge_decisions
                                }
                            )
            except Exception as e:
                logger.error(f"Error checking for table merges: {str(e)}")


if __name__ == "__main__":
    """
    Validation function to test the EnhancedTableProcessor.
    
    This is a simplified validation that checks if the enhanced processor can be initialized
    and if the quality evaluation is working as expected.
    """
    import sys
    import json
    from unittest.mock import MagicMock
    
    # List to track all validation failures
    all_validation_failures = []
    total_tests = 0
    
    # Test 1: Initialization with default config
    total_tests += 1
    try:
        # Create mock objects for the required models
        mock_detection_model = MagicMock()
        mock_recognition_model = MagicMock()
        mock_table_rec_model = MagicMock()
        
        # Initialize the enhanced processor
        processor = EnhancedTableProcessor(
            mock_detection_model,
            mock_recognition_model,
            mock_table_rec_model
        )
        
        # Check that the processor was initialized correctly with default config
        if not hasattr(processor, "table_config"):
            all_validation_failures.append("table_config not initialized")
        
        # Check that the balanced preset was used as default
        if processor.table_config != PRESET_BALANCED:
            all_validation_failures.append(f"Default config is not PRESET_BALANCED")
        
        # Check that the quality evaluator was initialized if Camelot is available
        if not hasattr(processor, "quality_evaluator") and CAMELOT_AVAILABLE:
            all_validation_failures.append("quality_evaluator not initialized")
            
    except Exception as e:
        all_validation_failures.append(f"Error in default initialization test: {str(e)}")
    
    # Test 2: Initialization with custom config
    total_tests += 1
    try:
        # Create a custom config
        custom_config = {
            "table": {
                "enabled": True,
                "use_llm": True,
                "camelot": {
                    "enabled": True,
                    "flavor": "stream"
                },
                "optimizer": {
                    "enabled": True,
                    "iterations": 3
                },
                "quality_evaluator": {
                    "enabled": True,
                    "min_quality_score": 0.8
                },
                "merger": {
                    "enabled": True,
                    "use_llm_for_merge_decisions": False
                }
            }
        }
        
        # Initialize with custom config
        processor_custom = EnhancedTableProcessor(
            mock_detection_model,
            mock_recognition_model,
            mock_table_rec_model,
            custom_config
        )
        
        # Check that custom config was properly loaded
        if not processor_custom.table_config.use_llm:
            all_validation_failures.append("Custom config use_llm not set correctly")
        
        if processor_custom.table_config.quality_evaluator.min_quality_score != 0.8:
            all_validation_failures.append(f"Custom config quality threshold not set correctly: {processor_custom.table_config.quality_evaluator.min_quality_score}")
            
        if processor_custom.table_config.merger.use_llm_for_merge_decisions != False:
            all_validation_failures.append("Custom config merger llm setting not set correctly")
            
    except Exception as e:
        all_validation_failures.append(f"Error in custom config initialization test: {str(e)}")
    
    # Test 3: Mock table extraction with configuration
    total_tests += 1
    try:
        if CAMELOT_AVAILABLE:
            # Mock the quality evaluator
            processor.quality_evaluator = MagicMock()
            processor.quality_evaluator.find_best_table_extraction.return_value = (
                [MagicMock(df=MagicMock(empty=False))],  # Mock tables
                {"flavor": "lattice", "line_scale": 15}   # Mock parameters
            )
            
            # Mock calculate_table_quality
            processor.quality_evaluator.calculate_table_quality.return_value = {
                "average_table_extraction_quality": 0.85,
                "table_scores": [{"table_index": 0, "weighted_score": 0.85}]
            }
            
            # Mock the document and other objects
            mock_document = MagicMock()
            mock_filepath = "/path/to/mock.pdf"
            mock_page = MagicMock()
            mock_page.polygon.height = 1000
            mock_page.polygon.width = 800
            
            mock_block = MagicMock()
            mock_block.polygon.bbox = [100, 200, 300, 400]
            mock_block.update_metadata = MagicMock()
            
            mock_fallback_tables = [{
                "page": mock_page,
                "block": mock_block,
                "page_idx": 0
            }]
            
            # Mock the camelot_table_to_cells method
            processor.camelot_table_to_cells = MagicMock()
            
            # Set a custom quality threshold for testing
            processor.table_config.quality_evaluator.min_quality_score = 0.80
            
            # Test the enhanced Camelot fallback
            processor._process_with_enhanced_camelot(mock_document, mock_filepath, mock_fallback_tables)
            
            # Check that the quality evaluator was called
            if not processor.quality_evaluator.find_best_table_extraction.called:
                all_validation_failures.append("find_best_table_extraction was not called")
                
            # Check that the table was processed
            if not processor.camelot_table_to_cells.called:
                all_validation_failures.append("camelot_table_to_cells was not called")
                
            # Check that the correct threshold was used
            metadata_calls = mock_block.update_metadata.call_args_list
            if not any("extraction_method" in call[1] and call[1]["extraction_method"] == "enhanced_camelot" for call in metadata_calls):
                all_validation_failures.append("Block metadata not updated correctly")
        else:
            print("Camelot not available, skipping test 3")
            
    except Exception as e:
        all_validation_failures.append(f"Error in mock table extraction test: {str(e)}")
    
    # Test 4: Configuration serialization
    total_tests += 1
    try:
        # Serialize the configuration
        config_json = json.dumps(processor.table_config.model_dump())
        
        # Check that it can be serialized and deserialized
        if not config_json:
            all_validation_failures.append("Failed to serialize table_config")
            
        # Deserialize the configuration
        config_dict = json.loads(config_json)
        
        # Check that key fields are preserved
        if "quality_evaluator" not in config_dict:
            all_validation_failures.append("quality_evaluator not found in serialized config")
            
        if "merger" not in config_dict:
            all_validation_failures.append("merger not found in serialized config")
            
    except Exception as e:
        all_validation_failures.append(f"Error in configuration serialization test: {str(e)}")
    
    # Final validation result
    if all_validation_failures:
        print(f"❌ VALIDATION FAILED - {len(all_validation_failures)} of {total_tests} tests failed:")
        for failure in all_validation_failures:
            print(f"  - {failure}")
        sys.exit(1)
    else:
        print(f"✅ VALIDATION PASSED - All {total_tests} tests produced expected results")
        print("EnhancedTableProcessor is validated and formal tests can now be written")
        sys.exit(0)