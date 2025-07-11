"""
ArangoDB Setup Utility for Marker Project
Module: arango_setup.py
Description: Functions for arango setup operations

This module provides utilities for setting up ArangoDB for vector search functionality
in the marker project. It includes functions for:
- Connecting to ArangoDB
- Creating and configuring databases
- Setting up collections
- Creating vector indexes for embedding fields
- Creating ArangoSearch views

Links:
- python-arango: https://python-arango.readthedocs.io/
- ArangoDB: https://www.arangodb.com/docs/
- ArangoDB Vector Search: https://www.arangodb.com/docs/stable/arangosearch-vector-search.html

Sample Input/Output:

- connect_arango():
  Input: None (uses environment variables)
  Output: ArangoClient instance

- ensure_database(client: ArangoClient):
  Input: ArangoClient instance
  Output: StandardDatabase instance

- ensure_collection(db: StandardDatabase, collection_name: str):
  Input: Database instance, collection name
  Output: True if collection exists or was created
"""
import os
import sys
import logging
from typing import Dict, List, Tuple, Any, Optional, Union
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

try:
    from arango import ArangoClient
    from arango.database import StandardDatabase
    from arango.exceptions import (
        ServerVersionError,
        DatabaseCreateError,
        CollectionCreateError,
        AQLQueryExecuteError,
        ArangoServerError,
        ViewCreateError
    )
    from tenacity import retry, stop_after_attempt, wait_exponential
    
    ARANGO_AVAILABLE = True
    logger.info(" ArangoDB client library is available")
except ImportError as e:
    ARANGO_AVAILABLE = False
    logger.error(f" ArangoDB client library is not available: {e}")
    logger.error("Please install with: pip install python-arango tenacity")

# Load environment variables from .env if present
from dotenv import load_dotenv
load_dotenv()

# Default configuration
DEFAULT_CONFIG = {
    "arango": {
        "host": os.environ.get("ARANGO_HOST", "localhost"),
        "port": int(os.environ.get("ARANGO_PORT", 8529)),
        "user": os.environ.get("ARANGO_USERNAME", "root"),
        "password": os.environ.get("ARANGO_PASSWORD", "openSesame"),
        "db_name": os.environ.get("ARANGO_DB", "marker")
    },
    "embedding": {
        "field": "combined_embedding",
        "dimensions": int(os.environ.get("EMBEDDING_DIMENSION", 1024)),  # Get from env or use 1024 as default
        "model": os.environ.get("EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5")  # Get from env or use BGE as default
    },
    "vector_search": {
        "collection_name": "documents",
        "view_name": "vector_search_view",
        "vector_index_nlists": 4  # Lower for small test collections
    }
}

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10)
)
def execute_aql_with_retry(
    db: StandardDatabase, 
    query: str, 
    bind_vars: Optional[Dict[str, Any]] = None
) -> Any:
    """
    Execute AQL query with retry logic for transient errors.
    
    Args:
        db: ArangoDB database
        query: AQL query string
        bind_vars: Query bind variables
        
    Returns:
        Query cursor
        
    Raises:
        Exception: Re-raises the last exception after retries are exhausted
    """
    try:
        return db.aql.execute(query, bind_vars=bind_vars)
    except (AQLQueryExecuteError, ArangoServerError) as e:
        # Log the error before retry
        logger.warning(f"ArangoDB query failed, retrying: {str(e)}")
        # Re-raise to let @retry handle it
        raise

def connect_arango(
    host: Optional[str] = None,
    port: Optional[int] = None,
    username: Optional[str] = None,
    password: Optional[str] = None
) -> Optional[ArangoClient]:
    """
    Connect to ArangoDB server.
    
    Args:
        host: ArangoDB host (default from env or DEFAULT_CONFIG)
        port: ArangoDB port (default from env or DEFAULT_CONFIG)
        username: ArangoDB username (default from env or DEFAULT_CONFIG)
        password: ArangoDB password (default from env or DEFAULT_CONFIG)
        
    Returns:
        ArangoClient instance if connection is successful, None otherwise
    """
    if not ARANGO_AVAILABLE:
        logger.error("ArangoDB client library not available")
        return None
    
    # Use provided values or defaults
    host = host or DEFAULT_CONFIG["arango"]["host"]
    port = port or DEFAULT_CONFIG["arango"]["port"]
    username = username or DEFAULT_CONFIG["arango"]["user"]
    password = password or DEFAULT_CONFIG["arango"]["password"]
    
    try:
        # Create an ArangoDB client with host and port
        client = ArangoClient(
            hosts=f"http://{host}:{port}"
        )
        
        # Connect to the _system database to verify connection
        sys_db = client.db(
            '_system',
            username=username,
            password=password
        )
        
        # Test connection by retrieving server version
        version = sys_db.version()
        logger.info(f" Connected to ArangoDB version: {version}")
        return client
        
    except ServerVersionError as e:
        logger.error(f" Failed to get server version: {e}")
        return None
    except Exception as e:
        logger.error(f" Failed to connect to ArangoDB: {e}")
        return None

def ensure_database(
    client: ArangoClient,
    db_name: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None
) -> Optional[StandardDatabase]:
    """
    Create a database if it doesn't exist and return the database instance.'
    
    Args:
        client: ArangoDB client instance
        db_name: Database name (default from env or DEFAULT_CONFIG)
        username: ArangoDB username (default from env or DEFAULT_CONFIG)
        password: ArangoDB password (default from env or DEFAULT_CONFIG)
        
    Returns:
        Database instance if creation was successful, None otherwise
    """
    if not ARANGO_AVAILABLE:
        logger.error("ArangoDB client library not available")
        return None
        
    # Use provided values or defaults
    db_name = db_name or DEFAULT_CONFIG["arango"]["db_name"]
    username = username or DEFAULT_CONFIG["arango"]["user"]
    password = password or DEFAULT_CONFIG["arango"]["password"]
    
    try:
        # Connect to _system database to check/create databases
        sys_db = client.db(
            '_system', 
            username=username,
            password=password
        )
        
        # Check if database already exists
        if sys_db.has_database(db_name):
            logger.info(f" Database '{db_name}' already exists")
        else:
            # Create the database
            sys_db.create_database(
                name=db_name,
                users=[{
                    'username': username,
                    'password': password,
                    'active': True
                }]
            )
            logger.info(f" Created database '{db_name}'")
        
        # Return the database instance
        return client.db(
            db_name,
            username=username,
            password=password
        )
        
    except DatabaseCreateError as e:
        logger.error(f" Failed to create database: {e}")
        return None
    except Exception as e:
        logger.error(f" Error working with database: {e}")
        return None

def ensure_collection(
    db: StandardDatabase,
    collection_name: str = "documents"
) -> bool:
    """
    Create collection if it doesn't exist.'
    
    Args:
        db: ArangoDB database instance
        collection_name: Name of the collection
        
    Returns:
        True if collection was created or already exists, False otherwise
    """
    if not ARANGO_AVAILABLE:
        logger.error("ArangoDB client library not available")
        return False
        
    try:
        # Check if collection exists
        if db.has_collection(collection_name):
            logger.info(f" Collection '{collection_name}' already exists")
            return True
        
        # Create collection
        db.create_collection(collection_name)
        logger.info(f" Created collection '{collection_name}'")
        return True
        
    except CollectionCreateError as e:
        logger.error(f" Failed to create collection: {e}")
        return False
    except Exception as e:
        logger.error(f" Error creating collection: {e}")
        return False

def check_vector_index_exists(
    db: StandardDatabase,
    collection_name: str,
    field_name: str
) -> bool:
    """
    Check if a vector index exists on the specified field in the collection.
    
    Args:
        db: ArangoDB database instance
        collection_name: Name of the collection
        field_name: Name of the field to check
        
    Returns:
        True if vector index exists, False otherwise
    """
    if not ARANGO_AVAILABLE:
        logger.error("ArangoDB client library not available")
        return False
        
    try:
        # Get the collection
        collection = db.collection(collection_name)
        
        # Check if vector index exists on the field
        existing_indexes = list(collection.indexes())
        
        for idx in existing_indexes:
            if idx.get("type") == "vector" and field_name in idx.get("fields", []):
                logger.info(f" Vector index exists on field '{field_name}'")
                return True
                
        logger.info(f" No vector index found on field '{field_name}'")
        return False
        
    except Exception as e:
        logger.error(f" Error checking vector index: {e}")
        return False

def ensure_vector_index(
    db: StandardDatabase,
    collection_name: str,
    field_name: str = "combined_embedding",
    dimensions: int = 384,
    nlists: int = 4
) -> bool:
    """
    Create a vector index on the specified field in the collection.
    
    Args:
        db: ArangoDB database instance
        collection_name: Name of the collection
        field_name: Name of the field to index
        dimensions: Dimensionality of the embedding vectors
        nlists: Number of lists for the HNSW algorithm (should be <= document count)
        
    Returns:
        True if index was created successfully, False otherwise
    """
    if not ARANGO_AVAILABLE:
        logger.error("ArangoDB client library not available")
        return False
        
    try:
        # First, verify if the index already exists
        if check_vector_index_exists(db, collection_name, field_name):
            logger.info(f"Vector index for {field_name} already exists")
            return True
            
        # Get the collection
        collection = db.collection(collection_name)
        
        # Count documents with embeddings to ensure we have enough for indexing
        try:
            count_query = f"""
            RETURN LENGTH(
                FOR doc IN {collection_name}
                FILTER HAS(doc, "{field_name}") AND IS_LIST(doc.{field_name})
                RETURN 1
            )
            """
            cursor = db.aql.execute(count_query)
            count_result = list(cursor)[0]
            
            if count_result < nlists:
                logger.warning(f"Not enough documents with embeddings to create vector index. Found {count_result}, need at least {nlists}.")
                logger.warning("Vector index creation may fail. Consider adding more documents or reducing nLists value.")
                
            logger.info(f"Found {count_result} documents with embeddings")
        except Exception as e:
            logger.warning(f"Could not verify embedding count: {e}")
            
        # Create vector index configuration
        index_config = {
            "type": "vector",
            "fields": [field_name],
            "params": {
                "metric": "cosine",  # Use cosine similarity for embeddings
                "dimension": dimensions,
                "nLists": nlists
            },
            "name": f"vector_idx_{field_name}"
        }
        
        # Create the index
        logger.info(f"Creating vector index on field '{field_name}' with dimension {dimensions} and nLists {nlists}")
        collection.add_index(index_config)
        logger.info(f" Vector index created successfully")
        return True
        
    except Exception as e:
        logger.error(f" Error creating vector index: {e}")
        return False

def ensure_arangosearch_view(
    db: StandardDatabase,
    view_name: str = "vector_search_view",
    collection_name: str = "documents",
    embedding_field: str = "combined_embedding"
) -> bool:
    """
    Create or update an ArangoSearch view for vector search.
    
    Args:
        db: ArangoDB database instance
        view_name: Name of the view to create or update
        collection_name: Name of the collection to include in the view
        embedding_field: Name of the field containing vector embeddings
        
    Returns:
        True if view was created or updated successfully, False otherwise
    """
    if not ARANGO_AVAILABLE:
        logger.error("ArangoDB client library not available")
        return False
        
    try:
        # Define fields to include in the view
        text_analyzer = "text_en"
        
        # Create text analyzer if it doesn't exist
        analyzers = [a["name"] for a in db.analyzers()]
        if text_analyzer not in analyzers:
            logger.info(f"Creating analyzer '{text_analyzer}'")
            db.create_analyzer(
                name=text_analyzer,
                analyzer_type="text",
                properties={"locale": "en", "stemming": True, "case": "lower"}
            )
        
        # Define field configurations for the view
        field_configs = {
            # Text fields with text analyzer
            "text": {"analyzers": [text_analyzer]},
            "title": {"analyzers": [text_analyzer]},
            "content": {"analyzers": [text_analyzer]},
            "question": {"analyzers": [text_analyzer]},
            "category": {"analyzers": [text_analyzer]},
            
            # Embedding field for vector search
            embedding_field: {}  # No analyzer for vector field
        }
        
        # Define links to collections
        links = {
            collection_name: {
                "fields": field_configs,
                "includeAllFields": True  # Include all fields in the index
            }
        }
        
        # Define view properties
        view_props = {"links": links}
        
        # Check if view exists
        view_exists = False
        existing_views = [v["name"] for v in db.views()]
        if view_name in existing_views:
            view_exists = True
            current_view = db.view(view_name)
            current_links = current_view.get("links", {})
            
            if current_links != links:
                logger.info(f"Recreating view '{view_name}' due to mismatched links")
                db.delete_view(view_name)
                db.create_view(name=view_name, view_type="arangosearch", properties=view_props)
            else:
                logger.info(f"View '{view_name}' is up-to-date")
        else:
            logger.info(f"Creating view '{view_name}'")
            db.create_view(name=view_name, view_type="arangosearch", properties=view_props)
            
        logger.info(f" ArangoSearch view '{view_name}' ready")
        return True
        
    except ViewCreateError as e:
        logger.error(f" Failed to create view: {e}")
        return False
    except Exception as e:
        logger.error(f" Error creating view: {e}")
        return False

def validate_embedding_dimensions(
    db: StandardDatabase,
    collection_name: str,
    embedding_field: str,
    expected_dimension: int
) -> Tuple[bool, Optional[str]]:
    """
    Validate that embedding dimensions in the documents match the expected dimension.
    
    Args:
        db: ArangoDB database instance
        collection_name: Name of the collection
        embedding_field: Name of the field containing embeddings
        expected_dimension: Expected dimensionality of the embeddings
        
    Returns:
        Tuple of (success, error_message)
    """
    try:
        # Query to check embedding dimensions
        aql = f"""
        FOR doc IN {collection_name}
            FILTER doc.{embedding_field} != null
            LIMIT 10
            RETURN {{
                _key: doc._key,
                embedding_type: TYPENAME(doc.{embedding_field}),
                embedding_length: LENGTH(doc.{embedding_field})
            }}
        """
        
        cursor = db.aql.execute(aql)
        sample_docs = list(cursor)
        
        if not sample_docs:
            return False, "No documents with embeddings found"
        
        # Validate types and dimensions
        dimension_errors = []
        type_errors = []
        
        for doc in sample_docs:
            # Check type is array/list
            if doc["embedding_type"] != "array":
                type_errors.append(doc["_key"])
                
            # Check dimension matches expected
            if doc["embedding_length"] != expected_dimension:
                dimension_errors.append((doc["_key"], doc["embedding_length"]))
        
        if type_errors:
            error_keys = ", ".join(type_errors[:3])
            return False, f"Found {len(type_errors)} documents with non-array embeddings (e.g., {error_keys})"
        
        if dimension_errors:
            error_examples = ", ".join([f"{k}:{d}" for k, d in dimension_errors[:3]])
            return False, f"Found {len(dimension_errors)} documents with wrong embedding dimensions (expected {expected_dimension}): {error_examples}"
        
        return True, None
        
    except Exception as e:
        return False, f"Error validating embeddings: {str(e)}"

def setup_arango_for_vector_search(
    host: Optional[str] = None,
    port: Optional[int] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    db_name: Optional[str] = None,
    collection_name: Optional[str] = None,
    embedding_field: Optional[str] = None,
    embedding_dimensions: Optional[int] = None,
    vector_index_nlists: Optional[int] = None
) -> bool:
    """
    Set up ArangoDB for vector search in one function call.
    
    This is a convenience function that calls the other functions in sequence
    to set up all components needed for vector search.
    
    Args:
        host: ArangoDB host
        port: ArangoDB port
        username: ArangoDB username
        password: ArangoDB password
        db_name: Database name
        collection_name: Collection name
        embedding_field: Field containing vector embeddings
        embedding_dimensions: Dimensionality of embeddings
        vector_index_nlists: Number of lists for vector index
        
    Returns:
        True if setup was successful, False otherwise
    """
    # Use defaults if not provided
    host = host or DEFAULT_CONFIG["arango"]["host"]
    port = port or DEFAULT_CONFIG["arango"]["port"]
    username = username or DEFAULT_CONFIG["arango"]["user"]
    password = password or DEFAULT_CONFIG["arango"]["password"]
    db_name = db_name or DEFAULT_CONFIG["arango"]["db_name"]
    collection_name = collection_name or DEFAULT_CONFIG["vector_search"]["collection_name"]
    embedding_field = embedding_field or DEFAULT_CONFIG["embedding"]["field"]
    embedding_dimensions = embedding_dimensions or DEFAULT_CONFIG["embedding"]["dimensions"]
    vector_index_nlists = vector_index_nlists or DEFAULT_CONFIG["vector_search"]["vector_index_nlists"]
    
    logger.info("Setting up ArangoDB for vector search...")
    
    # Track setup steps
    steps_completed = []
    
    # Connect to ArangoDB
    client = connect_arango(host, port, username, password)
    if not client:
        logger.error(" Failed to connect to ArangoDB")
        return False
    steps_completed.append("connect_arango")
    
    # Ensure database exists
    db = ensure_database(client, db_name, username, password)
    if not db:
        logger.error(" Failed to ensure database exists")
        return False
    steps_completed.append("ensure_database")
    
    # Ensure collection exists
    if not ensure_collection(db, collection_name):
        logger.error(" Failed to ensure collection exists")
        return False
    steps_completed.append("ensure_collection")
    
    # Ensure ArangoSearch view exists
    view_name = DEFAULT_CONFIG["vector_search"]["view_name"]
    if not ensure_arangosearch_view(db, view_name, collection_name, embedding_field):
        logger.error(" Failed to ensure ArangoSearch view exists")
        return False
    steps_completed.append("ensure_arangosearch_view")
    
    # Check if vector index exists (but don't fail if it doesn't - may need documents first)
    vector_index_exists = check_vector_index_exists(db, collection_name, embedding_field)
    if not vector_index_exists:
        logger.info("Vector index does not exist yet - it will be created after documents are added")
    
    logger.info(f" ArangoDB setup completed successfully. Steps completed: {', '.join(steps_completed)}")
    return True

def main():
    """
    Main function to set up ArangoDB when script is run directly.
    
    This function follows the validation approach from the reference script,
    tracking and reporting on each step of the setup process.
    """
    # Track validation
    validation_passed = True
    validation_failures = {}
    
    try:
        logger.info("Starting ArangoDB setup and validation...")
        
        # Connect to ArangoDB
        logger.info("Connecting to ArangoDB...")
        client = connect_arango()
        if not client:
            validation_passed = False
            validation_failures["connect_arango"] = "Failed to connect to ArangoDB"
            logger.error("Failed to connect to ArangoDB.")
            return 1
        
        # Ensure database exists
        logger.info("Ensuring database exists...")
        db = ensure_database(client)
        if not db:
            validation_passed = False
            validation_failures["ensure_database"] = "Failed to ensure database exists"
            logger.error("Failed to ensure database exists.")
            return 1
        
        # Ensure collection exists
        collection_name = DEFAULT_CONFIG["vector_search"]["collection_name"]
        logger.info(f"Ensuring collection '{collection_name}' exists...")
        if not ensure_collection(db, collection_name):
            validation_passed = False
            validation_failures["ensure_collection"] = f"Failed to ensure collection '{collection_name}' exists"
            logger.error(f"Failed to ensure collection '{collection_name}' exists.")
            return 1
        
        # Ensure ArangoSearch view exists
        view_name = DEFAULT_CONFIG["vector_search"]["view_name"]
        logger.info(f"Ensuring ArangoSearch view '{view_name}' exists...")
        if not ensure_arangosearch_view(db, view_name, collection_name, DEFAULT_CONFIG["embedding"]["field"]):
            validation_passed = False
            validation_failures["ensure_arangosearch_view"] = f"Failed to ensure ArangoSearch view '{view_name}' exists"
            logger.error(f"Failed to ensure ArangoSearch view '{view_name}' exists.")
            return 1
        
        # Check document count to determine if we can create a vector index
        collection = db.collection(collection_name)
        doc_count = collection.count()
        if doc_count < DEFAULT_CONFIG["vector_search"]["vector_index_nlists"]:
            logger.warning(f"Collection has only {doc_count} documents. Need at least {DEFAULT_CONFIG['vector_search']['vector_index_nlists']} for vector index.")
            logger.warning("Vector index will be created after sufficient documents are inserted.")
        else:
            # Try to create vector index if enough documents exist
            embedding_field = DEFAULT_CONFIG["embedding"]["field"]
            logger.info(f"Ensuring vector index for '{embedding_field}' exists...")
            if not ensure_vector_index(
                db, 
                collection_name, 
                embedding_field,
                DEFAULT_CONFIG["embedding"]["dimensions"],
                DEFAULT_CONFIG["vector_search"]["vector_index_nlists"]
            ):
                validation_passed = False
                validation_failures["ensure_vector_index"] = f"Failed to ensure vector index for '{embedding_field}' exists"
                logger.error(f"Failed to ensure vector index for '{embedding_field}' exists.")
                return 1
        
        # Final results
        if validation_passed:
            logger.info(" VALIDATION PASSED - ArangoDB setup completed successfully.")
            return 0
        else:
            logger.error(" VALIDATION FAILED - Issues detected during ArangoDB setup:")
            for key, value in validation_failures.items():
                logger.error(f"  - {key}: {value}")
            return 1
            
    except Exception as e:
        logger.exception(f"ArangoDB setup failed with error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())