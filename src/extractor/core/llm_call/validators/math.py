"""Math-specific validators for LLM validation."""
Module: math.py

from typing import Any, Dict, List, Optional
import re

from extractor.core.llm_call.core.base import ValidationResult
from extractor.core.llm_call.validators.base import BaseValidator
from extractor.core.llm_call.core.strategies import validator


@validator("latex_syntax")
class LaTeXSyntaxValidator(BaseValidator):
    """Validates LaTeX syntax for mathematical expressions."""
    
    def __init__(self,
                 check_delimiters: bool = True,
                 check_commands: bool = True,
                 check_brackets: bool = True):
        """Initialize LaTeX validator.
        
        Args:
            check_delimiters: Check for matching $ or $$ delimiters
            check_commands: Check for valid LaTeX commands
            check_brackets: Check for matching brackets
        """
        self.check_delimiters = check_delimiters
        self.check_commands = check_commands
        self.check_brackets = check_brackets
    
    @property
    def name(self) -> str:
        checks = []
        if self.check_delimiters:
            checks.append("delimiters")
        if self.check_commands:
            checks.append("commands")
        if self.check_brackets:
            checks.append("brackets")
        return f"latex_syntax(checks={','.join(checks)})"
    
    @property
    def description(self) -> str:
        return "Validates LaTeX mathematical expressions"
    
    def validate(self, response: Any, context: Dict[str, Any]) -> ValidationResult:
        """Validate LaTeX syntax."""
        # Extract LaTeX from response
        if hasattr(response, 'latex'):
            latex = response.latex
        elif isinstance(response, dict) and 'latex' in response:
            latex = response['latex']
        elif isinstance(response, str):
            latex = response
        else:
            return ValidationResult(
                valid=False,
                error=f"Could not extract LaTeX from response type: {type(response)}"
            )
        
        errors = []
        suggestions = []
        
        if self.check_delimiters:
            # Check for matching $ delimiters
            single_dollar_count = latex.count('$') - latex.count('$$') * 2
            if single_dollar_count % 2 != 0:
                errors.append("Unmatched $ delimiter")
                suggestions.append("Ensure all $ delimiters are properly paired")
            
            # Check for matching $$ delimiters
            double_dollar_count = latex.count('$$')
            if double_dollar_count % 2 != 0:
                errors.append("Unmatched $$ delimiter")
                suggestions.append("Ensure all $$ delimiters are properly paired")
        
        if self.check_brackets:
            # Check for matching brackets
            bracket_pairs = [
                ('{', '}'),
                ('[', ']'),
                ('(', ')'),
                ('\\{', '\\}'),
                ('\\[', '\\]'),
                ('\\(', '\\)')
            ]
            
            for open_bracket, close_bracket in bracket_pairs:
                open_count = latex.count(open_bracket)
                close_count = latex.count(close_bracket)
                if open_count != close_count:
                    errors.append(f"Unmatched {open_bracket} {close_bracket} brackets: {open_count} vs {close_count}")
                    suggestions.append(f"Check matching of {open_bracket} {close_bracket} brackets")
        
        if self.check_commands:
            # Check for common LaTeX command errors
            common_errors = {
                r'\\fraction': "Use \\frac instead of \\fraction",
                r'\\sqrt\[': "Use \\sqrt{} for square root or \\sqrt[n]{} for nth root",
                r'\^([^{])': "Use ^{} for superscripts with multiple characters",
                r'_([^{])': "Use _{} for subscripts with multiple characters"
            }
            
            for pattern, suggestion in common_errors.items():
                if re.search(pattern, latex):
                    errors.append(f"Invalid LaTeX syntax: {pattern}")
                    suggestions.append(suggestion)
        
        if errors:
            return ValidationResult(
                valid=False,
                error="; ".join(errors),
                suggestions=suggestions,
                debug_info={"latex_length": len(latex)}
            )
        
        return ValidationResult(
            valid=True,
            debug_info={"latex_length": len(latex)}
        )


@validator("math_consistency")
class MathConsistencyValidator(BaseValidator):
    """Validates mathematical consistency in expressions."""
    
    def __init__(self,
                 check_units: bool = True,
                 check_variables: bool = True):
        """Initialize math consistency validator.
        
        Args:
            check_units: Check for consistent unit usage
            check_variables: Check for consistent variable usage
        """
        self.check_units = check_units
        self.check_variables = check_variables
    
    @property
    def name(self) -> str:
        checks = []
        if self.check_units:
            checks.append("units")
        if self.check_variables:
            checks.append("variables")
        return f"math_consistency(checks={','.join(checks)})"
    
    @property
    def description(self) -> str:
        return "Validates mathematical consistency"
    
    def validate(self, response: Any, context: Dict[str, Any]) -> ValidationResult:
        """Validate mathematical consistency."""
        # Extract math content from response
        if hasattr(response, 'math'):
            math_content = response.math
        elif isinstance(response, dict) and 'math' in response:
            math_content = response['math']
        elif isinstance(response, str):
            math_content = response
        else:
            return ValidationResult(
                valid=False,
                error=f"Could not extract math content from response type: {type(response)}"
            )
        
        errors = []
        suggestions = []
        debug_info = {}
        
        if self.check_variables:
            # Extract variables (simple pattern - can be enhanced)
            variable_pattern = r'\b[a-zA-Z]\b(?![a-zA-Z])'
            variables = re.findall(variable_pattern, math_content)
            unique_vars = set(variables)
            
            # Check if variables are defined before use
            # This is a simplified check - would need more context
            debug_info["variables"] = list(unique_vars)
            
            # Check for undefined variables in context
            if context.get("defined_variables"):
                undefined_vars = unique_vars - set(context["defined_variables"])
                if undefined_vars:
                    errors.append(f"Undefined variables: {', '.join(undefined_vars)}")
                    suggestions.append("Define all variables before use")
        
        if self.check_units:
            # Simple unit checking - look for common unit patterns
            unit_pattern = r'\b(m|kg|s|m\/s|km\/h|N|J|W)\b'
            units = re.findall(unit_pattern, math_content)
            if units:
                debug_info["units_found"] = units
                # Could add more sophisticated unit consistency checking
        
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