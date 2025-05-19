"""
Simple test for code language detection.
"""
from marker.schema.document import Document
from marker.schema.blocks import Code, Page
from marker.processors.code import CodeProcessor
from marker.models import create_model_dict
from marker.schema import BlockTypes
import json

def test_language_detection():
    """Test language detection on code blocks."""
    print("Testing language detection...")
    
    # Create a simple document with code blocks
    document = Document()
    page = Page()
    document.pages.append(page)
    
    # Python code block
    python_code = Code()
    python_code.code = '''def factorial(n):
    """Calculate factorial"""
    if n <= 1:
        return 1
    return n * factorial(n - 1)'''
    page.blocks.append(python_code)
    
    # JavaScript code block
    js_code = Code()
    js_code.code = '''function fetchData(url) {
    return fetch(url)
        .then(response => response.json())
        .then(data => console.log(data));
}'''
    page.blocks.append(js_code)
    
    # Java code block
    java_code = Code()
    java_code.code = '''public class Main {
    public static void main(String[] args) {
        System.out.println("Hello, World!");
    }
}'''
    page.blocks.append(java_code)
    
    # C++ code block
    cpp_code = Code()
    cpp_code.code = '''#include <iostream>
using namespace std;

int main() {
    cout << "Hello, World!" << endl;
    return 0;
}'''
    page.blocks.append(cpp_code)
    
    # Go code block
    go_code = Code()
    go_code.code = '''package main

import "fmt"

func main() {
    fmt.Println("Hello, World!")
}'''
    page.blocks.append(go_code)
    
    # Create processor with language detection enabled
    processor = CodeProcessor({'enable_language_detection': True})
    
    # Process the document
    print("\nProcessing document with CodeProcessor...")
    processor(document)
    
    # Check results
    print("\nResults:")
    languages_detected = []
    for i, block in enumerate(page.blocks):
        if hasattr(block, 'language') and block.language:
            print(f"Block {i}: Detected language = {block.language}")
            print(f"  Code preview: {block.code[:50]}...")
            languages_detected.append(block.language)
        else:
            print(f"Block {i}: No language detected")
    
    # Create verification report
    report_path = "docs/reports/006_task_1_simple_language_detection.md"
    with open(report_path, 'w') as f:
        f.write("# Task 6.1: Simple Language Detection Test\n\n")
        f.write("## Test Results\n\n")
        f.write("```\n")
        f.write("Languages detected:\n")
        for i, lang in enumerate(languages_detected):
            f.write(f"  Block {i}: {lang}\n")
        f.write("```\n\n")
        f.write("## Summary\n")
        f.write(f"- Total blocks: {len(page.blocks)}\n")
        f.write(f"- Languages detected: {len(languages_detected)}\n")
        f.write(f"- Detection rate: {len(languages_detected)/len(page.blocks)*100:.0f}%\n")
    
    print(f"\nReport saved to: {report_path}")
    
    # Also test markdown rendering with language tags
    from marker.renderers.markdown import MarkdownRenderer
    md_renderer = MarkdownRenderer({'markdown_page_separator': '\n\n'})
    
    # First, we need to set up parent-child relationships
    for block in page.blocks:
        block.structure = document.structure
        page.add_structure(block)
    page.structure = document.structure
    document.add_structure(page)
    
    # Render to markdown
    rendered_content = md_renderer(document)
    with open("test_output_with_languages.md", 'w') as f:
        # Extract markdown from the output object
        if hasattr(rendered_content, 'markdown'):
            f.write(rendered_content.markdown)
        else:
            f.write(str(rendered_content))
    
    print("\nMarkdown output saved to: test_output_with_languages.md")

if __name__ == "__main__":
    test_language_detection()