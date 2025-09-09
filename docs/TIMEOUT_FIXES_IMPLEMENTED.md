# Timeout Fixes Implemented

## Changes Made

### 1. Increased Base Timeout to 5 Minutes
Updated in `utils/claude_processor.py`:
- Default timeout: 300s (was 30s)
- Minimum timeout: 300s (was 30s)
- Fallback timeout: 300s (was 30s)
- Batch processing default: 300s (was 30s)

### 2. POC 01 Timeout Fix
Updated in `poc_01_extract_annotations.py`:
- Added explicit timeout parameter to `call_claude()`
- Default timeout: 300s (5 minutes)
- This prevents timeouts when analyzing multiple annotation images

### 3. Existing Optimizations Found
The code already has good optimizations:
- Batch processing with `tqdm_asyncio.gather`
- Configurable batch size (default 5)
- Concurrent processing of annotations

## Why This Should Help

1. **13 images at 5 minutes each** = Up to 65 minutes total processing time available
2. **Batch processing** = Images are processed concurrently, not sequentially
3. **Predictive timeouts** = Claude processor adds extra time for images (10s per image)

## Testing

To test if this fixes the timeout issues:
```bash
cd /home/graham/workspace/experiments/extractor
python src/extractor/pipeline/poc/poc_01_extract_annotations.py \
    proof_of_concept/BHT_CV32A65X_marked.pdf \
    --output outputs/
```

## If Timeouts Still Occur

1. **Check if Claude CLI is actually working:**
   ```bash
   claude --version  # Should respond quickly
   claude -p "Say OK"  # Should respond within seconds
   ```

2. **Increase timeout further:**
   - Change 300.0 to 600.0 (10 minutes) in claude_processor.py

3. **Reduce batch size:**
   - In POC 01, change batch_size from 5 to 2 or 3

4. **Debug Claude hanging:**
   - The real issue might be Claude CLI hanging, not just slow responses