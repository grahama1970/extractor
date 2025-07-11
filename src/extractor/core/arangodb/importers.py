"""
ArangoDB importers for Marker document data.
Module: importers.py
Description: Functions for importers operations

This module provides functions to import Marker document data into ArangoDB,
including document nodes, block nodes, and relationship edges.

Example:
    ```python
    from extractor.core.arangodb.importers import document_to_arangodb
    
    # Load marker output
    with open('document.json', 'r') as f:
        marker_output = json.load(f)
    
    # Import to ArangoDB
    doc_key, stats = document_to_arangodb(
        marker_output, 
        db_host='localhost', 
        db_name='documents',
        username='root',
        password='password'
    )
    ```

Documentation:
    - ArangoDB Python Driver: https://github.com/ArangoDB-Community/python-arango
    - ArangoDB Graph Features: https://www.arangodb.com/docs/stable/graphs.html
    - Marker Document Structure: https://github.com/VikParuchuri/marker
"""

import json
import os
import time
import uuid
from typing import Dict, List, Any, Optional, Tuple, Union

from loguru import logger
from arango import ArangoClient

from extractor.core.utils.relationship_extractor import extract_relationships_from_marker, create_id_hash


# Constants for collection names
DOCUMENT_COLLECTION = "documents"
BLOCK_COLLECTION = "blocks"
PAGE_COLLECTION = "pages"
SECTION_COLLECTION = "sections"
CONTENT_COLLECTION = "content_blocks"
RELATIONSHIP_COLLECTION = "relationships"
GRAPH_NAME = "document_graph"


def create_arangodb_client(
    host: str = "localhost",
    port: int = 8529,
    username: str = "root",
    password: str = "",
    protocol: str = "http"
) -> ArangoClient:
    """
    Create an ArangoDB client.
    
    Args:
        host: ArangoDB host
        port: ArangoDB port
        username: ArangoDB username
        password: ArangoDB password
        protocol: Protocol (http or https)
        
    Returns:
        ArangoClient instance
    """
    return ArangoClient(
        hosts=f"{protocol}://{host}:{port}",
        username=username,
        password=password
    )


def ensure_collections(
    db,
    collections: List[str] = None,
    edge_collections: List[str] = None
) -> None:
    """
    Ensure that collections exist in the database.
    
    Args:
        db: ArangoDB database instance
        collections: List of document collection names
        edge_collections: List of edge collection names
    """
    if collections is None:
        collections = [
            DOCUMENT_COLLECTION,
            BLOCK_COLLECTION,
            PAGE_COLLECTION,
            SECTION_COLLECTION,
            CONTENT_COLLECTION
        ]
        
    if edge_collections is None:
        edge_collections = [RELATIONSHIP_COLLECTION]
    
    # Create document collections if they don't exist
    for collection_name in collections:
        if not db.has_collection(collection_name):
            db.create_collection(collection_name)
            logger.info(f"Created collection: {collection_name}")
    
    # Create edge collections if they don't exist
    for edge_name in edge_collections:
        if not db.has_collection(edge_name):
            db.create_collection(edge_name, edge=True)
            logger.info(f"Created edge collection: {edge_name}")


def ensure_graph(db) -> None:
    """
    Ensure that the document graph exists.
    
    Args:
        db: ArangoDB database instance
    """
    if not db.has_graph(GRAPH_NAME):
        # Define edge definitions
        edge_definitions = [
            {
                "edge_collection": RELATIONSHIP_COLLECTION,
                "from_vertex_collections": [
                    DOCUMENT_COLLECTION, 
                    PAGE_COLLECTION, 
                    SECTION_COLLECTION,
                    CONTENT_COLLECTION
                ],
                "to_vertex_collections": [
                    DOCUMENT_COLLECTION, 
                    PAGE_COLLECTION, 
                    SECTION_COLLECTION,
                    CONTENT_COLLECTION
                ]
            }
        ]
        
        # Create graph
        db.create_graph(GRAPH_NAME, edge_definitions)
        logger.info(f"Created graph: {GRAPH_NAME}")


def prepare_document_node(marker_output: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepare document node for ArangoDB.
    
    Args:
        marker_output: Marker output in ArangoDB-compatible JSON format
        
    Returns:
        Document node data
    """
    document = marker_output.get("document", {})
    metadata = marker_output.get("metadata", {})
    validation = marker_output.get("validation", {})
    raw_corpus = marker_output.get("raw_corpus", {})
    
    # Extract document ID or generate a new one
    doc_id = document.get("id", None)
    if not doc_id:
        doc_id = f"doc_{uuid.uuid4().hex[:12]}"
    
    # Create document node
    doc_node = {
        "_key": doc_id,
        "doc_id": doc_id,
        "title": metadata.get("title", "Untitled Document"),
        "filepath": metadata.get("filepath", ""),
        "processing_time": metadata.get("processing_time", 0),
        "page_count": len(document.get("pages", [])),
        "validation": validation,
        "created_at": time.time()
    }
    
    # Add document summary if available
    if "document_summary" in metadata:
        doc_node["summary"] = metadata["document_summary"]
    elif "summary" in metadata:
        doc_node["summary"] = metadata["summary"]
    
    # Add raw corpus full text for search capabilities
    if raw_corpus and "full_text" in raw_corpus:
        doc_node["full_text"] = raw_corpus["full_text"]
    
    # Add any additional metadata
    for key, value in metadata.items():
        if key not in doc_node and key != "validation" and key not in ["summaries", "section_summaries", "document_summary", "summary"]:
            doc_node[key] = value
    
    return doc_node


def prepare_page_nodes(marker_output: Dict[str, Any], doc_id: str) -> List[Dict[str, Any]]:
    """
    Prepare page nodes for ArangoDB.
    
    Args:
        marker_output: Marker output in ArangoDB-compatible JSON format
        doc_id: Document ID
        
    Returns:
        List of page node data
    """
    document = marker_output.get("document", {})
    raw_corpus = marker_output.get("raw_corpus", {})
    
    page_nodes = []
    
    # Get raw corpus pages
    raw_pages = raw_corpus.get("pages", [])
    
    # Process each page
    for page_idx, page in enumerate(document.get("pages", [])):
        # Get raw page text if available
        page_text = ""
        page_num = page_idx
        
        if page_idx < len(raw_pages):
            raw_page = raw_pages[page_idx]
            page_text = raw_page.get("text", "")
            page_num = raw_page.get("page_num", page_idx)
        
        # Create page ID
        page_id = f"page_{doc_id}_{page_idx}"
        
        # Create page node
        page_node = {
            "_key": page_id,
            "page_id": page_id,
            "doc_id": doc_id,
            "page_num": page_num,
            "text": page_text,
            "block_count": len(page.get("blocks", [])),
            "created_at": time.time()
        }
        
        page_nodes.append(page_node)
    
    return page_nodes


def prepare_block_nodes(marker_output: Dict[str, Any], doc_id: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Prepare block nodes for ArangoDB.
    
    Args:
        marker_output: Marker output in ArangoDB-compatible JSON format
        doc_id: Document ID
        
    Returns:
        Tuple of (section nodes, content nodes)
    """
    document = marker_output.get("document", {})
    metadata = marker_output.get("metadata", {})
    
    # Check if document has summaries
    summaries = {}
    if "summaries" in metadata:
        summaries = metadata["summaries"]
    elif "section_summaries" in metadata:
        summaries = metadata["section_summaries"]
    
    section_nodes = []
    content_nodes = []
    
    # Process each page
    for page_idx, page in enumerate(document.get("pages", [])):
        page_id = f"page_{doc_id}_{page_idx}"
        
        # Process blocks on this page
        for block_idx, block in enumerate(page.get("blocks", [])):
            block_type = block.get("type", "")
            block_text = block.get("text", "")
            
            # Create block ID based on content hash for stability
            content_hash = create_id_hash(block_text)
            block_id = f"{block_type}_{content_hash}"
            
            # Common block properties
            block_props = {
                "_key": block_id,
                "block_id": block_id,
                "doc_id": doc_id,
                "page_id": page_id,
                "page_num": page_idx,
                "block_idx": block_idx,
                "type": block_type,
                "text": block_text,
                "created_at": time.time()
            }
            
            # Handle different block types
            if block_type == "section_header":
                # Add section properties
                block_props["level"] = block.get("level", 1)
                
                # Add section summary if available
                section_summary = ""
                
                # Check for summary in different formats
                if block_id in summaries:
                    section_summary = summaries[block_id]
                elif content_hash in summaries:
                    section_summary = summaries[content_hash]
                elif block_text in summaries:
                    section_summary = summaries[block_text]
                
                # Add summary to section properties if found
                if section_summary:
                    block_props["summary"] = section_summary
                
                section_nodes.append(block_props)
            else:
                # Add content-specific properties
                if block_type == "code":
                    block_props["language"] = block.get("language", "")
                elif block_type == "table":
                    block_props["csv"] = block.get("csv", "")
                    block_props["json"] = block.get("json", {})
                elif block_type == "summarized":
                    # Handle summarized blocks specially
                    block_props["summary"] = block.get("summary", "")
                    block_props["source_text"] = block.get("source_text", "")
                
                content_nodes.append(block_props)
    
    return section_nodes, content_nodes


def prepare_relationships(relationships: List[Dict[str, Any]], collection_prefix: str = "") -> List[Dict[str, Any]]:
    """
    Prepare relationship edges for ArangoDB.
    
    Args:
        relationships: List of relationships from extract_relationships_from_marker
        collection_prefix: Prefix to add to collection names in _from and _to
        
    Returns:
        List of edge documents
    """
    edges = []
    
    for idx, rel in enumerate(relationships):
        from_id = rel["from"]
        to_id = rel["to"]
        rel_type = rel["type"]
        
        # Determine collections based on ID prefixes
        from_collection = determine_collection(from_id)
        to_collection = determine_collection(to_id)
        
        # Add collection prefix if provided
        if collection_prefix:
            from_collection = f"{collection_prefix}{from_collection}"
            to_collection = f"{collection_prefix}{to_collection}"
        
        # Create edge
        edge = {
            "_key": f"rel_{idx}_{create_id_hash(f'{from_id}_{to_id}_{rel_type}')}",
            "_from": f"{from_collection}/{from_id}",
            "_to": f"{to_collection}/{to_id}",
            "type": rel_type,
            "created_at": time.time()
        }
        
        edges.append(edge)
    
    return edges


def determine_collection(node_id: str) -> str:
    """
    Determine the collection for a node based on its ID prefix.
    
    Args:
        node_id: Node ID
        
    Returns:
        Collection name
    """
    if node_id.startswith("doc_") or node_id.startswith("document_"):
        return DOCUMENT_COLLECTION
    elif node_id.startswith("page_"):
        return PAGE_COLLECTION
    elif node_id.startswith("section_header_"):
        return SECTION_COLLECTION
    elif any(node_id.startswith(prefix) for prefix in ["text_", "code_", "table_", "equation_", "image_"]):
        return CONTENT_COLLECTION
    else:
        # Default to block collection for unknown types
        return BLOCK_COLLECTION


def document_to_arangodb(
    marker_output: Dict[str, Any],
    db_host: str = "localhost",
    db_port: int = 8529,
    db_name: str = "documents",
    username: str = "root",
    password: str = "",
    protocol: str = "http",
    batch_size: int = 100,
    create_collections: bool = True,
    create_graph: bool = True,
    extract_relationships: bool = True
) -> Tuple[str, Dict[str, Any]]:
    """
    Import Marker document data to ArangoDB.
    
    Args:
        marker_output: Marker output in ArangoDB-compatible JSON format
        db_host: ArangoDB host
        db_port: ArangoDB port
        db_name: ArangoDB database name
        username: ArangoDB username
        password: ArangoDB password
        protocol: Protocol (http or https)
        batch_size: Batch size for imports
        create_collections: Whether to create collections if they don't exist'
        create_graph: Whether to create graph if it doesn't exist'
        extract_relationships: Whether to extract relationships
        
    Returns:
        Tuple of (document key, import statistics)
    """
    start_time = time.time()
    stats = {
        "document_count": 0,
        "page_count": 0,
        "section_count": 0,
        "content_count": 0,
        "relationship_count": 0,
        "import_time": 0
    }
    
    try:
        # Create ArangoDB client
        client = create_arangodb_client(
            host=db_host,
            port=db_port,
            username=username,
            password=password,
            protocol=protocol
        )
        
        # Get database (create if doesn't exist)
        system_db = client.db("_system", username=username, password=password)
        if not system_db.has_database(db_name):
            system_db.create_database(db_name)
            logger.info(f"Created database: {db_name}")
        
        # Connect to database
        db = client.db(db_name, username=username, password=password)
        
        # Ensure collections exist
        if create_collections:
            ensure_collections(db)
        
        # Ensure graph exists
        if create_graph:
            ensure_graph(db)
        
        # Prepare document node
        doc_node = prepare_document_node(marker_output)
        doc_id = doc_node["_key"]
        
        # Insert document node
        db.collection(DOCUMENT_COLLECTION).insert(doc_node, overwrite=True)
        stats["document_count"] += 1
        
        # Prepare and insert page nodes
        page_nodes = prepare_page_nodes(marker_output, doc_id)
        if page_nodes:
            # Insert in batches
            for i in range(0, len(page_nodes), batch_size):
                batch = page_nodes[i:i+batch_size]
                db.collection(PAGE_COLLECTION).insert_many(batch, overwrite=True)
            stats["page_count"] += len(page_nodes)
        
        # Prepare and insert block nodes
        section_nodes, content_nodes = prepare_block_nodes(marker_output, doc_id)
        
        # Insert section nodes
        if section_nodes:
            for i in range(0, len(section_nodes), batch_size):
                batch = section_nodes[i:i+batch_size]
                db.collection(SECTION_COLLECTION).insert_many(batch, overwrite=True)
            stats["section_count"] += len(section_nodes)
        
        # Insert content nodes
        if content_nodes:
            for i in range(0, len(content_nodes), batch_size):
                batch = content_nodes[i:i+batch_size]
                db.collection(CONTENT_COLLECTION).insert_many(batch, overwrite=True)
            stats["content_count"] += len(content_nodes)
        
        # Extract and insert relationships
        if extract_relationships:
            relationships = extract_relationships_from_marker(marker_output)
            relationship_edges = prepare_relationships(relationships)
            
            # Insert relationship edges
            if relationship_edges:
                for i in range(0, len(relationship_edges), batch_size):
                    batch = relationship_edges[i:i+batch_size]
                    db.collection(RELATIONSHIP_COLLECTION).insert_many(batch, overwrite=True)
                stats["relationship_count"] += len(relationship_edges)
        
        # Update stats
        stats["import_time"] = time.time() - start_time
        
        return doc_id, stats
    
    except Exception as e:
        logger.error(f"Error importing document to ArangoDB: {str(e)}")
        raise


if __name__ == "__main__":
    import sys
    import os
    from pathlib import Path
    import argparse
    from dotenv import load_dotenv
    
    # Configure logger
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    logger.add("arangodb_import_validation.log", rotation="10 MB")
    
    # Load environment variables
    load_dotenv()
    
    # Default ArangoDB settings
    DEFAULT_HOST = os.getenv("ARANGO_HOST", "localhost")
    DEFAULT_PORT = int(os.getenv("ARANGO_PORT", "8529"))
    DEFAULT_DB = os.getenv("ARANGO_DB", "documents")
    DEFAULT_USER = os.getenv("ARANGO_USERNAME", "root")
    DEFAULT_PASS = os.getenv("ARANGO_PASSWORD", "")
    
    # Parse arguments
    parser = argparse.ArgumentParser(description="Validate ArangoDB import")
    parser.add_argument("--input", "-i", type=str, help="Path to Marker JSON output file")
    parser.add_argument("--host", type=str, default=DEFAULT_HOST, help="ArangoDB host")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="ArangoDB port")
    parser.add_argument("--db", type=str, default=DEFAULT_DB, help="ArangoDB database name")
    parser.add_argument("--user", type=str, default=DEFAULT_USER, help="ArangoDB username")
    parser.add_argument("--password", type=str, default=DEFAULT_PASS, help="ArangoDB password")
    parser.add_argument("--batch-size", type=int, default=100, help="Batch size for imports")
    parser.add_argument("--skip-graph", action="store_true", help="Skip graph creation")
    args = parser.parse_args()
    
    # List to track all validation failures
    all_validation_failures = []
    total_tests = 0
    
    # Test 1: Testing with a sample document
    total_tests += 1
    logger.info("Test 1: Testing with a sample document")
    
    # Create a sample document
    sample_doc = {
        "document": {
            "id": f"test_doc_{uuid.uuid4().hex[:8]}",
            "pages": [
                {
                    "blocks": [
                        {
                            "type": "section_header",
                            "text": "Introduction",
                            "level": 1
                        },
                        {
                            "type": "text",
                            "text": "This is introduction text."
                        },
                        {
                            "type": "code",
                            "text": "def hello():\n    print('Hello world')",
                            "language": "python"
                        }
                    ]
                },
                {
                    "blocks": [
                        {
                            "type": "section_header",
                            "text": "Methods",
                            "level": 1
                        },
                        {
                            "type": "text",
                            "text": "Methods description."
                        }
                    ]
                }
            ]
        },
        "metadata": {
            "title": "Test Document",
            "processing_time": 0.5
        },
        "validation": {
            "corpus_validation": {
                "performed": True,
                "threshold": 97,
                "raw_corpus_length": 200
            }
        },
        "raw_corpus": {
            "full_text": "Introduction\n\nThis is introduction text.\n\ndef hello():\n    print('Hello world')\n\nMethods\n\nMethods description.",
            "pages": [
                {
                    "page_num": 0,
                    "text": "Introduction\n\nThis is introduction text.\n\ndef hello():\n    print('Hello world')",
                    "tables": []
                },
                {
                    "page_num": 1,
                    "text": "Methods\n\nMethods description.",
                    "tables": []
                }
            ],
            "total_pages": 2
        }
    }
    
    try:
        # Test import with sample document
        doc_id, stats = document_to_arangodb(
            sample_doc,
            db_host=args.host,
            db_port=args.port,
            db_name=args.db,
            username=args.user,
            password=args.password,
            batch_size=args.batch_size,
            create_graph=not args.skip_graph
        )
        
        # Verify import results
        if not doc_id:
            failure_msg = "No document ID returned from import"
            all_validation_failures.append(failure_msg)
            logger.error(failure_msg)
        elif stats["document_count"] != 1:
            failure_msg = f"Expected 1 document, got {stats['document_count']}"
            all_validation_failures.append(failure_msg)
            logger.error(failure_msg)
        elif stats["page_count"] != 2:
            failure_msg = f"Expected 2 pages, got {stats['page_count']}"
            all_validation_failures.append(failure_msg)
            logger.error(failure_msg)
        elif stats["section_count"] != 2:
            failure_msg = f"Expected 2 sections, got {stats['section_count']}"
            all_validation_failures.append(failure_msg)
            logger.error(failure_msg)
        elif stats["content_count"] != 3:
            failure_msg = f"Expected 3 content blocks, got {stats['content_count']}"
            all_validation_failures.append(failure_msg)
            logger.error(failure_msg)
        else:
            logger.success(f"Sample document import successful: {doc_id}")
            logger.info(f"Import stats: {json.dumps(stats, indent=2)}")
        
        # Query document to verify data
        client = create_arangodb_client(
            host=args.host,
            port=args.port,
            username=args.user,
            password=args.password
        )
        db = client.db(args.db, username=args.user, password=args.password)
        
        imported_doc = db.collection(DOCUMENT_COLLECTION).get(doc_id)
        if not imported_doc:
            failure_msg = f"Document {doc_id} not found in database"
            all_validation_failures.append(failure_msg)
            logger.error(failure_msg)
        else:
            logger.success(f"Document {doc_id} found in database")
    except Exception as e:
        failure_msg = f"Sample document import failed: {str(e)}"
        all_validation_failures.append(failure_msg)
        logger.error(failure_msg)
    
    # Test 2: Import from file if specified
    if args.input:
        total_tests += 1
        input_path = Path(args.input)
        logger.info(f"Test 2: Importing from file: {input_path}")
        
        try:
            # Load Marker output
            with open(input_path, "r") as f:
                marker_output = json.load(f)
            
            # Import to ArangoDB
            doc_id, stats = document_to_arangodb(
                marker_output,
                db_host=args.host,
                db_port=args.port,
                db_name=args.db,
                username=args.user,
                password=args.password,
                batch_size=args.batch_size,
                create_graph=not args.skip_graph
            )
            
            # Verify import results
            if not doc_id:
                failure_msg = "No document ID returned from file import"
                all_validation_failures.append(failure_msg)
                logger.error(failure_msg)
            else:
                logger.success(f"File import successful: {doc_id}")
                logger.info(f"Import stats: {json.dumps(stats, indent=2)}")
                
                # Execute a test query to verify relationships
                # For sections with their content
                query = """
                FOR section IN sections
                    FILTER section.doc_id == @doc_id
                    LET content = (
                        FOR content, edge IN OUTBOUND section relationships
                            RETURN {
                                id: content._key,
                                type: content.type,
                                text: SUBSTRING(content.text, 0, 50) + '...'
                            }
                    )
                    RETURN {
                        section: section.text,
                        level: section.level,
                        content_count: LENGTH(content),
                        content: content
                    }
                """
                cursor = db.aql.execute(query, bind_vars={"doc_id": doc_id})
                results = [doc for doc in cursor]
                
                if not results:
                    failure_msg = "No section relationships found in query results"
                    all_validation_failures.append(failure_msg)
                    logger.error(failure_msg)
                else:
                    logger.success(f"Found {len(results)} sections with relationships")
                    for i, section in enumerate(results[:3]):  # Show first 3 for brevity
                        logger.info(f"Section {i+1}: {section['section']} (Level {section['level']})")
                        logger.info(f"Content count: {section['content_count']}")
        except Exception as e:
            failure_msg = f"File import failed: {str(e)}"
            all_validation_failures.append(failure_msg)
            logger.error(failure_msg)
    
    # Final validation result
    if all_validation_failures:
        logger.error(f" VALIDATION FAILED - {len(all_validation_failures)} of {total_tests} tests failed:")
        for failure in all_validation_failures:
            logger.error(f"  - {failure}")
        sys.exit(1)  # Exit with error code
    else:
        logger.success(f" VALIDATION PASSED - All {total_tests} tests produced expected results")
        logger.info("ArangoDB import module is validated and ready for use")
        sys.exit(0)  # Exit with success code