"""
Module: document_embedding_debug.py

External Dependencies:
- numpy: https://numpy.org/doc/
- loguru: https://loguru.readthedocs.io/

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

#!/usr/bin/env python
# examples/simple/document_embedding_debug.py
"""
Document embedding debug script.

This script demonstrates how to use the embedding utils to:
1. Generate embeddings for text content
2. Compare document sections using cosine similarity
3. Create a simple semantic search function

Sample input:
- Text blocks from marker document sections
- Example queries for semantic search

Expected output:
- Embeddings for text blocks
- Similarity scores between text blocks
- Search results for example queries
"""

import os
import sys
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
from loguru import logger
from pprint import pprint

# Import from marker utils
try:
    from marker.utils.embedding_utils import (
        get_embedding,
        get_embedder_model,
        cosine_similarity,
    )
    EMBEDDING_AVAILABLE = True
except ImportError:
    logger.error("Failed to import embedding utilities")
    EMBEDDING_AVAILABLE = False

# Import logging utilities
try:
    from marker.services.utils.log_utils import truncate_large_value
    LOG_UTILS_AVAILABLE = True
except ImportError:
    logger.error("Failed to import log utilities")
    LOG_UTILS_AVAILABLE = False
    
    # Fallback implementation if log utils not available
    def truncate_large_value(value, max_str_len=100, max_list_elements_shown=10):
        if isinstance(value, list) and len(value) > max_list_elements_shown:
            if value:
                element_type = type(value[0]).__name__
                return f"[<{len(value)} {element_type} elements>]"
            else:
                return "[<0 elements>]"
        return value

# Import document builder to create test document
try:
    from marker.schema.document import Document
    from marker.schema.blocks.text import Text
    from marker.schema.blocks.sectionheader import SectionHeader
    from marker.schema.groups.page import PageGroup
    from marker.schema.polygon import PolygonBox
    DOC_SCHEMA_AVAILABLE = True
except ImportError as e:
    logger.error(f"Failed to import document schema: {e}")
    DOC_SCHEMA_AVAILABLE = False

def create_test_document() -> Optional[Document]:
    """
    Create a simple test document with section headers and text blocks.
    
    Returns:
        Document object or None if schema not available
    """
    if not DOC_SCHEMA_AVAILABLE:
        logger.error("Document schema not available, cannot create test document")
        return None
    
    # Create page polygon
    page_polygon = PolygonBox(polygon=[[0, 0], [612, 0], [612, 792], [0, 792]])
    
    # Create document
    document = Document(filepath="test_document.pdf", pages=[])
    page = PageGroup(page_id=0, page_number=0, block_id=0, structure=[], polygon=page_polygon, children=[])
    document.pages = [page]
    
    # Add section headers and text content
    blocks = []
    
    # Introduction section
    intro_header = SectionHeader(
        block_id=1,
        polygon=PolygonBox(polygon=[[50, 50], [562, 50], [562, 70], [50, 70]]),
        raw="Introduction",
        heading_level=1
    )
    blocks.append(intro_header)
    
    intro_text = Text(
        block_id=2,
        polygon=PolygonBox(polygon=[[50, 80], [562, 80], [562, 150], [50, 150]]),
        raw="This document explores embedding techniques for document understanding. Embeddings are vector representations of text that capture semantic meaning."
    )
    blocks.append(intro_text)
    
    # Methods section
    methods_header = SectionHeader(
        block_id=3,
        polygon=PolygonBox(polygon=[[50, 180], [562, 180], [562, 200], [50, 200]]),
        raw="Methods",
        heading_level=1
    )
    blocks.append(methods_header)
    
    methods_text = Text(
        block_id=4,
        polygon=PolygonBox(polygon=[[50, 210], [562, 210], [562, 300], [50, 300]]),
        raw="We use transformer models to encode text into high-dimensional vectors. These vectors can be compared using cosine similarity to determine semantic relationships between text segments."
    )
    blocks.append(methods_text)
    
    # Results section
    results_header = SectionHeader(
        block_id=5,
        polygon=PolygonBox(polygon=[[50, 330], [562, 330], [562, 350], [50, 350]]),
        raw="Results",
        heading_level=1
    )
    blocks.append(results_header)
    
    results_text = Text(
        block_id=6,
        polygon=PolygonBox(polygon=[[50, 360], [562, 360], [562, 450], [50, 450]]),
        raw="Our experiments show that embeddings effectively capture semantic relationships between document sections. This allows for more nuanced search and retrieval compared to keyword-based approaches."
    )
    blocks.append(results_text)
    
    # Conclusion section
    conclusion_header = SectionHeader(
        block_id=7,
        polygon=PolygonBox(polygon=[[50, 480], [562, 480], [562, 500], [50, 500]]),
        raw="Conclusion",
        heading_level=1
    )
    blocks.append(conclusion_header)
    
    conclusion_text = Text(
        block_id=8,
        polygon=PolygonBox(polygon=[[50, 510], [562, 510], [562, 600], [50, 600]]),
        raw="Embedding-based approaches significantly enhance document processing pipelines. Future work will focus on optimizing performance and exploring multi-modal embeddings that incorporate both text and visual elements."
    )
    blocks.append(conclusion_text)
    
    # Add blocks to page
    page.children = blocks
    
    return document

def extract_text_blocks(document: Document) -> List[Dict[str, Any]]:
    """
    Extract text blocks from document with section context.
    
    Args:
        document: The marker document
        
    Returns:
        List of dicts with section info and text
    """
    if not document:
        return []
    
    text_blocks = []
    current_section = None
    
    for page in document.pages:
        for block in page.children:
            if isinstance(block, SectionHeader):
                current_section = {
                    "title": block.raw_text(None),
                    "level": block.heading_level,
                    "block_id": block.block_id
                }
            
            elif isinstance(block, Text) and current_section:
                text_blocks.append({
                    "section": current_section["title"],
                    "section_level": current_section["level"],
                    "section_id": current_section["block_id"],
                    "text": block.raw_text(None),
                    "block_id": block.block_id
                })
    
    return text_blocks

def embed_document_sections(text_blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Generate embeddings for each text block.
    
    Args:
        text_blocks: List of text blocks with section info
        
    Returns:
        Text blocks with added embeddings
    """
    if not EMBEDDING_AVAILABLE:
        logger.error("Embedding functionality not available")
        return text_blocks
    
    # Get embedding model info
    model_info = get_embedder_model()
    logger.info(f"Using embedding model: {model_info['model']} ({model_info['dimensions']} dimensions)")
    
    # Add embeddings to text blocks
    for block in text_blocks:
        # Generate embedding for this text block
        embedding = get_embedding(block["text"])
        block["embedding"] = embedding
        
        # Add embedding info with truncated values for logging
        truncated_embedding = truncate_large_value(embedding)
        logger.info(f"Generated embedding for section: {block['section']} (vector size: {len(embedding)}, truncated: {truncated_embedding})")
    
    return text_blocks

def analyze_section_similarities(embedded_blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Calculate similarities between all section pairs.
    
    Args:
        embedded_blocks: Text blocks with embeddings
        
    Returns:
        List of similarity scores between sections
    """
    similarities = []
    
    # Compare all pairs
    for i, block1 in enumerate(embedded_blocks):
        for j, block2 in enumerate(embedded_blocks):
            if i < j:  # Only compare unique pairs
                similarity = cosine_similarity(block1["embedding"], block2["embedding"])
                similarities.append({
                    "section1": block1["section"],
                    "section2": block2["section"],
                    "similarity": similarity
                })
    
    # Sort by similarity (highest first)
    similarities.sort(key=lambda x: x["similarity"], reverse=True)
    return similarities

def semantic_search(query: str, embedded_blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Perform semantic search on embedded document sections.
    
    Args:
        query: The search query text
        embedded_blocks: Text blocks with embeddings
        
    Returns:
        List of search results with similarity scores
    """
    if not EMBEDDING_AVAILABLE:
        logger.error("Embedding functionality not available")
        return []
    
    # Generate embedding for the query
    logger.info(f"Generating embedding for query: {query}")
    query_embedding = get_embedding(query)
    
    # Log with truncated value
    truncated_query_embedding = truncate_large_value(query_embedding)
    logger.debug(f"Query embedding generated: {truncated_query_embedding}")
    
    # Calculate similarity with each text block
    results = []
    for block in embedded_blocks:
        similarity = cosine_similarity(query_embedding, block["embedding"])
        results.append({
            "section": block["section"],
            "text": block["text"],
            "similarity": similarity
        })
    
    # Sort by similarity (highest first)
    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results

def validate_document_embedding():
    """
    Validate the document embedding functionality.
    """
    # Import ValidationTracker if available
    class SimpleValidator:
        def __init__(self, module_name):
            self.module_name = module_name
            self.failures = []
            self.total_tests = 0
            print(f"Validation for {module_name}")
            
        def check(self, test_name, expected, actual, description=None):
            self.total_tests += 1
            if expected == actual:
                print(f" PASS: {test_name}")
                return True
            else:
                self.failures.append({
                    "test_name": test_name,
                    "expected": expected,
                    "actual": actual,
                    "description": description
                })
                print(f" FAIL: {test_name}")
                print(f"  Expected: {expected}")
                print(f"  Actual: {actual}")
                if description:
                    print(f"  Description: {description}")
                return False
                
        def report_and_exit(self):
            failed_count = len(self.failures)
            if failed_count > 0:
                print(f"\n VALIDATION FAILED - {failed_count} of {self.total_tests} tests failed:")
                for failure in self.failures:
                    print(f"  - {failure['test_name']}")
                sys.exit(1)
            else:
                print(f"\n VALIDATION PASSED - All {self.total_tests} tests produced expected results")
                sys.exit(0)
    
    validator = SimpleValidator("Document Embedding Module")
    
    # Test 1: Check if embedding utilities are available
    validator.check(
        "Embedding utilities available",
        expected=True,
        actual=EMBEDDING_AVAILABLE,
        description="Check that embedding utilities are properly imported"
    )
    
    # Test 2: Check if document schema is available
    validator.check(
        "Document schema available",
        expected=True,
        actual=DOC_SCHEMA_AVAILABLE,
        description="Check that document schema is properly imported"
    )
    
    if not EMBEDDING_AVAILABLE or not DOC_SCHEMA_AVAILABLE:
        # Cannot proceed with further tests if basic imports fail
        validator.report_and_exit()
    
    # Test 3: Create test document
    document = create_test_document()
    validator.check(
        "Test document creation",
        expected=True,
        actual=document is not None,
        description="Check that test document is created successfully"
    )
    
    # Test 4: Extract text blocks
    text_blocks = extract_text_blocks(document)
    validator.check(
        "Text block extraction",
        expected=4,
        actual=len(text_blocks),
        description="Check that text blocks are extracted correctly"
    )
    
    # Test 5: Generate embeddings
    embedded_blocks = embed_document_sections(text_blocks)
    validator.check(
        "Embedding generation",
        expected=True,
        actual=all("embedding" in block for block in embedded_blocks),
        description="Check that all blocks have embeddings"
    )
    
    # Test 6: Analyze section similarities
    similarities = analyze_section_similarities(embedded_blocks)
    validator.check(
        "Section similarity analysis",
        expected=6,  # (4 choose 2) = 6 pairs
        actual=len(similarities),
        description="Check that all section pairs are compared"
    )
    
    # Test 7: Semantic search
    search_query = "embedding techniques for document processing"
    search_results = semantic_search(search_query, embedded_blocks)
    validator.check(
        "Semantic search",
        expected=4,
        actual=len(search_results),
        description="Check that search returns results for all sections"
    )
    
    # Test 8: Search relevance for known query - just check that we get results
    relevant_query = "semantic relationships between text"
    relevant_results = semantic_search(relevant_query, embedded_blocks)
    validator.check(
        "Search results available",
        expected=True,
        actual=len(relevant_results) > 0,
        description="Check that search returns at least one result"
    )
    
    # Generate final report
    validator.report_and_exit()

def main():
    """
    Run the document embedding debug tests.
    """
    logger.info("Starting document embedding debug")
    
    # Check if embedding utilities are available
    if not EMBEDDING_AVAILABLE:
        logger.error("Embedding utilities not available, exiting")
        sys.exit(1)
    
    # Create test document
    logger.info("Creating test document")
    document = create_test_document()
    if not document:
        logger.error("Failed to create test document, exiting")
        sys.exit(1)
    
    # Extract text blocks with section info
    logger.info("Extracting text blocks from document")
    text_blocks = extract_text_blocks(document)
    logger.info(f"Extracted {len(text_blocks)} text blocks")
    
    # Generate embeddings for text blocks
    logger.info("Generating embeddings for text blocks")
    embedded_blocks = embed_document_sections(text_blocks)
    
    # Analyze similarities between sections
    logger.info("Analyzing section similarities")
    similarities = analyze_section_similarities(embedded_blocks)
    
    # Print top 3 most similar section pairs
    logger.info("Top 3 most similar section pairs:")
    for i, sim in enumerate(similarities[:3]):
        logger.info(f"{i+1}. {sim['section1']} <-> {sim['section2']}: {sim['similarity']:.4f}")
    
    # Run semantic search with example queries
    logger.info("Running semantic search examples")
    
    example_queries = [
        "embedding techniques for document processing",
        "semantic similarity between document sections",
        "future research directions in document embeddings"
    ]
    
    for query in example_queries:
        logger.info(f"\nQuery: {query}")
        results = semantic_search(query, embedded_blocks)
        
        # Print top 2 results with truncated values
        for i, result in enumerate(results[:2]):
            # Truncate text for logging
            truncated_text = truncate_large_value(result['text'])
            
            logger.info(f"Result {i+1}: {result['section']} (score: {result['similarity']:.4f})")
            logger.info(f"  {truncated_text}")
    
    logger.info("Document embedding debug completed successfully")

if __name__ == "__main__":
    # First validate the functionality
    validate_document_embedding()
    
    # Then run the full demo
    main()