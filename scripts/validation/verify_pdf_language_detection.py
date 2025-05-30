"""
Verification script for language detection in PDF processing pipeline.
"""
import tempfile
import os
import json
from pathlib import Path
from marker.converters.pdf import PdfConverter
from marker.config.parser import ParserConfig
from marker.schema import BlockTypes
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test code samples to include in the PDF
test_code_samples = {
    'python': '''
def factorial(n):
    """Calculate factorial of n"""
    if n <= 1:
        return 1
    return n * factorial(n - 1)

class Calculator:
    def __init__(self):
        self.result = 0
    
    def add(self, x, y):
        return x + y
''',
    'javascript': '''
function fetchData(url) {
    return fetch(url)
        .then(response => response.json())
        .then(data => {
            console.log('Data:', data);
            return data;
        });
}

const calculator = {
    add: (a, b) => a + b,
    multiply: (a, b) => a * b
};
''',
    'java': '''
public class Main {
    public static void main(String[] args) {
        System.out.println("Hello, World!");
        Calculator calc = new Calculator();
        int result = calc.add(5, 3);
    }
    
    private static class Calculator {
        public int add(int a, int b) {
            return a + b;
        }
    }
}
'''
}

def create_test_pdf():
    """Create a test PDF with code samples."""
    try:
        from fpdf import FPDF
    except ImportError:
        import subprocess
        subprocess.check_call(["pip", "install", "fpdf2"])
        from fpdf import FPDF
    
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, "Language Detection Test PDF", ln=True, align='C')
    pdf.ln(5)
    
    for lang, code in test_code_samples.items():
        pdf.set_font("Arial", style='B', size=14)
        pdf.cell(0, 10, f'{lang.upper()} Code Example:', ln=True)
        pdf.set_font("Courier", size=10)
        
        # Add code in a box
        for line in code.strip().split('\n'):
            pdf.cell(0, 5, line, ln=True)
        
        pdf.ln(10)
    
    # Save to temporary file
    temp_file = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
    pdf.output(temp_file.name)
    logger.info(f"Created test PDF at {temp_file.name}")
    return temp_file.name

def verify_language_detection():
    """Verify language detection works in PDF conversion pipeline."""
    # Step 1: Create test PDF
    pdf_path = create_test_pdf()
    
    try:
        # Step 2: Configure converter with language detection enabled
        logger.info("Configuring converter with language detection enabled")
        config = {
            "enable_language_detection": True,
            "language_detection_min_confidence": 0.5,
            "fallback_language": "text",
            "parser_options": {},
        }
        
        # Step 3: Convert PDF
        logger.info("Converting PDF")
        converter = PdfConverter(config=config)
        document = converter(pdf_path)
        
        # Step 4: Analyze results
        logger.info("Analyzing results")
        results = []
        
        for page in document.pages:
            for block in page.blocks:
                if block.block_type == BlockTypes.Code:
                    # Extract first few lines to identify the language
                    code_preview = block.code[:50].replace("\n", "\\n")
                    expected_lang = None
                    
                    # Try to determine expected language from code preview
                    if "def " in code_preview or "class " in code_preview:
                        expected_lang = "python"
                    elif "function " in code_preview or "const " in code_preview:
                        expected_lang = "javascript"
                    elif "public class" in code_preview or "System.out" in code_preview:
                        expected_lang = "java"
                    
                    result = {
                        "detected_language": getattr(block, "language", None),
                        "expected_language": expected_lang,
                        "code_preview": code_preview,
                        "page": page.number
                    }
                    
                    results.append(result)
                    
                    logger.info(f"Block: {result['code_preview'][:30]}...")
                    logger.info(f"  Detected: {result['detected_language']}")
                    logger.info(f"  Expected: {result['expected_language']}")
        
        # Step 5: Generate summary
        correct = sum(1 for r in results if r["detected_language"] == r["expected_language"])
        total = len(results)
        accuracy = correct / total if total > 0 else 0
        
        summary = {
            "total_blocks": total,
            "correct_detections": correct,
            "accuracy": accuracy,
            "results": results
        }
        
        logger.info(f"Summary: {correct}/{total} correct detections ({accuracy:.2%})")
        
        # Save results to file
        output_dir = Path("test_results/pdf_language_detection")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        with open(output_dir / "results.json", "w") as f:
            json.dump(summary, f, indent=2)
            
        logger.info(f"Results saved to {output_dir / 'results.json'}")
        
        # Generate a simple report
        with open(output_dir / "report.md", "w") as f:
            f.write("# PDF Language Detection Verification\n\n")
            f.write(f"## Summary\n")
            f.write(f"- **Total Code Blocks**: {total}\n")
            f.write(f"- **Correct Detections**: {correct}\n")
            f.write(f"- **Accuracy**: {accuracy:.2%}\n\n")
            
            f.write("## Detailed Results\n\n")
            f.write("| Page | Expected | Detected | Code Preview |\n")
            f.write("|------|----------|----------|-------------|\n")
            
            for r in results:
                preview = r["code_preview"][:30] + "..."
                f.write(f"| {r['page']} | {r['expected_language']} | {r['detected_language']} | `{preview}` |\n")
                
        logger.info(f"Report saved to {output_dir / 'report.md'}")
        
    finally:
        # Clean up
        os.unlink(pdf_path)
        logger.info(f"Deleted temporary PDF {pdf_path}")

if __name__ == "__main__":
    verify_language_detection()