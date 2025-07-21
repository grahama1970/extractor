# Granger Common Implementation Examples

## 1. SPARTA Module - Complete Fix

```python
# src/sparta/core/cve_api.py

import httpx
from typing import Dict, Any, Optional, List
from granger_common import get_rate_limiter, schema_manager, create_message
from loguru import logger

class CVEAPI:
    """CVE API client with rate limiting and schema management."""
    
    BASE_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
    
    def __init__(self):
        self.rate_limiter = get_rate_limiter("nvd")
        self.client = httpx.Client(timeout=30.0)
        logger.info("CVE API initialized with standardized rate limiting")
    
    async def get_cve_async(self, cve_id: str) -> Optional[Dict[str, Any]]:
        """Get CVE with rate limiting (async)."""
        if not await self.rate_limiter.acquire_async():
            raise TimeoutError("Rate limit timeout")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.BASE_URL,
                params={"cveId": cve_id}
            )
            response.raise_for_status()
            return response.json()
    
    def send_to_marker(self, cve_data: Dict[str, Any]) -> Message:
        """Send CVE data to Marker module with proper schema."""
        message = create_message(
            id=f"cve_{cve_data['cve']['id']}",
            name="cve_document", 
            payload={
                "cve_id": cve_data['cve']['id'],
                "description": cve_data['cve']['descriptions'][0]['value'],
                "severity": cve_data.get('impact', {}).get('baseMetricV3', {}).get('cvssV3', {}).get('baseSeverity', 'UNKNOWN'),
                "references": [ref['url'] for ref in cve_data['cve'].get('references', [])]
            },
            metadata={
                "source": "sparta",
                "timestamp": datetime.now().isoformat()
            },
            routing={
                "destination": "marker",
                "priority": "high" if 'CRITICAL' in str(cve_data) else "normal"
            }
        )
        
        # Module communicator would handle actual sending
        return message
```

## 2. Marker Module - Smart PDF Processing

```python
# src/marker/core/pdf_processor.py

from pathlib import Path
from typing import Dict, Any, Optional
from granger_common import SmartPDFHandler, schema_manager, create_message
from loguru import logger

class MarkerPDFProcessor:
    """PDF processor with smart memory/streaming handling."""
    
    def __init__(self):
        # 1GB threshold for 256GB RAM workstation
        self.pdf_handler = SmartPDFHandler(memory_threshold_mb=1000)
        logger.info("Marker PDF processor initialized with 1GB memory threshold")
    
    def process_pdf(self, pdf_path: str, source_message: Optional[Message] = None) -> Message:
        """Process PDF and create standardized message."""
        # Get PDF info first
        info = self.pdf_handler.get_pdf_info(pdf_path)
        logger.info(
            f"Processing PDF: {info['file_name']} "
            f"({info['size_mb']:.1f}MB, {info['pages']} pages) "
            f"using {info['processing_method']} method"
        )
        
        # Process the PDF
        result = self.pdf_handler.process_pdf(pdf_path)
        
        # Create message for next module
        message = create_message(
            id=f"pdf_{Path(pdf_path).stem}_{int(time.time())}",
            name="pdf_processed",
            payload={
                "file_name": result['file_name'],
                "pages": result['pages'],
                "content": result['content'],
                "metadata": result.get('metadata', {})
            },
            metadata={
                "source": "marker",
                "processing_method": result['method'],
                "size_mb": result['size_mb'],
                "source_message_id": source_message.id if source_message else None
            },
            routing={
                "destination": "arangodb",
                "priority": "normal"
            }
        )
        
        return message
    
    def process_large_pdf_with_callback(self, pdf_path: str):
        """Process very large PDF with progress callback."""
        def progress_callback(chunk_text: str, current_page: int, total_pages: int):
            progress = (current_page / total_pages) * 100
            logger.info(f"Processing progress: {progress:.1f}% ({current_page}/{total_pages} pages)")
            
            # Could send partial results to ArangoDB here
            if current_page % 100 == 0:
                partial_message = create_message(
                    id=f"pdf_partial_{int(time.time())}",
                    name="pdf_chunk",
                    payload={"text": chunk_text, "pages": f"{current_page-99}-{current_page}"},
                    metadata={"source": "marker", "partial": True}
                )
                # Send to processing pipeline
        
        if self.pdf_handler.get_pdf_info(pdf_path)['size_mb'] > 1000:
            # Use callback for very large files
            self.pdf_handler.streaming_processor.process_with_callback(
                pdf_path, 
                progress_callback
            )
```

## 3. Module Communicator - Schema Compatibility

```python
# src/claude_module_communicator/core/message_router.py

from typing import Dict, Any, Optional
from granger_common import schema_manager, Message, SchemaVersion
from loguru import logger

class MessageRouter:
    """Routes messages between modules ensuring schema compatibility."""
    
    def __init__(self):
        self.module_versions = {
            "sparta": SchemaVersion.V2_1,      # Latest version
            "marker": SchemaVersion.V2_0,      # One version behind
            "arangodb": SchemaVersion.V2_1,    # Latest version  
            "old_module": SchemaVersion.V1_1   # Legacy module
        }
        logger.info("Message router initialized with schema compatibility")
    
    def route_message(
        self, 
        message: Message | Dict[str, Any], 
        destination: str
    ) -> Dict[str, Any]:
        """Route message ensuring compatibility with destination."""
        # Convert to dict if needed
        if isinstance(message, Message):
            message_data = message.dict()
        else:
            message_data = message
        
        # Get destination's expected version
        dest_version = self.module_versions.get(destination, SchemaVersion.V2_1)
        
        # Ensure compatibility
        compatible_data = schema_manager.ensure_compatibility(
            message_data,
            receiver_version=dest_version.value
        )
        
        logger.info(
            f"Routing message {compatible_data['id']} to {destination} "
            f"(converted from v{message_data.get('version', 'unknown')} to v{dest_version.value})"
        )
        
        return compatible_data
    
    def handle_legacy_message(self, legacy_data: Dict[str, Any]) -> Message:
        """Handle messages from legacy modules."""
        # Detect version
        version = legacy_data.get('version', '1.0')
        
        # Migrate to current version
        modern_data = schema_manager.migrate(
            legacy_data,
            from_version=version,
            to_version=SchemaVersion.V2_1.value
        )
        
        # Validate and return
        return schema_manager.validate(modern_data)
```

## 4. YouTube Transcripts - Rate Limited API

```python
# src/youtube_transcripts/core/transcript_fetcher.py

from typing import List, Dict, Any
import asyncio
from youtube_transcript_api import YouTubeTranscriptApi
from granger_common import get_rate_limiter, create_message
from loguru import logger

class TranscriptFetcher:
    """YouTube transcript fetcher with rate limiting."""
    
    def __init__(self):
        self.rate_limiter = get_rate_limiter("youtube")
        logger.info("YouTube transcript fetcher initialized with rate limiting")
    
    def fetch_transcript(self, video_id: str) -> List[Dict[str, Any]]:
        """Fetch transcript with rate limiting."""
        # Acquire rate limit
        if not self.rate_limiter.acquire(timeout=30.0):
            raise TimeoutError("YouTube API rate limit timeout")
        
        try:
            transcript = YouTubeTranscriptApi.get_transcript(video_id)
            logger.info(f"Fetched transcript for video {video_id}")
            return transcript
        except Exception as e:
            logger.error(f"Failed to fetch transcript for {video_id}: {e}")
            raise
    
    async def fetch_multiple_transcripts(self, video_ids: List[str]) -> List[Message]:
        """Fetch multiple transcripts with rate limiting."""
        messages = []
        
        for video_id in video_ids:
            # Rate limit each request
            if not await self.rate_limiter.acquire_async():
                logger.warning(f"Skipping {video_id} due to rate limit")
                continue
            
            try:
                transcript = await asyncio.to_thread(
                    YouTubeTranscriptApi.get_transcript, 
                    video_id
                )
                
                # Create message for Marker
                message = create_message(
                    id=f"yt_{video_id}",
                    name="youtube_transcript",
                    payload={
                        "video_id": video_id,
                        "transcript": transcript,
                        "duration": sum(t['duration'] for t in transcript)
                    },
                    metadata={
                        "source": "youtube_transcripts",
                        "language": transcript[0].get('language', 'en') if transcript else 'unknown'
                    },
                    routing={
                        "destination": "marker",
                        "priority": "normal"
                    }
                )
                messages.append(message)
                
            except Exception as e:
                logger.error(f"Failed to process {video_id}: {e}")
        
        return messages
```

## 5. ArangoDB - Schema Validation on Storage

```python
# src/arangodb/core/document_store.py

from typing import Dict, Any, List
from arango import ArangoClient
from granger_common import schema_manager, Message
from loguru import logger

class DocumentStore:
    """ArangoDB document store with schema validation."""
    
    def __init__(self, url: str = "http://localhost:8529"):
        self.client = ArangoClient(hosts=url)
        self.db = self.client.db('granger', username='root', password='password')
        self.collection = self.db.collection('documents')
        logger.info("ArangoDB document store initialized")
    
    def store_message(self, message: Message | Dict[str, Any]) -> str:
        """Store message with schema validation."""
        # Validate message
        if isinstance(message, dict):
            message = schema_manager.validate(message)
        
        # Prepare document
        doc = {
            "_key": message.id,
            "schema_version": message.version,
            "name": message.name,
            "payload": message.payload,
            "metadata": message.metadata,
            "routing": getattr(message, 'routing', {}),
            "timestamp": message.timestamp.isoformat() if hasattr(message, 'timestamp') else None
        }
        
        # Store in ArangoDB
        result = self.collection.insert(doc)
        logger.info(f"Stored message {message.id} in ArangoDB")
        
        return result['_key']
    
    def retrieve_message(self, message_id: str, target_version: str = None) -> Message:
        """Retrieve message and optionally convert to target version."""
        doc = self.collection.get(message_id)
        
        if not doc:
            raise ValueError(f"Message {message_id} not found")
        
        # Reconstruct message data
        message_data = {
            "id": doc['_key'],
            "name": doc['name'],
            "payload": doc['payload'],
            "metadata": doc['metadata'],
            "version": doc['schema_version']
        }
        
        if 'routing' in doc:
            message_data['routing'] = doc['routing']
        if 'timestamp' in doc:
            message_data['timestamp'] = doc['timestamp']
        
        # Convert to requested version if needed
        if target_version and target_version != doc['schema_version']:
            message_data = schema_manager.migrate(
                message_data,
                from_version=doc['schema_version'],
                to_version=target_version
            )
        
        return schema_manager.validate(message_data)
```

## Integration Test Example

```python
# tests/integration/test_full_pipeline.py

import asyncio
from granger_common import create_message, schema_manager

async def test_full_pipeline():
    """Test the complete pipeline with all standardizations."""
    
    # 1. SPARTA creates CVE alert
    sparta_message = create_message(
        id="cve_2024_12345",
        name="critical_cve",
        payload={
            "cve_id": "CVE-2024-12345",
            "description": "Critical vulnerability in Example Software",
            "severity": "CRITICAL"
        },
        metadata={"source": "sparta"},
        routing={"destination": "marker", "priority": "high"}
    )
    
    # 2. Module Communicator routes to Marker (v2.0)
    router = MessageRouter()
    marker_data = router.route_message(sparta_message, "marker")
    assert marker_data['version'] == '2.0'  # Downgraded for Marker
    
    # 3. Marker processes and creates response
    marker = MarkerPDFProcessor()
    # Process related PDFs...
    
    # 4. Store in ArangoDB
    store = DocumentStore()
    doc_id = store.store_message(sparta_message)
    
    # 5. Retrieve for legacy module (v1.1)
    legacy_message = store.retrieve_message(doc_id, target_version="1.1")
    assert legacy_message.version == "1.1"
    assert hasattr(legacy_message, 'data')  # v1.1 uses 'data' not 'payload'
    
    print("✅ Full pipeline test passed with schema compatibility!")

if __name__ == "__main__":
    asyncio.run(test_full_pipeline())
```

## Summary

All modules now use:
1. **Same rate limiting** - via `granger_common.get_rate_limiter()`
2. **Smart PDF processing** - via `granger_common.SmartPDFHandler` 
3. **Schema compatibility** - via `granger_common.schema_manager`

This ensures consistent architecture across the entire Granger ecosystem.