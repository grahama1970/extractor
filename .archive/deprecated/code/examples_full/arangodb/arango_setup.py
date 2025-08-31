"""
Module: arango_setup.py
Description: ArangoDB graph database interactions

External Dependencies:
- requests: https://docs.python-requests.org/
- torch: https://pytorch.org/docs/
- loguru: https://loguru.readthedocs.io/
- arango: https://docs.python-arango.com/

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

import sys
import os
import requests
import torch
from typing import Dict, List, Tuple, Any, Optional
from loguru import logger
from datasets import load_dataset, Dataset
from tqdm.auto import tqdm
from arango.client import ArangoClient
from arango.database import StandardDatabase
from arango.exceptions import (
    DatabaseCreateError,
    CollectionCreateError,
    ViewCreateError,
    ViewDeleteError,
    IndexCreateError,
    DocumentInsertError,
)
from dotenv import load_dotenv
from tqdm.contrib.logging import logging_redirect_tqdm

# Import EmbedderModel and CONFIG from the appropriate modules
try:
    from complexity.beta.rag.rag_classifier import EmbedderModel, DOC_PREFIX
    from complexity.beta.utils.config import CONFIG  # Import CONFIG from config.py
except ImportError:
    logger.error("Could not import required modules. Ensure PYTHONPATH includes 'src'.")
    sys.exit(1)

# Load environment variables
load_dotenv()

# Validate environment - allow empty password
required_keys = ["host", "user", "db_name"]
missing = [k for k in required_keys if not CONFIG["arango"].get(k)]
if missing:
    logger.error(f"Missing environment variables: {', '.join(missing)}")
    sys.exit(1)

# Set up loguru file sink
os.makedirs("logs", exist_ok=True)
logger.add("logs/arango_setup.log", level="DEBUG", rotation="10 MB")

# Cached EmbedderModel
_EmbedderModel_instance = None

def get_EmbedderModel(force_new: bool = False) -> EmbedderModel:
    """Return singleton EmbedderModel or create a new one if requested."""
    global _EmbedderModel_instance
    if _EmbedderModel_instance is None or force_new:
        logger.info(f"Initializing EmbedderModel: {CONFIG['embedding']['model_name']}")
        _EmbedderModel_instance = EmbedderModel(CONFIG["embedding"]["model_name"])
    return _EmbedderModel_instance

def connect_arango() -> ArangoClient:
    """Connect to ArangoDB."""
    logger.info(f"Connecting to ArangoDB at {CONFIG['arango']['host']}")
    try:
        client = ArangoClient(hosts=CONFIG["arango"]["host"])
        sys_db = client.db("_system", username=CONFIG["arango"]["user"], password=CONFIG["arango"]["password"])
        logger.info(f"Connected to ArangoDB version {sys_db.version()}")
        return client
    except Exception as e:
        logger.exception(f"Connection failed: {e}")
        sys.exit(1)

def ensure_database(client: ArangoClient) -> StandardDatabase:
    """Ensure database exists."""
    try:
        sys_db = client.db("_system", username=CONFIG["arango"]["user"], password=CONFIG["arango"]["password"])
        db_name = CONFIG["arango"]["db_name"]
        if db_name not in sys_db.databases():
            logger.info(f"Creating database '{db_name}'")
            sys_db.create_database(db_name)
        return client.db(db_name, username=CONFIG["arango"]["user"], password=CONFIG["arango"]["password"])
    except DatabaseCreateError as e:
        logger.exception(f"Database setup failed: {e}")
        sys.exit(1)

def ensure_collection(db: StandardDatabase) -> None:
    """Ensure collection exists."""
    try:
        name = CONFIG["search"]["collection_name"]
        existing_collections = [c['name'] for c in db.collections()]
        if name not in existing_collections:
            logger.info(f"Creating collection '{name}'")
            db.create_collection(name)
        logger.info(f"Collection '{name}' ready")
    except CollectionCreateError as e:
        logger.exception(f"Collection creation failed: {e}")
        sys.exit(1)

def ensure_arangosearch_view(db: StandardDatabase) -> None:
    """Ensure ArangoSearch view."""
    try:
        view_name = CONFIG["search"]["view_name"]
        analyzer = CONFIG["search"]["text_analyzer"]
        
        # Enhanced view configuration with more search fields
        # Use all fields from SEARCH_FIELDS in config
        field_configs = {}
        for field in CONFIG.get("search", {}).get("search_fields", 
                              ["question", "answer", "tags", "title", "context", "content"]):
            field_configs[field] = {"analyzers": [analyzer]}
        
        # Add embedding field for vector search
        field_configs[CONFIG["embedding"]["field"]] = {}
        
        # Define links with expanded field list for better search coverage
        links = {
            CONFIG["search"]["collection_name"]: {
                "fields": field_configs,
                "includeAllFields": True,  # Changed to True to include all possible fields in the index
            }
        }
        
        # For test collections, ensure the view can find them too
        test_collection = "test_docs"  # From test_fixtures.py
        if db.has_collection(test_collection):
            logger.info(f"Including test collection '{test_collection}' in view")
            links[test_collection] = {
                "fields": {
                    "title": {"analyzers": [analyzer]},
                    "content": {"analyzers": [analyzer]},
                    "tags": {"analyzers": [analyzer]},
                    "question": {"analyzers": [analyzer]},
                    "category": {"analyzers": [analyzer]},
                    "embedding": {}
                },
                "includeAllFields": True,
            }
        
        props = {"links": links}
        
        # Check if analyzer exists by iterating through the list provided by the db object
        analyzer_exists = False
        for a in db.analyzers():
            if a["name"] == analyzer:
                analyzer_exists = True
                break
        if not analyzer_exists:
            logger.info(f"Creating analyzer '{analyzer}'")
            db.create_analyzer(
                name=analyzer,
                analyzer_type="text",
                properties={"locale": "en", "stemming": True, "case": "lower"},
            )

        # Check if view exists by iterating
        view_exists = False
        for v in db.views():
            if v["name"] == view_name:
                view_exists = True
                break

        if view_exists:
            current_view = db.view(view_name)
            logger.debug(f"Current view data: {current_view}")
            current_links = current_view.get("links", {})
            if current_links != links:
                logger.info(f"Recreating view '{view_name}' due to mismatched links")
                db.delete_view(view_name)
                db.create_view(name=view_name, view_type="arangosearch", properties=props)
            else:
                logger.info(f"Search view '{view_name}' up-to-date")
        else:
            logger.info(f"Creating view '{view_name}'")
            db.create_view(name=view_name, view_type="arangosearch", properties=props)
        logger.info(f"Search view '{view_name}' ready")
    except (ViewCreateError, ViewDeleteError) as e:
        logger.exception(f"View setup failed: {e}")
        sys.exit(1)

def ensure_edge_collections(db: StandardDatabase) -> None:
    """Ensure edge collections for relationships exist."""
    try:
        existing_collections = [c['name'] for c in db.collections()]
        edge_collections = ["prerequisites", "related_topics"]
        for collection_name in edge_collections:
            if collection_name not in existing_collections:
                logger.info(f"Creating edge collection '{collection_name}'")
                db.create_collection(collection_name, edge=True)
            logger.info(f"Edge collection '{collection_name}' ready")
    except Exception as e:
        logger.exception(f"Edge collection setup failed: {e}")
        sys.exit(1)
        
def ensure_memory_agent_collections(db: StandardDatabase) -> None:
    """Ensures that all collections required by the Memory Agent exist."""
    try:
        # Define the required collections for Memory Agent
        message_collection = "agent_messages"
        memory_collection = "agent_memories"
        edge_collection = "agent_relationships"
        
        # Create document collections
        for collection_name in [message_collection, memory_collection]:
            if not db.has_collection(collection_name):
                logger.info(f"Creating Memory Agent collection '{collection_name}'")
                db.create_collection(collection_name)
                logger.info(f"Memory Agent collection '{collection_name}' created successfully.")
            else:
                logger.info(f"Memory Agent collection '{collection_name}' already exists.")
        
        # Create edge collection
        if not db.has_collection(edge_collection):
            logger.info(f"Creating Memory Agent edge collection '{edge_collection}'")
            db.create_collection(edge_collection, edge=True)
            logger.info(f"Memory Agent edge collection '{edge_collection}' created successfully.")
        else:
            # Verify it's an edge collection
            props = db.collection(edge_collection).properties()
            if props.get("type") != 3:  # 3 = edge
                logger.info(f"Collection '{edge_collection}' is not edge; recreating...")
                db.delete_collection(edge_collection)
                db.create_collection(edge_collection, edge=True)
                logger.info(f"Memory Agent edge collection '{edge_collection}' recreated.")
            else:
                logger.info(f"Memory Agent edge collection '{edge_collection}' already exists.")
        
        # Create ArangoSearch view for Memory Agent collections
        view_name = "agent_memory_view"
        
        # Ensure analyzers exist
        text_analyzer = "text_en"
        analyzers = {a["name"] for a in db.analyzers()}
        if text_analyzer not in analyzers:
            logger.info(f"Creating analyzer '{text_analyzer}' for Memory Agent")
            db.create_analyzer(
                text_analyzer,
                {"type": "text", "properties": {"locale": "en", "stemming": True, "case": "lower"}}
            )
            logger.info(f"Analyzer '{text_analyzer}' created.")
        
        # Define view properties
        view_props = {
            "links": {
                message_collection: {
                    "fields": {
                        "content": {"analyzers": [text_analyzer]},
                        "embedding": {}
                    },
                    "includeAllFields": False
                },
                memory_collection: {
                    "fields": {
                        "content": {"analyzers": [text_analyzer]},
                        "summary": {"analyzers": [text_analyzer]},
                        "embedding": {}
                    },
                    "includeAllFields": False
                }
            }
        }
        
        # Create or update view
        existing_views = {v["name"] for v in db.views()}
        if view_name in existing_views:
            curr_links = db.view(view_name).get("links", {})
            if curr_links != view_props["links"]:
                logger.info(f"Memory Agent view '{view_name}' links mismatch; recreating...")
                db.delete_view(view_name)
                db.create_view(
                    name=view_name,
                    view_type="arangosearch",
                    properties=view_props
                )
                logger.info(f"Memory Agent view '{view_name}' recreated.")
            else:
                logger.info(f"Memory Agent view '{view_name}' already up-to-date.")
        else:
            logger.info(f"Creating Memory Agent view '{view_name}'...")
            db.create_view(
                name=view_name,
                view_type="arangosearch",
                properties=view_props
            )
            logger.info(f"Memory Agent view '{view_name}' created.")
        
        logger.info("Memory Agent collections and view setup completed successfully.")
    except Exception as e:
        logger.exception(f"Failed to ensure Memory Agent collections: {e}")
        sys.exit(1)

def ensure_graph(db: StandardDatabase) -> None:
    """Ensure named graph exists for traversals."""
    try:
        graph_name = "complexity_graph"
        existing_graphs = [g['name'] for g in db.graphs()]
        edge_collections = ["prerequisites", "related_topics"]
        collection_name = CONFIG["search"]["collection_name"]
        if graph_name not in existing_graphs:
            logger.info(f"Creating graph '{graph_name}'")
            edge_definitions = []
            for edge_collection in edge_collections:
                edge_definitions.append({
                    "edge_collection": edge_collection,
                    "from_vertex_collections": [collection_name],
                    "to_vertex_collections": [collection_name]
                })
            db.create_graph(graph_name, edge_definitions)
        logger.info(f"Graph '{graph_name}' ready")
    except Exception as e:
        logger.exception(f"Graph setup failed: {e}")
        sys.exit(1)

def load_and_index_dataset(db: StandardDatabase, embedder_instance: Optional[EmbedderModel] = None) -> None:
    """Load dataset, embed texts with progress bars, and insert into collection."""
    logger.info("Loading dataset...")
    try:
        ds = load_dataset(
            CONFIG['dataset']['name'], split=CONFIG['dataset']['split'], trust_remote_code=True
        )
        if not isinstance(ds, Dataset):
            logger.error(f"Unexpected dataset type: {type(ds)}")
            sys.exit(1)
        
        emb = embedder_instance if embedder_instance else get_EmbedderModel()
        embedding_model_name = getattr(emb, 'model_name', CONFIG['embedding']['model_name'])
        logger.info(f"Generating embeddings using {embedding_model_name}")
        
        texts: List[str] = []
        docs: List[Dict[str, Any]] = []
        with logging_redirect_tqdm():
            for item in tqdm(ds, desc="Preparing docs"):
                q = item.get('question')
                r = item.get('rating')
                if not q or r is None:
                    continue
                try:
                    label = 1 if float(r) >= 0.5 else 0
                except (ValueError, TypeError):
                    continue
                texts.append(q)
                docs.append({'question': q, 'label': label, 'validated': True})

        batch_size = CONFIG["embedding"]["batch_size"]
        embeddings: List[List[float]] = []
        with logging_redirect_tqdm():
            emb_pbar = tqdm(total=len(texts), desc="Embedding docs")
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                batch_embs = emb.embed_batch(batch, prefix=DOC_PREFIX)
                embeddings.extend(batch_embs)
                emb_pbar.update(len(batch_embs))
            emb_pbar.close()

        if len(embeddings) != len(docs):
            logger.error(f"Embedding mismatch: {len(embeddings)} vs {len(docs)}")
            sys.exit(1)

        for doc, emb in zip(docs, embeddings):
            doc[CONFIG['embedding']['field']] = emb

        logger.info(f"Truncating collection {CONFIG['search']['collection_name']} to replace existing embeddings with new embeddings")
        
        col = db.collection(CONFIG['search']['collection_name'])
        col.truncate()
        with logging_redirect_tqdm():
            ins_pbar = tqdm(total=len(docs), desc="Inserting docs")
            for i in range(0, len(docs), 1000):
                batch = docs[i:i + 1000]
                col.insert_many(batch, overwrite=True)
                ins_pbar.update(len(batch))
            ins_pbar.close()
        logger.info(f"Inserted {len(docs)} docs in batches of 1000")

    except Exception as err:
        logger.exception(f"Loading/indexing failed: {err}")
        sys.exit(1)

def ensure_vector_index(db: StandardDatabase):
    """Ensure vector index after data insertion and verify embedding dimensions."""
    try:
        col = db.collection(CONFIG["search"]["collection_name"])
        doc_count = col.count()
        assert isinstance(doc_count, int), f"Expected int for doc_count, got {type(doc_count)}"
        if doc_count < 3:
            logger.error(f"Collection has {doc_count} documents; need at least 3 to create vector index")
            sys.exit(1)

        # First validate index exists
        current_indexes = list(col.indexes())
        logger.info(f"Current indexes: {len(current_indexes)}")
        vector_index = None
        for idx in current_indexes:
            if idx.get("type") == "vector" and CONFIG["embedding"]["field"] in idx.get("fields", []):
                vector_index = idx
                logger.info(f"Found existing vector index: {idx.get('name')} (id={idx.get('id')})")
                break
        
        if not vector_index:
            # Create vector index if it doesn't exist
            cfg = {
                "type": "vector",
                "fields": [CONFIG["embedding"]["field"]],
                "params": {
                    "metric": "cosine",
                    "dimension": CONFIG["embedding"]["dimensions"],
                    "nLists": CONFIG["search"]["vector_index_nlists"]
                },
                "name": "vector_index"
            }
            logger.info(f"Creating vector index with dimension {CONFIG['embedding']['dimensions']}")
            try:
                col.add_index(cfg)
                logger.info(f"Vector index created successfully")
            except Exception as e:
                logger.exception(f"Exception creating vector index: {e}")
                raise

            # Verify index exists after creation
            updated_indexes = list(col.indexes())
            vector_index_found = False
            for idx in updated_indexes:
                if idx.get("type") == "vector" and CONFIG["embedding"]["field"] in idx.get("fields", []): 
                    vector_index_found = True
                    break
            
            if not vector_index_found:
                logger.error("Vector index not found after creation attempt")
                sys.exit(1)
        
        # Now verify embedding dimensions in actual documents
        logger.info("Verifying embedding dimensions in documents...")
        
        # Create AQL query to sample documents and check embedding dimensions
        embedding_field = CONFIG["embedding"]["field"]
        expected_dimension = CONFIG["embedding"]["dimensions"]
        
        aql = f"""
        FOR doc IN {CONFIG["search"]["collection_name"]}
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
            logger.error("No documents with embeddings found")
            sys.exit(1)
            
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
            logger.error(f"Found {len(type_errors)} documents with non-array embeddings (e.g., {error_keys})")
            sys.exit(1)
            
        if dimension_errors:
            error_examples = ", ".join([f"{k}:{d}" for k, d in dimension_errors[:3]])
            logger.error(f"Found {len(dimension_errors)} documents with wrong embedding dimensions (expected {expected_dimension}): {error_examples}")
            sys.exit(1)
            
        logger.info(f"Verified {len(sample_docs)} documents with correct embedding dimensions ({expected_dimension})")
        
    except Exception as e:
        logger.exception(f"Vector index creation or validation failed: {e}")
        sys.exit(1)

def classify_complexity(db: StandardDatabase, question: str, k: Optional[int] = None, return_neighbors: bool = False) -> Tuple[int, float, bool, Optional[List[Dict[str, Any]]]]:
    """Classify question complexity using semantic search."""
    k = k or CONFIG["classification"]["default_k"]
    try:
        emb = get_EmbedderModel().embed_batch([question])[0]
        collection_name = CONFIG["search"]["collection_name"]
        embedding_field = CONFIG["embedding"]["field"]
        if return_neighbors:
            aql = f"""
            FOR doc IN {collection_name}
                LET score = COSINE_SIMILARITY(doc.{embedding_field}, @emb)
                SORT score DESC
                LIMIT @k
                RETURN {{ 
                    label: doc.label, 
                    score: score, 
                    question: doc.question,
                    id: doc._id,
                    embedding: doc.{embedding_field}
                }}
            """
        else:
            aql = f"""
            FOR doc IN {collection_name}
                LET score = COSINE_SIMILARITY(doc.{embedding_field}, @emb)
                SORT score DESC
                LIMIT @k
                RETURN {{ label: doc.label, score: score }}
            """
        cursor = db.aql.execute(aql, bind_vars={"emb": emb, "k": k})
        results = list(cursor)
        if not results:
            logger.warning("No neighbors found")
            return (0, 0.0, False, []) if return_neighbors else (0, 0.0, False, None)
        votes = {0: 0.0, 1: 0.0}
        total = 0.0
        exponent = 2.0
        for r in results:
            if r["score"] > 0:
                weight = r["score"] ** exponent
                votes[r["label"]] += weight
                total += weight
        if total <= 0:
            return (0, 0.0, False, []) if return_neighbors else (0, 0.0, False, None)
        majority = max(votes, key=votes.get)
        confidence = votes[majority] / total
        auto_accept = confidence >= CONFIG["classification"]["confidence_threshold"] and len(results) >= k
        logger.info(f"Classification: label={majority}, confidence={confidence:.2f}, auto_accept={auto_accept}")
        if return_neighbors:
            return majority, confidence, auto_accept, results
        return majority, confidence, auto_accept, None
    except Exception as e:
        logger.exception(f"Classification failed: {e}")
        return (0, 0.0, False, []) if return_neighbors else (0, 0.0, False, None)

def validate_embedding_dimensions(db: StandardDatabase) -> Tuple[bool, Optional[str]]:
    """
    Validate embedding dimensions in the database.
    
    Args:
        db: ArangoDB database connection
        
    Returns:
        Tuple of (success, error_message)
    """
    try:
        embedding_field = CONFIG["embedding"]["field"]
        expected_dimension = CONFIG["embedding"]["dimensions"]
        collection_name = CONFIG["search"]["collection_name"]
        
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

if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stderr, level="DEBUG")
    validation_passed = True
    validation_failures = {}
    
    # Configuration for which components to run
    # Set these flags to False to skip specific steps during debugging
    RUN_DATABASE_SETUP = True
    RUN_COLLECTION_SETUP = True
    RUN_VIEW_SETUP = True
    RUN_EDGE_COLLECTIONS_SETUP = True
    RUN_GRAPH_SETUP = True
    RUN_DATASET_LOADING = False  # Set to False to skip time-consuming embedding generation
    RUN_INDEX_SETUP = True
    RUN_CLASSIFICATION_TEST = True

    # Expected values from configuration
    EXPECTED_DB_NAME = CONFIG["arango"]["db_name"]
    EXPECTED_COLLECTION_NAME = CONFIG["search"]["collection_name"]
    EXPECTED_VIEW_NAME = CONFIG["search"]["view_name"]
    EXPECTED_GRAPH_NAME = "complexity_graph"
    EXPECTED_EDGE_COLLECTIONS = ["prerequisites", "related_topics"]
    EXPECTED_VECTOR_INDEX_FIELD = CONFIG["embedding"]["field"]
    EXPECTED_VECTOR_INDEX_DIM = CONFIG["embedding"]["dimensions"]
    TEST_QUESTION = "What is the capital of France?"
    EXPECTED_TEST_LABEL = 0
    
    try:
        logger.info("Starting ArangoDB setup and validation...")
        os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
        
        # ===================== DATABASE CONNECTION =====================
        if RUN_DATABASE_SETUP:
            logger.info("Connecting to ArangoDB...")
            client = connect_arango()
            logger.info("Ensuring database exists...")
            db = ensure_database(client)
            
            if db.name != EXPECTED_DB_NAME:
                validation_passed = False
                validation_failures["database_name"] = {"expected": EXPECTED_DB_NAME, "actual": db.name}
                logger.error(f"Database name mismatch: Expected {EXPECTED_DB_NAME}, Got {db.name}")
        else:
            logger.info("SKIPPING DATABASE SETUP - using existing connection")
            client = connect_arango()
            db = client.db(EXPECTED_DB_NAME, username=CONFIG["arango"]["user"], password=CONFIG["arango"]["password"])
        
        # ===================== COLLECTION SETUP =====================
        if RUN_COLLECTION_SETUP:
            logger.info(f"Ensuring collection '{EXPECTED_COLLECTION_NAME}' exists...")
            ensure_collection(db)
            
            existing_collections = [c['name'] for c in db.collections()]
            if EXPECTED_COLLECTION_NAME not in existing_collections:
                validation_passed = False
                validation_failures["collection_missing"] = {"expected": EXPECTED_COLLECTION_NAME, "actual": "Not Found"}
                logger.error(f"Collection '{EXPECTED_COLLECTION_NAME}' not found after ensure_collection.")
            else:
                logger.info(f"Collection '{EXPECTED_COLLECTION_NAME}' verified.")
        else:
            logger.info("SKIPPING COLLECTION SETUP - using existing collection")
        
        # ===================== VIEW SETUP =====================
        if RUN_VIEW_SETUP:
            logger.info(f"Ensuring ArangoSearch view '{EXPECTED_VIEW_NAME}' exists...")
            ensure_arangosearch_view(db)
            
            view_exists = any(v['name'] == EXPECTED_VIEW_NAME for v in db.views())
            if not view_exists:
                validation_passed = False
                validation_failures["view_missing"] = {"expected": EXPECTED_VIEW_NAME, "actual": "Not Found"}
                logger.error(f"View '{EXPECTED_VIEW_NAME}' not found after ensure_arangosearch_view.")
            else:
                logger.info(f"View '{EXPECTED_VIEW_NAME}' verified.")
        else:
            logger.info("SKIPPING VIEW SETUP - using existing view")
        
        # ===================== EDGE COLLECTIONS SETUP =====================
        if RUN_EDGE_COLLECTIONS_SETUP:
            logger.info("Ensuring edge collections exist...")
            ensure_edge_collections(db)
            
            db_collections = [c['name'] for c in db.collections()]
            edge_collections_valid = True
            for edge_coll in EXPECTED_EDGE_COLLECTIONS:
                if edge_coll not in db_collections:
                    validation_passed = False
                    validation_failures[f"edge_collection_{edge_coll}_missing"] = {"expected": edge_coll, "actual": "Not Found"}
                    logger.error(f"Edge collection '{edge_coll}' not found after ensure_edge_collections.")
                    edge_collections_valid = False
            
            if edge_collections_valid:
                logger.info(f"All edge collections verified.")
        else:
            logger.info("SKIPPING EDGE COLLECTIONS SETUP - using existing collections")
            
        # ===================== MEMORY AGENT COLLECTIONS SETUP =====================
        if RUN_EDGE_COLLECTIONS_SETUP:  # Use the same flag for Memory Agent setup
            logger.info("Ensuring Memory Agent collections and views exist...")
            ensure_memory_agent_collections(db)
            
            # Verify Memory Agent collections
            db_collections = [c['name'] for c in db.collections()]
            memory_collections = ["agent_messages", "agent_memories", "agent_relationships"]
            memory_collections_valid = True
            
            for name in memory_collections:
                if name not in db_collections:
                    validation_passed = False
                    validation_failures[f"missing_memory_agent_collection_{name}"] = {"expected": f"{name} exists", "actual": f"{name} not found"}
                    logger.error(f"Memory Agent collection '{name}' not found after ensure_memory_agent_collections.")
                    memory_collections_valid = False
            
            # Verify Memory Agent view
            memory_agent_view_name = "agent_memory_view"
            view_exists = any(v['name'] == memory_agent_view_name for v in db.views())
            if not view_exists:
                validation_passed = False
                validation_failures[f"missing_view_{memory_agent_view_name}"] = {"expected": f"{memory_agent_view_name} exists", "actual": "View not found"}
                logger.error(f"Memory Agent view '{memory_agent_view_name}' not found after ensure_memory_agent_collections.")
            
            if memory_collections_valid and view_exists:
                logger.info("All Memory Agent collections and view verified.")
        else:
            logger.info("SKIPPING MEMORY AGENT SETUP - using existing collections")
        
        # ===================== GRAPH SETUP =====================
        if RUN_GRAPH_SETUP:
            logger.info(f"Ensuring graph '{EXPECTED_GRAPH_NAME}' exists...")
            ensure_graph(db)
            
            if EXPECTED_GRAPH_NAME not in [g['name'] for g in db.graphs()]:
                validation_passed = False
                validation_failures["graph_missing"] = {"expected": EXPECTED_GRAPH_NAME, "actual": "Not Found"}
                logger.error(f"Graph '{EXPECTED_GRAPH_NAME}' not found after ensure_graph.")
            else:
                logger.info(f"Graph '{EXPECTED_GRAPH_NAME}' verified.")
        else:
            logger.info("SKIPPING GRAPH SETUP - using existing graph")
        
        # ===================== DATASET LOADING & EMBEDDING =====================
        if RUN_DATASET_LOADING:
            logger.info("Loading and indexing dataset...")
            embedder_model_instance = get_EmbedderModel()
            load_and_index_dataset(db, embedder_instance=embedder_model_instance)
        else:
            logger.info("SKIPPING DATASET LOADING - using existing data")
        
        # ===================== DOCUMENT COUNT VALIDATION =====================
        logger.info("Validating document count...")
        col = db.collection(EXPECTED_COLLECTION_NAME)
        doc_count = col.count()
        
        assert isinstance(doc_count, int), f"Expected int for doc_count, got {type(doc_count)}"
        if doc_count == 0:
            validation_passed = False
            validation_failures["data_loading"] = {"expected": "> 0 documents", "actual": "0 documents"}
            logger.error("Collection is empty - no documents found.")
        else:
            logger.info(f"Collection has {doc_count} documents.")
        
        # ===================== VECTOR INDEX SETUP =====================
        if RUN_INDEX_SETUP:
            logger.info("Ensuring vector index exists...")
            ensure_vector_index(db)
            
            # Verify vector index exists
            indexes = col.indexes()
            vector_index_found = False
            for idx in indexes:
                if idx.get("type") == "vector" and EXPECTED_VECTOR_INDEX_FIELD in idx.get("fields", []):
                    vector_index_found = True
                    logger.info(f"Vector index '{idx.get('name')}' verified.")
                    break
                    
            if not vector_index_found:
                validation_passed = False
                validation_failures["vector_index_missing"] = {"expected": f"Index on {EXPECTED_VECTOR_INDEX_FIELD}", "actual": "Not Found"}
                logger.error("Vector index not found after ensure_vector_index.")
        else:
            logger.info("SKIPPING INDEX SETUP - using existing index")
        
        # ===================== EMBEDDING DIMENSION VALIDATION =====================
        logger.info("Validating embedding dimensions...")
        dimension_validation_passed, dimension_error = validate_embedding_dimensions(db)
        
        if not dimension_validation_passed:
            validation_passed = False
            validation_failures["embedding_dimensions"] = {"expected": f"Embeddings with dimension {EXPECTED_VECTOR_INDEX_DIM}", "actual": dimension_error}
            logger.error(f"Embedding dimension validation failed: {dimension_error}")
        else:
            logger.info(f"Embedding dimensions validated successfully: {EXPECTED_VECTOR_INDEX_DIM}")
        
        # ===================== CLASSIFICATION TEST =====================
        if RUN_CLASSIFICATION_TEST:
            logger.info(f"Testing classification for: '{TEST_QUESTION}'")
            label, confidence, auto_accept, _ = classify_complexity(db, TEST_QUESTION)
            logger.info(f"Test classification result: label={label}, confidence={confidence:.2f}, auto_accept={auto_accept}")
            
            if label != EXPECTED_TEST_LABEL:
                validation_passed = False
                validation_failures["test_classification_label"] = {"expected": EXPECTED_TEST_LABEL, "actual": label}
                logger.error(f"Test classification label mismatch: Expected {EXPECTED_TEST_LABEL}, Got {label}")
            else:
                logger.info("Test classification label matches expected.")
        else:
            logger.info("SKIPPING CLASSIFICATION TEST")
    
    except Exception as e:
        validation_passed = False
        validation_failures["runtime_error"] = str(e)
        logger.exception(f"Setup or validation failed with runtime error: {e}")
    
    # ===================== FINAL RESULTS =====================
    if validation_passed:
        print(" VALIDATION COMPLETE - All setup and validation steps passed.")
        logger.success("Standalone execution and validation successful.")
        sys.exit(0)
    else:
        print(" VALIDATION FAILED - Issues detected during setup or validation.")
        print("FAILURE DETAILS:")
        for field, details in validation_failures.items():
            if isinstance(details, dict):
                print(f"  - {field}: Expected: {details.get('expected', 'N/A')}, Got: {details.get('actual', 'N/A')}")
            else:
                print(f"  - {field}: {details}")
        logger.error("Standalone execution and validation failed.")
        sys.exit(1)