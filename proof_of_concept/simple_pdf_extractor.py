#!/usr/bin/env python3
"""
Simple PDF to JSON Extractor - Working Example

This script extracts PDFs to structured JSON using the marker-pdf functionality
integrated into the extractor module.
"""

import os
import sys
import json
from pathlib import Path

# Environment setup
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Add extractor source to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Import the core converter directly
from extractor.core.converters.pdf import convert_single_pdf


def extract_pdf_to_json(pdf_path: str) -> dict:
    """
    Extract PDF to JSON using marker-pdf core functionality.
    
    Args:
        pdf_path: Path to PDF file
        
    Returns:
        Dictionary with extracted content
    """
    print(f"Extracting: {pdf_path}")
    
    # Convert PDF to markdown using core marker functionality
    markdown_result = convert_single_pdf(
        pdf_path,
        max_pages=None,  # Process all pages
        langs=["English"],
        ocr_all_pages=False
    )
    
    # Parse the markdown to extract structure
    if isinstance(markdown_result, str):
        markdown_text = markdown_result
    else:
        markdown_text = getattr(markdown_result, 'markdown', str(markdown_result))
    
    # Create structured JSON output
    sections = []
    lines = markdown_text.split('\n')
    current_section = None
    section_id = 0
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Detect headers (markdown style)
        if line.startswith('#'):
            # Count the level
            level = 0
            for char in line:
                if char == '#':
                    level += 1
                else:
                    break
            
            title = line[level:].strip()
            if title:
                # Save previous section
                if current_section and current_section.get('content'):
                    sections.append(current_section)
                
                # Start new section
                section_id += 1
                current_section = {
                    "id": f"section_{section_id}",
                    "title": title,
                    "level": level,
                    "content": ""
                }
        elif current_section is not None:
            # Add content to current section
            if current_section['content']:
                current_section['content'] += '\n'
            current_section['content'] += line
        else:
            # Content before first header
            if not sections and not current_section:
                section_id += 1
                current_section = {
                    "id": f"section_{section_id}",
                    "title": "Introduction",
                    "level": 1,
                    "content": line
                }
    
    # Don't forget the last section
    if current_section and current_section.get('content'):
        sections.append(current_section)
    
    # Build the final JSON structure
    result = {
        "document": {
            "source": pdf_path,
            "title": Path(pdf_path).stem,
            "format": "pdf"
        },
        "sections": sections,
        "metadata": {
            "total_sections": len(sections),
            "extraction_method": "marker-pdf-core",
            "markdown_length": len(markdown_text)
        }
    }
    
    return result


def main():
    """Main function."""
    # Default test PDF
    test_pdf = Path(__file__).parent.parent / "data" / "input" / "2505.03335v2.pdf"
    
    # Check command line argument
    if len(sys.argv) > 1:
        test_pdf = Path(sys.argv[1])
    
    if not test_pdf.exists():
        print(f"Error: PDF not found: {test_pdf}")
        return 1
    
    # Extract
    result = extract_pdf_to_json(str(test_pdf))
    
    # Save output
    output_file = Path(__file__).parent / "simple_extraction_output.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    # Print summary
    print(f"\n✅ Extraction complete!")
    print(f"📊 Summary:")
    print(f"   - Sections: {len(result['sections'])}")
    print(f"   - Output: {output_file}")
    
    # Show sample sections
    print(f"\n📑 Sample sections:")
    for section in result['sections'][:5]:
        print(f"   [{section['level']}] {section['title']}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())