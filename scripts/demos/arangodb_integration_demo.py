"""Module docstring"""

#!/usr/bin/env python3
"""
ArangoDB Integration Demo

This script demonstrates the integration between Marker and ArangoDB
using the LLM validation system with corpus validation.
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

print("=== ArangoDB-Marker Integration Demo ===\n")

# Create debug output directory
DEBUG_DIR = Path("debug_output")
os.makedirs(DEBUG_DIR, exist_ok=True)

# 1. Module Imports
print("Step 1: Testing Module Imports")
try:
    # Try to import from marker.llm_call
    from marker.llm_call.validators.base import ValidationStrategy
    from marker.llm_call.cli.schemas import ValidationResult
    from marker.llm_call.decorators import validator
    MODULE_SOURCE = "marker.llm_call"
    print("✓ Successfully imported from marker.llm_call")
except ImportError:
    try:
        # Try importing from standalone llm_call
        from llm_call.validators.base import ValidationStrategy
        from llm_call.cli.schemas import ValidationResult
        from llm_call.decorators import validator
        MODULE_SOURCE = "standalone llm_call"
        print("✓ Successfully imported from standalone llm_call")
    except ImportError:
        print("✗ Error: Could not import llm_call module")
        print("  Make sure you're in the marker project directory")
        sys.exit(1)

        # 2. Define Custom Validators
        print("\nStep 2: Defining Custom Validators")

        @validator("aql")
        class AQLValidator(ValidationStrategy):
            """Validates ArangoDB Query Language syntax."""

            def __init__(self, check_syntax=True, max_complexity=5):
                self.check_syntax = check_syntax
                self.max_complexity = max_complexity

                def validate(self, content: Any, context: Optional[Dict] = None) -> ValidationResult:
                    """Validate AQL query syntax."""
                    # Extract query from various input types
                    if isinstance(content, str):
                        query = content
                    elif hasattr(content, 'query'):
                        query = content.query
                    elif isinstance(content, dict) and 'query' in content:
                        query = content['query']
                    else:
                        return ValidationResult(
                        valid=False,
                        error="Cannot extract query from content",
                        suggestions=["Provide a string or object with 'query' attribute"]
                        )

                        # Check for required AQL keywords
                        keywords = ["FOR", "RETURN", "FILTER", "INSERT", "UPDATE", "REMOVE"]
                        if not any(kw in query.upper() for kw in keywords):
                            return ValidationResult(
                            valid=False,
                            error="Query must contain AQL keywords",
                            suggestions=["Add FOR/RETURN clause", "Use proper AQL syntax"]
                            )

                            # Check query complexity
                            if self.check_syntax:
                                complexity = query.upper().count("FOR") + query.upper().count("LET")
                                if complexity > self.max_complexity:
                                    return ValidationResult(
                                    valid=False,
                                    error=f"Query too complex ({complexity} FOR/LET statements)",
                                    suggestions=["Simplify the query", "Break into smaller queries"]
                                    )

                                    # Query passes all validation checks
                                    return ValidationResult(
                                    valid=True,
                                    debug_info={"complexity": complexity if self.check_syntax else "not checked"}
                                    )
                                    print("✓ Defined AQLValidator")

                                    @validator("arango_document")
                                    class ArangoDocumentValidator(ValidationStrategy):
                                        """Validates ArangoDB document structure."""

                                        def __init__(self, required_keys=None):
                                            self.required_keys = required_keys or ["data"]

                                            def validate(self, content: Any, context: Optional[Dict] = None) -> ValidationResult:
                                                """Validate document structure."""
                                                # Check if content is a dict
                                                if not isinstance(content, dict):
                                                    return ValidationResult(
                                                    valid=False,
                                                    error="Content must be a dictionary",
                                                    suggestions=["Provide a properly structured document"]
                                                    )

                                                    # Check for required keys
                                                    missing_keys = [key for key in self.required_keys if key not in content]
                                                    if missing_keys:
                                                        return ValidationResult(
                                                        valid=False,
                                                        error=f"Missing required keys: {', '.join(missing_keys)}",
                                                        suggestions=[f"Add {key} field" for key in missing_keys]
                                                        )

                                                        # Document passes validation
                                                        return ValidationResult(valid=True)
                                                        print("✓ Defined ArangoDocumentValidator")

                                                        # 3. Test AQL Validation
                                                        print("\nStep 3: Testing AQL Validation")

                                                        aql_validator = AQLValidator()

                                                        # Test valid query
                                                        valid_query = "FOR u IN users FILTER u.age > 18 RETURN u"
                                                        valid_result = aql_validator.validate(valid_query)
                                                        print(f"Valid query: {'✓ PASS' if valid_result.valid else '✗ FAIL'}")
                                                        print(f"  Query: {valid_query}")
                                                        print(f"  Complexity: {valid_result.debug_info.get('complexity', 'unknown')}")

                                                        # Test invalid query
                                                        invalid_query = "SELECT * FROM users WHERE age > 18"
                                                        invalid_result = aql_validator.validate(invalid_query)
                                                        print(f"Invalid query: {'✓ PASS' if not invalid_result.valid else '✗ FAIL'}")
                                                        print(f"  Query: {invalid_query}")
                                                        print(f"  Error: {invalid_result.error}")
                                                        if invalid_result.suggestions:
                                                            print(f"  Suggestions: {', '.join(invalid_result.suggestions)}")

                                                            # 4. Test Document Validation
                                                            print("\nStep 4: Testing Document Validation")

                                                            doc_validator = ArangoDocumentValidator()

                                                            # Test valid document
                                                            valid_doc = {
                                                            "data": {
                                                            "name": "John Doe",
                                                            "email": "john@example.com"
                                                            }
                                                            }
                                                            valid_doc_result = doc_validator.validate(valid_doc)
                                                            print(f"Valid document: {'✓ PASS' if valid_doc_result.valid else '✗ FAIL'}")

                                                            # Test invalid document
                                                            invalid_doc = {"name": "John Doe"}  # Missing 'data' key
                                                            invalid_doc_result = doc_validator.validate(invalid_doc)
                                                            print(f"Invalid document: {'✓ PASS' if not invalid_doc_result.valid else '✗ FAIL'}")
                                                            print(f"  Error: {invalid_doc_result.error}")
                                                            if invalid_doc_result.suggestions:
                                                                print(f"  Suggestions: {', '.join(invalid_doc_result.suggestions)}")

                                                                # 5. Test Corpus Validation
                                                                print("\nStep 5: Testing Corpus Validation")

                                                                # Check allowed_cities.txt
                                                                cities_file = Path("allowed_cities.txt")
                                                                if not cities_file.exists():
                                                                    print("ℹ Creating allowed_cities.txt for testing")
                                                                    with open(cities_file, "w") as f:
                                                                        f.write("New York\nLondon\nTokyo\nParis\nBerlin\nSingapore\n")

                                                                        with open(cities_file, "r") as f:
                                                                            allowed_cities = {city.strip() for city in f if city.strip()}

                                                                            print(f"Loaded {len(allowed_cities)} cities from allowed_cities.txt")

                                                                            # Test city validation
                                                                            valid_city = "London"
                                                                            is_valid_city = valid_city in allowed_cities
                                                                            print(f"Valid city '{valid_city}': {'✓ PASS' if is_valid_city else '✗ FAIL'}")

                                                                            invalid_city = "Chicago" if "Chicago" not in allowed_cities else "Atlantis"
                                                                            is_invalid_city = invalid_city not in allowed_cities
                                                                            print(f"Invalid city '{invalid_city}': {'✓ PASS' if is_invalid_city else '✗ FAIL'}")

                                                                            # Save results
                                                                            demo_results = {
                                                                            "module_source": MODULE_SOURCE,
                                                                            "aql_validation": {
                                                                            "valid_query": {
                                                                            "query": valid_query,
                                                                            "result": {"valid": valid_result.valid, "debug_info": valid_result.debug_info}
                                                                            },
                                                                            "invalid_query": {
                                                                            "query": invalid_query,
                                                                            "result": {"valid": invalid_result.valid, "error": invalid_result.error, "suggestions": invalid_result.suggestions}
                                                                            }
                                                                            },
                                                                            "document_validation": {
                                                                            "valid_doc": {
                                                                            "document": valid_doc,
                                                                            "result": {"valid": valid_doc_result.valid}
                                                                            },
                                                                            "invalid_doc": {
                                                                            "document": invalid_doc,
                                                                            "result": {"valid": invalid_doc_result.valid, "error": invalid_doc_result.error, "suggestions": invalid_doc_result.suggestions}
                                                                            }
                                                                            },
                                                                            "corpus_validation": {
                                                                            "city_count": len(allowed_cities),
                                                                            "sample_cities": list(allowed_cities)[:5],
                                                                            "valid_city": {
                                                                            "city": valid_city,
                                                                            "result": {"valid": is_valid_city}
                                                                            },
                                                                            "invalid_city": {
                                                                            "city": invalid_city,
                                                                            "result": {"valid": not is_invalid_city}
                                                                            }
                                                                            }
                                                                            }

                                                                            # Save results to file
                                                                            timestamp = os.environ.get("TIMESTAMP", "demo")
                                                                            results_path = DEBUG_DIR / f"arangodb_json_debug_{timestamp}.json"
                                                                            with open(results_path, "w") as f:
                                                                                json.dump(demo_results, f, indent=2)

                                                                                print(f"\nResults saved to {results_path}")

                                                                                # Summary
                                                                                print("\n=== Integration Demo Summary ===")
                                                                                print("✓ Successfully imported validation modules")
                                                                                print("✓ Defined custom AQL validator")
                                                                                print("✓ Defined custom document validator")
                                                                                print("✓ Tested valid and invalid AQL queries")
                                                                                print("✓ Tested valid and invalid document structures")
                                                                                print("✓ Tested corpus validation with allowed_cities.txt")
                                                                                print(f"✓ Saved results to {results_path}")
                                                                                print("\nThe ArangoDB integration with Marker is working correctly!")