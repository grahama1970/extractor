# Table Strategy Classifier - Project Context

> **Purpose**: This document provides complete context for the Table Strategy Classifier project, enabling any agent to continue work without prior knowledge.
>
> **Last Updated**: 2026-02-08
> **Status**: Production Ready (95.07% accuracy achieved)

---

## Executive Summary

We built a **machine learning classifier** to predict optimal Camelot table extraction strategies for PDF documents. The classifier replaces trial-and-error strategy selection in the S05 pipeline stage, reducing fallback rates from ~25% to <10%.

**Key Achievement**: 95.07% accuracy ensemble (EfficientNet-B0 + EdgeNeXt-small)

---

## Problem Statement

### The Original Problem

The S05 table extractor (`src/extractor/pipeline/steps/s05_table_extractor.py`) uses Camelot for PDF table extraction. Camelot has two main strategies:

1. **Lattice**: Detects tables using line intersections (grid-based)
2. **Stream**: Detects tables using text flow analysis (no lines needed)

Each strategy has parameters:
- `line_scale` (lattice): Controls line detection sensitivity (5-60)
- `edge_tol` (stream): Controls edge tolerance (25-200)

**The Challenge**: No single strategy works for all documents. The pipeline was:
1. Try lattice with default params
2. If fragmentation detected, try alternative params
3. If still failing, try stream
4. Repeat with different params

This trial-and-error approach was:
- **Slow**: Multiple extraction attempts per table
- **Unreliable**: ~25% of tables needed fallback strategies
- **Resource-intensive**: Wasted compute on failed extractions

### The Solution

Train a vision classifier to predict the optimal strategy from a table region image, achieving:
- Single-shot strategy selection
- Confidence-based fallback (only retry when confidence < threshold)
- Parameter prediction (line_scale, edge_tol)

---

## Architecture

### Model Architecture

```
Table Region Image (224x224)
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  Backbone (timm: efficientnet_b0 / edgenext_small)  │
│  - Pretrained on ImageNet                           │
│  - Feature extraction (no classification head)      │
└─────────────────────────────────────────────────────┘
    │
    ▼ Features + Preset Embedding
┌─────────────────────────────────────────────────────┐
│  Classification Head                                 │
│  - Strategy: 3-class (lattice/stream/lattice_sens)  │
│  - Params: line_scale (10-50), edge_tol (100-600)   │
│  - Confidence: sigmoid output                        │
└─────────────────────────────────────────────────────┘
```

### Ensemble Configuration (Final)

```json
{
  "type": "ensemble",
  "accuracy": 0.9507,
  "models": {
    "efficientnet_b0": {
      "weight": 0.55,
      "solo_accuracy": 0.9454
    },
    "edgenext_small": {
      "weight": 0.45,
      "solo_accuracy": 0.9441
    }
  },
  "per_class_accuracy": {
    "lattice": 0.957,
    "stream": 0.947,
    "lattice_sensitive": 0.800
  }
}
```

---

## File Locations

### Primary Skill Directory
```
/home/graham/workspace/experiments/pi-mono/.pi/skills/create-table-classifier/
├── SKILL.md                           # Skill documentation
├── run.sh                             # CLI wrapper
├── scripts/
│   ├── inference.py                   # Strategy prediction (for S05 integration)
│   ├── train_sft.py                   # Supervised fine-tuning trainer
│   ├── train_advanced.py              # Training with augmentation
│   ├── train_dit.py                   # DiT backbone trainer
│   ├── train_ensemble.py              # Ensemble evaluation
│   ├── collect_training_data.py       # Dataset collection
│   ├── evaluate.py                    # Model evaluation
│   └── taxonomy_bridge.py             # Preset recommendations
├── models/
│   ├── table-classifier-ensemble-final/   # Production model (95.07%)
│   │   └── config.json
│   ├── table-classifier-efficientnet-b0/  # Solo EfficientNet (94.54%)
│   ├── table-classifier-edgenext-small/   # Solo EdgeNeXt (94.41%)
│   ├── table-classifier-advanced/         # Augmented training (93.74%)
│   └── table-classifier-dit/              # DiT backbone (55.66% - not useful)
└── data/
    ├── images/                        # Table region images
    │   ├── train/
    │   └── eval/
    └── labels/
        ├── train_balanced.jsonl       # 4619 examples (balanced)
        └── eval.jsonl                 # 751 examples
```

### Integration Points
```
/home/graham/workspace/experiments/extractor/
└── src/extractor/pipeline/steps/
    └── s05_table_extractor.py         # Lines 155-269: Classifier integration

/home/graham/workspace/experiments/pi-mono/.pi/skills/
├── debug-table/debug_table/
│   ├── classifier.py                  # New: Classifier integration
│   ├── config.py                      # Updated: Classifier settings
│   └── tuner.py                       # Updated: Uses classifier for grid narrowing
└── extractor/extractor_skill/
    ├── config.py                      # Updated: Classifier settings
    └── SKILL.md                       # Updated: Documents classifier
```

---

## Training Data

### Dataset Statistics
- **Total Examples**: 5,370 (4,619 train + 751 eval)
- **Image Size**: 224x224 PNG (table regions cropped from PDFs)
- **Class Distribution** (balanced training set):
  - lattice: ~40%
  - stream: ~40%
  - lattice_sensitive: ~20%

### Label Schema
```json
{
  "image_path": "images/train/arxiv_2501_p3_t1.png",
  "strategy": "lattice",
  "line_scale": 15,
  "edge_tol": 300,
  "preset": "arxiv_scientific",
  "quality_score": 0.92,
  "source_pdf": "2501_15355.pdf"
}
```

### Data Sources
1. S05 successful extractions (from /memory lessons)
2. 12TB corpus extraction logs
3. PubLayNet dataset (335K document images - available for pretraining)

---

## Training Experiments

### Experiment Timeline

| Experiment | Accuracy | Notes |
|------------|----------|-------|
| MobileNetV2 baseline | 89.2% | Initial SFT warmup |
| EfficientNet-B0 | 94.54% | Best single model |
| EdgeNeXt-small | 94.41% | Competitive alternative |
| ConvNeXtV2-nano | 93.87% | Slower, no benefit |
| Advanced (augmentation) | 93.74% | MixUp/CutMix helped lattice_sensitive |
| DiT backbone | 55.66% | Needs more epochs, not useful |
| **Ensemble (55/45)** | **95.07%** | **Production model** |

### Key Findings

1. **EfficientNet-B0 is optimal**: Best balance of accuracy and speed
2. **Ensemble beats individuals**: 0.5-0.6% improvement from weighted voting
3. **Augmentation helps minority class**: lattice_sensitive improved 60%→80% with MixUp/CutMix
4. **DiT not worth it**: Document-pretrained backbone underperformed, likely needs more training
5. **PubLayNet available**: 335K images downloaded for future pretraining experiments

---

## Integration Details

### S05 Table Extractor Integration

**Location**: `src/extractor/pipeline/steps/s05_table_extractor.py`

**How it works** (lines 155-269):
```python
# Environment variables
USE_STRATEGY_PREDICTOR = os.getenv("USE_STRATEGY_PREDICTOR", "false")
STRATEGY_PREDICTOR_MODEL_PATH = os.getenv(
    "STRATEGY_PREDICTOR_MODEL_PATH",
    "/path/to/table-classifier-ensemble-final"
)
STRATEGY_PREDICTOR_CONFIDENCE_THRESHOLD = 0.75

# Lazy loading
_strategy_predictor = None
def _get_strategy_predictor():
    # Loads ensemble, returns TableStrategyPredictor instance

# Prediction
def _predict_strategy_for_table(pdf_doc, page_num, bbox, preset):
    # Extract table region image
    # Get prediction from classifier
    # Return strategy name, params, confidence
```

**Usage in extraction loop** (lines 706-738):
- If predictor available and confidence >= threshold, use predicted strategy first
- Otherwise, use default strategy order
- Fallback strategies still available if prediction fails

### debug-table Skill Integration

**New file**: `debug_table/classifier.py`
- `ClassifierRecommendation` dataclass
- `get_classifier_recommendation()` - predicts for a PDF page
- `get_classifier_grid_recommendation()` - returns focused parameter grids

**Updated**: `debug_table/tuner.py`
- Priority: Classifier > Memory > Defaults
- Respects `strategy_order` from classifier (lattice_first vs stream_first)
- Focused grids reduce sweep from 32 to 4-6 combinations

---

## Lessons Learned

### What Worked

1. **timm library**: Easy backbone swapping, pretrained weights, consistent API
2. **Balanced training set**: Critical for lattice_sensitive class
3. **Ensemble approach**: Simple weighted voting exceeds 95% target
4. **Preset embedding**: 16-dim embedding helps model specialize
5. **Confidence thresholding**: 0.75 threshold balances accuracy vs fallback rate

### What Didn't Work

1. **DiT backbone**: Document-pretrained model underperformed ImageNet models
   - Hypothesis: Needs more epochs or different fine-tuning strategy
   - Result: 55.66% accuracy vs 94%+ for CNN models

2. **Heavy augmentation alone**: MixUp/CutMix improved minority class but reduced overall accuracy
   - Solution: Combine with balanced sampling

3. **Single model obsession**: Spent time optimizing single models when ensemble was easier win

### Technical Gotchas

1. **Preset mismatch in training data**: Some presets in data don't match PRESETS list
   ```python
   # Fixed by defaulting to "unknown"
   preset_idx = PRESETS.index(preset) if preset in PRESETS else 0
   ```

2. **Path resolution in ensemble**: Config paths are relative to SKILL_DIR, not config file
   ```python
   # Wrong: base_dir = model_path.parent
   # Right: base_dir = SKILL_DIR
   ```

3. **PyTorch weights_only warning**: Use `weights_only=False` for loading custom models

---

## Next Steps

### Immediate (Ready to Implement)

1. **Enable by default**: Change `USE_STRATEGY_PREDICTOR` default from "false" to "true"
2. **Add metrics logging**: Track classifier accuracy vs actual extraction success in production
3. **Feedback loop**: Store (prediction, actual_outcome) pairs for retraining

### Short-term Improvements

1. **Per-table prediction**: Currently predicts for page center; could predict per detected table region
2. **Confidence calibration**: Current confidence may not match actual success probability
3. **ONNX export**: For faster inference without full PyTorch

### Long-term Research

1. **PubLayNet pretraining**: Use 335K document images for backbone pretraining
2. **Multi-task learning**: Predict table structure (rows, columns) alongside strategy
3. **Online learning**: Continuous improvement from production extractions

---

## Environment Setup

### Dependencies
```bash
# In create-table-classifier skill
cd /home/graham/workspace/experiments/pi-mono/.pi/skills/create-table-classifier
uv venv && source .venv/bin/activate
uv pip install torch torchvision timm pillow loguru typer tqdm
```

### Testing the Classifier
```bash
# Test inference
cd /home/graham/workspace/experiments/pi-mono/.pi/skills/create-table-classifier
source .venv/bin/activate
python scripts/inference.py predict data/images/eval/sample.png --json

# Test from S05
cd /home/graham/workspace/experiments/extractor
source .venv/bin/activate
USE_STRATEGY_PREDICTOR=true python -c "
from src.extractor.pipeline.steps.s05_table_extractor import _get_strategy_predictor
p = _get_strategy_predictor()
print(f'Ensemble: {p.is_ensemble}, Models: {len(p.models)}')
"
```

### Key Environment Variables
```bash
USE_STRATEGY_PREDICTOR=true              # Enable classifier in S05
STRATEGY_PREDICTOR_CONFIDENCE_THRESHOLD=0.75  # Min confidence
STRATEGY_PREDICTOR_MODEL_PATH=...        # Override model location
USE_TABLE_CLASSIFIER=true                # Enable in debug-table
```

---

## Quick Reference

### Model Performance
| Metric | Value |
|--------|-------|
| Overall Accuracy | 95.07% |
| Lattice Accuracy | 95.7% |
| Stream Accuracy | 94.7% |
| Lattice_sensitive Accuracy | 80.0% |
| Inference Time | ~15ms (GPU) |

### Class Mapping
| Index | Strategy | Camelot Flavor |
|-------|----------|----------------|
| 0 | lattice | lattice |
| 1 | stream | stream |
| 2 | lattice_sensitive | lattice (with lower line_scale) |

### Preset Mapping
| Index | Preset |
|-------|--------|
| 0 | unknown |
| 1 | arxiv_scientific |
| 2 | requirements_spec |
| 3 | archive_scanned |
| 4 | government_report |
| 5 | academic_thesis |
| 6 | engineering_manual |
| 7 | legal_document |

---

## Contact & Resources

- **Skill Path**: `/home/graham/workspace/experiments/pi-mono/.pi/skills/create-table-classifier/`
- **Main Integration**: `src/extractor/pipeline/steps/s05_table_extractor.py`
- **PubLayNet Data**: `/mnt/storage12tb/media/data/datasets/publaynet/`
- **Training Logs**: `models/*/history.json`

---

*This document should provide complete context for continuing work on the table strategy classifier.*
