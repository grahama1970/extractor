# MCP to Sub-Agent Conversion Plan

## Overview

Converting from MCP (Model Context Protocol) tools to dedicated sub-agents for better modularity, maintainability, and Claude Code integration.

## Current MCP Usage Analysis

### 1. ArangoDB Operations (mcp__arango_tools)
- **Usage**: Knowledge graph storage and retrieval
- **Functions**: upsert, query, edge creation, multi-hop traversal
- **Used By**: knowledge_architect, knowledge_integration.py

### 2. ArXiv Operations (mcp__arxiv)
- **Usage**: Paper search and analysis
- **Functions**: search_papers, download_papers, extract_sections
- **Used By**: Research workflows

### 3. LLM Operations (mcp__universal-llm-executor)
- **Usage**: LLM calls for analysis
- **Functions**: execute_llm
- **Used By**: Various processors

### 4. Code Review (mcp__code-review)
- **Usage**: Code bundling and review
- **Functions**: generate_bundle, generate_and_review
- **Used By**: code_reviewer sub-agent

## Conversion Strategy

### Phase 1: Create Database Sub-Agent

**File**: `.claude/agents/database_architect.md`

```markdown
---
name: database_architect
description: I manage ArangoDB operations for knowledge graph storage and retrieval
---

# Database Architect Sub-Agent

I handle all database operations for the knowledge graph, replacing mcp__arango_tools.

## Core Capabilities
1. Document storage and retrieval
2. Edge relationship management
3. Multi-hop graph traversal
4. BM25 text search
5. Pattern matching and learning

## Implementation
- Use arangodb Python client directly
- Implement connection pooling
- Add retry logic and error handling
- Cache frequently accessed data
```

**Implementation File**: `src/extractor/core/db/arango_client.py`

### Phase 2: Create Research Sub-Agent

**File**: `.claude/agents/research_librarian.md`

```markdown
---
name: research_librarian
description: I search and analyze research papers from ArXiv
---

# Research Librarian Sub-Agent

I handle research paper discovery and analysis, replacing mcp__arxiv tools.

## Core Capabilities
1. ArXiv paper search
2. PDF download and extraction
3. Section analysis
4. Citation tracking
5. Similar paper discovery
```

**Implementation File**: `src/extractor/core/research/arxiv_client.py`

### Phase 3: Create LLM Orchestrator Sub-Agent

**File**: `.claude/agents/llm_orchestrator.md`

```markdown
---
name: llm_orchestrator
description: I manage LLM calls across different providers
---

# LLM Orchestrator Sub-Agent

I handle all LLM operations, replacing mcp__universal-llm-executor.

## Core Capabilities
1. Multi-provider support (Claude, GPT, Gemini, Moonshot)
2. Automatic retry and fallback
3. Token management
4. Response parsing
5. Cost tracking
```

**Implementation File**: `src/extractor/core/llm/llm_client.py`

## Implementation Details

### 1. Database Architect Implementation

```python
# src/extractor/core/db/arango_client.py
from arango import ArangoClient
from typing import Dict, List, Any, Optional
import json
from loguru import logger

class DatabaseArchitect:
    """Direct ArangoDB client replacing MCP tools."""
    
    def __init__(self, config: Dict[str, Any]):
        self.client = ArangoClient(hosts=config['hosts'])
        self.db = self.client.db(
            config['database'],
            username=config['username'],
            password=config['password']
        )
        
    async def upsert(self, collection: str, search: Dict[str, Any], 
                     update: Dict[str, Any]) -> str:
        """Upsert document in collection."""
        try:
            col = self.db.collection(collection)
            # Search for existing document
            cursor = col.find(search)
            existing = list(cursor)
            
            if existing:
                # Update existing
                doc = existing[0]
                doc.update(update)
                col.update(doc)
                return doc['_key']
            else:
                # Insert new
                result = col.insert({**search, **update})
                return result['_key']
        except Exception as e:
            logger.error(f"Upsert failed: {e}")
            raise
            
    async def create_edge(self, from_id: str, to_id: str, 
                          collection: str, data: Dict[str, Any]) -> str:
        """Create edge between documents."""
        try:
            edge_col = self.db.collection(collection)
            edge_data = {
                '_from': from_id,
                '_to': to_id,
                **data
            }
            result = edge_col.insert(edge_data)
            return result['_key']
        except Exception as e:
            logger.error(f"Edge creation failed: {e}")
            raise
            
    async def multi_hop_traversal(self, start_node: str, 
                                  max_depth: int = 3) -> List[Dict[str, Any]]:
        """Perform multi-hop graph traversal."""
        query = '''
        FOR v, e, p IN 1..@depth OUTBOUND @start 
            GRAPH 'knowledge_graph'
            RETURN {vertex: v, edge: e, path: p}
        '''
        cursor = self.db.aql.execute(
            query,
            bind_vars={'start': start_node, 'depth': max_depth}
        )
        return list(cursor)
```

### 2. Research Librarian Implementation

```python
# src/extractor/core/research/arxiv_client.py
import arxiv
import aiohttp
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from loguru import logger

class ResearchLibrarian:
    """ArXiv research paper management."""
    
    def __init__(self, download_dir: Path):
        self.download_dir = download_dir
        self.client = arxiv.Client()
        
    async def search_papers(self, query: str, max_results: int = 20) -> List[Dict[str, Any]]:
        """Search ArXiv for papers."""
        try:
            search = arxiv.Search(
                query=query,
                max_results=max_results,
                sort_by=arxiv.SortCriterion.Relevance
            )
            
            results = []
            for paper in self.client.results(search):
                results.append({
                    'id': paper.entry_id,
                    'title': paper.title,
                    'abstract': paper.summary,
                    'authors': [a.name for a in paper.authors],
                    'published': paper.published,
                    'pdf_url': paper.pdf_url
                })
            
            return results
        except Exception as e:
            logger.error(f"ArXiv search failed: {e}")
            raise
            
    async def download_paper(self, paper_id: str) -> Path:
        """Download paper PDF."""
        # Implementation here
        pass
```

### 3. LLM Orchestrator Implementation

```python
# src/extractor/core/llm/llm_client.py
from litellm import acompletion
from typing import Dict, Any, Optional, List
from loguru import logger
import asyncio

class LLMOrchestrator:
    """Multi-provider LLM orchestration."""
    
    def __init__(self, default_model: str = "claude-3-opus-20240229"):
        self.default_model = default_model
        self.retry_config = {
            'max_retries': 3,
            'retry_delay': 1.0,
            'backoff_factor': 2.0
        }
        
    async def generate(self, prompt: str, model: Optional[str] = None,
                      **kwargs) -> str:
        """Generate LLM response with automatic retry."""
        model = model or self.default_model
        
        for attempt in range(self.retry_config['max_retries']):
            try:
                response = await acompletion(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    **kwargs
                )
                return response.choices[0].message.content
            except Exception as e:
                logger.warning(f"LLM call failed (attempt {attempt + 1}): {e}")
                if attempt < self.retry_config['max_retries'] - 1:
                    await asyncio.sleep(
                        self.retry_config['retry_delay'] * 
                        (self.retry_config['backoff_factor'] ** attempt)
                    )
                else:
                    raise
```

## Migration Steps

### Step 1: Create Sub-Agent Files
1. Create `.claude/agents/database_architect.md`
2. Create `.claude/agents/research_librarian.md`
3. Create `.claude/agents/llm_orchestrator.md`

### Step 2: Implement Core Clients
1. Implement `src/extractor/core/db/arango_client.py`
2. Implement `src/extractor/core/research/arxiv_client.py`
3. Implement `src/extractor/core/llm/llm_client.py`

### Step 3: Update Existing Code
1. Replace `mcp__arango_tools` calls with `DatabaseArchitect` methods
2. Replace `mcp__arxiv` calls with `ResearchLibrarian` methods
3. Replace `mcp__universal-llm-executor` calls with `LLMOrchestrator` methods

### Step 4: Update Sub-Agent Integration
1. Update `knowledge_integration.py` to use new clients
2. Update processors to use new clients
3. Update tests to use new clients

## Benefits of Conversion

### 1. Better Error Handling
- Direct control over retry logic
- Custom error messages
- Proper cleanup on failure

### 2. Performance Optimization
- Connection pooling
- Caching frequently accessed data
- Batch operations

### 3. Maintainability
- Clear separation of concerns
- Easier to test
- Better documentation

### 4. Flexibility
- Custom business logic
- Domain-specific optimizations
- Easier debugging

## Testing Strategy

### 1. Unit Tests
```python
# tests/test_database_architect.py
async def test_upsert_new_document():
    architect = DatabaseArchitect(test_config)
    key = await architect.upsert(
        collection="test_collection",
        search={"name": "test"},
        update={"value": 42}
    )
    assert key is not None
```

### 2. Integration Tests
```python
# tests/test_knowledge_integration.py
async def test_knowledge_graph_update():
    # Test full workflow with new clients
    pass
```

### 3. Migration Validation
- Compare results between MCP and sub-agent implementations
- Ensure no data loss during migration
- Validate performance improvements

## Timeline

### Week 1
- Create sub-agent markdown files
- Implement DatabaseArchitect
- Update knowledge_integration.py

### Week 2
- Implement ResearchLibrarian
- Implement LLMOrchestrator
- Update all processors

### Week 3
- Complete testing
- Performance optimization
- Documentation updates

## Rollback Plan

1. Keep MCP tools available as fallback
2. Use feature flags to switch between implementations
3. Gradual migration with monitoring

## Success Metrics

1. All MCP tool calls replaced
2. Performance improvement > 20%
3. Error rate reduction > 50%
4. All tests passing
5. Documentation complete