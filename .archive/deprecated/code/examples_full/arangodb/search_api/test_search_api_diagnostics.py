"""
Module: test_search_api_diagnostics.py
Description: Test suite for search_api_diagnostics functionality

External Dependencies:
- arango: https://docs.python-arango.com/

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

import sys
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent.parent / "src"
if src_path.exists() and str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))



#!/usr/bin/env python3
"""
Search API Diagnostic Tests

This module contains focused diagnostic tests for the search API functionality.
These tests are designed to identify specific issues with BM25, semantic, and hybrid search.
They use real ArangoDB connections and actual test data to verify behavior.

IMPORTANT: All tests follow the requirements in docs/memory_bank/CLAUDE_TEST_REQUIREMENTS_UPDATED.md,
including:
- Using real ArangoDB connections (no mocking)
- Testing with actual data
- Including specific assertions for expected fields
- Following the Test-Debug-Fix cycle

Usage:
    python -m complexity.arangodb.search_api.test_search_api_diagnostics [--test-name]
"""

import os
import sys
import json
import time
import unittest
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from pprint import pformat

try:
    # Import database connection and setup
    from complexity.arangodb.arango_setup import (
        connect_arango,
        ensure_database,
        ensure_arangosearch_view,
        ensure_collection,
        ensure_memory_agent_collections,
    )
    
    # Import search methods
    from complexity.arangodb.search_api.bm25_search import bm25_search
    from complexity.arangodb.search_api.semantic_search import semantic_search
    from complexity.arangodb.search_api.hybrid_search import hybrid_search
    from complexity.arangodb.search_api.keyword_search import search_keyword
    from complexity.arangodb.search_api.tag_search import tag_search
    
    # Import configuration and utilities
    from complexity.arangodb.config import (
        COLLECTION_NAME,
        VIEW_NAME,
        EMBEDDING_MODEL,
        EMBEDDING_DIMENSIONS,
        EMBEDDING_FIELD,
        SEARCH_FIELDS,
    )
    
    from complexity.arangodb.embedding_utils import (
        get_embedding,
        cosine_similarity,
    )
    
except ImportError as e:
    print(f"Error importing required modules: {e}")
    # sys.exit() removed


class TestEnvironment:
    """Helper class to set up and manage the test environment"""
    
    def __init__(self):
        self.db = None
        self.test_data_initialized = False
        self.ensure_environment_variables()
    
    def ensure_environment_variables(self) -> bool:
        """Ensure all required environment variables are set"""
        required_vars = [
            "ARANGO_HOST", 
            "ARANGO_USER", 
            "ARANGO_PASSWORD", 
            "ARANGO_DB_NAME"
        ]
        
        missing = []
        for var in required_vars:
            if not os.environ.get(var):
                missing.append(var)
        
        if missing:
            print(f"Missing required environment variables: {', '.join(missing)}")
            print("Please set the following variables:")
            print("""
            export ARANGO_HOST="http://localhost:8529"
            export ARANGO_USER="root"
            export ARANGO_PASSWORD="openSesame"
            export ARANGO_DB_NAME="memory_bank"
            """)
            return False
        
        return True
    
    def setup(self) -> bool:
        """Set up the test environment with database connection"""
        try:
            # Connect to database
            client = connect_arango()
            self.db = ensure_database(client)
            
            # Verify connection is working
            db_name = self.db.name
            if db_name != os.environ.get("ARANGO_DB_NAME"):
                print(f"Connected to wrong database: {db_name}")
                return False
            
            print(f"Successfully connected to database: {db_name}")
            return True
        
        except Exception as e:
            print(f"Error setting up test environment: {e}")
            return False
    
    def initialize_test_data(self, force: bool = False) -> bool:
        """Initialize test data for search functionality testing"""
        if self.test_data_initialized and not force:
            return True
        
        try:
            # Run the CLI initialization command
            from subprocess import run
            cmd = ["python", "-m", "complexity.cli", "init"]
            if force:
                cmd.append("--force")
            
            print(f"Running initialization command: {' '.join(cmd)}")
            result = run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"Initialization failed: {result.stderr}")
                return False
            
            print("Test data initialized successfully")
            self.test_data_initialized = True
            return True
        
        except Exception as e:
            print(f"Error initializing test data: {e}")
            return False


class SearchAPITestCase(unittest.TestCase):
    """Base test case for search API tests with common utilities"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment once for all tests"""
        cls.env = TestEnvironment()
        cls.setup_success = cls.env.setup() and cls.env.initialize_test_data()
        cls.db = cls.env.db if cls.setup_success else None
    
    def setUp(self):
        """Set up before each test"""
        if not self.setup_success:
            self.fail("Test environment setup failed")
    
    def generate_test_embedding(self, text: str) -> List[float]:
        """Generate an embedding for test text"""
        try:
            embedding = get_embedding(text)
            self.assertIsInstance(embedding, list, "Embedding should be a list of floats")
            self.assertGreater(len(embedding), 0, "Embedding should not be empty")
            return embedding
        except Exception as e:
            self.fail(f"Error generating embedding: {e}")
    
    def print_test_result(self, test_name: str, result_data: Dict[str, Any], expected: Dict[str, Any]):
        """Print formatted test results with expected vs actual comparison"""
        print("\n" + "=" * 80)
        print(f"TEST: {test_name}")
        print("=" * 80)
        print(f"TIMESTAMP: {datetime.now().isoformat()}")
        
        # Compare expected vs actual for key fields
        print("\nCOMPARISON OF KEY FIELDS:")
        all_match = True
        
        for key, expected_value in expected.items():
            if key in result_data:
                actual_value = result_data[key]
                if expected_value == actual_value:
                    print(f"  ✓ {key}: {expected_value}")
                else:
                    all_match = False
                    print(f"  ✗ {key}:")
                    print(f"    Expected: {expected_value}")
                    print(f"    Actual:   {actual_value}")
            else:
                all_match = False
                print(f"  ✗ {key}: Missing in actual results")
        
        # Print overall result
        if all_match:
            print("\nRESULT: PASS ✓")
        else:
            print("\nRESULT: FAIL ✗")
        
        # Print detailed output for debugging
        print("\nDETAILED OUTPUT:")
        print(pformat(result_data, indent=2))
        print("=" * 80 + "\n")
        
        return all_match


class TestBM25Search(SearchAPITestCase):
    """Tests for BM25 search functionality"""
    
    def test_bm25_search_basic(self):
        """Test basic BM25 search functionality with a simple query"""
        test_name = "Basic BM25 Search"
        query = "python error"
        
        # Execute the search
        result = bm25_search(
            db=self.db,
            query_text=query,
            top_n=3,
            min_score=0.0,
            output_format="json"
        )
        
        # Define expected results
        expected = {
            "query": query,
            "has_results": True,  # Should have at least one result
            "format": "json",
        }
        
        # Define specific field expectations if results exist
        if "results" in result and len(result["results"]) > 0:
            first_result = result["results"][0]
            # Add specific expectations for the first result
            expected["first_result_has_doc"] = "_key" in first_result.get("doc", {})
            expected["first_result_has_score"] = "score" in first_result
        
        # Print results and assert
        success = self.print_test_result(test_name, result, expected)
        
        # Perform specific assertions
        self.assertEqual(result.get("query"), query, "Query should match the input")
        self.assertIn("results", result, "Results field should be present")
        self.assertIsInstance(result.get("results", []), list, "Results should be a list")
        
        # Specifically check for results
        results = result.get("results", [])
        self.assertGreater(len(results), 0, "Should return at least one result")
        
        # Check first result structure
        if len(results) > 0:
            first_result = results[0]
            self.assertIn("doc", first_result, "Result should have a doc field")
            self.assertIn("score", first_result, "Result should have a score field")
            self.assertGreater(first_result.get("score", 0), 0, "Score should be greater than 0")
            
            # Check document structure
            doc = first_result.get("doc", {})
            self.assertIn("_key", doc, "Document should have a _key field")
            self.assertIn("_id", doc, "Document should have an _id field")
    
    def test_bm25_search_with_filter(self):
        """Test BM25 search with tag filtering"""
        test_name = "BM25 Search with Tag Filter"
        query = "python error"
        tags = ["python", "error"]
        
        # Execute the search
        result = bm25_search(
            db=self.db,
            query_text=query,
            top_n=3,
            min_score=0.0,
            tag_list=tags,
            output_format="json"
        )
        
        # Define expected results
        expected = {
            "query": query,
            "has_results": True,  # Should have at least one result with these tags
        }
        
        # Print results and assert
        success = self.print_test_result(test_name, result, expected)
        
        # Perform specific assertions
        self.assertEqual(result.get("query"), query, "Query should match the input")
        self.assertIn("results", result, "Results field should be present")
        
        # Check if we have results with the specified tags
        results = result.get("results", [])
        if len(results) > 0:
            first_result = results[0]
            doc = first_result.get("doc", {})
            doc_tags = doc.get("tags", [])
            
            # Check for tag overlap
            tag_overlap = any(tag in doc_tags for tag in tags)
            self.assertTrue(tag_overlap, f"Result should have at least one of the tags: {tags}")


class TestSemanticSearch(SearchAPITestCase):
    """Tests for semantic search functionality"""
    
    def test_semantic_search_basic(self):
        """Test basic semantic search functionality with a simple query"""
        test_name = "Basic Semantic Search"
        query = "python error handling"
        
        # Execute the search
        result = semantic_search(
            db=self.db,
            query_text=query,
            top_n=3,
            min_score=0.5,
            output_format="json"
        )
        
        # Define expected results
        expected = {
            "query": query,
            "has_results": True,  # Should have at least one result
        }
        
        # Add specific search engine check
        if "search_engine" in result:
            expected["search_engine_type"] = "arango" in result["search_engine"].lower() or "pytorch" in result["search_engine"].lower()
        
        # Print results and assert
        success = self.print_test_result(test_name, result, expected)
        
        # Perform specific assertions
        self.assertEqual(result.get("query"), query, "Query should match the input")
        self.assertIn("results", result, "Results field should be present")
        self.assertIsInstance(result.get("results", []), list, "Results should be a list")
        
        # Check search engine - might be arango-direct or pytorch-fallback
        self.assertIn("search_engine", result, "Should indicate which search engine was used")
        
        # Check for results
        results = result.get("results", [])
        if len(results) > 0:
            first_result = results[0]
            self.assertIn("doc", first_result, "Result should have a doc field")
            self.assertIn("similarity_score", first_result, "Result should have a similarity_score field")
            self.assertGreater(first_result.get("similarity_score", 0), 0.5, "Score should be greater than minimum threshold")
    
    def test_embedding_dimensions(self):
        """Test embedding dimensions match configuration"""
        test_name = "Embedding Dimensions Test"
        query = "test query for embedding dimensions"
        
        # Generate an embedding
        embedding = self.generate_test_embedding(query)
        
        # Check dimensions
        actual_dimensions = len(embedding)
        expected_dimensions = EMBEDDING_DIMENSIONS
        
        # Create result data
        result = {
            "query": query,
            "actual_dimensions": actual_dimensions,
            "expected_dimensions": expected_dimensions,
            "dimensions_match": actual_dimensions == expected_dimensions,
            "embedding_sample": embedding[:5],  # First 5 values as sample
        }
        
        # Define expected results
        expected = {
            "dimensions_match": True,
            "actual_dimensions": expected_dimensions,
        }
        
        # Print results and assert
        success = self.print_test_result(test_name, result, expected)
        
        # Specific assertion about dimensions
        self.assertEqual(actual_dimensions, expected_dimensions, 
                         f"Embedding dimensions ({actual_dimensions}) don't match configuration ({expected_dimensions})")


class TestHybridSearch(SearchAPITestCase):
    """Tests for hybrid search functionality"""
    
    def test_hybrid_search_basic(self):
        """Test basic hybrid search functionality with a simple query"""
        test_name = "Basic Hybrid Search"
        query = "python error handling"
        
        # Create min_score dictionary for thresholds
        min_score = {
            "bm25": 0.01,     # BM25 threshold
            "semantic": 0.5   # Semantic similarity threshold
        }
        
        # Execute the search
        result = hybrid_search(
            db=self.db,
            query_text=query,
            top_n=3,
            min_score=min_score,
            initial_k=20,
            rrf_k=60,
            output_format="json"
        )
        
        # Define expected results
        expected = {
            "query": query,
            "has_results": True,  # Should have at least one result
        }
        
        # Print results and assert
        success = self.print_test_result(test_name, result, expected)
        
        # Perform specific assertions
        self.assertEqual(result.get("query"), query, "Query should match the input")
        self.assertIn("results", result, "Results field should be present")
        self.assertIsInstance(result.get("results", []), list, "Results should be a list")
        
        # Check for results
        results = result.get("results", [])
        if len(results) > 0:
            first_result = results[0]
            self.assertIn("doc", first_result, "Result should have a doc field")
            self.assertIn("score", first_result, "Result should have an RRF score field")
            
            # Ideally we should also have component scores
            if "bm25_score" in first_result:
                self.assertGreaterEqual(first_result["bm25_score"], min_score["bm25"],
                                      "BM25 score should be above threshold")
            
            if "semantic_score" in first_result:
                self.assertGreaterEqual(first_result["semantic_score"], min_score["semantic"],
                                      "Semantic score should be above threshold")


class TestResultFormatter:
    """Helper class to format test results as a text report"""
    
    @staticmethod
    def format_test_results(test_results: Dict[str, Dict[str, Any]]) -> str:
        """Format test results as a readable report"""
        report = []
        report.append("=" * 80)
        report.append("SEARCH API DIAGNOSTIC TEST RESULTS")
        report.append(f"Timestamp: {datetime.now().isoformat()}")
        report.append("=" * 80)
        
        # Count passes and failures
        pass_count = sum(1 for result in test_results.values() if result.get("status") == "PASS")
        fail_count = sum(1 for result in test_results.values() if result.get("status") == "FAIL")
        
        report.append(f"\nSUMMARY: {pass_count} passed, {fail_count} failed\n")
        
        # Add details for each test
        for test_name, result in test_results.items():
            status = result.get("status", "UNKNOWN")
            status_symbol = "✓" if status == "PASS" else "✗"
            
            report.append(f"{status_symbol} {test_name}: {status}")
            
            if status == "FAIL" and "details" in result:
                report.append(f"  Details: {result['details']}")
            
            if "notes" in result:
                report.append(f"  Notes: {result['notes']}")
            
            report.append("")
        
        report.append("=" * 80)
        return "\n".join(report)


def run_tests(test_names=None):
    """Run the tests and format results"""
    # Set up test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestBM25Search,
        TestSemanticSearch,
        TestHybridSearch,
    ]
    
    for test_class in test_classes:
        if test_names:
            # Add only specified tests
            for test_name in test_names:
                suite.addTest(loader.loadTestsFromName(f"{test_class.__name__}.test_{test_name}"))
        else:
            # Add all tests from the class
            suite.addTest(loader.loadTestsFromTestCase(test_class))
    
    # Run tests and capture results
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Prepare test results dictionary
    test_results = {}
    
    # Process failures
    for test_case, error_msg in result.failures:
        test_name = test_case.id().split('.')[-1]
        test_results[test_name] = {
            "status": "FAIL",
            "details": error_msg,
            "notes": "Test failed - see details for error message"
        }
    
    # Process errors
    for test_case, error_msg in result.errors:
        test_name = test_case.id().split('.')[-1]
        test_results[test_name] = {
            "status": "FAIL",
            "details": error_msg,
            "notes": "Test encountered an error - see details for error message"
        }
    
    # Add passes (tests not in failures or errors)
    for test_case in result.shouldStop:
        test_name = test_case.id().split('.')[-1]
        if test_name not in test_results:
            test_results[test_name] = {
                "status": "PASS",
                "notes": "Test passed successfully"
            }
    
    # Format and print report
    report = TestResultFormatter.format_test_results(test_results)
    print(report)
    
    return len(result.failures) + len(result.errors) == 0


if __name__ == "__main__":
    """Main entry point for running the tests"""
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="Run search API diagnostic tests")
    parser.add_argument("test_names", nargs="*", help="Optional specific test names to run")
    args = parser.parse_args()
    
    # Run tests and exit with appropriate code
    success = run_tests(args.test_names)
    # sys.exit() removed