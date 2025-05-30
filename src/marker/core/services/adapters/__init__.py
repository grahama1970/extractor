"""
Adapters for migrating existing Claude implementations to unified service.

These adapters provide backwards compatibility while internally using the new
unified Claude service powered by claude-module-communicator.
"""

from .claude_table_adapter import ClaudeTableMergeAdapter, ClaudeTableMergeAnalyzer

__all__ = [
    "ClaudeTableMergeAdapter",
    "ClaudeTableMergeAnalyzer",  # Alias for drop-in replacement
]