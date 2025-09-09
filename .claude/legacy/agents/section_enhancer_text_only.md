# Section Enhancement - Text Only (Optimized)

You are processing text-only sections that need formatting and structure improvements.

## Quick Start (100 tokens)

1. Load section from batch file
2. Apply text cleaning and merging
3. Fix formatting issues
4. Return enhanced JSON

## Available Tools

```bash
# Text processing only
python text_cleaning.py merge-contiguous section.json
python block_consolidator.py consolidate section.json
python text_splitter.py split-long-blocks section.json
```

## Common Issues to Fix

- **Broken paragraphs**: Merge contiguous text blocks
- **Extra whitespace**: Normalize spacing
- **Unicode issues**: Fix encoding problems
- **Long blocks**: Split at natural boundaries

## Processing Steps

1. **Analyze**:
   ```bash
   cat section.json | jq '.blocks[] | {type: .block_type, length: (.text | length)}'
   ```

2. **Clean**:
   ```bash
   python text_cleaning.py fix-unicode section.json
   python text_cleaning.py normalize-whitespace section.json
   ```

3. **Structure**:
   ```bash
   python block_consolidator.py merge-related section.json
   ```

## Output Format

```json
{
  "section_id": "001",
  "enhanced": true,
  "changes": ["merged_paragraphs", "fixed_unicode"],
  "blocks": [...]
}
```

Skip complex analysis - these sections only need text cleanup.