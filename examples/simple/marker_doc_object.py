"""
Module: marker_doc_object.py
Description: Document processing and marking functionality

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

" + "="*80)
    print(f"DOCUMENT ANALYSIS RESULTS: {results['pdf_path']}")
    print("="*80)
    
    if not results["success"]:
        print(f"❌ Analysis failed: {results['error']}")
        return
        
    print(f"✅ Document loaded successfully in {results['loading_time']:.2f} seconds")
    if results["page_range"]:
        print(f"📄 Page Range: {results['page_range']}")
    
    # Print all blocks summary
    all_blocks = results["all_blocks"]
    print(f"\n==== ALL BLOCKS ({all_blocks['block_count']} total) ====")
    
    # Print block type distribution
    print("\nBlock Type Distribution:")
    for block_type, count in all_blocks["block_types"].items():
        print(f"  - {block_type}: {count}")
    
    # Print sample blocks (first 3)
    print("\nSample Blocks:")
    for i, block in enumerate(all_blocks["sample_blocks"][:3]):
        print(f"\nBlock {i+1}:")
        print(f"  Type: {block['block_type']}")
        print(f"  ID: {block['block_id']}")
        if "text_preview" in block:
            print(f"  Text: {block['text_preview']}")
        if "code_preview" in block:
            print(f"  Code: {block['code_preview']}")
            print(f"  Language: {block['language']}")
            
    # Print tables and images summary
    tables_images = results["tables_and_images"]
    print(f"\n==== TABLES AND IMAGES ({tables_images['block_count']} total) ====")
    
    # Print block type distribution for tables and images
    print("\nBlock Type Distribution:")
    for block_type, count in tables_images["block_types"].items():
        print(f"  - {block_type}: {count}")
        
    # Print sample tables and images (first 3)
    if tables_images["sample_blocks"]:
        print("\nSample Tables/Images:")
        for i, block in enumerate(tables_images["sample_blocks"][:3]):
            print(f"\nTable/Image {i+1}:")
            print(f"  Type: {block['block_type']}")
            print(f"  ID: {block['block_id']}")
            if "text_preview" in block:
                print(f"  Text: {block['text_preview']}")
    else:
        print("\nNo tables or images found in document")

if __name__ == "__main__":
    # Track validation results according to CLAUDE.md requirements
    validation_failures = []
    total_tests = 0
    
    print("=== Marker Document Object Inspection Tool ===")
    
    # Test 1: Parse command line arguments
    total_tests += 1
    try:
        # Default values
        pdf_path = None
        page_range = "1-3"  # Limit to first 3 pages by default
        
        # Parse arguments
        for i, arg in enumerate(sys.argv[1:]):
            if arg == "--page-range" and i+2 < len(sys.argv):
                page_range = sys.argv[i+2]
            elif os.path.exists(arg) and arg.lower().endswith(".pdf"):
                pdf_path = arg
        
        # If no PDF path provided, use sample
        if not pdf_path:
            pdf_path = get_sample_pdf_path()
            
        # Verify PDF exists
        if not os.path.exists(pdf_path):
            validation_failures.append(f"PDF file not found: {pdf_path}")
            print(f"❌ PDF file not found: {pdf_path}")
        else:
            print(f"✅ Using PDF: {pdf_path}")
            print(f"✅ Page range: {page_range}")
    except Exception as e:
        validation_failures.append(f"Failed to parse arguments: {e}")
        print(f"❌ Failed to parse arguments: {e}")
        
    # Test 2: Document loading and analysis
    total_tests += 1
    try:
        results = load_and_analyze_document(pdf_path, page_range)
        
        if results["success"]:
            print(f"✅ Document loaded and analyzed successfully")
            print_analysis_results(results)
        else:
            validation_failures.append(f"Document analysis failed: {results['error']}")
            print(f"❌ Document analysis failed: {results['error']}")
    except Exception as e:
        validation_failures.append(f"Document loading failed: {e}")
        print(f"❌ Document loading failed: {e}")
        import traceback
        traceback.print_exc()
        
    # Test 3: Verify block types are found
    total_tests += 1
    try:
        if results["success"] and results["all_blocks"]["block_count"] > 0:
            print(f"✅ Found {results['all_blocks']['block_count']} blocks in document")
        else:
            validation_failures.append("No blocks found in document")
            print(f"❌ No blocks found in document")
    except Exception as e:
        validation_failures.append(f"Block verification failed: {e}")
        print(f"❌ Block verification failed: {e}")
    
    # Final validation results
    print("\n" + "="*80)
    if validation_failures:
        print(f"❌ VALIDATION FAILED - {len(validation_failures)} of {total_tests} tests failed:")
        for failure in validation_failures:
            print(f"  - {failure}")
        sys.exit(1)
    else:
        print(f"✅ VALIDATION PASSED - All {total_tests} tests produced expected results")
        print("""
Usage Notes:
- Run with a specific PDF: python marker_doc_object.py /path/to/your.pdf
- Specify page range: python marker_doc_object.py --page-range 1-5
- Combine both: python marker_doc_object.py /path/to/your.pdf --page-range 1-5
""")
        sys.exit(0)
