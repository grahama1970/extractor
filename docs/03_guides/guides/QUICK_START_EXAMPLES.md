# Marker Debug Examples Guide

This document provides an overview of the example scripts in the `examples/simple` directory, explaining their functionality and use cases for debugging Marker components.

## Vector Search Components

### `vector_search_debug.py`
Demonstrates vector search functionality using ArangoDB with the `APPROX_NEAR_COSINE` operator.

- **Key Functions**:
  - `search_with_approx_near_cosine()` - Uses ArangoDB's vector search with HNSW indexes
  - `search_with_cosine_similarity()` - Fallback method when vector indexes aren't available
  - `fallback_in_memory_search()` - Last resort in-memory search option
  - `search_by_vector_similarity()` - High-level search function that handles fallbacks

- **Usage**:
  ```python
  query = "machine learning algorithms"
  search_results = search_by_vector_similarity(query, db, embedded_corpus)
  ```

### `document_embedding_debug.py`
Shows how to generate embeddings for document sections and perform semantic search.

- **Key Functions**:
  - `embed_document_sections()` - Generates embeddings for document sections
  - `analyze_section_similarities()` - Compares similarities between sections
  - `semantic_search()` - Searches for sections matching a query

- **Usage**:
  ```python
  embedded_blocks = embed_document_sections(text_blocks)
  search_results = semantic_search("embedding techniques", embedded_blocks)
  ```

### `arango_vector_index_debug.py`
Focuses on creating and using vector indexes in ArangoDB for similarity search.

- **Key Functions**:
  - `ensure_vector_index()` - Creates vector indexes with proper configuration
  - Setup of HNSW index with appropriate parameters
  - Dimension and nLists configuration for vector indexes

## Document Processing Components

### `section_hierarchy_debug.py`
Demonstrates section hierarchy and breadcrumb tracking in documents.

- **Key Functions**:
  - `inspect_section_hierarchy()` - Extracts and displays section structure
  - `trace_section_context()` - Finds section context for document blocks
  - `find_section_for_block()` - Determines which section a block belongs to

- **Usage**:
  ```python
  hierarchy_results = inspect_section_hierarchy(document)
  section_info = find_section_for_block(document, block)
  ```

### `code_language_detection_debug.py`
Shows tree-sitter language detection for code blocks with fallback to heuristics.

- **Key Functions**:
  - `detect_language_with_tree_sitter()` - Uses tree-sitter for precise detection
  - `detect_language_heuristic()` - Pattern-based fallback detection
  - `process_code_blocks()` - Processes and detects language for all code blocks

- **Usage**:
  ```python
  results = process_code_blocks(document)
  language_info = detect_language_with_tree_sitter(code_text)
  ```

### `async_image_processing_debug.py`
Demonstrates asynchronous batch processing of image descriptions using LiteLLM.

- **Key Functions**:
  - `ModifiedLLMImageDescriptionProcessor` class for async processing
  - `process_images_sync()` vs `process_images_async()` - Comparison of approaches

- **Usage**:
  ```python
  async_results = process_images_async(document, llm_service)
  ```

## Database Integration

### `arangodb_operations_debug.py`
Demonstrates basic ArangoDB operations from Python.

- **Key Functions**:
  - `verify_arango_connection()` - Tests database connectivity
  - `create_database()` - Creates database if it doesn't exist
  - `create_collections()` - Sets up document and edge collections
  - CRUD operations (insert, query, update, delete)

- **Usage**:
  ```python
  client = ArangoClient(hosts=f"http://{credentials['host']}:8529")
  db = create_database(client, db_name, credentials)
  ```

### `arangodb_json_debug.py`
Demonstrates the ArangoDB JSON renderer for producing graph database-ready document representations.

- **Key Functions**:
  - `simulate_document_with_sections()` - Creates JSON structure with section contexts
  - `analyze_sections_and_breadcrumbs()` - Processes section hierarchies

## Enhanced Features

### `enhanced_features_debug.py`
Comprehensive example showcasing multiple Marker features in one script.

- **Key Components**:
  - Tree-sitter language detection for code blocks
  - LiteLLM integration for multiple LLM providers
  - Asynchronous image description generation
  - Section hierarchy and breadcrumb tracking

## Common Patterns

Across these examples, several common patterns emerge:

1. **Error Handling Flow**:
   All scripts follow a pattern of graceful degradation with fallbacks when primary options fail.

2. **Validation Pattern**:
   Scripts use the validation pattern from CLAUDE.md with explicit failure tracking:
   ```python
   all_validation_failures = []
   total_tests = 0
   
   # Run tests, track failures
   
   if all_validation_failures:
       print(f"❌ VALIDATION FAILED - {len(all_validation_failures)} of {total_tests} tests failed:")
       for failure in all_validation_failures:
           print(f"  - {failure}")
       sys.exit(1)
   else:
       print(f"✅ VALIDATION PASSED - All {total_tests} tests produced expected results")
       sys.exit(0)
   ```

3. **Dependency Availability Checks**:
   Scripts check if required dependencies are available and adapt behavior accordingly.

4. **Real-World Data Testing**:
   Examples use realistic document data structures and test with typical content.

## Best Practices for Debugging Marker

1. **Use the Right Example Script**:
   - For vector search issues: `vector_search_debug.py`
   - For document processing issues: `section_hierarchy_debug.py`, `code_language_detection_debug.py`
   - For ArangoDB issues: `arangodb_operations_debug.py`

2. **Environment Variables**:
   - ArangoDB connection: `ARANGO_HOST`, `ARANGO_PORT`, `ARANGO_USERNAME`, `ARANGO_PASSWORD`
   - Embedding settings: `EMBEDDING_MODEL`, `EMBEDDING_DIMENSION`
   - LLM API keys: `OPENAI_API_KEY`

3. **Common Error Patterns**:
   - Vector index issues: Check dimensions and nLists parameters
   - Tree-sitter: Ensure language parsers are installed
   - ArangoDB connectivity: Test basic operations first