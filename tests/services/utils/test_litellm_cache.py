"""
Test the LiteLLM cache initialization.
"""

import os
import pytest
import logging
from unittest.mock import patch, MagicMock

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create the directory structure if it doesn't exist
os.makedirs(os.path.dirname(__file__), exist_ok=True)

# Import the module to test
try:
    from marker.services.utils.litellm_cache import initialize_litellm_cache
    from marker.services.utils.log_utils import truncate_large_value
except ImportError:
    pytestmark = pytest.mark.skip(reason="LiteLLM cache module not found")


@patch("redis.Redis")
def test_initialize_litellm_cache_redis_available(mock_redis):
    """Test the cache initialization when Redis is available."""
    # Mock Redis client
    mock_redis_instance = MagicMock()
    mock_redis.return_value = mock_redis_instance
    mock_redis_instance.ping.return_value = True
    mock_redis_instance.keys.return_value = []
    
    # Mock litellm module
    with patch("litellm.cache", None) as mock_cache, \
         patch("litellm.enable_cache") as mock_enable_cache:
        
        # Run the function
        initialize_litellm_cache()
        
        # Verify Redis was checked
        mock_redis_instance.ping.assert_called_once()
        
        # Verify litellm.enable_cache was called
        mock_enable_cache.assert_called_once()


@patch("redis.Redis")
def test_initialize_litellm_cache_redis_unavailable(mock_redis):
    """Test the cache initialization when Redis is unavailable."""
    # Mock Redis client to simulate connection error
    mock_redis_instance = MagicMock()
    mock_redis.return_value = mock_redis_instance
    mock_redis_instance.ping.side_effect = Exception("Connection failed")
    
    # Mock litellm module
    with patch("litellm.cache", None) as mock_cache, \
         patch("litellm.enable_cache") as mock_enable_cache:
        
        # Run the function
        initialize_litellm_cache()
        
        # Verify Redis was checked
        mock_redis_instance.ping.assert_called_once()
        
        # Verify litellm.enable_cache was still called (fallback to memory cache)
        mock_enable_cache.assert_called_once()