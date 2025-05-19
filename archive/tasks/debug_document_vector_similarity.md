# Task: Debug and Validate Document Vector Similarity Functionality

## Objective
Run and debug the `document_vector_similarity_debug.py` example script to ensure all document vector similarity functionality works correctly with real-world results. The script should run without errors, properly generate embeddings for document sections, calculate section similarities, and perform semantic searches across sections.

## Success Criteria
- The script runs successfully without errors
- All validation tests pass
- Document sections are properly structured
- Embeddings are generated for each section
- Section similarities are calculated correctly
- Semantic search across document sections produces relevant results

## Environment Setup
1. Ensure the project is cloned and available at `/home/graham/workspace/experiments/marker/`
2. Ensure all dependencies are installed via `uv pip install -e .` from the project root
3. Verify the embedding models are accessible

## Steps

### Step 1: Inspect the Example Script
- Review the code in `/home/graham/workspace/experiments/marker/examples/simple/document_vector_similarity_debug.py`
- Verify that it follows the requirements in CLAUDE.md
- Confirm that all functions have appropriate error handling and validation

### Step 2: Verify Dependencies
```bash
cd /home/graham/workspace/experiments/marker/
python -c "from marker.utils.embedding_utils import get_embedding; from marker.schema import BlockTypes; print('Dependencies available')"
```

### Step 3: Run the Script with Basic Validation
```bash
cd /home/graham/workspace/experiments/marker/
python examples/simple/document_vector_similarity_debug.py
```

### Step 4: Debug Document Section Issues (if any)
If the script fails to create or structure document sections:
1. Check the document schema imports
2. Verify the section hierarchy creation logic
3. Try with simpler section structures if necessary
4. Update the script if needed

### Step 5: Debug Embedding Generation Issues (if any)
If the script fails to generate embeddings for sections:
1. Check that the embedding model is accessible
2. Verify the model dimensions match the expected output
3. Try with smaller text samples if necessary
4. Update the script if needed

### Step 6: Debug Section Similarity Issues (if any)
If section similarity calculation does not produce expected results:
1. Check the cosine similarity implementation
2. Verify that the section content is appropriate for testing
3. Try with more distinct section topics to ensure consistent behavior
4. Update the script to improve similarity calculations if necessary

### Step 7: Debug Semantic Search Issues (if any)
If semantic search across document sections does not produce expected results:
1. Check the search query implementation
2. Verify that the search ranking logic is correct
3. Try different queries to ensure consistent behavior
4. Update the script to improve search results if necessary

### Step 8: Verify Real-World Results
To confirm that the results are valid and not mocked:
1. Compare section embeddings from related topics - they should have high similarity
2. Compare section embeddings from different topics - they should have lower similarity
3. Verify that the search results are semantically relevant to the queries
4. Check that section tree structure reflects the expected document hierarchy

## Expected Results
1. All validation tests pass with success message
2. Section embeddings have the correct dimensions (e.g., 1024 for BGE-large-en)
3. Similar sections have high similarity scores (>0.7)
4. Dissimilar sections have lower similarity scores (<0.5)
5. Search queries return semantically relevant document sections

## Troubleshooting
- If document schema imports fail, check if marker.schema is properly installed
- If embeddings fail to generate, check if the model is properly installed and accessible
- If section similarity scores are unexpected, check the text content of the sections
- If search results are poor, try different similarity thresholds or different queries

## Next Steps
After successful debugging and validation:
1. Document any issues encountered and their solutions
2. Consider integrating the document section similarity functionality into the main Marker application
3. Explore advanced features like section recommendations or document summarization
4. Test with real document examples from PDFs

## Reference
- Marker embedding utilities: `/home/graham/workspace/experiments/marker/marker/utils/embedding_utils.py`
- Marker document schema: `/home/graham/workspace/experiments/marker/marker/schema/`
- BGE model documentation: https://huggingface.co/BAAI/bge-large-en