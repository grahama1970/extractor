"""
Module: debug_search.py

External Dependencies:
- loguru: https://loguru.readthedocs.io/
- arango: https://docs.python-arango.com/

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

#!/usr/bin/env python3
"""
Diagnostic Script for ArangoDB Search API Issues

This script performs diagnostic tests on the different search API methods to help
identify issues with the search functionality. It provides detailed debugging 
information, including collection status, view configuration, embedding dimensions,
and test document validation.

Usage:
    python -m complexity.arangodb.search_api.debug_search [COMMAND] [OPTIONS]

Commands:
    all         Run all diagnostic tests
    bm25        Test BM25 search functionality
    semantic    Test semantic search functionality
    hybrid      Test hybrid search functionality
    config      Check database and view configuration
    embed       Test embedding generation and dimensions
    collections Verify collection status and document counts
"""

import os
import sys
import json
import time
from typing import Dict, Any, List, Optional
from loguru import logger
from colorama import init, Fore, Style

try:
    # Import database setup and connection
    from complexity.arangodb.arango_setup import (
        connect_arango,
        ensure_database,
        ensure_arangosearch_view,
        ensure_collection,
        ensure_memory_agent_collections,
    )
    
    # Import search methods
    from complexity.arangodb.search_api.bm25_search import bm25_search
    from complexity.arangodb.search_api.semantic_search import semantic_search
    from complexity.arangodb.search_api.hybrid_search import hybrid_search
    from complexity.arangodb.search_api.keyword_search import search_keyword
    from complexity.arangodb.search_api.tag_search import tag_search
    
    # Import configuration and utilities
    from complexity.arangodb.config import (
        COLLECTION_NAME,
        VIEW_NAME,
        EMBEDDING_MODEL,
        EMBEDDING_DIMENSIONS,
        EMBEDDING_FIELD,
        SEARCH_FIELDS,
    )
    
    from complexity.arangodb.embedding_utils import (
        get_embedding,
        cosine_similarity,
    )
    
except ImportError as e:
    print(f"Error importing required modules: {e}")
    sys.exit(1)


def print_section(title: str, color=Fore.CYAN):
    """Print a section header with color"""
    print(f"\n{color}{'=' * 70}")
    print(f"{title}")
    print(f"{'=' * 70}{Style.RESET_ALL}\n")


def check_environment_variables():
    """Check all required environment variables are set"""
    print_section("ENVIRONMENT VARIABLES", Fore.GREEN)
    
    required_vars = [
        "ARANGO_HOST", 
        "ARANGO_USER", 
        "ARANGO_PASSWORD", 
        "ARANGO_DB_NAME"
    ]
    
    all_present = True
    for var in required_vars:
        value = os.environ.get(var, None)
        if value:
            # Mask password
            if var == "ARANGO_PASSWORD":
                display_val = "********"
            else:
                display_val = value
            print(f"{Fore.GREEN} {var}: {display_val}{Style.RESET_ALL}")
        else:
            all_present = False
            print(f"{Fore.RED} {var}: NOT SET{Style.RESET_ALL}")
    
    if not all_present:
        print(f"\n{Fore.YELLOW}⚠️  Missing environment variables will cause connection issues{Style.RESET_ALL}")
        print(f"Set the following variables:")
        print("""
        export ARANGO_HOST="http://localhost:8529"
        export ARANGO_USER="root"
        export ARANGO_PASSWORD="openSesame"
        export ARANGO_DB_NAME="memory_bank"
        """)
    else:
        print(f"\n{Fore.GREEN} All required environment variables are set{Style.RESET_ALL}")
    
    return all_present


def check_database_connection():
    """Test database connection and basic configuration"""
    print_section("DATABASE CONNECTION", Fore.GREEN)
    
    try:
        client = connect_arango()
        print(f"{Fore.GREEN} Connected to ArangoDB server: {os.environ.get('ARANGO_HOST')}{Style.RESET_ALL}")
        
        # Check server version
        version = client.version()
        print(f"ArangoDB Version: {version.get('version', 'Unknown')}")
        
        # Check database existence
        db = ensure_database(client)
        print(f"{Fore.GREEN} Database '{os.environ.get('ARANGO_DB_NAME')}' exists or was created{Style.RESET_ALL}")
        
        # List collections
        collections = db.collections()
        collection_names = [c['name'] for c in collections if not c['name'].startswith('_')]
        print(f"Collections: {', '.join(collection_names) if collection_names else 'None'}")
        
        # List views
        views = db.views()
        view_names = [v['name'] for v in views]
        print(f"Views: {', '.join(view_names) if view_names else 'None'}")
        
        # Check for expected collections
        if COLLECTION_NAME in collection_names:
            print(f"{Fore.GREEN} Main collection '{COLLECTION_NAME}' exists{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED} Main collection '{COLLECTION_NAME}' does not exist{Style.RESET_ALL}")
        
        # Check for expected views
        if VIEW_NAME in view_names:
            print(f"{Fore.GREEN} Search view '{VIEW_NAME}' exists{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED} Search view '{VIEW_NAME}' does not exist{Style.RESET_ALL}")
        
        return db, True
    
    except Exception as e:
        print(f"{Fore.RED} Database connection failed: {str(e)}{Style.RESET_ALL}")
        return None, False


def check_collection_status(db):
    """Check collection status and document counts"""
    print_section("COLLECTION STATUS", Fore.GREEN)
    
    try:
        # Ensure the main collection exists
        collection = ensure_collection(db, COLLECTION_NAME)
        
        # Get document count
        doc_count = collection.count()
        print(f"Collection '{COLLECTION_NAME}' has {doc_count} documents")
        
        if doc_count == 0:
            print(f"{Fore.YELLOW}⚠️  Collection is empty - no search results will be returned{Style.RESET_ALL}")
            return False
        
        # Sample a document to check structure
        sample_doc = db.aql.execute(f"FOR doc IN {COLLECTION_NAME} LIMIT 1 RETURN doc").next()
        print(f"\nSample document structure:")
        
        # Check for key fields
        key_fields = ["_key", "_id"] + SEARCH_FIELDS
        
        for field in key_fields:
            field_path = field.split('.')
            value = sample_doc
            valid_field = True
            
            # Navigate nested fields
            for path in field_path:
                if isinstance(value, dict) and path in value:
                    value = value[path]
                else:
                    valid_field = False
                    break
            
            if valid_field:
                # Truncate long values for display
                if isinstance(value, str) and len(value) > 100:
                    display_val = value[:100] + "..."
                elif isinstance(value, (list, dict)):
                    display_val = f"{type(value).__name__} with {len(value)} items"
                else:
                    display_val = value
                
                print(f"{Fore.GREEN} {field}: {display_val}{Style.RESET_ALL}")
            else:
                print(f"{Fore.RED} {field}: Not found{Style.RESET_ALL}")
        
        # Check for embedding field specifically
        if EMBEDDING_FIELD in sample_doc:
            embedding = sample_doc[EMBEDDING_FIELD]
            if isinstance(embedding, list):
                dim = len(embedding)
                print(f"\nEmbedding dimensions: {dim}")
                
                if dim != EMBEDDING_DIMENSIONS:
                    print(f"{Fore.RED} Dimension mismatch: Found {dim}, expected {EMBEDDING_DIMENSIONS}{Style.RESET_ALL}")
                else:
                    print(f"{Fore.GREEN} Dimensions match configuration ({dim}){Style.RESET_ALL}")
            else:
                print(f"{Fore.RED} Embedding field exists but is not a list{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED} Embedding field '{EMBEDDING_FIELD}' not found in document{Style.RESET_ALL}")
        
        return True
    
    except Exception as e:
        print(f"{Fore.RED}Error checking collection: {str(e)}{Style.RESET_ALL}")
        return False


def check_view_configuration(db):
    """Check the search view configuration"""
    print_section("SEARCH VIEW CONFIGURATION", Fore.GREEN)
    
    try:
        # Get the view properties
        view_props = db.view(VIEW_NAME).properties()
        print(f"View name: {view_props.get('name')}")
        print(f"View type: {view_props.get('type')}")
        
        # Check links
        links = view_props.get('links', {})
        print(f"\nLinked collections:")
        for coll, config in links.items():
            print(f"  - {coll}:")
            
            # Check included fields
            include = config.get('includeAllFields', False)
            if include:
                print(f"    • {Fore.GREEN} includeAllFields: True{Style.RESET_ALL}")
            else:
                print(f"    • {Fore.YELLOW}⚠️  includeAllFields: False{Style.RESET_ALL}")
                
                # Check specific fields
                fields = config.get('fields', {})
                print(f"    • Indexed fields:")
                for field, field_config in fields.items():
                    print(f"      - {field}: {field_config}")
            
            # Check analyzers
            analyzers = config.get('analyzers', [])
            print(f"    • Analyzers: {', '.join(analyzers)}")
            
            # Check stored values (for vector search)
            stored_values = config.get('storeValues', [])
            print(f"    • Stored values: {', '.join(stored_values)}")
        
        # Check if the main collection is linked to the view
        if COLLECTION_NAME in links:
            print(f"\n{Fore.GREEN} Main collection '{COLLECTION_NAME}' is linked to the view{Style.RESET_ALL}")
        else:
            print(f"\n{Fore.RED} Main collection '{COLLECTION_NAME}' is NOT linked to the view{Style.RESET_ALL}")
            print(f"  This will prevent BM25 search from working!")
        
        # Check if the view has the vector index setup (in primary sort fields usually)
        primary_sort = view_props.get('primarySort', [])
        has_vector_index = False
        
        for field in primary_sort:
            if field.get('field', '') == EMBEDDING_FIELD:
                has_vector_index = True
                break
        
        if has_vector_index:
            print(f"{Fore.GREEN} Vector field '{EMBEDDING_FIELD}' is in primary sort (vector search enabled){Style.RESET_ALL}")
        else:
            print(f"{Fore.YELLOW}⚠️  Vector field not found in primary sort - vector search may not work{Style.RESET_ALL}")
        
        return True
    
    except Exception as e:
        print(f"{Fore.RED}Error checking view configuration: {str(e)}{Style.RESET_ALL}")
        return False


def test_embedding_generation():
    """Test embedding generation and dimensions"""
    print_section("EMBEDDING GENERATION", Fore.GREEN)
    
    try:
        # Generate a test embedding
        test_text = "This is a test text for embedding generation"
        print(f"Generating embedding for: '{test_text}'")
        
        start_time = time.time()
        embedding = get_embedding(test_text)
        end_time = time.time()
        
        # Check the result
        if embedding is not None and isinstance(embedding, list):
            dim = len(embedding)
            print(f"{Fore.GREEN} Successfully generated embedding with {dim} dimensions{Style.RESET_ALL}")
            print(f"Generation time: {(end_time - start_time):.4f} seconds")
            
            # Check against configuration
            if dim != EMBEDDING_DIMENSIONS:
                print(f"{Fore.RED} Dimension mismatch: Generated {dim}, expected {EMBEDDING_DIMENSIONS}{Style.RESET_ALL}")
            else:
                print(f"{Fore.GREEN} Dimensions match configuration ({dim}){Style.RESET_ALL}")
            
            # Show first few values
            preview = [f"{v:.6f}" for v in embedding[:5]]
            print(f"First 5 values: {preview}...")
            
            return True
        else:
            print(f"{Fore.RED} Failed to generate embedding or invalid result{Style.RESET_ALL}")
            print(f"Result: {embedding}")
            return False
    
    except Exception as e:
        print(f"{Fore.RED}Error testing embedding generation: {str(e)}{Style.RESET_ALL}")
        return False


def test_bm25_search(db):
    """Test BM25 search functionality"""
    print_section("BM25 SEARCH TEST", Fore.GREEN)
    
    try:
        # Define test query
        test_query = "python error"
        print(f"Running BM25 search for: '{test_query}'")
        
        # Run search with detailed information
        results = bm25_search(
            db=db,
            query_text=test_query,
            top_n=3,
            min_score=0.0,
            output_format="json"
        )
        
        # Check for errors
        if "error" in results:
            print(f"{Fore.RED} Search returned an error: {results['error']}{Style.RESET_ALL}")
            return False
        
        # Check results
        result_count = len(results.get("results", []))
        total_count = results.get("total", 0)
        search_time = results.get("time", 0)
        
        print(f"Found {result_count} results (out of {total_count} total)")
        print(f"Search time: {search_time*1000:.2f}ms")
        
        if result_count == 0:
            print(f"{Fore.YELLOW}⚠️  No results found - this may indicate an issue{Style.RESET_ALL}")
            
            # Print diagnostic information
            check_view_configuration(db)
            
            print(f"\nPossible causes:")
            print(f"  1. The collection might be empty")
            print(f"  2. The view might not be configured correctly")
            print(f"  3. The search fields might not match the document structure")
            print(f"  4. The query might not match any documents")
            
            return False
        else:
            print(f"{Fore.GREEN} Search returned {result_count} results{Style.RESET_ALL}")
            
            # Show first result
            first_result = results["results"][0]
            print(f"\nTop result:")
            print(f"  Document key: {first_result['doc'].get('_key', 'N/A')}")
            print(f"  Score: {first_result.get('score', 0):.5f}")
            
            # Try to find the most relevant field to display
            content_fields = ["question", "problem", "content", "text", "title"]
            content = None
            content_field = None
            
            for field in content_fields:
                if field in first_result['doc'] and first_result['doc'][field]:
                    content = first_result['doc'][field]
                    content_field = field
                    break
            
            if content:
                # Truncate long content
                if len(content) > 100:
                    content = content[:100] + "..."
                print(f"  {content_field.capitalize()}: {content}")
            
            # Show tags if present
            if "tags" in first_result['doc']:
                tags = first_result['doc']["tags"]
                print(f"  Tags: {', '.join(tags)}")
            
            return True
    
    except Exception as e:
        print(f"{Fore.RED}Error testing BM25 search: {str(e)}{Style.RESET_ALL}")
        import traceback
        traceback.print_exc()
        return False


def test_semantic_search(db):
    """Test semantic search functionality"""
    print_section("SEMANTIC SEARCH TEST", Fore.GREEN)
    
    try:
        # Define test query
        test_query = "python error"
        print(f"Running semantic search for: '{test_query}'")
        
        # Run search with detailed information
        results = semantic_search(
            db=db,
            query_text=test_query,
            top_n=3,
            min_score=0.5,
            output_format="json"
        )
        
        # Check for errors
        if "error" in results:
            print(f"{Fore.RED} Search returned an error: {results['error']}{Style.RESET_ALL}")
            
            if "vector search" in results["error"].lower():
                print(f"{Fore.YELLOW}⚠️  Vector search error - checking embedding dimensions...{Style.RESET_ALL}")
                
                # Get test query embedding
                print(f"Generating embedding for test query...")
                query_embedding = get_embedding(test_query)
                if query_embedding:
                    query_dim = len(query_embedding)
                    print(f"Query embedding dimensions: {query_dim}")
                    
                    # Check against configuration
                    if query_dim != EMBEDDING_DIMENSIONS:
                        print(f"{Fore.RED} Query dimension mismatch: Generated {query_dim}, expected {EMBEDDING_DIMENSIONS}{Style.RESET_ALL}")
                        print(f"This is likely causing the vector search error!")
                    
                    # Check a document embedding
                    print(f"\nChecking document embedding dimensions...")
                    try:
                        sample_doc = db.aql.execute(f"FOR doc IN {COLLECTION_NAME} FILTER doc.{EMBEDDING_FIELD} != null LIMIT 1 RETURN doc").next()
                        doc_embedding = sample_doc.get(EMBEDDING_FIELD, [])
                        doc_dim = len(doc_embedding)
                        print(f"Document embedding dimensions: {doc_dim}")
                        
                        if doc_dim != query_dim:
                            print(f"{Fore.RED} Dimension mismatch between query ({query_dim}) and document ({doc_dim}){Style.RESET_ALL}")
                            print(f"This is definitely causing the vector search error!")
                        
                    except Exception as e:
                        print(f"{Fore.RED}Error checking document embedding: {str(e)}{Style.RESET_ALL}")
            
            return False
        
        # Check results
        result_count = len(results.get("results", []))
        search_time = results.get("time", 0)
        search_engine = results.get("search_engine", "unknown")
        
        print(f"Found {result_count} results using {search_engine}")
        print(f"Search time: {search_time*1000:.2f}ms")
        
        if result_count == 0:
            print(f"{Fore.YELLOW}⚠️  No results found - this may indicate an issue{Style.RESET_ALL}")
            return False
        else:
            print(f"{Fore.GREEN} Search returned {result_count} results{Style.RESET_ALL}")
            
            # Show first result
            first_result = results["results"][0]
            print(f"\nTop result:")
            print(f"  Document key: {first_result['doc'].get('_key', 'N/A')}")
            print(f"  Similarity score: {first_result.get('similarity_score', 0):.5f}")
            
            # Try to find the most relevant field to display
            content_fields = ["question", "problem", "content", "text", "title"]
            content = None
            content_field = None
            
            for field in content_fields:
                if field in first_result['doc'] and first_result['doc'][field]:
                    content = first_result['doc'][field]
                    content_field = field
                    break
            
            if content:
                # Truncate long content
                if len(content) > 100:
                    content = content[:100] + "..."
                print(f"  {content_field.capitalize()}: {content}")
            
            # Show tags if present
            if "tags" in first_result['doc']:
                tags = first_result['doc']["tags"]
                print(f"  Tags: {', '.join(tags)}")
            
            return True
    
    except Exception as e:
        print(f"{Fore.RED}Error testing semantic search: {str(e)}{Style.RESET_ALL}")
        import traceback
        traceback.print_exc()
        return False


def test_hybrid_search(db):
    """Test hybrid search functionality"""
    print_section("HYBRID SEARCH TEST", Fore.GREEN)
    
    try:
        # Define test query
        test_query = "python error"
        print(f"Running hybrid search for: '{test_query}'")
        
        # Create min_score dictionary for thresholds
        min_score = {
            "bm25": 0.01,     # BM25 threshold
            "semantic": 0.5   # Semantic similarity threshold
        }
        
        # Run search with detailed information
        results = hybrid_search(
            db=db,
            query_text=test_query,
            top_n=3,
            min_score=min_score,
            initial_k=20,
            rrf_k=60,
            output_format="json"
        )
        
        # Check for errors
        if "error" in results:
            print(f"{Fore.RED} Search returned an error: {results['error']}{Style.RESET_ALL}")
            return False
        
        # Check results
        result_count = len(results.get("results", []))
        search_time = results.get("time", 0)
        
        print(f"Found {result_count} results")
        print(f"Search time: {search_time*1000:.2f}ms")
        
        if result_count == 0:
            print(f"{Fore.YELLOW}⚠️  No results found - this may indicate an issue{Style.RESET_ALL}")
            return False
        else:
            print(f"{Fore.GREEN} Search returned {result_count} results{Style.RESET_ALL}")
            
            # Show first result
            first_result = results["results"][0]
            print(f"\nTop result:")
            print(f"  Document key: {first_result['doc'].get('_key', 'N/A')}")
            print(f"  RRF score: {first_result.get('score', 0):.5f}")
            
            # Show component scores if available
            if "bm25_score" in first_result:
                print(f"  BM25 score: {first_result.get('bm25_score', 0):.5f}")
            if "semantic_score" in first_result:
                print(f"  Semantic score: {first_result.get('semantic_score', 0):.5f}")
            
            # Try to find the most relevant field to display
            content_fields = ["question", "problem", "content", "text", "title"]
            content = None
            content_field = None
            
            for field in content_fields:
                if field in first_result['doc'] and first_result['doc'][field]:
                    content = first_result['doc'][field]
                    content_field = field
                    break
            
            if content:
                # Truncate long content
                if len(content) > 100:
                    content = content[:100] + "..."
                print(f"  {content_field.capitalize()}: {content}")
            
            # Show tags if present
            if "tags" in first_result['doc']:
                tags = first_result['doc']["tags"]
                print(f"  Tags: {', '.join(tags)}")
            
            return True
    
    except Exception as e:
        print(f"{Fore.RED}Error testing hybrid search: {str(e)}{Style.RESET_ALL}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all diagnostic tests"""
    # Check environment variables first
    env_ok = check_environment_variables()
    if not env_ok:
        print(f"{Fore.YELLOW}⚠️  Fix environment variables before continuing{Style.RESET_ALL}")
        return
    
    # Try to connect to database
    db, conn_ok = check_database_connection()
    if not conn_ok or db is None:
        print(f"{Fore.RED} Cannot continue without database connection{Style.RESET_ALL}")
        return
    
    # Check collections
    collection_ok = check_collection_status(db)
    if not collection_ok:
        print(f"{Fore.YELLOW}⚠️  Collection issues detected - search may not work correctly{Style.RESET_ALL}")
    
    # Check view configuration
    view_ok = check_view_configuration(db)
    if not view_ok:
        print(f"{Fore.YELLOW}⚠️  View configuration issues detected - search may not work correctly{Style.RESET_ALL}")
    
    # Test embedding generation
    embedding_ok = test_embedding_generation()
    if not embedding_ok:
        print(f"{Fore.YELLOW}⚠️  Embedding issues detected - semantic search may fail{Style.RESET_ALL}")
    
    # Test search methods
    bm25_ok = test_bm25_search(db)
    semantic_ok = test_semantic_search(db)
    hybrid_ok = test_hybrid_search(db)
    
    # Print summary
    print_section("DIAGNOSTIC SUMMARY", Fore.GREEN)
    print(f"Environment variables: {'' if env_ok else ''}")
    print(f"Database connection: {'' if conn_ok else ''}")
    print(f"Collection status: {'' if collection_ok else '⚠️'}")
    print(f"View configuration: {'' if view_ok else '⚠️'}")
    print(f"Embedding generation: {'' if embedding_ok else '⚠️'}")
    print(f"BM25 search: {'' if bm25_ok else ''}")
    print(f"Semantic search: {'' if semantic_ok else ''}")
    print(f"Hybrid search: {'' if hybrid_ok else ''}")


def print_usage():
    """Print usage information"""
    print(f"{Fore.CYAN}ArangoDB Search API Diagnostic Tool{Style.RESET_ALL}")
    print(f"\nUsage: python -m complexity.arangodb.search_api.debug_search [COMMAND]")
    print(f"\nCommands:")
    print(f"  all         Run all diagnostic tests")
    print(f"  bm25        Test BM25 search functionality")
    print(f"  semantic    Test semantic search functionality")
    print(f"  hybrid      Test hybrid search functionality")
    print(f"  config      Check database and view configuration")
    print(f"  embed       Test embedding generation and dimensions")
    print(f"  collections Verify collection status and document counts")
    print(f"\nExample: python -m complexity.arangodb.search_api.debug_search all")


if __name__ == "__main__":
    # Initialize colorama for cross-platform colored output
    init(autoreset=True)
    
    # Set up logging
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    
    # Parse command line arguments
    args = sys.argv[1:]
    
    if not args or args[0] in ["-h", "--help"]:
        print_usage()
        sys.exit(0)
    
    command = args[0].lower()
    
    # Check environment variables and connect to database
    env_ok = check_environment_variables()
    if not env_ok:
        print(f"{Fore.YELLOW}⚠️  Fix environment variables before continuing{Style.RESET_ALL}")
        sys.exit(1)
    
    # Connect to database for most commands
    if command not in ["embed", "help"]:
        db, conn_ok = check_database_connection()
        if not conn_ok or db is None:
            print(f"{Fore.RED} Cannot continue without database connection{Style.RESET_ALL}")
            sys.exit(1)
    
    # Execute the requested command
    if command == "all":
        run_all_tests()
    elif command == "bm25":
        test_bm25_search(db)
    elif command == "semantic":
        test_semantic_search(db)
    elif command == "hybrid":
        test_hybrid_search(db)
    elif command == "config":
        check_view_configuration(db)
    elif command == "embed":
        test_embedding_generation()
    elif command == "collections":
        check_collection_status(db)
    else:
        print(f"{Fore.RED}Unknown command: {command}{Style.RESET_ALL}")
        print_usage()
        sys.exit(1)
    
    sys.exit(0)