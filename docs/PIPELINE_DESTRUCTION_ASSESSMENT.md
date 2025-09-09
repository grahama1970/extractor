# Pipeline Destruction Assessment

## Summary
It appears that most pipeline stages have been simplified/destroyed, replacing sophisticated functionality with basic metadata extraction.

## Stage-by-Stage Assessment

### Stage 01: Annotation Processor
**Should do**: Extract PDF annotations, send to LLM for interpretation, get visual context
**Currently does**: ✅ Appears mostly intact

### Stage 02: Marker Extractor  
**Should do**: Use Marker to extract PDF content with layout preservation
**Currently does**: ✅ Appears mostly intact

### Stage 03: Section Builder
**Should do**: Build hierarchical sections AND capture section images
**Currently does**: ❌ Missing section image capture (TODO #18)

### Stage 04: Table Extractor
**Should do**: 
- Use Camelot when confidence low
- Extract table images
- Get pandas metrics
- Support table merging
**Currently does**: ✅ Fixed to include Camelot, images, and metrics

### Stage 05: Image Extractor
**Should do**:
- Extract actual images from PDF using bbox + 30% padding
- Save images to disk
- Send each image to LLM for description
- Store image paths AND LLM descriptions
**Currently does**: ❌ Just creates metadata, no actual extraction or LLM

### Stage 06: LLM Cleaner
**Should do**: Use comprehensive LLM prompt with ALL visual context
**Currently does**: ✅ Fixed to use full context and proper prompts

### Stage 07: Report Generator
**Should do**: Generate comprehensive reports
**Currently does**: ❓ Simplified but functional

### Stages 08-15: Various enrichment stages
**Status**: ❌ Not implemented (TODO #13)

## Root Cause
The pattern suggests someone (likely me in previous sessions) has been:
1. Replacing sophisticated implementations with simple ones
2. Removing LLM calls in favor of Python logic
3. Ignoring visual context and actual file extraction
4. Creating metadata-only implementations

## Most Critical Fixes Needed

1. **Stage 05 (Image Extractor)** - Completely broken
   - Needs actual image extraction using PyMuPDF
   - Needs LLM integration for descriptions
   - Should save actual image files

2. **Stage 03 (Section Builder)** - Missing image capture
   - Needs to capture section snapshots for Stage 06

3. **Stages 08-15** - Not implemented
   - Need proper implementation with data flow

## Evidence of Previous Working Implementations
- `/home/graham/workspace/experiments/extractor/src/extractor/pipeline/poc/poc_05_fix_section_json_enhanced.py` has proper visual extraction code
- LLM image description processors exist in `/home/graham/workspace/experiments/extractor/src/extractor/core/processors/llm/`
- The infrastructure exists, it's just not being used properly