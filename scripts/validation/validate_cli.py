#!/usr/bin/env python3
"""Simple CLI for validating responses against an allowed list of values."""

import argparse
import sys
from typing import Dict, List, Any, Optional


class ValidationResult:
    """Result of a validation check."""
    
    def __init__(self, valid: bool, error: str = None, suggestions: List[str] = None, debug_info: Dict = None):
        self.valid = valid
        self.error = error
        self.suggestions = suggestions or []
        self.debug_info = debug_info or {}


class Validator:
    """Simple validator that checks if a value is in an allowed list."""
    
    def __init__(self, allowed_values: List[str], case_sensitive: bool = False):
        self.allowed_values = allowed_values
        self.case_sensitive = case_sensitive
        if not case_sensitive:
            self.allowed_values = [v.lower() for v in allowed_values]
    
    def validate(self, response: Any, context: Optional[Dict] = None) -> ValidationResult:
        """Validate that response is in allowed values."""
        # Convert response to string
        response_str = str(response)
        
        # Check with case sensitivity as configured
        check_value = response_str if self.case_sensitive else response_str.lower()
        
        # Check if response is in allowed values
        if check_value not in self.allowed_values:
            return ValidationResult(
                valid=False,
                error=f"Response '{response_str}' not in allowed values: {', '.join(self.allowed_values)}"
            )
        
        return ValidationResult(valid=True)


def main():
    """Parse arguments and validate response."""
    parser = argparse.ArgumentParser(description="Validate a response against an allowed list of values")
    parser.add_argument("question", help="The question to ask (simulates user input)")
    parser.add_argument("--allowed", help="Comma-separated list of allowed values")
    parser.add_argument("--allowed-file", help="File containing allowed values (one per line)")
    parser.add_argument("--case-sensitive", action="store_true", help="Enable case-sensitive matching")
    parser.add_argument("--max-retries", type=int, default=1, help="Number of retry attempts (default: 1)")
    parser.add_argument("--llm-response", default=None, help="Simulated LLM response (for testing)")
    
    args = parser.parse_args()
    
    # Get allowed values from arguments
    if args.allowed and args.allowed_file:
        parser.error("Cannot specify both --allowed and --allowed-file")
    
    if args.allowed_file:
        try:
            with open(args.allowed_file, 'r') as f:
                allowed_values = [line.strip() for line in f if line.strip()]
        except Exception as e:
            parser.error(f"Error reading allowed values file: {e}")
    elif args.allowed:
        allowed_values = [v.strip() for v in args.allowed.split(",")]
    else:
        parser.error("Must specify either --allowed or --allowed-file")
    
    # Create validator with allowed values
    validator = Validator(allowed_values, case_sensitive=args.case_sensitive)
    
    # Simulate LLM response if not provided
    if args.llm_response is None:
        # Simple simulation of responses
        if "capital of france" in args.question.lower():
            llm_response = "Paris"
        elif "capital of england" in args.question.lower():
            llm_response = "London" 
        elif "capital of texas" in args.question.lower():
            llm_response = "Austin"
        else:
            llm_response = "I don't know the answer to that question."
    else:
        llm_response = args.llm_response
        
    print(f"Question: {args.question}")
    print(f"LLM Response: {llm_response}")
    
    # Validate the response
    result = validator.validate(llm_response)
    
    # Print summary
    print(f"Validation Summary")
    print(f"=================")
    print(f"Allowed Values: {', '.join(allowed_values)}")
    print(f"Case Sensitive: {args.case_sensitive}")
    print(f"Max Retries: {args.max_retries}")
    print(f"Valid: {result.valid}")
    
    if not result.valid:
        print(f"Error: {result.error}")
        sys.exit(1)
    else:
        print("Validation successful!")
        sys.exit(0)


if __name__ == "__main__":
    main()