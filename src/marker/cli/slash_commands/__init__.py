"""Slash command infrastructure for marker CLI.

This module provides slash command functionality similar to sparta,
enabling easy integration with Claude Desktop and other tools.
"""

from .base import SlashCommand, CommandRegistry
from .extract import ExtractCommand
from .arangodb import ArangoDBCommands
from .claude import ClaudeCommands
from .qa import QACommands
from .workflow import WorkflowCommands
from .test import TestCommands
from .serve import ServeCommand

__all__ = [
    "SlashCommand",
    "CommandRegistry",
    "ExtractCommand",
    "ArangoDBCommands", 
    "ClaudeCommands",
    "QACommands",
    "WorkflowCommands",
    "TestCommands",
    "ServeCommand",
]

# Initialize global command registry
registry = CommandRegistry()

# Register all commands
registry.register(ExtractCommand())
registry.register(ArangoDBCommands())
registry.register(ClaudeCommands())
registry.register(QACommands())
registry.register(WorkflowCommands())
registry.register(TestCommands())
registry.register(ServeCommand())