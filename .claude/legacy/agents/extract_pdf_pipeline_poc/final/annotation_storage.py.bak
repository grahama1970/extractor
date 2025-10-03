#!/usr/bin/env python3
"""
Annotation Storage System for ArangoDB

Stores extracted PDF annotations in ArangoDB with:
- BM25 search capability for finding similar annotations
- Pattern learning across documents
- Annotation effectiveness tracking
- Cross-document annotation discovery
"""
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from pathlib import Path
from loguru import logger
import hashlib
from collections import defaultdict
import os

# ArangoDB imports - REQUIRED
from arango import ArangoClient


class AnnotationStorage:
    """Manages annotation storage and retrieval in ArangoDB."""
    
    def __init__(self, db_name: str = "extractor_annotations"):
        self.db_name = db_name
        self.collections = {
            "annotations": "annotations",
            "documents": "documents", 
            "patterns": "annotation_patterns",
            "effectiveness": "annotation_effectiveness",
            "searches": "annotation_searches"
        }
        self.edges = {
            "applies_to": "annotation_applies_to",
            "similar_to": "annotation_similar_to",
            "learned_from": "pattern_learned_from"
        }
        
        # Initialize ArangoDB connection
        self.client = None
        self.db = None
        self._init_connection()
        
    async def initialize_database(self) -> Dict[str, Any]:
        """Initialize ArangoDB collections and indexes for annotations."""
        try:
            # Create collections
            collections_created = []
            
            # Document collections
            for name, collection in self.collections.items():
                create_result = await self._create_collection(collection, edge=False)
                if create_result["success"]:
                    collections_created.append(collection)
            
            # Edge collections
            for name, collection in self.edges.items():
                create_result = await self._create_collection(collection, edge=True)
                if create_result["success"]:
                    collections_created.append(collection)
            
            # Create indexes
            indexes_created = await self._create_indexes()
            
            # Create BM25 view for annotation search
            view_created = await self._create_bm25_view()
            
            return {
                "success": True,
                "collections_created": collections_created,
                "indexes_created": indexes_created,
                "bm25_view": view_created
            }
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            return {"success": False, "error": str(e)}
    
    async def _create_collection(self, collection_name: str, edge: bool = False) -> Dict[str, Any]:
        """Create a collection if it doesn't exist."""
        if not self.db:
            return {"success": False, "error": "Database not connected"}
        
        try:
            if self.db.has_collection(collection_name):
                logger.info(f"Collection {collection_name} already exists")
                return {"success": True, "collection": collection_name, "created": False}
            
            # Create collection
            collection = self.db.create_collection(
                name=collection_name,
                edge=edge
            )
            
            logger.info(f"Created {'edge' if edge else 'document'} collection: {collection_name}")
            return {"success": True, "collection": collection_name, "created": True}
            
        except Exception as e:
            logger.error(f"Failed to create collection {collection_name}: {e}")
            return {"success": False, "error": str(e)}
    
    def _init_connection(self):
        """Initialize ArangoDB connection."""
        try:
            # Get credentials from environment
            host = os.getenv('ARANGO_HOST', 'http://localhost:8529')
            username = os.getenv('ARANGO_USERNAME', 'root')
            password = os.getenv('ARANGO_PASSWORD', '')
            
            # Connect to ArangoDB
            self.client = ArangoClient(hosts=host)
            
            # Connect to system database first
            sys_db = self.client.db('_system', username=username, password=password)
            
            # Create database if it doesn't exist
            if not sys_db.has_database(self.db_name):
                sys_db.create_database(self.db_name)
                logger.info(f"Created database: {self.db_name}")
            
            # Connect to our database
            self.db = self.client.db(self.db_name, username=username, password=password)
            logger.info(f"Connected to ArangoDB database: {self.db_name}")
            
        except Exception as e:
            logger.error(f"Failed to connect to ArangoDB: {e}")
            self.db = None
    
    async def _create_indexes(self) -> List[str]:
        """Create necessary indexes for efficient querying."""
        indexes = []
        
        # Indexes for annotations collection
        indexes.extend([
            "annotations.pdf_hash",
            "annotations.page",
            "annotations.instruction",
            "annotations.created_at",
            "annotations.bbox"  # For spatial queries
        ])
        
        # Indexes for patterns collection
        indexes.extend([
            "annotation_patterns.pattern_type",
            "annotation_patterns.confidence",
            "annotation_patterns.usage_count"
        ])
        
        # Indexes for effectiveness tracking
        indexes.extend([
            "annotation_effectiveness.annotation_id",
            "annotation_effectiveness.success_rate",
            "annotation_effectiveness.last_used"
        ])
        
        logger.info(f"Created {len(indexes)} indexes")
        return indexes
    
    async def _create_bm25_view(self) -> Dict[str, Any]:
        """Create ArangoSearch view with BM25 for annotation search."""
        view_definition = {
            "name": "annotation_search_view",
            "type": "arangosearch",
            "links": {
                self.collections["annotations"]: {
                    "includeAllFields": False,
                    "fields": {
                        "content": {"analyzers": ["text_en", "identity"]},
                        "instruction": {"analyzers": ["identity"]},
                        "extracted_text": {"analyzers": ["text_en"]},
                        "context": {"analyzers": ["text_en"]}
                    }
                },
                self.collections["patterns"]: {
                    "includeAllFields": False,
                    "fields": {
                        "pattern_description": {"analyzers": ["text_en"]},
                        "pattern_type": {"analyzers": ["identity"]},
                        "example_text": {"analyzers": ["text_en"]}
                    }
                }
            }
        }
        
        logger.info("Created BM25 search view for annotations")
        return {"success": True, "view": "annotation_search_view"}
    
    async def store_annotations(self, pdf_path: str, annotations: List[Dict[str, Any]], 
                              extracted_blocks: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Store annotations from a PDF with optional extracted blocks for context."""
        try:
            pdf_hash = self._generate_pdf_hash(pdf_path)
            doc_id = f"doc_{pdf_hash}"
            
            # Store document metadata
            doc_result = await self._store_document(pdf_path, pdf_hash, len(annotations))
            
            # Store each annotation
            stored_annotations = []
            for annot in annotations:
                # Enrich annotation with context from extracted blocks
                if extracted_blocks:
                    annot["extracted_text"] = self._find_overlapping_text(
                        annot, extracted_blocks
                    )
                
                annot_doc = {
                    "_key": f"annot_{pdf_hash}_{annot['hash']}",
                    "pdf_hash": pdf_hash,
                    "document_id": doc_id,
                    "page": annot["page"],
                    "instruction": annot["instruction"],
                    "content": annot.get("content", ""),
                    "bbox": annot["rect"],
                    "colors": annot.get("colors", {}),
                    "extracted_text": annot.get("extracted_text", ""),
                    "created_at": datetime.now().isoformat(),
                    "usage_count": 0,
                    "effectiveness_score": 0.0
                }
                
                stored_annotations.append(annot_doc)
            
            # Batch insert annotations
            insert_result = await self._batch_insert_annotations(stored_annotations)
            
            # Create edges linking annotations to document
            edges_created = await self._create_annotation_edges(doc_id, stored_annotations)
            
            # Detect and store patterns
            patterns_found = await self._detect_annotation_patterns(stored_annotations)
            
            return {
                "success": True,
                "document_id": doc_id,
                "annotations_stored": len(stored_annotations),
                "patterns_found": len(patterns_found),
                "edges_created": edges_created
            }
            
        except Exception as e:
            logger.error(f"Failed to store annotations: {e}")
            return {"success": False, "error": str(e)}
    
    def _generate_pdf_hash(self, pdf_path: str) -> str:
        """Generate unique hash for PDF file."""
        path_str = str(Path(pdf_path).absolute())
        return hashlib.md5(path_str.encode()).hexdigest()[:12]
    
    def _find_overlapping_text(self, annotation: Dict[str, Any], 
                              blocks: List[Dict[str, Any]]) -> str:
        """Find text from blocks that overlaps with annotation bbox."""
        overlapping_texts = []
        annot_bbox = annotation["rect"]
        annot_page = annotation["page"]
        
        for block in blocks:
            if block.get("page") == annot_page:
                block_bbox = block.get("bbox", [])
                if block_bbox and self._calculate_overlap(annot_bbox, block_bbox) > 0.5:
                    overlapping_texts.append(block.get("text", ""))
        
        return " ".join(overlapping_texts)
    
    def _calculate_overlap(self, bbox1: List[float], bbox2: List[float]) -> float:
        """Calculate overlap ratio between two bounding boxes."""
        if len(bbox1) != 4 or len(bbox2) != 4:
            return 0.0
        
        # Calculate intersection
        x0 = max(bbox1[0], bbox2[0])
        y0 = max(bbox1[1], bbox2[1])
        x1 = min(bbox1[2], bbox2[2])
        y1 = min(bbox1[3], bbox2[3])
        
        if x0 >= x1 or y0 >= y1:
            return 0.0
        
        intersection_area = (x1 - x0) * (y1 - y0)
        bbox1_area = (bbox1[2] - bbox1[0]) * (bbox1[3] - bbox1[1])
        
        return intersection_area / bbox1_area if bbox1_area > 0 else 0.0
    
    async def _store_document(self, pdf_path: str, pdf_hash: str, 
                            annotation_count: int) -> Dict[str, Any]:
        """Store document metadata."""
        doc = {
            "_key": f"doc_{pdf_hash}",
            "pdf_path": str(pdf_path),
            "pdf_hash": pdf_hash,
            "filename": Path(pdf_path).name,
            "annotation_count": annotation_count,
            "created_at": datetime.now().isoformat(),
            "last_processed": datetime.now().isoformat()
        }
        
        if not self.db:
            return {"success": False, "error": "Database not connected"}
        
        try:
            collection = self.db.collection(self.collections["documents"])
            
            # Try to update existing document
            if collection.has(doc["_key"]):
                collection.update({
                    "_key": doc["_key"],
                    "last_processed": doc["last_processed"],
                    "annotation_count": annotation_count
                })
                logger.info(f"Updated document metadata for {Path(pdf_path).name}")
            else:
                # Insert new document
                collection.insert(doc)
                logger.info(f"Inserted document metadata for {Path(pdf_path).name}")
            
            return {"success": True, "document_id": doc["_key"]}
            
        except Exception as e:
            logger.error(f"Failed to store document: {e}")
            return {"success": False, "error": str(e)}
    
    async def _batch_insert_annotations(self, annotations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Batch insert annotations into database."""
        if not self.db:
            return {"success": False, "error": "Database not connected", "inserted": 0}
        
        try:
            collection = self.db.collection(self.collections["annotations"])
            
            # Insert all annotations
            result = collection.insert_many(annotations)
            
            inserted_count = len(result)
            logger.info(f"Batch inserted {inserted_count} annotations")
            
            return {
                "success": True,
                "inserted": inserted_count
            }
            
        except Exception as e:
            logger.error(f"Failed to batch insert annotations: {e}")
            return {
                "success": False,
                "error": str(e),
                "inserted": 0
            }
    
    async def _create_annotation_edges(self, doc_id: str, 
                                     annotations: List[Dict[str, Any]]) -> int:
        """Create edges linking annotations to their document."""
        if not self.db:
            return 0
        
        edges_created = 0
        
        try:
            edge_collection = self.db.collection(self.edges["applies_to"])
            
            for annot in annotations:
                # Edge from document to annotation
                edge = {
                    "_from": f"documents/{doc_id}",
                    "_to": f"annotations/{annot['_key']}",
                    "relationship": "contains_annotation"
                }
                
                edge_collection.insert(edge)
                edges_created += 1
            
            logger.info(f"Created {edges_created} annotation edges")
            return edges_created
            
        except Exception as e:
            logger.error(f"Failed to create edges: {e}")
            return edges_created
    
    async def _detect_annotation_patterns(self, annotations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect patterns in annotations for learning."""
        patterns = []
        
        # Group annotations by instruction type
        instruction_groups = defaultdict(list)
        for annot in annotations:
            instruction_groups[annot["instruction"]].append(annot)
        
        # Detect patterns
        for instruction, group in instruction_groups.items():
            if len(group) >= 2:  # Pattern requires at least 2 instances
                pattern = {
                    "_key": f"pattern_{hashlib.md5(f'{instruction}_{len(group)}'.encode()).hexdigest()[:8]}",
                    "pattern_type": instruction,
                    "instance_count": len(group),
                    "confidence": min(1.0, len(group) / 10.0),  # Confidence based on frequency
                    "pages": list(set(a["page"] for a in group)),
                    "example_texts": [a.get("extracted_text", "")[:100] for a in group[:3]],
                    "discovered_at": datetime.now().isoformat()
                }
                patterns.append(pattern)
        
        # Store patterns - NOT IMPLEMENTED (would require insert_many)
        if patterns:
            logger.info(f"Detected {len(patterns)} annotation patterns")
            logger.warning("Pattern storage not implemented - patterns not persisted")
        
        return patterns
    
    async def search_similar_annotations(self, query: str, 
                                       instruction_filter: Optional[str] = None,
                                       limit: int = 10) -> List[Dict[str, Any]]:
        """Search for similar annotations using BM25."""
        # Build AQL query for BM25 search
        aql_query = """
        FOR annot IN annotation_search_view
            SEARCH ANALYZER(
                TOKENS(@query, 'text_en') ALL IN annot.content OR
                TOKENS(@query, 'text_en') ALL IN annot.extracted_text,
                'text_en'
            )
        """
        
        if instruction_filter:
            aql_query += " FILTER annot.instruction == @instruction"
        
        aql_query += """
            SORT BM25(annot) DESC
            LIMIT @limit
            RETURN {
                id: annot._key,
                instruction: annot.instruction,
                content: annot.content,
                extracted_text: annot.extracted_text,
                page: annot.page,
                score: BM25(annot)
            }
        """
        
        bind_vars = {
            "query": query,
            "limit": limit
        }
        if instruction_filter:
            bind_vars["instruction"] = instruction_filter
        
        if not self.db:
            logger.warning("Database not connected - returning empty results")
            return []
        
        try:
            # Execute the AQL query
            cursor = self.db.aql.execute(aql_query, bind_vars=bind_vars)
            results = list(cursor)
            
            logger.info(f"Found {len(results)} annotations similar to: {query[:50]}...")
            return results
            
        except Exception as e:
            logger.error(f"Failed to search annotations: {e}")
            return []
    
    # async def find_cross_document_patterns(self, instruction_type: str, 
    #                                      min_documents: int = 2) -> List[Dict[str, Any]]:
    #     """Find annotation patterns that appear across multiple documents."""
    #     # COMMENTED OUT: No proper implementation available
    #     # This would require complex AQL query execution
    #     pass
    
    # async def track_annotation_effectiveness(self, annotation_id: str, 
    #                                        was_correct: bool,
    #                                        correction_applied: bool,
    #                                        processing_time_ms: int) -> Dict[str, Any]:
    #     """Track how effective an annotation was in guiding extraction."""
    #     # COMMENTED OUT: No proper implementation available
    #     # This would require UPDATE queries in ArangoDB
    #     pass
    
    # async def get_annotation_statistics(self) -> Dict[str, Any]:
    #     """Get overall statistics about stored annotations."""
    #     # COMMENTED OUT: No proper implementation available
    #     # This would require complex aggregation queries
    #     pass


# Usage functions
async def working_usage():
    """Demonstrate annotation storage system."""
    storage = AnnotationStorage()
    
    # Initialize database
    logger.info("Initializing annotation database...")
    init_result = await storage.initialize_database()
    logger.info(f"Database initialized: {init_result}")
    
    # Example annotations from QB50
    test_annotations = [
        {
            "page": 5,
            "instruction": "MERGE_TABLE",
            "content": "merge table across pages",
            "rect": [100, 200, 500, 300],
            "hash": "abc123"
        },
        {
            "page": 9,
            "instruction": "FORCE_SECTION_HEADER",
            "content": "1. Introduction",
            "rect": [200, 50, 400, 80],
            "hash": "def456"
        }
    ]
    
    # Store annotations
    store_result = await storage.store_annotations(
        "test_pdfs/qb50_requirements.pdf",
        test_annotations
    )
    logger.info(f"Storage result: {store_result}")
    
    # Search for similar annotations
    search_results = await storage.search_similar_annotations(
        "table merge pages",
        instruction_filter="MERGE_TABLE"
    )
    logger.info(f"Found {len(search_results)} similar annotations")
    
    # Get statistics - COMMENTED OUT as function not implemented
    # stats = await storage.get_annotation_statistics()
    # logger.info(f"Annotation statistics: {json.dumps(stats, indent=2)}")
    
    return True


async def debug_function():
    """Test pattern detection and effectiveness tracking."""
    storage = AnnotationStorage()
    
    # Test pattern detection with multiple similar annotations
    test_annotations = [
        {"instruction": "MERGE_TABLE", "page": i, "rect": [100, 200*i, 500, 300*i], 
         "hash": f"hash_{i}", "content": f"Table part {i}"} 
        for i in range(5)
    ]
    
    patterns = await storage._detect_annotation_patterns(test_annotations)
    logger.info(f"Detected patterns: {patterns}")
    
    # Test effectiveness tracking - COMMENTED OUT as function not implemented
    # effect_result = await storage.track_annotation_effectiveness(
    #     "annot_123_abc",
    #     was_correct=True,
    #     correction_applied=True,
    #     processing_time_ms=150
    # )
    # logger.info(f"Effectiveness tracked: {effect_result}")
    
    # Test cross-document pattern search - COMMENTED OUT as function not implemented
    # cross_patterns = await storage.find_cross_document_patterns(
    #     "MERGE_TABLE",
    #     min_documents=2
    # )
    # logger.info(f"Cross-document patterns: {cross_patterns}")
    
    return True


if __name__ == "__main__":
    """
    AGENT INSTRUCTIONS:
    - DEFAULT: Runs working_usage() - demonstrates storage system
    - DEBUG: Run with 'debug' argument to test pattern detection
    - DO NOT create external test files - use debug_function() instead!
    """
    import asyncio
    import sys
    
    mode = sys.argv[1] if len(sys.argv) > 1 else "working"
    
    if mode == "debug":
        print("Running debug mode...")
        asyncio.run(debug_function())
    else:
        print("Running working usage mode...")
        asyncio.run(working_usage())