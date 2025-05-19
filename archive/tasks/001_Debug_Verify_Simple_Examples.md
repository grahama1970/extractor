# 001 - Debug and Verify Marker Simple Examples

## Objective
Run and debug all example scripts in the `examples/simple/` directory to ensure all functionality works as expected with real-world results. Each file will be validated separately to ensure it runs without errors and produces valid, non-mocked output.

## Success Criteria
- All scripts run successfully without errors
- All validation tests in each script pass
- Results match expected real-world outcomes
- No mocked data or results are used
- All functionality is properly documented

## Environment Setup
1. Ensure the project is cloned and available at `/home/graham/workspace/experiments/marker/`
2. Ensure all dependencies are installed via `uv pip install -e .` from the project root
3. Ensure ArangoDB is installed and running for the ArangoDB examples
4. Set environment variables as needed for specific examples

## Files to Verify

1. **vector_search_debug.py**
2. **arango_vector_index_debug.py**
3. **document_vector_similarity_debug.py**
4. **document_embedding_debug.py**
5. **arangodb_json_debug.py**
6. **arangodb_operations_debug.py**
7. **async_image_processing_debug.py**
8. **code_language_detection_debug.py**
9. **enhanced_features_debug.py**
10. **litellm_cache_debug.py**
11. **marker_doc_object.py**
12. **section_hierarchy_debug.py**
13. **table_data_debug.py**

## Debug Process for Each File

### General Steps for Each File
1. Review the file's documentation and purpose
2. Verify all dependencies are available
3. Run the script through its `if __name__ == "__main__":` block
4. Debug any issues that arise
5. Verify results against expected real-world outcomes
6. Document any issues and their solutions

### Failure Handling Protocol
- After 2 failures to run a script successfully, use the perplexity_ask tool to research solutions
- After 4 failures, stop and ask the human for clarifying questions
- Document all failures and attempted solutions

## Critical Validation Requirements
- **NEVER print "All Tests Passed" or similar success messages unless ALL tests actually passed**
- **NEVER suppress or ignore failures - ALL failures must be reported**
- **NEVER add code that masks or ignores errors**
- **ALWAYS verify actual results against expected results BEFORE reporting success**
- **ALWAYS track and report ALL failures, not just the first one encountered**
- **ALWAYS include detailed failure information (expected vs. actual results)**
- **ALWAYS ensure validation output includes count of failed tests out of total tests run**
- **NEVER use mocked data or mocked test results**
- **Exit with code 1 if ANY tests fail, and code 0 ONLY if ALL tests pass**

## Task 1: vector_search_debug.py

### Steps
1. Inspect the example script and understand its purpose and expected outcomes
2. Verify the embedding utilities are available:
   ```bash
   cd /home/graham/workspace/experiments/marker/
   python -c "from marker.utils.embedding_utils import get_embedding; print('Embedding utilities available')"
   ```
3. Run the script:
   ```bash
   cd /home/graham/workspace/experiments/marker/
   python examples/simple/vector_search_debug.py
   ```
4. Verify that:
   - Embeddings are generated with proper dimensions
   - Search queries return semantically relevant results
   - Similarity scores are plausible
   - Benchmark functions complete successfully

### Expected Results
- ALL tests must actually pass for success message to be printed
- Vector embeddings have the expected dimensions
- Search results are semantically relevant to queries
- No errors or exceptions occur during execution
- If ANY test fails, see detailed failure information

## Task 2: arango_vector_index_debug.py

### Steps
1. Inspect the example script and understand its purpose and expected outcomes
2. Verify ArangoDB is running:
   ```bash
   curl http://localhost:8529/_api/version
   ```
3. Verify the necessary dependencies:
   ```bash
   cd /home/graham/workspace/experiments/marker/
   python -c "import arango; from marker.utils.embedding_utils import get_embedding; print('Dependencies available')"
   ```
4. Run the script:
   ```bash
   cd /home/graham/workspace/experiments/marker/
   python examples/simple/arango_vector_index_debug.py
   ```
5. Verify that:
   - Connection to ArangoDB is successful
   - Test database and collections are created
   - Vector indexes are created with proper configuration
   - Documents with embeddings are inserted successfully
   - Vector searches return semantically relevant results

### Expected Results
- ALL tests must actually pass for success message to be printed
- ArangoDB structures are created and verified
- Vector searches produce meaningful results
- No errors or exceptions occur during execution
- If ANY test fails, see detailed failure information

## Task 3: document_vector_similarity_debug.py

### Steps
1. Inspect the example script and understand its purpose and expected outcomes
2. Verify the necessary dependencies:
   ```bash
   cd /home/graham/workspace/experiments/marker/
   python -c "from marker.utils.embedding_utils import get_embedding; from marker.schema import BlockTypes; print('Dependencies available')"
   ```
3. Run the script:
   ```bash
   cd /home/graham/workspace/experiments/marker/
   python examples/simple/document_vector_similarity_debug.py
   ```
4. Verify that:
   - Document sections are properly structured
   - Embeddings are generated for each section
   - Section similarities are calculated correctly
   - Semantic search across document sections produces relevant results

### Expected Results
- ALL tests must actually pass for success message to be printed
- Section embeddings have the expected dimensions
- Section similarities match semantic relationships
- Search queries return relevant document sections
- No errors or exceptions occur during execution
- If ANY test fails, see detailed failure information

## Task 4: document_embedding_debug.py

### Steps
1. Inspect the example script and understand its purpose and expected outcomes
2. Verify the necessary dependencies:
   ```bash
   cd /home/graham/workspace/experiments/marker/
   python -c "from marker.utils.embedding_utils import get_embedding; print('Embedding utilities available')"
   ```
3. Run the script:
   ```bash
   cd /home/graham/workspace/experiments/marker/
   python examples/simple/document_embedding_debug.py
   ```
4. Verify that:
   - Test documents are created successfully
   - Document text blocks are properly extracted
   - Embeddings are generated for document sections
   - Section similarity analysis works correctly
   - Semantic search functionality produces relevant results

### Expected Results
- ALL tests must actually pass for success message to be printed
- Document embeddings have the expected dimensions
- Document sections are properly embedded
- No errors or exceptions occur during execution
- If ANY test fails, see detailed failure information

## Task 5: arangodb_json_debug.py

### Steps
1. Inspect the example script and understand its purpose and expected outcomes
2. Verify ArangoDB renderer is available:
   ```bash
   cd /home/graham/workspace/experiments/marker/
   python -c "from marker.renderers.arangodb_json import ArangoDBRenderer; print('ArangoDB renderer available')"
   ```
3. Run the script:
   ```bash
   cd /home/graham/workspace/experiments/marker/
   python examples/simple/arangodb_json_debug.py
   ```
4. Verify that:
   - ArangoDB JSON representation is correctly generated
   - Section hierarchy and breadcrumbs are properly structured
   - Debug output is saved to the expected location

### Expected Results
- ALL tests must actually pass for success message to be printed
- ArangoDB JSON structure follows expected format
- Section hierarchy is correctly represented
- No errors or exceptions occur during execution
- If ANY test fails, see detailed failure information

## Task 6: arangodb_operations_debug.py

### Steps
1. Inspect the example script and understand its purpose and expected outcomes
2. Verify ArangoDB is running:
   ```bash
   curl http://localhost:8529/_api/version
   ```
3. Verify the necessary dependencies:
   ```bash
   cd /home/graham/workspace/experiments/marker/
   python -c "import arango; print('ArangoDB client available')"
   ```
4. Run the script:
   ```bash
   cd /home/graham/workspace/experiments/marker/
   python examples/simple/arangodb_operations_debug.py
   ```
5. Verify that:
   - Connection to ArangoDB is successful
   - Database and collections are created
   - CRUD operations work as expected
   - AQL queries execute successfully

### Expected Results
- ALL tests must actually pass for success message to be printed
- ArangoDB operations complete successfully
- No errors or exceptions occur during execution
- If ANY test fails, see detailed failure information

## Task 7: async_image_processing_debug.py

### Steps
1. Inspect the example script and understand its purpose and expected outcomes
2. Verify the necessary dependencies:
   ```bash
   cd /home/graham/workspace/experiments/marker/
   python -c "import asyncio; print('Async libraries available')"
   ```
3. Run the script:
   ```bash
   cd /home/graham/workspace/experiments/marker/
   python examples/simple/async_image_processing_debug.py
   ```
4. Verify that:
   - Async image processing functions initialize correctly
   - Images are processed concurrently
   - Results are collected properly
   - Performance metrics match expectations

### Expected Results
- ALL tests must actually pass for success message to be printed
- Async processing improves performance
- Results are consistent with synchronous processing
- No errors or exceptions occur during execution
- If ANY test fails, see detailed failure information

## Task 8: code_language_detection_debug.py

### Steps
1. Inspect the example script and understand its purpose and expected outcomes
2. Verify the necessary dependencies:
   ```bash
   cd /home/graham/workspace/experiments/marker/
   python -c "from marker.services.utils.tree_sitter_utils import detect_language; print('Language detection available')"
   ```
3. Run the script:
   ```bash
   cd /home/graham/workspace/experiments/marker/
   python examples/simple/code_language_detection_debug.py
   ```
4. Verify that:
   - Language detection functions initialize correctly
   - Code samples are correctly identified
   - Confidence scores match expectations
   - Edge cases are handled properly

### Expected Results
- ALL tests must actually pass for success message to be printed
- Languages are correctly detected
- No errors or exceptions occur during execution
- If ANY test fails, see detailed failure information

## Task 9: enhanced_features_debug.py

### Steps
1. Inspect the example script and understand its purpose and expected outcomes
2. Verify the necessary dependencies are available
3. Run the script:
   ```bash
   cd /home/graham/workspace/experiments/marker/
   python examples/simple/enhanced_features_debug.py
   ```
4. Verify that:
   - Enhanced features initialize correctly
   - Processing functions work as expected
   - Results match expected outputs
   - Debug output is saved to the expected location

### Expected Results
- ALL tests must actually pass for success message to be printed
- Enhanced features work as expected
- No errors or exceptions occur during execution
- If ANY test fails, see detailed failure information

## Task 10: litellm_cache_debug.py

### Steps
1. Inspect the example script and understand its purpose and expected outcomes
2. Verify the necessary dependencies:
   ```bash
   cd /home/graham/workspace/experiments/marker/
   python -c "from marker.services.utils.litellm_cache import LiteLLMCache; print('LiteLLM cache available')"
   ```
3. Run the script:
   ```bash
   cd /home/graham/workspace/experiments/marker/
   python examples/simple/litellm_cache_debug.py
   ```
4. Verify that:
   - Cache initialization is successful
   - Cache operations work as expected
   - Performance improvements are measurable
   - Cache expiration works correctly

### Expected Results
- ALL tests must actually pass for success message to be printed
- Cache operations improve performance
- No errors or exceptions occur during execution
- If ANY test fails, see detailed failure information

## Task 11: marker_doc_object.py

### Steps
1. Inspect the example script and understand its purpose and expected outcomes
2. Verify the necessary dependencies:
   ```bash
   cd /home/graham/workspace/experiments/marker/
   python -c "from marker.schema.document import Document; print('Document schema available')"
   ```
3. Run the script:
   ```bash
   cd /home/graham/workspace/experiments/marker/
   python examples/simple/marker_doc_object.py
   ```
4. Verify that:
   - Document objects are created correctly
   - Document operations work as expected
   - Document rendering produces expected output
   - Document manipulation functions work correctly

### Expected Results
- ALL tests must actually pass for success message to be printed
- Document object operations work as expected
- No errors or exceptions occur during execution
- If ANY test fails, see detailed failure information

## Task 12: section_hierarchy_debug.py

### Steps
1. Inspect the example script and understand its purpose and expected outcomes
2. Verify the necessary dependencies:
   ```bash
   cd /home/graham/workspace/experiments/marker/
   python -c "from marker.schema.document import Document; print('Document schema available')"
   ```
3. Run the script:
   ```bash
   cd /home/graham/workspace/experiments/marker/
   python examples/simple/section_hierarchy_debug.py
   ```
4. Verify that:
   - Section hierarchy is correctly built
   - Breadcrumbs are generated properly
   - Section navigation works as expected
   - Hierarchy manipulation functions work correctly

### Expected Results
- ALL tests must actually pass for success message to be printed
- Section hierarchy operations work as expected
- No errors or exceptions occur during execution
- If ANY test fails, see detailed failure information

## Task 13: table_data_debug.py

### Steps
1. Inspect the example script and understand its purpose and expected outcomes
2. Verify the necessary dependencies:
   ```bash
   cd /home/graham/workspace/experiments/marker/
   python -c "from marker.schema.blocks.table import Table; print('Table schema available')"
   ```
3. Run the script:
   ```bash
   cd /home/graham/workspace/experiments/marker/
   python examples/simple/table_data_debug.py
   ```
4. Verify that:
   - Table data structures are correctly built
   - Table parsing functions work as expected
   - Table formatting produces expected output
   - Table manipulation functions work correctly

### Expected Results
- ALL tests must actually pass for success message to be printed
- Table operations work as expected
- No errors or exceptions occur during execution
- If ANY test fails, see detailed failure information

## Troubleshooting Protocol

### If a Script Fails Once:
1. Review error messages carefully
2. Check that all dependencies are properly installed
3. Verify environment setup (e.g., ArangoDB running for ArangoDB examples)
4. Make minimal changes to fix the issue
5. Retry running the script

### If a Script Fails Twice:
1. Use perplexity_ask tool to research the issue:
   ```
   Ask perplexity: "How to solve [specific error] in [context of the script]"
   ```
2. Apply suggested solutions
3. Document the research findings and solutions
4. Retry running the script

### If a Script Fails Four Times:
1. Stop debugging the script
2. Prepare detailed questions for the human:
   - What is the expected environment for this script?
   - Are there specific configurations needed?
   - What are the expected inputs and outputs?
   - Are there known issues with this functionality?
3. Await human clarification before proceeding

## Validation Code Modifications
If any script validation code needs to be fixed, ensure it follows these patterns:

```python
# INCORRECT - DO NOT DO THIS:
if __name__ == "__main__":
    test_data = "test input"
    result = process_data(test_data)
    # This always prints regardless of success/failure
    print("✅ VALIDATION PASSED - All tests successful")

# CORRECT IMPLEMENTATION:
if __name__ == "__main__":
    import sys
    
    # List to track all validation failures
    all_validation_failures = []
    total_tests = 0
    
    # Test 1: Basic functionality
    total_tests += 1
    test_data = "example input"
    result = process_data(test_data)
    expected = {"key": "processed value"}
    if result != expected:
        all_validation_failures.append(f"Basic test: Expected {expected}, got {result}")
    
    # Test 2: Edge case handling
    total_tests += 1
    edge_case = "empty"
    edge_result = process_data(edge_case)
    edge_expected = {"key": ""}
    if edge_result != edge_expected:
        all_validation_failures.append(f"Edge case: Expected {edge_expected}, got {edge_result}")
    
    # Test 3: Error handling
    total_tests += 1
    try:
        error_result = process_data(None)
        all_validation_failures.append("Error handling: Expected exception for None input, but no exception was raised")
    except ValueError:
        # This is expected - test passes
        pass
    except Exception as e:
        all_validation_failures.append(f"Error handling: Expected ValueError for None input, but got {type(e).__name__}")
    
    # Final validation result
    if all_validation_failures:
        print(f"❌ VALIDATION FAILED - {len(all_validation_failures)} of {total_tests} tests failed:")
        for failure in all_validation_failures:
            print(f"  - {failure}")
        sys.exit(1)  # Exit with error code
    else:
        print(f"✅ VALIDATION PASSED - All {total_tests} tests produced expected results")
        sys.exit(0)  # Exit with success code
```

## Final Deliverables
1. A report of all scripts tested, with status (pass/fail)
2. Documentation of any issues encountered and their solutions
3. Any recommended improvements to make the example scripts more robust
4. Verification that all scripts run successfully with real-world results
5. Confirmation that no mocked data or results were used

## Reference
- Marker project structure and documentation
- Script-specific documentation within each file
- Relevant API documentation for dependencies