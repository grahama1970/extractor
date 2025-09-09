# PDF Suspicious Fixer Sub-Agent Prompt

You are analyzing remaining suspicious blocks that weren't fixed by batch processing.

## Your Task

Fix the final suspicious blocks using pattern recognition and contextual analysis.

### Input Format

You will receive a JSON file with blocks that may still be marked as suspicious:
```json
{
  "blocks": [
    {
      "block_id": 42,
      "uuid": "abc-123",
      "type": "Text",
      "text": "Interface",
      "page": 5,
      "suspicious": true,
      "issues": ["orphaned_word"],
      "metadata": {}
    }
  ]
}
```

### Step 1: Identify Remaining Issues

Scan for blocks where `suspicious == true`. Common patterns include:

1. **Orphaned Words**
   - Single capitalized words like "Interface", "Architecture"
   - Usually should merge with previous header
   - Check if previous block is a SectionHeader

2. **Floating Punctuation**
   - Blocks containing only ",", ".", ":", etc.
   - Always merge with previous block

3. **Continued Sentences**
   - Blocks starting with lowercase letters
   - Missing capital indicates continuation
   - Merge with previous block

4. **Split List Items**
   - Blocks starting with bullets or numbers: "•", "-", "1."
   - If very short, likely incomplete
   - Check next block for continuation

5. **Isolated Table Headers**
   - Pipe-separated text: "Name|Type|Description"
   - Not preceded by table blocks
   - Reclassify as Table type

### Step 2: Apply Fixes

For each suspicious block, determine the fix:

#### Merge with Previous
```json
{
  "block_id": 42,
  "action": "merge_with_previous",
  "reason": "Orphaned word 'Interface' belongs with header 'Cache'"
}
```

#### Merge with Next
```json
{
  "block_id": 43,
  "action": "merge_with_next",
  "reason": "Incomplete list item '1.' continues in next block"
}
```

#### Reclassify Type
```json
{
  "block_id": 44,
  "action": "reclassify",
  "new_type": "Table",
  "reason": "Pipe-separated text indicates table header"
}
```

#### Keep As-Is
```json
{
  "block_id": 45,
  "action": "none",
  "reason": "Legitimate short text block"
}
```

### Step 3: Context Rules

Consider these contextual clues:

1. **Previous Block Type**
   - If previous is SectionHeader → likely merge candidate
   - If previous is Table → current might be table continuation
   - If previous ends with ":" → current likely continues

2. **Next Block Type**
   - If next starts lowercase → current might be incomplete
   - If next is similar type → consider grouping

3. **Page Boundaries**
   - Be cautious at page transitions
   - Check page numbers before merging

4. **Text Length**
   - Very short (<5 chars) → likely needs merging
   - Single words → check if title/header fragment

### Step 4: Create Fix Instructions

Save your fixes to: `{output_file}`

Format:
```json
{
  "fixes": [
    {
      "block_id": 42,
      "uuid": "abc-123",
      "action": "merge_with_previous",
      "target_block_id": 41,
      "new_text": "4.1.5.5. Cache Interface",
      "reason": "Orphaned word completes section header",
      "confidence": 0.95
    },
    {
      "block_id": 43,
      "action": "delete",
      "reason": "Floating comma merged into previous",
      "confidence": 0.99
    },
    {
      "block_id": 44,
      "action": "reclassify",
      "new_type": "Table",
      "reason": "Table header pattern detected",
      "confidence": 0.90
    }
  ],
  "summary": {
    "total_suspicious": 15,
    "fixes_proposed": 12,
    "blocks_to_delete": 3,
    "blocks_to_merge": 8,
    "blocks_to_reclassify": 1
  }
}
```

### Important Guidelines

1. **Conservative Approach**: If unsure, mark confidence < 0.7
2. **Preserve Information**: Never lose text during merges
3. **Maintain Order**: Don't reorder blocks
4. **Check Boundaries**: Verify array bounds before merging
5. **Update Metadata**: Add fix information to metadata field

### Common Pitfalls to Avoid

1. **Don't merge across major section boundaries**
2. **Don't merge if it creates nonsensical text**
3. **Don't delete blocks with substantial content**
4. **Don't change type if content doesn't match**
5. **Don't merge blocks from different pages without checking continuity**

### Example Analysis

Given:
```
Block 41: [SectionHeader] "4.1.5.5. Cache"
Block 42: [Text] "Interface" (suspicious: orphaned_word)
Block 43: [Text] "The cache interface provides..."
```

Fix:
```json
{
  "block_id": 42,
  "action": "merge_with_previous",
  "new_text": "4.1.5.5. Cache Interface",
  "reason": "Orphaned word 'Interface' completes the section header",
  "confidence": 0.95
}
```

Now analyze the suspicious blocks and provide fixes.