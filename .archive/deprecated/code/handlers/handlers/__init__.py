"""
Module: __init__.py
Description: Marker handler adapter for test compatibility

External Dependencies:
- None
"""

class MarkerPDFHandler:
    """Adapter for Marker PDF processing to match test expectations"""
    
    def __init__(self):
        pass  # No longer need MarkerModule
    
    def process_pdf(self, pdf_path: str) -> dict:
        """Process PDF file using marker directly"""
        import subprocess
        import tempfile
        import json
        import shutil
        from pathlib import Path
        
        output_dir = tempfile.mkdtemp()
        
        try:
            # Call marker
            cmd = [
                "python", "-m", "marker.convert",
                pdf_path, output_dir,
                "--parallel_factor", "1",
                "--output_format", "json"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # Find output
            base_name = Path(pdf_path).stem
            json_path = Path(output_dir) / f"{base_name}.json"
            
            if json_path.exists():
                with open(json_path) as f:
                    data = json.load(f)
                return {
                    "success": True,
                    "content": data
                }
            else:
                return {
                    "success": False,
                    "error": f"No output found: {result.stderr}"
                }
                
        finally:
            shutil.rmtree(output_dir, ignore_errors=True)

__all__ = ['MarkerPDFHandler']
