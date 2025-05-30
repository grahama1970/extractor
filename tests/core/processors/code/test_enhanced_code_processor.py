=== After Processing ===")
    print(f"Language: {detected_lang}")
    print(f"Metadata exists: {code_block.metadata is not None}")
    
    # Check if tree-sitter data was stored
    if code_block.metadata:
        print("\nMetadata contents:")
        for key, value in code_block.metadata.__dict__.items():
            if key == 'tree_sitter_data' and value:
                print(f"  {key}: <present>")
                ts_data = value
                print(f"    Success: {ts_data.get('tree_sitter_success')}")
                print(f"    Functions: {len(ts_data.get('functions', []))}")
                print(f"    Classes: {len(ts_data.get('classes', []))}")
                
                # Show extracted details
                for func in ts_data.get('functions', []):
                    print(f"\n    Function: {func.get('name')}")
                    print(f"      Parameters: {len(func.get('parameters', []))}")
                    for param in func.get('parameters', []):
                        print(f"        - {param['name']}: {param.get('type', 'Any')}")
                    print(f"      Return type: {func.get('return_type', 'Any')}")
                    
                for cls in ts_data.get('classes', []):
                    print(f"\n    Class: {cls.get('name')}")
                    doc = cls.get('docstring', '')
                    if doc:
                        print(f"      Docstring: {doc[:50]}...")
            else:
                print(f"  {key}: {value}")
    
    print("\n=== Success! ===")
    print("Tree-sitter metadata is now stored on the code block!")
    print("LLMs and downstream processors can access:")
    print("- Function signatures with parameters and types")
    print("- Class structures and methods")
    print("- Docstrings and documentation")
    print("- Return types and parameter defaults")
    
    return code_block

def test_pdf_with_enhanced_processor():
    """Test on actual PDF with enhanced processor"""
    
    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict
    from marker.schema import BlockTypes
    import os
    
    pdf_path = "data/input/python-type-checking-readthedocs-io-en-latest.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"PDF not found: {pdf_path}")
        return
    
    print("\n=== Testing with PDF ===")
    
    # Create converter with enhanced processor
    converter = PdfConverter(
        processor_list=[
            "marker.builders.document",
            "marker.builders.layout",
            "marker.builders.ocr",
            "marker.processors.line_merge",
            "marker.processors.code_enhanced",  # Use our enhanced processor
            "marker.processors.text",
        ],
        artifact_dict=create_model_dict(),
        config={
            "page_range": range(7, 8),  # Just page 7
            "disable_tqdm": True,
        }
    )
    
    # Process the document
    document = converter.build_document(pdf_path)
    
    # Find code blocks with metadata
    code_blocks_with_metadata = []
    for page in document.pages:
        for block in page.contained_blocks(document, (BlockTypes.Code,)):
            if block.metadata and hasattr(block.metadata, 'tree_sitter_data'):
                code_blocks_with_metadata.append(block)
    
    print(f"Found {len(code_blocks_with_metadata)} code blocks with tree-sitter metadata")
    
    # Show first block with metadata
    if code_blocks_with_metadata:
        block = code_blocks_with_metadata[0]
        ts_data = block.metadata.tree_sitter_data
        
        print(f"\nFirst code block with metadata:")
        print(f"  Language: {block.language}")
        print(f"  Functions: {len(ts_data.get('functions', []))}")
        
        for func in ts_data.get('functions', [])[:2]:  # First 2 functions
            print(f"\n  Function: {func.get('name')}")
            print(f"    Parameters:")
            for param in func.get('parameters', []):
                print(f"      - {param['name']}: {param.get('type', 'Any')}")
            print(f"    Return type: {func.get('return_type', 'Any')}")

if __name__ == "__main__":
    # Test the enhanced processor
    result = test_enhanced_processor()
    
    # Test with real PDF
    test_pdf_with_enhanced_processor()