=== After Processing ===")
    print(f"Language: {code_block.language}")
    print(f"Metadata: {code_block.metadata}")
    
    # Show what tree-sitter COULD extract
    metadata = extract_code_metadata(test_code, "python")
    
    print("\n=== What Tree-Sitter Can Extract ===")
    print(f"Successful: {metadata.get('tree_sitter_success')}")
    print(f"Functions: {len(metadata.get('functions', []))}")
    
    for func in metadata.get('functions', []):
        print(f"\nFunction: {func['name']}")
        print(f"  Parameters: {len(func.get('parameters', []))} found")
        for param in func.get('parameters', []):
            print(f"    - {param['name']}: {param.get('type', 'Any')}")
        print(f"  Return type: {func.get('return_type', 'Any')}")
        doc = func.get('docstring', '')
        if doc:
            print(f"  Docstring: {doc[:50]}...")
    
    print("\n=== The Problem ===")
    print("Tree-sitter extracted rich metadata (parameters, types, docstrings)")
    print("but CodeProcessor only uses it for language detection scoring.")
    print("The metadata is NOT stored on the code block for downstream use!")
    
    # Show what SHOULD be stored
    print("\n=== What Should Be Stored ===")
    print("code_block.tree_sitter_metadata = {")
    print("    'functions': [...],")
    print("    'classes': [...],")
    print("    'language': 'python',")
    print("    'success': True")
    print("}")
    
    return metadata

if __name__ == "__main__":
    result = main()