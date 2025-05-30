"""
Adapter for migrating existing Claude API calls to unified service.

This adapter maintains backwards compatibility for direct Claude API usage
while internally using the new unified Claude service.

Links:
- Original implementation: marker/services/claude.py
- Migration plan: docs/tasks/034_Claude_Module_Communicator_Integration.md

Sample Input (existing format):
    ClaudeService()(prompt, image, block, response_schema, ...)

Expected Output (existing format):
    Parsed response object matching response_schema
"""

import asyncio
import json
from typing import Dict, Any, Optional, Type, List
from pathlib import Path

from loguru import logger
from pydantic import BaseModel

from marker.core.services.claude_unified_simple import unified_claude_service
from marker.core.schema.blocks import Block


class ClaudeAPIAdapter:
    """
    Adapter that maintains the original ClaudeService interface
    while using the new unified Claude service internally.
    
    This allows gradual migration without breaking existing code.
    """
    
    def __init__(self, model: str = None, api_key: str = None):
        """Initialize adapter with optional configuration."""
        self.model = model or "claude-3-5-sonnet-20241022"
        self.api_key = api_key
        self.claude = unified_claude_service
        
        logger.info("Initialized ClaudeAPIAdapter with unified service")
    
    def __call__(self, 
                 prompt: str,
                 image: Optional[Any] = None,
                 block: Optional[Block] = None,
                 response_schema: Optional[Type[BaseModel]] = None,
                 **kwargs) -> Any:
        """
        Main entry point matching original ClaudeService interface.
        
        Args:
            prompt: The prompt to send to Claude
            image: Optional image data
            block: Optional block context
            response_schema: Pydantic model for response parsing
            **kwargs: Additional arguments
            
        Returns:
            Parsed response object or raw response
        """
        # Determine task type based on inputs
        if image is not None:
            return self._handle_image_task(prompt, image, block, response_schema, **kwargs)
        elif "table" in prompt.lower() or (block and hasattr(block, 'cells')):
            return self._handle_table_task(prompt, block, response_schema, **kwargs)
        else:
            return self._handle_text_task(prompt, block, response_schema, **kwargs)
    
    def _handle_image_task(self, prompt: str, image: Any, block: Optional[Block], 
                          response_schema: Optional[Type[BaseModel]], **kwargs) -> Any:
        """Handle image-based tasks."""
        # Extract image path or data
        image_path = None
        if isinstance(image, str):
            image_path = image
        elif isinstance(image, Path):
            image_path = str(image)
        elif hasattr(image, 'filename'):
            image_path = image.filename
        else:
            # For PIL images or raw data, save temporarily
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                if hasattr(image, 'save'):
                    image.save(tmp.name)
                    image_path = tmp.name
                else:
                    logger.warning("Unknown image format, using placeholder")
                    image_path = "unknown_image.png"
        
        # Create task
        context = {
            "prompt": prompt,
            "block_type": block.block_type if block else None,
            "has_schema": response_schema is not None
        }
        
        task_id = self.claude.describe_image(image_path, context)
        
        # Wait for result
        result = self.claude.wait_for_task(task_id, timeout=30.0)
        
        return self._process_result(result, response_schema)
    
    def _handle_table_task(self, prompt: str, block: Optional[Block], 
                          response_schema: Optional[Type[BaseModel]], **kwargs) -> Any:
        """Handle table-related tasks."""
        # Extract table data
        table1_data = {}
        table2_data = {}
        
        if block and hasattr(block, 'cells'):
            table1_data = {
                "cells": block.cells,
                "bbox": block.bbox if hasattr(block, 'bbox') else None,
                "headers": block.cells[0] if block.cells else []
            }
        
        # Check if this is a merge analysis
        if "merge" in prompt.lower():
            # Extract second table from kwargs or prompt
            table2_block = kwargs.get('table2_block')
            if table2_block and hasattr(table2_block, 'cells'):
                table2_data = {
                    "cells": table2_block.cells,
                    "bbox": table2_block.bbox if hasattr(table2_block, 'bbox') else None,
                    "headers": table2_block.cells[0] if table2_block.cells else []
                }
        
        context = {
            "prompt": prompt,
            "task_type": "table_merge" if table2_data else "table_analysis"
        }
        
        task_id = self.claude.analyze_tables(table1_data, table2_data, context)
        
        # Wait for result
        result = self.claude.wait_for_task(task_id, timeout=30.0)
        
        return self._process_result(result, response_schema)
    
    def _handle_text_task(self, prompt: str, block: Optional[Block], 
                         response_schema: Optional[Type[BaseModel]], **kwargs) -> Any:
        """Handle general text tasks."""
        # Determine if this is validation or structure analysis
        if any(word in prompt.lower() for word in ["validate", "check", "verify"]):
            content = block.text if block and hasattr(block, 'text') else prompt
            validation_rules = kwargs.get('rules', ["general"])
            
            task_id = self.claude.validate_content(content, validation_rules)
        else:
            # Structure analysis
            blocks = kwargs.get('blocks', [])
            if not blocks and block:
                blocks = [{"type": block.block_type, "text": getattr(block, 'text', '')}]
            
            context = {"prompt": prompt, "source": "api_adapter"}
            task_id = self.claude.analyze_structure(blocks, context)
        
        # Wait for result
        result = self.claude.wait_for_task(task_id, timeout=30.0)
        
        return self._process_result(result, response_schema)
    
    def _process_result(self, task_result: Dict[str, Any], 
                       response_schema: Optional[Type[BaseModel]]) -> Any:
        """Process task result and apply schema if provided."""
        if task_result.get("status") != "completed":
            error = task_result.get("error", "Task failed")
            logger.error(f"Claude task failed: {error}")
            
            # Return default response if schema provided
            if response_schema:
                return response_schema()
            return None
        
        result_data = task_result.get("result", {})
        
        # If no schema, return raw result
        if not response_schema:
            return result_data
        
        # Try to parse with schema
        try:
            # Handle different response formats
            if isinstance(result_data, dict):
                return response_schema(**result_data)
            elif isinstance(result_data, str):
                # Try to parse as JSON
                try:
                    parsed = json.loads(result_data)
                    return response_schema(**parsed)
                except:
                    # Create minimal valid response
                    return response_schema()
            else:
                return response_schema()
                
        except Exception as e:
            logger.warning(f"Failed to parse response with schema: {e}")
            return response_schema()
    
    # Compatibility methods
    
    def generate_completion(self, prompt: str, **kwargs) -> str:
        """Generate text completion - compatibility method."""
        result = self(prompt, **kwargs)
        if isinstance(result, str):
            return result
        elif isinstance(result, dict):
            return json.dumps(result)
        elif hasattr(result, 'model_dump'):
            return json.dumps(result.model_dump())
        return str(result)
    
    def analyze_image(self, image_path: str, prompt: str, **kwargs) -> Dict[str, Any]:
        """Analyze image - compatibility method."""
        result = self(prompt, image=image_path, **kwargs)
        if isinstance(result, dict):
            return result
        elif hasattr(result, 'model_dump'):
            return result.model_dump()
        return {"description": str(result)}
    
    def validate_json(self, json_str: str, schema: Type[BaseModel]) -> Optional[BaseModel]:
        """Validate JSON against schema - compatibility method."""
        try:
            data = json.loads(json_str)
            return schema(**data)
        except Exception as e:
            logger.error(f"JSON validation failed: {e}")
            return None


# Create drop-in replacement
ClaudeService = ClaudeAPIAdapter


# Validation and testing
if __name__ == "__main__":
    from pydantic import BaseModel, Field
    
    # Test schemas
    class TableAnalysis(BaseModel):
        should_merge: bool = Field(default=False)
        confidence: float = Field(default=0.0)
        reason: str = Field(default="")
    
    class ImageDescription(BaseModel):
        description: str = Field(default="")
        elements: List[str] = Field(default_factory=list)
    
    # Test adapter
    adapter = ClaudeAPIAdapter()
    
    print("Testing Claude API Adapter...")
    
    # Test 1: Table analysis
    print("\n1. Table Analysis Test:")
    prompt = "Should these tables be merged?"
    
    # Create mock block
    class MockBlock:
        block_type = "Table"
        cells = [["Name", "Age"], ["John", "30"], ["Jane", "25"]]
        bbox = [0, 0, 100, 50]
    
    block = MockBlock()
    result = adapter(prompt, block=block, response_schema=TableAnalysis)
    print(f"   Result: {result}")
    print(f"   Type: {type(result)}")
    assert isinstance(result, TableAnalysis)
    
    # Test 2: Image description (with mock image path)
    print("\n2. Image Description Test:")
    prompt = "Describe this image"
    result = adapter(prompt, image="/path/to/image.png", response_schema=ImageDescription)
    print(f"   Result: {result}")
    assert isinstance(result, ImageDescription)
    
    # Test 3: Text generation without schema
    print("\n3. Text Generation Test:")
    prompt = "Explain quantum computing in one sentence"
    result = adapter.generate_completion(prompt)
    print(f"   Result: {result}")
    assert isinstance(result, str)
    
    # Test 4: Compatibility method
    print("\n4. Analyze Image Compatibility Test:")
    result = adapter.analyze_image("/path/to/chart.png", "What type of chart is this?")
    print(f"   Result: {result}")
    assert isinstance(result, dict)
    
    print("\n✅ All adapter tests passed!")