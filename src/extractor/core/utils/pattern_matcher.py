#!/usr/bin/env python3
"""
Pre-compiled pattern matching for performance optimization.

Compiles regex patterns once and caches results for efficient pattern matching.
"""

import re
from functools import lru_cache
from typing import Dict, List, Optional, Pattern, Set
from loguru import logger


class PatternMatcher:
    """Efficient pattern matching with pre-compiled regex patterns."""
    
    def __init__(self):
        """Initialize pattern matcher with common patterns."""
        self.patterns: Dict[str, List[Pattern]] = {
            'split_header': [
                re.compile(r'^For\s+any\s+', re.IGNORECASE),
                re.compile(r'^As\s+\w+\s*=', re.IGNORECASE),
                re.compile(r'^And\s+', re.IGNORECASE),
                re.compile(r'^But\s+', re.IGNORECASE),
                re.compile(r'^Or\s+', re.IGNORECASE),
                re.compile(r'^So\s+', re.IGNORECASE),
                re.compile(r'^Then\s+', re.IGNORECASE),
                re.compile(r'^When\s+', re.IGNORECASE),
                re.compile(r'^If\s+', re.IGNORECASE),
                re.compile(r',$'),  # Ends with comma
                re.compile(r':$'),  # Ends with colon
                re.compile(r';$'),  # Ends with semicolon
                re.compile(r'\s+\($'),  # Ends with opening parenthesis
                re.compile(r'^\)\s*'),  # Starts with closing parenthesis
            ],
            'continuation_indicators': [
                re.compile(r'^[a-z]'),  # Starts with lowercase
                re.compile(r'^\s*-\s+'),  # Bullet point continuation
                re.compile(r'^\s*\d+\.\s+'),  # Numbered list continuation
                re.compile(r'^\s*[ivx]+\.\s+', re.IGNORECASE),  # Roman numeral list
                re.compile(r'^\s*[a-z]\)\s+'),  # Letter list (a), b), etc.)
            ],
            'table_patterns': [
                re.compile(r'\|'),  # Pipe character (table delimiter)
                re.compile(r'^\s*\+[-+]+\+\s*$'),  # ASCII table border
                re.compile(r'^\s*[-=]{3,}\s*$'),  # Horizontal rule
                re.compile(r'\t{2,}'),  # Multiple tabs (column separator)
            ],
            'header_patterns': [
                re.compile(r'^\d+\.?\s+[A-Z]'),  # Numbered section (1. Title)
                re.compile(r'^[A-Z][A-Z\s]{2,}$'),  # All caps header
                re.compile(r'^Chapter\s+\d+', re.IGNORECASE),
                re.compile(r'^Section\s+\d+', re.IGNORECASE),
                re.compile(r'^Part\s+[IVX]+', re.IGNORECASE),
                re.compile(r'^Appendix\s+[A-Z]', re.IGNORECASE),
            ],
            'code_patterns': [
                re.compile(r'^\s*(?:def|class|function|var|let|const)\s+'),
                re.compile(r'^\s*(?:if|for|while|switch)\s*\('),
                re.compile(r'^\s*(?:import|from|include|require)\s+'),
                re.compile(r'[{};]\s*$'),  # Ends with code delimiters
            ],
            'math_patterns': [
                re.compile(r'\\[A-Za-z]+'),  # LaTeX commands
                re.compile(r'\$[^$]+\$'),  # Inline math
                re.compile(r'^\s*\\begin\{'),  # LaTeX environment
                re.compile(r'^\s*\\end\{'),
                re.compile(r'[∫∑∏∂∇]'),  # Math symbols
            ],
            'url_patterns': [
                re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+'),
                re.compile(r'www\.[^\s<>"{}|\\^`\[\]]+'),
                re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'),
            ],
            'reference_patterns': [
                re.compile(r'^\[\d+\]'),  # [1] style citations
                re.compile(r'\(\d{4}\)'),  # (2024) year citations
                re.compile(r'et\s+al\.'),  # et al.
                re.compile(r'Fig(?:ure)?\s*\.?\s*\d+', re.IGNORECASE),
                re.compile(r'Table\s*\.?\s*\d+', re.IGNORECASE),
            ]
        }
        
        # Cache for matched patterns
        self._cache_size = 10000
        
    @lru_cache(maxsize=10000)
    def is_suspicious(self, text: str, pattern_type: str = 'split_header') -> bool:
        """Check if text matches any pattern of the given type.
        
        Args:
            text: Text to check
            pattern_type: Type of pattern to check against
            
        Returns:
            True if text matches any pattern
        """
        if not text or pattern_type not in self.patterns:
            return False
        
        for pattern in self.patterns.get(pattern_type, []):
            if pattern.search(text):
                return True
        return False
    
    @lru_cache(maxsize=10000)
    def find_all_matches(self, text: str, pattern_type: str) -> List[str]:
        """Find all matches for a pattern type in text.
        
        Args:
            text: Text to search
            pattern_type: Type of pattern to find
            
        Returns:
            List of matched strings
        """
        matches = []
        if not text or pattern_type not in self.patterns:
            return matches
        
        for pattern in self.patterns.get(pattern_type, []):
            matches.extend(pattern.findall(text))
        
        return matches
    
    @lru_cache(maxsize=10000) 
    def get_matching_pattern_types(self, text: str) -> Set[str]:
        """Get all pattern types that match the given text.
        
        Args:
            text: Text to check
            
        Returns:
            Set of pattern type names that match
        """
        matching_types = set()
        
        for pattern_type, patterns in self.patterns.items():
            for pattern in patterns:
                if pattern.search(text):
                    matching_types.add(pattern_type)
                    break
        
        return matching_types
    
    def add_pattern(self, pattern_type: str, pattern: str, flags: int = 0):
        """Add a new pattern to the matcher.
        
        Args:
            pattern_type: Category of pattern
            pattern: Regex pattern string
            flags: Regex flags (e.g., re.IGNORECASE)
        """
        if pattern_type not in self.patterns:
            self.patterns[pattern_type] = []
        
        compiled = re.compile(pattern, flags)
        self.patterns[pattern_type].append(compiled)
        
        # Clear cache when patterns change
        self.is_suspicious.cache_clear()
        self.find_all_matches.cache_clear()
        self.get_matching_pattern_types.cache_clear()
    
    def analyze_block(self, text: str) -> Dict[str, any]:
        """Comprehensive analysis of a text block.
        
        Args:
            text: Text block to analyze
            
        Returns:
            Dictionary with analysis results
        """
        if not text:
            return {
                'is_empty': True,
                'pattern_matches': [],
                'suspicious_score': 0.0
            }
        
        # Get all matching patterns
        matching_types = self.get_matching_pattern_types(text)
        
        # Calculate suspicion score
        suspicious_indicators = {
            'split_header', 'continuation_indicators',
            'table_patterns', 'code_patterns'
        }
        
        suspicious_matches = matching_types & suspicious_indicators
        suspicious_score = len(suspicious_matches) / len(suspicious_indicators)
        
        # Additional heuristics
        if len(text.strip()) < 5:  # Very short text
            suspicious_score = max(suspicious_score, 0.7)
        
        if text.count(' ') < 2 and len(text) > 10:  # Few spaces (possible OCR issue)
            suspicious_score = max(suspicious_score, 0.6)
        
        return {
            'is_empty': False,
            'pattern_matches': list(matching_types),
            'suspicious_score': suspicious_score,
            'is_header_candidate': 'header_patterns' in matching_types,
            'is_code_candidate': 'code_patterns' in matching_types,
            'is_table_candidate': 'table_patterns' in matching_types,
            'is_math_candidate': 'math_patterns' in matching_types,
            'has_references': 'reference_patterns' in matching_types,
            'has_urls': 'url_patterns' in matching_types,
            'needs_continuation_check': 'continuation_indicators' in matching_types,
        }
    
    def clear_cache(self):
        """Clear the LRU cache."""
        self.is_suspicious.cache_clear()
        self.find_all_matches.cache_clear()
        self.get_matching_pattern_types.cache_clear()
        logger.info("Pattern matcher cache cleared")
    
    def get_cache_info(self) -> Dict[str, any]:
        """Get cache statistics."""
        return {
            'is_suspicious': self.is_suspicious.cache_info()._asdict(),
            'find_all_matches': self.find_all_matches.cache_info()._asdict(),
            'get_matching_pattern_types': self.get_matching_pattern_types.cache_info()._asdict()
        }


# Global pattern matcher instance
_pattern_matcher: Optional[PatternMatcher] = None


def get_pattern_matcher() -> PatternMatcher:
    """Get or create the global pattern matcher instance."""
    global _pattern_matcher
    if _pattern_matcher is None:
        _pattern_matcher = PatternMatcher()
    return _pattern_matcher