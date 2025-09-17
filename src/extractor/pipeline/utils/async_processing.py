"""
Shared async processing utilities with tenacity retry and semaphore rate limiting.

This implements the standard design pattern for concurrent LLM processing:
- Semaphore for rate limiting
- Tenacity retry for resilience
- tqdm progress bars
- asyncio.gather for concurrent execution
"""

import asyncio
import os
from typing import List, Dict, Any, Callable, Optional
from loguru import logger
from tqdm.asyncio import tqdm
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential_jitter,
    retry_if_exception_type,
)
import litellm

# Global semaphore for controlling concurrent LLM calls
LLM_SEMAPHORE = asyncio.Semaphore(int(os.getenv("MAX_CONCURRENT_LLM_CALLS", "3")))


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=1, max=10),
    retry=retry_if_exception_type(
        (
            litellm.exceptions.Timeout,
            litellm.exceptions.RateLimitError,
        )
    ),
)
async def call_llm_with_retry(**kwargs):
    """Call LiteLLM with tenacity retry pattern."""
    return litellm.completion(**kwargs)


async def process_with_semaphore(process_func: Callable, item: Any, *args, **kwargs) -> Any:
    """Process a single item with semaphore control."""
    async with LLM_SEMAPHORE:
        return await process_func(item, *args, **kwargs)


async def process_items_concurrently(
    items: List[Any], process_func: Callable, description: str = "Processing items", *args, **kwargs
) -> List[Any]:
    """
    Process items concurrently with progress bar and error handling.

    Args:
        items: List of items to process
        process_func: Async function to process each item
        description: Description for progress bar
        *args, **kwargs: Additional arguments passed to process_func

    Returns:
        List of results (None for failed items)
    """
    if not items:
        return []

    logger.info(f"Processing {len(items)} items concurrently")

    # Create tasks for all items
    tasks = [process_with_semaphore(process_func, item, *args, **kwargs) for item in items]

    # Process concurrently with progress bar
    results = []
    with tqdm(total=len(tasks), desc=description) as pbar:
        # Use gather for concurrent execution
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(batch_results):
            if isinstance(result, Exception):
                logger.error(f"Failed to process item {i}: {result}")
                results.append(None)
            else:
                results.append(result)
            pbar.update(1)

    successful = len([r for r in results if r is not None])
    logger.info(f"Successfully processed {successful}/{len(items)} items")

    return results


async def process_items_in_batches(
    items: List[Any],
    process_func: Callable,
    batch_size: int = 10,
    description: str = "Processing batches",
    *args,
    **kwargs,
) -> List[Any]:
    """
    Process items in batches with progress tracking.

    Args:
        items: List of items to process
        process_func: Async function to process each item
        batch_size: Number of items per batch
        description: Description for progress bar
        *args, **kwargs: Additional arguments passed to process_func

    Returns:
        List of all results
    """
    if not items:
        return []

    all_results = []

    with tqdm(total=len(items), desc=description) as pbar:
        for i in range(0, len(items), batch_size):
            batch = items[i : i + batch_size]

            # Process batch concurrently
            tasks = [process_with_semaphore(process_func, item, *args, **kwargs) for item in batch]

            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"Batch processing failed: {result}")
                    all_results.append(None)
                else:
                    all_results.append(result)
                pbar.update(1)

            # Optional: Add delay between batches for rate limiting
            if i + batch_size < len(items):
                await asyncio.sleep(0.1)

    return all_results
