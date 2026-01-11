
import logging
import sys
import os
from pathlib import Path
import camelot

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def debug_camelot_extraction(pdf_path: str, page: str = '3'):
    """
    Debug Camelot extraction for a specific page.
    """
    logger.info(f"Extracting tables from {pdf_path} (Page {page})")
    
    # 1. Try Lattice (Default)
    logger.info("--- Attempt 1: Lattice ---")
    try:
        tables = camelot.read_pdf(pdf_path, pages=page, flavor='lattice')
        logger.info(f"Found {len(tables)} tables")
        for i, t in enumerate(tables):
            logger.info(f"Table {i} Shape: {t.df.shape}")
            logger.info(f"Table {i} Content:\\n{t.df.head()}")
            logger.info(f"Table {i} Parsing Report: {t.parsing_report}")
    except Exception as e:
        logger.error(f"Lattice failed: {e}")

    # 2. Try Stream
    logger.info("\\n--- Attempt 2: Stream ---")
    try:
        tables = camelot.read_pdf(pdf_path, pages=page, flavor='stream')
        logger.info(f"Found {len(tables)} tables")
        for i, t in enumerate(tables):
            logger.info(f"Table {i} Shape: {t.df.shape}")
            logger.info(f"Table {i} Content:\\n{t.df.head()}")
            logger.info(f"Table {i} Parsing Report: {t.parsing_report}")
    except Exception as e:
        logger.error(f"Stream failed: {e}")

if __name__ == "__main__":
    pdf_file = "data/input/pipeline/BHT_CV32A65X_with_requirements_noannots.pdf"
    if not os.path.exists(pdf_file):
        logger.error(f"File not found: {pdf_file}")
        sys.exit(1)
        
    # Page 3 contains specific tables (verified from previous browsing attempts/context)
    debug_camelot_extraction(pdf_file, page='3,4,5')
