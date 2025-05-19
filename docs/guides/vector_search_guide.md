# Vector Search Implementation Guide

This document provides a detailed overview of the vector search functionality in Marker, focusing on ArangoDB integration with `APPROX_NEAR_COSINE` for efficient semantic search.

## Overview

Vector search in Marker uses ArangoDB's HNSW (Hierarchical Navigable Small World) indexes to perform efficient approximate nearest neighbor search with the `APPROX_NEAR_COSINE` operator. The implementation provides fallback mechanisms for when vector indexes aren't available.

## Key Components

### 1. ArangoDB Connection

The connection to ArangoDB is established using the `python-arango` library:

```python
from arango import ArangoClient
from arango.database import StandardDatabase

def connect_to_arango(url="localhost", username="root", password="", dbname="marker"):
    # Create an ArangoDB client
    client = ArangoClient(hosts=f"http://{url}:8529")
    
    # Connect to the database
    try:
        db = client.db(dbname, username=username, password=password)
        return db
    except Exception as e:
        logger.error(f"Failed to connect to ArangoDB: {e}")
        return None
```

### 2. Vector Index Creation

Vector indexes must be created before using `APPROX_NEAR_COSINE`:

```python
def ensure_vector_index(
    db: StandardDatabase,
    collection_name: str,
    field_name: str = "combined_embedding",
    dimensions: int = 1024,
    nlists: int = 4
) -> bool:
    try:
        # Check if vector index exists on the field
        if check_vector_index_exists(db, collection_name, field_name):
            return True
        
        # Create vector index configuration
        index_config = {
            "type": "vector",
            "fields": [field_name],
            "params": {
                "metric": "cosine",
                "dimension": dimensions,
                "nLists": nlists  # Must be <= document count
            },
            "name": f"vector_idx_{field_name}"
        }
        
        # Create the index
        collection = db.collection(collection_name)
        collection.add_index(index_config)
        return True
    except Exception as e:
        logger.error(f"Error creating vector index: {e}")
        return False
```

**Important**: The `nLists` parameter must be less than or equal to the number of documents in the collection. For small test collections, use `min(4, len(documents) - 1)`.

### 3. Embedding Generation

Embeddings are generated using `marker.utils.embedding_utils`:

```python
def get_embedding(text: str) -> List[float]:
    """Generate vector embedding for the given text."""
    # Implementation depends on embedding model in use
    # Default is BAAI/bge-large-en-v1.5 with 1024 dimensions
```

### 4. Vector Search with APPROX_NEAR_COSINE

The primary vector search function:

```python
def search_with_approx_near_cosine(
    db: StandardDatabase, 
    query_embedding: List[float], 
    collection_name: str, 
    embedding_field: str,
    limit: int = 5
) -> List[Dict[str, Any]]:
    """Perform vector search using APPROX_NEAR_COSINE AQL operator."""
    # Check if vector index exists
    has_vector_index = check_vector_index_exists(db, collection_name, embedding_field)
    
    if not has_vector_index:
        logger.warning(f"No vector index found for {embedding_field}, falling back to COSINE_SIMILARITY")
        return search_with_cosine_similarity(db, collection_name, embedding_field, query_embedding, limit)
    
    try:
        # Use APPROX_NEAR_COSINE which requires vector index
        vector_query = f"""
        FOR doc IN {collection_name}
          LET score = APPROX_NEAR_COSINE(doc.{embedding_field}, @query_embedding)
          SORT score DESC
          LIMIT {limit}
          RETURN {{
            "id": doc._id,
            "_key": doc._key,
            "title": doc.title,
            "content": doc.content,
            "category": doc.category,
            "similarity_score": score
          }}
        """
        
        bind_vars = {'query_embedding': query_embedding}
        cursor = db.aql.execute(vector_query, bind_vars=bind_vars)
        results = [doc for doc in cursor]
        
        if not results:
            logger.warning("No results from APPROX_NEAR_COSINE, falling back to COSINE_SIMILARITY")
            return search_with_cosine_similarity(db, collection_name, embedding_field, query_embedding, limit)
        
        return results
    except Exception as e:
        logger.error(f"Vector search with APPROX_NEAR_COSINE failed: {e}")
        logger.warning("Falling back to COSINE_SIMILARITY")
        return search_with_cosine_similarity(db, collection_name, embedding_field, query_embedding, limit)
```

### 5. Fallback Mechanism

If `APPROX_NEAR_COSINE` fails (usually due to missing vector index), the system falls back to `COSINE_SIMILARITY`:

```python
def search_with_cosine_similarity(
    db: StandardDatabase, 
    collection_name: str, 
    embedding_field: str, 
    query_embedding: List[float],
    limit: int = 5
) -> List[Dict[str, Any]]:
    """
    Perform vector search using COSINE_SIMILARITY AQL function.
    This is a fallback when vector indexes are not available.
    """
    try:
        cosine_query = f"""
        FOR doc IN {collection_name}
        FILTER HAS(doc, "{embedding_field}") AND IS_LIST(doc.{embedding_field})
        LET score = COSINE_SIMILARITY(doc.{embedding_field}, @query_embedding)
        SORT score DESC
        LIMIT {limit}
        RETURN {{
            "id": doc._id,
            "_key": doc._key,
            "title": doc.title,
            "content": doc.content,
            "category": doc.category,
            "similarity_score": score
        }}
        """
        
        bind_vars = {"query_embedding": query_embedding}
        cursor = db.aql.execute(cosine_query, bind_vars=bind_vars)
        return [doc for doc in cursor]
    except Exception as e:
        logger.error(f"Vector search with COSINE_SIMILARITY failed: {e}")
        return []
```

### 6. High-Level Search Function

A unified high-level function that handles all cases:

```python
def search_by_vector_similarity(
    query: str, 
    db: Optional[StandardDatabase] = None, 
    corpus: Optional[List[Dict[str, Any]]] = None, 
    field: str = "combined_embedding",
    top_k: int = 3
) -> List[Dict[str, Any]]:
    """
    Search by vector similarity using ArangoDB with APPROX_NEAR_COSINE.
    Falls back to in-memory search if ArangoDB is not available.
    
    Args:
        query: Search query text
        db: ArangoDB database instance (optional if corpus is provided)
        corpus: List of document dictionaries with embeddings (used as fallback)
        field: The embedding field to use for similarity calculation
        top_k: Number of top results to return
    """
    # Generate query embedding
    query_embedding = get_embedding(query)
    
    # Try ArangoDB first if available
    if db is not None:
        try:
            results = search_with_approx_near_cosine(
                db, query_embedding, "documents", field, top_k
            )
            return results
        except Exception as e:
            logger.error(f"ArangoDB search failed: {e}")
            # Fall back to in-memory search
    
    # If ArangoDB failed or isn't available, use in-memory search
    if corpus:
        return fallback_in_memory_search(query_embedding, corpus, field, top_k)
    
    return []
```

## Configuration Parameters

### Vector Index Parameters

1. **dimensions**: Should match your embedding model's output dimension
   - Example: 1024 for BAAI/bge-large-en-v1.5

2. **nLists**: Number of clusters for HNSW algorithm
   - Must be <= document count
   - Use `nlists = min(4, len(documents) - 1)` for small test collections
   - For production, 4-16 is typical for small collections (<1000 docs)

3. **metric**: Similarity metric
   - Use "cosine" for text embeddings
   - Other options: "euclidean", "manhattan"

## Environment Configuration

Key environment variables:

```
ARANGO_HOST=localhost
ARANGO_PORT=8529
ARANGO_USERNAME=root
ARANGO_PASSWORD=
ARANGO_DB=marker

EMBEDDING_MODEL=BAAI/bge-large-en-v1.5
EMBEDDING_DIMENSION=1024
```

## Troubleshooting

### Vector Index Creation Issues

1. **Invalid format**: Ensure embeddings are stored as arrays of numbers in ArangoDB
   ```python
   if embedding_type != "array":
       # Fix the embeddings in the collection
       fix_aql = f"""
       FOR doc IN {collection_name}
           FILTER HAS(doc, "{field_name}")
           UPDATE doc WITH {{ 
               {field_name}: (
                   FOR i IN 0..LENGTH(doc.{field_name})-1
                   RETURN TO_NUMBER(doc.{field_name}[i])
               ) 
           }} IN {collection_name}
       """
       db.aql.execute(fix_aql)
   ```

2. **nLists too large**: If you get errors about nLists, check document count
   ```python
   count_query = f"""
   RETURN LENGTH(
       FOR doc IN {collection_name}
       FILTER HAS(doc, "{field_name}") AND IS_LIST(doc.{field_name})
       RETURN 1
   )
   """
   count_result = list(db.aql.execute(count_query))[0]
   
   if count_result < nlists:
       logger.warning(f"Not enough documents with embeddings for nLists={nlists}. Found {count_result}, need at least {nlists}.")
       nlists = max(1, count_result - 1)
   ```

### APPROX_NEAR_COSINE Failures

If you get "no suitable inverted index found" or "unknown function" errors:

1. Check if vector index exists and is properly created
2. Verify embedding dimensions match the index definition
3. Make sure embeddings have correct format in ArangoDB (arrays of numbers)
4. Try searching with COSINE_SIMILARITY as a fallback