"""Slash command infrastructure for marker CLI.
Module: __init__.py
Description: Package initialization and exports

This module provides slash command functionality similar to sparta,
enabling easy integration with Claude Desktop and other tools.
"""

from .base import SlashCommand, CommandRegistry

# Initialize global command registry
registry = CommandRegistry()

__all__ = [
    "SlashCommand",
    "CommandRegistry",
    "registry",
]

# Register commands with graceful fallback for missing dependencies
# This allows the CLI to work even if some slash commands have broken imports


def _safe_register(module_name: str, class_name: str):
    """Safely import and register a command, logging failures."""
    try:
        import importlib

        module = importlib.import_module(f".{module_name}", package=__name__)
        command_class = getattr(module, class_name)
        registry.register(command_class())
        __all__.append(class_name)
        return True
    except Exception as e:
        from loguru import logger

        logger.debug(f"Could not register {class_name}: {e}")
        return False


# Core commands (most likely to work)
_safe_register("extract", "ExtractCommand")
_safe_register("serve", "ServeCommand")
_safe_register("test", "TestCommands")

# Commands with external dependencies (may fail)
_safe_register("workflow", "WorkflowCommands")
_safe_register("granger", "GrangerCommands")

# Disabled commands - depend on unimplemented modules
# _safe_register("arangodb", "ArangoDBCommands")  # Module deleted
# _safe_register("claude", "ClaudeCommands")  # Depends on unimplemented processors
# _safe_register("qa", "QACommands")  # Depends on extractor.core.arangodb
