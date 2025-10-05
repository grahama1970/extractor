# Table Fusion Module

## Overview

The table fusion module provides multi-strategy table candidate abstraction with optional learned calibration for improved table extraction accuracy.

## Purpose

When extracting tables from PDFs, multiple strategies (lattice, stream, network) often produce different results for the same table. The fusion module:

1. **Aggregates candidates** from multiple extraction strategies
2. **Selects the best representation** using composite scoring
3. **Merges split tables** (header/body patterns across pages)
4. **Computes rich confidence features** for downstream calibration

## Key Features

### 1. Single Candidate Pass-Through
When only one extraction strategy succeeds, the result passes through unchanged with metadata added.

### 2. Multi-Candidate Fusion
Selects best candidate based on:
- Primary: extraction score
- Secondary: data density (non-empty cell ratio)
- Penalty: fragmentation score

### 3. Header+Body Merge Detection
Automatically detects and merges split tables:
- Header table: single row with column names
- Body table: multiple data rows
- Criteria: horizontal alignment (>50% bbox overlap), adjacent pages

### 4. Confidence Diagnostics
Computes structured confidence components:
- **structure_prob**: Learned calibrator probability (optional)
- **fragmentation**: Inverted fragmentation score (lower frag = higher confidence)
- **header_jaccard**: Column name consistency across candidates
- **numeric_stability**: Variance in numeric cell counts
- **strategy_diversity**: Number of unique strategies used

## Usage

### Basic Usage

```python
from extractor.pipeline.utils.table_fusion import fuse_table_candidates, TableCandidate

# Create candidates from different strategies
candidates = [
    TableCandidate(
        pandas_df=[{"Signal": "valid_i", "IO": "I", "Type": "input"}],
        bbox=[100, 200, 500, 300],
        page_index=0,
        strategy="lattice",
        score=85.0,
        fragmentation_score=0.12,
        camelot_metrics={"accuracy": 92.5, "whitespace": 8.3},
        pandas_metrics={"shape": [1, 3], "data_density": 0.95}
    ),
    TableCandidate(
        pandas_df=[{"Signal": "valid_i", "IO": "I", "Type": "input"}],
        bbox=[100, 200, 500, 300],
        page_index=0,
        strategy="stream",
        score=78.0,
        fragmentation_score=0.18,
        camelot_metrics={"accuracy": 88.0, "whitespace": 12.0},
        pandas_metrics={"shape": [1, 3], "data_density": 0.88}
    ),
]

# Fuse candidates
result = fuse_table_candidates(candidates)

print(f"Merge type: {result['merge_type']}")
print(f"Source strategies: {result['source_strategies']}")
print(f"Confidence: {result['confidence']}")
```

### Output Structure

```json
{
  "pandas_df": [{"Signal": "valid_i", "IO": "I", "Type": "input"}],
  "bbox": [100, 200, 500, 300],
  "page_index": 0,
  "merge_type": "multi_best",
  "confidence": {
    "structure_prob": null,
    "fragmentation": 0.88,
    "header_jaccard": 1.0,
    "numeric_stability": 0.95,
    "strategy_diversity": 2
  },
  "source_strategies": ["lattice", "stream"],
  "camelot_metrics": {"accuracy": 92.5, "whitespace": 8.3},
  "pandas_metrics": {"shape": [1, 3], "data_density": 0.95}
}
```

## Environment Variables

### TABLE_CALIBRATOR_PATH

Path to pickled scikit-learn model for structure probability prediction.

```bash
export TABLE_CALIBRATOR_PATH="/path/to/calibrator.pkl"
```

**Model Requirements:**
- Must have `.predict_proba(X)` method
- Input features (6D vector):
  - fragmentation_score
  - header_jaccard_max
  - numeric_stability
  - row_count
  - col_count
  - strategy_diversity
- Output: Binary probability [P(bad), P(good)]
  - Returns P(good table) as structure_prob

If not set or file doesn't exist, `structure_prob` will be `None` (graceful degradation).

### TABLE_FUSION_DISABLE (Future)

Set to "1" to bypass fusion logic and use original single-best selection.

```bash
export TABLE_FUSION_DISABLE=1
```

*Note: Not yet implemented. Placeholder for rollback mechanism.*

## Integration with Stage 05

In Stage 05 (table_extractor.py), replace single-best selection:

```python
# Before (single best)
best_table = max(tables, key=lambda t: t.score)

# After (fusion)
from extractor.pipeline.utils.table_fusion import TableCandidate, fuse_table_candidates

candidates = [
    TableCandidate(
        pandas_df=table.df.to_dict("records"),
        bbox=table._bbox,
        page_index=page_num,
        strategy=strategy_name,
        score=table.accuracy,
        fragmentation_score=compute_fragmentation(table),
        camelot_metrics=extract_camelot_metrics(table),
        pandas_metrics=compute_pandas_metrics(table.df)
    )
    for table, strategy_name in strategy_results
]

fused_result = fuse_table_candidates(candidates)
```

## Confidence Calibration (Future)

### Training a Calibrator

1. **Collect Gold Standard Dataset**
   - Human-annotated tables with quality labels (good/bad)
   - Extract features from candidate sets

2. **Train Logistic Regression Model**
   ```python
   from sklearn.linear_model import LogisticRegression
   import pickle
   
   # Features: [frag, jaccard, num_stab, rows, cols, diversity]
   X_train = np.array([...])
   y_train = np.array([...])  # 0=bad, 1=good
   
   model = LogisticRegression()
   model.fit(X_train, y_train)
   
   # Save
   with open("calibrator.pkl", "wb") as f:
       pickle.dump(model, f)
   ```

3. **Deploy**
   ```bash
   export TABLE_CALIBRATOR_PATH="/path/to/calibrator.pkl"
   ```

### Expected Impact

- **Without calibrator**: Confidence based on heuristics (fragmentation, consistency)
- **With calibrator**: Confidence includes learned probability from labeled data
- **Target**: 90-95% accuracy on 1000+ page engineering/scientific PDFs

## Merge Type Semantics

| Merge Type | Description | Trigger Condition |
|------------|-------------|-------------------|
| `empty` | No candidates | `len(candidates) == 0` |
| `single` | Single candidate pass-through | `len(candidates) == 1` |
| `header_body_merge` | Header+body tables merged | Pattern detected: 1-row + multi-row, aligned |
| `multi_best` | Best selected from multiple | Multiple candidates, no merge pattern |

## Backward Compatibility

All existing fields are preserved:
- `pandas_df`: Table data (list of row dicts)
- `bbox`: Bounding box
- `page_index`: Page number
- `camelot_metrics`: Camelot's accuracy/whitespace/order
- `pandas_metrics`: Shape, density, etc.

New fields are **additive only**:
- `merge_type`: Fusion strategy used
- `confidence`: Rich confidence diagnostics
- `source_strategies`: List of strategies involved

Downstream consumers can safely ignore new fields.

## Feature Roadmap

### Planned Enhancements
- [ ] pdfplumber candidate integration
- [ ] ML-based table region detection
- [ ] Cross-page table continuation detection
- [ ] Figure-table disambiguation
- [ ] Confidence recalibration based on downstream validation

### Future Considerations
- Adaptive strategy selection based on document type
- Multi-model ensemble for structure_prob
- Real-time calibrator updates via feedback loop

## Testing

Unit tests cover:
- ✅ Single candidate pass-through
- ✅ Header+body merge detection
- ✅ Multi-candidate best selection
- ✅ Confidence component computation
- ✅ Calibrator loading (graceful failure)
- ✅ Backward compatibility

Run tests:
```bash
pytest tests/unit/test_table_fusion.py -v
```

## References

- **Camelot**: https://camelot-py.readthedocs.io/
- **Geometric Mean**: https://en.wikipedia.org/wiki/Geometric_mean
- **Jaccard Index**: https://en.wikipedia.org/wiki/Jaccard_index

## Support

For issues or questions:
1. Check existing unit tests for usage examples
2. Review confidence component definitions above
3. Open GitHub issue with minimal reproducible example

---

**Module Status**: ✅ Implemented, Tested, Ready for Stage 05 Integration
