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
    store_tree_sitter_metadata = True  # Store extracted functions/classes/etc
    
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
                if heuristic_confidence >= 0.3:
                    languages_to_try.append(heuristic_lang)
                
                # Add commonly used languages
                common_langs = ['python', 'javascript', 'java', 'cpp', 'go', 'bash', 'rust']
                for lang in common_langs:
                    if lang not in languages_to_try:
                        languages_to_try.append(lang)
                
                best_language = None
                best_score = 0
                best_metadata = None
                
                for lang in languages_to_try[:7]:  # Try a few more languages
                    if get_supported_language(lang):
                        try:
                            metadata = extract_code_metadata(block.code, lang)
                            if metadata.get('tree_sitter_success') and not metadata.get('error'):
                                # Base score for successful parsing
                                # Give higher base score for successful parsing even without functions/classes
                                score = 0.6
                                
                                # Bonus for finding functions/classes
                                if metadata.get('functions'):
                                    score += 0.2 * min(len(metadata['functions']), 2)
                                if metadata.get('classes'):
                                    score += 0.2 * min(len(metadata['classes']), 2)
                                    
                                # Bonus if it matches heuristic detection
                                if lang == heuristic_lang and heuristic_confidence >= 0.3:
                                    score += heuristic_confidence * 0.3
                                    
                                if score > best_score:
                                    best_score = score
                                    best_language = lang
                                    # Store the metadata for later use
                                    best_metadata = metadata
                                    
                        except Exception as e:
                            logger.debug(f"Error trying language {lang}: {e}")
                            continue
                
                if best_language and best_score >= 0.5:  # Lower threshold for simple code
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
        
        # Store tree-sitter metadata if available and enabled
        if (self.store_tree_sitter_metadata and 
            'best_metadata' in locals() and 
            best_metadata and 
            best_metadata.get('tree_sitter_success')):
            # Store directly on the block as a custom attribute
            # Since Code blocks are Pydantic models, we need to use __dict__ directly
            block.__dict__['tree_sitter_metadata'] = best_metadata
            
            # Log what we stored
            functions = best_metadata.get('functions', [])
            classes = best_metadata.get('classes', [])
            logger.debug(f"Stored tree-sitter metadata: {len(functions)} functions, {len(classes)} classes")
        
        return detected_language
    
    def _heuristic_detection(self, code: str) -> tuple[str, float]:
        """
        Enhanced heuristic-based language detection.
        
        This provides a quick estimation based on common patterns and keywords.
        Returns (language, confidence) tuple.
        """
        # Check for data formats first (JSON, YAML, XML)
        code_stripped = code.strip()
        
        # JSON detection
        if code_stripped.startswith('{') and code_stripped.endswith('}'):
            if '"' in code and ':' in code:
                return 'json', 0.9
        elif code_stripped.startswith('[') and code_stripped.endswith(']'):
            if '"' in code or "'" in code:
                return 'json', 0.8
                
        # XML/HTML detection
        if code_stripped.startswith('<') and code_stripped.endswith('>'):
            if '</' in code:
                return 'xml', 0.9
                
        # Python type hints detection - check BEFORE YAML
        if ('from typing' in code or 'import typing' in code):
            if 'List[' in code or 'Dict[' in code or 'Optional[' in code:
                return 'python', 0.95
                
        # YAML detection (simple heuristic)
        lines = code.split('\n')
        yaml_score = 0
        has_type_annotations = False
        
        for line in lines[:5]:  # Check first 5 lines
            stripped = line.strip()
            if stripped and ':' in stripped and not line.lstrip().startswith('#'):
                # Skip if it looks like Python type annotations
                if 'List[' in line or 'Dict[' in line or ': int' in line or ': str' in line or ': float' in line:
                    has_type_annotations = True
                    continue
                    
                # Check for YAML-style key: value
                if stripped.count(':') == 1 and not stripped.endswith(':'):
                    yaml_score += 1
                elif line.startswith(' ') or line.startswith('-'):
                    yaml_score += 0.5
        
        # Don't identify as YAML if Python type annotations found
        if yaml_score >= 2 and not has_type_annotations:
            return 'yaml', min(yaml_score / 3, 1.0)
        
        # SQL detection
        sql_keywords = ['SELECT', 'FROM', 'WHERE', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP', 'ALTER']
        sql_score = 0
        code_upper = code.upper()
        for keyword in sql_keywords:
            if keyword in code_upper:
                sql_score += 1
        if sql_score >= 2:
            return 'sql', min(sql_score / 3, 1.0)
        
        # Check for shell scripts first
        if code_stripped.startswith('#!/bin/bash') or code_stripped.startswith('#!/bin/sh'):
            return 'bash', 1.0
        
        # Bash detection (improved - check earlier)
        bash_indicators = ['echo ', 'cd ', 'export ', 'if [', ']; then', './', '#!/bin/bash']
        bash_score = 0
        for indicator in bash_indicators:
            if indicator in code:
                bash_score += 1
        
        if bash_score >= 2:
            return 'bash', min(bash_score / 3, 0.9)
                
        # JavaScript detection (improved) - check for strong patterns early
        if '=>' in code and ('const ' in code or 'let ' in code):
            if not ('from typing' in code or 'List[' in code or 'Dict[' in code):
                return 'javascript', 0.85
                
        # Check for TypeScript typing before Python typing
        if (': string' in code or ': number' in code or ': boolean' in code):
            if 'from typing' not in code and 'import typing' not in code:
                return 'typescript', 0.85
                
        
        # Common patterns for different languages
        patterns = {
            'python': {
                'keywords': ['def ', 'class ', 'import ', 'from ', 'if __name__', 'print(', 'elif ', 'lambda ', 'self.', '    return '],
                'patterns': [r'^\s*#[^!]', r'"""', r"'''", r'if __name__ == "__main__":', r'def \w+\(', r':\s*$', r'^\s*@', r'import\s+\w+'],
                'weight': 1.0
            },
            'javascript': {
                'keywords': ['function', 'const ', 'let ', 'var ', 'return', 'console.', '.then(', '=>', 'async ', 'await ', 'module.exports'],
                'patterns': [r'===', r'!==', r'=>', r'\.then\s*\(', r'async\s+function', r'console\.log\(', r'\$\{', r'`'],
                'weight': 0.95
            },
            'java': {
                'keywords': ['public class', 'private', 'void', 'new ', 'extends', 'implements', 'System.out', 'public static', 'package '],
                'patterns': [r'@Override', r'System\.out\.println', r'public\s+static\s+void\s+main', r'public\s+class', r';$'],
                'weight': 1.0
            },
            'cpp': {
                'keywords': ['#include', 'using namespace', 'std::', 'void ', 'int main', 'cout <<', 'cin >>', 'template'],
                'patterns': [r'#include\s*<', r'std::', r'<<', r'>>', r'->', r'using\s+namespace\s+std', r'::'],
                'weight': 0.95
            },
            'csharp': {
                'keywords': ['using ', 'namespace ', 'public class', 'void ', 'new ', 'static ', 'async Task', 'var '],
                'patterns': [r'\.NET', r'System\.', r'async\s+Task', r'public\s+class', r';$'],
                'weight': 0.9
            },
            'go': {
                'keywords': ['package ', 'import', 'func ', 'type ', 'struct ', ':=', 'fmt.', 'defer '],
                'patterns': [r'package\s+main', r':=', r'func\s+main\s*\(', r'fmt\.Print', r'func\s+\w+\s*\('],
                'weight': 0.95
            },
            'rust': {
                'keywords': ['fn ', 'let ', 'mut ', 'use ', 'struct ', 'impl ', 'pub fn', 'match '],
                'patterns': [r'fn\s+main\s*\(', r'&mut', r'Option<', r'Result<', r'println!\(', r'->'],
                'weight': 0.9
            },
            'ruby': {
                'keywords': ['def ', 'class ', 'module ', 'end', 'require ', 'puts ', 'elsif '],
                'patterns': [r'^\s*#', r'def\s+\w+', r'puts\s+', r'\.new', r'@\w+'],
                'weight': 0.85
            },
            'php': {
                'keywords': ['<?php', 'function ', '$', 'echo ', 'class ', 'new ', 'namespace '],
                'patterns': [r'<\?php', r'\$this->', r'->', r'echo\s+', r'\$\w+'],
                'weight': 0.9
            },
            'swift': {
                'keywords': ['func ', 'var ', 'let ', 'class ', 'struct ', 'import ', 'print(', 'guard '],
                'patterns': [r'func\s+\w+', r'import\s+UIKit', r'import\s+Foundation', r'guard\s+let'],
                'weight': 0.85
            },
            'bash': {
                'keywords': ['#!/bin/bash', 'echo ', 'if [', 'then', 'fi', 'for ', 'do', 'done', 'export '],
                'patterns': [r'^#!/bin/bash', r'^\s*#', r'\[\[', r'\]\]', r'\$\(', r'if\s+\['],
                'weight': 0.9
            },
            'typescript': {
                'keywords': ['interface ', 'type ', 'const ', 'let ', 'function', 'async ', 'await ', ': string', ': number'],
                'patterns': [r':\s*(string|number|boolean)', r'interface\s+\w+', r'type\s+\w+', r'=>', r'export\s+'],
                'weight': 0.9
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
                if match_ratio > 0.3:
                    normalized_score *= 1.2
                
                scores[lang] = min(normalized_score, 1.0)
        
        if scores:
            best_lang = max(scores.items(), key=lambda x: x[1])
            return best_lang[0], best_lang[1]
        
        return self.fallback_language, 0.0