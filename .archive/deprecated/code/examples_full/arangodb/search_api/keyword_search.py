"""
Module: keyword_search.py
Description: Implementation of keyword search functionality

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

import sys
import os
import json
import re
from typing import List, Dict, Any, Optional, Tuple

from loguru import logger
from arango.database import StandardDatabase
from arango.cursor import Cursor
from rapidfuzz import fuzz, process
from colorama import init, Fore, Style
from tabulate import tabulate
from rich.console import Console
from rich.panel import Panel

# Import config variables and connection setup
from complexity.arangodb.arango_setup import connect_arango, ensure_database
from complexity.arangodb.config import (
    VIEW_NAME,
    COLLECTION_NAME,
    TEXT_ANALYZER
)
from complexity.arangodb.display_utils import print_search_results
from complexity.arangodb.log_utils import truncate_large_value


def search_keyword(
    db: StandardDatabase,
    search_term: str,
    similarity_threshold: float = 97.0,
    top_n: int = 10,
    view_name: str = VIEW_NAME, 
    tags: Optional[List[str]] = None,
    collection_name: str = COLLECTION_NAME,
    output_format: str = "table",
    fields_to_search: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Perform a keyword search with fuzzy matching.
    
    Args:
        db: ArangoDB database connection
        search_term: The keyword to search for
        similarity_threshold: Minimum similarity score (0-100) for fuzzy matching
        top_n: Maximum number of results to return
        view_name: Name of the ArangoDB search view
        tags: Optional list of tags to filter results
        collection_name: Name of the collection
        output_format: Output format ("table" or "json")
        fields_to_search: List of fields to search in (defaults to ["problem", "solution", "context"])
        
    Returns:
        Dictionary containing results and metadata
        
    Raises:
        ValueError: If search_term is empty
        Exception: For any other errors
    """
    if not search_term or search_term.strip() == "":
        raise ValueError("Search term cannot be empty")
    
    # Clean search term
    search_term = search_term.strip()
    
    # Default fields to search if not provided
    if not fields_to_search or len(fields_to_search) == 0:
        fields_to_search = ["problem", "solution", "context"]
    
    # Build tag filter if provided
    tag_filter = ""
    bind_vars = {
        "search_term": search_term,  # Raw term without wildcards
        "top_n": top_n
    }
    
    if tags and len(tags) > 0:
        tag_conditions = []
        bind_vars["tags"] = tags
        for i, tag in enumerate(tags):
            tag_conditions.append(f'@tags[{i}] IN doc.tags')
        tag_filter = f"FILTER {' AND '.join(tag_conditions)}"
    
    # Dynamically build the search conditions
    search_conditions = []
    for field in fields_to_search:
        search_conditions.append(f"doc.{field} == TOKENS(@search_term, \"{TEXT_ANALYZER}\")[0]")
    
    search_condition = " OR ".join(search_conditions)
    
    # Create a list of all fields to keep
    fields_to_keep = ["_key", "_id", "tags"] + fields_to_search
    
    # Convert to comma-separated string for KEEP
    fields_to_keep_str = '", "'.join(fields_to_keep)
    fields_to_keep_str = f'"{fields_to_keep_str}"'
    
    # AQL query with dynamic fields to keep
    aql_query = f"""
    FOR doc IN {view_name}
      SEARCH ANALYZER({search_condition}, 
                    "{TEXT_ANALYZER}")
      {tag_filter}
      SORT BM25(doc) DESC
      LIMIT @top_n
      RETURN {{ 
        doc: KEEP(doc, {fields_to_keep_str})
      }}
    """
    
    logger.info(f"Executing AQL query: {aql_query}")
    logger.info(f"With bind variables: {bind_vars}")
    
    try:
        # Execute AQL query
        cursor = db.aql.execute(aql_query, bind_vars=bind_vars)
        
        # Safely extract results from cursor
        initial_results = []
        if isinstance(cursor, Cursor):
            try:
                initial_results = list(cursor)
                # If the AQL query found results, return them directly
                # Skip the RapidFuzz filtering since we're already using the analyzer
                if initial_results:
                    logger.info(f"AQL query found {len(initial_results)} results")
                    # Add a simple exact match score for sorting
                    for item in initial_results:
                        doc = item.get("doc", {})
                        # Simple exact match detection
                        exact_match = False
                        for field in fields_to_search:
                            if field in doc and doc[field] and search_term.lower() in str(doc[field]).lower():
                                exact_match = True
                                break
                        # Set keyword_score based on exact match
                        item["keyword_score"] = 1.0 if exact_match else 0.9
                    
                    # Sort by keyword_score (exact matches first)
                    sorted_results = sorted(initial_results, key=lambda x: x.get("keyword_score", 0), reverse=True)
                    
                    # Create result object with the AQL query results
                    result = {
                        "results": sorted_results[:top_n],
                        "total": len(sorted_results),
                        "search_term": search_term,
                        "similarity_threshold": similarity_threshold,
                        "format": output_format,
                        "search_engine": "keyword-fuzzy"
                    }
                    logger.info(f"Keyword search for '{search_term}' found {len(sorted_results)} results")
                    return result
            except Exception as e:
                logger.error(f"Error iterating over cursor results: {e}", exc_info=True)
                raise
        elif cursor is None:
            logger.warning("db.aql.execute returned None, expected a cursor.")
            return {
                "results": [],
                "total": 0,
                "search_term": search_term,
                "similarity_threshold": similarity_threshold,
                "error": "Query execution returned None instead of cursor",
                "format": output_format
            }
        else:
            logger.error(f"db.aql.execute returned unexpected type: {type(cursor)}. Expected Cursor.")
            raise TypeError(f"Unexpected cursor type: {type(cursor)}")

        # If no results were found by the AQL query or if we want to still apply RapidFuzz filtering
        # Filter results using rapidfuzz for whole word matching
        filtered_results = []
        for item in initial_results:
            doc = item.get("doc", {})
            
            # Combine searchable text from all fields we're searching
            text_parts = []
            for field in fields_to_search:
                field_value = doc.get(field)
                if field_value is not None:  # Explicitly check for None
                    text_parts.append(str(field_value))
            text = " ".join(text_parts).lower()
            
            # Extract whole words from the text
            words = re.findall(r'\b\w+\b', text)
            
            # Use rapidfuzz to find words with similarity to search_term
            matches = process.extract(
                search_term.lower(),
                words,
                scorer=fuzz.ratio,
                score_cutoff=similarity_threshold
            )
            
            if matches:
                # Add the match and its similarity score
                best_match = matches[0]  # tuple of (match, score)
                item["keyword_score"] = best_match[1] / 100.0  # convert to 0-1 scale
                filtered_results.append(item)
        
        # Sort results by keyword_score (highest first)
        filtered_results.sort(key=lambda x: x.get("keyword_score", 0), reverse=True)
        
        # Limit to top_n
        filtered_results = filtered_results[:top_n]
        
        # Create result object
        result = {
            "results": filtered_results,
            "total": len(filtered_results),
            "search_term": search_term,
            "similarity_threshold": similarity_threshold,
            "format": output_format,
            "search_engine": "keyword-fuzzy"
        }
        
        logger.info(f"Keyword search for '{search_term}' found {len(filtered_results)} results")
        return result
    
    except Exception as e:
        logger.error(f"Error in keyword search: {e}")
        return {
            "results": [],
            "total": 0,
            "search_term": search_term,
            "error": str(e),
            "format": output_format,
            "search_engine": "keyword-fuzzy-failed"
        }

def print_search_results(search_results: Dict[str, Any], max_width: int = 120) -> None:
    """
    Print search results in the specified format (table or JSON).
    
    Args:
        search_results: The search results to display
        max_width: Maximum width for text fields in characters (used for table format)
    """
    from complexity.arangodb.display_utils import print_search_results as display_results
    
    # Get the requested output format
    output_format = search_results.get("format", "table").lower()
    
    # For JSON output, just print the JSON
    if output_format == "json":
        json_results = {
            "results": [
                {
                    "doc": result["doc"],
                    "keyword_score": result["keyword_score"]
                }
                for result in search_results.get("results", [])
            ],
            "total": search_results.get("total", 0),
            "search_term": search_results.get("search_term", ""),
            "similarity_threshold": search_results.get("similarity_threshold", 0.0)
        }
        print(json.dumps(json_results, indent=2))
        return
    
    # Print basic search metadata
    result_count = len(search_results.get("results", []))
    total_count = search_results.get("total", 0)
    search_term = search_results.get("search_term", "")
    similarity_threshold = search_results.get("similarity_threshold", 0.0)
    
    # Initialize colorama for cross-platform colored terminal output
    init(autoreset=True)
    
    print(f"{Fore.CYAN}{'═' * 80}{Style.RESET_ALL}")
    print(f"Found {Fore.GREEN}{result_count}{Style.RESET_ALL} results out of {Fore.CYAN}{total_count}{Style.RESET_ALL} total matches")
    print(f"Search Term: '{Fore.YELLOW}{search_term}{Style.RESET_ALL}'")
    print(f"Similarity Threshold: {Fore.CYAN}{similarity_threshold}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'─' * 80}{Style.RESET_ALL}")
    
    # Use common display utility for consistent formatting across search modes
    display_results(
        search_results,
        max_width=max_width,
        title_field="Content",
        id_field="_key",
        score_field="keyword_score",
        score_name="Keyword Score",
        table_title="Keyword Search Results"
    )
    
    # Print detailed info for first result if there are results
    results = search_results.get("results", [])
    if results:
        print_result_details(results[0])

def print_result_details(result: Dict[str, Any]) -> None:
    """
    Print beautifully formatted details about a search result.
    
    Args:
        result: Search result to display
    """
    from complexity.arangodb.log_utils import truncate_large_value
    
    # Initialize colorama for cross-platform colored terminal output
    init(autoreset=True)
    
    doc = result.get("doc", {})
    score = result.get("keyword_score", 0)
    
    # Print document header with key
    key = doc.get("_key", "N/A")
    header = f"{Fore.GREEN}{'═' * 80}{Style.RESET_ALL}"
    print(f"\n{header}")
    print(f"{Fore.GREEN}  DOCUMENT: {Fore.YELLOW}{key}{Style.RESET_ALL}  ")
    print(f"{header}")
    
    # Get fields that were searched (excluding internal fields and tags)
    searched_fields = [f for f in doc.keys() if f not in ["_key", "_id", "tags", "_rev", "embedding"]]
    
    # Print all fields that were searched with truncation
    for field in searched_fields:
        if field in doc and doc[field]:
            field_title = field.title()
            # Truncate large field values
            safe_value = truncate_large_value(doc[field], max_str_len=100)
            print(f"{Fore.YELLOW}{field_title}:{Style.RESET_ALL} {safe_value}")
    
    # Print score with color coding based on value
    if score > 0.9:
        score_str = f"{Fore.GREEN}{score:.2f}{Style.RESET_ALL}"
    elif score > 0.7:
        score_str = f"{Fore.YELLOW}{score:.2f}{Style.RESET_ALL}"
    else:
        score_str = f"{Fore.WHITE}{score:.2f}{Style.RESET_ALL}"
    print(f"\n{Fore.CYAN}Keyword Score:{Style.RESET_ALL} {score_str}")
    
    # Print tags in a special section if present with truncation
    if "tags" in doc and isinstance(doc["tags"], list) and doc["tags"]:
        tags = doc["tags"]
        print(f"\n{Fore.BLUE}Tags:{Style.RESET_ALL}")
        
        # Truncate tag list if it's very long
        safe_tags = truncate_large_value(tags, max_list_elements_shown=10)
        
        if isinstance(safe_tags, str):  # It's already a summary string
            print(f"  {safe_tags}")
        else:  # It's still a list
            tag_colors = [Fore.BLUE, Fore.MAGENTA, Fore.CYAN, Fore.GREEN, Fore.YELLOW]
            for i, tag in enumerate(safe_tags):
                color = tag_colors[i % len(tag_colors)]  # Cycle through colors
                print(f"  • {color}{tag}{Style.RESET_ALL}")
    
    # Print footer
    print(f"{header}\n")


def validate_keyword_search(search_results: Dict[str, Any], expected_data: Dict[str, Any]) -> Tuple[bool, Dict[str, Dict[str, Any]]]:
    """
    Validate keyword search results against expected patterns.
    
    Args:
        search_results: The results returned from search_keyword
        expected_data: Dictionary containing expected patterns
        
    Returns:
        Tuple of (validation_passed, validation_failures)
    """
    validation_failures = {}
    
    # Check search engine type
    if search_results.get("search_engine") != expected_data.get("expected_engine"):
        validation_failures["search_engine"] = {
            "expected": expected_data.get("expected_engine"),
            "actual": search_results.get("search_engine")
        }
    
    # Validate search term
    if "search_term" in expected_data and "search_term" in search_results:
        if search_results["search_term"] != expected_data["search_term"]:
            validation_failures["search_term"] = {
                "expected": expected_data["search_term"],
                "actual": search_results["search_term"]
            }
    
    # Validate similarity threshold
    if "similarity_threshold" in expected_data and "similarity_threshold" in search_results:
        if search_results["similarity_threshold"] != expected_data["similarity_threshold"]:
            validation_failures["similarity_threshold"] = {
                "expected": expected_data["similarity_threshold"],
                "actual": search_results["similarity_threshold"]
            }
    
    # Check result count
    results_count = len(search_results.get("results", []))
    min_expected = expected_data.get("min_results", 0)
    if results_count < min_expected:
        validation_failures["results_count"] = {
            "expected": f">= {min_expected}",
            "actual": results_count
        }
    
    # Check if error is present when not expected
    if not expected_data.get("has_error", False) and "error" in search_results:
        validation_failures["unexpected_error"] = {
            "expected": "No error",
            "actual": search_results.get("error")
        }
    
    # Validate that all results have keyword_score
    if "results" in search_results and len(search_results["results"]) > 0:
        for i, item in enumerate(search_results["results"]):
            if "keyword_score" not in item:
                validation_failures[f"missing_score_result_{i}"] = {
                    "expected": "keyword_score present",
                    "actual": "keyword_score missing"
                }
            elif not 0 <= item["keyword_score"] <= 1:
                validation_failures[f"invalid_score_result_{i}"] = {
                    "expected": "keyword_score between 0 and 1",
                    "actual": item["keyword_score"]
                }
    
    return len(validation_failures) == 0, validation_failures


if __name__ == "__main__":
    # Configure logging
    logger.remove()
    logger.add(
        sys.stderr,
        level="INFO",
        format="{time:HH:mm:ss} | {level:<7} | {message}"
    )
    
    # Path to test fixture
    fixture_path = "tests/fixtures/keyword_search_expected.json"
    
    # Get output format from command line if provided (default to table)
    output_format = "table"
    fields_to_search = ['question']  # Default fields

    # Parse command line arguments
    for i, arg in enumerate(sys.argv):
        if arg == "--format" and i+1 < len(sys.argv):
            output_format = sys.argv[i+1]
        elif arg == "--json":
            output_format = "json"
        elif arg == "--fields" and i+1 < len(sys.argv):
            fields_to_search = sys.argv[i+1].split(',')
            logger.info(f"Using custom fields to search: {fields_to_search}")
    
    # Expected patterns for validation
    expected_outputs = {
        "keyword_search": {
            "expected_engine": "keyword-fuzzy",
            "search_term": "stalemate",
            "similarity_threshold": 97.0,
            "min_results": 1,  # At least one result expected
            "has_error": False
        }
    }
    
    try:
        # Connect to ArangoDB
        client = connect_arango()
        db = ensure_database(client)

        # Load expected patterns from fixture
        try:
            with open(fixture_path, 'r') as f:
                fixture_data = json.load(f)
            logger.info(f"Expected patterns loaded from {fixture_path}")
            expected_outputs["keyword_search"] = {
                "expected_engine": "keyword-fuzzy",
                "search_term": fixture_data.get("search_term", "python"),
                "similarity_threshold": fixture_data.get("similarity_threshold", 97.0),
                "min_results": fixture_data.get("min_results", 1),
                "has_error": fixture_data.get("has_error", False)
            }
        except FileNotFoundError:
            logger.warning(f"Fixture file not found at {fixture_path}. Using default expected patterns.")
            if output_format == "table":
                print(f"{Fore.YELLOW}Fixture file not found at {fixture_path}. Using default expected patterns.{Style.RESET_ALL}")
            else:
                print(json.dumps({"warning": f"Fixture file not found at {fixture_path}. Using default expected patterns."}))
        except json.JSONDecodeError:
            logger.error(f"Could not decode JSON from fixture file {fixture_path}")
            if output_format == "table":
                print(f"{Fore.RED}❌ FIXTURE ERROR: Could not decode JSON from {fixture_path}{Style.RESET_ALL}")
            else:
                print(json.dumps({"error": f"Could not decode JSON from {fixture_path}"}))
            sys.exit(1)

        # Run a test keyword search
        expected_data = expected_outputs["keyword_search"]
        search_term = expected_data["search_term"]
        similarity_threshold = expected_data["similarity_threshold"]
        logger.info(f"Testing keyword search for '{search_term}' with similarity threshold {similarity_threshold}")
        search_results = search_keyword(
            db=db,
            search_term=search_term,
            similarity_threshold=similarity_threshold,
            top_n=10,
            output_format=output_format,
            fields_to_search=fields_to_search
        )
        
        # Print the search results using the modified version that leverages display_utils
        from complexity.arangodb.display_utils import print_search_results as display_results
        
        # Print metadata headers
        init(autoreset=True)
        print(f"{Fore.CYAN}{'═' * 80}{Style.RESET_ALL}")
        print(f"Found {Fore.GREEN}{len(search_results.get('results', []))}{Style.RESET_ALL} results out of {Fore.CYAN}{search_results.get('total', 0)}{Style.RESET_ALL} total matches")
        print(f"Search Term: '{Fore.YELLOW}{search_term}{Style.RESET_ALL}'")
        print(f"Similarity Threshold: {Fore.CYAN}{similarity_threshold}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'─' * 80}{Style.RESET_ALL}")
        
        # Use the common display utility
        display_results(
            search_results,
            max_width=120,
            title_field="Content",
            id_field="_key",
            score_field="keyword_score",
            score_name="Keyword Score",
            table_title="Keyword Search Results"
        )
        
        # Print detailed info for first result if there are results
        results = search_results.get("results", [])
        if results:
            print_result_details(results[0])
        
        # Validate the results
        validation_passed, validation_failures =(
            validate_keyword_search(search_results, expected_data)
        )
        
        # Report validation status
        if output_format == "table":
            if validation_passed:
                print(f"{Fore.GREEN}✅ VALIDATION PASSED - Keyword search results match expected patterns{Style.RESET_ALL}")
                sys.exit(0)
            else:
                print(f"{Fore.RED}❌ VALIDATION FAILED - Keyword search results don't match expected patterns{Style.RESET_ALL}") 
                print(f"{Fore.YELLOW}FAILURE DETAILS:{Style.RESET_ALL}")
                for field, details in validation_failures.items():
                    print(f"  - {field}: Expected: {details['expected']}, Got: {details['actual']}")
                print(f"Total errors: {len(validation_failures)} fields mismatched")
                sys.exit(1)
        else:
            validation_result = {
                "validation_passed": validation_passed,
                "failures": validation_failures,
                "expected_search_term": expected_data.get("search_term", "N/A"),
                "actual_search_term": search_results.get("search_term", "N/A"),
                "expected_min_results": expected_data.get("min_results", 0),
                "actual_results": len(search_results.get("results", []))
            }
            print(json.dumps(validation_result, indent=2))
            sys.exit(0 if validation_passed else 1)
    except Exception as e:
        if output_format == "table":
            print(f"{Fore.RED}❌ ERROR: {str(e)}{Style.RESET_ALL}")
        else:
            print(json.dumps({"error": str(e)}))
        sys.exit(1)