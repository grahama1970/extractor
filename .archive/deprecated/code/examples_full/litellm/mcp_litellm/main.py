"""
Module: main.py
Description: Model Context Protocol (MCP) integration

External Dependencies:
- fastapi: https://fastapi.tiangolo.com/
- loguru: https://loguru.readthedocs.io/
- arango: https://docs.python-arango.com/
- litellm: https://docs.litellm.ai/

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

# Description: Main FastAPI application for the MCP LiteLLM Service.
#              Handles incoming batch requests, processes them using the engine,
#              and returns the results. Includes startup logic for cache initialization.
# Core Lib Links:
# - FastAPI: https://fastapi.tiangolo.com/
# - Uvicorn: https://www.uvicorn.org/
# Sample I/O: N/A (This is the main application entry point)

import yaml
import os
from typing import List, Dict, Any
from fastapi import FastAPI, HTTPException, Depends, Request, Response
from loguru import logger
from fastapi_mcp import add_mcp_server
from fastapi.middleware.cors import CORSMiddleware
from arango import ArangoClient
# import uvicorn # Not directly used, but related for running the app

from .models import (
    BatchRequest,
    BatchResponse,
    LessonQueryRequest,
    LessonQueryResponse,
    LessonResultItem
)
from .engine import process_batch
from .initialize_litellm_cache import initialize_litellm_cache
# Assuming arango_utils is correctly structured for relative import
from .utils.db.arango_utils import connect_to_arango_client, query_lessons_by_similarity
# --- Configuration Loading ---
# Load ArangoDB config - adjust path as necessary
# TODO: Use a more robust config loading mechanism (e.g., Pydantic settings)
CONFIG_PATH = "config.yaml" # Expect config in the working directory (/app)
ARANGO_CONFIG = {}
try:
    with open(CONFIG_PATH, 'r') as f:
        full_config = yaml.safe_load(f)
        ARANGO_CONFIG = full_config.get('database', {})
        if not ARANGO_CONFIG:
            logger.warning(f"ArangoDB configuration not found or empty in {CONFIG_PATH}")
        else:
            # Substitute environment variables in ARANGO_CONFIG
            for key, value in ARANGO_CONFIG.items():
                if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                    env_var = value[2:-1]
                    env_value = os.environ.get(env_var)
                    if env_value is not None:
                        ARANGO_CONFIG[key] = env_value
                    else:
                        logger.warning(f"Environment variable '{env_var}' not set for database config key '{key}'")
except FileNotFoundError:
    logger.error(f"Configuration file not found at {CONFIG_PATH}")
except yaml.YAMLError as e:
    logger.error(f"Error parsing configuration file {CONFIG_PATH}: {e}")


# --- Dependency for ArangoDB Connection ---
def get_db() -> ArangoClient:
    """
    Dependency function to get an ArangoDB database connection.
    Handles connection errors.
    """
    if not ARANGO_CONFIG:
        logger.error("ArangoDB connection cannot be established: Configuration missing.")
        raise HTTPException(status_code=500, detail="Database configuration error.")
    try:
        # Assuming connect_to_arango_client returns the db object directly
        db = connect_to_arango_client(ARANGO_CONFIG)
        # Optional: Add a check to ensure the connection is live
        # db.version()
        return db
    except Exception as e:
        logger.error(f"Failed to connect to ArangoDB: {e}")
        raise HTTPException(status_code=503, detail=f"Could not connect to the database: {e}")


# --- FastAPI Application Instance ---
app = FastAPI(
    title="MCP LiteLLM Service",
    version="0.1.0",
    description="A service to process batch requests for LiteLLM calls via MCP and query lessons learned.",
)

# Add the MCP server endpoint, automatically discovering FastAPI routes as tools
add_mcp_server(
    app=app,
    mount_path="/mcp", # Standard path for MCP over HTTP/SSE
    name="mcp-litellm-batch-fastapi", # Server name for MCP discovery
    # Automatically describe responses based on FastAPI response_model
    describe_all_responses=True
)

# Add CORS middleware to allow connections from any origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://your-known-frontend.com"], # TODO: restrict to known client origins before production
    allow_credentials=True,
    allow_methods=["*"], # Allows all methods
    allow_headers=["*"], # Allows all headers
)
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response


@app.on_event("startup")
async def startup_event():
    """
    Initializes the LiteLLM cache upon application startup.
    """
    logger.info("Initializing LiteLLM cache on startup...")
    # Assuming initialize_litellm_cache is synchronous based on example/plan
    # If it were async, it would need an 'await'
    initialize_litellm_cache()
    logger.info("Cache initialization complete.")

@app.post("/ask", response_model=BatchResponse, summary="Process a batch of LLM questions")
async def ask_batch(request: BatchRequest):
    """
    Accepts a batch of questions, processes them concurrently or sequentially
    based on dependencies using the engine, and returns the results.

    Handles potential errors during processing and returns appropriate HTTP responses.
    """
    logger.info(f"Received batch request with {len(request.tasks)} tasks.")
    try:
        # The core logic is delegated to the process_batch function
        response = await process_batch(request)
        logger.info(f"Successfully processed batch request.")
        return response
    except HTTPException as http_exc:
        # Re-raise HTTPExceptions directly
        logger.warning(f"HTTP Exception during processing: {http_exc.detail}")
        raise http_exc
    except Exception as e:
        # Catch any other unexpected errors
        logger.exception(f"Fatal error processing batch request: {e}")
        # Log full error, return generic 500 error to the client
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.get("/", summary="Health check")
async def read_root():
    """
    Provides a basic health check endpoint to confirm the service is running.
    """
    logger.debug("Root health check endpoint accessed.")
    return {"message": "MCP LiteLLM Service is running"}


# --- Lessons Learned Query Endpoint ---

@app.post("/query_lessons",
          response_model=LessonQueryResponse,
          summary="Query Lessons Learned by Semantic Similarity",
          tags=["Lessons Learned"])
async def query_lessons(
    request: LessonQueryRequest,
    db: ArangoClient = Depends(get_db)
):
    """
    Accepts a natural language query and returns the top_k most semantically
    similar lessons learned from the ArangoDB database.

    Requires a vector index on the 'lesson_embedding' field in the
    'lessons_learned' collection.
    """
    logger.info(f"Received lessons query: '{request.query_text[:50]}...', top_k={request.top_k}")
    try:
        # Call the utility function to perform the similarity search
        # This function handles embedding the query text and querying ArangoDB
        similar_lessons_raw: List[Dict[str, Any]] = query_lessons_by_similarity(
            db=db,
            query_text=request.query_text,
            top_n=request.top_k
        )

        # Process results into the response model format
        results = []
        for item in similar_lessons_raw:
            lesson_doc = item.get('document', {})
            score = item.get('similarity_score', 0.0)
            lesson_id = lesson_doc.get('_id', 'N/A')
            lesson_key = lesson_doc.get('_key', 'N/A')

            results.append(LessonResultItem(
                id=lesson_id,
                key=lesson_key,
                score=score,
                lesson=lesson_doc # Include the full lesson document
            ))

        logger.info(f"Returning {len(results)} similar lessons for query.")
        return LessonQueryResponse(lessons=results)

    except HTTPException as http_exc:
        # Re-raise HTTPExceptions (e.g., from get_db)
        logger.warning(f"HTTP Exception during lessons query: {http_exc.detail}")
        raise http_exc
    except Exception as e:
        # Catch any other unexpected errors during query or processing
        logger.exception(f"Error processing lessons query: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


# Note: To run this application locally, use:
# uvicorn mcp_litellm.main:app --reload --port 8000