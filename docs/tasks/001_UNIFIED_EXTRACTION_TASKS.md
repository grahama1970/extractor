# Master Task List - Extractor Unified Extraction Implementation

**Total Tasks**: 12  
**Completed**: 0/12  
**Active Tasks**: #001 (Primary)  
**Last Updated**: 2025-06-11 18:30 EDT  

## 🏥 Project Health Check (Run BEFORE Creating Tasks)

### Python Version Check
```bash
# Check Python version requirement
cat pyproject.toml | grep -E "python.*=" | grep -v python-
# Result: requires-python = ">=3.10.11"
```

### Service Availability Check
```bash
# Check all required services are running
curl -s http://localhost:8529/_api/version || echo "❌ ArangoDB not running"
# ArangoDB needed for testing graph output format
```

### Test Infrastructure Check
```bash
# Verify pytest can collect tests
cd /home/graham/workspace/experiments/extractor && python -m pytest --collect-only 2>&1 | grep -E "(collected|error)"
```

### Existing Configuration Check
```bash
# Look for existing extraction implementations
find . -name "convert*.py" | grep -v test
# Found: convert.py, convert_single.py, converters/pdf.py, etc.
```

⚠️ **CRITICAL ISSUE**: OpenCV (cv2) is missing from the extractor's virtual environment!
The extractor has its own .venv at /home/graham/workspace/experiments/extractor/.venv
but opencv-python needs to be installed there for Surya models to work.

---

## 🎯 TASK #001: Install Missing Dependencies in Extractor Environment

**Status**: 🔄 In Progress  
**Dependencies**: None  
**Expected Test Duration**: 1.0s–5.0s  

### Implementation
- [ ] Activate extractor's virtual environment: `/home/graham/workspace/experiments/extractor/.venv`
- [ ] Install opencv-python: `uv add opencv-python`
- [ ] Install pymupdf: `uv add pymupdf`
- [ ] Reinstall project: `uv pip install -e .`
- [ ] Verify cv2 imports correctly
- [ ] Test Surya model initialization

### Test Loop
```
CURRENT LOOP: #1
1. Test with real PDF file (2505.03335v2.pdf)
2. Verify output > 10KB (not placeholder)
3. Check for actual content extraction
4. Validate markdown structure
```

#### Tests to Run:
| Test ID | Description | Command | Expected Outcome |
|---------|-------------|---------|------------------|
| 001.1   | Extract real PDF content | `python -c "from extractor import convert_single_pdf; print(len(convert_single_pdf('data/input/2505.03335v2.pdf')))"` | Length > 10000 chars |
| 001.2   | Verify not placeholder | `python -c "from extractor import convert_single_pdf; r=convert_single_pdf('data/input/2505.03335v2.pdf'); assert 'placeholder' not in r.lower()"` | No assertion error |
| 001.3   | Extract contains title | `python -c "from extractor import convert_single_pdf; r=convert_single_pdf('data/input/2505.03335v2.pdf'); assert 'Absolute Zero' in r"` | Title found |

**Task #001 Complete**: [ ]  

---

## 🎯 TASK #002: Create Unified Document Schema

**Status**: 🔄 Not Started  
**Dependencies**: None  
**Expected Test Duration**: 0.1s–1.0s  

### Implementation
- [ ] Define JSON schema for unified document structure
- [ ] Include section hierarchy with parent-child relationships
- [ ] Support entities and relationships for ArangoDB
- [ ] Create schema validation functions
- [ ] Document all required fields and types
- [ ] Save as `schemas/unified_document_schema.json`

### Schema Structure:
```json
{
  "document": {
    "title": "string",
    "metadata": {},
    "sections": [{
      "id": "string",
      "title": "string", 
      "level": "integer",
      "content": "string",
      "parent": "string|null"
    }],
    "entities": [],
    "relationships": []
  }
}
```

**Task #002 Complete**: [ ]  

---

## 🎯 TASK #003: Implement HTML to Unified JSON Converter

**Status**: 🔄 Not Started  
**Dependencies**: #002  
**Expected Test Duration**: 0.5s–2.0s  

### Implementation
- [ ] Create HTMLProvider if not exists
- [ ] Parse HTML structure using BeautifulSoup
- [ ] Extract hierarchical sections (h1-h6)
- [ ] Build parent-child relationships
- [ ] Extract tables and preserve structure
- [ ] Map to unified JSON schema
- [ ] Handle malformed HTML gracefully

### Tests to Run:
| Test ID | Description | Command | Expected Outcome |
|---------|-------------|---------|------------------|
| 003.1   | Convert HTML file | `python test_unified_extraction.py --format=html` | Valid JSON output |
| 003.2   | Verify section hierarchy | Check h1->h2->h3 relationships preserved | Correct parent-child |
| 003.3   | Extract HTML tables | Verify table data extraction | Tables in JSON |

**Task #003 Complete**: [ ]  

---

## 🎯 TASK #004: Implement XML to Unified JSON Converter

**Status**: 🔄 Not Started  
**Dependencies**: #002  
**Expected Test Duration**: 0.5s–2.0s  

### Implementation
- [ ] Create XMLProvider using defusedxml for security
- [ ] Parse XML structure recursively
- [ ] Map XML elements to document sections
- [ ] Handle namespaces properly
- [ ] Extract attributes as metadata
- [ ] Build hierarchical structure
- [ ] Validate against unified schema

**Task #004 Complete**: [ ]  

---

## 🎯 TASK #005: Implement DOCX to Unified JSON Converter

**Status**: 🔄 Not Started  
**Dependencies**: #002  
**Expected Test Duration**: 1.0s–5.0s  

### Implementation
- [ ] Create DOCXProvider using python-docx
- [ ] Extract document structure and styles
- [ ] Map heading styles to hierarchy levels
- [ ] Extract tables with formatting
- [ ] Handle embedded images/objects
- [ ] Preserve metadata (author, dates)
- [ ] Convert to unified JSON format

### Required Dependencies:
```bash
uv add python-docx openpyxl
```

**Task #005 Complete**: [ ]  

---

## 🎯 TASK #006: Fix PDF to Unified JSON Pipeline

**Status**: 🔄 Not Started  
**Dependencies**: #001, #002  
**Expected Test Duration**: 10.0s–30.0s  

### Implementation
- [ ] Fix PdfConverter initialization issues
- [ ] Resolve missing model dependencies
- [ ] Extract document structure from PDF
- [ ] Build section hierarchy from headings
- [ ] Extract tables using Surya/Camelot
- [ ] Handle multi-column layouts
- [ ] Map to unified JSON schema

### Model Dependencies Fix:
```python
# Add to create_model_dict():
"inline_detection_model": None  # Optional
```

**Task #006 Complete**: [ ]  

---

## 🎯 TASK #007: Create Unified Renderer Base Class

**Status**: 🔄 Not Started  
**Dependencies**: #002  
**Expected Test Duration**: 0.1s–0.5s  

### Implementation
- [ ] Create UnifiedRenderer base class
- [ ] Define render_to_unified_json() method
- [ ] Implement section hierarchy builder
- [ ] Add entity extraction hooks
- [ ] Create relationship detection
- [ ] Ensure consistent output format
- [ ] Add schema validation

**Task #007 Complete**: [ ]  

---

## 🎯 TASK #008: Implement Cross-Format Consistency Tests

**Status**: 🔄 Not Started  
**Dependencies**: #003, #004, #005, #006  
**Expected Test Duration**: 30.0s–60.0s  

### Implementation
- [ ] Create test documents in all formats with same content
- [ ] Extract each format to unified JSON
- [ ] Compare structural consistency
- [ ] Verify section counts match
- [ ] Check content preservation
- [ ] Validate entity extraction
- [ ] Generate comparison report

### Test Files:
- test_document.pdf
- test_document.html  
- test_document.xml
- test_document.docx

All should produce identical JSON structure!

**Task #008 Complete**: [ ]  

---

## 🎯 TASK #009: ArangoDB Schema Compatibility

**Status**: 🔄 Not Started  
**Dependencies**: #007, #008  
**Expected Test Duration**: 1.0s–5.0s  

### Implementation
- [ ] Verify JSON format matches ArangoDB requirements
- [ ] Test vertex/edge structure
- [ ] Validate _key generation
- [ ] Ensure proper collection names
- [ ] Test relationship format
- [ ] Create import validation
- [ ] Document schema mapping

### ArangoDB Format:
```json
{
  "vertices": {
    "documents": [],
    "sections": [],
    "entities": []
  },
  "edges": {
    "contains": [],
    "references": []
  }
}
```

**Task #009 Complete**: [ ]  

---

## 🎯 TASK #010: Image and Table Extraction

**Status**: 🔄 Not Started  
**Dependencies**: #006  
**Expected Test Duration**: 5.0s–20.0s  

### Implementation
- [ ] Use PyMuPDF to extract page images
- [ ] Implement table detection with Surya
- [ ] Extract table structure and data
- [ ] Generate image descriptions (optional)
- [ ] Include in unified JSON output
- [ ] Test with complex documents
- [ ] Handle multi-page tables

### PyMuPDF Usage:
```python
import fitz  # PyMuPDF
doc = fitz.open("document.pdf")
for page in doc:
    pix = page.get_pixmap()
    # Process image for tables/figures
```

**Task #010 Complete**: [ ]  

---

## 🎯 TASK #011: Performance Optimization

**Status**: 🔄 Not Started  
**Dependencies**: #008  
**Expected Test Duration**: Variable  

### Implementation
- [ ] Profile extraction performance
- [ ] Implement batch processing
- [ ] Add progress callbacks
- [ ] Optimize model loading
- [ ] Cache extracted results
- [ ] Parallel page processing
- [ ] Memory usage optimization

**Task #011 Complete**: [ ]  

---

## 🎯 TASK #012: Integration with ArangoDB Project

**Status**: 🔄 Not Started  
**Dependencies**: #009  
**Expected Test Duration**: 2.0s–10.0s  

### Implementation
- [ ] Test with real ArangoDB instance
- [ ] Verify data imports correctly
- [ ] Test graph queries work
- [ ] Validate relationship traversal
- [ ] Check Q&A model compatibility
- [ ] Document integration process
- [ ] Create usage examples

### Integration Test:
```python
from extractor import extract_to_unified_json
from arangodb import import_document

# Extract any format
json_data = extract_to_unified_json("document.pdf")
# Import to ArangoDB
import_document(json_data)
```

**Task #012 Complete**: [ ]  

---

## 📊 Overall Progress

### By Status:
- ✅ Complete: 0 (#none)  
- ⏳ In Progress: 0 (#none)  
- 🚫 Blocked: 0 (#none)  
- 🔄 Not Started: 12 (#001-#012)  

### Dependency Graph:
```
#001 (Fix PDF) → #006 (PDF Pipeline) → #010 (Images/Tables)
#002 (Schema) → #003, #004, #005, #007 (Format Converters)
#003-#006 → #008 (Consistency Tests)
#007-#008 → #009 (ArangoDB) → #012 (Integration)
#008 → #011 (Performance)
```

### Critical Issues:
1. **convert_single_pdf() is a placeholder** - Must be fixed first!
2. **Model initialization failures** - Missing dependencies
3. **No unified schema exists** - Needed for all converters
4. **Format converters incomplete** - Only PDF partially works

### Next Actions:
1. Fix convert_single_pdf() implementation (#001)
2. Create unified document schema (#002)  
3. Implement format converters in parallel (#003-#006)
4. Run consistency tests across all formats (#008)

---

## 🔍 Key Success Criteria

The extractor MUST:
1. ✅ Extract real content from PDFs (not placeholder text)
2. ✅ Support PDF, HTML, XML, DOCX formats
3. ✅ Produce identical JSON structure from any format
4. ✅ Include hierarchical section structure
5. ✅ Be compatible with ArangoDB ingestion
6. ✅ Preserve tables and important formatting
7. ✅ Handle large documents efficiently

**CRITICAL**: All formats must produce the SAME hierarchical JSON structure for ArangoDB!