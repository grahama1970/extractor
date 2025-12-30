#!/usr/bin/env python3
"""
Stage 01: HTML Ingestor - Native HTML extraction

This stage processes HTML documents directly without PDF conversion,
preserving HTML semantics and structure.
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

try:
    from bs4 import BeautifulSoup, Tag
except ImportError:
    print("ERROR: BeautifulSoup not available. Install with: pip install beautifulsoup4")
    sys.exit(1)

# Minimal local imports for standalone operation
import json
import hashlib

# Core schema definitions embedded to avoid circular imports
class BlockType:
    HEADING = "Heading"
    TABLE = "Table"
    FIGURE = "Figure"
    LISTITEM = "ListItem"
    PARAGRAPH = "Paragraph"
    TEXT = "Text"

class HTMLProvider:
    """Native HTML to unified format converter."""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.content = ""
        self.blocks: List[Dict[str, Any]] = []
        self.block_counter = 0

    def parse(self) -> Dict[str, Any]:
        """Convert HTML to stage 02 compatible format."""
        try:
            self.content = self.file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            self.content = self.file_path.read_text(encoding="latin-1")

        soup = BeautifulSoup(self.content, 'html.parser')

        # Remove script/style",