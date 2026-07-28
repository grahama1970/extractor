
import unittest
import sys
from pathlib import Path
import re

# Add src to path
sys.path.append(str(Path.cwd() / "src"))

# Mock dependencies
from unittest.mock import MagicMock
sys.modules["extractor.pipeline.utils.reliability"] = MagicMock()
sys.modules["extractor.pipeline.utils.diagnostics"] = MagicMock()

# Import S04 constants and functions
# Note: we need to import carefully as some imports might trigger heavy dependencies
from extractor.pipeline.steps.s04_section_builder import TOC_ENTRY_PATTERNSS, PAGE_HEADER_FOOTER_PATTERNSS

class TestV3Fixes(unittest.TestCase):
    """Test V3 fixes for TOC pattern matching."""
    def test_toc_patterns(self):
        # Test new V3 patterns
        cases = [
            "...", "True", # Multiple dots
            ". . .", "True", # Spaced dots
            "Title\t...............12", "True", # Tab + dots + num
            "1.2 Section Name ..... 55", "True", # Numbered + dots
        ]
        
        # We manually check the regex against the list
        for text in ["...", ". . .", "Title\t...............12", "1.2 Section Name ..... 55"]:
            matched = False
            for pat in TOC_ENTRY_PATTERNSS:
                if re.search(pat, text):
                    matched = True
                    break
            self.assertTrue(matched, f"Failed to match TOC pattern: {text}")

    def test_metadata_pattern(self):
        """Tests if metadata text matches a header/footer pattern."""
        text = "Jkt 067464 PO 00000 Frm 00010"
        matched = False
        for pat in PAGE_HEADER_FOOTER_PATTERNSS:
            if re.search(pat, text):
                matched = True
                break
        self.assertTrue(matched, "Failed to match Metadata pattern")

if __name__ == '__main__':
    unittest.main()
