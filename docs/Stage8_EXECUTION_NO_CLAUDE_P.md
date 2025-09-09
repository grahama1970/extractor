# Stage 8 Execution Model - NO claude -p Calls

## The Key Understanding

When the task list says "Spawn CONCURRENT sub-agents", it does NOT mean spawning Claude instances with `claude -p`. Instead:

1. **I AM the agent executing the entire pipeline**
2. **"Sub-agents" are just conceptual groupings of tasks**
3. **I execute ALL tasks myself directly**

## How Stage 8 Actually Works

### Step 1: Create Batches (Python Command)
```bash
$ python section_enhancer_orchestrator.py create-batches sections.json

Created batches:
- /tmp/section_batches/batch_table_001.json
- /tmp/section_batches/batch_text_001.json
- /tmp/section_batches/batch_math_001.json
```

### Step 2: "Spawn CONCURRENT sub-agents" (Agent Task)

This task means I should:
1. Read `section_enhancer_tasklist.md` to understand the task format
2. Process each batch to generate tasks
3. Execute all generated tasks myself

For example, I process batch_table_001.json:

```python
# I read the batch and generate tasks based on metadata
tasks = [
    "python text_cleaning.py merge-contiguous section_004.json",
    "python camelot_extractor.py extract-tables doc.pdf --page 42",
    "python table_merger.py merge-blocks 4 5",
    # ... more tasks for other sections
]

# I execute these tasks myself
for task in tasks:
    # Execute using Bash tool
    result = bash(task)
```

### Step 3: Apply Enhancements (Python Command)
```bash
$ python section_enhancer_orchestrator.py apply-enhancements sections.json
```

## The Complete Pattern

```
Extract-PDF Agent (Me)
    │
    ├── Task: Create batches → Execute: python create-batches
    │
    ├── Task: "Spawn sub-agents" → I process batches myself:
    │   ├── Read batch_table_001.json
    │   ├── Generate task list from metadata
    │   ├── Execute: python text_cleaning.py ...
    │   ├── Execute: python camelot_extractor.py ...
    │   └── Execute: python table_merger.py ...
    │
    └── Task: Apply enhancements → Execute: python apply-enhancements
```

## NO claude -p Anywhere!

- ❌ NOT: `claude -p section_enhancer_tasklist.md`
- ✅ INSTEAD: I read the prompt logic and execute tasks myself
- ❌ NOT: Spawning separate Claude instances
- ✅ INSTEAD: I run all Python commands directly

## Stage 5.5 vs Stage 8 - Same Pattern

**Stage 5.5:**
- I create suspicious block batches
- I analyze each batch using `pdf_block_fixer_prompt.md` logic
- I write decisions and apply fixes

**Stage 8:**
- I create section enhancement batches
- I generate tasks using `section_enhancer_tasklist.md` logic
- I execute all tasks and apply enhancements

Both follow the same pattern - I do all the work myself, no `claude -p` calls!

## Why This Architecture Works

1. **Single Agent Control**: I maintain context across the entire pipeline
2. **No Subprocess Overhead**: No spawning separate Claude instances
3. **Direct Execution**: I run Python commands directly
4. **Metadata-Driven**: Pre-computed recommendations guide my actions
5. **Conceptual Parallelism**: Tasks can be executed concurrently by me

## Summary

The term "spawn sub-agents" in the task list is conceptual - it means I should:
- Process multiple batches of work
- Use specialized logic for each batch type
- Execute all resulting tasks myself
- NO `claude -p` commands ever!