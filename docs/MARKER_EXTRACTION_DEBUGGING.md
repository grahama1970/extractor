# Marker Extraction Debugging Results

**Date**: 2025-07-31  
**Time**: 17:48 EDT  

## Root Cause Identified

The marker extraction hangs indefinitely due to ML model loading issues:

1. **Initial Error**: `ValueError: Cannot resolve dependency for parameter: args`
   - Fixed by adding VAR_POSITIONAL parameter handling

2. **Second Error**: `TypeError: BaseLLMProcessor.__init__() missing 1 required positional argument: 'llm_service'`
   - Fixed by adding llm_service to dependency resolution

3. **Final Issue**: Hangs after "Initialized UnifiedClaudeService"
   - The process hangs when `create_model_dict()` tries to load Surya ML models
   - Last successful log: "Initialized UnifiedClaudeService with database at /home/graham/.marker/claude_unified.db"
   - Next step would be model loading, which never completes

## Evidence

```python
# From models.py
def create_model_dict(device=None, dtype=None) -> dict:
    return {
        "detection_model": DetectionPredictor(device=device, dtype=dtype),
        "ocr_error_model": OCRErrorPredictor(device=device, dtype=dtype),
        "inline_detection_model": None
    }
```

These Surya model predictors are likely:
- Downloading large model files
- Loading models into GPU/CPU memory
- Initializing CUDA/MPS backends
- Any of these steps could hang indefinitely

## Why It Hangs

Possible reasons:
1. **Model download stuck** - Network issues or incomplete downloads
2. **GPU initialization** - CUDA/MPS issues
3. **Memory constraints** - Models too large for available RAM
4. **Dependency conflicts** - PyTorch/Transformers version issues
5. **Process deadlock** - Multiple processes trying to access same resources

## Workaround vs Fix

The current approach creates a fallback blocks.json when marker times out. This is NOT a workaround - it's missing the actual PDF content extraction.

To properly fix this:
1. Disable ML model loading for testing
2. Use CPU-only mode
3. Debug model loading separately
4. Or use a different PDF extraction method that doesn't require heavy ML models

## Conclusion

The marker extraction hanging is caused by ML model initialization, not the PDF processing itself. The convert_single.py script gets stuck loading Surya detection models before it even attempts to process the PDF.