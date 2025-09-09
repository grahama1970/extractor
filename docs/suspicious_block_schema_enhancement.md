# Suspicious Block Schema Enhancement

## Overview

The block schema in `/src/extractor/core/schema/blocks/base.py` has been enhanced to support suspicious block detection during the extraction process, rather than in post-processing.

## Enhanced Fields

### Core Fields

- **`is_suspicious`**: `bool = False` - Whether this block has quality issues
- **`suspicious_reasons`**: `List[str]` - Multiple reasons why the block is suspicious
- **`suspicion_confidence`**: `Optional[float]` - Confidence that block is suspicious (0.0-1.0)
- **`confidence`**: `Optional[float]` - Surya/extraction confidence score (0.0-1.0)
- **`quality_score`**: `Optional[float]` - Overall quality assessment score
- **`requires_review`**: `bool = False` - Whether human/LLM review is needed
- **`validation_metadata`**: `Dict[str, Any]` - Additional validation data (e.g., pattern matches)

## New Methods

### `mark_suspicious(reason: str, confidence: float = 0.8, metadata: Optional[Dict[str, Any]] = None)`

Marks a block as suspicious with a reason and confidence score.

```python
block.mark_suspicious(
    reason="header_ends_with_comma",
    confidence=0.9,
    metadata={"pattern": "ends_with_comma", "text": "Introduction,"}
)
```

Features:
- Adds reason to list (no duplicates)
- Updates suspicion confidence (takes highest)
- Stores metadata for later analysis
- Automatically sets `requires_review=True` if confidence >= 0.7

### `clear_suspicion()`

Clears all suspicion flags and reasons.

```python
block.clear_suspicion()
```

### `calculate_quality_score() -> float`

Calculates overall quality score based on extraction confidence and suspicion level.

```python
score = block.calculate_quality_score()
# Returns 0.0-1.0, where lower scores indicate more issues
```

Algorithm:
- Starts with extraction confidence (or 0.5 if not set)
- Reduces by up to 50% based on suspicion confidence
- Further reduces by 10% per additional suspicion reason (max 30%)

### `get_suspicion_summary() -> Dict[str, Any]`

Returns a comprehensive summary of the block's suspicion status.

```python
summary = block.get_suspicion_summary()
# Returns:
# {
#     "is_suspicious": True,
#     "reasons": ["header_ends_with_comma", "starts_with_lowercase"],
#     "suspicion_confidence": 0.9,
#     "extraction_confidence": 0.85,
#     "quality_score": 0.42,
#     "requires_review": True,
#     "metadata": {...}
# }
```

## Usage in Processors

Processors can now mark blocks as suspicious during extraction:

```python
# In a processor analyzing a potential section header
if text.endswith(','):
    block.mark_suspicious(
        "header_ends_with_comma",
        confidence=0.85,
        metadata={"text": text, "position": "end"}
    )

# For low Surya confidence
if block.confidence < 0.5:
    block.mark_suspicious(
        "low_extraction_confidence",
        confidence=0.9,
        metadata={"surya_confidence": block.confidence}
    )

# For merged table data
if is_merged_text(text):
    block.mark_suspicious(
        "merged_table_headers",
        confidence=0.8,
        metadata={"detected_words": split_merged_text(text)}
    )
```

## Benefits

1. **Early Detection**: Issues are caught during extraction when context is richest
2. **Better Accuracy**: Combines Surya confidence with heuristic patterns
3. **Reduced Pipeline Steps**: No need for separate suspicious block detection step
4. **Richer Metadata**: Stores reasons and context for later analysis
5. **Quality Scoring**: Provides quantitative measure of block reliability

## Migration Path

1. Update processors to use `mark_suspicious()` during extraction
2. Migrate detection logic from `poc_03_identify_suspicious_blocks.py`
3. Simplify pipeline by removing redundant post-processing steps
4. Use `requires_review` flag to route blocks for LLM analysis

## Next Steps

1. Integrate suspicious detection logic into core processors:
   - TextProcessor
   - TableProcessor  
   - SectionHeaderProcessor
2. Add Surya confidence thresholds
3. Port heuristics from POC implementation
4. Update pipeline to use block quality scores