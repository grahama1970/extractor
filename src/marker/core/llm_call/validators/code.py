"""Code-specific validators for LLM validation."""

from typing import Any, Dict, List, Optional
import ast
import re

from marker.core.llm_call.core.base import ValidationResult
from marker.core.llm_call.validators.base import BaseValidator
from marker.core.llm_call.core.strategies import validator


@validator("python_syntax")
class PythonSyntaxValidator(BaseValidator):
    """Validates Python code syntax."""
    
    def __init__(self, check_imports: bool = True, check_style: bool = False):
        """Initialize Python syntax validator.
        
        Args:
            check_imports: Whether to check import statements
            check_style: Whether to check basic style guidelines
        """
        self.check_imports = check_imports
        self.check_style = check_style
    
    @property
    def name(self) -> str:
        checks = []
        if self.check_imports:
            checks.append("imports")
        if self.check_style:
            checks.append("style")
        checks_str = f"(checks={','.join(checks)})" if checks else ""
        return f"python_syntax{checks_str}"
    
    @property
    def description(self) -> str:
        return "Validates Python code syntax and structure"
    
    def validate(self, response: Any, context: Dict[str, Any]) -> ValidationResult:
        """Validate Python syntax."""
        # Extract code from response
        if hasattr(response, 'code'):
            code = response.code
        elif isinstance(response, dict) and 'code' in response:
            code = response['code']
        elif isinstance(response, str):
            code = response
        else:
            return ValidationResult(
                valid=False,
                error=f"Could not extract code from response type: {type(response)}"
            )
        
        errors = []
        suggestions = []
        debug_info = {}
        
        # Check basic syntax
        try:
            ast.parse(code)
            debug_info["syntax_valid"] = True
        except SyntaxError as e:
            errors.append(f"Syntax error: {e.msg} at line {e.lineno}")
            suggestions.append(f"Fix syntax error at line {e.lineno}: {e.msg}")
            debug_info["syntax_valid"] = False
            debug_info["syntax_error"] = str(e)
        
        if self.check_imports and debug_info.get("syntax_valid", False):
            # Check import statements
            tree = ast.parse(code)
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    for alias in node.names:
                        imports.append(f"{module}.{alias.name}")
            
            debug_info["imports"] = imports
            
            # Check for common import issues
            if any(imp.startswith("from .") for imp in imports):
                errors.append("Relative imports found")
                suggestions.append("Use absolute imports instead of relative imports")
        
        if self.check_style:
            # Basic style checks
            lines = code.split('\n')
            for i, line in enumerate(lines):
                # Check line length
                if len(line) > 88:  # Black's default
                    errors.append(f"Line {i+1} exceeds 88 characters")
                    suggestions.append(f"Break line {i+1} into multiple lines")
                
                # Check for tabs
                if '\t' in line:
                    errors.append(f"Line {i+1} contains tabs")
                    suggestions.append("Use spaces instead of tabs")
        
        if errors:
            return ValidationResult(
                valid=False,
                error="; ".join(errors),
                suggestions=suggestions,
                debug_info=debug_info
            )
        
        return ValidationResult(
            valid=True,
            debug_info=debug_info
        )


@validator("code_language")
class CodeLanguageValidator(BaseValidator):
    """Validates code language detection and consistency."""
    
    def __init__(self, 
                 expected_language: Optional[str] = None,
                 allowed_languages: Optional[List[str]] = None):
        """Initialize code language validator.
        
        Args:
            expected_language: Expected programming language
            allowed_languages: List of allowed languages
        """
        self.expected_language = expected_language
        self.allowed_languages = allowed_languages or []
    
    @property
    def name(self) -> str:
        if self.expected_language:
            return f"code_language(expected={self.expected_language})"
        elif self.allowed_languages:
            return f"code_language(allowed={self.allowed_languages})"
        return "code_language"
    
    @property
    def description(self) -> str:
        return "Validates code language detection"
    
    def validate(self, response: Any, context: Dict[str, Any]) -> ValidationResult:
        """Validate code language."""
        # Extract language from response
        if hasattr(response, 'language'):
            language = response.language
        elif isinstance(response, dict) and 'language' in response:
            language = response['language']
        else:
            # Try to detect from code block
            if hasattr(response, 'code'):
                code = response.code
            elif isinstance(response, dict) and 'code' in response:
                code = response['code']
            elif isinstance(response, str):
                code = response
            else:
                return ValidationResult(
                    valid=False,
                    error="Could not extract language or code from response"
                )
            
            # Simple language detection based on patterns
            language = self._detect_language(code)
        
        if not language:
            return ValidationResult(
                valid=False,
                error="Could not detect programming language",
                suggestions=["Specify the programming language explicitly"]
            )
        
        errors = []
        suggestions = []
        
        if self.expected_language and language.lower() != self.expected_language.lower():
            errors.append(f"Expected {self.expected_language}, got {language}")
            suggestions.append(f"Use {self.expected_language} instead of {language}")
        
        if self.allowed_languages and language.lower() not in [l.lower() for l in self.allowed_languages]:
            errors.append(f"Language {language} not in allowed list: {self.allowed_languages}")
            suggestions.append(f"Use one of: {', '.join(self.allowed_languages)}")
        
        if errors:
            return ValidationResult(
                valid=False,
                error="; ".join(errors),
                suggestions=suggestions,
                debug_info={"detected_language": language}
            )
        
        return ValidationResult(
            valid=True,
            debug_info={"detected_language": language}
        )
    
    def _detect_language(self, code: str) -> Optional[str]:
        """Simple language detection based on patterns."""
        patterns = {
            "python": [r"def\s+\w+\s*\(", r"import\s+\w+", r"print\s*\(", r"class\s+\w+"],
            "javascript": [r"function\s+\w+\s*\(", r"const\s+\w+", r"let\s+\w+", r"console\.log"],
            "java": [r"public\s+class", r"public\s+static\s+void", r"import\s+java\."],
            "c++": [r"#include\s*<", r"using\s+namespace", r"int\s+main\s*\("],
            "rust": [r"fn\s+\w+\s*\(", r"let\s+mut\s+", r"use\s+std::", r"impl\s+\w+"],
        }
        
        for language, language_patterns in patterns.items():
            for pattern in language_patterns:
                if re.search(pattern, code):
                    return language
        
        return None


@validator("code_completeness")
class CodeCompletenessValidator(BaseValidator):
    """Validates code completeness and structure."""
    
    def __init__(self,
                 require_main: bool = False,
                 require_imports: bool = True,
                 require_docstrings: bool = False):
        """Initialize code completeness validator.
        
        Args:
            require_main: Whether to require a main function/block
            require_imports: Whether to require import statements
            require_docstrings: Whether to require docstrings
        """
        self.require_main = require_main
        self.require_imports = require_imports
        self.require_docstrings = require_docstrings
    
    @property
    def name(self) -> str:
        requirements = []
        if self.require_main:
            requirements.append("main")
        if self.require_imports:
            requirements.append("imports")
        if self.require_docstrings:
            requirements.append("docstrings")
        req_str = f"(require={','.join(requirements)})" if requirements else ""
        return f"code_completeness{req_str}"
    
    @property
    def description(self) -> str:
        return "Validates code completeness and required elements"
    
    def validate(self, response: Any, context: Dict[str, Any]) -> ValidationResult:
        """Validate code completeness."""
        # Extract code from response
        if hasattr(response, 'code'):
            code = response.code
        elif isinstance(response, dict) and 'code' in response:
            code = response['code']
        elif isinstance(response, str):
            code = response
        else:
            return ValidationResult(
                valid=False,
                error=f"Could not extract code from response type: {type(response)}"
            )
        
        errors = []
        suggestions = []
        debug_info = {}
        
        try:
            tree = ast.parse(code)
            
            if self.require_main:
                # Check for main function or if __name__ == "__main__" block
                has_main = False
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef) and node.name == "main":
                        has_main = True
                        break
                    elif isinstance(node, ast.If):
                        # Check for if __name__ == "__main__"
                        if (isinstance(node.test, ast.Compare) and
                            isinstance(node.test.left, ast.Name) and
                            node.test.left.id == "__name__"):
                            has_main = True
                            break
                
                if not has_main:
                    errors.append("Missing main function or entry point")
                    suggestions.append("Add a main() function or if __name__ == '__main__' block")
                debug_info["has_main"] = has_main
            
            if self.require_imports:
                # Check for import statements
                has_imports = any(isinstance(node, (ast.Import, ast.ImportFrom)) 
                                for node in ast.walk(tree))
                if not has_imports:
                    errors.append("No import statements found")
                    suggestions.append("Add necessary import statements")
                debug_info["has_imports"] = has_imports
            
            if self.require_docstrings:
                # Check for docstrings in functions and classes
                missing_docstrings = []
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                        if not ast.get_docstring(node):
                            missing_docstrings.append(node.name)
                
                if missing_docstrings:
                    errors.append(f"Missing docstrings for: {', '.join(missing_docstrings)}")
                    suggestions.append("Add docstrings to all functions and classes")
                debug_info["missing_docstrings"] = missing_docstrings
            
        except SyntaxError:
            errors.append("Cannot parse code due to syntax errors")
            suggestions.append("Fix syntax errors first")
        
        if errors:
            return ValidationResult(
                valid=False,
                error="; ".join(errors),
                suggestions=suggestions,
                debug_info=debug_info
            )
        
        return ValidationResult(
            valid=True,
            debug_info=debug_info
        )