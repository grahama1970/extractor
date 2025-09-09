# Main Agent Batching Strategy for PDF Section Processing

**Date:** July 29, 2025  
**Purpose:** Define optimal batching strategies for main agent to orchestrate pdf-section-cleaner calls

## Overview

For a 50-section PDF, the main agent needs an efficient strategy to batch section cleaning operations. We have several approaches, each with trade-offs.

## Strategy 1: Direct Parallel Batching with jq

The main agent uses jq to create batches and spawns multiple sub-agents:

```bash
# Extract sections into batches of 10
sections=$(cat extracted_sections.json | jq -r '.sections')
total_sections=$(echo "$sections" | jq 'length')

# Process in batches of 10
for i in $(seq 0 10 $((total_sections-1))); do
    echo "Processing sections $i to $((i+9))..."
    
    # Create batch
    batch=$(echo "$sections" | jq ".[$i:$((i+10))]")
    
    # Spawn 10 parallel sub-agent calls
    for j in $(seq 0 9); do
        section=$(echo "$batch" | jq ".[$j]")
        if [ "$section" != "null" ]; then
            # Launch sub-agent in background
            claude -p "Use pdf-section-cleaner to analyze this section: $section" > "section_${i}_${j}.json" &
        fi
    done
    
    # Wait for batch completion
    wait
    
    echo "Batch complete. Proceeding to next..."
done
```

**Pros:**
- Simple to implement
- Direct parallelism control
- No intermediate storage needed

**Cons:**
- Limited error handling
- No progress tracking
- Difficult to resume if interrupted

## Strategy 2: ArangoDB Queue-Based Processing (RECOMMENDED)

Store sections in ArangoDB and use it as a work queue:

### Setup Phase
```python
# Main agent stores all sections in ArangoDB
async def store_sections_for_processing(pdf_id: str, sections: List[Dict]):
    """Store sections in ArangoDB with processing status."""
    
    # Create processing job
    job = {
        "_key": f"job_{pdf_id}",
        "pdf_id": pdf_id,
        "total_sections": len(sections),
        "status": "pending",
        "created_at": datetime.now().isoformat()
    }
    await upsert_impl(collection="pdf_jobs", document=job)
    
    # Store each section
    for section in sections:
        section_doc = {
            "_key": f"{pdf_id}_section_{section['id']}",
            "job_id": pdf_id,
            "section_id": section["id"],
            "status": "pending",
            "data": section,
            "created_at": datetime.now().isoformat()
        }
        await upsert_impl(collection="pdf_sections", document=section_doc)
        
        # Create edge: job -> section
        await edge_impl(
            from_collection="pdf_jobs",
            from_key=f"job_{pdf_id}",
            to_collection="pdf_sections", 
            to_key=section_doc["_key"],
            edge_type="has_section"
        )
```

### Batch Processing Phase
```python
async def process_sections_in_batches(pdf_id: str, batch_size: int = 10):
    """Process sections in batches using ArangoDB as queue."""
    
    while True:
        # Get next batch of pending sections
        query = """
        FOR section IN pdf_sections
            FILTER section.job_id == @job_id
            FILTER section.status == "pending"
            LIMIT @batch_size
            UPDATE section WITH {status: "processing"} IN pdf_sections
            RETURN NEW
        """
        
        batch = await query_impl(
            query=query,
            bind_vars={"job_id": pdf_id, "batch_size": batch_size}
        )
        
        if not batch:
            break  # No more pending sections
        
        # Process batch in parallel
        tasks = []
        for section_doc in batch:
            task = process_single_section(section_doc)
            tasks.append(task)
        
        # Wait for batch completion
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Update statuses
        for section_doc, result in zip(batch, results):
            if isinstance(result, Exception):
                await update_section_status(section_doc["_key"], "failed", str(result))
            else:
                await update_section_status(section_doc["_key"], "completed", result)
```

### Individual Section Processing
```python
async def process_single_section(section_doc: Dict) -> Dict:
    """Process a single section with pdf-section-cleaner."""
    
    # Call pdf-section-cleaner sub-agent
    prompt = f"""
    Use pdf-section-cleaner to analyze this section:
    {json.dumps(section_doc['data'], indent=2)}
    
    Return the cleaned section data.
    """
    
    # In production, this would be actual sub-agent call
    result = await call_subagent("pdf-section-cleaner", prompt)
    
    # Store cleaned result
    cleaned_doc = {
        "_key": f"cleaned_{section_doc['_key']}",
        "original_key": section_doc["_key"],
        "cleaned_data": result,
        "processed_at": datetime.now().isoformat()
    }
    await upsert_impl(collection="pdf_sections_cleaned", document=cleaned_doc)
    
    return result
```

### Progress Monitoring
```python
async def get_job_progress(pdf_id: str) -> Dict:
    """Get current processing progress."""
    
    query = """
    LET job = DOCUMENT("pdf_jobs", @job_key)
    LET sections = (
        FOR section IN pdf_sections
            FILTER section.job_id == @job_id
            COLLECT status = section.status WITH COUNT INTO count
            RETURN {status: status, count: count}
    )
    RETURN {
        job: job,
        progress: sections,
        percentage: (
            FOR s IN sections
                FILTER s.status == "completed"
                RETURN s.count / job.total_sections * 100
        )[0]
    }
    """
    
    return await query_impl(
        query=query,
        bind_vars={"job_id": pdf_id, "job_key": f"job_{pdf_id}"}
    )
```

## Strategy 3: Hybrid Task List with Progress Tracking

Combine natural language task list with progress tracking:

```
Main Agent Task List:

1. Store all sections in ArangoDB with status "pending"
2. Create job tracker in ArangoDB

3. Process batch 1 (sections 0-9):
   - Query ArangoDB for 10 pending sections
   - Mark as "processing"
   - Call pdf-section-cleaner for each section (parallel)
   - Update status to "completed" or "failed"
   - Store cleaned results

4. Check progress: 10/50 completed (20%)

5. Process batch 2 (sections 10-19):
   [Same process]

...continue until all sections processed...

N. Aggregate all cleaned sections from ArangoDB
N+1. Build final document structure
```

## Recommended Approach: ArangoDB Queue

**Why ArangoDB Queue is Best:**

1. **Resilience**: Can resume from interruptions
2. **Monitoring**: Real-time progress tracking
3. **Error Handling**: Failed sections can be retried
4. **Scalability**: Easy to adjust batch size
5. **Debugging**: Complete audit trail in database
6. **Flexibility**: Can prioritize certain sections

**Implementation in Main Agent:**

```python
# Main agent's orchestration
async def orchestrate_pdf_cleaning(pdf_path: Path):
    # 1. Extract with Marker
    sections = await extract_sections(pdf_path)
    
    # 2. Store in ArangoDB
    job_id = await store_sections_for_processing(pdf_path.stem, sections)
    
    # 3. Process in batches
    await process_sections_in_batches(job_id, batch_size=10)
    
    # 4. Retrieve cleaned sections
    cleaned = await get_all_cleaned_sections(job_id)
    
    # 5. Build final structure
    final_doc = await build_document_structure(cleaned)
    
    return final_doc
```

## Performance Considerations

| Strategy | Setup Time | Processing Time | Error Recovery | Monitoring |
|----------|------------|-----------------|----------------|------------|
| Direct jq batching | Low | Fast | Poor | Limited |
| ArangoDB queue | Medium | Fast | Excellent | Real-time |
| Hybrid approach | Low | Fast | Good | Good |

## Conclusion

The ArangoDB queue approach provides the best balance of:
- **Reliability**: Automatic failure recovery
- **Visibility**: Progress monitoring
- **Flexibility**: Dynamic batch sizing
- **Integration**: Leverages existing Knowledge Architect

For production PDF processing, use the ArangoDB queue strategy with 10-section batches for optimal performance and reliability.