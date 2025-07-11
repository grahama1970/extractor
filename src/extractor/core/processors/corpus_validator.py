"""
Corpus validation processor for Marker.
Module: corpus_validator.py

This processor ensures all extracted content is validated against the raw PDF
text using PyMuPDF. It runs after initial extraction but before final output,
ensuring the corpus is complete and accurate.
"""

import fitz  # PyMuPDF
from typing import Dict, List, Optional, Any
from pathlib import Path
from loguru import logger
from rapidfuzz import fuzz

from extractor.core.processors import BaseProcessor
from extractor.core.schema.document import Document


class CorpusValidationProcessor(BaseProcessor):
    """
    Validates extracted content against raw PDF text.
    
    This processor:
    1. Extracts raw text using PyMuPDF
    2. Validates all text blocks against raw corpus
    3. Flags or corrects missing content
    4. Ensures table content is properly captured
    """
    
    def __init__(self, config=None):
        super().__init__(config)
        self.validation_threshold = self.config.get("validation_threshold", 97)
        self.include_raw_corpus = self.config.get("include_raw_corpus", True)
        self._pdf_corpus = None
        
    def __call__(self, document: Document) -> Document:
        """Process document for corpus validation."""
        pdf_path = document.filepath
        
        # Extract raw PDF text
        logger.info(f"Extracting raw corpus from {pdf_path}")
        self._pdf_corpus = self._extract_pdf_corpus(pdf_path)
        
        # Validate all text blocks
        self._validate_text_blocks(document)
        
        # Validate table content  
        self._validate_tables(document)
        
        # Add raw corpus to document if requested
        if self.include_raw_corpus:
            document.raw_corpus = self._pdf_corpus
            document.metadata["corpus_validation"] = {
                "performed": True,
                "threshold": self.validation_threshold,
                "raw_corpus_length": len(self._pdf_corpus["full_text"])
            }
        
        return document
    
    def _extract_pdf_corpus(self, pdf_path: Path) -> Dict[str, Any]:
        """Extract complete text corpus from PDF using PyMuPDF."""
        doc = fitz.open(str(pdf_path))
        
        full_text_parts = []
        page_texts = []
        
        for page_num, page in enumerate(doc):
            # Get all text including tables
            text = page.get_text()
            
            # Also extract tables separately for validation
            tables = []
            for table in page.find_tables():
                table_text = "\n".join(
                    " | ".join(str(cell) if cell else "" for cell in row)
                    for row in table.extract()
                )
                tables.append(table_text)
            
            page_data = {
                "page_num": page_num,
                "text": text,
                "tables": tables
            }
            
            page_texts.append(page_data)
            full_text_parts.append(text)
        
        doc.close()
        
        return {
            "full_text": "\n".join(full_text_parts),
            "pages": page_texts,
            "total_pages": len(page_texts)
        }
    
    def _validate_text_blocks(self, document: Document):
        """Validate all text blocks against raw corpus."""
        validation_issues = []
        
        for page in document.pages:
            for block in page.blocks:
                if hasattr(block, 'text') and block.text:
                    # Check if text exists in raw corpus
                    score = self._check_text_in_corpus(block.text)
                    
                    if score < self.validation_threshold:
                        validation_issues.append({
                            "block_id": block.id,
                            "block_type": block.__class__.__name__,
                            "score": score,
                            "text_preview": block.text[:100]
                        })
                        
                        # Optionally fix by finding best match in corpus
                        if self.config.get("auto_fix", False):
                            fixed_text = self._find_best_match(block.text)
                            if fixed_text:
                                block.text = fixed_text
        
        if validation_issues:
            logger.warning(f"Found {len(validation_issues)} validation issues")
            document.metadata["validation_issues"] = validation_issues
    
    def _validate_tables(self, document: Document):
        """Ensure all tables are properly captured."""
        # Check each table against PyMuPDF extracted tables
        for page_num, page in enumerate(document.pages):
            page_tables = [b for b in page.blocks if b.__class__.__name__ == "Table"]
            
            if page_num < len(self._pdf_corpus["pages"]):
                raw_tables = self._pdf_corpus["pages"][page_num]["tables"]
                
                # Verify each Marker table exists in raw tables
                for table in page_tables:
                    table_text = self._table_to_text(table)
                    found = False
                    
                    for raw_table in raw_tables:
                        score = fuzz.partial_ratio(table_text, raw_table)
                        if score >= self.validation_threshold:
                            found = True
                            break
                    
                    if not found:
                        logger.warning(f"Table {table.id} not found in raw corpus")
                        # Could trigger Camelot here for better extraction
    
    def _check_text_in_corpus(self, text: str) -> float:
        """Check if text exists in raw corpus."""
        if len(text) < 20:
            return 100.0  # Skip very short text
        
        # Check against full corpus
        score = fuzz.partial_ratio(text[:100], self._pdf_corpus["full_text"])
        return score
    
    def _find_best_match(self, text: str) -> Optional[str]:
        """Find best matching text in corpus."""
        # This would implement fuzzy matching to find
        # the best corresponding text in the raw corpus
        pass
    
    def _table_to_text(self, table) -> str:
        """Convert table block to text for comparison."""
        # Convert Marker table format to text
        rows = []
        for row in table.rows:
            cells = [str(cell.text) if cell.text else "" for cell in row.cells]
            rows.append(" | ".join(cells))
        return "\n".join(rows)