from marker.processors import BaseProcessor
from marker.schema import BlockTypes
from marker.schema.blocks import Code
from marker.schema.document import Document
from marker.services.utils.tree_sitter_utils import extract_code_metadata, get_supported_language
from typing import Optional
import logging

# Set up logging
logger = logging.getLogger(__name__)


class CodeProcessor(BaseProcessor):
    """
    Enhanced processor for formatting and language detection of code blocks.
    
    This processor:
    1. Formats code block text with proper indentation
    2. Detects programming language using tree-sitter
    3. Falls back to heuristic detection when tree-sitter fails
    4. Sets the language attribute on Code blocks
    """
    block_types = (BlockTypes.Code, )
    
    # Configuration attributes
    enable_language_detection = True
    detection_timeout = 1.0
    min_confidence = 0.7
    fallback_language = 'text'
    
    def __init__(self, config=None):
        super().__init__(config)
        self._detection_cache = {}
    
    def __call__(self, document: Document):
        for page in document.pages:
            for block in page.contained_blocks(document, self.block_types):
                self.format_block(document, block)
                if self.enable_language_detection and not block.language:
                    self.detect_language(block)

    def format_block(self, document: Document, block: Code):
        min_left = 9999  # will contain x- coord of column 0
        total_width = 0
        total_chars = 0
        
        contained_lines = block.contained_blocks(document, (BlockTypes.Line,))
        for line in contained_lines:
            min_left = min(line.polygon.bbox[0], min_left)
            total_width += line.polygon.width
            total_chars += len(line.raw_text(document))

        avg_char_width = total_width / max(total_chars, 1)
        code_text = ""
        is_new_line = False
        for line in contained_lines:
            text = line.raw_text(document)
            if avg_char_width == 0:
                prefix = ""
            else:
                total_spaces = int((line.polygon.bbox[0] - min_left) / avg_char_width)
                prefix = " " * max(0, total_spaces)

            if is_new_line:
                text = prefix + text

            code_text += text
            is_new_line = text.endswith("\n")

        block.code = code_text.rstrip()
    
    def detect_language(self, block: Code) -> Optional[str]:
        """
        Detect the programming language of a code block.
        
        This method:
        1. First attempts detection using tree-sitter
        2. Falls back to heuristic detection if tree-sitter fails
        3. Sets the language attribute on the block
        4. Returns the detected language
        """
        if not block.code:
            return None
            
        # Check cache first
        cache_key = hash(block.code[:500])  # Use first 500 chars for cache key
        if cache_key in self._detection_cache:
            detected_language = self._detection_cache[cache_key]
            block.language = detected_language
            return detected_language
        
        detected_language = None
        confidence = 0.0
        
        # First try heuristic detection for quick, obvious cases
        heuristic_lang, heuristic_confidence = self._heuristic_detection(block.code)
        
        # If heuristic detection is very confident, use it
        if heuristic_confidence >= 0.8:
            detected_language = heuristic_lang
            confidence = heuristic_confidence
        else:
            # Try tree-sitter detection for a more thorough analysis
            try:
                # Only try a few most likely languages based on heuristics
                languages_to_try = []
                
                # Add languages based on heuristic detection
                if heuristic_confidence >= 0.4:
                    languages_to_try.append(heuristic_lang)
                
                # Add commonly used languages
                common_langs = ['python', 'javascript', 'java', 'cpp', 'go']
                for lang in common_langs:
                    if lang not in languages_to_try:
                        languages_to_try.append(lang)
                
                best_language = None
                best_score = 0
                
                for lang in languages_to_try[:5]:  # Limit to 5 attempts
                    if get_supported_language(lang):
                        try:
                            metadata = extract_code_metadata(block.code, lang)
                            if metadata.get('tree_sitter_success') and not metadata.get('error'):
                                # Score based on successful parsing and structure found
                                score = 0.7  # Base score for successful parsing
                                
                                # Bonus for finding functions/classes
                                if metadata.get('functions'):
                                    score += 0.1 * min(len(metadata['functions']), 3)
                                if metadata.get('classes'):
                                    score += 0.2 * min(len(metadata['classes']), 2)
                                    
                                # Bonus if it matches heuristic detection
                                if lang == heuristic_lang:
                                    score += 0.1
                                    
                                if score > best_score:
                                    best_score = score
                                    best_language = lang
                                    
                        except Exception as e:
                            logger.debug(f"Error trying language {lang}: {e}")
                            continue
                
                if best_language and best_score >= self.min_confidence:
                    detected_language = best_language
                    confidence = min(best_score, 1.0)
                    
            except Exception as e:
                logger.debug(f"Tree-sitter detection failed: {e}")
        
        # Use heuristic detection as fallback
        if not detected_language and heuristic_confidence >= 0.3:
            detected_language = heuristic_lang
            confidence = heuristic_confidence
        
        # Use fallback if confidence is too low
        if not detected_language or confidence < 0.3:
            detected_language = self.fallback_language
            
        # Cache the result
        self._detection_cache[cache_key] = detected_language
        
        # Set the language on the block
        block.language = detected_language
        logger.debug(f"Detected language: {detected_language} (confidence: {confidence})")
        
        return detected_language
    
    def _heuristic_detection(self, code: str) -> tuple[str, float]:
        """
        Enhanced heuristic-based language detection.
        
        This provides a quick estimation based on common patterns and keywords.
        Returns (language, confidence) tuple.
        """
        # Common patterns for different languages
        patterns = {
            'python': {
                'keywords': ['def ', 'class ', 'import ', 'from ', 'if __name__', 'async def', 'self.', 'print('],
                'patterns': [r'^\s*#', r'"""', r"'''", r'if __name__ == "__main__":', r'def \w+\(self'],
                'weight': 1.0
            },
            'javascript': {
                'keywords': ['function', 'const ', 'let ', 'var ', 'return', 'console.', '.then(', '=>'],
                'patterns': [r'===', r'!==', r'=>', r'\.then\s*\(', r'async\s+function', r'console\.log\('],
                'weight': 0.95
            },
            'java': {
                'keywords': ['public class', 'private', 'void', 'new ', 'extends', 'implements', 'System.out', 'public static'],
                'patterns': [r'@Override', r'System\.out\.println', r'public\s+static\s+void\s+main', r'public\s+class'],
                'weight': 1.0
            },
            'cpp': {
                'keywords': ['#include', 'using namespace', 'std::', 'void ', 'int main', 'cout <<', 'cin >>'],
                'patterns': [r'#include\s*<', r'std::', r'<<', r'>>', r'->', r'using\s+namespace\s+std'],
                'weight': 0.95
            },
            'csharp': {
                'keywords': ['using ', 'namespace ', 'public class', 'void ', 'new ', 'static ', 'async Task'],
                'patterns': [r'\.NET', r'System\.', r'async\s+Task', r'public\s+class'],
                'weight': 0.9
            },
            'go': {
                'keywords': ['package ', 'import', 'func ', 'type ', 'struct ', ':=', 'fmt.P'],
                'patterns': [r'package\s+main', r':=', r'func\s+main\s*\(', r'fmt\.Print'],
                'weight': 0.95
            },
            'rust': {
                'keywords': ['fn ', 'let ', 'mut ', 'use ', 'struct ', 'impl ', 'pub fn'],
                'patterns': [r'fn\s+main\s*\(', r'&mut', r'Option<', r'Result<', r'println!\('],
                'weight': 0.9
            },
            'ruby': {
                'keywords': ['def ', 'class ', 'module ', 'end', 'require ', 'puts '],
                'patterns': [r'^\s*#', r'def\s+\w+', r'puts\s+', r'\.new'],
                'weight': 0.85
            },
            'php': {
                'keywords': ['<?php', 'function ', '$', 'echo ', 'class ', 'new '],
                'patterns': [r'<\?php', r'\$this->', r'->', r'echo\s+'],
                'weight': 0.9
            },
            'swift': {
                'keywords': ['func ', 'var ', 'let ', 'class ', 'struct ', 'import ', 'print('],
                'patterns': [r'func\s+\w+', r'import\s+UIKit', r'import\s+Foundation'],
                'weight': 0.85
            }
        }
        
        scores = {}
        code_lower = code.lower()
        
        for lang, info in patterns.items():
            score = 0.0
            matches = 0
            total_patterns = len(info['keywords']) + len(info['patterns'])
            
            # Check keywords
            for keyword in info['keywords']:
                if keyword.lower() in code_lower:
                    score += 1.0
                    matches += 1
            
            # Check patterns
            import re
            for pattern in info['patterns']:
                if re.search(pattern, code, re.MULTILINE | re.IGNORECASE):
                    score += 1.2  # Patterns are more specific, so weight them higher
                    matches += 1
            
            # Normalize score
            if matches > 0:
                # Calculate confidence based on number of matches and total possible patterns
                normalized_score = (score / total_patterns) * info['weight']
                match_ratio = matches / total_patterns
                
                # Boost confidence if many patterns match
                if match_ratio > 0.5:
                    normalized_score *= 1.2
                
                scores[lang] = min(normalized_score, 1.0)
        
        if scores:
            best_lang = max(scores.items(), key=lambda x: x[1])
            return best_lang[0], best_lang[1]
        
        return self.fallback_language, 0.0