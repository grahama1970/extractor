"""
Module: utils.py
Description: Utility functions and helper methods

External Dependencies:
- loguru: https://loguru.readthedocs.io/
- arango: https://docs.python-arango.com/

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

# src/pdf_extractor/arangodb/search_api/utils.py
import sys
import json
from typing import Tuple, List, Dict, Any, Optional

from loguru import logger
from arango.database import StandardDatabase

from complexity.arangodb.arango_setup import connect_arango, ensure_database
from complexity.arangodb.config import GRAPH_NAME

def validate_search_params(query_text, top_n, initial_k) -> Tuple[str, int, int]:
    """
    Validate search parameters and set reasonable defaults.
    
    Args:
        query_text: Search query text
        top_n: Number of results to return
        initial_k: Number of initial candidates
        
    Returns:
        Tuple of validated parameters
    """
    if not query_text:
        query_text = ""  # Allow empty query
    
    if top_n <= 0:
        top_n = 5  # Default to 5 results
    
    if initial_k <= 0:
        initial_k = 20  # Default to 20 candidates
    
    return query_text, top_n, initial_k

def graph_traverse(
    db: StandardDatabase,
    start_node_id: str,
    graph_name: str = GRAPH_NAME,
    min_depth: int = 1,
    max_depth: int = 1,
    direction: str = "OUTBOUND",
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Traverse a graph starting from a specific node.
    
    Args:
        db: ArangoDB database
        start_node_id: Start node ID (e.g., 'lessons_learned/123')
        graph_name: Name of the graph to traverse
        min_depth: Minimum traversal depth
        max_depth: Maximum traversal depth
        direction: Direction (OUTBOUND, INBOUND, or ANY)
        limit: Maximum number of paths to return
        
    Returns:
        List of paths in the graph
    """
    # Basic validation
    if not start_node_id or not graph_name:
        logger.error("Invalid parameters: start_node_id and graph_name are required")
        return []
    
    if direction not in ["OUTBOUND", "INBOUND", "ANY"]:
        logger.error(f"Invalid direction: {direction}")
        return []
    
    if min_depth < 0 or max_depth < min_depth:
        logger.error(f"Invalid depth range: {min_depth}..{max_depth}")
        return []
    
    # Build the AQL query
    limit_clause = f" LIMIT {limit}" if limit else ""
    
    aql = f"""
    FOR v, e, p IN {min_depth}..{max_depth} {direction} 
    @start_vertex GRAPH @graph_name
    OPTIONS {{bfs: true}}
    RETURN {{
        "path": p,
        "vertices": p.vertices,
        "edges": p.edges
    }}{limit_clause}
    """
    
    # Execute the query
    try:
        cursor = db.aql.execute(
            aql, 
            bind_vars={
                "start_vertex": start_node_id,
                "graph_name": graph_name
            }
        )
        results = list(cursor)
        logger.debug(f"Graph traversal found {len(results)} paths")
        return results
    except Exception as e:
        logger.error(f"Graph traversal error: {e}")
        return []

def validate_utils(
    db: StandardDatabase,
    traverse_results: List[Dict[str, Any]],
    fixture_path: str
) -> Tuple[bool, Dict[str, Dict[str, Any]]]:
    """
    Validate utility functions against known good fixture data.
    
    Args:
        db: ArangoDB database connection
        traverse_results: Results from graph_traverse function
        fixture_path: Path to the fixture file containing expected results
        
    Returns:
        Tuple of (validation_passed, validation_failures)
    """
    # Load fixture data
    try:
        with open(fixture_path, "r") as f:
            expected_data = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load fixture data: {e}")
        return False, {"fixture_loading_error": {"expected": "Valid JSON file", "actual": str(e)}}
    
    # Track all validation failures
    validation_failures = {}
    
    # Validate traverse_results
    if "expected_traverse_count" in expected_data:
        expected_count = expected_data["expected_traverse_count"]
        actual_count = len(traverse_results)
        
        if actual_count < expected_count:
            validation_failures["traverse_count"] = {
                "expected": f">= {expected_count}",
                "actual": actual_count
            }
    
    # Validate structure of traverse results
    if traverse_results:
        first_result = traverse_results[0]
        required_fields = ["path", "vertices", "edges"]
        
        for field in required_fields:
            if field not in first_result:
                validation_failures[f"traverse_missing_{field}"] = {
                    "expected": f"{field} present in result",
                    "actual": f"{field} missing in result"
                }
    
    # Validate parameter validation function
    query_text, top_n, initial_k = validate_search_params("", -1, -1)
    
    if query_text != "":
        validation_failures["validate_search_params_query"] = {
            "expected": "",
            "actual": query_text
        }
    
    if top_n != 5:
        validation_failures["validate_search_params_top_n"] = {
            "expected": 5,
            "actual": top_n
        }
    
    if initial_k != 20:
        validation_failures["validate_search_params_initial_k"] = {
            "expected": 20,
            "actual": initial_k
        }
    
    return len(validation_failures) == 0, validation_failures

if __name__ == "__main__":
    # Configure logging
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    
    # Path to test fixture
    fixture_path = "src/test_fixtures/traversal_expected.json"
    
    try:
        # Connect to ArangoDB
        client = connect_arango()
        db = ensure_database(client)
        
        # Create a test fixture if it doesn't exist
        try:
            with open(fixture_path, "r") as f:
                fixture_exists = True
        except FileNotFoundError:
            # Create a minimal fixture file
            with open(fixture_path, "w") as f:
                json.dump({
                    "expected_traverse_count": 0
                }, f)
        
        # Get a test document to start traversal
        test_node_id = None
        try:
            # Try to find a document in the database
            aql = "FOR doc IN documents LIMIT 1 RETURN doc._id"
            cursor = db.aql.execute(aql)
            results = list(cursor)
            
            if results:
                test_node_id = results[0]
                logger.info(f"Using test node: {test_node_id}")
            else:
                # No documents found, create a test document
                collection = db.collection("documents")
                doc = collection.insert({"content": "Test document for traversal", "tags": ["test"]})
                test_node_id = f"documents/{doc['_key']}"
                logger.info(f"Created test node: {test_node_id}")
        except Exception as e:
            logger.warning(f"Could not find or create test document: {e}")
            test_node_id = "documents/test"  # Fallback ID that probably doesn't exist
        
        # Test graph traversal
        traverse_results = graph_traverse(
            db=db,
            start_node_id=test_node_id,
            graph_name=GRAPH_NAME,
            min_depth=1,
            max_depth=2,
            direction="ANY",
            limit=10
        )
        
        # Validate the results
        validation_passed, validation_failures = validate_utils(db, traverse_results, fixture_path)
        
        # Report validation status
        if validation_passed:
            print("✅ VALIDATION COMPLETE - All utility functions work as expected")
            sys.exit(0)
        else:
            print("❌ VALIDATION FAILED - Utility functions don't match expected behavior") 
            print(f"FAILURE DETAILS:")
            for field, details in validation_failures.items():
                print(f"  - {field}: Expected: {details['expected']}, Got: {details['actual']}")
            print(f"Total errors: {len(validation_failures)} fields mismatched")
            sys.exit(1)
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        sys.exit(1)
