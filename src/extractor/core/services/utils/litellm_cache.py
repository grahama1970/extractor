"""
Initializes LiteLLM Caching Configuration.
Module: litellm_cache.py
Description: Functions for litellm cache operations

This module sets up LiteLLM's caching mechanism. It attempts to configure'
Redis as the primary cache backend. If Redis is unavailable or fails connection
tests, it falls back to using LiteLLM's built-in in-memory cache. Includes'
a test function to verify cache functionality.

Relevant Documentation:
- LiteLLM Caching: https://docs.litellm.ai/docs/proxy/caching
- Redis Python Client: https://redis.io/docs/clients/python/
- Project Caching Notes: ../../repo_docs/caching_strategy.md (Placeholder)

Input/Output:
- Input: Environment variables for Redis connection (optional).
- Output: Configures LiteLLM global cache settings. Logs status messages.
- The `test_litellm_cache` function demonstrates usage by making cached calls.
"""

# ==============================================================================
# !!! WARNING - DO NOT MODIFY THIS FILE !!!
# ==============================================================================
# This is a core functionality file that other parts of the system depend on.
# Changing this file (especially its sync/async nature) will break multiple dependent systems.
# Any changes here will cascade into test failures across the codebase.
#
# If you think you need to modify this file:
# 1. DON'T. The synchronous implementation is intentional
# 2. The caching system is working as designed
# 3. Test files should adapt to this implementation, not vice versa
# 4. Consult LESSONS_LEARNED.md about not breaking working code
# ==============================================================================

import litellm
import os
import redis
from dotenv import load_dotenv  # Import dotenv for environment variable loading
# from litellm.caching import Cache, Type  # Import Cache and Type
import sys  # Import sys for exit codes
from loguru import logger
from litellm.caching.caching import (
    Cache as LiteLLMCache,
    LiteLLMCacheType,
)  # Import Cache and Type
from typing import Any  # Import Any for type hint

# Import the utility function from our utils
try:
    from extractor.core.services.utils.log_utils import truncate_large_value
except ImportError:
    logger.warning("Could not import truncate_large_value. Logs might be verbose.")

    # Define a dummy function with compatible signature if import fails
    def truncate_large_value(value: Any, *args: Any, **kwargs: Any) -> Any:
        return value

# load_env_file() # Removed - Docker Compose handles .env loading via env_file
load_dotenv()


def initialize_litellm_cache() -> None:
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", 6379))
    redis_password = os.getenv(
        "REDIS_PASSWORD", None
    )  # Assuming password might be needed

    try:
        logger.debug(
            f"Starting LiteLLM cache initialization (Redis target: {redis_host}:{redis_port})..."
        )

        # Test Redis connection before enabling caching
        logger.debug("Testing Redis connection...")
        test_redis = redis.Redis(
            host=redis_host,
            port=redis_port,
            password=redis_password,
            socket_timeout=2,
            decode_responses=True,  # Added decode_responses for easier debugging if needed
        )
        if not test_redis.ping():
            raise ConnectionError(
                f"Redis is not responding at {redis_host}:{redis_port}."
            )

        # Verify Redis is empty or log existing keys
        keys = test_redis.keys("*")
        if keys:
            # Use the truncate utility for logging keys
            logger.debug(f"Existing Redis keys: {truncate_large_value(keys)}")
        else:
            logger.debug("Redis cache is empty")

        # Set up LiteLLM cache with debug logging
        logger.debug("Configuring LiteLLM Redis cache...")
        litellm.cache = LiteLLMCache(  # Use imported Cache
            type=LiteLLMCacheType.REDIS,  # Use Enum/Type
            host=redis_host,
            port=str(redis_port),  # Ensure port is a string
            password=redis_password,
            supported_call_types=["acompletion", "completion"],
            ttl=60 * 60 * 24 * 2,  # 2 days
        )

        # Enable caching and verify
        logger.debug("Enabling LiteLLM cache...")
        litellm.enable_cache()

        # Set debug logging for LiteLLM
        os.environ["LITELLM_LOG"] = "DEBUG"

        # Verify cache configuration
        logger.debug(
            f"LiteLLM cache config: {litellm.cache.__dict__ if hasattr(litellm.cache, '__dict__') else 'No cache config available'}"
        )
        logger.info(" Redis caching enabled on localhost:6379")

        # Try a test set/get to verify Redis is working
        try:
            test_key = "litellm_cache_test"
            test_redis.set(test_key, "test_value", ex=60)
            result = test_redis.get(test_key)
            logger.debug(f"Redis test write/read successful: {result == 'test_value'}")
            test_redis.delete(test_key)
        except Exception as e:
            logger.warning(f"Redis test write/read failed: {e}")

    except (redis.ConnectionError, redis.TimeoutError) as e:
        logger.warning(
            f"⚠️ Redis connection failed: {e}. Falling back to in-memory caching."
        )
        # Fall back to in-memory caching if Redis is unavailable
        logger.debug("Configuring in-memory cache fallback...")
        litellm.cache = LiteLLMCache(type=LiteLLMCacheType.LOCAL)  # Use Enum/Type
        litellm.enable_cache()
        logger.debug("In-memory cache enabled")


from typing import Tuple, Dict, Optional  # Add Optional


def test_litellm_cache() -> Tuple[bool, Dict[str, Optional[bool]]]:
    """
    Test the LiteLLM cache functionality with a sample completion call.
    Returns a tuple: (overall_success, cache_hit_details)
    """
    initialize_litellm_cache()
    test_success = False
    # Explicitly annotate the dictionary type
    cache_details: Dict[str, Optional[bool]] = {"cache_hit1": None, "cache_hit2": None}

    try:
        # Test the cache with a simple completion call
        test_messages = [
            {
                "role": "user",
                "content": "What is the capital of France? Respond concisely.",
            }
        ]
        logger.info("Testing cache with completion call...")

        # First call - Expect cache miss (cache_hit should be False or None)
        response1 = litellm.completion(
            model="gpt-4o-mini",
            messages=test_messages,
            # Ensure caching is attempted, remove specific cache param unless needed for override
        )
        usage1 = getattr(response1, "usage", "N/A")
        hidden_params1 = getattr(response1, "_hidden_params", {})
        cache_hit1 = hidden_params1.get(
            "cache_hit"
        )  # Could be None if not hit or feature disabled
        cache_details["cache_hit1"] = cache_hit1
        logger.info(f"First call usage: {usage1}")
        logger.info(f"Response 1: Cache hit: {cache_hit1}")
        # Check if first call was NOT a cache hit (allow None or False)
        first_call_missed = cache_hit1 is None or cache_hit1 is False

        # Second call - Expect cache hit (cache_hit should be True)
        response2 = litellm.completion(
            model="gpt-4o-mini",
            messages=test_messages,
            # Ensure caching is attempted
        )
        usage2 = getattr(response2, "usage", "N/A")
        hidden_params2 = getattr(response2, "_hidden_params", {})
        cache_hit2 = hidden_params2.get("cache_hit")
        cache_details["cache_hit2"] = cache_hit2
        logger.info(f"Second call usage: {usage2}")
        logger.info(f"Response 2: Cache hit: {cache_hit2}")
        # Check if second call WAS a cache hit
        second_call_hit = cache_hit2 is True

        # Determine overall test success
        test_success = first_call_missed and second_call_hit

    except Exception as e:
        logger.error(f"Cache test failed during execution: {e}")
        test_success = False  # Ensure failure is recorded

    return test_success, cache_details


if __name__ == "__main__":
    logger.info("--- Running Standalone Validation for initialize_litellm_cache.py ---")

    tests_passed_count = 0
    tests_failed_count = 0
    total_tests = 1

    try:
        test_result, details = test_litellm_cache()

        if test_result:
            tests_passed_count += 1
            logger.success(" Test 'cache_hit_miss': PASSED")
        else:
            tests_failed_count += 1
            logger.error(" Test 'cache_hit_miss': FAILED")
            logger.error(
                f"   Expected first call cache_hit=False/None, second call cache_hit=True."
            )
            logger.error(
                f"   Got: cache_hit1={details.get('cache_hit1')}, cache_hit2={details.get('cache_hit2')}"
            )

    except Exception as e:
        tests_failed_count += 1  # Count exception as failure
        logger.error(
            f" Test 'cache_hit_miss': FAILED due to exception during test execution."
        )
        logger.error(f"   Exception: {e}", exc_info=True)

    # --- Report validation status ---
    print(f"\n--- Test Summary ---")
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {tests_passed_count}")
    print(f"Failed: {tests_failed_count}")

    if tests_failed_count == 0:
        print("\n VALIDATION COMPLETE - All LiteLLM cache tests passed.")
        sys.exit(0)
    else:
        print("\n VALIDATION FAILED - LiteLLM cache test failed.")
        # Error details already logged above
        sys.exit(1)