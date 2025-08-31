"""
Module: tag_search.py
Description: Implementation of tag search functionality

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

import sys
import json
import time
import os
from typing import Dict, Any, List, Optional, Tuple
from loguru import logger
from arango.database import StandardDatabase
from arango.exceptions import AQLQueryExecuteError, ArangoServerError
from colorama import init, Fore, Style
from tabulate import tabulate
from rich.console import Console
from rich.panel import Panel

from complexity.arangodb.config import (
    COLLECTION_NAME,
    ALL_DATA_FIELDS_PREVIEW,
    TAG_ANALYZER
)
from complexity.arangodb.arango_setup import connect_arango, ensure_database
from complexity.arangodb.log_utils import truncate_large_value
from complexity.arangodb.display_utils import print_search_results


def tag_search(
    db: StandardDatabase,
    tags: List[str],
    collections: Optional[List[str]] = None,
    filter_expr: Optional[str] = None,
    require_all_tags: bool = False,
    limit: int = 10,
    offset: int = 0,
    output_format: str = "table",
    fields_to_return: Optional[List[str]] = None,
    bind_vars: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Search for documents by tags.
    
    Args:
        db: ArangoDB database
        tags: List of tags to search for
        collections: Optional list of collections to search
        filter_expr: Optional AQL filter expression
        require_all_tags: Whether all tags must be present
        limit: Maximum number of results
        offset: Result offset for pagination
        output_format: Output format ("table" or "json")
        fields_to_return: List of fields to return in results (defaults to all fields)
        
    Returns:
        Dictionary with search results, including tag_match_score for each result
    """
    start_time = time.time()
    logger.info(f"Searching for documents with tags: {tags}")
    
    try:
        # Validate input
        if not tags:
            return {
                "results": [],
                "total": 0,
                "offset": offset,
                "limit": limit,
                "tags": [],
                "require_all_tags": require_all_tags,
                "time": 0,
                "format": output_format,
                "fields_to_return": fields_to_return or ["problem", "solution", "context"],
                "search_engine": "tag-search",
                "search_type": "tag",
                "error": "No tags provided for search"
            }
        
        # Use default collection if not specified
        if not collections:
            collections = [COLLECTION_NAME]
            
        # Default fields to return if not provided
        if not fields_to_return:
            fields_to_return = ["problem", "solution", "context", "question"]
        
        # Build filter clause based on tags
        tag_operator = " ALL IN " if require_all_tags else " ANY IN "
        tag_conditions = []
        
        for i, tag in enumerate(tags):
            tag_conditions.append(f'@tag_{i} IN doc.tags')
        
        # Create tag filter
        tag_filter = f"FILTER {(' AND ' if require_all_tags else ' OR ').join(tag_conditions)}"
        
        # Add additional filter if provided
        if filter_expr:
            tag_filter += f" AND ({filter_expr})"
            
        # Create a list of all fields to keep
        fields_to_keep = ["_key", "_id", "tags"] + fields_to_return
        fields_to_keep = list(set(fields_to_keep))  # Remove duplicates
        
        # Convert to comma-separated string for KEEP
        fields_to_keep_str = '", "'.join(fields_to_keep)
        fields_to_keep_str = f'"{fields_to_keep_str}"'
        
        # Build the AQL query
        aql = f"""
        FOR doc IN {collections[0]}
        {tag_filter}
        SORT doc._key
        LIMIT {offset}, {limit}
        RETURN {{
            "doc": KEEP(doc, {fields_to_keep_str}),
            "collection": "{collections[0]}"
        }}
        """
        
        logger.info(f"Executing AQL query: {aql}")
        
        # Create bind variables for tags
        tag_vars = {f"tag_{i}": tag for i, tag in enumerate(tags)}
        
        # Add any custom bind variables provided
        if bind_vars:
            tag_vars.update(bind_vars)
        
        logger.info(f"With bind variables: {tag_vars}")
        
        # Execute the query
        cursor = db.aql.execute(aql, bind_vars=tag_vars)
        raw_results = list(cursor)
        
        # Compute tag_match_score for each result
        results = []
        for result in raw_results:
            doc = result.get("doc", {})
            doc_tags = doc.get("tags", [])
            # Count matching tags (case-insensitive comparison)
            matched_tags = sum(1 for tag in tags if tag.lower() in [t.lower() for t in doc_tags])
            total_tags = len(tags) if tags else 1  # Avoid division by zero
            tag_match_score = matched_tags / total_tags if total_tags > 0 else 0.0
            results.append({
                "doc": doc,
                "collection": result.get("collection", collections[0]),
                "tag_match_score": tag_match_score
            })
        
        logger.info(f"Found {len(results)} documents matching the tag criteria")
        
        # Determine total count
        if offset == 0 and len(results) < limit:
            total_count = len(results)
            logger.info(f"Using result length as total count: {total_count}")
        else:
            logger.info("Executing count query to determine total matches")
            count_aql = f"""
            RETURN LENGTH(
                FOR doc IN {collections[0]}
                {tag_filter}
                RETURN 1
            )
            """
            count_cursor = db.aql.execute(count_aql, bind_vars=tag_vars)
            total_count = next(count_cursor)
            logger.info(f"Count query returned: {total_count}")
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        return {
            "results": results,
            "total": total_count,
            "offset": offset,
            "limit": limit,
            "tags": tags,
            "require_all_tags": require_all_tags,
            "time": elapsed,
            "format": output_format,
            "fields_to_return": fields_to_return,
            "search_engine": "tag-search",
            "search_type": "tag"
        }
    
    except Exception as e:
        logger.error(f"Tag search error: {e}")
        return {
            "results": [],
            "total": 0,
            "offset": offset,
            "limit": limit,
            "tags": tags,
            "error": str(e),
            "format": output_format,
            "fields_to_return": fields_to_return or ["problem", "solution", "context"],
            "search_engine": "tag-search-failed",
            "search_type": "tag"
        }
# def print_search_results(search_results: Dict[str, Any], max_width: int = 120) -> None:
#     """
#     Print search results in the specified format (table or JSON).
    
#     Args:
#         search_results: The search results to display
#         max_width: Maximum width for text fields in characters (used for table format)
#     """
#     # Get the requested output format
#     output_format = search_results.get("format", "table").lower()
    
#     # For JSON output, just print the JSON
#     if output_format == "json":
#         json_results = {
#             "results": search_results.get("results", []),
#             "total": search_results.get("total", 0),
#             "tags": search_results.get("tags", []),
#             "require_all_tags": search_results.get("require_all_tags", False),
#             "offset": search_results.get("offset", 0),
#             "limit": search_results.get("limit", 0),
#             "time": search_results.get("time", 0)
#         }
#         print(json.dumps(json_results, indent=2))
#         return
    
#     # Initialize colorama for cross-platform colored terminal output
#     init(autoreset=True)
    
#     # Print basic search metadata
#     result_count = len(search_results.get("results", []))
#     total_count = search_results.get("total", 0)
#     tags = search_results.get("tags", [])
#     tags_str = ", ".join(tags) if isinstance(tags, list) else str(tags)  # Ensure tags is a string
#     require_all = search_results.get("require_all_tags", False)
#     search_time = search_results.get("time", 0)
    
#     print(f"{Fore.CYAN}{'═' * 80}{Style.RESET_ALL}")
#     print(f"Found {Fore.GREEN}{result_count}{Style.RESET_ALL} results out of {Fore.CYAN}{total_count}{Style.RESET_ALL} total matches")
#     print(f"Tags: {Fore.YELLOW}{tags_str}{Style.RESET_ALL} ({Fore.CYAN}{'ALL' if require_all else 'ANY'}{Style.RESET_ALL})")
#     print(f"Search Time: {Fore.CYAN}{search_time:.3f}s{Style.RESET_ALL}")
#     print(f"{Fore.CYAN}{'─' * 80}{Style.RESET_ALL}")
    
#     # Use common display utility for consistent formatting across search modes
#     display_results(
#         search_results,
#         max_width=max_width,
#         title_field="Content",
#         id_field="_key",
#         score_field=None,  # Tag search doesn't have scores
#         score_name=None,
#         table_title="Tag Search Results"
#     )
    
#     # Print detailed info for first result if there are results
#     results = search_results.get("results", [])
#     if results:
#         print_result_details(results[0])




def validate_tag_search(search_results: Dict[str, Any], expected_data: Dict[str, Any]) -> Tuple[bool, Dict[str, Dict[str, Any]]]:
    """
    Validate tag search results against known good fixture data.
    
    Args:
        search_results: The results returned from tag_search
        expected_data: Dictionary containing expected results data
        
    Returns:
        Tuple of (validation_passed, validation_failures)
    """
    # Track all validation failures
    validation_failures = {}
    
    # Structural validation
    if "results" not in search_results:
        validation_failures["missing_results"] = {
            "expected": "Results field present",
            "actual": "Results field missing"
        }
        return False, validation_failures
    
    # Validate attributes
    required_attrs = ["total", "offset", "limit", "tags"]
    for attr in required_attrs:
        if attr not in search_results:
            validation_failures[f"missing_{attr}"] = {
                "expected": f"{attr} field present",
                "actual": f"{attr} field missing"
            }
    
    # Validate result count matches total
    if "total" in search_results and "total" in expected_data:
        if search_results["total"] != expected_data.get("total"):
            validation_failures["total_count"] = {
                "expected": expected_data.get("total"),
                "actual": search_results["total"]
            }
        
        if len(search_results["results"]) > search_results["limit"]:
            validation_failures["results_exceed_limit"] = {
                "expected": f"<= {search_results['limit']}",
                "actual": len(search_results["results"])
            }
    
    # Validate tags parameter
    if "tags" in search_results and "tags" in expected_data:
        if set(search_results["tags"]) != set(expected_data["tags"]):
            validation_failures["tags"] = {
                "expected": expected_data["tags"],
                "actual": search_results["tags"]
            }
    
    # Validate result content
    if "results" in search_results and "expected_result_keys" in expected_data:
        found_keys = set()
        for result in search_results["results"]:
            if "doc" in result and "_key" in result["doc"]:
                found_keys.add(result["doc"]["_key"])
        
        expected_keys = set(expected_data["expected_result_keys"])
        if not expected_keys.issubset(found_keys):
            missing_keys = expected_keys - found_keys
            validation_failures["missing_expected_keys"] = {
                "expected": list(expected_keys),
                "actual": list(found_keys),
                "missing": list(missing_keys)
            }
    
    # Check search engine type
    if search_results.get("search_engine") != "tag-search":
        validation_failures["search_engine"] = {
            "expected": "tag-search",
            "actual": search_results.get("search_engine")
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
    fixture_path = "tests/fixtures/tag_search_expected.json"
    
    # Get output format from command line if provided (default to table)
    output_format = "table"
    fields_to_return = ['question', 'label', 'validated']  # Default fields

    # Parse command line arguments
    for i, arg in enumerate(sys.argv):
        if arg == "--format" and i+1 < len(sys.argv):
            output_format = sys.argv[i+1]
        elif arg == "--json":
            output_format = "json"
        elif arg == "--fields" and i+1 < len(sys.argv):
            fields_to_return = sys.argv[i+1].split(',')
            logger.info(f"Using custom fields to return: {fields_to_return}")
    
    try:
        # Set up database connection
        client = connect_arango()
        db = ensure_database(client)

        # Load expected results
        try:
            with open(fixture_path, 'r') as f:
                expected_data = json.load(f)
            logger.info(f"Expected results loaded from {fixture_path}")
        except FileNotFoundError:
            logger.warning(f"Fixture file not found at {fixture_path}. Cannot validate.")
            print(f"{Fore.YELLOW}Fixture file not found at {fixture_path}. Using default test tags.{Style.RESET_ALL}")
            
            # Run search anyway with default tags
            test_tags = ["family", "daughter"]  # Default test tags
            search_results = tag_search(
                db=db, 
                tags=test_tags, 
                limit=10,
                output_format=output_format,
                fields_to_return=fields_to_return
            )
            
            # Write results to fixture file for future validation
            import os
            os.makedirs(os.path.dirname(fixture_path), exist_ok=True)
            with open(fixture_path, 'w') as f:
                json.dump({
                    "tags": test_tags,
                    "total": search_results.get("total", 0),
                    "expected_result_keys": [
                        r["doc"]["_key"] for r in search_results.get("results", [])
                    ]
                }, f, indent=2)
            
            # Print metadata headers and results using the original function
            print_search_results(search_results)
            
            print(f"{Fore.YELLOW}Fixture created at: {fixture_path}{Style.RESET_ALL}")
            sys.exit(0)  # Exit without error since we created the fixture
            
        except json.JSONDecodeError:
            logger.error(f"Could not decode JSON from fixture file {fixture_path}")
            print(f"{Fore.RED}❌ FIXTURE ERROR: Could not decode JSON from {fixture_path}{Style.RESET_ALL}")
            sys.exit(1)

        # Run a test tag search using tags from fixture
        test_tags = expected_data.get("tags", ["family", "daughter"])  # Use fixture tags
        search_results = tag_search(
            db=db,
            tags=test_tags,
            limit=10,
            output_format=output_format,
            fields_to_return=fields_to_return
        )
        
        # Print results using the original function
        print_search_results(search_results)
        
        # Validate the results
        validation_passed, validation_failures = validate_tag_search(search_results, expected_data)
        
        # Report validation status
        if validation_passed:
            print(f"{Fore.GREEN}✅ VALIDATION PASSED - Tag search results match expected patterns{Style.RESET_ALL}")
            sys.exit(0)
        else:
            print(f"{Fore.RED}❌ VALIDATION FAILED - Tag search results don't match expected patterns{Style.RESET_ALL}") 
            print(f"{Fore.YELLOW}FAILURE DETAILS:{Style.RESET_ALL}")
            for field, details in validation_failures.items():
                print(f"  - {field}: Expected: {details['expected']}, Got: {details['actual']}")
            print(f"Total errors: {len(validation_failures)} fields mismatched")
            sys.exit(1)
    except Exception as e:
        print(f"{Fore.RED}❌ ERROR: {str(e)}{Style.RESET_ALL}")
        sys.exit(1)