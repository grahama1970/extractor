# PDF Block Fixer Sub-Agent Prompt

You are analyzing suspicious PDF blocks from batch file: `{batch_file}`

## Your Task

Analyze each suspicious block in the batch and determine the correct action to fix extraction errors.

### Step 1: Read the Batch File

Read the JSON file at the path provided. It contains:
- `batch_id`: The batch number
- `suspicious_blocks`: Array of blocks to analyze
- Each block has:
  - `uuid`: Unique identifier (CRITICAL for write-back)
  - `block`: The suspicious block data
  - `context`: Extended context with:
    - `before_2`: Block 2 positions before (may be null)
    - `before_1`: Block 1 position before (may be null)
    - `after_1`: Block 1 position after (may be null)
    - `after_2`: Block 2 positions after (may be null)

### Step 2: Analyze Each Suspicious Block

For each suspicious block, examine:

1. **The block itself**:
   - `text`: The extracted text
   - `type`: Current classification (often wrong)
   - `issues`: Why it was flagged as suspicious
   - `page`: Page number for context
   - `uuid`: Unique identifier for tracking

2. **Extended context blocks** (2-5 blocks around):
   - `before_2`: Two blocks before (check for patterns)
   - `before_1`: One block before (immediate context)
   - `after_1`: One block after (continuation check)
   - `after_2`: Two blocks after (pattern completion)
   - Use ALL context to understand document structure

### Step 3: Determine the Correct Action

Choose ONE action per block:

#### `merge_with_next`
- Use when text clearly continues in the next block
- Examples:
  - "4.1.5.4. BHT (Branch History" → "Table) submodule"
  - "Figure 3.2: System" → "Architecture Diagram"
- Provide `new_text` combining both blocks
- Specify `new_type` (usually SectionHeader)

#### `merge_with_previous`
- Use when this block completes the previous one
- Examples:
  - Previous: "Section 2.3", Current: "Overview"
  - Previous ends with "(", Current starts with ")"
- This block will be deleted (merged into previous)

#### `reclassify`
- Use when only the type is wrong
- Examples:
  - "4.1.5.4. System Design" typed as Text → SectionHeader
  - "• Item one" typed as Text → ListItem
- Specify `new_type` only

#### `none`
- Use when no action needed
- Block is correctly classified despite being suspicious

### Step 4: Common Patterns to Recognize

1. **Split Headers** (most common):
   ```
   Block: "4.1.5.4. BHT (Branch History"
   Next: "Table) submodule"
   Action: merge_with_next
   ```

2. **Orphaned Words**:
   ```
   Prev: "4.2.3. Cache"
   Block: "Interface"
   Action: merge_with_previous
   ```

3. **Numbered Lists Split**:
   ```
   Block: "1. First item"
   Next: "2. Second item"
   Action: none (both are correct)
   ```

4. **Table Continuations**:
   ```
   Block: "Signal|Type|Description" (Table)
   Next: "clk|logic|Clock signal" (Table)
   Action: none (correct as separate rows)
   ```

### Step 5: Create Your Decisions

Save your analysis to: `/tmp/pdf_batches/batch_{batch_id:03d}_decisions.json`

Format:
```json
{
  "batch_id": {batch_id},
  "decisions": [
    {{
      "uuid": "block-uuid-here",
      "action": "merge_with_next|merge_with_previous|reclassify|none",
      "new_type": "SectionHeader|Text|Table|Figure|ListItem",  // if changing type
      "new_text": "Combined text here",  // if merging
      "reason": "Clear explanation of why this action",
      "confidence": 0.95  // 0.0 to 1.0
    }}
  ]
}
```

### Important Notes

1. **UUID is Critical**: Always use the exact UUID from the block
2. **One Action Per Block**: Each block gets exactly one decision
3. **Preserve Content**: Never lose information when merging
4. **Section Headers**: Look for patterns like "X.Y.Z. Title"
5. **Be Conservative**: If unsure, use "none"

### Example Analysis

Given:
```json
{{
  "uuid": "abc-123",
  "index": 42,
  "block": {{
    "uuid": "abc-123",
    "text": "4.1.5.4. BHT (Branch History",
    "type": "Text",
    "page": 22,
    "issues": ["incomplete_sentence"]
  }},
  "context": {{
    "before_2": {{"text": "The CPU architecture includes:", "type": "Text"}},
    "before_1": {{"text": "multiple subsystems as follows:", "type": "Text"}},
    "after_1": {{"text": "Table) submodule", "type": "Text"}},
    "after_2": {{"text": "The BHT uses a 2-bit saturating counter", "type": "Text"}}
  }}
}}
```

Decision:
```json
{{
  "uuid": "abc-123",
  "action": "merge_with_next",
  "new_type": "SectionHeader",
  "new_text": "4.1.5.4. BHT (Branch History Table) submodule",
  "reason": "Split section header with parentheses",
  "confidence": 0.98
}}
```

Now analyze the batch file and create your decisions.