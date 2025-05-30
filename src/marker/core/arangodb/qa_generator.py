"""
QA Generation module for ArangoDB-Marker integration.

This module provides functions to generate QA pairs from Marker document outputs
stored in ArangoDB, including generating questions from document content and
exporting to Unsloth-compatible format.

Example:
    ```python
    from marker.core.arangodb.qa_generator import generate_qa_pairs
    
    # Generate QA pairs from marker output
    qa_pairs, stats = generate_qa_pairs(
        marker_output_path='document.json',
        output_dir='qa_output',
        max_questions=20,
        question_types=["factual", "reasoning"]
    )
    ```

Documentation:
    - ArangoDB Python Driver: https://github.com/ArangoDB-Community/python-arango
    - ArangoDB Graph Features: https://www.arangodb.com/docs/stable/graphs.html
    - Marker Document Structure: https://github.com/VikParuchuri/marker
    - Unsloth Format: https://github.com/unslothai/unsloth
"""

import json
import os
import time
import datetime
import uuid
import re
import random
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union, Set

from loguru import logger
from arango import ArangoClient

from marker.core.utils.relationship_extractor import extract_relationships_from_marker
from marker.core.arangodb.importers import (
    create_arangodb_client, document_to_arangodb,
    DOCUMENT_COLLECTION, SECTION_COLLECTION, CONTENT_COLLECTION
)


# Constants
DEFAULT_MAX_QUESTIONS = 20
DEFAULT_QUESTION_TYPES = ["factual", "conceptual", "application"]
DEFAULT_QUESTION_DISTRIBUTION = {
    "factual": 0.6,         # Basic factual questions
    "conceptual": 0.3,      # Questions requiring understanding of concepts
    "application": 0.1      # Questions requiring application of knowledge
}
DEFAULT_MIN_LENGTH_THRESHOLD = 100  # Minimum text length for generating questions
DEFAULT_EXPORT_FORMATS = ["unsloth"]


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


def extract_question_contexts(
    marker_output: Dict[str, Any],
    min_length: int = DEFAULT_MIN_LENGTH_THRESHOLD
) -> List[Dict[str, Any]]:
    """
    Extract contexts from marker output for question generation.
    
    Args:
        marker_output: Marker output dictionary
        min_length: Minimum text length to consider for questions
        
    Returns:
        List of context dictionaries
    """
    contexts = []
    document = marker_output.get("document", {})
    doc_id = document.get("id", "unknown")
    
    # Track section contexts
    current_section = None
    section_context = {}
    
    # Process each page
    for page_idx, page in enumerate(document.get("pages", [])):
        # Process blocks on this page
        for block_idx, block in enumerate(page.get("blocks", [])):
            block_type = block.get("type", "")
            block_text = block.get("text", "")
            
            # Skip empty blocks
            if not block_text or len(block_text) < 10:
                continue
            
            # Handle section headers
            if block_type == "section_header":
                # Start new section context
                current_section = {
                    "title": block_text,
                    "level": block.get("level", 1),
                    "content": ""
                }
                section_context = current_section
            
            # For text blocks, add to current section context
            elif block_type == "text" and current_section:
                if block_text:
                    # Add to section content
                    if current_section["content"]:
                        current_section["content"] += "\n\n" + block_text
                    else:
                        current_section["content"] = block_text
                    
                    # If section content is long enough, add as context
                    if len(current_section["content"]) >= min_length and "added" not in current_section:
                        contexts.append({
                            "doc_id": doc_id,
                            "type": "section",
                            "title": current_section["title"],
                            "content": current_section["content"],
                            "level": current_section["level"]
                        })
                        current_section["added"] = True
            
            # For code blocks, create separate context
            elif block_type == "code" and len(block_text) >= min_length:
                contexts.append({
                    "doc_id": doc_id,
                    "type": "code",
                    "language": block.get("language", ""),
                    "content": block_text
                })
            
            # For table blocks, create separate context if content available
            elif block_type == "table" and block_text and len(block_text) >= min_length:
                contexts.append({
                    "doc_id": doc_id,
                    "type": "table",
                    "content": block_text,
                    "title": current_section["title"] if current_section else ""
                })
            
            # For equation blocks with sufficient content
            elif block_type == "equation" and block_text and len(block_text) >= min_length:
                contexts.append({
                    "doc_id": doc_id,
                    "type": "equation",
                    "content": block_text,
                    "title": current_section["title"] if current_section else ""
                })
    
    # Check if there's a document summary in metadata
    metadata = marker_output.get("metadata", {})
    if "document_summary" in metadata and len(metadata["document_summary"]) >= min_length:
        contexts.append({
            "doc_id": doc_id,
            "type": "summary",
            "title": metadata.get("title", "Document Summary"),
            "content": metadata["document_summary"]
        })
    elif "summary" in metadata and len(metadata["summary"]) >= min_length:
        contexts.append({
            "doc_id": doc_id,
            "type": "summary",
            "title": metadata.get("title", "Document Summary"),
            "content": metadata["summary"]
        })
    
    return contexts


def generate_question_from_context(
    context: Dict[str, Any], 
    question_type: str = "factual"
) -> Dict[str, Any]:
    """
    Generate a question from a context.
    
    Note: This is a placeholder for actual LLM-based question generation.
    In a real implementation, this would call an LLM to generate questions.
    
    Args:
        context: Context dictionary
        question_type: Type of question to generate
        
    Returns:
        Question dictionary
    """
    # This would be replaced with actual LLM call in production
    context_type = context.get("type", "text")
    content = context.get("content", "")
    title = context.get("title", "")
    
    # Create a placeholder question and answer
    # In real implementation, this would be generated by an LLM
    if question_type == "factual":
        question = f"What is described in the section '{title}'?"
        answer = f"The section describes {content[:100]}..."
    elif question_type == "conceptual":
        question = f"Explain the concept of {title}."
        answer = f"The concept involves {content[:100]}..."
    elif question_type == "application":
        question = f"How would you apply the information about {title}?"
        answer = f"You could apply this by understanding {content[:100]}..."
    else:
        question = f"What is {title} about?"
        answer = f"It's about {content[:100]}..."
    
    return {
        "question": question,
        "answer": answer,
        "context": content,
        "type": question_type,
        "source_type": context_type,
        "title": title
    }


def format_qa_pairs_for_unsloth(
    qa_pairs: List[Dict[str, Any]],
    doc_id: str,
    doc_title: str
) -> List[Dict[str, Any]]:
    """
    Format QA pairs for Unsloth fine-tuning.
    
    Args:
        qa_pairs: List of QA pair dictionaries
        doc_id: Document ID
        doc_title: Document title
        
    Returns:
        List of formatted QA pairs for Unsloth
    """
    formatted_pairs = []
    
    for pair in qa_pairs:
        # Format according to Unsloth requirements
        formatted_pair = {
            "instruction": pair["question"],
            "input": "",  # No input for basic QA
            "output": pair["answer"],
            "metadata": {
                "source_doc": doc_id,
                "doc_title": doc_title,
                "context": pair["context"],
                "question_type": pair["type"],
                "source_type": pair["source_type"],
                "title": pair["title"]
            }
        }
        
        formatted_pairs.append(formatted_pair)
    
    return formatted_pairs


def export_qa_pairs(
    qa_pairs: List[Dict[str, Any]],
    output_dir: str,
    doc_id: str,
    doc_title: str,
    formats: List[str] = DEFAULT_EXPORT_FORMATS
) -> Dict[str, str]:
    """
    Export QA pairs to various formats.
    
    Args:
        qa_pairs: List of QA pair dictionaries
        output_dir: Output directory
        doc_id: Document ID
        doc_title: Document title
        formats: List of export formats
        
    Returns:
        Dictionary mapping format to output file path
    """
    output_files = {}
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate timestamp for output files
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Export to each format
    for fmt in formats:
        if fmt.lower() == "unsloth":
            # Format for Unsloth
            unsloth_pairs = format_qa_pairs_for_unsloth(qa_pairs, doc_id, doc_title)
            
            # Write to JSONL file
            output_file = os.path.join(output_dir, f"qa_unsloth_{timestamp}.jsonl")
            with open(output_file, "w", encoding="utf-8") as f:
                for pair in unsloth_pairs:
                    f.write(json.dumps(pair) + "\n")
            
            # Write stats file
            stats_file = os.path.join(output_dir, f"qa_unsloth_{timestamp}.stats.json")
            stats = {
                "document_id": doc_id,
                "document_title": doc_title,
                "total_qa_pairs": len(qa_pairs),
                "question_type_counts": {},
                "source_type_counts": {},
                "generated_at": timestamp
            }
            
            # Count question types
            for pair in qa_pairs:
                q_type = pair["type"]
                s_type = pair["source_type"]
                
                if q_type not in stats["question_type_counts"]:
                    stats["question_type_counts"][q_type] = 0
                stats["question_type_counts"][q_type] += 1
                
                if s_type not in stats["source_type_counts"]:
                    stats["source_type_counts"][s_type] = 0
                stats["source_type_counts"][s_type] += 1
            
            with open(stats_file, "w", encoding="utf-8") as f:
                json.dump(stats, f, indent=2)
                
            output_files[fmt] = output_file
    
    return output_files


def generate_qa_pairs(
    marker_output_path: Optional[str] = None,
    marker_output: Optional[Dict[str, Any]] = None,
    output_dir: str = "qa_output",
    max_questions: int = DEFAULT_MAX_QUESTIONS,
    question_types: List[str] = None,
    question_distribution: Dict[str, float] = None,
    min_length: int = DEFAULT_MIN_LENGTH_THRESHOLD,
    export_formats: List[str] = DEFAULT_EXPORT_FORMATS,
    random_seed: Optional[int] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Generate QA pairs from marker output.
    
    Args:
        marker_output_path: Path to marker output JSON file
        marker_output: Marker output dictionary (alternative to path)
        output_dir: Output directory for QA pairs
        max_questions: Maximum number of questions to generate
        question_types: List of question types to generate
        question_distribution: Distribution of question types
        min_length: Minimum text length for contexts
        export_formats: List of export formats
        random_seed: Random seed for reproducibility
        
    Returns:
        Tuple of (QA pairs list, stats dictionary)
    """
    start_time = time.time()
    
    # Set random seed if provided
    if random_seed is not None:
        random.seed(random_seed)
    
    # Set default question types and distribution if not provided
    if question_types is None:
        question_types = DEFAULT_QUESTION_TYPES
    
    if question_distribution is None:
        question_distribution = DEFAULT_QUESTION_DISTRIBUTION
    
    # Normalize distribution if needed
    total_distribution = sum(question_distribution.get(qt, 0) for qt in question_types)
    if total_distribution <= 0:
        # Use equal distribution if invalid
        question_distribution = {qt: 1.0 / len(question_types) for qt in question_types}
    elif total_distribution != 1.0:
        # Normalize to sum to 1
        question_distribution = {
            qt: question_distribution.get(qt, 0) / total_distribution 
            for qt in question_types
        }
    
    # Load marker output if path provided
    if marker_output_path and not marker_output:
        marker_output = load_marker_output(marker_output_path)
    
    if not marker_output:
        raise ValueError("Either marker_output_path or marker_output must be provided")
    
    # Extract document info
    document = marker_output.get("document", {})
    doc_id = document.get("id", f"doc_{uuid.uuid4().hex[:8]}")
    metadata = marker_output.get("metadata", {})
    doc_title = metadata.get("title", "Untitled Document")
    
    # Extract contexts for question generation
    contexts = extract_question_contexts(marker_output, min_length)
    
    # Calculate number of questions to generate per type
    type_counts = {}
    for qt in question_types:
        type_counts[qt] = int(max_questions * question_distribution.get(qt, 0))
    
    # Ensure we generate the requested number by assigning remainder
    total_assigned = sum(type_counts.values())
    if total_assigned < max_questions:
        # Assign remainder to first type
        first_type = question_types[0] if question_types else "factual"
        type_counts[first_type] = type_counts.get(first_type, 0) + (max_questions - total_assigned)
    
    # Generate questions
    qa_pairs = []
    
    # Track used contexts to avoid duplication
    used_contexts = set()
    
    # Generate questions by type
    for q_type, count in type_counts.items():
        # Skip if no questions of this type
        if count <= 0:
            continue
        
        # Find suitable contexts for this question type
        suitable_contexts = []
        
        for context in contexts:
            context_key = f"{context['type']}:{context.get('title', '')}:{hash(context['content'])}"
            
            # Skip if context already used
            if context_key in used_contexts:
                continue
            
            # Add suitable contexts based on type
            if q_type == "factual":
                # All contexts are good for factual questions
                suitable_contexts.append((context, context_key))
            elif q_type == "conceptual" and context["type"] in ["section", "summary"]:
                # Conceptual questions work best with section or summary contexts
                suitable_contexts.append((context, context_key))
            elif q_type == "application" and context["type"] in ["code", "section"]:
                # Application questions work well with code or substantial sections
                suitable_contexts.append((context, context_key))
        
        # Shuffle contexts to get variety
        random.shuffle(suitable_contexts)
        
        # Generate questions
        for i in range(min(count, len(suitable_contexts))):
            context, context_key = suitable_contexts[i]
            
            # Generate question
            qa_pair = generate_question_from_context(context, q_type)
            qa_pairs.append(qa_pair)
            
            # Mark context as used
            used_contexts.add(context_key)
    
    # Export QA pairs
    output_files = export_qa_pairs(qa_pairs, output_dir, doc_id, doc_title, export_formats)
    
    # Generate stats
    stats = {
        "document_id": doc_id,
        "document_title": doc_title,
        "contexts_extracted": len(contexts),
        "contexts_used": len(used_contexts),
        "qa_pairs_generated": len(qa_pairs),
        "question_type_counts": {qt: sum(1 for qa in qa_pairs if qa["type"] == qt) for qt in question_types},
        "source_type_counts": {},
        "output_files": output_files,
        "generation_time": time.time() - start_time
    }
    
    # Count source types
    for qa in qa_pairs:
        s_type = qa["source_type"]
        if s_type not in stats["source_type_counts"]:
            stats["source_type_counts"][s_type] = 0
        stats["source_type_counts"][s_type] += 1
    
    return qa_pairs, stats


if __name__ == "__main__":
    import sys
    import argparse
    from pathlib import Path
    
    # Configure logger
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    logger.add("qa_generator_validation.log", rotation="10 MB")
    
    # Parse arguments
    parser = argparse.ArgumentParser(description="Generate QA pairs from Marker output")
    parser.add_argument("--input", "-i", type=str, help="Path to Marker JSON output file")
    parser.add_argument("--output-dir", "-o", type=str, default="qa_output", help="Output directory")
    parser.add_argument("--max-questions", "-m", type=int, default=DEFAULT_MAX_QUESTIONS, help="Maximum number of questions")
    parser.add_argument("--question-types", "-t", type=str, default=",".join(DEFAULT_QUESTION_TYPES), help="Comma-separated question types")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    parser.add_argument("--min-length", type=int, default=DEFAULT_MIN_LENGTH_THRESHOLD, help="Minimum text length for contexts")
    args = parser.parse_args()
    
    # List to track all validation failures
    all_validation_failures = []
    total_tests = 0
    
    # Extract question types
    question_types = [qt.strip() for qt in args.question_types.split(",") if qt.strip()]
    
    # Test 1: Basic functionality test with sample document
    total_tests += 1
    logger.info("Test 1: Basic functionality test with sample document")
    
    # Create a sample document
    sample_doc = {
        "document": {
            "id": f"test_doc_{uuid.uuid4().hex[:8]}",
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
            "title": "Python Programming Guide",
            "document_summary": "This guide provides an introduction to Python programming language, covering its basic features, syntax, and applications in various domains. Python is valued for its simplicity, readability, and versatility across different programming tasks."
        },
        "validation": {
            "corpus_validation": {
                "performed": True,
                "threshold": 97,
                "raw_corpus_length": 200
            }
        },
        "raw_corpus": {
            "full_text": "Introduction to Python\n\nPython is a high-level, interpreted programming language. It was created by Guido van Rossum and first released in 1991. Python's design philosophy emphasizes code readability with its notable use of significant whitespace. Its language constructs and object-oriented approach aim to help programmers write clear, logical code for small and large-scale projects.\n\ndef hello_world():\n    print('Hello, World!')\n\nhello_world()\n\nFeatures of Python\n\nPython is known for its simplicity and readability. It has a large standard library that supports many common programming tasks such as connecting to web servers, searching text with regular expressions, reading and modifying files. Python's syntax allows programmers to express concepts in fewer lines of code than would be possible in languages such as C++ or Java.",
            "pages": [
                {
                    "page_num": 0,
                    "text": "Introduction to Python\n\nPython is a high-level, interpreted programming language. It was created by Guido van Rossum and first released in 1991. Python's design philosophy emphasizes code readability with its notable use of significant whitespace. Its language constructs and object-oriented approach aim to help programmers write clear, logical code for small and large-scale projects.\n\ndef hello_world():\n    print('Hello, World!')\n\nhello_world()\n\nFeatures of Python\n\nPython is known for its simplicity and readability. It has a large standard library that supports many common programming tasks such as connecting to web servers, searching text with regular expressions, reading and modifying files. Python's syntax allows programmers to express concepts in fewer lines of code than would be possible in languages such as C++ or Java.",
                    "tables": []
                }
            ],
            "total_pages": 1
        }
    }
    
    # Save sample document to file
    sample_path = "sample_doc.json"
    with open(sample_path, "w", encoding="utf-8") as f:
        json.dump(sample_doc, f, indent=2)
    
    try:
        # Generate QA pairs
        qa_pairs, stats = generate_qa_pairs(
            marker_output_path=sample_path,
            output_dir=args.output_dir,
            max_questions=10,
            question_types=question_types,
            random_seed=args.seed,
            min_length=args.min_length
        )
        
        # Check if QA pairs were generated
        if not qa_pairs:
            failure_msg = "No QA pairs generated"
            all_validation_failures.append(failure_msg)
            logger.error(failure_msg)
        elif len(qa_pairs) != 10:
            failure_msg = f"Expected 10 QA pairs, got {len(qa_pairs)}"
            all_validation_failures.append(failure_msg)
            logger.error(failure_msg)
        else:
            logger.success(f"Generated {len(qa_pairs)} QA pairs")
            
            # Log sample QA pairs
            logger.info("Sample QA pairs:")
            for i, qa in enumerate(qa_pairs[:3]):
                logger.info(f"Question {i+1}: {qa['question']}")
                logger.info(f"Answer: {qa['answer'][:100]}...")
                logger.info(f"Type: {qa['type']}")
                logger.info(f"Source: {qa['source_type']}")
                logger.info("")
            
            # Check output files
            output_files = stats["output_files"]
            if not output_files:
                failure_msg = "No output files generated"
                all_validation_failures.append(failure_msg)
                logger.error(failure_msg)
            else:
                for fmt, path in output_files.items():
                    if not os.path.exists(path):
                        failure_msg = f"Output file {path} does not exist"
                        all_validation_failures.append(failure_msg)
                        logger.error(failure_msg)
                    else:
                        logger.success(f"Output file created: {path}")
                
                # Check stats file
                stats_file = next((path.replace(".jsonl", ".stats.json") for path in output_files.values()), None)
                if stats_file and os.path.exists(stats_file):
                    logger.success(f"Stats file created: {stats_file}")
                else:
                    failure_msg = "Stats file not created"
                    all_validation_failures.append(failure_msg)
                    logger.error(failure_msg)
    except Exception as e:
        failure_msg = f"Error generating QA pairs: {str(e)}"
        all_validation_failures.append(failure_msg)
        logger.error(failure_msg)
        logger.error(f"Traceback: {e.__traceback__}")
    
    # Test 2: Process from command line args if provided
    if args.input:
        total_tests += 1
        logger.info(f"Test 2: Processing input file: {args.input}")
        
        try:
            # Generate QA pairs
            qa_pairs, stats = generate_qa_pairs(
                marker_output_path=args.input,
                output_dir=args.output_dir,
                max_questions=args.max_questions,
                question_types=question_types,
                random_seed=args.seed,
                min_length=args.min_length
            )
            
            # Check if QA pairs were generated
            if not qa_pairs:
                failure_msg = "No QA pairs generated from input file"
                all_validation_failures.append(failure_msg)
                logger.error(failure_msg)
            else:
                logger.success(f"Generated {len(qa_pairs)} QA pairs from input file")
                logger.info(f"Generation time: {stats['generation_time']:.2f} seconds")
                logger.info(f"Question types: {stats['question_type_counts']}")
                logger.info(f"Source types: {stats['source_type_counts']}")
                
                # Check output files
                output_files = stats["output_files"]
                if not output_files:
                    failure_msg = "No output files generated from input file"
                    all_validation_failures.append(failure_msg)
                    logger.error(failure_msg)
                else:
                    for fmt, path in output_files.items():
                        if not os.path.exists(path):
                            failure_msg = f"Output file {path} does not exist"
                            all_validation_failures.append(failure_msg)
                            logger.error(failure_msg)
                        else:
                            logger.success(f"Output file created: {path}")
        except Exception as e:
            failure_msg = f"Error generating QA pairs from input file: {str(e)}"
            all_validation_failures.append(failure_msg)
            logger.error(failure_msg)
    
    # Clean up sample file
    if os.path.exists(sample_path):
        os.remove(sample_path)
    
    # Final validation result
    if all_validation_failures:
        logger.error(f"❌ VALIDATION FAILED - {len(all_validation_failures)} of {total_tests} tests failed:")
        for failure in all_validation_failures:
            logger.error(f"  - {failure}")
        sys.exit(1)  # Exit with error code
    else:
        logger.success(f"✅ VALIDATION PASSED - All {total_tests} tests produced expected results")
        logger.info("QA Generator is validated and ready for use")
        sys.exit(0)  # Exit with success code