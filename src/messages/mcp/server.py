"""
marker FastMCP Server
Module: server.py
Description: Functions for server operations

Granger standard MCP server implementation for marker.
"""

from fastmcp import FastMCP
from .messages_prompts import register_all_prompts
from .prompts import get_prompt_registry

# Initialize server
mcp = FastMCP("marker")
mcp.description = "marker - Granger spoke module"

# Register prompts
register_all_prompts()
prompt_registry = get_prompt_registry()


# =============================================================================
# PROMPTS - Required for Granger standard
# =============================================================================

@mcp.prompt()
async def capabilities() -> str:
    """List all MCP server capabilities"""
    return await prompt_registry.execute("marker:capabilities")


@mcp.prompt()
async def help(context: str = None) -> str:
    """Get context-aware help"""
    return await prompt_registry.execute("marker:help", context=context)


@mcp.prompt()
async def quick_start() -> str:
    """Quick start guide for new users"""
    return await prompt_registry.execute("marker:quick-start")


# =============================================================================
# TOOLS - Add your existing tools here
# =============================================================================

# TODO: Migrate existing tools from your current implementation
# Example:
# @mcp.tool()
# async def your_tool(param: str) -> dict:
#     """Tool description"""
#     return {"success": True, "result": param}


# =============================================================================
# SERVER
# =============================================================================

def serve():
    """Start the MCP server"""
    mcp.run(transport="stdio")  # Use stdio for Claude Code


if __name__ == "__main__":
    # Quick validation
    import asyncio
    
    async def validate():
        result = await capabilities()
        assert "marker" in result.lower()
        print(" Server validation passed")
    
    asyncio.run(validate())
    
    # Start server
    serve()
