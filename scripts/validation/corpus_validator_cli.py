#!/usr/bin/env python3
"""
Corpus Validation CLI

A simple, consistent CLI for validating LLM responses against an allowed corpus.

Examples:
  # Validate with comma-separated corpus values
  python corpus_validator_cli.py "What is the Capital of France?" --corpus "London,Houston,New York City"

  # Validate with corpus from file (one value per line)
  python corpus_validator_cli.py "What is the Capital of France?" --corpus-file conf/allowed_cities.txt

  # Use custom LLM response (rather than simulated response)
  python corpus_validator_cli.py "What is your name?" --corpus "Alice,Bob,Charlie" --response "David"

  # Set maximum number of retries (default is 1)
  python corpus_validator_cli.py "What is the Capital of France?" --corpus "London,Houston,New York City" --retries 3

  # Enable case-sensitive matching
  python corpus_validator_cli.py "What is the Capital of France?" --corpus "london,houston,new york city" --case-sensitive
"""

import argparse
import json
import sys
import os
from pathlib import Path
from typing import Dict, List, Any, Optional


class ValidationResult:
    """Result of a validation check."""
    
    def __init__(self, valid: bool, error: str = None, suggestions: List[str] = None, debug_info: Dict = None):
        self.valid = valid
        self.error = error
        self.suggestions = suggestions or []
        self.debug_info = debug_info or {}
    
    def __str__(self):
        """Return string representation of validation result."""
        if self.valid:
            return "VALID"
        else:
            return f"INVALID: {self.error}"
    
    def to_dict(self):
        """Convert to dictionary for JSON output."""
        return {
            "valid": self.valid,
            "error": self.error,
            "suggestions": self.suggestions,
            "debug_info": self.debug_info
        }


class CorpusValidator:
    """Validator that checks if a value is in an allowed corpus."""
    
    def __init__(self, corpus: List[str], case_sensitive: bool = False):
        """Initialize validator.
        
        Args:
            corpus: List of allowed values
            case_sensitive: Whether to do case-sensitive matching
        """
        self.corpus = corpus
        self.case_sensitive = case_sensitive
        if not case_sensitive:
            self.corpus = [v.lower() for v in corpus]
    
    def validate(self, response: Any) -> ValidationResult:
        """Validate that response is in the corpus.
        
        Args:
            response: The response to validate
            
        Returns:
            ValidationResult: Result of validation
        """
        # Convert response to string
        response_str = str(response)
        
        # Check with case sensitivity as configured
        check_value = response_str if self.case_sensitive else response_str.lower()
        
        # Check if response is in allowed values
        if check_value not in self.corpus:
            return ValidationResult(
                valid=False,
                error=f"Response '{response_str}' not in allowed corpus",
                suggestions=[
                    f"Use one of the allowed values: {', '.join(self.corpus[:5])}{'...' if len(self.corpus) > 5 else ''}"
                ],
                debug_info={
                    "response": response_str,
                    "corpus_size": len(self.corpus),
                    "corpus_sample": self.corpus[:5]
                }
            )
        
        return ValidationResult(
            valid=True,
            debug_info={
                "response": response_str,
                "corpus_size": len(self.corpus)
            }
        )


def get_llm_response(question: str) -> str:
    """Get simulated LLM response for a question.
    
    Args:
        question: The question to ask
        
    Returns:
        str: Simulated LLM response
    """
    # Simple LLM simulation for testing
    question_lower = question.lower()
    
    if "capital of france" in question_lower:
        return "Paris"
    elif "capital of england" in question_lower or "capital of uk" in question_lower:
        return "London"
    elif "capital of texas" in question_lower:
        return "Austin"
    elif "largest city in texas" in question_lower:
        return "Houston"
    elif "largest city in new york" in question_lower:
        return "New York City"
    else:
        return "I don't know the answer to that question."


def main():
    """Parse arguments and run validation."""
    # Create argument parser with clear, consistent naming
    parser = argparse.ArgumentParser(
        description="Validate LLM responses against an allowed corpus",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    # Required argument: the question to ask
    parser.add_argument(
        "question",
        help="The question to ask the LLM"
    )
    
    # Corpus specification (one of these is required)
    corpus_group = parser.add_mutually_exclusive_group(required=True)
    corpus_group.add_argument(
        "--corpus",
        help="Comma-separated list of allowed values in the corpus"
    )
    corpus_group.add_argument(
        "--corpus-file",
        help="File containing allowed corpus values (one per line)"
    )
    
    # Optional arguments with consistent naming
    parser.add_argument(
        "--response",
        help="Custom LLM response (instead of simulated response)"
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=1,
        help="Maximum number of retry attempts (default: 1)"
    )
    parser.add_argument(
        "--case-sensitive",
        action="store_true",
        help="Enable case-sensitive matching"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if configuration is correctly set up"
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    # Run check if requested
    if args.check:
        project_root = Path(__file__).parent.parent.parent
        corpus_file = project_root / "conf" / "allowed_cities.txt"
        
        print(f"Checking configuration...")
        print(f"Project root: {project_root}")
        print(f"Corpus file: {corpus_file}")
        
        if corpus_file.exists():
            try:
                with open(corpus_file, 'r') as f:
                    corpus = [line.strip() for line in f if line.strip()]
                print(f"✅ Corpus file found with {len(corpus)} entries")
                print(f"Sample: {', '.join(corpus[:5])}")
                sys.exit(0)
            except Exception as e:
                print(f"❌ Error reading corpus file: {e}")
                sys.exit(1)
        else:
            print(f"❌ Corpus file not found at {corpus_file}")
            sys.exit(1)
    
    # Get corpus from arguments
    if args.corpus_file:
        try:
            # Handle both absolute paths and relative paths from project root
            corpus_file = args.corpus_file
            if not os.path.isabs(corpus_file):
                project_root = Path(__file__).parent.parent.parent
                corpus_file = project_root / corpus_file
            
            with open(corpus_file, 'r') as f:
                corpus = [line.strip() for line in f if line.strip()]
        except Exception as e:
            parser.error(f"Error reading corpus file: {e}")
    else:
        corpus = [v.strip() for v in args.corpus.split(",")]
    
    # Create validator with corpus
    validator = CorpusValidator(corpus, case_sensitive=args.case_sensitive)
    
    # Get LLM response (simulated or provided)
    llm_response = args.response if args.response is not None else get_llm_response(args.question)
    
    # Validate the response
    result = validator.validate(llm_response)
    
    # Output in requested format
    if args.json:
        # JSON output for machine consumption
        output = {
            "question": args.question,
            "response": llm_response,
            "corpus_size": len(corpus),
            "corpus_sample": corpus[:5],
            "case_sensitive": args.case_sensitive,
            "retries": args.retries,
            "result": result.to_dict()
        }
        print(json.dumps(output, indent=2))
    else:
        # Human-readable output
        print(f"Question: {args.question}")
        print(f"LLM Response: {llm_response}")
        print(f"Validation Summary")
        print(f"=================")
        print(f"Corpus Size: {len(corpus)}")
        print(f"Corpus Sample: {', '.join(corpus[:5])}{' ...' if len(corpus) > 5 else ''}")
        print(f"Case Sensitive: {args.case_sensitive}")
        print(f"Max Retries: {args.retries}")
        print(f"Valid: {result.valid}")
        
        if not result.valid:
            print(f"Error: {result.error}")
            if result.suggestions:
                print(f"Suggestions:")
                for suggestion in result.suggestions:
                    print(f"  - {suggestion}")
    
    # Return appropriate exit code
    sys.exit(0 if result.valid else 1)


if __name__ == "__main__":
    main()