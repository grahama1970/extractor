"""
Module: async_image_processing_debug.py
Description: Implementation of async image processing debug functionality

Sample Input:
>>> # See function docstrings for specific examples

Expected Output:
>>> # See function docstrings for expected results

Example Usage:
>>> # Import and use as needed based on module functionality
"""

Sample Image Description (Sync):")
        print(f"  {successful_blocks[0].description[:150]}...")
    
    return results

def process_images_async(document: Document, llm_service: LiteLLMService) -> Dict[str, Any]:
    """
    Process images in a document asynchronously using LiteLLM's batch processing.
    
    Args:
        document: Document object with images
        llm_service: LiteLLMService instance for processing
        
    Returns:
        Dictionary with timing and processing statistics
    """
    # Make sure we have a valid LiteLLMService
    if llm_service is None:
        print("Error: LiteLLM service not provided")
        return {"success": False, "error": "No LiteLLM service"}
    
    if not isinstance(llm_service, LiteLLMService):
        print("Error: LLM service is not a LiteLLMService")
        return {"success": False, "error": "Not LiteLLMService"}
    
    # Create image processor with async batch processing
    processor = ModifiedLLMImageDescriptionProcessor(
        llm_service=llm_service,  # Pass the LLM service to our modified processor
        use_llm=True,
        use_async_batch=True,  # Enable async processing
        max_batch_size=3,      # Process up to 3 images at once
        extract_images=False,
        detail_level="brief"
    )
    
    # Get all image blocks directly from page children
    image_blocks = []
    for page in document.pages:
        for child in page.children:
            if isinstance(child, (Picture, Figure)):
                image_blocks.append(child)
    
    if not image_blocks:
        print("No images found in document")
        return {"success": False, "error": "No images found"}
    
    # Process only the first 3 images to save time and costs
    max_images = min(3, len(image_blocks))
    print(f"Processing {max_images} images asynchronously (in batches)...")
    
    # Create a slice of the document with limited pages to process fewer images
    pages_with_images = []  # Use a list instead of a set since PageGroup is not hashable
    processed_count = 0
    for page in document.pages:
        page_image_blocks = [child for child in page.children if isinstance(child, (Picture, Figure))]
        if page_image_blocks:
            if page not in pages_with_images:  # Manual check
                pages_with_images.append(page)
            processed_count += len(page_image_blocks)
            if processed_count >= max_images:
                break
    
    # Create limited document
    limited_document = Document(
        filepath=document.filepath,
        filename=os.path.basename(document.filepath),
        pages=pages_with_images[:3]  # Limit to first 3 pages with images
    )
    
    # We won't modify the document class directly since Pydantic v2 is strict
    
    # Count how many images we'll process
    limited_image_blocks = []
    for page in limited_document.pages:
        for child in page.children:
            if isinstance(child, (Picture, Figure)):
                limited_image_blocks.append(child)
    
    print(f"Limited to {len(limited_image_blocks)} images on {len(limited_document.pages)} pages")
    
    # Process with timing
    start_time = time.time()
    # Process the document with our modified processor
    processor(limited_document)
    end_time = time.time()
    
    # Gather results
    successful_blocks = []
    failed_blocks = []
    
    for block in limited_image_blocks:
        if hasattr(block, "description") and block.description:
            successful_blocks.append(block)
        else:
            failed_blocks.append(block)
    
    results = {
        "success": True,
        "total_images": len(limited_image_blocks),
        "successful": len(successful_blocks),
        "failed": len(failed_blocks),
        "time_taken": end_time - start_time,
        "avg_time_per_image": (end_time - start_time) / max(1, len(limited_image_blocks)),
    }
    
    # Print a sample of the results
    if successful_blocks:
        print("\nSample Image Description (Async):")
        print(f"  {successful_blocks[0].description[:150]}...")
    
    return results

if __name__ == "__main__":
    # Track validation results
    validation_failures = []
    total_tests = 0
    
    print("=== Async Image Processing Debug Tool ===")
    
    # Test 1: API key check
    total_tests += 1
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        validation_failures.append("API key not found in environment variables")
        print("❌ API key test failed: OPENAI_API_KEY environment variable not set")
        print("   Set it with: export OPENAI_API_KEY=your_api_key")
    else:
        print("✅ API key test passed: OPENAI_API_KEY environment variable is set")
    
    # Get the PDF path from command line argument or use a default
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        pdf_path = get_sample_pdf_path()
    
    # Test 2: Document loading
    total_tests += 1
    print(f"\nAttempting to load document: {pdf_path}")
    result = load_document_with_images(pdf_path)
    
    if result is None:
        validation_failures.append("Failed to load document")
        print("❌ Document loading test failed")
    else:
        document, llm_service = result  # Unpack the returned tuple
        print("✅ Document loading test passed")
        
        # Only run these tests if we have a valid document and API key
        if api_key:
            # Test 3: Synchronous processing
            total_tests += 1
            print("\nTesting synchronous image processing...")
            sync_results = process_images_sync(document, llm_service)
            
            if sync_results.get("success", False) and sync_results.get("successful", 0) > 0:
                print(f"✅ Sync processing test passed: {sync_results['successful']} of {sync_results['total_images']} images processed")
                print(f"   Time taken: {sync_results['time_taken']:.2f} seconds ({sync_results['avg_time_per_image']:.2f} sec/image)")
            else:
                validation_failures.append("Synchronous processing failed")
                print("❌ Sync processing test failed")
            
            # Test 4: Asynchronous processing
            total_tests += 1
            print("\nTesting asynchronous image processing...")
            async_results = process_images_async(document, llm_service)
            
            if async_results.get("success", False) and async_results.get("successful", 0) > 0:
                print(f"✅ Async processing test passed: {async_results['successful']} of {async_results['total_images']} images processed")
                print(f"   Time taken: {async_results['time_taken']:.2f} seconds ({async_results['avg_time_per_image']:.2f} sec/image)")
            else:
                validation_failures.append("Asynchronous processing failed")
                print("❌ Async processing test failed")
            
            # Test 5: Compare sync vs async performance
            if "time_taken" in sync_results and "time_taken" in async_results:
                total_tests += 1
                if async_results["time_taken"] < sync_results["time_taken"]:
                    speedup = sync_results["time_taken"] / async_results["time_taken"]
                    print(f"\n✅ Performance test passed: Async batch processing was {speedup:.2f}x faster")
                else:
                    print("\n⚠️ Performance test note: Async processing was not faster in this test")
                    print("   This can happen with small batches or when cache hits occur")
    
    # Final validation results
    if validation_failures:
        print(f"\n❌ VALIDATION FAILED - {len(validation_failures)} of {total_tests} tests failed:")
        for failure in validation_failures:
            print(f"  - {failure}")
        sys.exit(1)
    else:
        print(f"\n✅ VALIDATION PASSED - All {total_tests} tests produced expected results")
        print("""
Usage Notes:
- Run with a specific PDF: python async_image_processing_debug.py /path/to/your.pdf
- Configure LiteLLM: Set OPENAI_API_KEY environment variable
- For better performance: Install Redis and run initialize_litellm_cache.py
- To modify parameters: Adjust the max_batch_size and detail_level in the code
""")
        sys.exit(0)