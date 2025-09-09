# OCRmyPDF Integration Proposal for Confidence Scores

Generated: 2025-08-02

## Problem Statement

The current PDF extraction pipeline using marker/Surya does NOT provide OCR confidence scores, which are critical for:
- Quality assessment of extracted text
- Identifying low-confidence regions for review
- Selective re-processing of problematic areas
- Post-processing workflows that need confidence thresholds

## Proposed Solution: OCRmyPDF Integration

Based on research with Perplexity, we can integrate OCRmyPDF (which uses Tesseract) to get confidence scores while still leveraging marker's excellent layout analysis.

### Approach 1: Hybrid Pipeline

```python
# Step 1: Use OCRmyPDF for OCR with confidence
ocrmypdf.ocr(input_pdf, ocr_pdf, force_ocr=True)

# Step 2: Extract confidence scores via pytesseract
pages = convert_from_path(ocr_pdf)
for page in pages:
    data = pytesseract.image_to_data(page, output_type=Output.DICT)
    # data['conf'] contains confidence scores (0-100)

# Step 3: Use marker for layout (skip OCR)
os.environ['OCR_ENGINE'] = 'None'
marker_results = marker.convert_single_pdf(ocr_pdf)

# Step 4: Combine results
enhanced_blocks = match_confidence_to_blocks(marker_blocks, confidence_data)
```

### Approach 2: Marker with OCRmyPDF Backend

```python
# Configure marker to use ocrmypdf
os.environ['OCR_ENGINE'] = 'ocrmypdf'
os.environ['OCR_ALL_PAGES'] = 'true'

# Marker will use ocrmypdf internally
results = marker.convert_single_pdf(input_pdf)

# Extract confidence separately via Tesseract API
confidence_data = extract_tesseract_confidence(input_pdf)
```

## Expected Benefits

### 1. Real OCR Confidence Scores
```json
{
  "block_type": "Text",
  "text": "The BHT is never flushed.",
  "ocr_confidence": {
    "avg": 95.2,
    "min": 88,
    "max": 99,
    "word_count": 5,
    "is_low_confidence": false
  }
}
```

### 2. Quality Metrics
```json
{
  "summary": {
    "total_words": 1234,
    "avg_confidence": 92.5,
    "low_confidence_count": 23,
    "low_confidence_blocks": [
      {
        "text": "SignalIODescripticonnexiTypeonon",
        "avg_confidence": 72.3,
        "reason": "Mangled table text"
      }
    ]
  }
}
```

### 3. Selective Re-processing
- Identify blocks with confidence < 80%
- Re-OCR with different settings
- Apply targeted corrections

## Implementation Requirements

### Required Packages
```toml
[dependencies]
ocrmypdf = "^15.0"
pytesseract = "^0.3.10"
pdf2image = "^1.16.0"  # Already available
```

### System Dependencies
- Tesseract OCR engine (apt install tesseract-ocr)
- Ghostscript (for PDF processing)
- Language data files for Tesseract

## Comparison: Surya vs Tesseract/OCRmyPDF

| Feature | Surya (Current) | Tesseract/OCRmyPDF |
|---------|-----------------|-------------------|
| **Accuracy** | ~97.7% | ~87.7% |
| **Confidence Scores** | ❌ Not available | ✅ Per-word scores |
| **Language Support** | 90+ languages | Many languages |
| **Layout Analysis** | Advanced | Basic |
| **Hardware** | GPU recommended | CPU-friendly |
| **Speed** | Fast with GPU | Fast on CPU |

## Recommendation

For the extractor project, consider a **hybrid approach**:

1. **Primary Pipeline**: Continue using marker/Surya for highest accuracy
2. **Confidence Pipeline**: Add optional OCRmyPDF processing for documents requiring confidence scores
3. **Configuration**: Make it configurable based on use case:
   ```python
   extractor.convert_pdf(
       input_pdf,
       ocr_engine='hybrid',  # 'surya', 'tesseract', or 'hybrid'
       extract_confidence=True
   )
   ```

## POC 03 Demonstration

The created `poc_03_ocrmypdf_confidence.py` demonstrates how this would work:

1. Processes PDF with ocrmypdf
2. Extracts word and block-level confidence scores
3. Uses marker for layout analysis
4. Combines results into enhanced blocks with confidence data

### Sample Output Structure
```json
{
  "blocks": [
    {
      "block_type": "Text",
      "text": "BHT is implemented as a memory...",
      "ocr_confidence": {
        "avg": 94.5,
        "min": 89,
        "max": 98,
        "word_count": 23,
        "is_low_confidence": false
      }
    }
  ],
  "confidence_data": {
    "summary": {
      "total_words": 543,
      "avg_confidence": 91.2,
      "low_confidence_count": 12
    }
  }
}
```

## Next Steps

1. **Install Dependencies**: Add ocrmypdf and pytesseract to project dependencies
2. **Test Integration**: Run POC 03 with test documents
3. **Evaluate Trade-offs**: Compare accuracy vs confidence availability
4. **Production Integration**: Implement configurable OCR engine selection

This approach provides the best of both worlds: Surya's high accuracy when confidence isn't needed, and Tesseract's confidence scores when quality assessment is required.