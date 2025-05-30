"""
Simple test of language detection on the provided PDF.
"""
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import save_output
from marker.processors.code import CodeProcessor
from pathlib import Path
import json

def test_simple_pdf():
    """Test language detection on PDF."""
    
    # Path to the test PDF
    pdf_path = "."
    
    print(f"Testing language detection on: {pdf_path}")
    print("This may take a moment for model initialization...")
    
    # Create models
    models = create_model_dict()
    
    # Create converter with language detection enabled
    config_dict = {
        'enable_language_detection': True
    }
    
    converter = PdfConverter(
        config=config_dict,
        artifact_dict=models,
        # We'll use default processors which includes CodeProcessor
    )
    
    try:
        # Convert the PDF  
        print("\nConverting PDF...")
        rendered = converter(pdf_path)
        
        # Save output
        output_folder = Path("test_output_lang_detection")
        output_folder.mkdir(exist_ok=True)
        save_output(rendered, output_folder, "python-type-checking")
        
        print(f"\nOutput saved to: {output_folder}")
        
        # Check markdown for language tags
        md_file = output_folder / "python-type-checking.md"
        if md_file.exists():
            with open(md_file, 'r') as f:
                markdown = f.read()
            
            # Count language tags
            python_count = markdown.count('```python')
            total_code = markdown.count('```')
            
            print(f"\nLanguage detection results:")
            print(f"Total code blocks: {total_code // 2}")
            print(f"Python blocks: {python_count}")
            
            # Show first few code blocks
            import re
            code_blocks = re.findall(r'```(\w*)\n(.*?)\n```', markdown, re.DOTALL)[:3]
            
            print("\nFirst 3 code blocks:")
            for i, (lang, code) in enumerate(code_blocks):
                print(f"\nBlock {i+1} - Language: {lang or 'none'}")
                print(f"Code preview: {code[:100]}...")
                
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_simple_pdf()