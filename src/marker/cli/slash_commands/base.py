"""Base classes for slash command infrastructure.

This module provides the foundation for implementing slash commands
that can be used with Claude Desktop and other CLI tools.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Callable
import typer
from loguru import logger
from dataclasses import dataclass
import inspect


@dataclass
class CommandInfo:
    """Information about a registered command."""
    name: str
    description: str
    handler: Callable
    examples: List[str]
    category: str


class SlashCommand(ABC):
    """Base class for implementing slash commands."""
    
    def __init__(self, name: str, description: str, category: str = "general"):
        self.name = name
        self.description = description
        self.category = category
        self.app = typer.Typer(help=description)
        self._setup_commands()
    
    @abstractmethod
    def _setup_commands(self):
        """Setup command handlers. Must be implemented by subclasses."""
        pass
    
    def get_help(self) -> str:
        """Get help text for this command."""
        help_text = f"/{self.name}\n"
        help_text += f"Description: {self.description}\n"
        
        # Get all registered commands
        for command in self.app.registered_commands:
            help_text += f"\nSubcommand: {command.name or 'default'}\n"
            if command.help:
                help_text += f"  {command.help}\n"
            
            # Get parameters
            sig = inspect.signature(command.callback)
            params = []
            for param_name, param in sig.parameters.items():
                if param_name not in ['self']:
                    param_type = param.annotation if param.annotation != inspect.Parameter.empty else "Any"
                    default = f" = {param.default}" if param.default != inspect.Parameter.empty else ""
                    params.append(f"{param_name}: {param_type}{default}")
            
            if params:
                help_text += f"  Arguments: {', '.join(params)}\n"
        
        return help_text
    
    def get_examples(self) -> List[str]:
        """Get example usage for this command."""
        return [
            f"/{self.name}",
            f"/{self.name} --help",
        ]


class CommandRegistry:
    """Registry for managing slash commands."""
    
    def __init__(self):
        self.commands: Dict[str, SlashCommand] = {}
        self.categories: Dict[str, List[str]] = {}
    
    def register(self, command: SlashCommand):
        """Register a slash command."""
        if command.name in self.commands:
            logger.warning(f"Command {command.name} already registered, overwriting")
        
        self.commands[command.name] = command
        
        # Add to category
        if command.category not in self.categories:
            self.categories[command.category] = []
        if command.name not in self.categories[command.category]:
            self.categories[command.category].append(command.name)
        
        logger.debug(f"Registered command: {command.name}")
    
    def get_command(self, name: str) -> Optional[SlashCommand]:
        """Get a command by name."""
        return self.commands.get(name)
    
    def list_commands(self, category: Optional[str] = None) -> List[str]:
        """List all registered commands, optionally filtered by category."""
        if category:
            return self.categories.get(category, [])
        return list(self.commands.keys())
    
    def get_help(self, command_name: Optional[str] = None) -> str:
        """Get help text for a command or all commands."""
        if command_name:
            command = self.get_command(command_name)
            if command:
                return command.get_help()
            return f"Command '{command_name}' not found"
        
        # Get help for all commands
        help_text = "# Marker Slash Commands\n\n"
        
        for category, command_names in sorted(self.categories.items()):
            help_text += f"\n## {category.title()} Commands\n\n"
            for name in sorted(command_names):
                command = self.commands[name]
                help_text += f"### /{name}\n"
                help_text += f"{command.description}\n\n"
        
        return help_text
    
    def execute(self, command_line: str) -> Any:
        """Execute a slash command from a command line string."""
        parts = command_line.strip().split()
        if not parts or not parts[0].startswith('/'):
            raise ValueError("Invalid command format. Commands must start with '/'")
        
        command_name = parts[0][1:]  # Remove the '/'
        args = parts[1:]
        
        command = self.get_command(command_name)
        if not command:
            available = ", ".join(self.list_commands())
            raise ValueError(f"Unknown command: {command_name}. Available: {available}")
        
        # Execute through typer app
        return command.app(args)


class CommandGroup(SlashCommand):
    """Base class for commands with multiple subcommands."""
    
    def __init__(self, name: str, description: str, category: str = "general"):
        super().__init__(name, description, category)
        self.subcommands = {}
    
    def add_subcommand(self, name: str, handler: Callable, help_text: str = ""):
        """Add a subcommand to this group."""
        self.subcommands[name] = {
            'handler': handler,
            'help': help_text
        }
        
        # Register with typer
        self.app.command(name=name, help=help_text)(handler)
    
    def _setup_commands(self):
        """Setup default command that shows help."""
        @self.app.callback(invoke_without_command=True)
        def default(ctx: typer.Context):
            """Show help when no subcommand is provided."""
            if ctx.invoked_subcommand is None:
                print(self.get_help())


# Utility functions for command implementations
def format_output(data: Any, format: str = "text") -> str:
    """Format output data based on requested format."""
    if format == "json":
        import json
        return json.dumps(data, indent=2)
    elif format == "yaml":
        import yaml
        return yaml.dump(data, default_flow_style=False)
    elif format == "table":
        # Simple table formatting
        if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
            headers = list(data[0].keys())
            rows = []
            for item in data:
                rows.append([str(item.get(h, '')) for h in headers])
            
            # Calculate column widths
            widths = [len(h) for h in headers]
            for row in rows:
                for i, cell in enumerate(row):
                    widths[i] = max(widths[i], len(cell))
            
            # Format table
            table = " | ".join(h.ljust(w) for h, w in zip(headers, widths)) + "\n"
            table += "-+-".join("-" * w for w in widths) + "\n"
            for row in rows:
                table += " | ".join(c.ljust(w) for c, w in zip(row, widths)) + "\n"
            
            return table
    
    # Default text format
    return str(data)


def validate_file_path(path: str, must_exist: bool = True) -> str:
    """Validate a file path."""
    from pathlib import Path
    
    p = Path(path)
    if must_exist and not p.exists():
        raise typer.BadParameter(f"File not found: {path}")
    
    return str(p.absolute())


def validate_url(url: str) -> str:
    """Validate a URL."""
    from urllib.parse import urlparse
    
    result = urlparse(url)
    if not all([result.scheme, result.netloc]):
        raise typer.BadParameter(f"Invalid URL: {url}")
    
    return url