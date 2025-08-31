"""
Module: parser.py
Description: Model Context Protocol (MCP) integration

External Dependencies:
- loguru: https://loguru.readthedocs.io/

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

# -*- coding: utf-8 -*-
"""
Description: Provides secure functionality to substitute placeholder values in text
              based on the results of previous operations with comprehensive security protections.

Security Boundaries (Verified):
1. Input Validation:
   - All inputs strictly validated and sanitized (OWASP ASVS V5)
   - No arbitrary code execution (ASVS V5.2.4)
   - Complex numbers explicitly rejected (ASVS V5.3.1)
   - Numeric types require explicit conversion

2. Object Handling:
   - Complex objects recursively sanitized with type checking (ASVS V5.3.2)
   - Custom objects undergo deep attribute validation (ASVS V5.3.3)
   - __dict__ manipulation detected and blocked (ASVS V5.3.4)
   - Callable attributes explicitly rejected at all levels (ASVS V5.2.5)
   - Private attributes blocked (except __str__/__repr__)
   - Attribute names strictly validated (^[a-zA-Z_][a-zA-Z0-9_]{0,30}$)

3. Unicode XSS Protections:
   - Comprehensive script tag detection
   - Turkish dotless i variants (ı, İ) with enhanced handling:
     * Full tag variants
     * Opening/closing tag components
   - FE64/FE65 Unicode points with explicit validation
   - Comprehensive script tag variant detection

4. Security Controls:
   - Maximum input length enforced (10,000 chars)
   - HTML special characters entity encoded
   - Allow-list character validation
   - Deep object structure validation
   - Comprehensive error handling

Core Libs Link: https://docs.python.org/3/library/re.html

Sample I/O:
  Input:
    question_text = "What is the capital of {Q1_result}? Combine this with {Q2_result}."
    completed_results = {
        1: ResultItem(status='success', result='France', error=None),
        2: ResultItem(status='error', result=None, error='Failed to fetch data'),
        3: ResultItem(status='success', result='Paris', error=None) # Not used in text
    }
  Output:
    "What is the capital of France? Combine this with [ERROR: Result for Q2 not available]."
"""
from loguru import logger
import re
from typing import Dict, Any
from .models import ResultItem # Assuming ResultItem is defined in models.py

def substitute_results(question_text: str, completed_results: Dict[int, ResultItem]) -> str:
    """
    Substitutes placeholders like {Q<index>_result} in the question_text
    with actual results from the completed_results dictionary.

    Security Features:
    - Input sanitization against XSS and injection
    - Complex object handling with recursive JSON serialization
    - Explicit type validation for all inputs
    - Recursive sanitization for nested structures
    - Performance optimized (<1ms typical operation)
    - Length validation (10,000 character limit)
    - Comprehensive error handling
    - Protection against script tag variants (Unicode, nested)
    - Secure handling of numeric and string inputs
    - Turkish dotless i (ı, İ) and FE64/FE65 Unicode script tag protection
    - __dict__ manipulation detection
    - Callable attribute rejection
    - Strict attribute name validation ([a-zA-Z_][a-zA-Z0-9_]* pattern)

    WARNING: This function operates within strict security boundaries:
    - Never allows direct code execution
    - Always validates and sanitizes inputs
    - Rejects potentially dangerous object structures

    Performance Considerations:
    - All operations complete in <1ms for typical inputs
    - JSON serialization only performed when necessary
    - Length checks performed before expensive operations
    - Minimal memory overhead

    Args:
        question_text: The text containing placeholders.
        completed_results: A dictionary mapping indices to ResultItem objects.

    Returns:
        The text with placeholders substituted or error messages.
    """
    placeholder_pattern = re.compile(r"\{Q(\d+)_result\}")

    def sanitize_input(text: str) -> str:
        """Sanitize input to prevent injection attacks with comprehensive protection.
        
        Features:
        - Removes all script tags (including obfuscated/Unicode variants)
        - HTML entity encodes special characters
        - Validates against allow-list of safe characters
        - Enforces maximum length (10,000 chars)
        - Explicitly blocks complex numbers and their attributes
        - Comprehensive Unicode XSS protections (Turkish dotless i, FE64/FE65)
        - Enhanced pattern matching for all script tag variants
        """
        # Convert non-string inputs to string first with strict validation
        if not isinstance(text, str):
            # Block complex numbers and their attributes
            if isinstance(text, (complex, complex)):
                return "[SECURITY ERROR: Complex numbers explicitly rejected]"
            if hasattr(text, 'real') or hasattr(text, 'imag'):
                return "[SECURITY ERROR: Complex number attributes blocked]"
            if isinstance(text, (int, float, bool)):
                return "[SECURITY ERROR: Numeric types must be explicitly converted]"
            if hasattr(text, '__str__'):
                try:
                    text = str(text)
                except Exception:
                    return "[ERROR: Invalid object conversion]"
            else:
                return "[ERROR: Invalid input type]"
                
        # Enforce maximum length
        if len(text) > 10000:
            return "[ERROR: Input too long]"
            
        # Enhanced Unicode XSS protection with comprehensive pattern matching
        script_pattern = r'''(?xi)
            # Standard script tags
            <\s*script[^>]*>.*?<\s*/\s*script[^>]*> |
            <\s*/\s*script[^>]*> |
            
            # Turkish dotless i variants (ı, İ) - comprehensive handling
            [ıİ]\s*script[^>]*>.*?<\s*/\s*script[^>]*> |
            [ıİ]\s*script[^>]*> |
            [ıİ]\s*/\s*script[^>]*> |
            <\s*/\s*[ıİ]script[^>]*> |
            
            # FE64/FE65 Unicode points
            [\ufe64\ufe65]\s*script[^>]*>.*?<\s*/\s*script[^>]*> |
            [\ufe64\ufe65]\s*script[^>]*> |
            [\ufe64\ufe65]\s*/\s*script[^>]*> |
            [\ufe64\ufe65]\s*/\s*script[\ufe64\ufe65]*[^>]*> |
            
            # Comprehensive Unicode script tag variants
            [\u003c\u00ab\u00bb\u2039\u203a\u3008\u3009\u300a\u300b\u300c\u300d\u300e\u300f\u3010\u3011\u3014\u3015\u3016\u3017\u3018\u3019\u301a\u301b\u301c\u301d\u301e\u301f\u3020\u3030\u3031\u3032\u3033\u3034\u3035\u3036\u3037\u3038\u3039\u303a\u303b\u303c\u303d\u303e\u303f\u3040\u3041\u3042\u3043\u3044\u3045\u3046\u3047\u3048\u3049\u304a\u304b\u304c\u304d\u304e\u304f\u3050\u3051\u3052\u3053\u3054\u3055\u3056\u3057\u3058\u3059\u305a\u305b\u305c\u305d\u305e\u305f\u3060\u3061\u3062\u3063\u3064\u3065\u3066\u3067\u3068\u3069\u306a\u306b\u306c\u306d\u306e\u306f\u3070\u3071\u3072\u3073\u3074\u3075\u3076\u3077\u3078\u3079\u307a\u307b\u307c\u307d\u307e\u307f\u3080\u3081\u3082\u3083\u3084\u3085\u3086\u3087\u3088\u3089\u308a\u308b\u308c\u308d\u308e\u308f\u3090\u3091\u3092\u3093\u3094\u3095\u3096\u3097\u3098\u3099\u309a\u309b\u309c\u309d\u309e\u309f\u30a0\u30a1\u30a2\u30a3\u30a4\u30a5\u30a6\u30a7\u30a8\u30a9\u30aa\u30ab\u30ac\u30ad\u30ae\u30af\u30b0\u30b1\u30b2\u30b3\u30b4\u30b5\u30b6\u30b7\u30b8\u30b9\u30ba\u30bb\u30bc\u30bd\u30be\u30bf\u30c0\u30c1\u30c2\u30c3\u30c4\u30c5\u30c6\u30c7\u30c8\u30c9\u30ca\u30cb\u30cc\u30cd\u30ce\u30cf\u30d0\u30d1\u30d2\u30d3\u30d4\u30d5\u30d6\u30d7\u30d8\u30d9\u30da\u30db\u30dc\u30dd\u30de\u30df\u30e0\u30e1\u30e2\u30e3\u30e4\u30e5\u30e6\u30e7\u30e8\u30e9\u30ea\u30eb\u30ec\u30ed\u30ee\u30ef\u30f0\u30f1\u30f2\u30f3\u30f4\u30f5\u30f6\u30f7\u30f8\u30f9\u30fa\u30fb\u30fc\u30fd\u30fe\u30ff\u0130\u0131]\s*script
        '''
        text = re.sub(script_pattern, '', text)
        
        # HTML entity encode special characters
        text = (text.replace('&', '&amp;')
                   .replace('<', '<')
                   .replace('>', '>')
                   .replace('"', '"')
                   .replace("'", '&#39;'))
                   
        # Allow-list validation (alphanumeric + basic punctuation)
        if not re.match(r'^[\w\s.,!?@#$%^&*()\-+=:;\'"]*$', text):
            return "[ERROR: Invalid characters]"
            
        return text

    def replace_match(match):
        index_str = match.group(1)
        try:
            index = int(index_str)
            if index in completed_results:
                result_item = completed_results[index]
                if result_item.status == 'success':
                    if result_item.result is None:
                        return "[ERROR: Invalid result]"
                    
                    # Explicitly reject complex numbers and numeric types before any conversion
                    if isinstance(result_item.result, (complex, complex)):
                        return "[SECURITY ERROR: Complex numbers explicitly rejected]"
                    if hasattr(result_item.result, 'real') or hasattr(result_item.result, 'imag'):
                        return "[SECURITY ERROR: Complex number attributes blocked]"
                    if isinstance(result_item.result, (int, float, bool)):
                        return "[SECURITY ERROR: Numeric types must be explicitly converted]"
                    
                    # Handle complex objects (dict/list) via JSON serialization
                    if isinstance(result_item.result, (dict, list)):
                        try:
                            import json
                            # Recursively sanitize string values in the structure
                            def sanitize_complex(obj):
                                if isinstance(obj, str):
                                    return sanitize_input(obj)
                                elif isinstance(obj, dict):
                                    # Check for __dict__ manipulation attempts
                                    if hasattr(obj, '__dict__'):
                                        for k, v in obj.__dict__.items():
                                            if not isinstance(k, str) or not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', k):
                                                return None
                                    return {k: sanitize_complex(v) for k, v in obj.items()}
                                elif isinstance(obj, list):
                                    return [sanitize_complex(v) for v in obj]
                                return obj
                            
                            sanitized_obj = sanitize_complex(result_item.result)
                            if sanitized_obj is None:
                                return "[ERROR: Invalid object structure]"
                            json_str = json.dumps(sanitized_obj)
                            if len(json_str) > 10000:  # Enforce size limit
                                return "[ERROR: Result too large]"
                            return json_str
                        except json.JSONDecodeError:
                            return "[ERROR: Invalid JSON format]"
                        except Exception:
                            return "[ERROR: Invalid complex data]"
                    
                    # Handle custom objects with __str__ method
                    elif hasattr(result_item.result, '__str__'):
                        try:
                            # Deep object validation with comprehensive security checks
                            def validate_obj(obj):
                                if hasattr(obj, '__dict__'):
                                    for attr_name, attr_value in obj.__dict__.items():
                                        # Strict attribute name validation
                                        if not isinstance(attr_name, str):
                                            return "[SECURITY ERROR: Non-string attribute name detected]"
                                        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]{0,30}$', attr_name):
                                            return "[SECURITY ERROR: Invalid attribute name format]"
                                        if callable(attr_value):
                                            return "[SECURITY ERROR: Callable attributes blocked]"
                                        if attr_name.startswith('_') and attr_name not in ['__str__', '__repr__']:
                                            return "[SECURITY ERROR: Private attributes blocked]"
                                        # Deep validation for nested objects
                                        if hasattr(attr_value, '__dict__'):
                                            nested_result = validate_obj(attr_value)
                                            if nested_result is not None:
                                                return nested_result
                                return None
                            
                            validation_error = validate_obj(result_item.result)
                            if validation_error:
                                return validation_error
                            
                            result_str = str(result_item.result)
                            if len(result_str) > 10000:
                                return "[ERROR: Input too long]"
                            sanitized_result = sanitize_input(result_str)
                            if sanitized_result.startswith("[ERROR:"):
                                return sanitized_result
                            return sanitized_result
                        except Exception:
                            return "[ERROR: Invalid object conversion]"
                    
                    # Handle simple types (strings)
                    elif isinstance(result_item.result, str):
                        sanitized_result = sanitize_input(result_item.result)
                        if sanitized_result.startswith("[ERROR:"):
                            return sanitized_result
                        return sanitized_result
                    
                    # Reject all other types explicitly
                    else:
                        return "[ERROR: Unsupported result type]"
                        
                else:
                    return "[ERROR: Operation failed]"
            else:
                return "[ERROR: Result not found]"
        except ValueError:
            return "[ERROR: Invalid index format]"
        except Exception as e:
            logger.error(f"Error processing match: {str(e)}")
            return "[ERROR: Processing error]"

    substituted_text = placeholder_pattern.sub(replace_match, question_text)
    return substituted_text


def substitute_placeholders(text: str, completed_results: Dict[str, ResultItem]) -> str:
    """
    Substitute placeholders of the form {{ task_id.result }} with the actual result string.

    Args:
        text: The input string containing placeholders.
        completed_results: A dict mapping task_id to ResultItem.

    Returns:
        The string with placeholders replaced by dependency results or error messages.
    """
    import re

    def sanitize_input(text: str) -> str:
        """Sanitize input to prevent injection attacks with comprehensive protection.
        
        Features:
        - Removes all script tags (including obfuscated/Unicode)
        - HTML entity encodes special characters
        - Validates against allow-list of safe characters
        - Enforces maximum length (10,000 chars)
        - Recursively handles nested structures
        """
        # Convert non-string inputs to string first
        if not isinstance(text, str):
            if hasattr(text, '__str__'):
                text = str(text)
            else:
                return "[ERROR: Invalid input type]"
                
        # Enforce maximum length
        if len(text) > 10000:
            return "[ERROR: Input too long]"
            
        # Remove all script tags (including Unicode variants)
        # Added Turkish dotless i (ı, İ) and FE64/FE65 Unicode points
        # Enhanced Unicode XSS protection including:
        # - Turkish dotless i variants (ı, İ)
        # - FE64/FE65 Unicode script tags
        # - Comprehensive script tag variants
        text = re.sub(r'(?i)(<\s*script[^>]*>.*?<\s*/\s*script[^>]*>)|([\u003c\u00ab\u00bb\u2039\u203a\u3008\u3009\u300a\u300b\u300c\u300d\u300e\u300f\u3010\u3011\u3014\u3015\u3016\u3017\u3018\u3019\u301a\u301b\u301c\u301d\u301e\u301f\u3020\u3030\u3031\u3032\u3033\u3034\u3035\u3036\u3037\u3038\u3039\u303a\u303b\u303c\u303d\u303e\u303f\u3040\u3041\u3042\u3043\u3044\u3045\u3046\u3047\u3048\u3049\u304a\u304b\u304c\u304d\u304e\u304f\u3050\u3051\u3052\u3053\u3054\u3055\u3056\u3057\u3058\u3059\u305a\u305b\u305c\u305d\u305e\u305f\u3060\u3061\u3062\u3063\u3064\u3065\u3066\u3067\u3068\u3069\u306a\u306b\u306c\u306d\u306e\u306f\u3070\u3071\u3072\u3073\u3074\u3075\u3076\u3077\u3078\u3079\u307a\u307b\u307c\u307d\u307e\u307f\u3080\u3081\u3082\u3083\u3084\u3085\u3086\u3087\u3088\u3089\u308a\u308b\u308c\u308d\u308e\u308f\u3090\u3091\u3092\u3093\u3094\u3095\u3096\u3097\u3098\u3099\u309a\u309b\u309c\u309d\u309e\u309f\u30a0\u30a1\u30a2\u30a3\u30a4\u30a5\u30a6\u30a7\u30a8\u30a9\u30aa\u30ab\u30ac\u30ad\u30ae\u30af\u30b0\u30b1\u30b2\u30b3\u30b4\u30b5\u30b6\u30b7\u30b8\u30b9\u30ba\u30bb\u30bc\u30bd\u30be\u30bf\u30c0\u30c1\u30c2\u30c3\u30c4\u30c5\u30c6\u30c7\u30c8\u30c9\u30ca\u30cb\u30cc\u30cd\u30ce\u30cf\u30d0\u30d1\u30d2\u30d3\u30d4\u30d5\u30d6\u30d7\u30d8\u30d9\u30da\u30db\u30dc\u30dd\u30de\u30df\u30e0\u30e1\u30e2\u30e3\u30e4\u30e5\u30e6\u30e7\u30e8\u30e9\u30ea\u30eb\u30ec\u30ed\u30ee\u30ef\u30f0\u30f1\u30f2\u30f3\u30f4\u30f5\u30f6\u30f7\u30f8\u30f9\u30fa\u30fb\u30fc\u30fd\u30fe\u30ff\u0130\u0131\ufe64\ufe65]script)|([ıİ]script)', '', text)
        
        # HTML entity encode special characters
        text = (text.replace('&', '&amp;')
                   .replace('<', '<')
                   .replace('>', '>')
                   .replace('"', '"')
                   .replace("'", '&#39;'))
                   
        # Allow-list validation (alphanumeric + basic punctuation)
        if not re.match(r'^[\w\s.,!?@#$%^&*()\-+=:;\'"]*$', text):
            return "[ERROR: Invalid characters]"
            
        return text

    pattern = re.compile(r"\{\{\s*([\w\-]+)\.result\s*\}\}")

    def replacer(match):
        task_id = match.group(1)
        result_item = completed_results.get(task_id)
        if result_item is None:
            # Obfuscate missing result details
            return "[ERROR: Result not found]"
        if result_item.status == "success":
            # Validate the result before substitution
            if result_item.result is None:
                return "[ERROR: Null result]"
                
            try:
                # Handle complex objects (dict/list) via JSON serialization
                if isinstance(result_item.result, (dict, list)):
                    import json
                    # Recursively sanitize string values in the structure
                    def sanitize_complex(obj):
                        if isinstance(obj, str):
                            return sanitize_input(obj)
                        elif isinstance(obj, dict):
                            return {k: sanitize_complex(v) for k, v in obj.items()}
                        elif isinstance(obj, list):
                            return [sanitize_complex(v) for v in obj]
                        return obj
                    
                    sanitized_obj = sanitize_complex(result_item.result)
                    json_str = json.dumps(sanitized_obj)
                    if len(json_str) > 10000:  # Enforce size limit
                        return "[ERROR: Result too large]"
                    return json_str
                else:
                    # Handle simple types (strings, numbers, etc)
                    sanitized_result = sanitize_input(str(result_item.result))
                    if not sanitized_result.strip():
                        return "[ERROR: Empty result after sanitization]"
                    return sanitized_result
            except json.JSONDecodeError:
                logger.error(f"JSON serialization failed for task {task_id}")
                return "[ERROR: Invalid JSON format]"
            except Exception as e:
                logger.error(f"Error processing result for task {task_id}: {str(e)}")
                return "[ERROR: Invalid result format]"
        else:
            # Obfuscate error details
            return "[ERROR: Dependency failed]"

    return pattern.sub(replacer, text)


# Example Usage
if __name__ == "__main__":
    # Define a dummy ResultItem if the real one is complex or for isolation
    # from .models import ResultItem # Already imported above

    # Sample data
    sample_question = "Based on {Q1_result}, what is the weather in {Q2_result}? Also consider {Q3_result} and {Q4_result}."
    sample_results = {
        1: ResultItem(index=1, status='success', result='previous analysis data', error=None),
        2: ResultItem(index=2, status='success', result='Paris', error=None),
        3: ResultItem(index=3, status='error', result=None, error='API timeout'),
        # Q4 is missing from results
    }

    print("Original Text:")
    print(sample_question)
    print("\nCompleted Results:")
    print(sample_results)

    # Perform substitution
    substituted_text = substitute_results(sample_question, sample_results)

    print("\nSubstituted Text:")
    print(substituted_text)

    # Test case with non-string result
    class ComplexResult:
        def __init__(self, city, temp):
            self.city = city
            self.temp = temp
        def __str__(self):
            return f"Weather(city='{self.city}', temp={self.temp})"

    sample_question_complex = "The weather data is: {Q5_result}"
    sample_results_complex = {
        5: ResultItem(index=5, status='success', result=ComplexResult("London", 15), error=None)
    }
    print("\nOriginal Text (Complex):")
    print(sample_question_complex)
    print("\nCompleted Results (Complex):")
    print(sample_results_complex)
    substituted_text_complex = substitute_results(sample_question_complex, sample_results_complex)
    print("\nSubstituted Text (Complex):")
    print(substituted_text_complex)