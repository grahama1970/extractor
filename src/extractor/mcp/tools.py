"""MCP Tools for Marker - Proper MCP server implementation.
Module: tools.py

This module provides the actual MCP tools as described in the README.
"""

import json
from typing import Dict, Any, Optional, List
from pathlib import Path

from extractor.core.mcp_server import MarkerMCPServer


class MarkerMCPTools:
    """MCP tools for Marker integration."""
    
    def __init__(self):
        self.server = MarkerMCPServer()
    
    async def convert_pdf(
        self,
        file_path: str,
        claude_config: Optional[str] = None,
        extraction_method: str = "marker",
        check_system_resources: bool = True
    ) -> Dict[str, Any]:
        """Convert PDF with optional Claude enhancements.
        
        Args:
            file_path: Path to PDF file
            claude_config: One of: minimal, tables_only, accuracy, research, disabled
            extraction_method: marker (full) or pymupdf4llm (fast text-only)
            check_system_resources: Check system resources for recommendations
            
        Returns:
            Conversion result with metadata
        """
        result = await self.server.convert_pdf_with_claude_intelligence(
            file_path=file_path,
            claude_config=claude_config,
            check_system_resources=check_system_resources,
            extraction_method=extraction_method
        )
        
        # Format for MCP response
        return {
            "success": "error" not in result,
            "file_path": result["file_path"],
            "extraction_method": result["extraction_method"],
            "claude_config_used": result["claude_config_used"],
            "warnings": result.get("warnings", []),
            "recommendations": result.get("recommendations", []),
            "performance_estimate": result.get("performance_estimate", {}),
            "conversion_result": result.get("conversion_result", {}),
            "error": result.get("error")
        }
    
    async def get_system_resources(self) -> Dict[str, Any]:
        """Check system resources for Claude feature recommendations.
        
        Returns:
            System resource information and Claude availability
        """
        return await self.server.get_system_resources_for_agent()
    
    async def validate_claude_config(
        self,
        config_name: str
    ) -> Dict[str, Any]:
        """Validate Claude configuration and get performance estimates.
        
        Args:
            config_name: Configuration name to validate
            
        Returns:
            Validation results and performance estimates
        """
        return await self.server.validate_claude_config_for_agent(config_name)
    
    async def recommend_extraction_strategy(
        self,
        speed_priority: str = "normal",
        accuracy_priority: str = "normal", 
        content_types: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Get intelligent recommendations based on speed/accuracy requirements.
        
        Args:
            speed_priority: fastest, fast, normal, slow
            accuracy_priority: basic, normal, high, research
            content_types: List of content types needed (text, tables, images, equations)
            
        Returns:
            Recommended extraction method and Claude configuration
        """
        if content_types is None:
            content_types = ["text"]
            
        requirements = {
            "speed_priority": speed_priority,
            "accuracy_priority": accuracy_priority,
            "content_types": content_types
        }
        
        return await self.server.recommend_extraction_strategy(requirements)


# MCP tool definitions for registration
MCP_TOOLS = {
    "convert_pdf": {
        "description": "Convert PDF with optional Claude enhancements",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to PDF file"
                },
                "claude_config": {
                    "type": "string",
                    "enum": ["minimal", "tables_only", "accuracy", "research", "disabled"],
                    "description": "Claude configuration preset"
                },
                "extraction_method": {
                    "type": "string", 
                    "enum": ["marker", "pymupdf4llm"],
                    "description": "Extraction method - marker (full) or pymupdf4llm (fast text)"
                },
                "check_system_resources": {
                    "type": "boolean",
                    "description": "Check system resources for recommendations"
                }
            },
            "required": ["file_path"]
        }
    },
    "get_system_resources": {
        "description": "Check system resources for Claude feature recommendations",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    "validate_claude_config": {
        "description": "Validate Claude configuration and get performance estimates",
        "parameters": {
            "type": "object",
            "properties": {
                "config_name": {
                    "type": "string",
                    "description": "Configuration name to validate"
                }
            },
            "required": ["config_name"]
        }
    },
    "recommend_extraction_strategy": {
        "description": "Get intelligent recommendations based on speed/accuracy requirements",
        "parameters": {
            "type": "object",
            "properties": {
                "speed_priority": {
                    "type": "string",
                    "enum": ["fastest", "fast", "normal", "slow"],
                    "description": "Speed priority level"
                },
                "accuracy_priority": {
                    "type": "string",
                    "enum": ["basic", "normal", "high", "research"], 
                    "description": "Accuracy priority level"
                },
                "content_types": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["text", "tables", "images", "equations"]
                    },
                    "description": "Content types needed from document"
                }
            }
        }
    }
}


async def main():
    """Example usage of MCP tools."""
    tools = MarkerMCPTools()
    
    # Example 1: Speed priority
    print("=== Example 1: Speed Priority ===")
    resources = await tools.get_system_resources()
    print(f"System: {resources['cpu']['count']} CPUs, {resources['memory']['available_gb']}GB free RAM")
    
    strategy = await tools.recommend_extraction_strategy(
        speed_priority="fastest",
        accuracy_priority="basic",
        content_types=["text"]
    )
    print(f"Recommendation: {strategy['extraction_method']} with {strategy['claude_config']}")
    
    # Example 2: Research quality
    print("\n=== Example 2: Research Quality ===")
    strategy = await tools.recommend_extraction_strategy(
        speed_priority="normal",
        accuracy_priority="research", 
        content_types=["text", "tables", "equations"]
    )
    print(f"Recommendation: {strategy['extraction_method']} with {strategy['claude_config']}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())