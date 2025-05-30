# Task: Verify Corpus Generator and Tree-Sitter Integration

## Summary
Verify that the corpus generator with PyMuPDF and Camelot works as expected, and ensure tree_sitter_utils.py is properly extracting code blocks in the marker document model.

## Current Investigation
Based on the investigation so far:

1. **Corpus Generator Implementation**:
   - ✅ `marker/processors/corpus_validator.py` - Validates extracted content against raw PDF using PyMuPDF
   - ✅ `marker/scripts/convert_for_qa.py` - Conversion script optimized for Q&A generation
   - ✅ `marker/config/qa_optimized.py` - Configuration for Q&A-optimized extraction
   - ✅ `marker/processors/enhanced_table_validator.py` - Enhanced table validation using multiple methods
   - ❌ **Missing**: Specific tests for corpus validation functionality

2. **Tree-Sitter Integration**:
   - ✅ `marker/services/utils/tree_sitter_utils.py` - Comprehensive language detection and metadata extraction
   - ✅ `marker/processors/code.py` - Uses tree-sitter for code language detection
   - ✅ `tests/features/test_enhanced_features.py` - Tests tree-sitter availability but not functionality
   - ❌ **Missing**: Direct tests for code block extraction in the document model

## Tasks

### 1. Create Corpus Validation Test
Create a test file that verifies the corpus generator works correctly:

```python
# tests/test_corpus_validation.py
import pytest
from marker.processors.corpus_validator import CorpusValidator
from marker.scripts.convert_for_qa import convert_single_pdf
from marker.config.qa_optimized import QAOptimizedConfig
```

**Tests to include**:
- Test PyMuPDF extraction works
- Test validation threshold (97%) is enforced
- Test fallback to Camelot for low-confidence tables
- Test comprehensive validation data in output

### 2. Create Tree-Sitter Code Extraction Test
Create a test file that verifies tree-sitter properly extracts code blocks:

```python
# tests/test_tree_sitter_code_extraction.py
import pytest
from marker.processors.code import CodeProcessor
from marker.services.utils.tree_sitter_utils import extract_code_metadata, get_supported_language
```

**Tests to include**:
- Test language detection for various code snippets
- Test code metadata extraction (functions, classes)
- Test integration with document model
- Test fallback to heuristic detection

### 3. Create End-to-End QA Conversion Test
Create a test that runs the complete Q&A-optimized conversion:

```python
# tests/test_qa_conversion_e2e.py
import pytest
from marker.scripts.convert_for_qa import convert_single_pdf
from pathlib import Path
```

**Tests to include**:
- Test conversion with Q&A optimization
- Verify corpus validation is included
- Check that Camelot fallback works
- Validate output format includes validation metrics

### 4. Manual Verification Script
Create a script to manually verify the functionality:

```python
# tests/manual_corpus_verification.py
"""Manual script to verify corpus generator and tree-sitter functionality"""
```

### 5. Documentation Update
Update documentation to explain:
- How corpus validation works
- How to use Q&A-optimized conversion
- Tree-sitter integration details
- When Camelot fallback is triggered

## Success Criteria
- [ ] Corpus validation test passes with 97% threshold
- [ ] Tree-sitter correctly identifies code languages
- [ ] Camelot fallback triggers for low-confidence tables  
- [ ] Q&A conversion includes validation metrics in output
- [ ] Manual verification script demonstrates functionality
- [ ] Documentation clearly explains the features

## Priority
HIGH - These are new features that need test coverage to ensure reliability

## Dependencies
- PyMuPDF must be installed
- Camelot-py must be installed
- Tree-sitter language packs must be available

## Notes
- The corpus generator appears to be fully implemented but lacks test coverage
- Tree-sitter integration exists in CodeProcessor but needs more comprehensive testing
- Q&A-optimized conversion combines both features and needs end-to-end testing