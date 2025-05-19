"""
Cache utilities for table extraction.

This module provides a caching mechanism for table extraction results to improve
performance when processing multiple documents or when reprocessing the same document.

References:
- Python documentation on functools.lru_cache: https://docs.python.org/3/library/functools.html#functools.lru_cache

Sample input:
- Functions to cache
- Cache parameters

Expected output:
- Cached function results for improved performance
"""

import functools
import hashlib
import json
import os
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from loguru import logger


class TableExtractionCache:
    """
    Cache for table extraction results.
    
    This class provides a disk-based cache for table extraction results
    to improve performance when processing multiple documents or when
    reprocessing the same document.
    """
    
    def __init__(self, cache_dir: Optional[str] = None, max_size: int = 100):
        """
        Initialize the cache.
        
        Args:
            cache_dir: Directory to store cache files. If None, a temporary directory is used.
            max_size: Maximum number of cache entries to keep.
        """
        self.cache_dir = cache_dir or os.path.join(os.path.expanduser("~"), ".marker", "cache", "tables")
        self.max_size = max_size
        
        # Create cache directory if it doesn't exist
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Load cache index
        self.cache_index = self._load_cache_index()
    
    def _load_cache_index(self) -> Dict[str, str]:
        """
        Load the cache index from disk.
        
        Returns:
            Dict mapping cache keys to cache file paths.
        """
        index_path = os.path.join(self.cache_dir, "index.json")
        if os.path.exists(index_path):
            try:
                with open(index_path, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Error loading cache index: {str(e)}")
        
        return {}
    
    def _save_cache_index(self) -> None:
        """Save the cache index to disk."""
        index_path = os.path.join(self.cache_dir, "index.json")
        try:
            with open(index_path, "w") as f:
                json.dump(self.cache_index, f)
        except IOError as e:
            logger.error(f"Error saving cache index: {str(e)}")
    
    def _compute_key(self, *args, **kwargs) -> str:
        """
        Compute a cache key based on the function arguments.
        
        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments
            
        Returns:
            Cache key as a string
        """
        # Special handling for file paths
        if args and isinstance(args[0], str) and os.path.exists(args[0]):
            # For file paths, use the file modification time in the key
            filepath = args[0]
            mtime = os.path.getmtime(filepath)
            args_to_hash = [mtime] + list(args[1:])
        else:
            args_to_hash = args
        
        # Convert arguments to JSON and compute hash
        arg_hash = hashlib.md5(
            json.dumps((args_to_hash, sorted(kwargs.items())), sort_keys=True).encode()
        ).hexdigest()
        
        return arg_hash
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get an item from the cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached item or None if not found
        """
        if key not in self.cache_index:
            return None
        
        cache_path = os.path.join(self.cache_dir, self.cache_index[key])
        if not os.path.exists(cache_path):
            # Remove from index if file doesn't exist
            del self.cache_index[key]
            self._save_cache_index()
            return None
        
        try:
            with open(cache_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error loading cache entry: {str(e)}")
            return None
    
    def set(self, key: str, value: Any) -> None:
        """
        Set an item in the cache.
        
        Args:
            key: Cache key
            value: Value to cache
        """
        # Generate a filename for the cache entry
        filename = f"{key}.json"
        cache_path = os.path.join(self.cache_dir, filename)
        
        try:
            # Save the cache entry
            with open(cache_path, "w") as f:
                json.dump(value, f)
            
            # Update the index
            self.cache_index[key] = filename
            self._save_cache_index()
            
            # Clean up old entries if we've exceeded the max size
            if len(self.cache_index) > self.max_size:
                self._clean_cache()
        except IOError as e:
            logger.error(f"Error saving cache entry: {str(e)}")
    
    def _clean_cache(self) -> None:
        """Clean up old cache entries."""
        # Get a list of cache entries sorted by modification time
        entries = []
        for key, filename in self.cache_index.items():
            cache_path = os.path.join(self.cache_dir, filename)
            if os.path.exists(cache_path):
                mtime = os.path.getmtime(cache_path)
                entries.append((key, mtime))
        
        # Sort by modification time (oldest first)
        entries.sort(key=lambda x: x[1])
        
        # Remove oldest entries until we're under the max size
        entries_to_remove = len(entries) - self.max_size
        if entries_to_remove > 0:
            for i in range(entries_to_remove):
                key, _ = entries[i]
                filename = self.cache_index[key]
                cache_path = os.path.join(self.cache_dir, filename)
                
                try:
                    os.remove(cache_path)
                except IOError:
                    pass
                
                del self.cache_index[key]
            
            # Save the updated index
            self._save_cache_index()
    
    def clear(self) -> None:
        """Clear all cache entries."""
        for filename in self.cache_index.values():
            cache_path = os.path.join(self.cache_dir, filename)
            try:
                if os.path.exists(cache_path):
                    os.remove(cache_path)
            except IOError:
                pass
        
        self.cache_index = {}
        self._save_cache_index()


# Global cache instance
global _global_cache
_global_cache = None

def get_cache() -> TableExtractionCache:
    """
    Get the global cache instance.
    
    Returns:
        TableExtractionCache: The global cache instance
    """
    global _global_cache
    if _global_cache is None:
        _global_cache = TableExtractionCache()
    return _global_cache


def cached(func: Callable) -> Callable:
    """
    Decorator to cache function results.
    
    Args:
        func: Function to cache
        
    Returns:
        Decorated function
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Skip caching if cache_enabled is False
        cache_enabled = kwargs.pop("cache_enabled", True)
        if not cache_enabled:
            return func(*args, **kwargs)
        
        # Get the cache
        cache = get_cache()
        
        # Compute the cache key
        key = cache._compute_key(func.__name__, *args, **kwargs)
        
        # Check if we have a cached result
        cached_result = cache.get(key)
        if cached_result is not None:
            logger.debug(f"Cache hit for {func.__name__}")
            return cached_result
        
        # Call the function
        result = func(*args, **kwargs)
        
        # Cache the result
        try:
            # Check if the result is JSON serializable
            json.dumps(result)
            cache.set(key, result)
        except (TypeError, OverflowError):
            # If not JSON serializable, don't cache
            logger.warning(f"Result of {func.__name__} is not JSON serializable, skipping cache")
        
        return result
    
    return wrapper


if __name__ == "__main__":
    """
    Validation function to test the table cache.
    """
    import sys
    import tempfile
    import time
    
    # List to track all validation failures
    all_validation_failures = []
    total_tests = 0
    
    # Test 1: Basic caching
    total_tests += 1
    try:
        # Create a temporary cache directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a cache
            cache = TableExtractionCache(cache_dir=temp_dir)
            
            # Set a value
            cache.set("test", {"value": 42})
            
            # Get the value
            result = cache.get("test")
            
            # Check that we got the expected value
            if result is None:
                all_validation_failures.append("Cache get returned None")
            elif result.get("value") != 42:
                all_validation_failures.append(f"Cache get returned unexpected value: {result}")
            
            # Check that the index was updated
            if "test" not in cache.cache_index:
                all_validation_failures.append("Cache index was not updated")
    except Exception as e:
        all_validation_failures.append(f"Error in test 1: {str(e)}")
    
    # Test 2: Cache decorator
    total_tests += 1
    try:
        # Create a temporary cache directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a cache
            cache = TableExtractionCache(cache_dir=temp_dir)
            
            # Set the global cache
            _global_cache = cache
            
            # Create a reference for the call count
            call_count_ref = [0]
            
            @cached
            def test_function(a, b):
                call_count_ref[0] += 1
                return {"sum": a + b}
            
            # Call the function twice with the same arguments
            result1 = test_function(1, 2)
            result2 = test_function(1, 2)
            
            # Check that the function was only called once
            if call_count_ref[0] != 1:
                all_validation_failures.append(f"Function was called {call_count_ref[0]} times, expected 1")
            
            # Check that we got the expected results
            if result1.get("sum") != 3:
                all_validation_failures.append(f"First call returned unexpected value: {result1}")
            
            if result2.get("sum") != 3:
                all_validation_failures.append(f"Second call returned unexpected value: {result2}")
            
            # Call the function with different arguments
            result3 = test_function(3, 4)
            
            # Check that the function was called again
            if call_count_ref[0] != 2:
                all_validation_failures.append(f"Function was called {call_count_ref[0]} times, expected 2")
            
            # Check that we got the expected result
            if result3.get("sum") != 7:
                all_validation_failures.append(f"Third call returned unexpected value: {result3}")
    except Exception as e:
        all_validation_failures.append(f"Error in test 2: {str(e)}")
    
    # Test 3: Cache cleaning
    total_tests += 1
    try:
        # Create a temporary cache directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a cache with a small max size
            cache = TableExtractionCache(cache_dir=temp_dir, max_size=2)
            
            # Set multiple values
            cache.set("test1", {"value": 1})
            time.sleep(0.1)  # Ensure different modification times
            cache.set("test2", {"value": 2})
            time.sleep(0.1)  # Ensure different modification times
            cache.set("test3", {"value": 3})
            
            # Check that the oldest entry was removed
            if "test1" in cache.cache_index:
                all_validation_failures.append("Cache cleaning failed: oldest entry was not removed")
            
            # Check that the newer entries are still there
            if "test2" not in cache.cache_index:
                all_validation_failures.append("Cache cleaning removed too many entries: test2 missing")
            
            if "test3" not in cache.cache_index:
                all_validation_failures.append("Cache cleaning removed too many entries: test3 missing")
    except Exception as e:
        all_validation_failures.append(f"Error in test 3: {str(e)}")
    
    # Final validation result
    if all_validation_failures:
        print(f"❌ VALIDATION FAILED - {len(all_validation_failures)} of {total_tests} tests failed:")
        for failure in all_validation_failures:
            print(f"  - {failure}")
        sys.exit(1)
    else:
        print(f"✅ VALIDATION PASSED - All {total_tests} tests produced expected results")
        print("Table cache is validated and formal tests can now be written")
        sys.exit(0)