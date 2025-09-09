# PDF Label to Extraction Integration Guide

## Overview

This guide explains how to integrate labeled PDF objects from the pdf_header_labeler directly into the extractor pipeline for immediate classification benefits.

## Architecture Decision: k-NN with Existing Infrastructure

Based on analysis and the Perplexity critique, we're using **k-NN classification** because:
1. **Immediate results** - No training delays
2. **Works with small datasets** - Effective with 50-200 examples per type
3. **Leverages existing embeddings** - Uses BAAI/bge-large-en (1024 dims) for text
4. **Supports multimodal** - CLIP for visual features + text context

## Integration Components

### 1. Dual Embedding Strategy

For each PDF object, we maintain TWO embeddings:

```python
# Visual embedding (CLIP) - What the object looks like
visual_embedding = clip_model.encode_image(image)  # 512 dims

# Context embedding (BAAI/bge) - Surrounding text context  
from extractor.core.utils.embedding_utils import get_embedding
context_embedding = get_embedding(surrounding_text)  # 1024 dims
```

**Why dual embeddings?**
- A figure of a "neural network architecture" under a "Methods" header is different from the same image under "Results"
- Headers like "Table 1:" depend on context - is it under "Experimental Setup" or "Financial Data"?

### 2. Storage in ArangoDB

The labeled patterns are stored in collections:
- `header_patterns` - Text-based header patterns
- `pdf_object_patterns` - Multimodal patterns with dual embeddings

### 3. Classification Pipeline Integration

Add the k-NN classifier to the pipeline after Marker extraction:

```python
# In 00_run_pipeline.py, add after stage 03:
{
    "num": "03d",
    "name": "knn_suspicious_detector",
    "script": "03d_knn_suspicious_detector.py",
    "description": "Detect suspicious headers using k-NN with labeled data",
    "input": "stage_03c_results.json",
    "output": "stage_03d_results.json",
    "depends_on": ["03c"]
}
```

## Implementation Steps

### Step 1: Label Collection
Users label PDF objects through the web interface:
```bash
cd src/extractor/pipeline/pdf_header_labeler
./start_unified.sh
```

### Step 2: Automatic Integration
The k-NN classifier automatically uses labeled data:

```python
from extractor.core.processors.pdf_object_classifier import PDFObjectClassifier

# In your pipeline processor:
classifier = PDFObjectClassifier(
    k=5,                    # Use 5 nearest neighbors
    min_confidence=0.7,     # Minimum confidence threshold
    use_faiss=True,         # Use FAISS for speed
    context_window=3        # Look at 3 blocks before/after
)

# Process blocks
processed_blocks = classifier.process(blocks, metadata)
```

### Step 3: Immediate Benefits
- Suspicious headers are marked for review
- Misclassified figures/tables are detected
- Domain-specific patterns are learned

## FAISS Optimization (Optional)

For large collections (>1000 patterns), FAISS provides speed benefits:

```python
# The classifier automatically maintains 3 FAISS indices:
visual_index    # CLIP embeddings (512d)
context_index   # Text embeddings (1024d)  
combined_index  # Concatenated (1536d)
```

**Note**: With <1000 patterns, ArangoDB's native search is sufficient.

## Best Practices

### 1. Start Simple
- Begin with text-only classification for headers
- Add CLIP embeddings for figures/tables later
- Use combined embeddings for complex cases

### 2. Label Strategically
- Focus on edge cases and errors
- Label both positive and negative examples
- Use the ML readiness metrics to guide labeling

### 3. Monitor Performance
```python
# Check classifier effectiveness
stats = classifier.get_classification_stats()
print(f"Suspicious headers found: {stats['headers_detected']}")
print(f"Low confidence items: {stats['low_confidence']}")
```

## Example: Complete Integration

```python
# 1. User labels headers in the web UI
# 2. In extraction pipeline:

from extractor.core.processors.knn_header_classifier import KNNHeaderClassifier
from extractor.core.utils.embedding_utils import get_embedding

# Initialize with existing labeled data
classifier = KNNHeaderClassifier(k=5, min_confidence=0.7)

# Process blocks from Marker
for block in blocks:
    if block.type == "Text":
        # Generate embedding using project's standard embedder
        embedding = get_embedding(block.text)
        
        # Classify using k-NN
        result = classifier.classify_with_embedding(
            text=block.text,
            embedding=embedding
        )
        
        # Mark suspicious blocks
        if result.label == 'header' and result.confidence > 0.7:
            block.metadata['suspicious'] = True
            block.metadata['suspicious_reason'] = f"k-NN: {result.reasoning}"
```

## Advantages of This Approach

1. **No Training Time** - Labels are immediately useful
2. **Domain Adaptation** - Learns your specific document patterns
3. **Explainable** - Shows which examples influenced classification
4. **Incremental** - Gets better with each label
5. **Multimodal** - Handles text, images, and context together

## Future Enhancements

Once you have >500 labels per type:
1. Consider training a small BERT classifier for speed
2. Use active learning to identify most useful examples to label
3. Implement online learning for continuous improvement

But for immediate use with 50-200 labels, k-NN is optimal.