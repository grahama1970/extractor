"""
Module: enhanced_code.py
Description: Enhanced Code Processor that stores tree-sitter metadata
"""

from typing import Optional
from extractor.core.processors.code import CodeProcessor as BaseCodeProcessor
from extractor.core.services.utils.tree_sitter_utils import extract_code_metadata, get_supported_language
from extractor.core.schema.blocks import Code
import logging

logger = logging.getLogger(__name__)


class EnhancedCodeProcessor(BaseCodeProcessor):
    """
    Enhanced processor that extracts and stores tree-sitter metadata.
    
    In addition to language detection, this processor:
    1. Extracts function/class metadata using tree-sitter
    2. Stores parameters, types, docstrings on the code block
    3. Makes code structure available for downstream processing
    """
    
    # Configuration
    extract_metadata = True  # Whether to extract and store metadata
    
    def detect_language(self, block: Code) -> Optional[str]:
        """
        Detect language and extract metadata if enabled.
        """
        # First detect language using parent method
        detected_language = super().detect_language(block)
        
        # If metadata extraction is enabled and we have a language
        if self.extract_metadata and detected_language and detected_language != self.fallback_language:
            try:
                # Extract metadata using tree-sitter
                metadata = extract_code_metadata(block.code, detected_language)
                
                if metadata.get('tree_sitter_success'):
                    # Store the metadata on the block if it has the field
                    if hasattr(block, 'tree_sitter_metadata'):
                        block.tree_sitter_metadata = metadata
                        logger.debug(
                            f"Stored tree-sitter metadata: "
                            f"{len(metadata.get('functions', []))} functions, "
                            f"{len(metadata.get('classes', []))} classes"
                        )
                    else:
                        logger.debug("Block doesn't support tree_sitter_metadata field")
                        
            except Exception as e:
                logger.warning(f"Failed to extract tree-sitter metadata: {e}")
        
        return detected_language
    
    def __call__(self, document):
        """Process document and extract metadata for all code blocks"""
        super().__call__(document)
        
        # Log summary of metadata extraction
        metadata_count = 0
        function_count = 0
        
        for page in document.pages:
            for block in page.contained_blocks(document, self.block_types):
                if hasattr(block, 'tree_sitter_metadata') and block.tree_sitter_metadata:
                    metadata_count += 1
                    functions = block.tree_sitter_metadata.get('functions', [])
                    function_count += len(functions)
        
        if metadata_count > 0:
            logger.info(
                f"Extracted tree-sitter metadata for {metadata_count} code blocks "
                f"containing {function_count} functions"
            )