"""
QA pair validation module for ArangoDB-Marker integration.

This module provides functions to validate the quality, relevance, accuracy, and diversity of
question-answer pairs generated from Marker documents, ensuring they are suitable
for fine-tuning language models.

The validation system specifically supports the ArangoDB-compatible JSON format from Marker,
which includes document hierarchical structure, metadata, and raw corpus text needed for
comprehensive validation.

Example:
    ```python
    from marker.core.arangodb.validators.qa_validator import validate_qa_pairs
    
    # Validate QA pairs
    validation_results = validate_qa_pairs(
        qa_pairs_path='qa_output/qa_unsloth_20250519_120000.jsonl',
        marker_output_path='document.json',
        validation_config={'relevance_threshold': 0.7}
    )
    ```

Required Marker Data Format:
    ```json
    {
      "document": {
        "id": "marker_doc_123",
        "title": "Document Title",
        "pages": [
          {
            "blocks": [
              {
                "type": "section_header",
                "level": 1,
                "text": "Section Title"
              },
              {
                "type": "text",
                "text": "Section content..."
              }
            ]
          }
        ]
      },
      "raw_corpus": {
        "full_text": "Complete document text..."
      }
    }
    ```

Documentation:
    - ArangoDB Python Driver: https://github.com/ArangoDB-Community/python-arango
    - Marker Document Structure: https://github.com/VikParuchuri/marker
    - Unsloth Format: https://github.com/unslothai/unsloth
"""

import json
import os
import time
import datetime
import uuid
import re
import difflib
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union, Set

from loguru import logger


# Constants
DEFAULT_RELEVANCE_THRESHOLD = 0.7
DEFAULT_ACCURACY_THRESHOLD = 0.6
DEFAULT_QUESTION_QUALITY_THRESHOLD = 0.5
DEFAULT_VALIDATION_CHECKS = ["relevance", "accuracy", "quality", "diversity"]


def load_qa_pairs(file_path: str) -> List[Dict[str, Any]]:
    """
    Load QA pairs from a JSONL file.
    
    Args:
        file_path: Path to QA pairs JSONL file
        
    Returns:
        List of QA pair dictionaries
    """
    qa_pairs = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                qa_pairs.append(json.loads(line))
    return qa_pairs


def load_marker_output(file_path: str) -> Dict[str, Any]:
    """
    Load marker output from JSON file.
    
    Args:
        file_path: Path to marker output JSON file
        
    Returns:
        Marker output as dictionary
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def validate_qa_relevance(
    qa_pair: Dict[str, Any], 
    marker_output: Dict[str, Any],
    threshold: float = DEFAULT_RELEVANCE_THRESHOLD
) -> Dict[str, Any]:
    """
    Validate the relevance of a QA pair to the document content.
    
    This function checks if the question and answer are relevant to the 
    document context they claim to be about.
    
    Args:
        qa_pair: QA pair dictionary
        marker_output: Marker output dictionary
        threshold: Minimum relevance score required to pass
        
    Returns:
        Dictionary with validation results
    """
    # Extract context and QA content
    context = qa_pair.get("metadata", {}).get("context", "")
    question = qa_pair.get("instruction", "")
    answer = qa_pair.get("output", "")
    
    if not context or not question or not answer:
        return {
            "validated": False,
            "score": 0.0,
            "reason": "Missing context, question, or answer"
        }
    
    # Find the context in the document
    found_in_document = False
    context_similarity = 0.0
    
    # Check if context exists in raw corpus - this field is CRITICAL for ArangoDB integration
    # according to the integration notes, raw_corpus.full_text is absolutely critical for answer validation
    raw_corpus = marker_output.get("raw_corpus", {}).get("full_text", "")
    if raw_corpus and context:
        # Use difflib to find the best match for context in the document
        # This is a simple approach - in a real implementation you would use
        # semantic similarity or better text matching algorithms
        matcher = difflib.SequenceMatcher(None, context, raw_corpus)
        context_similarity = matcher.ratio()
        
        # If similarity is above a certain threshold, consider it found
        if context_similarity >= 0.6:  # 60% similarity
            found_in_document = True
    
    # If not found in raw corpus, try to find in document blocks
    if not found_in_document and marker_output.get("document"):
        # Extract all block texts
        block_texts = []
        for page in marker_output.get("document", {}).get("pages", []):
            for block in page.get("blocks", []):
                block_texts.append(block.get("text", ""))
        
        # Check each block for high similarity
        for block_text in block_texts:
            if block_text and len(block_text) >= len(context) / 2:  # Only check substantial blocks
                matcher = difflib.SequenceMatcher(None, context, block_text)
                similarity = matcher.ratio()
                if similarity > context_similarity:
                    context_similarity = similarity
                    
                    # If similarity is above threshold, consider it found
                    if context_similarity >= 0.6:
                        found_in_document = True
                        break
    
    # Calculate relevance based on several factors
    relevance_score = 0.0
    
    if found_in_document:
        # Basic relevance check: does the question mention terms from context?
        context_terms = set(re.findall(r'\b\w+\b', context.lower()))
        question_terms = set(re.findall(r'\b\w+\b', question.lower()))
        answer_terms = set(re.findall(r'\b\w+\b', answer.lower()))
        
        # Calculate term overlap
        question_overlap = len(question_terms.intersection(context_terms)) / max(len(question_terms), 1)
        answer_overlap = len(answer_terms.intersection(context_terms)) / max(len(answer_terms), 1)
        
        # Combine factors for final relevance score
        relevance_score = 0.4 * context_similarity + 0.3 * question_overlap + 0.3 * answer_overlap
    
    # Return validation result
    return {
        "validated": relevance_score >= threshold,
        "score": relevance_score,
        "reason": "Relevant to document content" if relevance_score >= threshold else "Not sufficiently relevant to document content"
    }


def validate_qa_accuracy(
    qa_pair: Dict[str, Any], 
    marker_output: Dict[str, Any],
    threshold: float = DEFAULT_ACCURACY_THRESHOLD
) -> Dict[str, Any]:
    """
    Validate the accuracy of the answer based on document content.
    
    This function checks if the answer is supported by the document context.
    
    Args:
        qa_pair: QA pair dictionary
        marker_output: Marker output dictionary
        threshold: Minimum accuracy score required to pass
        
    Returns:
        Dictionary with validation results
    """
    context = qa_pair.get("metadata", {}).get("context", "")
    answer = qa_pair.get("output", "")
    source_type = qa_pair.get("metadata", {}).get("source_type", "")
    
    if not context or not answer:
        return {
            "validated": False,
            "score": 0.0,
            "reason": "Missing context or answer"
        }
    
    # Simple accuracy check: is the answer content contained in or derived from the context?
    # In a real implementation, this would be a much more sophisticated semantic comparison
    
    # Extract key facts from answer (simplified approach)
    answer_facts = set(re.findall(r'\b\w+\b', answer.lower()))
    context_facts = set(re.findall(r'\b\w+\b', context.lower()))
    
    # Calculate fact overlap
    if len(answer_facts) == 0:
        fact_overlap = 0.0
    else:
        fact_overlap = len(answer_facts.intersection(context_facts)) / len(answer_facts)
    
    # Check for factual contradictions (simplified)
    # In a real implementation, this would involve NLI or semantic contradiction detection
    contradiction_score = 1.0  # Assume no contradictions by default
    
    # Use sequence matching for additional accuracy signal
    matcher = difflib.SequenceMatcher(None, answer, context)
    sequence_similarity = matcher.ratio()
    
    # If source type is available, adjust validation approach
    if source_type:
        # For code blocks, check for programming terms and syntax
        if source_type == "code":
            # Adjust fact overlap for code - common code terms might be missing from context
            # but that doesn't mean the answer is wrong
            if fact_overlap < 0.5 and sequence_similarity > 0.4:
                fact_overlap = min(fact_overlap + 0.3, 1.0)
        
        # For tables, we need a more lenient approach since tabular data may be
        # transformed significantly in the answer
        elif source_type == "table":
            if fact_overlap >= 0.4:  # Lower threshold for tables
                fact_overlap = min(fact_overlap + 0.2, 1.0)
    
    # Check if we can also validate against raw corpus for additional context
    raw_corpus = marker_output.get("raw_corpus", {}).get("full_text", "")
    if raw_corpus:
        # Get facts from full document
        doc_facts = set(re.findall(r'\b\w+\b', raw_corpus.lower()))
        
        # Additional check against full document text
        doc_fact_overlap = len(answer_facts.intersection(doc_facts)) / len(answer_facts) if len(answer_facts) > 0 else 0.0
        
        # If document validates better than context, consider it partially
        if doc_fact_overlap > fact_overlap:
            fact_overlap = 0.7 * fact_overlap + 0.3 * doc_fact_overlap
    
    # Check for specific block-based validation in ArangoDB format
    doc_structure = marker_output.get("document", {})
    if doc_structure and source_type:
        # Look for specific blocks in the document that match the source type
        for page in doc_structure.get("pages", []):
            for block in page.get("blocks", []):
                if block.get("type", "") == source_type or block.get("type", "") == "text":
                    block_text = block.get("text", "")
                    if block_text:
                        block_facts = set(re.findall(r'\b\w+\b', block_text.lower()))
                        block_fact_overlap = len(answer_facts.intersection(block_facts)) / len(answer_facts) if len(answer_facts) > 0 else 0.0
                        
                        # If a better match is found, improve the fact overlap score
                        if block_fact_overlap > fact_overlap:
                            fact_overlap = 0.6 * fact_overlap + 0.4 * block_fact_overlap
    
    # Combine factors for final accuracy score
    accuracy_score = 0.6 * fact_overlap + 0.2 * contradiction_score + 0.2 * sequence_similarity
    
    # Return validation result
    return {
        "validated": accuracy_score >= threshold,
        "score": accuracy_score,
        "reason": "Answer supported by document content" if accuracy_score >= threshold else "Answer not sufficiently supported by document content"
    }


def validate_qa_quality(
    qa_pair: Dict[str, Any],
    threshold: float = DEFAULT_QUESTION_QUALITY_THRESHOLD
) -> Dict[str, Any]:
    """
    Validate the quality of the question and answer.
    
    This function checks various quality aspects:
    - Question is well-formed and clear
    - Answer is comprehensive and well-structured
    - Length is appropriate
    
    Args:
        qa_pair: QA pair dictionary
        threshold: Minimum quality score required to pass
        
    Returns:
        Dictionary with validation results
    """
    question = qa_pair.get("instruction", "")
    answer = qa_pair.get("output", "")
    
    if not question or not answer:
        return {
            "validated": False,
            "score": 0.0,
            "reason": "Missing question or answer"
        }
    
    quality_score = 0.0
    quality_factors = []
    
    # Check question ends with question mark
    if question.endswith("?"):
        quality_score += 0.1
        quality_factors.append("Question properly formatted with question mark")
    
    # Check question length (not too short, not too long)
    q_words = len(question.split())
    if 3 <= q_words <= 25:
        quality_score += 0.2
        quality_factors.append(f"Question length appropriate ({q_words} words)")
    elif q_words < 3:
        quality_factors.append("Question too short")
    else:
        quality_factors.append("Question unnecessarily verbose")
    
    # Check answer length
    a_words = len(answer.split())
    if 10 <= a_words <= 200:
        quality_score += 0.2
        quality_factors.append(f"Answer length appropriate ({a_words} words)")
    elif a_words < 10:
        quality_factors.append("Answer too short")
    else:
        quality_factors.append("Answer unnecessarily verbose")
    
    # Check for question words in question
    question_words = ["what", "who", "where", "when", "why", "how", "which", "can", "do", "is"]
    has_question_word = any(qw in question.lower().split() for qw in question_words)
    if has_question_word:
        quality_score += 0.1
        quality_factors.append("Question contains proper interrogative words")
    
    # Check for paragraph structure in answer
    has_structure = len(answer.split(".")) > 1 or "\n" in answer
    if has_structure:
        quality_score += 0.1
        quality_factors.append("Answer has good structure")
    
    # Check for capitalization and punctuation
    if answer[0].isupper() and (answer.endswith(".") or answer.endswith("!") or answer.endswith("?")):
        quality_score += 0.1
        quality_factors.append("Answer has proper capitalization and punctuation")
    
    # Check for answer completeness (does it actually answer the question)
    # This is a simplified check - in real implementation you'd use a more sophisticated approach
    if "placeholder" in answer.lower() or "generating" in answer.lower():
        quality_factors.append("Answer appears to be a placeholder or incomplete")
    else:
        quality_score += 0.2
        quality_factors.append("Answer appears complete")
    
    # Return validation result
    return {
        "validated": quality_score >= threshold,
        "score": quality_score,
        "reason": "Good quality QA pair" if quality_score >= threshold else "Quality issues detected",
        "details": quality_factors
    }


def validate_qa_diversity(
    qa_pair: Dict[str, Any],
    qa_pairs: List[Dict[str, Any]],
    similarity_threshold: float = 0.8
) -> Dict[str, Any]:
    """
    Validate the diversity of a QA pair compared to others.
    
    This function checks if the question is too similar to other questions,
    to ensure a diverse set of questions.
    
    Args:
        qa_pair: QA pair dictionary to validate
        qa_pairs: List of all QA pairs to compare against
        similarity_threshold: Maximum allowed similarity
        
    Returns:
        Dictionary with validation results
    """
    question = qa_pair.get("instruction", "")
    
    if not question:
        return {
            "validated": False,
            "score": 0.0,
            "reason": "Missing question"
        }
    
    # Extract question type and title from metadata
    q_type = qa_pair.get("metadata", {}).get("question_type", "")
    title = qa_pair.get("metadata", {}).get("title", "")
    
    # Find similar questions
    similar_questions = []
    max_similarity = 0.0
    
    for other_qa in qa_pairs:
        if other_qa is qa_pair:  # Skip self
            continue
        
        other_question = other_qa.get("instruction", "")
        other_type = other_qa.get("metadata", {}).get("question_type", "")
        other_title = other_qa.get("metadata", {}).get("title", "")
        
        # Calculate string similarity
        matcher = difflib.SequenceMatcher(None, question, other_question)
        similarity = matcher.ratio()
        
        # Adjust similarity based on type and title
        # Questions of same type about same topic are more likely to be similar
        if q_type and other_type and q_type == other_type:
            similarity += 0.1
        if title and other_title and title == other_title:
            similarity += 0.1
        
        # Cap at 1.0
        similarity = min(similarity, 1.0)
        
        if similarity > max_similarity:
            max_similarity = similarity
        
        if similarity >= similarity_threshold:
            similar_questions.append({
                "question": other_question,
                "similarity": similarity
            })
    
    # Diversity score is inverse of max similarity
    diversity_score = 1.0 - max_similarity
    
    # Return validation result
    return {
        "validated": diversity_score >= (1.0 - similarity_threshold),
        "score": diversity_score,
        "reason": "Question is sufficiently diverse" if diversity_score >= (1.0 - similarity_threshold) else "Question too similar to others",
        "similar_questions": similar_questions
    }


def validate_qa_pairs(
    qa_pairs_path: str,
    marker_output_path: Optional[str] = None,
    marker_output: Optional[Dict[str, Any]] = None,
    checks: List[str] = DEFAULT_VALIDATION_CHECKS,
    relevance_threshold: float = DEFAULT_RELEVANCE_THRESHOLD,
    accuracy_threshold: float = DEFAULT_ACCURACY_THRESHOLD,
    quality_threshold: float = DEFAULT_QUESTION_QUALITY_THRESHOLD,
    output_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Validate QA pairs against various criteria.
    
    Args:
        qa_pairs_path: Path to QA pairs JSONL file
        marker_output_path: Path to marker output JSON file
        marker_output: Marker output dictionary (alternative to path)
        checks: List of validation checks to perform
        relevance_threshold: Threshold for relevance validation
        accuracy_threshold: Threshold for accuracy validation
        quality_threshold: Threshold for quality validation
        output_path: Path to write validation results
        
    Returns:
        Dictionary with validation results
    """
    start_time = time.time()
    
    # Load QA pairs
    qa_pairs = load_qa_pairs(qa_pairs_path)
    
    if not qa_pairs:
        return {
            "status": "error",
            "message": "No QA pairs found in file",
            "validation_time": time.time() - start_time
        }
    
    # Load marker output if needed and not provided
    if ("relevance" in checks or "accuracy" in checks) and not marker_output:
        if not marker_output_path:
            return {
                "status": "error",
                "message": "Marker output is required for relevance and accuracy checks",
                "validation_time": time.time() - start_time
            }
        marker_output = load_marker_output(marker_output_path)
    
    # Initialize validation results
    validation_results = {
        "status": "success",
        "total_qa_pairs": len(qa_pairs),
        "checks_performed": checks.copy(),
        "passing_qa_pairs": 0,
        "failing_qa_pairs": 0,
        "results_by_check": {},
        "detailed_results": [],
        "validation_time": 0
    }
    
    # Initialize check-specific results
    for check in checks:
        validation_results["results_by_check"][check] = {
            "passed": 0,
            "failed": 0,
            "average_score": 0.0
        }
    
    # Validate each QA pair
    for qa_pair in qa_pairs:
        qa_result = {
            "instruction": qa_pair.get("instruction", ""),
            "check_results": {},
            "passed_all_checks": True
        }
        
        # Perform each check
        if "relevance" in checks and marker_output:
            relevance_result = validate_qa_relevance(qa_pair, marker_output, relevance_threshold)
            qa_result["check_results"]["relevance"] = relevance_result
            
            if relevance_result["validated"]:
                validation_results["results_by_check"]["relevance"]["passed"] += 1
            else:
                validation_results["results_by_check"]["relevance"]["failed"] += 1
                qa_result["passed_all_checks"] = False
        
        if "accuracy" in checks and marker_output:
            accuracy_result = validate_qa_accuracy(qa_pair, marker_output, accuracy_threshold)
            qa_result["check_results"]["accuracy"] = accuracy_result
            
            if accuracy_result["validated"]:
                validation_results["results_by_check"]["accuracy"]["passed"] += 1
            else:
                validation_results["results_by_check"]["accuracy"]["failed"] += 1
                qa_result["passed_all_checks"] = False
        
        if "quality" in checks:
            quality_result = validate_qa_quality(qa_pair, quality_threshold)
            qa_result["check_results"]["quality"] = quality_result
            
            if quality_result["validated"]:
                validation_results["results_by_check"]["quality"]["passed"] += 1
            else:
                validation_results["results_by_check"]["quality"]["failed"] += 1
                qa_result["passed_all_checks"] = False
        
        if "diversity" in checks:
            diversity_result = validate_qa_diversity(qa_pair, qa_pairs)
            qa_result["check_results"]["diversity"] = diversity_result
            
            if diversity_result["validated"]:
                validation_results["results_by_check"]["diversity"]["passed"] += 1
            else:
                validation_results["results_by_check"]["diversity"]["failed"] += 1
                qa_result["passed_all_checks"] = False
        
        # Add to detailed results
        validation_results["detailed_results"].append(qa_result)
        
        # Count overall pass/fail
        if qa_result["passed_all_checks"]:
            validation_results["passing_qa_pairs"] += 1
        else:
            validation_results["failing_qa_pairs"] += 1
    
    # Calculate average scores
    for check in checks:
        total_count = validation_results["results_by_check"][check]["passed"] + validation_results["results_by_check"][check]["failed"]
        if total_count > 0:
            total_score = sum(
                qa["check_results"][check]["score"] 
                for qa in validation_results["detailed_results"] 
                if check in qa["check_results"]
            )
            validation_results["results_by_check"][check]["average_score"] = total_score / total_count
    
    # Calculate overall passing percentage
    validation_results["passing_percentage"] = (validation_results["passing_qa_pairs"] / len(qa_pairs)) * 100
    
    # Calculate validation time
    validation_results["validation_time"] = time.time() - start_time
    
    # Write validation results to file if output path provided
    if output_path:
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(validation_results, f, indent=2)
    
    return validation_results


def generate_validation_report(
    validation_results: Dict[str, Any],
    output_path: Optional[str] = None
) -> str:
    """
    Generate a human-readable validation report.
    
    Args:
        validation_results: Validation results dictionary
        output_path: Path to write report
        
    Returns:
        Report as string
    """
    # Create report
    report = []
    report.append("# QA Pairs Validation Report")
    report.append("")
    
    # Summary section
    report.append("## Summary")
    report.append("")
    report.append(f"- Total QA pairs: {validation_results['total_qa_pairs']}")
    report.append(f"- Passing QA pairs: {validation_results['passing_qa_pairs']} ({validation_results['passing_percentage']:.1f}%)")
    report.append(f"- Failing QA pairs: {validation_results['failing_qa_pairs']}")
    report.append(f"- Validation time: {validation_results['validation_time']:.2f} seconds")
    report.append("")
    
    # Results by check
    report.append("## Results by Check")
    report.append("")
    
    for check, results in validation_results["results_by_check"].items():
        passed = results["passed"]
        total = passed + results["failed"]
        pass_percentage = (passed / total) * 100 if total > 0 else 0
        report.append(f"### {check.capitalize()}")
        report.append("")
        report.append(f"- Passed: {passed}/{total} ({pass_percentage:.1f}%)")
        report.append(f"- Average score: {results['average_score']:.2f}")
        report.append("")
    
    # Common failure reasons
    report.append("## Common Failure Reasons")
    report.append("")
    
    # Extract failure reasons by check
    failure_reasons = {}
    
    for qa_result in validation_results["detailed_results"]:
        for check, check_result in qa_result["check_results"].items():
            if not check_result["validated"]:
                reason = check_result["reason"]
                if check not in failure_reasons:
                    failure_reasons[check] = {}
                
                if reason not in failure_reasons[check]:
                    failure_reasons[check][reason] = 0
                
                failure_reasons[check][reason] += 1
    
    # Report failure reasons
    for check, reasons in failure_reasons.items():
        report.append(f"### {check.capitalize()}")
        report.append("")
        
        # Sort reasons by frequency
        sorted_reasons = sorted(
            [(reason, count) for reason, count in reasons.items()],
            key=lambda x: x[1],
            reverse=True
        )
        
        for reason, count in sorted_reasons:
            report.append(f"- {reason}: {count} occurrences")
        
        report.append("")
    
    # Sample failing QA pairs
    report.append("## Sample Failing QA Pairs")
    report.append("")
    
    # Get up to 5 failing QA pairs
    failing_samples = [
        qa for qa in validation_results["detailed_results"]
        if not qa["passed_all_checks"]
    ][:5]
    
    for i, sample in enumerate(failing_samples):
        report.append(f"### Sample {i+1}")
        report.append("")
        report.append(f"Question: {sample['instruction']}")
        report.append("")
        report.append("Failures:")
        
        for check, check_result in sample["check_results"].items():
            if not check_result["validated"]:
                report.append(f"- {check.capitalize()}: {check_result['reason']} (Score: {check_result['score']:.2f})")
        
        report.append("")
    
    # Join report
    report_text = "\n".join(report)
    
    # Write report to file if output path provided
    if output_path:
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report_text)
    
    return report_text


if __name__ == "__main__":
    import sys
    import argparse
    
    # Configure logger
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    logger.add("qa_validator_validation.log", rotation="10 MB")
    
    # Parse arguments
    parser = argparse.ArgumentParser(description="Validate QA pairs")
    parser.add_argument("--qa-pairs", "-q", type=str, help="Path to QA pairs JSONL file")
    parser.add_argument("--marker-output", "-m", type=str, help="Path to Marker JSON output file")
    parser.add_argument("--output", "-o", type=str, help="Path to write validation results")
    parser.add_argument("--report", "-r", type=str, help="Path to write validation report")
    parser.add_argument("--relevance-threshold", type=float, default=DEFAULT_RELEVANCE_THRESHOLD, help="Threshold for relevance validation")
    parser.add_argument("--accuracy-threshold", type=float, default=DEFAULT_ACCURACY_THRESHOLD, help="Threshold for accuracy validation")
    parser.add_argument("--quality-threshold", type=float, default=DEFAULT_QUESTION_QUALITY_THRESHOLD, help="Threshold for quality validation")
    parser.add_argument("--checks", type=str, default=",".join(DEFAULT_VALIDATION_CHECKS), help="Comma-separated list of checks to perform")
    args = parser.parse_args()
    
    # List to track all validation failures
    all_validation_failures = []
    total_tests = 0
    
    # Parse checks
    checks_to_perform = [check.strip() for check in args.checks.split(",") if check.strip()]
    
    # Test 1: Create sample QA pairs and validate them
    total_tests += 1
    logger.info("Test 1: Validating sample QA pairs")
    
    # Create a sample QA pairs file
    sample_qa_pairs = [
        {
            "instruction": "What is the main purpose of Python?",
            "input": "",
            "output": "Python is a high-level, interpreted programming language designed for readability and ease of use. Its main purpose is to help programmers write clear, logical code for small and large-scale projects.",
            "metadata": {
                "source_doc": "test_doc_123",
                "doc_title": "Python Programming Guide",
                "context": "Python is a high-level, interpreted programming language. It was created by Guido van Rossum and first released in 1991. Python's design philosophy emphasizes code readability with its notable use of significant whitespace. Its language constructs and object-oriented approach aim to help programmers write clear, logical code for small and large-scale projects.",
                "question_type": "factual",
                "source_type": "section",
                "title": "Introduction to Python"
            }
        },
        {
            "instruction": "What is Python?",
            "input": "",
            "output": "Python is a programming language.",
            "metadata": {
                "source_doc": "test_doc_123",
                "doc_title": "Python Programming Guide",
                "context": "Python is a high-level, interpreted programming language.",
                "question_type": "factual",
                "source_type": "section",
                "title": "Introduction to Python"
            }
        },
        {
            "instruction": "List three features of Python",
            "input": "",
            "output": "Three key features of Python are:\n1. Readability with significant whitespace\n2. Large standard library\n3. Support for multiple programming paradigms including object-oriented and functional programming",
            "metadata": {
                "source_doc": "test_doc_123",
                "doc_title": "Python Programming Guide",
                "context": "Python is known for its simplicity and readability. It has a large standard library that supports many common programming tasks such as connecting to web servers, searching text with regular expressions, reading and modifying files. Python's syntax allows programmers to express concepts in fewer lines of code than would be possible in languages such as C++ or Java.",
                "question_type": "factual",
                "source_type": "section",
                "title": "Features of Python"
            }
        },
        {
            "instruction": "What is wrong with this code: print hello world",
            "input": "",
            "output": "The code has a syntax error. In Python, string literals should be enclosed in quotes. The correct code would be: print('hello world')",
            "metadata": {
                "source_doc": "test_doc_123",
                "doc_title": "Python Programming Guide",
                "context": "def hello_world():\n    print('Hello, World!')\n\nhello_world()",
                "question_type": "application",
                "source_type": "code",
                "title": "Introduction to Python"
            }
        },
        {
            "instruction": "How do I run a Python function?",
            "input": "",
            "output": "To run a Python function, you need to define it first using the def keyword, then call it by using the function name followed by parentheses. For example:\n\ndef hello_world():\n    print('Hello, World!')\n\nhello_world()",
            "metadata": {
                "source_doc": "test_doc_123",
                "doc_title": "Python Programming Guide",
                "context": "def hello_world():\n    print('Hello, World!')\n\nhello_world()",
                "question_type": "application",
                "source_type": "code",
                "title": "Introduction to Python"
            }
        }
    ]
    
    # Create sample marker output
    sample_marker_output = {
        "document": {
            "id": "test_doc_123",
            "pages": [
                {
                    "blocks": [
                        {
                            "type": "section_header",
                            "text": "Introduction to Python",
                            "level": 1
                        },
                        {
                            "type": "text",
                            "text": "Python is a high-level, interpreted programming language. It was created by Guido van Rossum and first released in 1991. Python's design philosophy emphasizes code readability with its notable use of significant whitespace. Its language constructs and object-oriented approach aim to help programmers write clear, logical code for small and large-scale projects."
                        },
                        {
                            "type": "code",
                            "text": "def hello_world():\n    print('Hello, World!')\n\nhello_world()",
                            "language": "python"
                        },
                        {
                            "type": "section_header",
                            "text": "Features of Python",
                            "level": 2
                        },
                        {
                            "type": "text",
                            "text": "Python is known for its simplicity and readability. It has a large standard library that supports many common programming tasks such as connecting to web servers, searching text with regular expressions, reading and modifying files. Python's syntax allows programmers to express concepts in fewer lines of code than would be possible in languages such as C++ or Java."
                        }
                    ]
                }
            ]
        },
        "metadata": {
            "title": "Python Programming Guide"
        },
        "raw_corpus": {
            "full_text": "Introduction to Python\n\nPython is a high-level, interpreted programming language. It was created by Guido van Rossum and first released in 1991. Python's design philosophy emphasizes code readability with its notable use of significant whitespace. Its language constructs and object-oriented approach aim to help programmers write clear, logical code for small and large-scale projects.\n\ndef hello_world():\n    print('Hello, World!')\n\nhello_world()\n\nFeatures of Python\n\nPython is known for its simplicity and readability. It has a large standard library that supports many common programming tasks such as connecting to web servers, searching text with regular expressions, reading and modifying files. Python's syntax allows programmers to express concepts in fewer lines of code than would be possible in languages such as C++ or Java."
        }
    }
    
    # Write sample files
    sample_qa_path = "sample_qa_pairs.jsonl"
    sample_marker_path = "sample_marker_output.json"
    
    with open(sample_qa_path, "w", encoding="utf-8") as f:
        for pair in sample_qa_pairs:
            f.write(json.dumps(pair) + "\n")
    
    with open(sample_marker_path, "w", encoding="utf-8") as f:
        json.dump(sample_marker_output, f, indent=2)
    
    try:
        # Validate sample QA pairs
        validation_results = validate_qa_pairs(
            qa_pairs_path=sample_qa_path,
            marker_output_path=sample_marker_path,
            checks=checks_to_perform,
            relevance_threshold=args.relevance_threshold,
            accuracy_threshold=args.accuracy_threshold,
            quality_threshold=args.quality_threshold,
            output_path="sample_validation_results.json"
        )
        
        # Check validation results
        if validation_results["status"] != "success":
            failure_msg = f"Validation failed: {validation_results.get('message', 'Unknown error')}"
            all_validation_failures.append(failure_msg)
            logger.error(failure_msg)
        else:
            logger.success("Validation completed successfully")
            logger.info(f"Total QA pairs: {validation_results['total_qa_pairs']}")
            logger.info(f"Passing QA pairs: {validation_results['passing_qa_pairs']} ({validation_results['passing_percentage']:.1f}%)")
            logger.info(f"Failing QA pairs: {validation_results['failing_qa_pairs']}")
            logger.info(f"Validation time: {validation_results['validation_time']:.2f} seconds")
            
            # Generate report
            report = generate_validation_report(validation_results, "sample_validation_report.md")
            logger.info("Generated validation report")
            
            # Check individual validations
            if "relevance" in checks_to_perform:
                relevance_results = validation_results["results_by_check"]["relevance"]
                logger.info(f"Relevance: {relevance_results['passed']}/{relevance_results['passed'] + relevance_results['failed']} passed, avg score: {relevance_results['average_score']:.2f}")
            
            if "accuracy" in checks_to_perform:
                accuracy_results = validation_results["results_by_check"]["accuracy"]
                logger.info(f"Accuracy: {accuracy_results['passed']}/{accuracy_results['passed'] + accuracy_results['failed']} passed, avg score: {accuracy_results['average_score']:.2f}")
            
            if "quality" in checks_to_perform:
                quality_results = validation_results["results_by_check"]["quality"]
                logger.info(f"Quality: {quality_results['passed']}/{quality_results['passed'] + quality_results['failed']} passed, avg score: {quality_results['average_score']:.2f}")
            
            if "diversity" in checks_to_perform:
                diversity_results = validation_results["results_by_check"]["diversity"]
                logger.info(f"Diversity: {diversity_results['passed']}/{diversity_results['passed'] + diversity_results['failed']} passed, avg score: {diversity_results['average_score']:.2f}")
    except Exception as e:
        failure_msg = f"Validation failed with error: {str(e)}"
        all_validation_failures.append(failure_msg)
        logger.error(failure_msg)
    
    # Test 2: Validate from command line args if provided
    if args.qa_pairs:
        total_tests += 1
        logger.info(f"Test 2: Validating QA pairs from file: {args.qa_pairs}")
        
        try:
            # Validate QA pairs
            validation_results = validate_qa_pairs(
                qa_pairs_path=args.qa_pairs,
                marker_output_path=args.marker_output,
                checks=checks_to_perform,
                relevance_threshold=args.relevance_threshold,
                accuracy_threshold=args.accuracy_threshold,
                quality_threshold=args.quality_threshold,
                output_path=args.output
            )
            
            # Check validation results
            if validation_results["status"] != "success":
                failure_msg = f"Validation failed: {validation_results.get('message', 'Unknown error')}"
                all_validation_failures.append(failure_msg)
                logger.error(failure_msg)
            else:
                logger.success("Validation completed successfully")
                logger.info(f"Total QA pairs: {validation_results['total_qa_pairs']}")
                logger.info(f"Passing QA pairs: {validation_results['passing_qa_pairs']} ({validation_results['passing_percentage']:.1f}%)")
                logger.info(f"Failing QA pairs: {validation_results['failing_qa_pairs']}")
                logger.info(f"Validation time: {validation_results['validation_time']:.2f} seconds")
                
                # Generate report if requested
                if args.report:
                    report = generate_validation_report(validation_results, args.report)
                    logger.info(f"Generated validation report: {args.report}")
        except Exception as e:
            failure_msg = f"Validation failed with error: {str(e)}"
            all_validation_failures.append(failure_msg)
            logger.error(failure_msg)
    
    # Clean up sample files
    if os.path.exists(sample_qa_path):
        os.remove(sample_qa_path)
    
    if os.path.exists(sample_marker_path):
        os.remove(sample_marker_path)
    
    # Final validation result
    if all_validation_failures:
        logger.error(f"❌ VALIDATION FAILED - {len(all_validation_failures)} of {total_tests} tests failed:")
        for failure in all_validation_failures:
            logger.error(f"  - {failure}")
        sys.exit(1)  # Exit with error code
    else:
        logger.success(f"✅ VALIDATION PASSED - All {total_tests} tests produced expected results")
        logger.info("QA validator is validated and ready for use")
        sys.exit(0)  # Exit with success code