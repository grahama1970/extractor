"""
Improvements to the code language detection heuristics.
"""

def _heuristic_detection_improved(self, code: str) -> tuple[str, float]:
    """
    Enhanced heuristic-based language detection with better pattern matching.
    """
    # Check for data formats first (JSON, YAML, XML)
    code_stripped = code.strip()
    
    # JSON detection
    if code_stripped.startswith('{') and code_stripped.endswith('}'):
        if '"' in code and ':' in code:
            return 'json', 0.9
    elif code_stripped.startswith('[') and code_stripped.endswith(']'):
        if '"' in code and '{' in code:
            return 'json', 0.9
        elif '"' in code or "'" in code:
            # Could be JSON array or Python/JS list
            if 'const ' in code or 'let ' in code or '=>' in code:
                return 'javascript', 0.7
            else:
                return 'json', 0.6
            
    # XML/HTML detection
    if code_stripped.startswith('<') and code_stripped.endswith('>'):
        if '</' in code:
            return 'xml', 0.9
            
    # YAML detection (improved)
    lines = code.split('\n')
    yaml_score = 0
    colon_lines = 0
    for line in lines[:10]:  # Check first 10 lines
        stripped = line.strip()
        if stripped and ':' in stripped and not line.lstrip().startswith('#'):
            # Check for YAML-style key: value
            parts = stripped.split(':', 1)
            if len(parts) == 2 and parts[1].strip():
                yaml_score += 1
                colon_lines += 1
            elif line.startswith(' ') or line.startswith('-'):
                yaml_score += 0.5
    
    # If many lines have colons and proper structure, it's likely YAML
    if yaml_score >= 2 and colon_lines >= 2:
        return 'yaml', min(yaml_score / 3, 1.0)
    
    # SQL detection (improved)
    sql_keywords = ['SELECT', 'FROM', 'WHERE', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP', 'ALTER', 'JOIN', 'GROUP BY', 'ORDER BY']
    sql_score = 0
    code_upper = code.upper()
    for keyword in sql_keywords:
        if keyword in code_upper:
            sql_score += 1
    if sql_score >= 2:
        return 'sql', min(sql_score / 3, 1.0)
    
    # Bash detection (improved - check earlier)
    if code_stripped.startswith('#!/bin/bash') or code_stripped.startswith('#!/bin/sh'):
        return 'bash', 1.0
    
    bash_indicators = ['echo ', 'cd ', 'export ', 'if [', ']; then', 'for ', 'do\n', 'done\n']
    bash_score = 0
    for indicator in bash_indicators:
        if indicator in code:
            bash_score += 1
    
    if bash_score >= 2:
        return 'bash', min(bash_score / 3, 0.9)
    
    # JavaScript detection (improved)
    js_indicators = ['=>', 'const ', 'let ', 'var ', '.map(', '.filter(', 'async ', 'await ', 'console.log(']
    js_score = 0
    for indicator in js_indicators:
        if indicator in code:
            js_score += 1
    
    # Strong JS patterns
    if '=>' in code and ('const ' in code or 'let ' in code):
        return 'javascript', 0.9
    elif js_score >= 2:
        return 'javascript', min(js_score / 4, 0.8)
    
    # TypeScript detection (check before JavaScript)
    if (': string' in code or ': number' in code or ': boolean' in code or 
        'interface ' in code or 'type ' in code):
        if 'from typing' not in code and 'import typing' not in code:  # Not Python typing
            return 'typescript', 0.85
    
    # Python detection (improved - check for type hints)
    python_type_hints = ['List[', 'Dict[', 'Optional[', 'Union[', 'typing', ': str', ': int', ': float']
    python_typing_score = 0
    
    for hint in python_type_hints:
        if hint in code:
            python_typing_score += 1
    
    # If Python typing imports or annotations are present
    if ('from typing' in code or 'import typing' in code) and python_typing_score >= 1:
        return 'python', 0.95
    elif python_typing_score >= 2 and ('->' in code or 'def ' in code or 'class ' in code):
        return 'python', 0.9
    
    # Regular patterns for different languages
    patterns = {
        'python': {
            'keywords': ['def ', 'class ', 'import ', 'from ', 'if __name__', 'print(', 'elif ', 'lambda ', 'numpy', 'pandas', 'self.'],
            'patterns': [r'^\s*#[^!]', r'"""', r"'''", r':\s*$', r'^\s*@', r'if\s+\w+:', r'for\s+\w+\s+in\s+'],
            'weight': 1.0
        },
        'javascript': {
            'keywords': ['function', 'const ', 'let ', 'var ', 'return', 'console.', '=>', 'async ', 'await '],
            'patterns': [r'===', r'!==', r'=>', r'\.then\s*\(', r'console\.log\(', r'\$\{', r'`'],
            'weight': 0.95
        },
        'java': {
            'keywords': ['public class', 'private', 'void', 'new ', 'extends', 'implements', 'System.out', 'public static'],
            'patterns': [r'@Override', r'System\.out\.println', r'public\s+static\s+void\s+main', r';$'],
            'weight': 1.0
        },
        'cpp': {
            'keywords': ['#include', 'using namespace', 'std::', 'cout <<', 'cin >>', 'template<'],
            'patterns': [r'#include\s*<', r'std::', r'<<', r'>>', r'->', r'::'],
            'weight': 0.95
        },
        'go': {
            'keywords': ['package ', 'import', 'func ', 'type ', 'struct ', ':=', 'fmt.'],
            'patterns': [r'package\s+main', r':=', r'func\s+\w+\s*\(', r'fmt\.Print'],
            'weight': 0.95
        },
        'rust': {
            'keywords': ['fn ', 'let ', 'mut ', 'use ', 'struct ', 'impl ', 'pub fn'],
            'patterns': [r'fn\s+main\s*\(', r'&mut', r'Option<', r'Result<', r'println!\('],
            'weight': 0.9
        },
        'ruby': {
            'keywords': ['def ', 'class ', 'module ', 'end', 'require ', 'puts '],
            'patterns': [r'def\s+\w+', r'puts\s+', r'\.new', r'@\w+'],
            'weight': 0.85
        },
        'php': {
            'keywords': ['<?php', 'function ', '$', 'echo ', 'class '],
            'patterns': [r'<\?php', r'\$\w+', r'->', r'echo\s+'],
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
            if re.search(pattern, code, re.MULTILINE):
                score += 1.2
                matches += 1
        
        # Normalize score
        if matches > 0:
            normalized_score = (score / total_patterns) * info['weight']
            match_ratio = matches / total_patterns
            
            if match_ratio > 0.3:
                normalized_score *= 1.2
            
            scores[lang] = min(normalized_score, 1.0)
    
    if scores:
        best_lang = max(scores.items(), key=lambda x: x[1])
        return best_lang[0], best_lang[1]
    
    return 'text', 0.0