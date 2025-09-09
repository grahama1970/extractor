#!/usr/bin/env python3
"""
Analyze a suspicious PDF block to determine its correct type.

This script examines the characteristics of a garbled text block
to make an informed decision about its actual type.
"""

def analyze_suspicious_block(block_details):
    """
    Analyze a suspicious block and determine its correct type.
    
    Args:
        block_details: Dictionary containing block information
        
    Returns:
        Dictionary with analysis results
    """
    uuid = block_details.get("uuid", "unknown")
    current_type = block_details.get("block_type", "unknown")
    text = block_details.get("text", "")
    page = block_details.get("page", 0)
    suspicion_reasons = block_details.get("suspicion_reasons", [])
    suspicion_score = block_details.get("suspicion_score", 0.0)
    
    print(f"\n=== Analyzing Suspicious Block ===")
    print(f"UUID: {uuid}")
    print(f"Current Type: {current_type}")
    print(f"Text: '{text}'")
    print(f"Page: {page}")
    print(f"Suspicion Reasons: {suspicion_reasons}")
    print(f"Suspicion Score: {suspicion_score}")
    
    # Analysis logic
    analysis_results = {
        "uuid": uuid,
        "original_type": current_type,
        "text": text,
        "analysis": {},
        "recommendation": {}
    }
    
    # Check for garbled text patterns
    if "garbled_table_text" in suspicion_reasons:
        print("\n[Analysis] Block marked as garbled table text")
        
        # Look for patterns that suggest table headers
        # Common table header words that might be corrupted
        table_indicators = ["signal", "io", "description", "type", "connection", 
                          "pin", "name", "value", "unit", "parameter"]
        
        text_lower = text.lower()
        found_indicators = []
        
        # Check for partial matches (accounting for OCR errors)
        for indicator in table_indicators:
            # Check if any part of the indicator appears in the text
            for i in range(len(indicator) - 2):  # Look for 3+ character matches
                substr = indicator[i:i+3]
                if substr in text_lower:
                    found_indicators.append(indicator)
                    break
        
        analysis_results["analysis"]["found_indicators"] = found_indicators
        
        # Analyze the text pattern
        # "SignalIODescripticonnexiTypeonon" appears to be concatenated words
        # This is typical of OCR errors in table headers where spacing is lost
        
        # Try to identify word boundaries
        possible_words = []
        # Look for capital letters that might indicate word starts
        word_start = 0
        for i, char in enumerate(text):
            if i > 0 and char.isupper() and not text[i-1].isupper():
                possible_words.append(text[word_start:i])
                word_start = i
        possible_words.append(text[word_start:])  # Add the last word
        
        # Filter out empty strings
        possible_words = [w for w in possible_words if w]
        
        analysis_results["analysis"]["possible_words"] = possible_words
        print(f"\nPossible word boundaries detected: {possible_words}")
        
        # Determine confidence based on analysis
        confidence = 0.0
        reasoning = []
        
        if len(found_indicators) >= 2:
            confidence += 0.4
            reasoning.append(f"Found {len(found_indicators)} table-related keywords")
        
        if len(possible_words) >= 3:
            confidence += 0.3
            reasoning.append(f"Text appears to contain {len(possible_words)} concatenated words")
        
        if current_type == "Table":
            confidence += 0.2
            reasoning.append("Originally classified as Table")
        
        if "garbled" in " ".join(suspicion_reasons):
            confidence += 0.1
            reasoning.append("Explicitly marked as garbled text")
        
        # Make recommendation
        if confidence >= 0.5:
            recommended_type = "TableCell"
            confidence_level = "moderate" if confidence < 0.7 else "high"
            recommendation_reason = (
                "This appears to be a corrupted table header row. The text pattern "
                "suggests concatenated column headers (possibly 'Signal', 'IO', "
                "'Description', 'Type') that lost spacing during OCR processing."
            )
        else:
            recommended_type = "Paragraph"
            confidence_level = "low"
            recommendation_reason = (
                "While originally classified as Table, the garbled text doesn't "
                "show strong enough patterns to confirm it's a table structure. "
                "Safer to treat as corrupted paragraph text."
            )
    
    else:
        # Default analysis for non-garbled suspicious blocks
        recommended_type = current_type
        confidence_level = "low"
        recommendation_reason = "Insufficient information to reclassify"
        confidence = 0.3
        reasoning = ["No specific garbled text indicators"]
    
    analysis_results["recommendation"] = {
        "new_type": recommended_type,
        "confidence": confidence,
        "confidence_level": confidence_level,
        "reasoning": reasoning,
        "explanation": recommendation_reason
    }
    
    return analysis_results


def main():
    """Test the analysis with the provided block."""
    # The suspicious block from the prompt
    test_block = {
        "uuid": "test-001",
        "block_type": "Table",
        "text": "SignalIODescripticonnexiTypeonon",
        "page": 0,
        "suspicion_reasons": ["garbled_table_text"],
        "suspicion_score": 0.7
    }
    
    results = analyze_suspicious_block(test_block)
    
    print("\n\n=== ANALYSIS RESULTS ===")
    print(f"Original Type: {results['original_type']}")
    print(f"Recommended Type: {results['recommendation']['new_type']}")
    print(f"Confidence Score: {results['recommendation']['confidence']:.2f}")
    print(f"Confidence Level: {results['recommendation']['confidence_level']}")
    print(f"\nReasoning:")
    for reason in results['recommendation']['reasoning']:
        print(f"  - {reason}")
    print(f"\nExplanation: {results['recommendation']['explanation']}")
    
    # Additional test cases
    print("\n\n=== TESTING ADDITIONAL CASES ===")
    
    # Test case 2: Less garbled table text
    test_block2 = {
        "uuid": "test-002",
        "block_type": "Table",
        "text": "Pin Signal Direction",
        "page": 1,
        "suspicion_reasons": ["short_table_text"],
        "suspicion_score": 0.5
    }
    
    results2 = analyze_suspicious_block(test_block2)
    print(f"\nTest 2 - Recommended: {results2['recommendation']['new_type']} "
          f"(confidence: {results2['recommendation']['confidence_level']})")


if __name__ == "__main__":
    main()