# Task 034: Claude Module Communicator Integration

## Executive Summary

This task integrates the `claude-module-communicator` library into the Marker project to replace the current fragmented Claude integration approach. The current implementation uses multiple SQLite databases, subprocess calls, and custom background processing. The new architecture will provide a unified, modular, and maintainable approach to Claude interactions.

## Current State Analysis

### 1. Multiple Claude Integration Points

The Marker project currently has several different Claude integration patterns:

#### 1.1 Direct API Integration (`marker/services/claude.py`)
- Uses Anthropic Python SDK directly
- Handles image processing and JSON schema validation
- Custom retry logic for rate limits
- **Issues**: Duplicated retry logic, no caching, no background processing

#### 1.2 Subprocess-based Module Query (`marker/services/claude_module_query.py`)
- Runs Claude CLI commands via subprocess
- Custom response storage system using JSON files
- Background processing with file-based status tracking
- **Issues**: Fragile subprocess handling, file-based state management, no proper queue

#### 1.3 SQLite-based Background Processing (`marker/processors/claude_table_merge_analyzer.py`)
- Uses SQLite for task queue management
- Background Claude instances with threading
- Custom task status tracking
- **Issues**: Database per feature, complex threading logic, no shared infrastructure

### 2. Architecture Problems

1. **Fragmentation**: Each feature implements its own Claude integration
2. **Duplication**: Retry logic, error handling, and response parsing repeated
3. **Complexity**: Multiple storage backends (SQLite, JSON files, in-memory)
4. **Maintenance**: Difficult to update Claude API changes across all implementations
5. **Testing**: Each implementation requires separate mocking/testing approach

## Proposed Architecture

### 1. Unified ModuleCommunicator Integration

Replace all current Claude integrations with a single `ModuleCommunicator` instance:

```python
# marker/services/claude_unified.py
from claude_module_communicator import ModuleCommunicator
from marker.config.claude_config import CLAUDE_CONFIG

class UnifiedClaudeService:
    """Unified Claude service using ModuleCommunicator."""
    
    def __init__(self):
        self.communicator = ModuleCommunicator(
            db_path=CLAUDE_CONFIG.db_path,
            model=CLAUDE_CONFIG.model,
            api_key=CLAUDE_CONFIG.api_key
        )
    
    async def process_document(self, doc_data, prompt_template):
        """Process any document-related Claude request."""
        return await self.communicator.send_message(
            prompt=prompt_template.format(**doc_data),
            context=doc_data,
            metadata={"source": "marker", "type": "document"}
        )
```

### 2. Migration Strategy

#### Phase 1: Create Adapter Layer
Create adapters that maintain existing interfaces while using ModuleCommunicator internally:

```python
# marker/services/adapters/claude_api_adapter.py
class ClaudeAPIAdapter:
    """Adapter for existing ClaudeService API."""
    
    def __init__(self, unified_service):
        self.unified = unified_service
    
    def __call__(self, prompt, image, block, response_schema, **kwargs):
        # Convert existing call format to ModuleCommunicator format
        message_data = {
            "prompt": prompt,
            "images": self.prepare_images(image),
            "schema": response_schema.model_json_schema(),
            "context": {"block": block.model_dump()}
        }
        
        # Use unified service
        result = asyncio.run(
            self.unified.process_document(
                doc_data=message_data,
                prompt_template="{prompt}"
            )
        )
        
        # Convert response back to expected format
        return self.validate_response(result, response_schema)
```

#### Phase 2: Update Features Incrementally

##### Before (subprocess-based):
```python
# marker/services/claude_module_query.py
def query_module(prompt, module_path, system_prompt=None):
    claude_cmd = ["claude", "-p", prompt, "--system-prompt", system_prompt]
    result = subprocess.run(claude_cmd, cwd=module_path, capture_output=True)
    # Complex error handling and JSON parsing
    return json.loads(result.stdout)
```

##### After (ModuleCommunicator):
```python
# marker/services/claude_module_query.py
async def query_module(prompt, module_path, system_prompt=None):
    async with unified_claude.communicator.create_session() as session:
        return await session.query_module(
            prompt=prompt,
            module_context={"path": module_path},
            system_prompt=system_prompt
        )
```

##### Before (SQLite-based background):
```python
# marker/processors/claude_table_merge_analyzer.py
class ClaudeTableMergeAnalyzer:
    def __init__(self):
        self.db_path = Path.home() / ".marker_claude" / "table_merge.db"
        self._init_database()
        self._start_background_worker()
    
    def analyze_tables_async(self, config):
        task_id = str(uuid.uuid4())
        # Insert into SQLite
        # Background thread picks up task
        return task_id
```

##### After (ModuleCommunicator):
```python
# marker/processors/claude_table_merge_analyzer.py
class ClaudeTableMergeAnalyzer:
    def __init__(self):
        self.claude = UnifiedClaudeService()
    
    async def analyze_tables_async(self, config):
        return await self.claude.communicator.send_message_async(
            prompt=self._build_analysis_prompt(config),
            context={"tables": config.table_data},
            priority="high"
        )
```

### 3. Feature Mapping

| Current Feature | Current Implementation | New Implementation |
|----------------|----------------------|-------------------|
| Image Description | Direct API + custom retry | `communicator.process_image()` |
| Table Analysis | SQLite queue + threading | `communicator.send_message_async()` |
| Module Query | Subprocess + JSON files | `communicator.query_module()` |
| Structure Analysis | SQLite + background | `communicator.analyze_structure()` |
| Content Validation | SQLite + custom queue | `communicator.validate_content()` |

### 4. Benefits

#### 4.1 Reduced Complexity
- Single database for all Claude interactions
- Unified retry and rate limit handling
- Consistent error handling and logging

#### 4.2 Improved Modularity
- Clear separation of concerns
- Reusable components
- Easier to test and mock

#### 4.3 Better Performance
- Shared connection pool
- Intelligent request batching
- Unified caching layer

#### 4.4 Enhanced Monitoring
- Centralized metrics collection
- Unified logging
- Request/response history

### 5. Implementation Steps

#### Step 1: Setup and Configuration (Week 1)
```python
# marker/config/claude_config.py
from pathlib import Path
from pydantic import BaseSettings

class ClaudeConfig(BaseSettings):
    """Unified Claude configuration."""
    db_path: Path = Path.home() / ".marker" / "claude.db"
    model: str = "claude-3-5-sonnet-20241022"
    api_key: str = None
    max_concurrent: int = 5
    retry_config: dict = {
        "max_retries": 3,
        "backoff_factor": 2
    }
    
    class Config:
        env_prefix = "MARKER_CLAUDE_"

CLAUDE_CONFIG = ClaudeConfig()
```

#### Step 2: Create Unified Service (Week 1)
```python
# marker/services/claude_unified.py
from claude_module_communicator import ModuleCommunicator
from marker.config.claude_config import CLAUDE_CONFIG

class UnifiedClaudeService:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.communicator = ModuleCommunicator(
            db_path=str(CLAUDE_CONFIG.db_path),
            config=CLAUDE_CONFIG.model_dump()
        )
        self._initialized = True
    
    # Service methods...
```

#### Step 3: Create Adapters (Week 2)
- `ClaudeAPIAdapter` for direct API calls
- `ClaudeSubprocessAdapter` for module queries
- `ClaudeBackgroundAdapter` for async processing

#### Step 4: Migrate Features (Weeks 3-4)
1. Image description processors
2. Table merge analyzers
3. Module query system
4. Content validators
5. Structure analyzers

#### Step 5: Testing and Validation (Week 5)
- Unit tests for adapters
- Integration tests for migrated features
- Performance benchmarks
- Regression testing

#### Step 6: Cleanup (Week 6)
- Remove old SQLite databases
- Remove subprocess code
- Update documentation
- Remove legacy code

### 6. Migration Example

Here's a complete example of migrating the table merge analyzer:

#### Current Implementation:
```python
# marker/processors/claude_table_merge_analyzer.py (current)
class ClaudeTableMergeAnalyzer:
    def __init__(self):
        self.db_path = Path.home() / ".marker_claude" / "table_merge.db"
        self._init_database()
        self._start_background_worker()
    
    def _init_database(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.execute('''CREATE TABLE IF NOT EXISTS tasks ...''')
        conn.close()
    
    def _start_background_worker(self):
        self.worker_thread = threading.Thread(target=self._worker_loop)
        self.worker_thread.start()
    
    def analyze_tables_async(self, config: AnalysisConfig) -> str:
        task_id = str(uuid.uuid4())
        conn = sqlite3.connect(str(self.db_path))
        conn.execute(
            "INSERT INTO tasks VALUES (?, ?, ?, ?, ?)",
            (task_id, TaskStatus.PENDING.value, json.dumps(config), None, datetime.now())
        )
        conn.commit()
        conn.close()
        return task_id
```

#### New Implementation:
```python
# marker/processors/claude_table_merge_analyzer.py (new)
from marker.services.claude_unified import UnifiedClaudeService

class ClaudeTableMergeAnalyzer:
    def __init__(self):
        self.claude = UnifiedClaudeService()
        self.analyzer = self.claude.create_analyzer("table_merge")
    
    async def analyze_tables_async(self, config: AnalysisConfig) -> AnalysisResult:
        prompt = self._build_analysis_prompt(config)
        
        result = await self.analyzer.analyze(
            prompt=prompt,
            context={
                "table1": config.table1_data,
                "table2": config.table2_data,
                "document_context": config.context
            },
            schema=AnalysisResult,
            priority="high" if config.confidence_threshold > 0.8 else "normal"
        )
        
        return AnalysisResult(**result)
    
    def _build_analysis_prompt(self, config: AnalysisConfig) -> str:
        return f"""
        Analyze these two tables for potential merging:
        
        Table 1: {json.dumps(config.table1_data, indent=2)}
        Table 2: {json.dumps(config.table2_data, indent=2)}
        
        Context: {json.dumps(config.context, indent=2)}
        
        Determine if these tables should be merged based on:
        1. Content continuity
        2. Structure similarity
        3. Semantic relationships
        
        Provide your analysis in the specified format.
        """
```

### 7. Challenges and Mitigations

#### Challenge 1: Async Migration
**Issue**: Current code uses synchronous patterns, ModuleCommunicator is async-first
**Mitigation**: Create sync wrappers during migration:
```python
def sync_wrapper(async_func):
    def wrapper(*args, **kwargs):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(async_func(*args, **kwargs))
        finally:
            loop.close()
    return wrapper
```

#### Challenge 2: Feature Parity
**Issue**: Ensuring all current features work identically after migration
**Mitigation**: Comprehensive test suite before migration, A/B testing during rollout

#### Challenge 3: Performance Impact
**Issue**: Unified system might have different performance characteristics
**Mitigation**: Benchmark critical paths, implement caching, optimize hot paths

### 8. Success Metrics

1. **Code Reduction**: Target 40% reduction in Claude-related code
2. **Performance**: No regression in processing times
3. **Reliability**: Reduce Claude-related errors by 50%
4. **Maintainability**: Single point of Claude configuration
5. **Testing**: 90%+ test coverage for Claude interactions

### 9. Timeline

- **Week 1**: Setup unified service and configuration
- **Week 2**: Create adapter layer
- **Week 3-4**: Migrate features incrementally
- **Week 5**: Testing and validation
- **Week 6**: Cleanup and documentation

### 10. Rollback Plan

If issues arise during migration:
1. Adapters allow instant rollback to old implementation
2. Feature flags control which implementation is active
3. Both systems can run in parallel during transition
4. Database migration is reversible

## Conclusion

Integrating `claude-module-communicator` will significantly improve the Marker project's architecture by:
- Consolidating multiple Claude integration approaches into one
- Reducing code complexity and duplication
- Improving reliability and performance
- Making the codebase more maintainable

The phased migration approach with adapters ensures a smooth transition with minimal risk.