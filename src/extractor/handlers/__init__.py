"""
Module: __init__.py
Description: Marker handler adapter for test compatibility

External Dependencies:
- None
"""

from ..integrations.marker_module import MarkerModule

class MarkerPDFHandler:
    """Adapter for Marker PDF processing to match test expectations"""
    
    def __init__(self):
        self.module = MarkerModule()
    
    def process_pdf(self, pdf_path: str) -> dict:
        """Process PDF file"""
        import asyncio
        
        # Transform to module format
        module_request = {
            "action": "process_pdf",
            "data": {
                "file_path": pdf_path
            }
        }
        
        # Run async module
        result = asyncio.run(self.module.process(module_request))
        
        # Transform response
        if result.get("success"):
            return {
                "success": True,
                "content": result.get("data", {})
            }
        else:
            return {
                "success": False,
                "error": result.get("error", "Unknown error")
            }

__all__ = ['MarkerPDFHandler']
