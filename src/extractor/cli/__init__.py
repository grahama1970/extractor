"""
Module: __init__.py
Description: Marker CLI module with slash command support - Package initialization and exports
"""

from extractor.cli.agent_commands import app as agent_app
from extractor.cli.slash_commands import registry as slash_registry

__all__ = ["agent_app", "slash_registry"]