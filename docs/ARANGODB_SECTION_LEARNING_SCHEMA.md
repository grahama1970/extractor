# ArangoDB Section Learning Schema

**Purpose:** Store raw and cleaned PDF sections with detailed change tracking to enable learning from past processing decisions

## Core Collections

### 1. pdf_sections Collection

Stores both raw and cleaned data with comprehensive metadata:

```json
{
  "_key": "doc123_section_4",
  "_id": "pdf_sections/doc123_section_4",
  
  // Document metadata
  "document_id": "doc123",
  "document_name": "BHT_CV32A65X_marked.pdf",
  "section_id": 4,
  "section_header": "4.1.5.4. BHT (Branch History Table) submodule",
  
  // Raw data from Marker extraction
  "raw": {
    "header": "4.1.5.4.   BHT   (Branch   History   Table)   submodule",
    "blocks": [
      {
        "id": 0,
        "block_type": "Text",
        "text": "BHT is implemented as a memory which is composed of   BHTDepth entries",
        "bbox": [72, 100, 400, 115],
        "confidence": 0.92
      },
      {
        "id": 1,
        "block_type": "Text", 
        "text": "addressed by a hash of the PC.",
        "bbox": [72, 115, 450, 130],
        "confidence": 0.88
      }
    ],
    "total_blocks": 15,
    "issues_detected": ["excessive_spacing", "split_text", "fragmented_table"]
  },
  
  // Cleaned data after processing
  "cleaned": {
    "header": "4.1.5.4. BHT (Branch History Table) submodule",
    "blocks": [
      {
        "id": 0,
        "block_type": "Text",
        "text": "BHT is implemented as a memory which is composed of BHTDepth entries addressed by a hash of the PC.",
        "merged_from": [0, 1],
        "confidence": 0.95
      }
    ],
    "total_blocks": 8
  },
  
  // Processing metadata
  "processing": {
    "timestamp": "2025-07-29T10:30:00Z",
    "agent": "pdf-section-cleaner",
    "version": "1.0.0",
    "duration_ms": 2340,
    "confidence_score": 0.94,
    "changes_made": 7
  },
  
  // Tool journey tracking (MANDATORY)
  "tool_journey": {
    "journey_id": "journey_abc123",
    "task_type": "section_cleaning",
    "start_time": 1735475400.123,
    "end_time": 1735475402.463,
    "total_duration": 2.34,
    "steps": [
      {
        "tool": "section_cleaner",
        "method": "clean_section",
        "timestamp": "2025-07-29T10:30:00.123Z",
        "parameters": {"section_id": 4, "block_count": 15},
        "status": "completed",
        "step_number": 1,
        "duration": 0.045
      },
      {
        "tool": "knowledge_architect",
        "method": "find_similar_sections",
        "timestamp": "2025-07-29T10:30:00.168Z",
        "parameters": {"query": "BHT Branch History Table", "top_k": 5},
        "status": "completed",
        "step_number": 2,
        "duration": 0.234,
        "result_summary": "Found 3 similar sections"
      },
      {
        "tool": "text_processor",
        "method": "fix_spacing",
        "timestamp": "2025-07-29T10:30:00.402Z",
        "parameters": {"blocks": 15},
        "status": "completed",
        "step_number": 3,
        "duration": 0.156
      },
      {
        "tool": "text_merger",
        "method": "merge_split_text",
        "timestamp": "2025-07-29T10:30:00.558Z",
        "parameters": {"mergeable_blocks": 6},
        "status": "completed",
        "step_number": 4,
        "duration": 0.289
      },
      {
        "tool": "table_reconstructor",
        "method": "rebuild_from_fragments",
        "timestamp": "2025-07-29T10:30:00.847Z",
        "parameters": {"fragments": 20},
        "status": "completed",
        "step_number": 5,
        "duration": 0.512
      },
      {
        "tool": "validator",
        "method": "semantic_validation",
        "timestamp": "2025-07-29T10:30:01.359Z",
        "parameters": {"suspicious_blocks": 2},
        "status": "completed",
        "step_number": 6,
        "duration": 0.234
      },
      {
        "tool": "knowledge_architect",
        "method": "store_patterns",
        "timestamp": "2025-07-29T10:30:01.593Z",
        "parameters": {"patterns": 3},
        "status": "completed",
        "step_number": 7,
        "duration": 0.087
      }
    ],
    "success": true,
    "optimization_opportunities": [
      "Pattern 'header_spacing' could be cached",
      "Similar sections suggest pre-applying merge rules"
    ]
  },
  
  // Change rationale
  "changes": [
    {
      "type": "spacing_fix",
      "description": "Fixed excessive spacing in header",
      "before": "4.1.5.4.   BHT   (Branch   History   Table)   submodule",
      "after": "4.1.5.4. BHT (Branch History Table) submodule",
      "confidence": 0.98
    },
    {
      "type": "text_merge",
      "description": "Merged split text blocks based on proximity",
      "merged_blocks": [0, 1],
      "rationale": "Blocks were contiguous with small vertical gap",
      "confidence": 0.95
    },
    {
      "type": "table_reconstruction",
      "description": "Reconstructed fragmented table from 20 cells",
      "original_fragments": 20,
      "final_structure": {"rows": 5, "cols": 4},
      "confidence": 0.92
    }
  ],
  
  // Searchable fields for BM25
  "search_text": "BHT Branch History Table submodule memory composed BHTDepth entries hash PC",
  
  // Embeddings for semantic search
  "embeddings": {
    "model": "text-embedding-ada-002",
    "vector": [0.0123, -0.0456, ...],  // 1536 dimensions
    "generated_at": "2025-07-29T10:30:05Z"
  },
  
  // Tags for categorization
  "tags": ["technical", "cpu", "branch_prediction", "hardware"],
  "document_type": "technical_specification",
  
  // Quality metrics
  "quality": {
    "accuracy_score": 0.94,
    "completeness": 0.96,
    "formatting_quality": 0.92
  }
}
```

### 2. section_patterns Collection

Learned patterns from processing similar sections:

```json
{
  "_key": "pattern_header_spacing",
  "pattern_type": "spacing_issue",
  "description": "Headers with excessive spacing between words",
  "regex_pattern": "\\s{2,}",
  "examples": [
    "4.1.5.4.   BHT   (Branch",
    "2.3.1.    CPU    Architecture"
  ],
  "solution": "Collapse multiple spaces to single space",
  "success_rate": 0.98,
  "occurrences": 156,
  "last_seen": "2025-07-29T10:30:00Z"
}
```

### 3. processing_edges Collection

Relationships between sections, patterns, and documents:

```json
{
  "_from": "pdf_sections/doc123_section_4",
  "_to": "section_patterns/pattern_header_spacing",
  "_key": "applied_pattern_12345",
  "edge_type": "applied_pattern",
  "confidence": 0.98,
  "timestamp": "2025-07-29T10:30:00Z"
}
```

## Search Capabilities

### 1. BM25 Text Search
```javascript
// Find sections with similar text content
FOR section IN pdf_sections
  SEARCH ANALYZER(
    TOKENS("branch history table", "text_en") ALL IN section.search_text,
    "text_en"
  )
  SORT BM25(section) DESC
  LIMIT 10
  RETURN section
```

### 2. Semantic Vector Search
```javascript
// Find semantically similar sections using embeddings
FOR section IN pdf_sections
  LET similarity = COSINE_SIMILARITY(section.embeddings.vector, @query_vector)
  FILTER similarity > 0.85
  SORT similarity DESC
  LIMIT 10
  RETURN {
    section: section,
    similarity: similarity
  }
```

### 3. Multi-hop Graph Traversal
```javascript
// Find sections that used similar processing patterns
FOR section IN pdf_sections
  FILTER section._key == @section_key
  FOR v, e, p IN 1..3 OUTBOUND section processing_edges
    FILTER e.edge_type == "applied_pattern"
    FOR related IN pdf_sections
      FILTER related._key IN p.vertices[*]._key
      FILTER related._key != section._key
      RETURN DISTINCT {
        original: section.section_header,
        related: related.section_header,
        pattern: p.edges[0]._to,
        path_length: LENGTH(p.edges)
      }
```

## Integration with pdf-section-cleaner

### Storing Results
```python
async def store_section_with_learning(
    raw_section: Dict,
    cleaned_section: Dict,
    changes: List[Dict],
    confidence: float,
    tool_journey: ToolJourneyTracker  # MANDATORY parameter
) -> str:
    """Store section with full learning context and tool journey."""
    
    # Get the complete journey
    journey_data = await tool_journey.save_journey()
    
    # Create comprehensive document
    section_doc = {
        "_key": f"{raw_section['document_id']}_section_{raw_section['id']}",
        "document_id": raw_section['document_id'],
        "section_id": raw_section['id'],
        "section_header": cleaned_section['header'],
        
        # Store both versions
        "raw": raw_section,
        "cleaned": cleaned_section,
        
        # Processing metadata
        "processing": {
            "timestamp": datetime.now().isoformat(),
            "agent": "pdf-section-cleaner",
            "confidence_score": confidence,
            "changes_made": len(changes)
        },
        
        # MANDATORY: Include complete tool journey
        "tool_journey": journey_data,
        
        # Detailed changes
        "changes": changes,
        
        # Searchable text (for BM25)
        "search_text": extract_searchable_text(cleaned_section),
        
        # Generate embeddings
        "embeddings": await generate_embeddings(cleaned_section['header'] + " " + 
                                               extract_text(cleaned_section['blocks']))
    }
    
    # Store in ArangoDB
    result = await upsert_impl(
        collection="pdf_sections",
        document=section_doc
    )
    
    # Create pattern relationships
    for change in changes:
        if pattern := await find_matching_pattern(change):
            await edge_impl(
                from_collection="pdf_sections",
                from_key=section_doc["_key"],
                to_collection="section_patterns",
                to_key=pattern["_key"],
                edge_type="applied_pattern",
                attributes={"confidence": change.get("confidence", 0.9)}
            )
    
    return section_doc["_key"]
```

### Finding Similar Sections
```python
async def find_similar_sections_multi_method(
    section: Dict,
    methods: List[str] = ["bm25", "semantic", "graph"]
) -> Dict[str, List[Dict]]:
    """Find similar sections using multiple search methods."""
    
    results = {}
    
    # BM25 text search
    if "bm25" in methods:
        query_text = section.get("header", "") + " " + extract_text(section.get("blocks", []))
        results["bm25"] = await query_impl(
            query="""
            FOR section IN pdf_sections
              SEARCH ANALYZER(
                TOKENS(@query_text, "text_en") ALL IN section.search_text,
                "text_en"
              )
              SORT BM25(section) DESC
              LIMIT 10
              RETURN section
            """,
            bind_vars={"query_text": query_text}
        )
    
    # Semantic search
    if "semantic" in methods:
        embeddings = await generate_embeddings(extract_text(section))
        results["semantic"] = await semantic_search_impl(
            collection="pdf_sections",
            query_vector=embeddings,
            vector_field="embeddings.vector",
            top_k=10
        )
    
    # Graph traversal
    if "graph" in methods:
        # Find sections that share processing patterns
        results["graph"] = await query_impl(
            query="""
            FOR pattern IN section_patterns
              FILTER pattern.pattern_type IN @issue_types
              FOR section IN 1..2 INBOUND pattern processing_edges
                FILTER section._key != @current_key
                COLLECT similar = section WITH COUNT INTO occurrences
                SORT occurrences DESC
                LIMIT 10
                RETURN {
                  section: similar,
                  shared_patterns: occurrences
                }
            """,
            bind_vars={
                "issue_types": detect_issues(section),
                "current_key": section.get("_key", "")
            }
        )
    
    return results
```

## Tool Journey Analytics

### Finding Optimal Processing Sequences
```javascript
// Find the most successful tool sequences for similar sections
FOR section IN pdf_sections
  FILTER section.quality.accuracy_score > 0.90
  FILTER "technical_specification" IN section.tags
  LET journey = section.tool_journey
  COLLECT sequence = journey.steps[*].method WITH COUNT INTO occurrences
  FILTER occurrences > 5
  SORT occurrences DESC
  RETURN {
    tool_sequence: sequence,
    usage_count: occurrences,
    avg_duration: AVG(FOR s IN pdf_sections 
                      FILTER s.tool_journey.steps[*].method == sequence 
                      RETURN s.tool_journey.total_duration)
  }
```

### Performance Optimization Analysis
```javascript
// Identify slow processing steps
FOR section IN pdf_sections
  FOR step IN section.tool_journey.steps
    FILTER step.duration > 0.5  // Steps taking more than 500ms
    COLLECT tool = step.tool, method = step.method 
    AGGREGATE 
      avg_duration = AVG(step.duration),
      max_duration = MAX(step.duration),
      occurrences = COUNT(1)
    SORT avg_duration DESC
    RETURN {
      tool: tool,
      method: method,
      avg_duration: avg_duration,
      max_duration: max_duration,
      occurrences: occurrences,
      optimization_needed: avg_duration > 1.0
    }
```

### Error Pattern Detection
```javascript
// Find common failure patterns in tool journeys
FOR section IN pdf_sections
  FILTER section.tool_journey.success == false
  FOR step IN section.tool_journey.steps
    FILTER step.status == "failed"
    COLLECT error_pattern = {
      tool: step.tool,
      method: step.method,
      error: step.error
    } WITH COUNT INTO failure_count
    FILTER failure_count > 3
    SORT failure_count DESC
    RETURN {
      pattern: error_pattern,
      failure_count: failure_count,
      common_context: (
        FOR s IN pdf_sections
          FOR st IN s.tool_journey.steps
            FILTER st.tool == error_pattern.tool 
            AND st.method == error_pattern.method
            AND st.status == "failed"
            RETURN DISTINCT s.raw.issues_detected
      )
    }
```

## Benefits of This Approach

1. **Complete History**: Every processing decision is recorded with rationale
2. **Multi-Modal Search**: BM25 for keywords, semantic for meaning, graph for patterns
3. **Learning Optimization**: Frequently successful patterns can be cached
4. **Quality Improvement**: Track which changes improve accuracy
5. **Debugging**: Full audit trail of what changed and why
6. **Tool Journey Analysis**: Optimize processing sequences based on historical performance
7. **Error Prevention**: Learn from past failures to avoid repeated mistakes

## Usage in pdf-section-cleaner

```python
# Before processing, find similar sections
similar = await find_similar_sections_multi_method(
    raw_section,
    methods=["bm25", "semantic", "graph"]
)

# Apply learned patterns
if similar["graph"]:
    # Use patterns that worked for similar sections
    successful_changes = extract_successful_patterns(similar["graph"])
    apply_patterns(raw_section, successful_changes)

# After processing, store with learning context
await store_section_with_learning(
    raw_section=original,
    cleaned_section=result,
    changes=change_log,
    confidence=overall_confidence
)
```

This schema enables the system to learn from every processed section and continuously improve accuracy through pattern recognition and reuse.