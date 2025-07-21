"""
MCP Prompt Infrastructure for YouTube Transcripts
Module: prompts.py

This module provides the core infrastructure for implementing MCP prompts,
which are higher-level workflows that compose multiple tools into guided
agentic experiences.

External Dependencies:
- typing: https://docs.python.org/3/library/typing.html
- asyncio: https://docs.python.org/3/library/asyncio.html

Example Usage:
>>> from youtube_transcripts.mcp.prompts import PromptRegistry, mcp_prompt
>>> registry = PromptRegistry()
>>> 
>>> @mcp_prompt(name="youtube:capabilities", description="List all capabilities")
>>> async def list_capabilities(registry: PromptRegistry) -> str:
...     return "Available capabilities: ..."
"""

from typing import Dict, List, Callable, Any, Optional, Union, TypeVar, Protocol
from dataclasses import dataclass, field
import asyncio
import inspect
from functools import wraps
import json

# Type definitions
PromptFunction = TypeVar('PromptFunction', bound=Callable[..., Union[str, Dict[str, Any]]])


class PromptProtocol(Protocol):
    """Protocol for MCP prompt functions"""
    async def __call__(self, **kwargs) -> Union[str, Dict[str, Any]]: ...


@dataclass
class MCPPrompt:
    """Represents a single MCP prompt"""
    name: str
    description: str
    function: Callable
    parameters: Dict[str, Any] = field(default_factory=dict)
    required_params: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)
    next_steps: List[str] = field(default_factory=list)
    
    def to_schema(self) -> Dict[str, Any]:
        """Convert prompt to MCP schema format"""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": {
                "type": "object",
                "properties": self.parameters,
                "required": self.required_params
            },
            "examples": self.examples
        }


class PromptRegistry:
    """Registry for managing MCP prompts"""
    
    def __init__(self):
        self._prompts: Dict[str, MCPPrompt] = {}
        self._categories: Dict[str, List[str]] = {
            "discovery": [],
            "research": [],
            "analysis": [],
            "integration": [],
            "export": [],
            "help": []
        }
    
    def register(
        self,
        name: str,
        description: str,
        category: str = "general",
        parameters: Optional[Dict[str, Any]] = None,
        required_params: Optional[List[str]] = None,
        examples: Optional[List[str]] = None,
        next_steps: Optional[List[str]] = None
    ) -> Callable:
        """Register a prompt function"""
        def decorator(func: PromptFunction) -> PromptFunction:
            # Extract parameters from function signature if not provided
            if parameters is None:
                sig = inspect.signature(func)
                params = {}
                required = []
                
                for param_name, param in sig.parameters.items():
                    if param_name in ['self', 'registry', 'tools']:
                        continue
                    
                    param_type = "string"
                    if param.annotation != param.empty:
                        if param.annotation == int:
                            param_type = "integer"
                        elif param.annotation == bool:
                            param_type = "boolean"
                        elif param.annotation == float:
                            param_type = "number"
                        elif param.annotation == list:
                            param_type = "array"
                        elif param.annotation == dict:
                            param_type = "object"
                    
                    params[param_name] = {
                        "type": param_type,
                        "description": f"Parameter {param_name}"
                    }
                    
                    if param.default == param.empty:
                        required.append(param_name)
            else:
                params = parameters
                required = required_params or []
            
            # Create prompt object
            prompt = MCPPrompt(
                name=name,
                description=description,
                function=func,
                parameters=params,
                required_params=required,
                examples=examples or [],
                next_steps=next_steps or []
            )
            
            # Register prompt
            self._prompts[name] = prompt
            
            # Add to category
            if category in self._categories:
                self._categories[category].append(name)
            else:
                self._categories[category] = [name]
            
            # Add metadata to function
            func._mcp_prompt = prompt
            func._prompt_name = name
            
            return func
        
        return decorator
    
    def get(self, name: str) -> Optional[MCPPrompt]:
        """Get a prompt by name"""
        return self._prompts.get(name)
    
    def list_prompts(self) -> List[MCPPrompt]:
        """List all registered prompts"""
        return list(self._prompts.values())
    
    def list_by_category(self, category: str) -> List[MCPPrompt]:
        """List prompts in a specific category"""
        names = self._categories.get(category, [])
        return [self._prompts[name] for name in names if name in self._prompts]
    
    def get_categories(self) -> Dict[str, List[str]]:
        """Get all categories and their prompts"""
        return self._categories.copy()
    
    async def execute(self, name: str, **kwargs) -> Union[str, Dict[str, Any]]:
        """Execute a prompt by name"""
        prompt = self.get(name)
        if not prompt:
            raise ValueError(f"Prompt '{name}' not found")
        
        # Inject registry if needed
        sig = inspect.signature(prompt.function)
        if 'registry' in sig.parameters:
            kwargs['registry'] = self
        
        # Execute function
        if asyncio.iscoroutinefunction(prompt.function):
            return await prompt.function(**kwargs)
        else:
            return prompt.function(**kwargs)
    
    def to_schema(self) -> Dict[str, Any]:
        """Convert all prompts to MCP schema format"""
        return {
            "prompts": [prompt.to_schema() for prompt in self._prompts.values()],
            "categories": self._categories
        }


# Global registry instance
_global_registry = PromptRegistry()


def mcp_prompt(
    name: str,
    description: str,
    category: str = "general",
    parameters: Optional[Dict[str, Any]] = None,
    required_params: Optional[List[str]] = None,
    examples: Optional[List[str]] = None,
    next_steps: Optional[List[str]] = None
) -> Callable:
    """
    Decorator for registering MCP prompts
    
    Usage:
        @mcp_prompt(
            name="youtube:research",
            description="Research a topic across YouTube transcripts",
            category="research",
            examples=["Research AI safety discussions"],
            next_steps=["Use youtube:analyze for deeper analysis"]
        )
        async def research_topic(query: str, limit: int = 10) -> str:
            return f"Researching '{query}'..."
    """
    return _global_registry.register(
        name=name,
        description=description,
        category=category,
        parameters=parameters,
        required_params=required_params,
        examples=examples,
        next_steps=next_steps
    )


def get_prompt_registry() -> PromptRegistry:
    """Get the global prompt registry"""
    return _global_registry


def format_prompt_response(
    content: str,
    next_steps: Optional[List[str]] = None,
    suggestions: Optional[Dict[str, str]] = None,
    data: Optional[Dict[str, Any]] = None
) -> str:
    """
    Format a prompt response with guidance for the agent
    
    Args:
        content: Main response content
        next_steps: List of suggested next actions
        suggestions: Dict of command suggestions
        data: Additional structured data
    
    Returns:
        Formatted response string
    """
    parts = [content]
    
    if data:
        parts.append("\n## Data")
        parts.append(f"```json\n{json.dumps(data, indent=2)}\n```")
    
    if next_steps:
        parts.append("\n## Next Steps")
        for i, step in enumerate(next_steps, 1):
            parts.append(f"{i}. {step}")
    
    if suggestions:
        parts.append("\n## Quick Commands")
        for cmd, desc in suggestions.items():
            parts.append(f"- `{cmd}` - {desc}")
    
    return "\n".join(parts)


# Validation
if __name__ == "__main__":
    # Test prompt registration
    @mcp_prompt(
        name="test:hello",
        description="Test prompt",
        examples=["Say hello to the world"]
    )
    async def test_hello(name: str = "World") -> str:
        return f"Hello, {name}!"
    
    # Test registry
    registry = get_prompt_registry()
    prompt = registry.get("test:hello")
    
    assert prompt is not None, "Prompt should be registered"
    assert prompt.name == "test:hello", f"Expected 'test:hello', got {prompt.name}"
    assert len(prompt.parameters) == 1, f"Expected 1 parameter, got {len(prompt.parameters)}"
    assert "name" in prompt.parameters, "Should have 'name' parameter"
    
    # Test async execution
    import asyncio
    result = asyncio.run(registry.execute("test:hello", name="Test"))
    assert result == "Hello, Test!", f"Expected 'Hello, Test!', got {result}"
    
    print(" Prompt infrastructure validation passed")