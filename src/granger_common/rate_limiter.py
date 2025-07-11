#!/usr/bin/env python3
"""
Module: rate_limiter.py
Description: Standardized rate limiter for all Granger modules to use with external APIs

This module provides a consistent rate limiting implementation that all Granger
projects should use when making external API calls.

External Dependencies:
- asyncio: Built-in async support
- time: Built-in time tracking
- threading: Built-in thread safety
- collections: Built-in deque for sliding window

Sample Input:
>>> limiter = RateLimiter(calls_per_second=3, burst_size=10)
>>> limiter.acquire()  # Returns immediately if under limit
>>> limiter.acquire()  # May block if rate limit reached

Expected Output:
>>> True  # When rate limit allows the call
>>> # Blocks until rate limit allows, then returns True

Example Usage:
>>> from granger_common.rate_limiter import RateLimiter
>>> 
>>> # Create limiter for external API
>>> api_limiter = RateLimiter(
...     calls_per_second=3,
...     burst_size=10,
...     name="NVD_API"
... )
>>> 
>>> # Use in sync code
>>> if api_limiter.acquire():
...     response = requests.get(api_url)
>>> 
>>> # Use in async code
>>> if await api_limiter.acquire_async():
...     response = await httpx.get(api_url)
"""

import asyncio
import time
import threading
from collections import deque
from typing import Optional, Union
from loguru import logger


class RateLimiter:
    """
    Thread-safe rate limiter using sliding window algorithm.
    
    This implementation ensures consistent rate limiting across all Granger modules.
    """
    
    def __init__(
        self,
        calls_per_second: float = 3.0,
        burst_size: Optional[int] = None,
        name: str = "default",
        retry_on_limit: bool = True,
        max_retry_wait: float = 60.0
    ):
        """
        Initialize rate limiter.
        
        Args:
            calls_per_second: Maximum sustained rate of calls
            burst_size: Maximum burst capacity (defaults to 3x calls_per_second)
            name: Name for logging purposes
            retry_on_limit: Whether to wait and retry when rate limited
            max_retry_wait: Maximum time to wait for retry (seconds)
        """
        self.calls_per_second = calls_per_second
        self.burst_size = burst_size or int(calls_per_second * 3)
        self.name = name
        self.retry_on_limit = retry_on_limit
        self.max_retry_wait = max_retry_wait
        
        # Calculate minimum interval between calls
        self.min_interval = 1.0 / calls_per_second
        
        # Thread-safe call history
        self._call_times = deque(maxlen=self.burst_size)
        self._lock = threading.Lock()
        
        logger.info(
            f"RateLimiter '{name}' initialized: "
            f"{calls_per_second} calls/sec, burst={self.burst_size}"
        )
    
    def _can_proceed(self) -> tuple[bool, float]:
        """
        Check if we can proceed with a call.
        
        Returns:
            Tuple of (can_proceed, wait_time_if_not)
        """
        now = time.time()
        
        with self._lock:
            # Remove old calls outside the window
            cutoff = now - (self.burst_size / self.calls_per_second)
            while self._call_times and self._call_times[0] < cutoff:
                self._call_times.popleft()
            
            # Check if we're under the limit
            if len(self._call_times) < self.burst_size:
                # Check minimum interval since last call
                if self._call_times:
                    time_since_last = now - self._call_times[-1]
                    if time_since_last < self.min_interval:
                        wait_time = self.min_interval - time_since_last
                        return False, wait_time
                
                return True, 0.0
            
            # Calculate when the oldest call will expire
            wait_time = self._call_times[0] + (self.burst_size / self.calls_per_second) - now
            return False, wait_time
    
    def acquire(self, timeout: Optional[float] = None) -> bool:
        """
        Acquire permission to make a call (synchronous).
        
        Args:
            timeout: Maximum time to wait (None for retry_on_limit behavior)
            
        Returns:
            True if acquired, False if timed out
        """
        start_time = time.time()
        timeout = timeout or (self.max_retry_wait if self.retry_on_limit else 0)
        
        while True:
            can_proceed, wait_time = self._can_proceed()
            
            if can_proceed:
                with self._lock:
                    self._call_times.append(time.time())
                logger.debug(f"RateLimiter '{self.name}': Call acquired")
                return True
            
            # Check timeout
            elapsed = time.time() - start_time
            if elapsed + wait_time > timeout:
                logger.warning(
                    f"RateLimiter '{self.name}': "
                    f"Timeout after {elapsed:.1f}s (would need {wait_time:.1f}s more)"
                )
                return False
            
            # Wait before retry
            logger.debug(f"RateLimiter '{self.name}': Waiting {wait_time:.3f}s")
            time.sleep(wait_time)
    
    async def acquire_async(self, timeout: Optional[float] = None) -> bool:
        """
        Acquire permission to make a call (asynchronous).
        
        Args:
            timeout: Maximum time to wait (None for retry_on_limit behavior)
            
        Returns:
            True if acquired, False if timed out
        """
        start_time = time.time()
        timeout = timeout or (self.max_retry_wait if self.retry_on_limit else 0)
        
        while True:
            can_proceed, wait_time = self._can_proceed()
            
            if can_proceed:
                with self._lock:
                    self._call_times.append(time.time())
                logger.debug(f"RateLimiter '{self.name}': Call acquired (async)")
                return True
            
            # Check timeout
            elapsed = time.time() - start_time
            if elapsed + wait_time > timeout:
                logger.warning(
                    f"RateLimiter '{self.name}': "
                    f"Timeout after {elapsed:.1f}s (would need {wait_time:.1f}s more)"
                )
                return False
            
            # Wait before retry
            logger.debug(f"RateLimiter '{self.name}': Waiting {wait_time:.3f}s (async)")
            await asyncio.sleep(wait_time)
    
    def get_stats(self) -> dict:
        """Get current rate limiter statistics."""
        with self._lock:
            current_calls = len(self._call_times)
            
        return {
            "name": self.name,
            "calls_per_second": self.calls_per_second,
            "burst_size": self.burst_size,
            "current_calls": current_calls,
            "available_capacity": self.burst_size - current_calls
        }


# Pre-configured rate limiters for common APIs
RATE_LIMITERS = {
    "nvd": RateLimiter(
        calls_per_second=3.0,  # NVD allows ~3 requests/sec
        burst_size=10,
        name="NVD_API"
    ),
    "arxiv": RateLimiter(
        calls_per_second=3.0,  # ArXiv recommends 3 requests/sec
        burst_size=10,
        name="ArXiv_API"
    ),
    "youtube": RateLimiter(
        calls_per_second=10.0,  # YouTube API has higher limits
        burst_size=50,
        name="YouTube_API"
    ),
    "github": RateLimiter(
        calls_per_second=5.0,  # GitHub API allows 5 requests/sec for authenticated
        burst_size=20,
        name="GitHub_API"
    )
}


def get_rate_limiter(api_name: str) -> RateLimiter:
    """
    Get a pre-configured rate limiter for a specific API.
    
    Args:
        api_name: Name of the API (nvd, arxiv, youtube, github)
        
    Returns:
        Configured RateLimiter instance
    """
    if api_name not in RATE_LIMITERS:
        logger.warning(f"No pre-configured rate limiter for '{api_name}', using default")
        return RateLimiter(name=api_name)
    
    return RATE_LIMITERS[api_name]


if __name__ == "__main__":
    # Validation tests
    print("🧪 Testing RateLimiter...")
    
    # Test synchronous rate limiting
    limiter = RateLimiter(calls_per_second=2, burst_size=4, name="test")
    
    print("\nTest 1: Burst capacity")
    for i in range(6):
        start = time.time()
        acquired = limiter.acquire(timeout=5.0)
        elapsed = time.time() - start
        print(f"  Call {i+1}: {'✅' if acquired else '❌'} (waited {elapsed:.3f}s)")
    
    print("\nTest 2: Rate limiter stats")
    print(f"  Stats: {limiter.get_stats()}")
    
    # Test async rate limiting
    async def test_async():
        print("\nTest 3: Async rate limiting")
        async_limiter = RateLimiter(calls_per_second=5, name="async_test")
        
        async def make_call(i):
            start = time.time()
            acquired = await async_limiter.acquire_async(timeout=2.0)
            elapsed = time.time() - start
            print(f"  Async call {i}: {'✅' if acquired else '❌'} (waited {elapsed:.3f}s)")
        
        await asyncio.gather(*[make_call(i) for i in range(10)])
    
    asyncio.run(test_async())
    
    print("\n✅ RateLimiter validation complete!")