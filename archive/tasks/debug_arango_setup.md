# Task: Debug and Validate ArangoDB Setup Script

## Objective
Run and debug the main `arango_setup.py` script to ensure it correctly sets up an ArangoDB database with proper collections, views, and vector indexes. The script should run without errors, establish connections, create all necessary database structures, and validate the setup.

## Success Criteria
- The script runs successfully without errors
- All validation tests pass
- ArangoDB database is created with proper collections
- ArangoSearch view is created with text and vector search capabilities
- Vector indexes are created with proper configuration
- Sample document insertion works correctly
- Vector and hybrid searches produce relevant results

## Environment Setup
1. Ensure the project is cloned and available at `/home/graham/workspace/experiments/marker/`
2. Ensure all dependencies are installed via `uv pip install -e .` from the project root
3. Verify that ArangoDB is installed and running
4. Set environment variables for ArangoDB connection if necessary:
   ```bash
   export ARANGO_HOST=localhost
   export ARANGO_PORT=8529
   export ARANGO_USERNAME=root
   export ARANGO_PASSWORD=openSesame
   export ARANGO_DB=marker
   ```

## Steps

### Step 1: Inspect the Setup Script
- Review the code in `/home/graham/workspace/experiments/marker/examples/arango_setup.py`
- Verify that it follows the requirements in CLAUDE.md
- Confirm that all functions have appropriate error handling and validation

### Step 2: Verify Dependencies
```bash
cd /home/graham/workspace/experiments/marker/
python -c "import arango; from marker.utils.embedding_utils import get_embedding; print('Dependencies available')"
```

### Step 3: Run the Script with Basic Validation
```bash
cd /home/graham/workspace/experiments/marker/
python examples/arango_setup.py
```

### Step 4: Debug ArangoDB Connection Issues (if any)
If the script fails to connect to ArangoDB:
1. Verify that ArangoDB is running: `curl http://localhost:8529/_api/version`
2. Check the connection credentials
3. Ensure no network restrictions are blocking the connection
4. Update the script with correct credentials if necessary

### Step 5: Debug Database and Collection Creation Issues (if any)
If database or collection creation fails:
1. Check user permissions in ArangoDB
2. Verify that the collections don't already exist with different configurations
3. Try dropping and recreating the database if necessary
4. Update the script if needed

### Step 6: Debug ArangoSearch View Creation Issues (if any)
If view creation fails:
1. Check if the ArangoDB version supports ArangoSearch views
2. Verify the view configuration parameters
3. Check if the text analyzer exists or can be created
4. Update the script if needed

### Step 7: Debug Vector Index Creation Issues (if any)
If vector index creation fails:
1. Check if the ArangoDB version supports vector indexes
2. Verify the index configuration parameters
3. Try with different dimensions or parameters if necessary
4. Update the script if needed

### Step 8: Debug Sample Document Insertion Issues (if any)
If document insertion fails:
1. Check that embeddings are generated correctly
2. Verify collection permissions
3. Check for duplicate keys or other insertion errors
4. Update the script if needed

### Step 9: Debug Search Issues (if any)
If vector or hybrid search does not produce expected results:
1. Check the AQL query syntax
2. Verify that COSINE_SIMILARITY function is available
3. Check that documents have embeddings
4. Update the script to improve search results if necessary

### Step 10: Verify Real-World Results
To confirm that the results are valid and not mocked:
1. Connect to ArangoDB web interface and verify the created database, collections, views, and indexes
2. Check that documents are actually inserted with embeddings
3. Run manual AQL queries to verify search results
4. Verify that search results are semantically relevant to the queries

## Expected Results
1. All validation tests pass with success message
2. ArangoDB database is created with proper collections
3. ArangoSearch view is created with correct configuration
4. Vector indexes are created with correct parameters
5. Sample documents are inserted with embeddings
6. Vector and hybrid searches return semantically relevant results

## Troubleshooting
- If ArangoDB connection fails, check if the service is running and accessible
- If database or collection creation fails, check user permissions
- If view creation fails, check ArangoDB version (3.7+ required for ArangoSearch)
- If vector index creation fails, check ArangoDB version (3.9+ required for vector indexes)
- If embeddings fail to generate, check if the model is properly installed and accessible
- If search results are poor, try different AQL queries or similarity thresholds

## Next Steps
After successful debugging and validation:
1. Document any issues encountered and their solutions
2. Consider integrating the ArangoDB setup into the main Marker application initialization
3. Explore advanced features like hybrid search combining text and vector search
4. Optimize ArangoDB configuration for production use

## Reference
- Marker embedding utilities: `/home/graham/workspace/experiments/marker/marker/utils/embedding_utils.py`
- ArangoDB vector search documentation: https://www.arangodb.com/docs/stable/arangosearch-vector-search.html
- ArangoDB AQL documentation: https://www.arangodb.com/docs/stable/aql/
- ArangoDB views documentation: https://www.arangodb.com/docs/stable/arangosearch-views.html