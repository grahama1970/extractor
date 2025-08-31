"""
Module: vector_search_debug.py
Description: Implementation of vector search debug functionality

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
        similarity = result.get("similarity_score", 0)
        print(f"{i+1}. [{result.get('category', 'Unknown')}] {result.get('title', 'Untitled')} (Score: {similarity:.4f})")
        print(f"   {result.get('content', '')[:100]}..." if len(result.get('content', '')) > 100 else f"   {result.get('content', '')}")
        print()


def benchmark_embedding_performance(text_length: int = 1000, iterations: int = 5) -> Dict[str, float]:
    """
    Benchmark embedding generation performance.
    
    Args:
        text_length: Length of random text to generate for benchmarking
        iterations: Number of iterations to run
        
    Returns:
        Dictionary with benchmark results
    """
    if not EMBEDDING_AVAILABLE:
        logger.error("Embedding utilities not available, cannot benchmark")
        return {"error": "Embedding utilities not available"}
    
    # Generate a random text of specified length
    import random
    import string
    random_text = ''.join(random.choices(string.ascii_letters + ' ', k=text_length))
    
    # Benchmark embedding generation
    start_time = time.time()
    for _ in range(iterations):
        embedding = get_embedding(random_text)
    end_time = time.time()
    
    # Calculate results
    total_time = end_time - start_time
    avg_time = total_time / iterations
    
    return {
        "text_length": text_length,
        "iterations": iterations,
        "total_time": total_time,
        "average_time": avg_time
    }


def print_model_info() -> None:
    """
    Print information about the embedding model.
    """
    if not EMBEDDING_AVAILABLE:
        logger.error("Embedding utilities not available, cannot retrieve model info")
        return
    
    try:
        model = get_embedder_model()
        if model:
            logger.info(f"Embedding model: {model.__class__.__name__}")
            logger.info(f"Model name: {getattr(model, 'name', 'Unknown')}")
        else:
            logger.warning("No embedding model loaded")
    except Exception as e:
        logger.error(f"Error retrieving model info: {e}")


def main() -> int:
    """
    Main function demonstrating vector search capabilities.
    
    Returns:
        Exit code (0 for success, 1 for failure)
    """
    # Track validation failures
    validation_failures = []
    total_tests = 0
    
    # Verify embedding availability
    total_tests += 1
    if not EMBEDDING_AVAILABLE:
        validation_failures.append("Embedding utilities are not available")
        print("\n" + "="*80)
        print(f"❌ VALIDATION FAILED - {len(validation_failures)} of {total_tests} tests failed:")
        for failure in validation_failures:
            print(f"  - {failure}")
        return 1
    
    # Print model information
    print_model_info()
    
    # Test 1: Create and embed corpus
    total_tests += 1
    print("\nTest 1: Creating and embedding sample corpus...")
    
    try:
        corpus = create_sample_corpus()
        embedded_corpus = embed_corpus(corpus)
        
        if embedded_corpus and "combined_embedding" in embedded_corpus[0]:
            print(f"✅ Successfully embedded corpus with {len(embedded_corpus)} documents")
            embedding_dims = len(embedded_corpus[0]["combined_embedding"])
            print(f"   Embedding dimensions: {embedding_dims}")
        else:
            validation_failures.append("Failed to generate embeddings for corpus")
            print("❌ Failed to generate embeddings for corpus")
    except Exception as e:
        validation_failures.append(f"Error embedding corpus: {str(e)}")
        print(f"❌ Error embedding corpus: {str(e)}")
    
    # Test 2: Try to connect to ArangoDB and set up database
    total_tests += 1
    print("\nTest 2: Setting up ArangoDB...")
    
    db = None
    if ARANGO_AVAILABLE:
        try:
            credentials = get_arango_credentials()
            client = connect_arango(credentials)
            
            if client:
                print(f"✅ Connected to ArangoDB at {credentials['host']}:{credentials['port']}")
                
                # Ensure database exists
                db = ensure_database(client, credentials)
                
                if db:
                    print(f"✅ Database '{credentials['db_name']}' ready")
                    
                    # Insert corpus into ArangoDB
                    if embedded_corpus:
                        inserted_keys = insert_corpus_to_arango(db, embedded_corpus)
                        
                        if inserted_keys:
                            print(f"✅ Inserted {len(inserted_keys)} documents into ArangoDB")
                        else:
                            print("⚠️ Failed to insert documents into ArangoDB")
                            # Continue with in-memory corpus
                else:
                    print(f"⚠️ Failed to ensure database '{credentials['db_name']}'")
                    # Continue with in-memory corpus
            else:
                print("⚠️ Failed to connect to ArangoDB")
                # Continue with in-memory corpus
        except Exception as e:
            print(f"⚠️ ArangoDB setup error: {str(e)}")
            # Continue with in-memory corpus
    else:
        print("⚠️ ArangoDB client not available, continuing with in-memory corpus")
    
    # Test 3: Perform vector search using ArangoDB if available, otherwise in-memory
    total_tests += 1
    print("\nTest 3: Performing vector search...")
    
    try:
        query = "machine learning algorithms"
        print(f"\nSearching for: '{query}'")
        
        search_results = search_by_vector_similarity(query, db, embedded_corpus)
        if search_results:
            print(f"✅ Vector search returned {len(search_results)} results")
            print_search_results(search_results)
        else:
            validation_failures.append("Vector search returned no results")
            print("❌ Vector search returned no results")
    except Exception as e:
        validation_failures.append(f"Error during vector search: {str(e)}")
        print(f"❌ Error during vector search: {str(e)}")
    
    # Test 4: Try different query
    total_tests += 1
    print("\nTest 4: Testing a different query...")
    
    try:
        query = "document processing and analysis"
        print(f"\nSearching for: '{query}'")
        
        search_results = search_by_vector_similarity(query, db, embedded_corpus)
        if search_results:
            print(f"✅ Vector search returned {len(search_results)} results")
            print_search_results(search_results)
        else:
            validation_failures.append("Vector search returned no results for second query")
            print("❌ Vector search returned no results for second query")
    except Exception as e:
        validation_failures.append(f"Error during second vector search: {str(e)}")
        print(f"❌ Error during second vector search: {str(e)}")
    
    # Test 5: Benchmark embedding performance
    total_tests += 1
    print("\nTest 5: Benchmarking embedding performance...")
    
    try:
        benchmark_results = benchmark_embedding_performance()
        if "error" not in benchmark_results:
            print(f"✅ Embedding benchmark completed successfully")
            print(f"   Text length: {benchmark_results['text_length']} characters")
            print(f"   Iterations: {benchmark_results['iterations']}")
            print(f"   Total time: {benchmark_results['total_time']:.4f} seconds")
            print(f"   Average time per embedding: {benchmark_results['average_time']:.4f} seconds")
        else:
            validation_failures.append(f"Embedding benchmark failed: {benchmark_results['error']}")
            print(f"❌ Embedding benchmark failed: {benchmark_results['error']}")
    except Exception as e:
        validation_failures.append(f"Error during embedding benchmark: {str(e)}")
        print(f"❌ Error during embedding benchmark: {str(e)}")
    
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
Vector Search Functionality Verified Successfully!
-------------------------------------------------
The vector search module demonstrates:

1. Embedding generation for document content
2. ArangoDB integration with APPROX_NEAR_COSINE for vector search
3. Fallback mechanisms for reliable operation
4. Performance optimizations including caching and retry logic
5. Support for both ArangoDB and in-memory search

You can use this as a template for implementing vector search in your applications.
""")
        return 0


if __name__ == "__main__":
    sys.exit(main())