")

validator = CitationMatchValidator(min_score=80.0)
print(f"Validator name: {validator.name}")
print(f"Description: {validator.description}")

# Test case 1: Valid citations matching references
response1 = {
    "citations": [
        "Smith et al. (2023) found that machine learning improves accuracy.",
        "Johnson (2022) demonstrated the effectiveness of neural networks."
    ]
}
context1 = {
    "references": [
        "Smith, J., Doe, A., & Brown, C. (2023). Machine learning improves accuracy in medical diagnosis. Journal of AI Medicine, 15(3), 45-60.",
        "Johnson, R. (2022). Neural networks and their effectiveness in pattern recognition. Computer Science Review, 8(2), 123-145."
    ]
}

result1 = validator.validate(response1, context1)
print(f"\nTest 1 - Valid citations: {result1.valid}")
print(f"Result: {result1}")
if result1.debug_info:
    print(f"Debug info: {result1.debug_info}")

# Test case 2: No matching references
response2 = {
    "citations": [
        "Wilson (2021) argued that quantum computing is the future.",
        "Davis (2020) showed limitations of current algorithms."
    ]
}
context2 = {
    "references": [
        "Different Author (2019). Unrelated paper about biology.",
        "Another Author (2018). Completely different topic."
    ]
}

result2 = validator.validate(response2, context2)
print(f"\nTest 2 - No matching references: {result2.valid}")
print(f"Result: {result2}")
if result2.error:
    print(f"Error: {result2.error}")
if result2.suggestions:
    print(f"Suggestions: {result2.suggestions}")

# Test case 3: No citations
response3 = {"citations": []}
result3 = validator.validate(response3, {})
print(f"\nTest 3 - No citations: {result3.valid}")
print(f"Error: {result3.error}")

# Test CitationFormatValidator
print("\n\n=== Testing CitationFormatValidator ===\n")

apa_validator = CitationFormatValidator(format_style="apa")
print(f"Validator name: {apa_validator.name}")
print(f"Description: {apa_validator.description}")

# Test case 1: Valid APA format
apa_response1 = {
    "citations": [
        "Smith, J. A. (2023). The future of AI. Tech Publishers.",
        "Johnson, R. B., & Davis, K. L. (2022). Neural networks explained. Science Press."
    ]
}

apa_result1 = apa_validator.validate(apa_response1, {})
print(f"\nTest 1 - Valid APA format: {apa_result1.valid}")
print(f"Result: {apa_result1}")

# Test case 2: Invalid APA format
apa_response2 = {
    "citations": [
        "smith 2023 ai future",  # Missing proper capitalization and format
        "Johnson & Davis. Neural networks"  # Missing year and period
    ]
}

apa_result2 = apa_validator.validate(apa_response2, {})
print(f"\nTest 2 - Invalid APA format: {apa_result2.valid}")
print(f"Error: {apa_result2.error}")
if apa_result2.debug_info:
    print(f"Invalid citations: {apa_result2.debug_info['invalid_citations']}")

# Test CitationRelevanceValidator
print("\n\n=== Testing CitationRelevanceValidator ===\n")

relevance_validator = CitationRelevanceValidator(min_relevance_score=70.0)
print(f"Validator name: {relevance_validator.name}")
print(f"Description: {relevance_validator.description}")

# Test case 1: Citations referenced in content
content_response1 = {
    "content": "According to Smith et al. [1], machine learning has revolutionized healthcare. Johnson (2022) further supported this claim.",
    "citations": [
        "Smith, J., et al. (2023). Machine learning in healthcare.",
        "Johnson, R. (2022). Supporting evidence for ML applications."
    ]
}

relevance_result1 = relevance_validator.validate(content_response1, {})
print(f"\nTest 1 - Referenced citations: {relevance_result1.valid}")
print(f"Result: {relevance_result1}")

# Test case 2: Unreferenced citations
content_response2 = {
    "content": "Machine learning is important in modern technology.",
    "citations": [
        "Unreferenced, A. (2023). This citation is not mentioned in the text.",
        "AlsoUnreferenced, B. (2022). Neither is this one."
    ]
}

relevance_result2 = relevance_validator.validate(content_response2, {})
print(f"\nTest 2 - Unreferenced citations: {relevance_result2.valid}")
print(f"Error: {relevance_result2.error}")
if relevance_result2.debug_info:
    print(f"Irrelevant citations: {relevance_result2.debug_info['irrelevant_citations']}")

print("\n=== All Citation Validator Tests Completed ===")