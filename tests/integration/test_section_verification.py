Found {len(issues)} section issues:")
        for i, issue in enumerate(issues, 1):
            logger.info(f"\nIssue {i}:")
            logger.info(f"  Type: {issue['type']}")
            logger.info(f"  Severity: {issue['severity']}")
            logger.info(f"  Description: {issue['description']}")
            logger.info(f"  Suggestion: {issue['suggestion']}")
            logger.info(f"  Confidence: {issue['confidence']:.2f}")
    else:
        logger.info("No section issues found")
    
    return document


def main():
    """Main test function."""
    if len(sys.argv) < 2:
        print("Usage: python test_section_verification.py <pdf_file>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    if not Path(pdf_path).exists():
        print(f"Error: File not found: {pdf_path}")
        sys.exit(1)
    
    # Enable debug logging
    logger.remove()
    logger.add(sys.stderr, level="DEBUG")  # Change to DEBUG for more details
    
    try:
        document = test_section_verification(pdf_path)
        
        # Save results to file
        output_file = Path(pdf_path).stem + "_section_verification.json"
        logger.info(f"\nSaving results to: {output_file}")
        
        import json
        results = {
            "pdf_file": pdf_path,
            "pages": len(document.pages),
            "section_verification": getattr(document, 'section_verification', None),
            "section_issues": getattr(document, 'section_issues', None)
        }
        
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info("Test completed successfully!")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()