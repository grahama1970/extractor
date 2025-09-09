"""
Module: initialize_litellm_cache.py
Description: Model Context Protocol (MCP) integration

External Dependencies:
- litellm: https://docs.litellm.ai/
- loguru: https://loguru.readthedocs.io/

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
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
from loguru import logger
# load_env_file() # Removed - Docker Compose handles .env loading via env_file


def initialize_litellm_cache() -> None:
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", 6379))
    redis_password = os.getenv("REDIS_PASSWORD", None) # Assuming password might be needed

    try:
        logger.debug(f"Starting LiteLLM cache initialization (Redis target: {redis_host}:{redis_port})...")

        # Test Redis connection before enabling caching
        logger.debug("Testing Redis connection...")
        test_redis = redis.Redis(
            host=redis_host, port=redis_port, password=redis_password, socket_timeout=2, decode_responses=True # Added decode_responses for easier debugging if needed
        )
        if not test_redis.ping():
            raise ConnectionError(f"Redis is not responding at {redis_host}:{redis_port}.")

        # Verify Redis is empty or log existing keys
        keys = test_redis.keys("*")
        if keys:
            logger.debug(f"Existing Redis keys: {keys}")
        else:
            logger.debug("Redis cache is empty")

        # Set up LiteLLM cache with debug logging
        logger.debug("Configuring LiteLLM Redis cache...")
        litellm.cache = litellm.Cache(
            type="redis",
            host=redis_host,
            port=redis_port,
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
        litellm.cache = litellm.Cache(type="local")
        litellm.enable_cache()
        logger.debug("In-memory cache enabled")


def test_litellm_cache():
    """Test the LiteLLM cache functionality with a sample completion call"""
    initialize_litellm_cache()

    try:
        # Test the cache with a simple completion call
        test_messages = [
            {"role": "user", "content": "What is the capital of France?"}
        ]  # Make sure it's >1024 tokens'
        logger.info("Testing cache with completion call...")

        # First call should miss cache
        response1 = litellm.completion(
            model="vertex_ai/gemini-2.5-flash",
            messages=test_messages,
            cache={"no-cache": False},
        )
        logger.info(f"First call usage: {response1.usage}")
        if m := response1._hidden_params.get("cache_hit"):
            logger.info(f"Response 1: Cache hit: {m}")

        # Second call should hit cache
        response2 = litellm.completion(
            model="vertex_ai/gemini-2.5-flash",
            messages=test_messages,
            cache={"no-cache": False},
        )
        logger.info(f"Second call usage: {response2.usage}")
        if m := response2._hidden_params.get("cache_hit"):
            logger.info(f"Response 2: Cache hit: {m}")

    except Exception as e:
        logger.error(f"Cache test failed with error: {e}")
        raise


if __name__ == "__main__":
    test_litellm_cache()