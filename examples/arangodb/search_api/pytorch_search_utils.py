"""
Module: pytorch_search_utils.py
Description: Utility functions and helper methods

External Dependencies:
- arango: https://docs.python-arango.com/
- torch: https://pytorch.org/docs/

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

import sys
import os
import json
import time
from typing import Dict, Any, List, Optional, Union, Tuple, Callable

from loguru import logger
from arango.database import StandardDatabase
from colorama import init, Fore, Style
from tabulate import tabulate
from rich.console import Console
from rich.panel import Panel

from complexity.arangodb.log_utils import truncate_large_value
from complexity.arangodb.display_utils import print_search_results as display_results


# Try to import tqdm for progress bars
try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    logger.warning("tqdm not available, progress bars will be disabled")

# In-memory document cache
_document_cache = {}
_embedding_cache = {}
_metadata_cache = {}

# Check if PyTorch is available
def has_pytorch_available() -> bool:
    """
    Check if PyTorch is available in the current environment.
    
    Returns:
        bool: True if PyTorch is available, False otherwise
    """
    try:
        import torch
        import numpy as np
        return True
    except ImportError:
        return False


def load_documents_from_arango(
    db: StandardDatabase,
    collection_name: str,
    embedding_field: str = "embedding",
    filter_conditions: str = "",
    fields_to_return: Optional[List[str]] = None,
    force_reload: bool = False,
    show_progress: bool = True
) -> Tuple[Optional[List], Optional[List], Optional[List], Optional[int]]:
    """
    Load documents and embeddings from ArangoDB with optional filtering.
    Uses in-memory caching to speed up repeated searches.
    
    Args:
        db: ArangoDB database connection
        collection_name: Collection to load documents from
        embedding_field: Field containing the embedding vectors
        filter_conditions: Optional AQL filter conditions
        fields_to_return: Fields to include in the result
        force_reload: Whether to force reload from the database
        show_progress: Whether to show a progress bar
        
    Returns:
        Tuple of:
            - embeddings: List of embedding vectors
            - ids: List of document IDs
            - metadata: List of document metadata
            - dimension: Embedding dimension
    """
    # Check if we need to reload
    cache_key = f"{collection_name}_{embedding_field}_{filter_conditions}"
    if not force_reload and cache_key in _document_cache:
        logger.info(f"Using cached documents for {collection_name}")
        return (_embedding_cache[cache_key],
                _document_cache[cache_key],
                _metadata_cache[cache_key],
                len(_embedding_cache[cache_key][0]) if len(_embedding_cache[cache_key]) > 0 else 0)
    
    try:
        import numpy as np
        
        # Default fields to return if not provided
        if not fields_to_return:
            fields_to_return = ["_key", "_id", "question", "problem", "solution", "context", "tags"]
        
        # Ensure embedding field is included
        if embedding_field not in fields_to_return:
            fields_to_return.append(embedding_field)
            
        # Ensure ID fields are included
        for field in ["_key", "_id"]:
            if field not in fields_to_return:
                fields_to_return.append(field)
        
        # Build KEEP clause
        fields_str = '", "'.join(fields_to_return)
        fields_str = f'"{fields_str}"'
        
        # Build the AQL query with optional filter
        filter_clause = f"FILTER {filter_conditions}" if filter_conditions else ""
        
        # First get the count to initialize the progress bar
        count_query = f"""
        RETURN LENGTH(
            FOR doc IN {collection_name}
            {filter_clause}
            RETURN 1
        )
        """
        
        # Execute the count query
        try:
            logger.debug("Counting documents...")
            count_cursor = db.aql.execute(count_query)
            total_docs = next(count_cursor)
            logger.info(f"Found {total_docs} documents to load")
        except Exception as e:
            logger.warning(f"Error counting documents: {e}")
            total_docs = None
        
        # Build the main query
        query = f"""
        FOR doc IN {collection_name}
        {filter_clause}
        RETURN KEEP(doc, {fields_str})
        """
        
        logger.info(f"Loading documents from {collection_name}...")
        logger.debug(f"Query: {query}")
        
        # Execute the query
        start_time = time.time()
        cursor = db.aql.execute(query)
        
        # Initialize lists
        embeddings = []
        ids = []
        metadata = []
        
        # Setup progress bar if available and requested
        if TQDM_AVAILABLE and show_progress and total_docs:
            pbar = tqdm(total=total_docs, desc="Loading documents", unit="doc")
        else:
            pbar = None
        
        # Extract data from documents
        for doc in cursor:
            if pbar:
                pbar.update(1)
                
            if embedding_field in doc and doc[embedding_field]:
                embeddings.append(doc[embedding_field])
                ids.append(doc["_id"])
                # Make a copy of the document for metadata
                meta = doc.copy()
                # Remove the embedding to save memory
                if embedding_field in meta:
                    del meta[embedding_field]
                metadata.append(meta)
        
        # Close progress bar
        if pbar:
            pbar.close()
        
        # Convert embeddings to numpy array
        embeddings_np = np.array(embeddings, dtype=np.float32)
        
        # Get embedding dimension
        dimension = embeddings_np.shape[1] if embeddings_np.size > 0 else 0
        
        load_time = time.time() - start_time
        logger.info(f"Loaded {len(embeddings)} documents in {load_time:.2f}s with embedding dimension {dimension}")
        
        # Cache the results
        _embedding_cache[cache_key] = embeddings_np
        _document_cache[cache_key] = ids
        _metadata_cache[cache_key] = metadata
        
        return embeddings_np, ids, metadata, dimension
    
    except Exception as e:
        logger.exception(f"Error loading documents from ArangoDB: {e}")
        return None, None, None, None


def clear_document_cache():
    """Clear the in-memory document cache to free up memory."""
    global _document_cache, _embedding_cache, _metadata_cache
    _document_cache = {}
    _embedding_cache = {}
    _metadata_cache = {}
    logger.info("Document cache cleared")


def pytorch_vector_search(
    embeddings: List,
    query_embedding: List[float],
    ids: List[str],
    metadata: List[Dict],
    threshold: float = 0.7,
    top_k: int = 10,
    batch_size: int = 128,
    fp16: bool = False,
    distance_fn: str = "cosine",
    show_progress: bool = True
) -> Tuple[List[Dict[str, Any]], float]:
    """
    Perform optimized similarity search using PyTorch.
    
    Args:
        embeddings: Document embeddings
        query_embedding: Query embedding vector
        ids: Document IDs
        metadata: Document metadata
        threshold: Minimum similarity threshold
        top_k: Maximum number of results to return
        batch_size: Batch size for processing
        fp16: Whether to use FP16 precision
        distance_fn: Distance function to use (cosine, dot, l2)
        show_progress: Whether to show a progress bar
        
    Returns:
        Tuple of:
            - results: List of search results
            - search_time: Search execution time
    """
    try:
        import torch
        import numpy as np
        
        start_time = time.time()
        
        # Determine device
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"Using device: {device} for search")
        
        # Convert embeddings to torch tensors
        embeddings_tensor = torch.tensor(embeddings, device=device)
        
        # Convert query embedding to torch tensor
        query_tensor = torch.tensor(query_embedding, device=device)
        
        # Use FP16 if requested and available
        if fp16 and device.type == "cuda":
            embeddings_tensor = embeddings_tensor.half()
            query_tensor = query_tensor.half()
        
        # Normalize embeddings for cosine similarity
        if distance_fn == "cosine":
            embeddings_norm = torch.nn.functional.normalize(embeddings_tensor, p=2, dim=1)
            query_norm = torch.nn.functional.normalize(query_tensor, p=2, dim=0)
        else:
            embeddings_norm = embeddings_tensor
            query_norm = query_tensor
        
        # Calculate similarities
        results = []
        
        # Process in batches to avoid OOM
        num_docs = embeddings_norm.shape[0]
        num_batches = (num_docs + batch_size - 1) // batch_size  # Ceiling division
        
        # Setup progress bar if available and requested
        if TQDM_AVAILABLE and show_progress and num_batches > 1:
            pbar = tqdm(total=num_batches, desc="Computing similarities", unit="batch")
        else:
            pbar = None
        
        for i in range(0, num_docs, batch_size):
            if pbar:
                pbar.update(1)
                
            batch_end = min(i + batch_size, num_docs)
            batch = embeddings_norm[i:batch_end]
            
            # Calculate similarities based on distance function
            if distance_fn == "cosine":
                # Cosine similarity (higher is better)
                similarities = torch.matmul(batch, query_norm)
            elif distance_fn == "dot":
                # Dot product (higher is better)
                similarities = torch.matmul(batch, query_norm)
            elif distance_fn == "l2":
                # L2 distance (lower is better)
                similarities = -torch.sum((batch - query_norm) ** 2, dim=1)
            else:
                raise ValueError(f"Unknown distance function: {distance_fn}")
            
            # Get indices and scores for the batch
            for j, similarity in enumerate(similarities):
                idx = i + j
                score = similarity.item()
                
                # Only include results that meet the threshold
                if score >= threshold:
                    results.append({
                        "id": ids[idx],
                        "metadata": metadata[idx],
                        "similarity": score
                    })
        
        # Close progress bar
        if pbar:
            pbar.close()
        
        # Sort results by similarity (descending)
        results.sort(key=lambda x: x["similarity"], reverse=True)
        
        # Limit to top_k results
        results = results[:top_k]
        
        search_time = time.time() - start_time
        logger.info(f"Search completed in {search_time:.3f}s, found {len(results)} results")
        
        return results, search_time
    
    except Exception as e:
        logger.exception(f"Error in PyTorch search: {e}")
        return [], time.time() - start_time


def pytorch_search(
    db: StandardDatabase,
    query_embedding: List[float],
    query_text: str,
    collection_name: str,
    embedding_field: str = "embedding",
    filter_conditions: str = "",
    min_score: float = 0.7,
    top_n: int = 10,
    output_format: str = "table",
    fields_to_return: Optional[List[str]] = None,
    force_reload: bool = False,
    show_progress: bool = True
) -> Dict[str, Any]:
    """
    Perform semantic search using PyTorch.
    
    Args:
        db: ArangoDB database
        query_embedding: Vector representation of the query
        query_text: Original query text
        collection_name: Name of the collection to search
        embedding_field: Name of the field containing embeddings
        filter_conditions: AQL filter conditions
        min_score: Minimum similarity threshold
        top_n: Maximum number of results to return
        output_format: Output format ("table" or "json")
        fields_to_return: Fields to include in the result
        force_reload: Whether to force reload from the database
        show_progress: Whether to show a progress bar
        
    Returns:
        Dict with search results
    """
    start_time = time.time()
    
    # Check if PyTorch is available
    if not has_pytorch_available():
        error_msg = "PyTorch is not available. Please install PyTorch to use this function."
        logger.error(error_msg)
        return {
            "results": [],
            "total": 0,
            "query": query_text,
            "time": 0,
            "format": output_format,
            "error": error_msg,
            "search_engine": "pytorch-failed"
        }
    
    logger.info(f"Using PyTorch-based semantic search with threshold {min_score}")
    if filter_conditions:
        logger.info(f"Applying filter conditions: {filter_conditions}")
    
    # Load documents with filtering
    embeddings, ids, metadata, dimension = load_documents_from_arango(
        db, collection_name, embedding_field,
        filter_conditions=filter_conditions,
        fields_to_return=fields_to_return,
        force_reload=force_reload,
        show_progress=show_progress
    )
    
    if embeddings is None or len(embeddings) == 0:
        logger.warning("No documents found matching the filter criteria")
        return {
            "results": [],
            "total": 0,
            "query": query_text,
            "time": time.time() - start_time,
            "format": output_format,
            "search_engine": "pytorch-no-results"
        }
    
    # Check if GPU is available
    import torch
    has_gpu = torch.cuda.is_available()
    logger.info(f"GPU available: {has_gpu}")
    
    # Perform similarity search
    results, search_time = pytorch_vector_search(
        embeddings=embeddings,
        query_embedding=query_embedding,
        ids=ids,
        metadata=metadata,
        threshold=min_score,
        top_k=top_n,
        batch_size=128,
        fp16=has_gpu,
        show_progress=show_progress
    )
    
    # Format results to match the expected output
    formatted_results = []
    for result in results:
        formatted_result = {
            "doc": result["metadata"],
            "similarity_score": result["similarity"]
        }
        formatted_results.append(formatted_result)
    
    # Return results
    return {
        "results": formatted_results[:top_n],  # Apply top_n limit
        "total": len(results),
        "query": query_text,
        "time": time.time() - start_time,
        "format": output_format,
        "search_engine": "pytorch"
    }


def print_search_results(search_results: Dict[str, Any], max_width: int = 120) -> None:
    """
    Print search results in the specified format (table or JSON).
    
    Args:
        search_results: The search results to display
        max_width: Maximum width for text fields in characters (used for table format)
    """
    # Get the requested output format
    output_format = search_results.get("format", "table").lower()
    
    # For JSON output, just print the JSON
    if output_format == "json":
        json_results = {
            "results": search_results.get("results", []),
            "total": search_results.get("total", 0),
            "query": search_results.get("query", ""),
            "time": search_results.get("time", 0),
            "search_engine": search_results.get("search_engine", "pytorch")
        }
        print(json.dumps(json_results, indent=2))
        return
    
    # Initialize colorama for cross-platform colored terminal output
    init(autoreset=True)
    
    # Print basic search metadata
    result_count = len(search_results.get("results", []))
    total_count = search_results.get("total", 0)
    query = search_results.get("query", "")
    search_time = search_results.get("time", 0)
    search_engine = search_results.get("search_engine", "pytorch")
    
    print(f"{Fore.CYAN}{'═' * 80}{Style.RESET_ALL}")
    print(f"Found {Fore.GREEN}{result_count}{Style.RESET_ALL} results for query '{Fore.YELLOW}{query}{Style.RESET_ALL}'")
    print(f"Engine: {Fore.MAGENTA}{search_engine}{Style.RESET_ALL}, Time: {Fore.CYAN}{search_time:.3f}s{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'─' * 80}{Style.RESET_ALL}")
    
    # Use common display utility for consistent formatting across search modes
    display_results(
        search_results,
        max_width=max_width,
        title_field="Content",
        id_field="_key",
        score_field="similarity_score",
        score_name="Similarity Score",
        table_title="PyTorch Search Results"
    )
    
    # Print detailed info for first result if there are results
    results = search_results.get("results", [])
    if results:
        print_result_details(results[0])


def print_result_details(result: Dict[str, Any]) -> None:
    """
    Print beautifully formatted details about a search result.
    
    Args:
        result: Search result to display
    """
    # Initialize colorama for cross-platform colored terminal output
    init(autoreset=True)
    
    doc = result.get("doc", {})
    score = result.get("similarity_score", 0)
    
    # Print document header with key
    key = doc.get("_key", "N/A")
    header = f"{Fore.GREEN}{'═' * 80}{Style.RESET_ALL}"
    print(f"\n{header}")
    print(f"{Fore.GREEN}  DOCUMENT: {Fore.YELLOW}{key}{Style.RESET_ALL}  ")
    print(f"{header}")
    
    # Get fields to display (excluding internal fields and tags)
    display_fields = [f for f in doc.keys() if f not in ["_key", "_id", "tags", "_rev", "embedding"]]
    
    # Print all fields with truncation
    for field in display_fields:
        if field in doc and doc[field]:
            field_title = field.title()
            # Truncate large field values
            safe_value = truncate_large_value(doc[field], max_str_len=100)
            print(f"{Fore.YELLOW}{field_title}:{Style.RESET_ALL} {safe_value}")
    
    # Print score with color coding based on value
    if score > 0.9:
        score_str = f"{Fore.GREEN}{score:.2f}{Style.RESET_ALL}"
    elif score > 0.7:
        score_str = f"{Fore.YELLOW}{score:.2f}{Style.RESET_ALL}"
    else:
        score_str = f"{Fore.WHITE}{score:.2f}{Style.RESET_ALL}"
    print(f"\n{Fore.CYAN}Similarity Score:{Style.RESET_ALL} {score_str}")
    
    # Print tags in a special section if present with truncation
    if "tags" in doc and isinstance(doc["tags"], list) and doc["tags"]:
        tags = doc["tags"]
        print(f"\n{Fore.BLUE}Tags:{Style.RESET_ALL}")
        
        # Truncate tag list if it's very long
        safe_tags = truncate_large_value(tags, max_list_elements_shown=10)
        
        if isinstance(safe_tags, str):  # It's already a summary string'
            print(f"  {safe_tags}")
        else:  # It's still a list'
            tag_colors = [Fore.BLUE, Fore.MAGENTA, Fore.CYAN, Fore.GREEN, Fore.YELLOW]
            for i, tag in enumerate(safe_tags):
                color = tag_colors[i % len(tag_colors)]  # Cycle through colors
                print(f"  • {color}{tag}{Style.RESET_ALL}")
    
    # Print footer
    print(f"{header}\n")


if __name__ == "__main__":
    """
    Test the PyTorch search utilities with sample query.
    """
    # Configure logging
    logger.remove()
    logger.add(
        sys.stderr,
        level="INFO",
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <7}</level> | <cyan>{message}</cyan>",
        colorize=True  # Explicitly enable colorization
    )
    
    # Parse command line arguments
    output_format = "table"
    fields_to_return = None
    test_query = "What are primary colors?"
    collection_name = "complexity"
    min_score = 0.7
    top_n = 10
    show_progress = True

    # Parse command line arguments
    for i, arg in enumerate(sys.argv):
        if arg == "--format" and i+1 < len(sys.argv):
            output_format = sys.argv[i+1]
        elif arg == "--json":
            output_format = "json"
        elif arg == "--fields" and i+1 < len(sys.argv):
            fields_to_return = sys.argv[i+1].split(',')
            logger.info(f"Using custom fields to return: {fields_to_return}")
        elif arg == "--query" and i+1 < len(sys.argv):
            test_query = sys.argv[i+1]
        elif arg == "--collection" and i+1 < len(sys.argv):
            collection_name = sys.argv[i+1]
        elif arg == "--threshold" and i+1 < len(sys.argv):
            min_score = float(sys.argv[i+1])
        elif arg == "--limit" and i+1 < len(sys.argv):
            top_n = int(sys.argv[i+1])
        elif arg == "--no-progress":
            show_progress = False
    
    # Check if PyTorch is available
    if not has_pytorch_available():
        print(f"{Fore.RED}PyTorch is not available. Please install PyTorch to use this script.{Style.RESET_ALL}")
        sys.exit(1)
    
    # Import ArangoDB setup utilities
    try:
        from complexity.arangodb.arango_setup import connect_arango, ensure_database
        from complexity.arangodb.embedding_utils import get_embedding
        from complexity.arangodb.display_utils import print_search_results as display_results
        from complexity.arangodb.log_utils import truncate_large_value
    except ImportError as e:
        print(f"{Fore.RED}Missing dependencies: {e}{Style.RESET_ALL}")
        print("Please make sure that complexity.arangodb modules are available.")
        sys.exit(1)
    
    try:
        # Set up database connection
        client = connect_arango()
        db = ensure_database(client)
        
        # Get query embedding
        logger.info(f"Generating embedding for query: '{test_query}'")
        query_embedding = get_embedding(test_query)
        if not query_embedding:
            print(f"{Fore.RED}Could not generate embedding for test query{Style.RESET_ALL}")
            sys.exit(1)
        
        # Run PyTorch search
        logger.info(f"Running PyTorch search with threshold {min_score} and limit {top_n}")
        search_results = pytorch_search(
            db=db,
            query_embedding=query_embedding,
            query_text=test_query,
            collection_name=collection_name,
            min_score=min_score,
            top_n=top_n,
            output_format=output_format,
            fields_to_return=fields_to_return,
            show_progress=show_progress
        )
        
        # Print metadata headers
        init(autoreset=True)
        print(f"{Fore.CYAN}{'═' * 80}{Style.RESET_ALL}")
        print(f"Found {Fore.GREEN}{len(search_results.get('results', []))}{Style.RESET_ALL} results for query '{Fore.YELLOW}{test_query}{Style.RESET_ALL}'")
        print(f"Engine: {Fore.MAGENTA}{search_results.get('search_engine', 'pytorch')}{Style.RESET_ALL}, Time: {Fore.CYAN}{search_results.get('time', 0):.3f}s{Style.RESET_ALL}")
        print(f"{Fore.CYAN}{'─' * 80}{Style.RESET_ALL}")
        
        # Use the common display utility
        display_results(
            search_results,
            max_width=120,
            title_field="Content",
            id_field="_key",
            score_field="similarity_score",
            score_name="Similarity Score",
            table_title="PyTorch Search Results"
        )
        
        # Print detailed info for first result if there are results
        results = search_results.get("results", [])
        if results:
            print_result_details(results[0])
        
    except Exception as e:
        logger.exception(f"Error running PyTorch search: {e}")
        print(f"{Fore.RED}Error: {str(e)}{Style.RESET_ALL}")
        sys.exit(1)