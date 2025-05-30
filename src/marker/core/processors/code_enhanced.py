"""Enhanced CodeProcessor that stores tree-sitter metadata in the existing metadata field"""

from marker.core.processors.code import CodeProcessor
from marker.core.schema import BlockTypes
from marker.core.schema.blocks import Code
from marker.core.schema.document import Document
from marker.core.services.utils.tree_sitter_utils import extract_code_metadata, get_supported_language
from marker.core.schema.blocks.base import BlockMetadata
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


# Extend BlockMetadata to include tree-sitter data
class CodeBlockMetadata(BlockMetadata):
    """Extended metadata that includes tree-sitter extraction"""
    tree_sitter_data: Optional[Dict[str, Any]] = None


class EnhancedCodeProcessor(CodeProcessor):
    """
    Enhanced processor that stores tree-sitter metadata.
    
    Extends the base CodeProcessor to:
    1. Extract function/class metadata using tree-sitter
    2. Store it in the block's metadata field
    3. Make code structure available for downstream use
    """
    
    # Configuration
    extract_tree_sitter_metadata = True
    
    def detect_language(self, block: Code) -> Optional[str]:
        """
        Detect language and extract tree-sitter metadata.
        
        This method extends the parent to also extract and store
        function/class/parameter information from tree-sitter.
        """
        # First detect language using parent method
        detected_language = super().detect_language(block)
        
        # Extract and store metadata if enabled
        if (self.extract_tree_sitter_metadata and 
            detected_language and 
            detected_language != self.fallback_language and
            block.code):
            
            try:
                # Extract metadata using tree-sitter
                ts_metadata = extract_code_metadata(block.code, detected_language)
                
                if ts_metadata.get('tree_sitter_success'):
                    # Create or update metadata
                    if not block.metadata:
                        block.metadata = CodeBlockMetadata(tree_sitter_data=ts_metadata)
                    else:
                        # Store in existing metadata
                        if hasattr(block.metadata, 'tree_sitter_data'):
                            block.metadata.tree_sitter_data = ts_metadata
                        else:
                            # Fallback: store as dict in metadata
                            block.metadata = BlockMetadata(
                                llm_request_count=block.metadata.llm_request_count,
                                llm_error_count=block.metadata.llm_error_count,
                                llm_tokens_used=block.metadata.llm_tokens_used,
                                tree_sitter_data=ts_metadata  # This will be in extra fields
                            )
                    
                    # Log what we extracted
                    functions = ts_metadata.get('functions', [])
                    classes = ts_metadata.get('classes', [])
                    
                    logger.debug(
                        f"Extracted tree-sitter metadata for {detected_language}: "
                        f"{len(functions)} functions, {len(classes)} classes"
                    )
                    
                    # Log first function as example
                    if functions:
                        func = functions[0]
                        logger.debug(
                            f"Example function: {func.get('name', 'unnamed')} "
                            f"with {len(func.get('parameters', []))} parameters"
                        )
                        
            except Exception as e:
                logger.warning(f"Failed to extract tree-sitter metadata: {e}")
        
        return detected_language
    
    def __call__(self, document: Document):
        """Process document and report metadata extraction summary"""
        # Process all code blocks
        super().__call__(document)
        
        # Report what we extracted
        metadata_count = 0
        total_functions = 0
        total_classes = 0
        
        for page in document.pages:
            for block in page.contained_blocks(document, self.block_types):
                if block.metadata and hasattr(block.metadata, 'tree_sitter_data'):
                    ts_data = block.metadata.tree_sitter_data
                    if ts_data and ts_data.get('tree_sitter_success'):
                        metadata_count += 1
                        total_functions += len(ts_data.get('functions', []))
                        total_classes += len(ts_data.get('classes', []))
        
        if metadata_count > 0:
            logger.info(
                f"Extracted tree-sitter metadata for {metadata_count} code blocks: "
                f"{total_functions} functions, {total_classes} classes"
            )