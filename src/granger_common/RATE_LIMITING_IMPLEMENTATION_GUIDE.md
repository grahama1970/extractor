# Rate Limiting Implementation Guide

## Overview
All Granger modules MUST use the standardized `RateLimiter` class when calling external APIs.

## Installation

1. Copy the `granger_common` folder to your project's src directory
2. Or add as a git submodule: `git submodule add <repo> src/granger_common`

## Implementation Examples

### 1. SPARTA Module (NVD API)

```python
# src/sparta/core/cve_lookup.py

from granger_common import get_rate_limiter
import httpx

class CVELookup:
    def __init__(self):
        self.rate_limiter = get_rate_limiter("nvd")
        self.client = httpx.Client()
    
    async def get_cve(self, cve_id: str) -> dict:
        """Get CVE data with rate limiting."""
        # Acquire rate limit permission
        if not await self.rate_limiter.acquire_async():
            raise TimeoutError("Rate limit timeout")
        
        # Make the API call
        response = await self.client.get(
            f"https://services.nvd.nist.gov/rest/json/cves/2.0",
            params={"cveId": cve_id}
        )
        return response.json()
```

### 2. ArXiv Module (Already Partially Implemented)

```python
# src/arxiv_mcp_server/core/search.py

from granger_common import get_rate_limiter
import arxiv

class ArxivSearcher:
    def __init__(self):
        self.rate_limiter = get_rate_limiter("arxiv")
        # ArXiv client already has rate limiting, but we add our own for consistency
        self.client = arxiv.Client(
            page_size=100,
            delay_seconds=0.0,  # We handle rate limiting
            num_retries=3
        )
    
    def search(self, query: str, max_results: int = 10):
        """Search ArXiv with rate limiting."""
        # Acquire rate limit permission
        if not self.rate_limiter.acquire():
            raise TimeoutError("Rate limit timeout")
        
        search = arxiv.Search(query=query, max_results=max_results)
        return list(self.client.results(search))
```

### 3. YouTube Transcripts Module

```python
# src/youtube_transcripts/core/transcript_fetcher.py

from granger_common import get_rate_limiter
from youtube_transcript_api import YouTubeTranscriptApi

class TranscriptFetcher:
    def __init__(self):
        self.rate_limiter = get_rate_limiter("youtube")
    
    def get_transcript(self, video_id: str) -> list:
        """Get YouTube transcript with rate limiting."""
        # Acquire rate limit permission
        if not self.rate_limiter.acquire():
            raise TimeoutError("Rate limit timeout")
        
        return YouTubeTranscriptApi.get_transcript(video_id)
```

### 4. Custom API Rate Limiting

```python
# For APIs not in the pre-configured list

from granger_common import RateLimiter

class CustomAPIClient:
    def __init__(self):
        # Create custom rate limiter
        self.rate_limiter = RateLimiter(
            calls_per_second=1.0,  # 1 call per second
            burst_size=5,          # Allow bursts up to 5
            name="CustomAPI"
        )
    
    async def call_api(self, endpoint: str):
        if not await self.rate_limiter.acquire_async():
            raise TimeoutError("Rate limit timeout")
        
        # Make API call
        return await make_request(endpoint)
```

## Best Practices

1. **Always use the same rate limiter instance** for the same API across your module
2. **Log rate limit events** - The RateLimiter uses loguru for automatic logging
3. **Handle timeouts gracefully** - Provide user-friendly error messages
4. **Use pre-configured limiters** when available (nvd, arxiv, youtube, github)
5. **Test with concurrent requests** to ensure rate limiting works properly

## Monitoring

```python
# Get rate limiter statistics
stats = rate_limiter.get_stats()
print(f"Current usage: {stats['current_calls']}/{stats['burst_size']}")
```

## Migration Checklist

For each module:

- [ ] Add `granger_common` to the module
- [ ] Import `get_rate_limiter` or `RateLimiter`
- [ ] Create rate limiter instance in `__init__`
- [ ] Add `acquire()` before every external API call
- [ ] Handle timeout errors appropriately
- [ ] Test with concurrent requests
- [ ] Verify rate limiting in logs

## Example: Complete SPARTA Fix

```python
# src/sparta/core/cve_api.py

import httpx
from typing import Dict, Any, Optional
from granger_common import get_rate_limiter
from loguru import logger

class CVEAPI:
    """CVE API client with proper rate limiting."""
    
    BASE_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
    
    def __init__(self):
        self.rate_limiter = get_rate_limiter("nvd")
        self.client = httpx.Client(timeout=30.0)
        logger.info("CVE API client initialized with NVD rate limiting")
    
    def get_cve(self, cve_id: str) -> Optional[Dict[str, Any]]:
        """
        Get CVE details with rate limiting.
        
        Args:
            cve_id: CVE identifier (e.g., 'CVE-2021-44228')
            
        Returns:
            CVE data dict or None if not found
        """
        try:
            # Acquire rate limit permission
            if not self.rate_limiter.acquire(timeout=30.0):
                logger.error(f"Rate limit timeout for CVE {cve_id}")
                raise TimeoutError("NVD API rate limit timeout")
            
            # Make the API call
            response = self.client.get(
                self.BASE_URL,
                params={"cveId": cve_id}
            )
            response.raise_for_status()
            
            data = response.json()
            vulnerabilities = data.get("vulnerabilities", [])
            
            if vulnerabilities:
                logger.info(f"Successfully retrieved CVE {cve_id}")
                return vulnerabilities[0]
            else:
                logger.warning(f"CVE {cve_id} not found")
                return None
                
        except httpx.HTTPError as e:
            logger.error(f"HTTP error retrieving CVE {cve_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error retrieving CVE {cve_id}: {e}")
            raise
    
    def __del__(self):
        """Clean up HTTP client."""
        if hasattr(self, 'client'):
            self.client.close()
```