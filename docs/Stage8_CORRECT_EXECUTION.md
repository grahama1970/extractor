# Stage 8: Correct Agent Execution (No claude -p)

## How Stage 8 Actually Works

I (the PDF extraction orchestrator agent) execute enhancement tasks directly from the task list.

## Step 1: Create Batches

```bash
$ python section_enhancer_orchestrator.py create-batches sections.json
```

This creates enriched batches with metadata at `/tmp/section_batches/`:
- `batch_table_001.json` - Table-heavy sections with enriched metadata
- `batch_text_001.json` - Text-only sections
- `batch_mixed_001.json` - Complex sections

## Step 2: Generate Task Lists

Using `section_enhancer_tasklist.md`, I generate task lists for each batch:

### Example Task List for batch_table_001.json

```markdown
# Enhancement Tasks - Batch table_20241115_143022

## Section 004 (BHT submodule)
**Metadata Summary**: BHT spec section with split header text and low-quality table extraction
**Complexity**: medium

☐ Split header detected: '4.1.5.4. BHT (Branch History' + 'Table) submodule'
  ```bash
  python text_cleaning.py merge-contiguous section_004.json
  ```
  Expected: Merged header text

☐ marker_confidence 0.67 < 0.7, has_borders=true
  ```bash
  python camelot_extractor.py extract-tables doc.pdf --page 0 --lattice
  ```
  Expected: 0.67 → 0.90+

☐ Annotation: 'Merge Table', continuation detected
  ```bash
  python table_merger_worker.py merge t4.json t5.json
  ```
  Expected: Human annotation satisfied
```

## Step 3: I Execute Each Task Directly

As the agent, I execute each task in the list:

### Task 1: Merge Split Header
```bash
$ python text_cleaning.py merge-contiguous section_004.json

# Output:
Successfully merged split header:
  Before: '4.1.5.4. BHT (Branch History' + 'Table) submodule'
  After: '4.1.5.4. BHT (Branch History Table) submodule'
Output saved to: section_004_merged.json
```

### Task 2: Extract Table with Camelot
```bash
$ python camelot_extractor.py extract-tables doc.pdf --page 0 --lattice

# Output:
Extracting tables from page 0 using lattice mode...
Table confidence: 0.91 (improved from 0.67)
Headers: ['Signal', 'I/O', 'Description', 'Connection', 'Type']
Output saved to: table_page0.json
```

### Task 3: Merge Tables
```bash
$ python table_merger_worker.py merge t4.json t5.json

# Output:
Merging tables based on annotation "Merge Table"
Result: 8 rows total
Output saved to: merged_table.json
```

## Step 4: Build Enhanced Section

After executing all tasks, I construct the enhanced section:

```json
{
  "section_id": "004",
  "actions_taken": [
    {
      "task": "python text_cleaning.py merge-contiguous section_004.json",
      "result": "success",
      "output": "Merged header: '4.1.5.4. BHT (Branch History Table) submodule'"
    },
    {
      "task": "python camelot_extractor.py extract-tables doc.pdf --page 0 --lattice",
      "result": "success", 
      "output": "Extracted table with 0.91 confidence"
    },
    {
      "task": "python table_merger_worker.py merge t4.json t5.json",
      "result": "success",
      "output": "Merged to 8-row table"
    }
  ],
  "enhanced_blocks": [
    {
      "block_id": 0,
      "block_type": "SectionHeader",
      "text": "4.1.5.4. BHT (Branch History Table) submodule",
      "confidence": 0.95
    },
    // ... rest of enhanced blocks
  ]
}
```

## Step 5: Apply All Enhancements

```bash
$ python section_enhancer_orchestrator.py apply-enhancements sections.json

# This merges all enhanced sections back into the original structure
```

## Key Points

1. **I execute tasks directly** - No spawning new Claude instances
2. **Metadata drives everything** - Pre-computed in enrichment phase
3. **Task list is executable** - Each checkbox is a command I run
4. **Concurrent execution** - I can run multiple tasks in parallel
5. **Real tool execution** - Actual Python scripts, not simulations

## The Complete Flow

```
1. Orchestrator enriches sections with metadata
   ↓
2. Orchestrator creates batches 
   ↓
3. I generate task lists from metadata
   ↓
4. I execute each task directly (python commands)
   ↓
5. I collect results and build enhanced sections
   ↓
6. Orchestrator applies enhancements back
```

This is why the metadata is so important - it pre-computes everything I need to execute successfully!