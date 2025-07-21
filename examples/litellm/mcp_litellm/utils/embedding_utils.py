"""
Module: embedding_utils.py
Description: Utility functions and helper methods

External Dependencies:
- openai: https://platform.openai.com/docs/

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

import os
import time
from typing import List, Dict, Union, Any, Optional
from functools import lru_cache
import asyncio
import warnings

# Use standard library logging
import logging

# Import OpenAI client
from openai import OpenAI, AsyncOpenAI, APIError, RateLimitError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Setup logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- OpenAI Configuration ---
# Default model, can be overridden by environment variable
DEFAULT_OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
# API key is expected to be set as an environment variable OPENAI_API_KEY
# The OpenAI client automatically picks it up.

# --- OpenAI Client Initialization ---
# Use LRU cache to avoid re-creating the client unnecessarily
@lru_cache(maxsize=1)
def get_openai_client() -> OpenAI:
    """Get or lazily initialize the synchronous OpenAI client."""
    logger.info("Initializing synchronous OpenAI client.")
    try:
        client = OpenAI()
        # Perform a simple test call to ensure the client is configured correctly
        # client.models.list() # This might be too slow/costly for initialization
        return client
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI client: {e}", exc_info=True)
        raise

@lru_cache(maxsize=1)
def get_async_openai_client() -> AsyncOpenAI:
    """Get or lazily initialize the asynchronous OpenAI client."""
    logger.info("Initializing asynchronous OpenAI client.")
    try:
        client = AsyncOpenAI()
        # Consider adding a lightweight check if necessary
        return client
    except Exception as e:
        logger.error(f"Failed to initialize AsyncOpenAI client: {e}", exc_info=True)
        raise

# --- Embedding Generation ---

# Define retry mechanism for API calls
retry_decorator = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((APIError, RateLimitError, asyncio.TimeoutError)),
    reraise=True,
)

@retry_decorator
async def create_embedding_with_openai(
    text: str,
    model: str = DEFAULT_OPENAI_EMBEDDING_MODEL,
    client: Optional[AsyncOpenAI] = None,
    **kwargs: Any # Allow passing extra arguments like dimensions if needed
) -> Dict[str, Union[List[float], Dict[str, Any]]]:
    """
    Generate an embedding using the OpenAI API (asynchronously).

    Args:
        text: The text content to embed.
        model: The OpenAI embedding model to use.
        client: An optional pre-initialized AsyncOpenAI client.
        **kwargs: Additional arguments for the OpenAI API call (e.g., dimensions).

    Returns:
        A dictionary containing the embedding vector and metadata.
    """
    if not text or not isinstance(text, str):
        raise ValueError("Input text must be a non-empty string.")

    aclient = client or get_async_openai_client()
    start_time = time.perf_counter()

    try:
        logger.debug(f"Requesting OpenAI embedding for text (length: {len(text)}) using model: {model}")
        response = await aclient.embeddings.create(
            input=[text], # API expects a list of strings
            model=model,
            **kwargs
        )
        end_time = time.perf_counter()
        duration = end_time - start_time

        if response.data and len(response.data) > 0:
            embedding_data = response.data[0]
            embedding = embedding_data.embedding
            usage = response.usage

            logger.debug(f"Successfully generated embedding. Duration: {duration:.4f}s. Usage: {usage.total_tokens} tokens.")

            metadata = {
                "embedding_model": model,
                "provider": "openai",
                "duration_seconds": duration,
                "usage": {
                    "prompt_tokens": usage.prompt_tokens,
                    "total_tokens": usage.total_tokens,
                },
                "dimensions": len(embedding),
                # Add any extra metadata returned or needed
            }
            if hasattr(embedding_data, 'object'):
                 metadata['object_type'] = embedding_data.object
            if hasattr(embedding_data, 'index'):
                 metadata['index'] = embedding_data.index


            return {"embedding": embedding, "metadata": metadata}
        else:
            logger.error("OpenAI API returned empty data for embedding request.")
            raise ValueError("OpenAI API returned no embedding data.")

    except (APIError, RateLimitError) as e:
        logger.error(f"OpenAI API error during embedding generation: {e}", exc_info=True)
        raise # Re-raise for tenacity to handle retries
    except Exception as e:
        logger.error(f"Unexpected error during OpenAI embedding generation: {e}", exc_info=True)
        raise # Re-raise other unexpected errors


# --- Example Usage ---
async def main():
    """Example usage of the embedding function."""
    test_text = "This is a test sentence for OpenAI embedding."
    print(f"Generating embedding for: '{test_text}' using model {DEFAULT_OPENAI_EMBEDDING_MODEL}")

    try:
        # Ensure OPENAI_API_KEY is set in your environment variables
        if not os.getenv("OPENAI_API_KEY"):
            print("\nWARNING: OPENAI_API_KEY environment variable not set.")
            print("Please set it to run the example.")
            return

        result_dict = await create_embedding_with_openai(test_text)

        print("\n--- OpenAI Embedding Result ---")
        if result_dict and "embedding" in result_dict:
            print(f"Embedding dimension: {len(result_dict['embedding'])}")
            # print(f"Embedding vector (first 10 dims): {result_dict['embedding'][:10]}...") # Uncomment to view part of the vector
        else:
            print("Embedding generation failed or returned empty result.")

        if result_dict and "metadata" in result_dict:
            print("Metadata:")
            for key, value in result_dict["metadata"].items():
                print(f"  {key}: {value}")

    except Exception as e:
        print(f"\nAn error occurred during the example run: {e}")

if __name__ == "__main__":
    # To run this example directly:
    # 1. Make sure you have an OPENAI_API_KEY environment variable set.
    # 2. Run `python -m mcp_litellm.utils.embedding_utils` from the project root directory.
    asyncio.run(main())
