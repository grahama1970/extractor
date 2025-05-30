"""Enhanced Code block with tree-sitter metadata support"""

from typing import Optional, Dict, Any
from marker.core.schema.blocks.code import Code as BaseCode
from pydantic import Field


class EnhancedCode(BaseCode):
    """Code block that stores tree-sitter metadata for better code understanding"""
    
    # Add field for tree-sitter metadata
    tree_sitter_metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Extracted metadata from tree-sitter including functions, classes, parameters, etc."
    )
    
    def get_functions(self) -> list:
        """Get list of functions extracted by tree-sitter"""
        if not self.tree_sitter_metadata:
            return []
        return self.tree_sitter_metadata.get('functions', [])
    
    def get_classes(self) -> list:
        """Get list of classes extracted by tree-sitter"""
        if not self.tree_sitter_metadata:
            return []
        return self.tree_sitter_metadata.get('classes', [])
    
    def get_all_parameters(self) -> list:
        """Get all parameters from all functions"""
        parameters = []
        for func in self.get_functions():
            parameters.extend(func.get('parameters', []))
        return parameters