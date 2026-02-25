# Classifier Model Assessment for Extractor

**Date**: 2026-02-07
**Status**: Assessment Complete
**Priority**: Medium-High

## Summary

The user suggested creating a small classifier model for the extractor project, similar to the `create-intent-map` skill in pi-mono. After analysis, this is a **valuable opportunity** that could improve debug-pdf, fixture-tricky, and debug-table.

## Recommended Classifier: Table Strategy Predictor

### Why This Model?

| Reason | Impact |
|--------|--------|
| Reduces fallback strategies in S05 | High - fewer retries = faster extraction |
| Currently S05 uses trial-and-error | Wastes compute on wrong strategies |
| Training data already exists | From /memory successful params |
| Small model (< 100MB) is sufficient | Can run on CPU, no GPU required |

### Architecture

```
Table Region Image (cropped from PDF)
    │
    ▼
┌─────────────────────────────────────────────┐
│  MobileNetV2/EfficientNet-B0 (pretrained)   │
│  + Custom Classification Head               │
└─────────────────────────────────────────────┘
    │
    ▼
Strategy Prediction
{
  "strategy": "lattice_sensitive",
  "line_scale": 15,
  "edge_tol": 300,
  "confidence": 0.92
}
```

### Training Data Sources

1. **Successful Extractions** (stored in /memory by S05)
   - PDF name, preset, strategy used, quality metrics
   - Already collecting via continuous learning (added today)

2. **Manual Annotations** (fixture-tricky)
   - Ground truth labels for adversarial tables

3. **Corpus Results** (12TB corpus)
   - Extraction logs with strategy outcomes

### Training Pipeline (Modeled on create-intent-map)

```
1. Data Preparation
   ├── Extract table region images from successful runs
   ├── Label with strategy that worked (no fallback)
   └── Split train/eval (85/15)

2. SFT Warmup (1 epoch)
   └── Initialize on confident predictions only

3. GRPO with Execution Feedback
   ├── Generate N strategy predictions
   ├── Execute Camelot with each
   └── Reward = quality_score * (1 - fallback_used)

4. Evaluation
   └── Measure strategy_accuracy, avg_quality
```

### Implementation Steps

| Phase | Task | Effort | Dependencies |
|-------|------|--------|--------------|
| 1 | Collect training images from /memory | Low | S05 continuous learning (done) |
| 2 | Create dataset loader | Low | PyTorch/torchvision |
| 3 | Train MobileNetV2 classifier | Medium | GPU (RunPod optional) |
| 4 | Integrate into S05 | Low | Model checkpoint |
| 5 | Evaluate on holdout | Low | Test fixtures |

### Alternative: Heuristic-Based (No Training)

If training is too expensive, we could instead:
1. Expand the current heuristic in `_get_preset_table_config()`
2. Use features: line width CV, cell density, page region location
3. Store successful combinations in /memory for recall

This is already partially implemented via today's changes.

## Other Classifier Opportunities

### 1. PDF Issue Predictor

**Purpose**: Predict which extraction issues are likely from S00 profile.

```
Input: S00 profile.json features
Output: List of likely issues (hyphenation, ligatures, split_tables, etc.)
```

**Value**: Pre-warn the pipeline about expected issues, adjust thresholds accordingly.

**Training Data**: Already have from preset_match.errors + actual extraction results.

### 2. Document Domain Classifier

**Purpose**: Improve domain detection beyond keyword matching.

```
Input: First N pages of text
Output: Domain category (scientific, engineering, legal, etc.)
```

**Value**: Better preset selection for edge cases where keywords fail.

**Training Data**: PDF corpus with known domains from filenames/metadata.

### 3. Fixture Generator (fixture-tricky Enhancement)

**Purpose**: Generate adversarial PDFs that break specific extractors.

```
Input: Extractor weakness description (e.g., "misses thin table borders")
Output: PDF with that weakness embedded
```

**Value**: Automated regression testing and hardening.

**Training Data**: Manual fixture creation patterns.

## Resource Requirements

| Component | Requirement |
|-----------|-------------|
| GPU | Optional (CPU fine for inference, A10 for training) |
| Storage | 5-10GB for training data |
| Training Time | 2-4 hours on A10 |
| Inference Latency | < 50ms per table |

## Recommendation

**Phase 1 (Immediate)**: Continue with heuristic improvements
- S05 continuous learning already stores successful params
- Recall from /memory before trying default strategies

**Phase 2 (Next Sprint)**: Collect training data
- Accumulate 1000+ labeled table images from corpus runs
- Store in structured format for training

**Phase 3 (Future)**: Train Table Strategy Classifier
- Use architecture similar to create-intent-map
- GRPO with execution feedback from Camelot
- Deploy as optional model in S05

## Files to Create

```
src/extractor/pipeline/
├── models/
│   ├── table_strategy_classifier.py    # Inference wrapper
│   └── training/
│       ├── dataset.py                  # Table image dataset
│       ├── train_grpo.py               # GRPO training loop
│       └── evaluate.py                 # Holdout evaluation
└── utils/
    └── strategy_predictor.py           # Integration with S05
```

## Success Criteria

| Metric | Target | Current Baseline |
|--------|--------|------------------|
| Strategy accuracy | ≥ 85% | N/A (heuristic) |
| Fallback rate | < 10% | ~25% |
| Avg extraction time | -20% | Baseline |
| Quality score | ≥ 0.85 | 0.78 |

---

**Conclusion**: A classifier model is a good fit for the extractor project. The Table Strategy Classifier is the highest-impact option. However, the heuristic improvements implemented today (verbose preset detection, continuous learning to /memory) provide a strong foundation that can be enhanced with a trained model later.
