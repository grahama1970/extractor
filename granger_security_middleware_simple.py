#!/usr/bin/env python3
"""
Module: granger_security_middleware_simple.py
Description: Security middleware for Granger modules without external dependencies

Sample Input:
>>> request = {"token": "granger_valid_token_123", "query": "SELECT * FROM users WHERE id = 1"}

Expected Output:
>>> validate_request(request)
{"valid": True, "user": "authenticated_user", "sanitized_query": "SELECT * FROM users WHERE id = 1"}
"""

import re
import hashlib
import secrets
import time
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from functools import wraps
from collections import defaultdict

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class SecurityConfig:
    """Security configuration for Granger modules"""
    min_token_length: int = 20
    token_prefix: str = "granger_"
    max_login_attempts: int = 5
    lockout_duration: int = 300  # 5 minutes
    rate_limit_requests: int = 100
    rate_limit_window: int = 60  # 1 minute
    sql_keywords_blacklist: List[str] = None
    
    def __post_init__(self):
        if self.sql_keywords_blacklist is None:
            self.sql_keywords_blacklist = [
                "DROP", "DELETE", "TRUNCATE", "ALTER", "CREATE",
                "GRANT", "REVOKE", "--", "/*", "*/", "xp_", "sp_",
                "UNION", "';", '";'
            ]


class SQLInjectionProtector:
    """Protect against SQL injection attacks"""
    
    def __init__(self, config: SecurityConfig):
        self.config = config
        # Common SQL injection patterns
        self.injection_patterns = [
            r"('\s*OR\s*'1'\s*=\s*'1)",  # ' OR '1'='1
            r"('\s*OR\s+1\s*=\s*1)",      # ' OR 1=1
            r"(--\s*$)",                   # SQL comment at end
            r"(/\*.*\*/)",                 # Block comments
            r"(;\s*DROP\s+TABLE)",         # ; DROP TABLE
            r"(;\s*DELETE\s+FROM)",        # ; DELETE FROM
            r"(UNION\s+SELECT)",           # UNION SELECT
            r"(INTO\s+OUTFILE)",           # INTO OUTFILE
            r"(EXEC\s*\()",                # EXEC(
        ]
        self.pattern = re.compile("|".join(self.injection_patterns), re.IGNORECASE)
    
    def is_safe_input(self, user_input: str) -> Tuple[bool, Optional[str]]:
        """Check if input is safe from SQL injection"""
        if not user_input:
            return True, None
        
        # Check for injection patterns
        if self.pattern.search(user_input):
            return False, "Potential SQL injection detected"
        
        # Check for dangerous keywords
        upper_input = user_input.upper()
        for keyword in self.config.sql_keywords_blacklist:
            if keyword in upper_input:
                # Allow SELECT in read-only contexts
                if keyword == "SELECT" and not any(bad in upper_input for bad in ["DROP", "DELETE", "UPDATE"]):
                    continue
                return False, f"Dangerous SQL keyword detected: {keyword}"
        
        # Check for suspicious character combinations
        if "';" in user_input or '";' in user_input:
            return False, "Suspicious character combination detected"
        
        return True, None
    
    def sanitize_input(self, user_input: str) -> str:
        """Sanitize user input to prevent SQL injection"""
        if not user_input:
            return ""
        
        # Remove SQL comments
        sanitized = re.sub(r"(--|#|/\*|\*/)", "", user_input)
        
        # Escape quotes properly
        sanitized = sanitized.replace("'", "''")
        
        # Remove null bytes and other dangerous characters
        sanitized = re.sub(r"[\x00\x1a;]", "", sanitized)
        
        return sanitized.strip()


class TokenValidator:
    """Validate authentication tokens"""
    
    def __init__(self, config: SecurityConfig):
        self.config = config
        self.failed_attempts = defaultdict(int)
        self.lockouts = {}
    
    def validate_token(self, token: Any) -> Tuple[bool, Optional[str]]:
        """Validate authentication token"""
        # Check if empty or None
        if not token:
            return False, "Missing authentication token"
        
        # Check type
        if not isinstance(token, str):
            return False, "Invalid token format - must be string"
        
        # Check for empty string
        if token.strip() == "":
            return False, "Empty authentication token"
        
        # Check prefix
        if not token.startswith(self.config.token_prefix):
            return False, f"Invalid token prefix - must start with '{self.config.token_prefix}'"
        
        # Check length
        if len(token) < self.config.min_token_length:
            return False, f"Token too short - minimum {self.config.min_token_length} characters"
        
        # Check for SQL injection in token
        if any(char in token for char in ["'", '"', ";", "--", "/*", "*/"]):
            return False, "Invalid characters in token - possible injection attempt"
        
        # Check format
        if not re.match(r"^granger_[a-zA-Z0-9_]{16,}$", token):
            return False, "Invalid token format"
        
        return True, None


class GrangerSecurity:
    """Main security middleware for Granger ecosystem"""
    
    def __init__(self, config: Optional[SecurityConfig] = None):
        self.config = config or SecurityConfig()
        self.token_validator = TokenValidator(self.config)
        self.sql_protector = SQLInjectionProtector(self.config)
    
    def validate_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Validate entire request for security issues"""
        result = {
            "valid": False,
            "errors": [],
            "warnings": [],
            "sanitized": {}
        }
        
        # Validate token
        token = request.get("token") or request.get("auth") or request.get("authorization", "")
        token_valid, token_error = self.token_validator.validate_token(token)
        
        if not token_valid:
            result["errors"].append(token_error or "Invalid token")
            return result
        
        # Check all string fields for SQL injection
        for key, value in request.items():
            if isinstance(value, str):
                safe, error = self.sql_protector.is_safe_input(value)
                if not safe:
                    result["errors"].append(f"Security issue in '{key}': {error}")
                    return result
                
                # Sanitize the input
                result["sanitized"][key] = self.sql_protector.sanitize_input(value)
            else:
                result["sanitized"][key] = value
        
        # Valid request
        result["valid"] = True
        result["user"] = "authenticated_user"
        
        return result
    
    def remove_stack_traces(self, error_message: str) -> str:
        """Remove stack traces and sensitive info from error messages"""
        if not error_message:
            return ""
        
        # Remove file paths
        cleaned = re.sub(r'File "[^"]+", line \d+', 'File [hidden]', error_message)
        cleaned = re.sub(r'/(home|usr|var|etc|Users)/[^\s]+', '/[hidden]', cleaned)
        
        # Remove memory addresses
        cleaned = re.sub(r'at 0x[0-9a-fA-F]+', 'at [address]', cleaned)
        
        # Remove line numbers and function names that might reveal structure
        cleaned = re.sub(r'in \w+\(\)', 'in function()', cleaned)
        
        # Remove sensitive keywords (case-insensitive)
        sensitive_words = [
            'password', 'secret', 'token', 'api_key', 'apikey', 
            'private', 'credential', 'auth', 'bearer', 'jwt',
            'session', 'cookie', 'hash', 'salt', 'encrypt'
        ]
        for word in sensitive_words:
            # Replace the word preserving case for first letter if possible
            cleaned = re.sub(rf'\b{word}\b', '[redacted]', cleaned, flags=re.IGNORECASE)
        
        # Remove any remaining class names that might leak info
        cleaned = re.sub(r'([A-Z][a-zA-Z]+Error)\b', 'Error', cleaned)
        
        # Clean up any double spaces or newlines
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        # Truncate if too long
        if len(cleaned) > 200:
            cleaned = cleaned[:197] + "..."
        
        return cleaned


# Module validation
if __name__ == "__main__":
    security = GrangerSecurity()
    
    # Test cases
    test_cases = [
        # Valid token
        {
            "name": "Valid token",
            "request": {"token": "granger_valid_token_12345678901234567890", "query": "SELECT * FROM users"},
            "expected": True
        },
        # Empty token
        {
            "name": "Empty token",
            "request": {"token": "", "query": "SELECT * FROM users"},
            "expected": False
        },
        # SQL injection
        {
            "name": "SQL injection",
            "request": {"token": "granger_valid_token_123", "query": "'; DROP TABLE users; --"},
            "expected": False
        },
        # None token
        {
            "name": "None token",
            "request": {"token": None, "data": "test"},
            "expected": False
        },
        # JWT none algorithm attempt
        {
            "name": "JWT none algorithm",
            "request": {"token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJub25lIn0.eyJyb2xlIjoiYWRtaW4ifQ.", "action": "delete"},
            "expected": False
        },
        # OR 1=1 injection
        {
            "name": "OR 1=1 injection",
            "request": {"token": "granger_test_token_12345", "password": "' OR '1'='1"},
            "expected": False
        },
        # Valid request with special chars
        {
            "name": "Valid with special chars",
            "request": {"token": "granger_test_token_12345", "name": "O'Brien"},
            "expected": True
        }
    ]
    
    print("Testing Granger Security Middleware\n")
    print("="*60)
    
    passed = 0
    failed = 0
    
    for test in test_cases:
        result = security.validate_request(test["request"])
        success = (result["valid"] == test["expected"])
        
        status = "✅ PASS" if success else "❌ FAIL"
        if success:
            passed += 1
        else:
            failed += 1
            
        print(f"\nTest: {test['name']}")
        print(f"Expected: {'Valid' if test['expected'] else 'Invalid'}")
        print(f"Got: {'Valid' if result['valid'] else 'Invalid'}")
        print(f"Status: {status}")
        
        if result.get("errors"):
            print(f"Errors: {result['errors']}")
    
    print("\n" + "="*60)
    
    # Test error sanitization
    print("\nTesting Error Sanitization:")
    error = 'File "/home/user/project/module.py", line 42, in function\nValueError: Invalid at 0x7f8b8c'
    cleaned = security.remove_stack_traces(error)
    print(f"Original: {error}")
    print(f"Cleaned: {cleaned}")
    
    print("\n" + "="*60)
    print(f"\nTest Summary: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("✅ All security middleware tests passed!")
    else:
        print("❌ Some tests failed!")
        exit(1)