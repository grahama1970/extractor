"""Marker CLI module with slash command support."""

from marker.cli.agent_commands import app as agent_app
from marker.cli.slash_commands import registry as slash_registry

__all__ = ["agent_app", "slash_registry"]