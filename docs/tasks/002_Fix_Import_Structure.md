# Task 002: Fix Import Issues for External Usage

**Goal**: Ensure marker imports work when called from MCP context

## Problem

When marker is called from external contexts (like MCP), relative imports fail:
- `from ..schema import Document` breaks
- Models can't be loaded properly
- Path issues prevent proper module discovery

## Solution

```python
# FILE: /home/graham/workspace/experiments/marker/marker/__init__.py
"""
Marker package initialization with proper path setup
"""

import sys
from pathlib import Path

# Add marker root to Python path
marker_root = Path(__file__).parent.parent
if str(marker_root) not in sys.path:
    sys.path.insert(0, str(marker_root))

# Import key components for easier access
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.schema import Document

__all__ = ['PdfConverter', 'create_model_dict', 'Document']
```

## Files to Update

1. **marker/converters/pdf.py**
   - Replace: `from ..schema.document import Document`
   - With: `from marker.schema.document import Document`

2. **marker/processors/*.py**
   - Fix all relative imports

3. **marker/builders/*.py**
   - Fix all relative imports

## Validation Script

```python
# FILE: test_marker_imports.py
import sys
sys.path.insert(0, '/home/graham/workspace/experiments/marker')

try:
    from marker import PdfConverter, create_model_dict
    from marker.schema import Document
    print("✅ All imports successful")
    
    # Test basic functionality
    models = create_model_dict()
    print("✅ Models loaded successfully")
    
except Exception as e:
    print(f"❌ Import/Load failed: {e}")
```

## Checklist

- [ ] Update marker/__init__.py
- [ ] Fix converters imports
- [ ] Fix processors imports
- [ ] Fix builders imports
- [ ] Run validation script
- [ ] Test from external directory