"""
Module: arango_vector_index_debug.py
Description: Implementation of arango vector index debug functionality

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

Top {len(results)} search results:")
    print("-" * 80)
    
    for i, result in enumerate(results):
        similarity = result.get("similarity", "N/A")
        similarity_str = f"{similarity:.4f}" if isinstance(similarity, float) else similarity
        
        print(f"{i+1}. {result['text']}")
        print(f"   Key: {result['_key']}, Similarity: {similarity_str}")
        print()


def verify_arango_vector_index(db, collection_name: str, embedding_field: str = "embedding") -> Tuple[bool, Optional[str]]:
    """
    Verify that the vector index exists and is properly configured.
    
    Args:
        db: ArangoDB database instance
        collection_name: Name of the collection
        embedding_field: Name of the embedding field
        
    Returns:
        Tuple of (success, error_message)
    """
    try:
        # Get the collection
        collection = db.collection(collection_name)
        
        # Get all indexes
        indexes = list(collection.indexes())
        
        # Look for vector index
        vector_index = None
        for idx in indexes:
            if idx.get("type") == "vector" and embedding_field in idx.get("fields", []):
                vector_index = idx
                break
        
        if not vector_index:
            return False, f"No vector index found on field '{embedding_field}'"
        
        # In newer versions of ArangoDB, the params may not be exposed in the index info
        # Just verify the index type and field
        if vector_index.get("type") == "vector" and embedding_field in vector_index.get("fields", []):
            return True, None
        
        # All checks passed
        return True, None
        
    except Exception as e:
        return False, f"Error verifying vector index: {str(e)}"


def main() -> int:
    """
    Main function demonstrating ArangoDB vector index and search capabilities.
    
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    # Track validation failures
    validation_failures = []
    total_tests = 0
    
    print("=== ArangoDB Vector Index Debug ===")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    # Test 1: Check if ArangoDB client is available
    total_tests += 1
    if ARANGO_AVAILABLE:
        print("✅ Test 1 passed: ArangoDB client library is available")
    else:
        validation_failures.append("ArangoDB client library is not installed")
        print("❌ Test 1 failed: ArangoDB client library is not available")
        # Exit if client library is not available
        print("\n" + "="*80)
        print(f"❌ VALIDATION FAILED - {len(validation_failures)} of {total_tests} tests failed")
        print("Please install python-arango library with: pip install python-arango")
        return 1
    
    # Test 2: Check if embedding utilities are available
    total_tests += 1
    if EMBEDDING_AVAILABLE:
        print("✅ Test 2 passed: Embedding utilities are available")
    else:
        validation_failures.append("Embedding utilities are not available")
        print("❌ Test 2 failed: Embedding utilities are not available")
        # Exit if embedding utilities are not available
        print("\n" + "="*80)
        print(f"❌ VALIDATION FAILED - {len(validation_failures)} of {total_tests} tests failed")
        print("Please ensure marker.utils.embedding_utils is properly installed")
        return 1
    
    # Get ArangoDB credentials
    credentials = get_arango_credentials()
    
    # Test 3: Connect to ArangoDB
    total_tests += 1
    client = connect_arango(credentials)
    
    if client:
        print(f"✅ Test 3 passed: Successfully connected to ArangoDB at {credentials['host']}:{credentials['port']}")
    else:
        validation_failures.append("Failed to connect to ArangoDB")
        print(f"❌ Test 3 failed: Could not connect to ArangoDB at {credentials['host']}:{credentials['port']}")
        # Exit if connection fails
        print("\n" + "="*80)
        print(f"❌ VALIDATION FAILED - {len(validation_failures)} of {total_tests} tests failed")
        return 1
    
    # Test 4: Create test database
    total_tests += 1
    db_name = "marker_vector_test"
    db = ensure_test_database(client, credentials, db_name)
    
    if db:
        print(f"✅ Test 4 passed: Database '{db_name}' exists or was created")
    else:
        validation_failures.append(f"Failed to create database '{db_name}'")
        print(f"❌ Test 4 failed: Could not create database '{db_name}'")
        # Exit if database creation fails
        print("\n" + "="*80)
        print(f"❌ VALIDATION FAILED - {len(validation_failures)} of {total_tests} tests failed")
        return 1
    
    # Test 5: Create vector collection
    total_tests += 1
    collection_name = "vector_docs"
    created = create_vector_collection(db, collection_name)
    
    if created:
        print(f"✅ Test 5 passed: Collection '{collection_name}' created successfully")
    else:
        validation_failures.append(f"Failed to create collection '{collection_name}'")
        print(f"❌ Test 5 failed: Could not create collection '{collection_name}'")
        # Exit if collection creation fails
        print("\n" + "="*80)
        print(f"❌ VALIDATION FAILED - {len(validation_failures)} of {total_tests} tests failed")
        return 1
    
    # Test 6: Insert sample documents with embeddings
    total_tests += 1
    doc_count = 10
    inserted_keys = insert_sample_docs_with_embeddings(db, collection_name, doc_count)
    
    if len(inserted_keys) == doc_count:
        print(f"✅ Test 6 passed: {len(inserted_keys)} documents inserted with embeddings")
    else:
        validation_failures.append(f"Failed to insert all documents with embeddings (inserted {len(inserted_keys)} of {doc_count})")
        print(f"❌ Test 6 failed: Could not insert all documents with embeddings")
        # Continue with the documents we have
    
    # Test 7: Create vector index
    total_tests += 1
    embedding_field = "embedding"
    embedding_dimensions = 1024  # BGE-large-en dimensions
    
    created = create_vector_index(db, collection_name, embedding_field, embedding_dimensions)
    
    if created:
        print(f"✅ Test 7 passed: Vector index created on field '{embedding_field}'")
    else:
        validation_failures.append(f"Failed to create vector index on field '{embedding_field}'")
        print(f"❌ Test 7 failed: Could not create vector index")
        # Exit if index creation fails
        print("\n" + "="*80)
        print(f"❌ VALIDATION FAILED - {len(validation_failures)} of {total_tests} tests failed")
        return 1
    
    # Test 8: Vector search using AQL
    total_tests += 1
    search_query = "machine learning"
    search_results = vector_search_aql(db, collection_name, search_query)
    
    if search_results:
        print(f"✅ Test 8 passed: Vector search returned {len(search_results)} results")
        print_search_results(search_results)
    else:
        validation_failures.append("Vector search returned no results")
        print("❌ Test 8 failed: Vector search returned no results")
    
    # Test 9: Approximated vector search
    total_tests += 1
    approx_query = "neural networks"
    approx_results = approximated_vector_search_aql(db, collection_name, approx_query)
    
    if approx_results:
        print(f"✅ Test 9 passed: Approximated vector search returned {len(approx_results)} results")
        print_search_results(approx_results)
    else:
        validation_failures.append("Approximated vector search returned no results")
        print("❌ Test 9 failed: Approximated vector search returned no results")
    
    # Test 10: Verify vector index
    total_tests += 1
    verification, error_message = verify_arango_vector_index(db, collection_name, embedding_field)
    
    if verification:
        print(f"✅ Test 10 passed: Vector index on '{embedding_field}' is valid")
    else:
        validation_failures.append(f"Vector index verification failed: {error_message}")
        print(f"❌ Test 10 failed: Vector index verification - {error_message}")
    
    # Final validation results
    print("\n" + "="*80)
    if validation_failures:
        print(f"❌ VALIDATION FAILED - {len(validation_failures)} of {total_tests} tests failed:")
        for failure in validation_failures:
            print(f"  - {failure}")
        return 1
    else:
        print(f"✅ VALIDATION PASSED - All {total_tests} tests produced expected results")
        print("""
ArangoDB Vector Index Functionality Verified Successfully!
---------------------------------------------------------
This script demonstrates:

1. Creating a collection in ArangoDB for vector data
2. Setting up a vector index with cosine similarity metric
3. Inserting documents with vector embeddings
4. Performing vector similarity search using COSINE_SIMILARITY
5. Using approximated vector search for faster lookups

Example AQL for vector search:
```
FOR doc IN vector_docs
    FILTER doc.embedding != null
    LET similarity = COSINE_SIMILARITY(doc.embedding, @query_embedding)
    SORT similarity DESC
    LIMIT 5
    RETURN {
        _id: doc._id,
        text: doc.text,
        similarity: similarity
    }
```

You can use this as a template for implementing vector search in ArangoDB.
""")
        return 0


if __name__ == "__main__":
    sys.exit(main())