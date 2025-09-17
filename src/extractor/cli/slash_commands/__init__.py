"""Slash command infrastructure for marker CLI.
Module: __init__.py
Description: Package initialization and exports

This module provides slash command functionality similar to sparta,
enabling easy integration with Claude Desktop and other tools.
"""

from .base import SlashCommand, CommandRegistry
from .extract import ExtractCommand

# from .arangodb import ArangoDBCommands  # Temporarily disabled - module deleted in cleanup
from .claude import ClaudeCommands
from .qa import QACommands
from .workflow import WorkflowCommands
from .test import TestCommands
from .serve import ServeCommand
from .granger import GrangerCommands

__all__ = [
    "SlashCommand",
    "CommandRegistry",
    "ExtractCommand",
    # "ArangoDBCommands",  # Temporarily disabled
    "ClaudeCommands",
    "QACommands",
    "WorkflowCommands",
    "TestCommands",
    "ServeCommand",
    "GrangerCommands",
]

# Initialize global command registry
registry = CommandRegistry()

# Register all commands
registry.register(ExtractCommand())
# registry.register(ArangoDBCommands())  # Temporarily disabled
registry.register(ClaudeCommands())
registry.register(QACommands())
registry.register(WorkflowCommands())
registry.register(TestCommands())
registry.register(ServeCommand())
registry.register(GrangerCommands())
