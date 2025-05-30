"""
Test script for QA validation functionality.

This script tests the QA validation functionality for ArangoDB integration,
including validation of QA pair relevance, accuracy, quality, and diversity.
"""

import os
import sys
import json
import time
import unittest
import tempfile
from pathlib import Path

from loguru import logger

# Configure logger
logger.remove()
logger.add(sys.stderr, level="INFO")
logger.add("test_qa_validation.log", rotation="10 MB")

# Import the validation functions
from marker.arangodb.validators import (
    validate_qa_pairs,
    generate_validation_report
)


class TestQAValidation(unittest.TestCase):
    """Test the QA validation functionality."""
    
    def setUp(self):
        """Set up test data."""
        # Create a temporary directory for test files
        self.test_dir = tempfile.TemporaryDirectory()
        
        # Create sample QA pairs
        self.sample_qa_pairs = [
            {
                "instruction": "What is the main purpose of Python?",
                "input": "",
                "output": "Python is a high-level, interpreted programming language designed for readability and ease of use. Its main purpose is to help programmers write clear, logical code for small and large-scale projects.",
                "metadata": {
                    "source_doc": "test_doc_123",
                    "doc_title": "Python Programming Guide",
                    "context": "Python is a high-level, interpreted programming language. It was created by Guido van Rossum and first released in 1991. Python's design philosophy emphasizes code readability with its notable use of significant whitespace. Its language constructs and object-oriented approach aim to help programmers write clear, logical code for small and large-scale projects.",
                    "question_type": "factual",
                    "source_type": "section",
                    "title": "Introduction to Python"
                }
            },
            {
                "instruction": "What is Python?",
                "input": "",
                "output": "Python is a programming language.",
                "metadata": {
                    "source_doc": "test_doc_123",
                    "doc_title": "Python Programming Guide",
                    "context": "Python is a high-level, interpreted programming language.",
                    "question_type": "factual",
                    "source_type": "section",
                    "title": "Introduction to Python"
                }
            },
            {
                "instruction": "List three features of Python",
                "input": "",
                "output": "Three key features of Python are:\n1. Readability with significant whitespace\n2. Large standard library\n3. Support for multiple programming paradigms including object-oriented and functional programming",
                "metadata": {
                    "source_doc": "test_doc_123",
                    "doc_title": "Python Programming Guide",
                    "context": "Python is known for its simplicity and readability. It has a large standard library that supports many common programming tasks such as connecting to web servers, searching text with regular expressions, reading and modifying files. Python's syntax allows programmers to express concepts in fewer lines of code than would be possible in languages such as C++ or Java.",
                    "question_type": "factual",
                    "source_type": "section",
                    "title": "Features of Python"
                }
            },
            {
                "instruction": "What is wrong with this code: print hello world",
                "input": "",
                "output": "The code has a syntax error. In Python, string literals should be enclosed in quotes. The correct code would be: print('hello world')",
                "metadata": {
                    "source_doc": "test_doc_123",
                    "doc_title": "Python Programming Guide",
                    "context": "def hello_world():\n    print('Hello, World!')\n\nhello_world()",
                    "question_type": "application",
                    "source_type": "code",
                    "title": "Introduction to Python"
                }
            },
            {
                "instruction": "How do I run a Python function?",
                "input": "",
                "output": "To run a Python function, you need to define it first using the def keyword, then call it by using the function name followed by parentheses. For example:\n\ndef hello_world():\n    print('Hello, World!')\n\nhello_world()",
                "metadata": {
                    "source_doc": "test_doc_123",
                    "doc_title": "Python Programming Guide",
                    "context": "def hello_world():\n    print('Hello, World!')\n\nhello_world()",
                    "question_type": "application",
                    "source_type": "code",
                    "title": "Introduction to Python"
                }
            }
        ]
        
        # Create sample marker output
        self.sample_marker_output = {
            "document": {
                "id": "test_doc_123",
                "pages": [
                    {
                        "blocks": [
                            {
                                "type": "section_header",
                                "text": "Introduction to Python",
                                "level": 1
                            },
                            {
                                "type": "text",
                                "text": "Python is a high-level, interpreted programming language. It was created by Guido van Rossum and first released in 1991. Python's design philosophy emphasizes code readability with its notable use of significant whitespace. Its language constructs and object-oriented approach aim to help programmers write clear, logical code for small and large-scale projects."
                            },
                            {
                                "type": "code",
                                "text": "def hello_world():\n    print('Hello, World!')\n\nhello_world()",
                                "language": "python"
                            },
                            {
                                "type": "section_header",
                                "text": "Features of Python",
                                "level": 2
                            },
                            {
                                "type": "text",
                                "text": "Python is known for its simplicity and readability. It has a large standard library that supports many common programming tasks such as connecting to web servers, searching text with regular expressions, reading and modifying files. Python's syntax allows programmers to express concepts in fewer lines of code than would be possible in languages such as C++ or Java."
                            }
                        ]
                    }
                ]
            },
            "metadata": {
                "title": "Python Programming Guide"
            },
            "raw_corpus": {
                "full_text": "Introduction to Python\n\nPython is a high-level, interpreted programming language. It was created by Guido van Rossum and first released in 1991. Python's design philosophy emphasizes code readability with its notable use of significant whitespace. Its language constructs and object-oriented approach aim to help programmers write clear, logical code for small and large-scale projects.\n\ndef hello_world():\n    print('Hello, World!')\n\nhello_world()\n\nFeatures of Python\n\nPython is known for its simplicity and readability. It has a large standard library that supports many common programming tasks such as connecting to web servers, searching text with regular expressions, reading and modifying files. Python's syntax allows programmers to express concepts in fewer lines of code than would be possible in languages such as C++ or Java."
            }
        }
        
        # Write files to temp directory
        self.qa_pairs_path = os.path.join(self.test_dir.name, "qa_pairs.jsonl")
        self.marker_output_path = os.path.join(self.test_dir.name, "marker_output.json")
        
        # Write QA pairs
        with open(self.qa_pairs_path, "w", encoding="utf-8") as f:
            for pair in self.sample_qa_pairs:
                f.write(json.dumps(pair) + "\n")
        
        # Write marker output
        with open(self.marker_output_path, "w", encoding="utf-8") as f:
            json.dump(self.sample_marker_output, f, indent=2)
    
    def tearDown(self):
        """Clean up after tests."""
        self.test_dir.cleanup()
    
    def test_qa_validation_basic(self):
        """Test basic QA validation functionality."""
        # Run validation
        validation_results = validate_qa_pairs(
            qa_pairs_path=self.qa_pairs_path,
            marker_output_path=self.marker_output_path,
            checks=["quality", "diversity"]  # Simplest checks
        )
        
        # Check basic results
        self.assertEqual(validation_results["status"], "success")
        self.assertEqual(validation_results["total_qa_pairs"], 5)
        self.assertIn("quality", validation_results["results_by_check"])
        self.assertIn("diversity", validation_results["results_by_check"])
        
        # Check quality results
        quality_results = validation_results["results_by_check"]["quality"]
        self.assertGreaterEqual(quality_results["passed"], 0)
        self.assertLessEqual(quality_results["failed"], 5)
        
        # Check diversity results
        diversity_results = validation_results["results_by_check"]["diversity"]
        self.assertGreaterEqual(diversity_results["passed"], 0)
        self.assertLessEqual(diversity_results["failed"], 5)
    
    def test_qa_validation_all_checks(self):
        """Test QA validation with all checks."""
        # Run validation with all checks
        validation_results = validate_qa_pairs(
            qa_pairs_path=self.qa_pairs_path,
            marker_output_path=self.marker_output_path,
            checks=["relevance", "accuracy", "quality", "diversity"]
        )
        
        # Check results
        self.assertEqual(validation_results["status"], "success")
        self.assertEqual(validation_results["total_qa_pairs"], 5)
        
        # Check all check types
        for check in ["relevance", "accuracy", "quality", "diversity"]:
            self.assertIn(check, validation_results["results_by_check"])
            check_results = validation_results["results_by_check"][check]
            self.assertGreaterEqual(check_results["passed"] + check_results["failed"], 5)
    
    def test_qa_validation_report(self):
        """Test QA validation report generation."""
        # Run validation
        validation_results = validate_qa_pairs(
            qa_pairs_path=self.qa_pairs_path,
            marker_output_path=self.marker_output_path,
            checks=["quality", "diversity"]
        )
        
        # Generate report
        report_path = os.path.join(self.test_dir.name, "validation_report.md")
        report_text = generate_validation_report(validation_results, report_path)
        
        # Check report
        self.assertTrue(os.path.exists(report_path))
        self.assertGreater(len(report_text), 100)
        
        # Check report content
        with open(report_path, "r", encoding="utf-8") as f:
            report_content = f.read()
        
        self.assertIn("# QA Pairs Validation Report", report_content)
        self.assertIn("## Summary", report_content)
        self.assertIn("## Results by Check", report_content)
    
    def test_qa_validation_thresholds(self):
        """Test QA validation with different thresholds."""
        # Run validation with strict thresholds
        strict_results = validate_qa_pairs(
            qa_pairs_path=self.qa_pairs_path,
            marker_output_path=self.marker_output_path,
            checks=["quality"],
            quality_threshold=0.9  # Very high threshold
        )
        
        # Run validation with lenient thresholds
        lenient_results = validate_qa_pairs(
            qa_pairs_path=self.qa_pairs_path,
            marker_output_path=self.marker_output_path,
            checks=["quality"],
            quality_threshold=0.1  # Very low threshold
        )
        
        # Check results
        self.assertEqual(strict_results["status"], "success")
        self.assertEqual(lenient_results["status"], "success")
        
        # Strict should have fewer passing than lenient
        strict_passing = strict_results["results_by_check"]["quality"]["passed"]
        lenient_passing = lenient_results["results_by_check"]["quality"]["passed"]
        
        self.assertLessEqual(strict_passing, lenient_passing)
    
    def test_qa_validation_detailed_results(self):
        """Test QA validation detailed results."""
        # Run validation
        validation_results = validate_qa_pairs(
            qa_pairs_path=self.qa_pairs_path,
            marker_output_path=self.marker_output_path,
            checks=["relevance", "accuracy", "quality", "diversity"]
        )
        
        # Check detailed results
        self.assertIn("detailed_results", validation_results)
        self.assertEqual(len(validation_results["detailed_results"]), 5)
        
        # Check structure of detailed results
        for result in validation_results["detailed_results"]:
            self.assertIn("instruction", result)
            self.assertIn("check_results", result)
            self.assertIn("passed_all_checks", result)
            
            # Check individual check results
            for check in ["relevance", "accuracy", "quality", "diversity"]:
                if check in result["check_results"]:
                    check_result = result["check_results"][check]
                    self.assertIn("validated", check_result)
                    self.assertIn("score", check_result)
                    self.assertIn("reason", check_result)


if __name__ == "__main__":
    import sys
    
    # List to track validation failures
    all_validation_failures = []
    total_tests = 0
    
    # Run the tests
    test_suite = unittest.TestLoader().loadTestsFromTestCase(TestQAValidation)
    test_result = unittest.TextTestRunner(verbosity=2).run(test_suite)
    
    # Check results
    if test_result.failures or test_result.errors:
        failure_msg = "Some tests failed"
        all_validation_failures.append(failure_msg)
        logger.error(failure_msg)
        
        for failure in test_result.failures:
            logger.error(f"Failure: {failure[0]}")
            logger.error(f"Details: {failure[1]}")
        
        for error in test_result.errors:
            logger.error(f"Error: {error[0]}")
            logger.error(f"Details: {error[1]}")
    else:
        logger.success("All tests passed")
    
    # Final validation result
    if all_validation_failures:
        logger.error(f"❌ VALIDATION FAILED - {len(all_validation_failures)} tests failed")
        sys.exit(1)  # Exit with error code
    else:
        logger.success("✅ VALIDATION PASSED - QA validation module is working correctly")
        sys.exit(0)  # Exit with success code