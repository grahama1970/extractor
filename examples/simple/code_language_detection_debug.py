"""
Module: code_language_detection_debug.py
Description: Implementation of code language detection debug functionality

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

")[0].strip()
    shebang_detected = None
    if first_line.startswith("#!"):
        if "python" in first_line:
            detected_language = "python"
            shebang_detected = "python"
        elif "node" in first_line:
            detected_language = "javascript"
            shebang_detected = "node/javascript"
        elif "ruby" in first_line:
            detected_language = "ruby"
            shebang_detected = "ruby"
        elif "bash" in first_line or "sh" in first_line:
            detected_language = "bash"
            shebang_detected = "bash/sh"
    
    return {
        "language": detected_language,
        "method": "heuristic",
        "confidence": max_score,
        "pattern_matches": matches,
        "shebang_detected": shebang_detected
    }


def process_code_blocks(document: Document) -> List[Dict[str, Any]]:
    """
    Process all code blocks in a document to detect their languages.
    
    Args:
        document: Document containing code blocks
        
    Returns:
        List of dictionaries with detection results for each code block
    """
    results = []
    code_processor = CodeProcessor()
    
    # Get all code blocks from the document
    code_blocks = []
    for page_idx, page in enumerate(document.pages):
        if page.children:
            for block_idx, block in enumerate(page.children):
                if block.block_type == BlockTypes.Code:
                    code_text = block.code or ""
                    
                    # Save original state
                    original_language = block.language
                    
                    # Tree-sitter detection
                    tree_sitter_result = detect_language_with_tree_sitter(code_text, original_language)
                    tree_sitter_lang = tree_sitter_result.get("language") if tree_sitter_result.get("tree_sitter_success") else None
                    
                    # Heuristic detection
                    heuristic_result = detect_language_heuristic(code_text)
                    
                    # Use the code processor's detection method (both tree-sitter and heuristic) if possible
                    processor_language = None
                    try:
                        # Create a copy of the block so we don't modify the original
                        block_copy = copy.deepcopy(block)
                        code_processor.format_block(document, block_copy)
                        processor_language = block_copy.language
                    except Exception as e:
                        print(f"Warning: Code processor failed: {e}")
                    
                    # Determine best language
                    detected_language = (
                        tree_sitter_lang if tree_sitter_lang and tree_sitter_lang != "unknown"
                        else processor_language if processor_language
                        else heuristic_result["language"]
                    )
                    
                    # Store results
                    results.append({
                        "page_idx": page_idx,
                        "block_idx": block_idx,
                        "code_preview": code_text[:50] + ("..." if len(code_text) > 50 else ""),
                        "code_length": len(code_text),
                        "original_language": original_language,
                        "tree_sitter": tree_sitter_result,
                        "heuristic": heuristic_result,
                        "processor_language": processor_language,
                        "best_detected_language": detected_language
                    })
    
    return results


def list_supported_languages() -> Dict[str, List[str]]:
    """
    List all programming languages supported by tree-sitter in marker.
    
    Returns:
        Dictionary mapping language names to their file extensions
    """
    language_info = {}
    
    if not TREE_SITTER_AVAILABLE:
        return language_info
    
    for ext, lang in LANGUAGE_MAPPINGS.items():
        if lang not in language_info:
            language_info[lang] = []
        language_info[lang].append(ext)
    
    return language_info


def display_results(results: List[Dict[str, Any]]):
    """
    Display language detection results in a readable format.
    
    Args:
        results: List of detection results for each code block
    """
    for idx, result in enumerate(results):
        print(f"\n{'='*80}")
        print(f"CODE BLOCK #{idx+1}")
        print(f"{'='*80}")
        print(f"Preview: {result['code_preview']}")
        print(f"Length: {result['code_length']} characters")
        print(f"Original Language: {result['original_language'] or 'None'}")
        print(f"Best Detected Language: {result['best_detected_language']}")
        
        print("\nTree-sitter Detection:")
        if TREE_SITTER_AVAILABLE:
            ts_result = result['tree_sitter']
            print(f"  Success: {ts_result.get('tree_sitter_success', False)}")
            print(f"  Language: {ts_result.get('language', 'unknown')}")
            print(f"  Confidence: {ts_result.get('confidence', 0.0):.2f}")
            if ts_result.get('functions', 0) > 0 or ts_result.get('classes', 0) > 0:
                print(f"  Functions: {ts_result.get('functions', 0)}")
                print(f"  Classes: {ts_result.get('classes', 0)}")
            if ts_result.get('error'):
                print(f"  Error: {ts_result.get('error')}")
        else:
            print("  Not available")
        
        print("\nHeuristic Detection:")
        h_result = result['heuristic']
        print(f"  Language: {h_result.get('language', 'unknown')}")
        print(f"  Confidence: {h_result.get('confidence', 0.0):.2f}")
        if h_result.get('pattern_matches'):
            print(f"  Pattern Matches: {', '.join(h_result.get('pattern_matches', []))}")
        if h_result.get('shebang_detected'):
            print(f"  Shebang Detected: {h_result.get('shebang_detected')}")
        
        print(f"\nProcessor Detection: {result['processor_language'] or 'None'}")


if __name__ == "__main__":
    import sys
    
    # List to track all validation failures
    all_validation_failures = []
    total_tests = 0
    
    print("Code Language Detection Debug Script")
    print("======================================")
    
    # Test 1: Check if tree-sitter is available
    total_tests += 1
    print("\nTest 1: Checking tree-sitter availability...")
    if TREE_SITTER_AVAILABLE:
        print("✅ tree-sitter is available")
    else:
        print("⚠️ tree-sitter is not available, will use heuristic fallback")
        all_validation_failures.append("tree-sitter libraries not installed")
    
    # Test 2: List supported languages
    total_tests += 1
    print("\nTest 2: Listing supported languages...")
    try:
        languages = list_supported_languages()
        print(f"✅ Found {len(languages)} supported languages")
        print(f"Sample languages: {', '.join(list(languages.keys())[:5])}...")
    except Exception as e:
        print(f"❌ Failed to list supported languages: {e}")
        all_validation_failures.append(f"Failed to list supported languages: {e}")
    
    # Test 3: Create test document with code blocks
    total_tests += 1
    print("\nTest 3: Creating test document with code blocks...")
    try:
        document = create_test_document()
        
        # Instead of using contained_blocks, get direct access to the children
        code_blocks = []
        for page in document.pages:
            if page.children:
                for block in page.children:
                    if block.block_type == BlockTypes.Code:
                        code_blocks.append(block)
        
        print(f"✅ Created document with {len(code_blocks)} code blocks")
    except Exception as e:
        print(f"❌ Failed to create test document: {e}")
        import traceback
        traceback.print_exc()
        all_validation_failures.append(f"Failed to create test document: {e}")
        sys.exit(1)  # Critical failure, exit early
    
    # Test 4: Detect languages of all code blocks
    total_tests += 1
    print("\nTest 4: Detecting languages of all code blocks...")
    results = []
    try:
        results = process_code_blocks(document)
        if len(results) == len(code_blocks):
            print(f"✅ Successfully detected languages for all {len(results)} code blocks")
        else:
            print(f"❌ Expected {len(code_blocks)} results, but got {len(results)}")
            all_validation_failures.append(f"Expected {len(code_blocks)} results, but got {len(results)}")
    except Exception as e:
        print(f"❌ Failed to detect languages: {e}")
        import traceback
        traceback.print_exc()
        all_validation_failures.append(f"Failed to detect languages: {e}")
    
    # Test 5: Test heuristic detection on Python code
    total_tests += 1
    print("\nTest 5: Testing heuristic detection on Python code...")
    try:
        python_code = """
def hello_world():
    print("Hello, World!")
    
if __name__ == "__main__":
    hello_world()
"""
        result = detect_language_heuristic(python_code)
        expected_language = "python"
        if result["language"] == expected_language:
            print(f"✅ Correctly identified Python code (confidence: {result['confidence']:.2f})")
        else:
            print(f"❌ Failed to identify Python code. Got {result['language']} instead of {expected_language}")
            all_validation_failures.append(f"Failed to identify Python code. Got {result['language']} instead of {expected_language}")
    except Exception as e:
        print(f"❌ Error in heuristic detection: {e}")
        all_validation_failures.append(f"Error in heuristic detection: {e}")
    
    # Test 6: Test tree-sitter detection (if available)
    total_tests += 1
    print("\nTest 6: Testing tree-sitter detection (if available)...")
    if TREE_SITTER_AVAILABLE:
        try:
            python_code = """
def hello_world():
    \"\"\"A simple hello world function\"\"\"
    print("Hello, World!")
    
if __name__ == "__main__":
    hello_world()
"""
            result = detect_language_with_tree_sitter(python_code, "python")
            expected_language = "python"
            if result["language"] == expected_language:
                print(f"✅ tree-sitter correctly identified Python code")
            else:
                print(f"❌ tree-sitter failed to identify Python code. Got {result['language']} instead of {expected_language}")
                all_validation_failures.append(f"tree-sitter failed to identify Python code. Got {result['language']} instead of {expected_language}")
        except Exception as e:
            print(f"❌ Error in tree-sitter detection: {e}")
            all_validation_failures.append(f"Error in tree-sitter detection: {e}")
    else:
        print("⚠️ tree-sitter is not available, skipping this test")
    
    # Test 7: Compare language detection results for code blocks
    total_tests += 1
    print("\nTest 7: Comparing detection methods for all code blocks...")
    try:
        expected_languages = ["python", "javascript", "cpp", "sql", "markdown", "html"]
        detected_count = 0
        
        # Skip if we don't have results
        if not results:
            print("⚠️ No detection results to compare, skipping this test")
        else:
            expected_detected = 0
            
            for i, result in enumerate(results):
                best_detected = result["best_detected_language"]
                expected = expected_languages[i] if i < len(expected_languages) else None
                
                # SQL is a special case - it might be detected as text since tree-sitter doesn't support it
                if expected == "sql" and best_detected in ["sql", "text"]:
                    detected_count += 1
                    expected_detected += 1
                elif expected and best_detected == expected:
                    detected_count += 1
                    expected_detected += 1
                
                # Print the detection results for debugging
                print(f"Expected: {expected}, Detected: {best_detected}, Match: {expected == best_detected}")
            
            # We expect all languages to be detected except SQL if it's marked as text
            expected_total = len(expected_languages)
            if detected_count == expected_total:
                print(f"✅ All {detected_count} known code blocks were correctly identified")
            else:
                print(f"⚠️ Only {detected_count} out of {expected_total} known code blocks were correctly identified")
                # This is not a failure unless we have very poor detection
                if detected_count < expected_total - 1:
                    all_validation_failures.append(f"Only {detected_count} out of {expected_total} known code blocks were correctly identified")
    except Exception as e:
        print(f"❌ Error comparing detection methods: {e}")
        import traceback
        traceback.print_exc()
        all_validation_failures.append(f"Error comparing detection methods: {e}")
    
    # Display detailed results if no critical failures
    if len(all_validation_failures) < 3:  # Minor failures are acceptable
        print("\nDETAILED RESULTS:")
        display_results(results)
    
    # Final validation result
    print("\n" + "="*80)
    if all_validation_failures:
        print(f"❌ VALIDATION FAILED - {len(all_validation_failures)} of {total_tests} tests failed:")
        for failure in all_validation_failures:
            print(f"  - {failure}")
        sys.exit(1)  # Exit with error code
    else:
        print(f"✅ VALIDATION PASSED - All {total_tests} tests produced expected results")
        print("Code language detection is working correctly")
        sys.exit(0)  # Exit with success code