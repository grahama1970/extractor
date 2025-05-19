"""
Test script for the enhanced Camelot table processor.

This script directly tests the EnhancedTableProcessor on a sample PDF with tables.
"""

import os
import sys
import time
from pathlib import Path

from marker.models import create_model_dict
from marker.config.table import TableConfig, PRESET_HIGH_ACCURACY
from marker.processors.enhanced_camelot import EnhancedTableProcessor
from marker.processors.table import TableProcessor
from marker.schema import BlockTypes

def print_separator():
    print("-" * 80)

def main():
    # Parse command line arguments
    if len(sys.argv) > 1:
        fpath = sys.argv[1]
    else:
        # Use default test PDF
        fpath = "data/input/2505.03335v2.pdf"
    
    # Create models dictionary
    models = create_model_dict()
    
    # Create configuration with high accuracy preset
    config = {
        "table": PRESET_HIGH_ACCURACY.model_dump()
    }
    
    # Print test information
    print(f"Testing Enhanced Camelot Table Processor on {fpath}")
    print_separator()
    
    # Create the regular table processor (for comparison)
    standard_processor = TableProcessor(
        detection_model=models.get("detection_model"),
        recognition_model=models.get("recognition_model"),
        table_rec_model=models.get("table_rec_model")
    )
    
    # Create the enhanced table processor
    enhanced_processor = EnhancedTableProcessor(
        detection_model=models.get("detection_model"),
        recognition_model=models.get("recognition_model"),
        table_rec_model=models.get("table_rec_model"),
        config=config
    )
    
    # Print processor configurations
    print("Standard Table Processor Configuration:")
    for attr in dir(standard_processor):
        if attr.startswith('_') or callable(getattr(standard_processor, attr)):
            continue
        print(f"  {attr}: {getattr(standard_processor, attr)}")
    
    print_separator()
    print("Enhanced Table Processor Configuration:")
    for attr in dir(enhanced_processor):
        if attr.startswith('_') or callable(getattr(enhanced_processor, attr)):
            continue
        print(f"  {attr}: {getattr(enhanced_processor, attr)}")
    
    print_separator()
    print("Table Config from Enhanced Processor:")
    if hasattr(enhanced_processor, 'table_config'):
        for key, value in enhanced_processor.table_config.model_dump().items():
            if isinstance(value, dict):
                print(f"  {key}:")
                for subkey, subvalue in value.items():
                    print(f"    {subkey}: {subvalue}")
            else:
                print(f"  {key}: {value}")
    
    print_separator()
    print("Test Completed")

if __name__ == "__main__":
    main()