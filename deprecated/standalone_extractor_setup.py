#!/usr/bin/env python3
"""
Standalone setup guide for using extractor's PDF to JSON conversion in another project.

This shows the minimal setup and dependencies needed.
"""

import json
from pathlib import Path


def setup_instructions():
    """Print setup instructions for using extractor in another project."""
    
    print("""
SETUP INSTRUCTIONS FOR USING EXTRACTOR IN ANOTHER PROJECT
========================================================

1. DEPENDENCIES (add to your pyproject.toml or requirements.txt):
   --------------------------------------------------------------
   pymupdf>=1.23.0
   pydantic>=2.0.0
   pillow>=10.0.0
   surya-ocr>=0.4.0
   torch>=2.0.0
   transformers>=4.35.0
   
2. MINIMAL CODE EXAMPLE:
   --------------------
   """)
    
    minimal_code = '''
import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from pathlib import Path
import json

# Option A: If you have extractor installed as a package
from extractor.core.convert import convert_pdf_to_json

# Option B: If copying the code directly
from your_project.extractor.core.convert import convert_pdf_to_json

def extract_pdf(pdf_path: str) -> dict:
    """Extract PDF to structured JSON."""
    return convert_pdf_to_json(
        pdf_path,
        disable_multiprocessing=True,
        disable_tqdm=True,
        use_llm=False  # Set True if you want AI enhancement
    )

# Usage
result = extract_pdf("document.pdf")
print(json.dumps(result, indent=2))
'''
    
    print(minimal_code)
    
    print("""
3. REQUIRED FILES TO COPY (if not installing as package):
   ------------------------------------------------------
   From extractor project, copy these directories:
   - src/extractor/core/convert.py
   - src/extractor/core/converters/
   - src/extractor/core/renderers/
   - src/extractor/core/processors/
   - src/extractor/core/builders/
   - src/extractor/core/schema/
   - src/extractor/core/providers/
   - src/extractor/core/models.py
   - src/extractor/core/settings.py
   - src/extractor/core/util.py
   
4. ENVIRONMENT SETUP:
   -----------------
   export PYTHONPATH=/path/to/your/project/src:$PYTHONPATH
   
5. COMMON ISSUES AND FIXES:
   ------------------------
   - ImportError for extractor modules: Ensure PYTHONPATH is set
   - Model download issues: Models will auto-download on first run
   - Memory issues: Use max_pages parameter to limit processing
   - GPU issues: Set CUDA_VISIBLE_DEVICES="" to force CPU mode
    """)


def create_minimal_wrapper():
    """Create a minimal wrapper that can be copied to another project."""
    
    wrapper_code = '''#!/usr/bin/env python3
"""
Minimal PDF to JSON extractor wrapper.
Copy this file to your project and adjust imports as needed.
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional

# Set required environment variables
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"


class PDFExtractor:
    """Simple wrapper for PDF extraction."""
    
    def __init__(self, use_llm: bool = False):
        """Initialize extractor.
        
        Args:
            use_llm: Enable LLM enhancement (requires API keys)
        """
        self.use_llm = use_llm
        self._converter = None
    
    def _get_converter(self):
        """Lazy load converter to avoid import issues."""
        if self._converter is None:
            from extractor.core.converters.pdf import PdfConverter
            from extractor.core.models import create_model_dict
            
            config = {
                "disable_multiprocessing": True,
                "disable_tqdm": True,
                "use_llm": self.use_llm,
            }
            
            self._converter = PdfConverter(
                artifact_dict=create_model_dict(),
                renderer="extractor.core.renderers.json.JSONRenderer",
                config=config
            )
        return self._converter
    
    def extract(self, pdf_path: str, max_pages: Optional[int] = None) -> Dict[str, Any]:
        """Extract PDF to JSON.
        
        Args:
            pdf_path: Path to PDF file
            max_pages: Limit number of pages to process
            
        Returns:
            Structured JSON dict with extracted content
        """
        if not Path(pdf_path).exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")
        
        # Add max_pages to config if specified
        if max_pages:
            self._converter = None  # Reset to apply new config
            self.max_pages = max_pages
        
        converter = self._get_converter()
        result = converter(pdf_path)
        return result.model_dump()
    
    def extract_to_file(self, pdf_path: str, output_path: str, **kwargs):
        """Extract PDF and save to JSON file."""
        result = self.extract(pdf_path, **kwargs)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        return output_path


# Example usage
if __name__ == "__main__":
    extractor = PDFExtractor(use_llm=False)
    
    # Extract PDF
    result = extractor.extract("sample.pdf", max_pages=5)
    
    # Save to file
    extractor.extract_to_file("sample.pdf", "output.json")
    
    # Access structured data
    for page in result.get("children", []):
        print(f"Page with {len(page.get('children', []))} blocks")
'''
    
    with open("pdf_extractor_wrapper.py", "w") as f:
        f.write(wrapper_code)
    
    print("\n✓ Created pdf_extractor_wrapper.py - a minimal wrapper you can copy to your project")


if __name__ == "__main__":
    setup_instructions()
    create_minimal_wrapper()
    
    print("\n" + "="*60)
    print("QUICK TEST")
    print("="*60)
    
    # Try the simple import approach
    try:
        from extractor.core.convert import convert_pdf_to_json
        print("✓ Import successful! The extractor module is available.")
        
        # Test with a sample file if available
        test_pdf = "data/input/2505.03335v2.pdf"
        if Path(test_pdf).exists():
            print(f"\n✓ Found test PDF: {test_pdf}")
            print("  Run one of the example scripts to test conversion:")
            print("  - python simple_pdf_to_json_poc.py")
            print("  - python minimal_pdf_json_example.py")
        
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        print("\nMake sure you're running this from the extractor project directory")