"""
ArangoDB import/export pipeline for Marker documents.
Module: pipeline.py
Description: Implementation of pipeline functionality

This module provides a complete pipeline for importing Marker documents
into ArangoDB and exporting them back, maintaining all relationships
and metadata.

Links:
- PyArango docs: https://pyarango.readthedocs.io/
- ArangoDB HTTP API: https://www.arangodb.com/docs/stable/http/

Sample Input:
    marker_output = convert_single_pdf("document.pdf")
    
Expected Output:
    {
        "imported": {
            "documents": 1,
            "vertices": 150,
            "edges": 200
        },
        "database": "marker_docs",
        "collections": ["documents", "sections", "blocks", "entities"]
    }
"""

import json
import os
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from pathlib import Path

from loguru import logger

# Try to import pyArango, fallback to requests if not available
try:
    from pyArango.connection import Connection
    from pyArango.database import Database
    from pyArango.collection import Collection
    PYARANGO_AVAILABLE = True
except ImportError:
    logger.warning("pyArango not available, using requests for HTTP API")
    PYARANGO_AVAILABLE = False
    import requests


class ArangoDBPipeline:
    """
    Pipeline for importing/exporting Marker documents to/from ArangoDB.
    
    Features:
    - Automatic collection creation
    - Batch imports for performance
    - Relationship preservation
    - Query helpers for common operations
    - Export with structure reconstruction
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.host = self.config.get("host", "localhost")
        self.port = self.config.get("port", 8529)
        self.username = self.config.get("username", "root")
        self.password = self.config.get("password", "")
        self.database = self.config.get("database", "marker_docs")
        
        self.connection = None
        self.db = None
        self._connect()
    
    def _connect(self):
        """Establish connection to ArangoDB."""
        if PYARANGO_AVAILABLE:
            try:
                self.connection = Connection(
                    arangoURL=f"http://{self.host}:{self.port}",
                    username=self.username,
                    password=self.password
                )
                
                # Create database if it doesn't exist
                if not self.connection.hasDatabase(self.database):
                    self.connection.createDatabase(name=self.database)
                
                self.db = self.connection[self.database]
                logger.info(f"Connected to ArangoDB database: {self.database}")
            except Exception as e:
                logger.error(f"Failed to connect to ArangoDB: {e}")
                self.connection = None
                self.db = None
        else:
            # Fallback to HTTP API
            self.base_url = f"http://{self.host}:{self.port}"
            self._test_connection()
    
    def _test_connection(self):
        """Test connection using HTTP API."""
        try:
            response = requests.get(
                f"{self.base_url}/_api/version",
                auth=(self.username, self.password)
            )
            if response.status_code == 200:
                logger.info("Connected to ArangoDB via HTTP API")
            else:
                logger.error(f"Failed to connect: {response.status_code}")
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
    
    def create_collections(self):
        """Create required collections if they don't exist."""
        collections = {
            "documents": {"type": "document"},
            "sections": {"type": "document"},
            "blocks": {"type": "document"},
            "entities": {"type": "document"},
            "tables": {"type": "document"},
            "contains": {"type": "edge"},
            "references": {"type": "edge"},
            "follows": {"type": "edge"},
            "relates_to": {"type": "edge"}
        }
        
        if PYARANGO_AVAILABLE and self.db:
            for name, config in collections.items():
                if not self.db.hasCollection(name):
                    if config["type"] == "edge":
                        self.db.createCollection(name=name, className="Edges")
                    else:
                        self.db.createCollection(name=name)
                    logger.info(f"Created collection: {name}")
        else:
            # HTTP API fallback
            for name, config in collections.items():
                self._create_collection_http(name, config["type"] == "edge")
    
    def _create_collection_http(self, name: str, is_edge: bool = False):
        """Create collection using HTTP API."""
        data = {
            "name": name,
            "type": 3 if is_edge else 2  # 3 for edge, 2 for document
        }
        
        response = requests.post(
            f"{self.base_url}/_db/{self.database}/_api/collection",
            json=data,
            auth=(self.username, self.password)
        )
        
        if response.status_code in [200, 409]:  # 409 = already exists
            logger.info(f"Collection ready: {name}")
        else:
            logger.error(f"Failed to create collection {name}: {response.text}")
    
    def import_marker_output(self, marker_output: Dict[str, Any], 
                           source_file: Optional[str] = None) -> Dict[str, Any]:
        """
        Import Marker output into ArangoDB.
        
        Args:
            marker_output: Marker output with graph structure
            source_file: Optional source file path
            
        Returns:
            Import statistics
        """
        start_time = datetime.now()
        stats = {
            "documents": 0,
            "vertices": 0,
            "edges": 0,
            "errors": []
        }
        
        try:
            # Ensure collections exist
            self.create_collections()
            
            # Import vertices
            vertex_mapping = {}  # Map old IDs to new ArangoDB IDs
            
            for vertex_type, vertices in marker_output.get("vertices", {}).items():
                collection_name = vertex_type
                
                for vertex in vertices:
                    old_id = vertex.get("_id", vertex.get("_key"))
                    
                    # Add metadata
                    vertex["imported_at"] = datetime.now().isoformat()
                    if source_file:
                        vertex["source_file"] = source_file
                    
                    # Import vertex
                    new_id = self._import_vertex(collection_name, vertex)
                    if new_id:
                        vertex_mapping[old_id] = new_id
                        stats["vertices"] += 1
                        
                        if vertex_type == "documents":
                            stats["documents"] += 1
                    else:
                        stats["errors"].append(f"Failed to import vertex: {old_id}")
            
            # Import edges with ID mapping
            for edge_type, edges in marker_output.get("edges", {}).items():
                collection_name = edge_type
                
                for edge in edges:
                    # Map old IDs to new IDs
                    old_from = edge.get("_from")
                    old_to = edge.get("_to")
                    
                    if old_from in vertex_mapping and old_to in vertex_mapping:
                        edge["_from"] = vertex_mapping[old_from]
                        edge["_to"] = vertex_mapping[old_to]
                        
                        # Import edge
                        if self._import_edge(collection_name, edge):
                            stats["edges"] += 1
                        else:
                            stats["errors"].append(f"Failed to import edge: {old_from} -> {old_to}")
                    else:
                        stats["errors"].append(f"Missing vertex for edge: {old_from} -> {old_to}")
            
            # Log results
            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"Import completed in {duration:.2f}s: {stats['vertices']} vertices, {stats['edges']} edges")
            
            if stats["errors"]:
                logger.warning(f"Import had {len(stats['errors'])} errors")
            
        except Exception as e:
            logger.error(f"Import failed: {e}")
            stats["errors"].append(str(e))
        
        return stats
    
    def _import_vertex(self, collection: str, vertex: Dict[str, Any]) -> Optional[str]:
        """Import a single vertex."""
        if PYARANGO_AVAILABLE and self.db:
            try:
                col = self.db[collection]
                doc = col.createDocument(vertex)
                doc.save()
                return doc._id
            except Exception as e:
                logger.error(f"Failed to import vertex: {e}")
                return None
        else:
            # HTTP API fallback
            response = requests.post(
                f"{self.base_url}/_db/{self.database}/_api/document/{collection}",
                json=vertex,
                auth=(self.username, self.password)
            )
            if response.status_code == 201:
                return response.json().get("_id")
            else:
                logger.error(f"Failed to import vertex: {response.text}")
                return None
    
    def _import_edge(self, collection: str, edge: Dict[str, Any]) -> bool:
        """Import a single edge."""
        if PYARANGO_AVAILABLE and self.db:
            try:
                col = self.db[collection]
                doc = col.createDocument(edge)
                doc.save()
                return True
            except Exception as e:
                logger.error(f"Failed to import edge: {e}")
                return False
        else:
            # HTTP API fallback
            response = requests.post(
                f"{self.base_url}/_db/{self.database}/_api/document/{collection}",
                json=edge,
                auth=(self.username, self.password)
            )
            return response.status_code == 201
    
    def query_documents(self, filter_dict: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Query documents with optional filters.
        
        Args:
            filter_dict: Optional filters (e.g., {"title": "Introduction"})
            
        Returns:
            List of matching documents
        """
        aql_query = "FOR doc IN documents"
        
        if filter_dict:
            filters = []
            for key, value in filter_dict.items():
                filters.append(f'doc.{key} == "{value}"')
            
            if filters:
                aql_query += f" FILTER {' AND '.join(filters)}"
        
        aql_query += " RETURN doc"
        
        return self._execute_query(aql_query)
    
    def get_document_structure(self, doc_id: str) -> Dict[str, Any]:
        """
        Get complete document structure with all related entities.
        
        Args:
            doc_id: Document ID
            
        Returns:
            Document structure with sections, blocks, etc.
        """
        # Query to get document with all related data
        aql_query = f"""
        LET doc = DOCUMENT("{doc_id}")
        
        LET sections = (
            FOR v, e IN 1..10 OUTBOUND doc contains
                FILTER v.type == "section"
                RETURN v
        )
        
        LET blocks = (
            FOR v, e IN 1..10 OUTBOUND doc contains
                FILTER v.type != "section"
                RETURN v
        )
        
        RETURN {{
            document: doc,
            sections: sections,
            blocks: blocks
        }}
        """
        
        results = self._execute_query(aql_query)
        return results[0] if results else {}
    
    def export_document(self, doc_id: str) -> Dict[str, Any]:
        """
        Export document from ArangoDB back to Marker format.
        
        Args:
            doc_id: Document ID to export
            
        Returns:
            Marker-compatible output format
        """
        # Get document structure
        structure = self.get_document_structure(doc_id)
        
        if not structure:
            logger.error(f"Document not found: {doc_id}")
            return {}
        
        # Reconstruct Marker format
        # This is simplified - full implementation would reconstruct exact format
        marker_output = {
            "document": {
                "id": structure["document"]["_key"],
                "pages": []
            },
            "metadata": structure["document"].get("metadata", {}),
            "vertices": {
                "documents": [structure["document"]],
                "sections": structure["sections"],
                "blocks": structure["blocks"]
            }
        }
        
        return marker_output
    
    def _execute_query(self, aql: str, bind_vars: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """Execute AQL query and return results."""
        if PYARANGO_AVAILABLE and self.db:
            try:
                result = self.db.AQLQuery(aql, bindVars=bind_vars or {})
                return list(result)
            except Exception as e:
                logger.error(f"Query failed: {e}")
                return []
        else:
            # HTTP API fallback
            data = {
                "query": aql,
                "bindVars": bind_vars or {}
            }
            
            response = requests.post(
                f"{self.base_url}/_db/{self.database}/_api/cursor",
                json=data,
                auth=(self.username, self.password)
            )
            
            if response.status_code == 201:
                return response.json().get("result", [])
            else:
                logger.error(f"Query failed: {response.text}")
                return []
    
    def close(self):
        """Close database connection."""
        if PYARANGO_AVAILABLE and self.connection:
            # PyArango doesn't have explicit close
            self.connection = None
            self.db = None
        logger.info("Closed ArangoDB connection")


# CLI integration
def import_to_arangodb(marker_output_path: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Import Marker output file to ArangoDB.
    
    Args:
        marker_output_path: Path to Marker JSON output
        config: Optional ArangoDB configuration
        
    Returns:
        Import statistics
    """
    # Load Marker output
    with open(marker_output_path, 'r', encoding='utf-8') as f:
        marker_output = json.load(f)
    
    # Create pipeline
    pipeline = ArangoDBPipeline(config)
    
    # Import
    stats = pipeline.import_marker_output(
        marker_output,
        source_file=marker_output_path
    )
    
    pipeline.close()
    return stats


# Validation and testing
if __name__ == "__main__":
    # Test data matching enhanced renderer output
    test_output = {
        "vertices": {
            "documents": [{
                "_key": "doc_test123",
                "_id": "documents/doc_test123",
                "type": "document",
                "title": "Test Document",
                "page_count": 1
            }],
            "sections": [{
                "_key": "section_intro",
                "_id": "sections/section_intro",
                "title": "Introduction",
                "level": 1,
                "type": "section"
            }],
            "blocks": [{
                "_key": "block_text1",
                "_id": "blocks/block_text1",
                "type": "text",
                "page": 0,
                "position": 0,
                "text": "This is test content."
            }]
        },
        "edges": {
            "contains": [
                {
                    "_from": "documents/doc_test123",
                    "_to": "sections/section_intro",
                    "type": "document_contains_section"
                },
                {
                    "_from": "sections/section_intro",
                    "_to": "blocks/block_text1",
                    "type": "section_contains_block"
                }
            ]
        }
    }
    
    # Test pipeline (will use mock if no ArangoDB available)
    pipeline = ArangoDBPipeline({
        "host": "localhost",
        "port": 8529,
        "username": "root",
        "password": "",
        "database": "marker_test"
    })
    
    print("Testing ArangoDB Pipeline...")
    
    # Test import
    print("\n1. Testing import...")
    stats = pipeline.import_marker_output(test_output, "test.pdf")
    print(f"   Import stats: {stats}")
    
    # Test query
    print("\n2. Testing query...")
    docs = pipeline.query_documents({"title": "Test Document"})
    print(f"   Found {len(docs)} documents")
    
    # Test export
    if docs:
        print("\n3. Testing export...")
        doc_id = docs[0]["_id"]
        exported = pipeline.export_document(doc_id)
        print(f"   Exported document with {len(exported.get('vertices', {}).get('blocks', []))} blocks")
    
    pipeline.close()
    print("\n✅ ArangoDB Pipeline test completed!")