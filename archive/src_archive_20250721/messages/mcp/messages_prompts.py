"""
Module: messages_prompts.py
Description: Model Context Protocol (MCP) integration

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

from typing import Dict, Any, List, Optional
from ..mcp.prompts import mcp_prompt, format_prompt_response, get_prompt_registry

# Replace 'messages' with your project name throughout this file
PROJECT_NAME = "messages"
PROJECT_DESCRIPTION = "marker - Intelligent automation for the Granger ecosystem"


# =============================================================================
# REQUIRED PROMPTS - Every spoke must implement these
# =============================================================================

@mcp_prompt(
    name=f"{PROJECT_NAME}:capabilities",
    description="List all available MCP server capabilities including prompts, tools, and resources",
    category="discovery",
    next_steps=[
        f"Use /{PROJECT_NAME}:quick-start to get started",
        f"Use /{PROJECT_NAME}:help for detailed assistance"
    ]
)
async def list_capabilities(registry: Any = None) -> str:
    """List all available capabilities of this MCP server"""
    
    if registry is None:
        registry = get_prompt_registry()
    
    categories = registry.get_categories()
    
    content = f"""# {PROJECT_NAME.title()} MCP Server Capabilities

{PROJECT_DESCRIPTION}

## Quick Start Workflow

1. **Discover**: Use `/{PROJECT_NAME}:capabilities` (you are here!)
2. **Explore**: Use `/{PROJECT_NAME}:quick-start` for guided introduction
3. **Execute**: Use domain-specific prompts for your tasks
4. **Help**: Use `/{PROJECT_NAME}:help` anytime for assistance

## Available Prompts
"""
    
    # Add prompts by category
    for category, prompt_names in categories.items():
        if prompt_names:
            content += f"\n### {category.title()} Prompts\n"
            for name in prompt_names:
                prompt = registry.get(name)
                if prompt and name.startswith(PROJECT_NAME):
                    content += f"- `/{name}` - {prompt.description}\n"
    
    # Add tools section
    content += f"""
## Core Tools

- `tool_one` - Description of tool one
- `tool_two` - Description of tool two
- [Add your actual tools here]

## Key Features

- [Feature 1]: Brief description
- [Feature 2]: Brief description
- [Feature 3]: Brief description
"""
    
    suggestions = {
        f"/{PROJECT_NAME}:quick-start": "Get started with guided tutorial",
        f"/{PROJECT_NAME}:help": "Get detailed help"
    }
    
    return format_prompt_response(
        content=content,
        suggestions=suggestions
    )


@mcp_prompt(
    name=f"{PROJECT_NAME}:help",
    description="Get context-aware help based on your current task",
    category="help",
    parameters={
        "context": {"type": "string", "description": "What you're trying to do"}
    }
)
async def get_help(context: Optional[str] = None) -> str:
    """Provide context-aware help"""
    
    if not context:
        return format_prompt_response(
            content=f"""# {PROJECT_NAME.title()} Help

## Common Tasks

### Getting Started
- Use `/{PROJECT_NAME}:quick-start` for a guided introduction
- Use `/{PROJECT_NAME}:capabilities` to see all features

### [Task Category 1]
- [Specific instruction]
- [Example command]

### [Task Category 2]
- [Specific instruction]
- [Example command]

## Need More Help?
Describe what you're trying to do for specific guidance.
""",
            suggestions={
                f"/{PROJECT_NAME}:capabilities": "View all capabilities",
                f"/{PROJECT_NAME}:quick-start": "Start guided tutorial"
            }
        )
    
    # Provide context-specific help
    content = f"# Help: {context}\n\n"
    
    # Add context-specific guidance based on keywords
    if "search" in context.lower() or "find" in context.lower():
        content += """## Searching/Finding

1. **[Search instruction 1]**
   ```
   /messages:search "query"
   ```

2. **[Search instruction 2]**
   - [Detail]
   - [Example]
"""
    elif "analyze" in context.lower() or "process" in context.lower():
        content += """## Analysis/Processing

1. **[Analysis instruction 1]**
2. **[Analysis instruction 2]**
"""
    else:
        content += "Please try one of the suggested commands below for your task."
    
    return format_prompt_response(
        content=content,
        suggestions={
            f"/{PROJECT_NAME}:capabilities": "View all features",
            f"/{PROJECT_NAME}:quick-start": "Start tutorial"
        }
    )


@mcp_prompt(
    name=f"{PROJECT_NAME}:quick-start",
    description="Quick start guide for using this MCP server",
    category="discovery"
)
async def quick_start() -> str:
    """Quick start guide for new users"""
    
    content = f"""# {PROJECT_NAME.title()} Quick Start Guide

Welcome! This guide will help you get started with {PROJECT_NAME}.

## What is {PROJECT_NAME}?

{PROJECT_DESCRIPTION}

## Basic Workflow

### 1. [First Step Name]
```
/{PROJECT_NAME}:command-one
```
[Explain what this does]

### 2. [Second Step Name]
```
/{PROJECT_NAME}:command-two "parameter"
```
[Explain what this does]

### 3. [Third Step Name]
```
/{PROJECT_NAME}:command-three
```
[Explain what this does]

## Example Use Cases

### Use Case 1: [Name]
1. [Step 1]
2. [Step 2]
3. [Step 3]

### Use Case 2: [Name]
1. [Step 1]
2. [Step 2]

## Pro Tips
- [Tip 1]
- [Tip 2]
- [Tip 3]

## Next Steps
- Try the example commands above
- Use `/{PROJECT_NAME}:help` for detailed assistance
- Explore all features with `/{PROJECT_NAME}:capabilities`

Ready to start? Try the first command above!
"""
    
    suggestions = {
        f"/{PROJECT_NAME}:command-one": "Try the first command",
        f"/{PROJECT_NAME}:capabilities": "See all features",
        f"/{PROJECT_NAME}:help": "Get more help"
    }
    
    return format_prompt_response(
        content=content,
        suggestions=suggestions
    )


# =============================================================================
# DOMAIN-SPECIFIC PROMPTS - Add your project-specific prompts here
# =============================================================================

@mcp_prompt(
    name=f"{PROJECT_NAME}:example-action",
    description="Example domain-specific action",
    category="research",  # or: analysis, integration, export, etc.
    parameters={
        "input": {"type": "string", "description": "Input parameter"},
        "options": {"type": "object", "description": "Optional settings"}
    },
    examples=[
        "Example usage 1",
        "Example usage 2"
    ],
    next_steps=[
        f"Use /{PROJECT_NAME}:next-action to continue",
        f"Use /{PROJECT_NAME}:export to save results"
    ]
)
async def example_action(
    input: str,
    options: Optional[Dict[str, Any]] = None
) -> str:
    """
    Example domain-specific prompt implementation.
    
    This shows the pattern for implementing your own prompts:
    1. Accept parameters
    2. Process/orchestrate tools
    3. Return formatted response with next steps
    """
    
    try:
        # Your implementation here
        # - Call tools
        # - Process data
        # - Orchestrate workflow
        
        results = {
            "processed": input,
            "status": "success"
        }
        
        content = f"""# Action Results

Processed: {input}
Status: Success

## Results Summary
[Your formatted results here]

## What's Next?
Based on these results, you might want to:
1. [Suggested action 1]
2. [Suggested action 2]
"""
        
        suggestions = {
            f"/{PROJECT_NAME}:next-action": "Continue processing",
            f"/{PROJECT_NAME}:export": "Export results",
            f"/{PROJECT_NAME}:help": "Get more guidance"
        }
        
        return format_prompt_response(
            content=content,
            suggestions=suggestions,
            data=results
        )
        
    except Exception as e:
        return format_prompt_response(
            content=f"Error: {str(e)}",
            suggestions={
                f"/{PROJECT_NAME}:help": "Get help",
                f"/{PROJECT_NAME}:capabilities": "View all options"
            }
        )


# =============================================================================
# REGISTRATION - Call this from your MCP server
# =============================================================================

def register_all_prompts():
    """Register all prompts for this project"""
    # The decorators automatically register prompts
    # This function ensures the module is imported
    registry = get_prompt_registry()
    
    # Verify required prompts are registered
    required = [
        f"{PROJECT_NAME}:capabilities",
        f"{PROJECT_NAME}:help",
        f"{PROJECT_NAME}:quick-start"
    ]
    
    registered = [p.name for p in registry.list_prompts()]
    for req in required:
        if req not in registered:
            raise ValueError(f"Required prompt '{req}' not registered!")
    
    return registry


# =============================================================================
# VALIDATION
# =============================================================================

if __name__ == "__main__":
    import asyncio
    
    # Test registration
    registry = register_all_prompts()
    prompts = registry.list_prompts()
    
    print(f"Registered {len(prompts)} prompts for {PROJECT_NAME}:")
    for p in prompts:
        if p.name.startswith(PROJECT_NAME):
            print(f"  - {p.name}: {p.description}")
    
    # Test execution
    async def test_prompts():
        # Test capabilities
        result = await registry.execute(f"{PROJECT_NAME}:capabilities")
        assert PROJECT_NAME in result.lower()
        print(f"✅ Capabilities prompt works")
        
        # Test help
        help_result = await registry.execute(f"{PROJECT_NAME}:help")
        assert "Common Tasks" in help_result
        print(f"✅ Help prompt works")
        
        # Test quick-start
        qs_result = await registry.execute(f"{PROJECT_NAME}:quick-start")
        assert "Quick Start" in qs_result
        print(f"✅ Quick-start prompt works")
        
        print(f"\n✅ All {PROJECT_NAME} prompts validated")
    
    asyncio.run(test_prompts())