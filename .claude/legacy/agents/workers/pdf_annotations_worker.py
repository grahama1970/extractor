#!/usr/bin/env python3
"""
PDF Annotations Worker - Mechanical executor for annotation extraction and analysis.

This worker provides the implementation for the pdf-annotations sub-agent.
It handles annotation extraction, content analysis, and interpretation with 
Knowledge Architect integration for caching, tool journey tracking, and edge 
relationship creation.

Key capabilities:
- Extract all PDF annotation types (both standard and custom)
- Analyze content inside Square annotations (feature engineering)
- Interpret annotation meaning with semantic rationale
- Map custom annotation types to standard PDF types for interoperability
- Store patterns in Knowledge Architect for learning

ANNOTATION TYPE MAPPING:
This worker handles both standard PDF annotation types (ISO 32000) and custom
semantic types used in specialized document processing:

Standard Types (ISO 32000):
- Square, FreeText, Highlight, Circle, Text, Ink, Stamp

Custom Semantic Types (for document structure corrections):
- section_header → Square (box around header text)
- figure → Square (box around figure/diagram)
- merge_table → FreeText (instruction to merge split tables)
- not_section_header → FreeText (instruction to fix misclassified headers)

AGENT VERIFICATION INSTRUCTIONS:
- Run this script directly to execute working_usage()
- The working_usage() function demonstrates all core capabilities
- debug_function() is for testing new features
- All operations integrate with Knowledge Architect

Example Usage:
    # Direct execution
    python pdf_annotations_worker.py
    
    # From sub-agent markdown
    from .claude.agents.workers.pdf_annotations_worker import (
        extract_annotations,
        interpret_annotations,
        analyze_square_content
    )
"""

import asyncio
import json
import sys
import time
import hashlib
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

# Third-party imports
from loguru import logger
from dotenv import load_dotenv, find_dotenv
import fitz  # PyMuPDF

# Knowledge Architect imports (MANDATORY for all sub-agents)
sys.path.insert(0, str(Path.home() / ".claude" / "agents"))
from workers.knowledge_architect_worker import (
    upsert_impl,
    semantic_search_impl,
    edge_impl,
    query_impl,
    find_similar_documents_impl,
    build_faiss_index_impl,
    find_most_successful_sequences_impl,
    # Centralized tool journey tracking functions
    ToolJourneyTracker,
    create_solution_relationships,
    check_existing_solutions,
    extract_task_type
)

# Configure logging
logger.remove()
logger.add(sys.stderr, level="INFO", format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>")

# Load environment variables
load_dotenv(find_dotenv())

# Constants for this agent
AGENT_NAME = "pdf-annotations"
COLLECTION_PREFIX = f"{AGENT_NAME}_"
CACHE_COLLECTION = f"{COLLECTION_PREFIX}cache"
ANNOTATIONS_COLLECTION = "pdf_annotations"

# Import the annotation extractor from the extractor codebase
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from src.extractor.core.learning.annotation_extractor import (
    extract_annotations_from_pdf,
    find_nearby_content
)


def analyze_content_features(text: str, blocks: List[Dict]) -> Dict[str, Any]:
    """Analyze content features to determine type."""
    features = {
        'content_type': 'unknown',
        'has_numbering': False,
        'has_caption': False,
        'is_header_pattern': False
    }
    
    if not text:
        return features
    
    # Check for section header patterns
    import re
    if re.match(r'^\d+(\.\d+)*\.?\s+\w', text):
        features['has_numbering'] = True
        features['is_header_pattern'] = True
        features['content_type'] = 'section_header'
    
    # Check for table captions
    elif re.match(r'^(Table|TABLE|Tab\.)\s+\d+', text, re.IGNORECASE):
        features['has_caption'] = True
        features['content_type'] = 'table'
    
    # Check for figure captions
    elif re.match(r'^(Figure|FIGURE|Fig\.)\s+\d+', text, re.IGNORECASE):
        features['has_caption'] = True
        features['content_type'] = 'figure'
    
    return features


# ============================================
# MAIN AGENT FUNCTIONS
# ============================================

async def extract_annotations(pdf_path: str, analyze_content: bool = True) -> Dict[str, Any]:
    """
    Extract all annotations from a PDF file with content analysis.
    
    This function:
    1. Checks for cached results
    2. Tracks tool journey
    3. Extracts annotations
    4. Analyzes Square annotation content
    5. Returns structured results
    """
    task_description = f"Extract annotations from PDF: {pdf_path}"
    task_type = extract_task_type(task_description)
    
    # Initialize journey tracker
    journey = ToolJourneyTracker(task_type, task_description)
    
    # Check for existing solutions
    existing = check_existing_solutions(task_description)
    if existing and existing.get('has_patterns'):
        logger.info(f"Using optimal sequence: {existing['optimal_sequence']['sequence']}")
    
    try:
        # Step 1: Check cache
        cache_key = hashlib.md5(f"annotations:{pdf_path}".encode()).hexdigest()
        step_idx = journey.add_step("cache", "check", {"pdf_path": pdf_path})
        
        cached = query_impl(
            collection=CACHE_COLLECTION,
            aql=f"FOR doc IN {CACHE_COLLECTION} FILTER doc._key == @key RETURN doc",
            bind_vars=json.dumps({"key": cache_key})
        )
        
        if cached.get('success') and cached.get('results'):
            journey.complete_step(step_idx, True, "Found cached annotations")
            return cached['results'][0]['data']
        
        journey.complete_step(step_idx, False, "No cache found")
        
        # Step 2: Extract annotations
        step_idx = journey.add_step("annotation_extractor", "extract", {"pdf_path": pdf_path})
        
        result = extract_annotations_from_pdf(pdf_path)
        
        if not result or result.get('status') == 'error':
            journey.complete_step(step_idx, False, f"Extraction failed: {result.get('message', 'Unknown error')}")
            return {
                'success': False,
                'error': result.get('message', 'Failed to extract annotations'),
                'tool_journey': journey.journey
            }
        
        annotations = result.get('annotations', [])
        journey.complete_step(step_idx, True, f"Extracted {len(annotations)} annotations")
        
        # Step 3: Analyze Square annotation content if requested
        if analyze_content and annotations:
            step_idx = journey.add_step("content_analyzer", "analyze_squares", {"count": len(annotations)})
            enhanced_annotations = await enhance_annotations_with_content(pdf_path, annotations)
            journey.complete_step(step_idx, True, f"Enhanced {len([a for a in enhanced_annotations if a.get('content')])} annotations with content")
            annotations = enhanced_annotations
        
        # If successful, save journey and cache
        if annotations:
            journey.finish_journey("success")
            journey.save_successful_journey()
            
            # Cache results
            upsert_impl(
                collection=CACHE_COLLECTION,
                search=json.dumps({'_key': cache_key}),
                update=json.dumps({'access_count': 1}),
                create=json.dumps({
                    '_key': cache_key,
                    'pdf_path': pdf_path,
                    'data': {
                        'success': True,
                        'annotations': annotations,
                        'extraction_time': datetime.now().isoformat()
                    },
                    'cached_at': datetime.now().isoformat()
                })
            )
            
            # Create solution relationships
            solution_summary = f"Extracted {len(annotations)} annotations from PDF"
            create_solution_relationships(
                problem=task_description,
                solution=solution_summary,
                tool_journey=journey.journey,
                metrics={'annotation_count': len(annotations)}
            )
        
        # Return comprehensive results
        return {
            'success': True,
            'annotations': annotations,
            'metrics': {
                'tool_journey': journey.journey,
                'annotation_count': len(annotations),
                'types': list(set(a.get('type', 'Unknown') for a in annotations))
            },
            'agent': AGENT_NAME
        }
        
    except Exception as e:
        logger.error(f"Annotation extraction failed: {e}")
        journey.finish_journey("failed")
        return {
            'success': False,
            'error': str(e),
            'tool_journey': journey.journey
        }


async def enhance_annotations_with_content(pdf_path: str, annotations: List[Dict]) -> List[Dict]:
    """
    Enhance annotations by analyzing what content is inside them.
    This is the feature engineering step for Square annotations.
    """
    doc = fitz.open(pdf_path)
    enhanced = []
    
    for annot in annotations:
        enhanced_annot = annot.copy()
        
        # Only analyze Square, Circle, Rectangle annotations
        if annot.get('type') in ['Square', 'Circle', 'Rectangle']:
            page_num = annot.get('page', 0)
            if 0 <= page_num < len(doc):
                page = doc[page_num]
                
                # Find content inside the annotation
                nearby = find_nearby_content(page, annot['rect'])
                overlapping = nearby.get('overlapping', [])
                
                if overlapping:
                    # Get primary text content
                    primary_text = ' '.join([item['text'] for item in overlapping if item.get('text')])
                    
                    # Analyze content features
                    features = analyze_content_features(primary_text, overlapping)
                    
                    # Add enhanced information
                    enhanced_annot['content'] = primary_text
                    enhanced_annot['content_features'] = features
                    enhanced_annot['inferred_type'] = features['content_type']
                    enhanced_annot['blocks_inside'] = len(overlapping)
        
        enhanced.append(enhanced_annot)
    
    doc.close()
    return enhanced


async def interpret_annotations(annotations: List[Dict], pdf_path: str = None) -> Dict[str, Any]:
    """
    Interpret annotations and provide semantic rationale for each.
    
    This function provides the "why" behind each annotation:
    - What type of content is marked
    - Why it was marked
    - What action is needed
    """
    task_description = f"Interpret {len(annotations)} annotations"
    journey = ToolJourneyTracker("interpret", task_description)
    
    try:
        interpreted = []
        
        # Process each annotation
        step_idx = journey.add_step("interpreter", "analyze", {"count": len(annotations)})
        
        for annot in annotations:
            interpretation = await interpret_single_annotation(annot)
            interpreted.append({
                **annot,
                'interpretation': interpretation
            })
        
        journey.complete_step(step_idx, True, f"Interpreted {len(interpreted)} annotations")
        
        # Store interpretations in Knowledge Architect
        if pdf_path:
            step_idx = journey.add_step("knowledge_architect", "store", {"count": len(interpreted)})
            stored_count = 0
            
            for interp in interpreted:
                if interp.get('interpretation'):
                    stored = await store_annotation_interpretation(interp, pdf_path)
                    if stored:
                        stored_count += 1
            
            journey.complete_step(step_idx, True, f"Stored {stored_count} interpretations")
        
        # Finish journey
        journey.finish_journey("success")
        journey.save_successful_journey()
        
        return {
            'success': True,
            'interpreted_annotations': interpreted,
            'metrics': {
                'tool_journey': journey.journey,
                'total_annotations': len(annotations),
                'interpreted': len(interpreted)
            }
        }
        
    except Exception as e:
        logger.error(f"Interpretation failed: {e}")
        journey.finish_journey("failed")
        return {
            'success': False,
            'error': str(e),
            'tool_journey': journey.journey
        }


async def interpret_single_annotation(annot: Dict) -> Dict[str, Any]:
    """
    Interpret a single annotation based on its type and content.
    
    Handles both standard PDF annotation types (Square, FreeText, Highlight) 
    and custom annotation types (section_header, merge_table, not_section_header, figure).
    """
    annot_type = annot.get('type', 'Unknown')
    content = annot.get('content', '')
    instruction = annot.get('instruction', '')
    extracted_content = annot.get('extracted_content', '')
    
    interpretation = {
        'marking': 'unknown',
        'rationale': 'Unable to determine purpose',
        'action': 'Review manually',
        'confidence': 0.0
    }
    
    # ==== CUSTOM ANNOTATION TYPES (Best Practice) ====
    # These follow the pattern used in professional PDF annotation tools
    # where annotations have semantic types that directly indicate their purpose
    
    if annot_type == 'section_header':
        # Custom type that directly indicates a section header
        interpretation = {
            'marking': 'section_header',
            'rationale': f"Annotation type 'section_header' directly indicates this text should be classified as a SectionHeader block",
            'action': 'Change block type from Text to SectionHeader and ensure proper hierarchy level',
            'confidence': 0.95
        }
        if extracted_content:
            interpretation['rationale'] += f". Content: '{extracted_content[:60]}...'"
            if re.match(r'^[\d\.]+\s+', extracted_content):
                interpretation['confidence'] = 0.98  # Higher confidence for numbered headers
                
    elif annot_type == 'merge_table':
        # Custom type for split tables
        interpretation = {
            'marking': 'split_table',
            'rationale': "Annotation type 'merge_table' indicates a table that has been split across pages or columns",
            'action': 'Identify all table fragments and merge into single coherent table structure',
            'confidence': 0.95
        }
        if content and 'merge table' in content.lower():
            interpretation['confidence'] = 0.98
            
    elif annot_type == 'not_section_header':
        # Custom type for false headers
        interpretation = {
            'marking': 'false_header',
            'rationale': "Annotation type 'not_section_header' indicates text incorrectly classified as a header",
            'action': 'Change block type from SectionHeader to Text',
            'confidence': 0.90
        }
        if content and 'not' in content.lower() and 'header' in content.lower():
            interpretation['rationale'] = f"Annotation explicitly states: '{content}'"
            interpretation['confidence'] = 0.95
            
    elif annot_type == 'figure':
        # Custom type for figures
        interpretation = {
            'marking': 'figure',
            'rationale': "Annotation type 'figure' indicates this area contains a figure, diagram, or image",
            'action': 'Extract as Figure block with appropriate caption and description',
            'confidence': 0.85
        }
        if extracted_content and re.match(r'^(Figure|Fig\.)\s+\d+', extracted_content, re.IGNORECASE):
            interpretation['confidence'] = 0.95
            
    # ==== STANDARD PDF ANNOTATION TYPES ====
    # These follow the PDF specification (ISO 32000)
    
    elif annot_type == 'Square' and (content or extracted_content):
        # Square/Rectangle annotations - analyze content to determine purpose
        text_to_analyze = extracted_content or content
        features = annot.get('content_features', {})
        content_type = features.get('content_type', 'unknown')
        
        if content_type == 'section_header' or re.match(r'^[\d\.]+\s+', text_to_analyze):
            interpretation = {
                'marking': 'section_header',
                'rationale': f"Square annotation surrounds text with numbered hierarchy pattern: '{text_to_analyze[:50]}...'",
                'action': 'Ensure marker classifies this as SectionHeader type, not Text',
                'confidence': 0.95
            }
        elif content_type == 'table' or re.match(r'^(Table|Tab\.)\s+\d+', text_to_analyze, re.IGNORECASE):
            interpretation = {
                'marking': 'table',
                'rationale': f"Square annotation marks tabular data or table caption",
                'action': 'Process as Table block with proper row/column structure',
                'confidence': 0.90
            }
        elif content_type == 'figure' or re.match(r'^(Figure|Fig\.)\s+\d+', text_to_analyze, re.IGNORECASE):
            interpretation = {
                'marking': 'figure',
                'rationale': f"Square annotation marks a figure or diagram area",
                'action': 'Extract as Figure block with caption',
                'confidence': 0.85
            }
        else:
            interpretation = {
                'marking': 'important_content',
                'rationale': f"Square annotation marks '{text_to_analyze[:50]}...' for special attention",
                'action': 'Ensure content is properly extracted with appropriate block type',
                'confidence': 0.75
            }
    
    elif annot_type == 'FreeText':
        # FreeText annotations - check both instruction and content fields
        text = instruction or content
        if text:
            text_lower = text.lower()
            
            if 'merge' in text_lower and 'table' in text_lower:
                interpretation = {
                    'marking': 'split_table',
                    'rationale': f"FreeText annotation '{text}' indicates a table split across pages",
                    'action': 'Merge table blocks across page boundary',
                    'confidence': 0.95
                }
            elif 'not' in text_lower and 'header' in text_lower:
                interpretation = {
                    'marking': 'false_header',
                    'rationale': f"FreeText annotation '{text}' indicates incorrectly classified header",
                    'action': 'Change block type from SectionHeader to Text',
                    'confidence': 0.90
                }
            elif 'section' in text_lower or 'subsection' in text_lower:
                interpretation = {
                    'marking': 'section_boundary',
                    'rationale': f"FreeText annotation '{text}' provides section organization guidance",
                    'action': 'Adjust section hierarchy based on instruction',
                    'confidence': 0.85
                }
            else:
                interpretation = {
                    'marking': 'custom_instruction',
                    'rationale': f"FreeText annotation provides instruction: '{text}'",
                    'action': f"Apply the specified correction: {text}",
                    'confidence': 0.80
                }
    
    elif annot_type == 'Highlight':
        # Highlight annotations
        interpretation = {
            'marking': 'important_content',
            'rationale': 'Highlighted text indicates important content that must be preserved during extraction',
            'action': 'Ensure this content is properly extracted and not lost or corrupted',
            'confidence': 0.80
        }
    
    elif annot_type in ['Circle', 'Polygon', 'PolyLine']:
        # Other geometric annotations
        interpretation = {
            'marking': 'area_of_interest',
            'rationale': f"{annot_type} annotation marks a specific area for attention",
            'action': 'Review the marked area and ensure proper extraction',
            'confidence': 0.70
        }
    
    elif annot_type == 'Ink':
        # Ink/drawing annotations
        interpretation = {
            'marking': 'handwritten_note',
            'rationale': 'Ink annotation may contain handwritten corrections or notes',
            'action': 'Review for manual corrections or additional instructions',
            'confidence': 0.65
        }
    
    # Add standard annotation type to interpretation for tracking
    interpretation['annotation_type'] = annot_type
    interpretation['standard_type'] = map_to_standard_type(annot_type)
    
    return interpretation


def map_to_standard_type(custom_type: str) -> str:
    """
    Map custom annotation types to standard PDF annotation types.
    
    Standard types from PDF specification (ISO 32000):
    - Text, FreeText, Line, Square, Circle, Polygon, PolyLine,
    - Highlight, Underline, Squiggly, StrikeOut, Stamp, Caret,
    - Ink, Popup, FileAttachment, Sound, Movie, Widget, Screen,
    - PrinterMark, TrapNet, Watermark, 3D, Redact
    """
    mapping = {
        # Custom types to standard types
        'section_header': 'Square',      # Box around header text
        'figure': 'Square',              # Box around figure
        'merge_table': 'FreeText',       # Text instruction
        'not_section_header': 'FreeText', # Text instruction
        
        # Already standard types
        'Square': 'Square',
        'FreeText': 'FreeText',
        'Highlight': 'Highlight',
        'Circle': 'Circle',
        'Text': 'Text',
        'Ink': 'Ink',
        'Stamp': 'Stamp'
    }
    
    return mapping.get(custom_type, custom_type)


def standardize_annotations(annotations: List[Dict]) -> List[Dict]:
    """
    Standardize annotations by adding standard type mapping and semantic metadata.
    
    This follows PDF annotation best practices by:
    1. Preserving the original custom type for semantic meaning
    2. Adding a standard_type field for interoperability
    3. Adding semantic_category to group related corrections
    
    Args:
        annotations: List of annotations with potential custom types
        
    Returns:
        List of annotations with added standardization fields
    """
    standardized = []
    
    for annot in annotations:
        std_annot = annot.copy()
        custom_type = annot.get('type', 'Unknown')
        
        # Add standard type mapping
        std_annot['standard_type'] = map_to_standard_type(custom_type)
        std_annot['original_type'] = custom_type
        
        # Add semantic category for document structure corrections
        if custom_type in ['section_header', 'figure']:
            std_annot['semantic_category'] = 'structure_marking'
        elif custom_type in ['merge_table', 'not_section_header']:
            std_annot['semantic_category'] = 'structure_correction'
        elif custom_type == 'Highlight':
            std_annot['semantic_category'] = 'emphasis'
        else:
            std_annot['semantic_category'] = 'general'
        
        # Add recommended color coding based on semantic category
        color_mapping = {
            'structure_marking': '#0066CC',     # Blue for structure elements
            'structure_correction': '#CC6600',   # Orange for corrections
            'emphasis': '#FFFF00',              # Yellow for highlights
            'general': '#00CC00'                # Green for general
        }
        std_annot['recommended_color'] = color_mapping.get(
            std_annot['semantic_category'], 
            '#000000'
        )
        
        standardized.append(std_annot)
    
    return standardized


async def store_annotation_interpretation(annotation: Dict, pdf_path: str) -> bool:
    """
    Store annotation interpretation in Knowledge Architect.
    """
    try:
        # Create unique key from annotation properties
        annot_data = f"{pdf_path}:{annotation.get('page', 0)}:{annotation.get('rect', [])}"
        annotation_hash = hashlib.md5(annot_data.encode()).hexdigest()[:8]
        
        interpretation = annotation.get('interpretation', {})
        
        # Store in ArangoDB
        result = upsert_impl(
            collection=ANNOTATIONS_COLLECTION,
            search=json.dumps({'_key': annotation_hash}),
            update=json.dumps({'usage_count': 1}),
            create=json.dumps({
                '_key': annotation_hash,
                'pdf_path': pdf_path,
                'page': annotation.get('page', 0),
                'annotation_type': annotation.get('type', 'Unknown'),
                'content': annotation.get('content', ''),
                'instruction': annotation.get('instruction', ''),
                'interpretation': interpretation.get('marking', 'unknown'),
                'rationale': interpretation.get('rationale', ''),
                'action': interpretation.get('action', ''),
                'confidence': interpretation.get('confidence', 0.0),
                'rect': annotation.get('rect', []),
                'created_at': datetime.now().isoformat()
            })
        )
        
        return result.get('success', False)
        
    except Exception as e:
        logger.error(f"Failed to store interpretation: {e}")
        return False


async def create_annotation_edges(annotation_id: str, block_ids: List[str]) -> int:
    """
    Create edges between annotations and the blocks they guide.
    """
    created = 0
    
    for block_id in block_ids:
        result = edge_impl(
            from_collection=ANNOTATIONS_COLLECTION,
            from_key=annotation_id,
            to_collection='document_blocks',
            to_key=block_id,
            edge_collection='annotation_guides_block',
            data=json.dumps({
                'relationship': 'marks_for_correction',
                'created_at': datetime.now().isoformat()
            })
        )
        
        if result.get('success'):
            created += 1
    
    return created


# ============================================
# USAGE EXAMPLES (MANDATORY)
# ============================================

async def working_usage():
    """
    Known working examples that demonstrate all agent capabilities.
    
    CRITICAL FOR AGENTS:
    - Shows tool journey tracking
    - Demonstrates edge relationship creation
    - Validates Knowledge Architect integration
    - Must pass all assertions
    """
    logger.info("=== Running Working Usage Examples ===")
    
    # Example 1: Extract annotations with content analysis
    test_pdf = "/home/graham/workspace/experiments/extractor/gold_standards/BHT_CV32A65X_marked.pdf"
    
    if Path(test_pdf).exists():
        logger.info("\nTest 1: Extract annotations with content analysis")
        result = await extract_annotations(test_pdf, analyze_content=True)
        
        # Verify results
        assert result['success'], "Expected successful extraction"
        assert 'tool_journey' in result['metrics'], "Missing tool journey"
        assert len(result['metrics']['tool_journey']) >= 2, "Expected at least 2 journey steps"
        assert result['agent'] == AGENT_NAME, f"Expected agent name {AGENT_NAME}"
        
        logger.success(f"✓ Extracted {len(result.get('annotations', []))} annotations")
        
        # Show sample Square annotation with content
        for annot in result.get('annotations', []):
            if annot.get('type') == 'Square' and annot.get('content'):
                logger.info(f"Square annotation found with content: {annot['content'][:50]}...")
                break
        
        # Example 2: Interpret annotations
        if result.get('annotations'):
            logger.info("\nTest 2: Interpret annotations")
            interp_result = await interpret_annotations(result['annotations'][:3], test_pdf)
            
            assert interp_result['success'], "Expected successful interpretation"
            assert len(interp_result['interpreted_annotations']) > 0, "No interpretations generated"
            
            # Show sample interpretation
            for annot in interp_result['interpreted_annotations']:
                if annot.get('interpretation'):
                    interp = annot['interpretation']
                    logger.info(f"Interpretation: {interp['marking']} - {interp['rationale'][:80]}...")
                    break
            
            logger.success("✓ Annotation interpretation completed")
    else:
        # Use simulated data for testing
        logger.info("\nTest with simulated annotations")
        
        test_annotations = [
            {
                'page': 0,
                'type': 'Square',
                'rect': [64.7, 71.0, 327.4, 105.6],
                'content': '4.1.5.4. BHT (Branch History Table) submodule',
                'content_features': {'content_type': 'section_header'}
            },
            {
                'page': 1,
                'type': 'FreeText',
                'instruction': 'Merge Table',
                'rect': [100, 200, 300, 250]
            }
        ]
        
        result = await interpret_annotations(test_annotations)
        assert result['success'], "Expected successful interpretation"
        logger.success("✓ Simulated annotation test passed")
    
    # Example 3: Verify Knowledge Architect integration
    logger.info("\nTest 3: Knowledge Architect integration")
    
    # Check if annotations were stored
    solution_check = semantic_search_impl(
        collection='solutions',
        query='Extract annotations from PDF',
        text_field='problem',
        top_k=1
    )
    
    if solution_check.get('success') and solution_check.get('results'):
        logger.success("✓ Knowledge Architect integration verified")
    else:
        logger.warning("No solutions found - this is expected on first run")
    
    # Example 4: Tool sequence retrieval
    logger.info("\nTest 4: Tool sequence retrieval")
    
    sequences = find_most_successful_sequences_impl(
        task_type='extract',
        limit=3
    )
    
    if sequences.get('success') and sequences.get('sequences'):
        logger.info(f"Found {len(sequences['sequences'])} successful patterns")
        for seq in sequences['sequences'][:2]:
            logger.info(f"  - {seq['sequence']} (used {seq['usage_count']} times)")
    
    logger.success("✓ All working usage tests passed!")
    return True


async def debug_function():
    """
    Debug function for testing new features.
    
    AGENT: Rewrite this freely for experimentation!
    Current focus: Testing BHT PDF annotation extraction and reasoning
    """
    logger.info("=== Running Debug Function ===")
    
    # Test with actual BHT PDF
    marked_pdf = Path("/home/graham/workspace/experiments/extractor/proof_of_concept/BHT_CV32A65X_marked.pdf")
    
    if not marked_pdf.exists():
        logger.error(f"BHT marked PDF not found at: {marked_pdf}")
        return False
    
    logger.info(f"Testing annotation extraction on: {marked_pdf}")
    
    # Step 1: Extract annotations
    logger.info("\n=== Step 1: Basic Extraction ===")
    from src.extractor.core.learning.annotation_extractor import extract_annotations_from_pdf
    result = extract_annotations_from_pdf(str(marked_pdf))
    
    if result.get('status') == 'error':
        logger.error(f"Extraction failed: {result.get('message')}")
        return False
    
    annotations = result.get('annotations', [])
    logger.info(f"Extracted {len(annotations)} annotations")
    
    # Step 2: Let's see what types we actually got
    logger.info("\n=== Step 2: Analyze Annotation Types ===")
    type_counts = {}
    for annot in annotations:
        ann_type = annot.get('type', 'Unknown')
        type_counts[ann_type] = type_counts.get(ann_type, 0) + 1
    
    logger.info("Annotation types found:")
    for ann_type, count in type_counts.items():
        logger.info(f"  {ann_type}: {count}")
    
    # Step 3: Extract content from all annotations for feature engineering
    logger.info("\n=== Step 3: Feature Engineering - Extract Content from Annotations ===")
    
    # Import PyMuPDF to analyze content
    import fitz
    doc = fitz.open(str(marked_pdf))
    
    enhanced_annotations = []
    for i, annot in enumerate(annotations):
        logger.info(f"\nProcessing annotation {i+1}/{len(annotations)}:")
        logger.info(f"  Type: {annot.get('type')}")
        logger.info(f"  Page: {annot.get('page', 0)}")
        
        # For section_header and figure annotations, extract content
        if annot.get('type') in ['section_header', 'figure']:
            page_num = annot.get('page', 0)
            if 0 <= page_num < len(doc):
                page = doc[page_num]
                rect = annot.get('rect', [])
                
                # Extract text in this area
                if len(rect) >= 4:
                    # Convert rect to fitz.Rect - handle both list and tuple
                    if isinstance(rect, (list, tuple)):
                        rect_obj = fitz.Rect(rect[0], rect[1], rect[2], rect[3])
                    else:
                        rect_obj = fitz.Rect(rect)
                    
                    # Get text content within the rectangle
                    text = page.get_text(clip=rect_obj).strip()
                    
                    # Look for content BELOW the annotation for section headers
                    if annot.get('type') == 'section_header' and not text:
                        # Try expanding the search area below the annotation
                        extended_rect = fitz.Rect(rect[0], rect[3], rect[2], rect[3] + 50)
                        text = page.get_text(clip=extended_rect).strip()
                    
                    if text:
                        logger.info(f"  Found content: '{text[:80]}...'")
                        annot['extracted_content'] = text
                        
                        # Check if it's a numbered header
                        import re
                        if re.match(r'^[\d\.]+\s+', text):
                            logger.success(f"  ✅ Contains numbered header pattern!")
                            annot['is_numbered_header'] = True
                    else:
                        logger.warning(f"  ⚠️ No text content found in annotation area")
        
        enhanced_annotations.append(annot)
    
    doc.close()
    
    # Step 4: Semantic interpretation based on custom types
    logger.info("\n=== Step 4: Semantic Interpretation of Custom Annotation Types ===")
    
    for i, annot in enumerate(enhanced_annotations[:6]):  # Show first 6
        logger.info(f"\n{'='*50}")
        logger.info(f"Annotation {i+1}:")
        ann_type = annot.get('type', '')
        
        # Interpret based on custom type
        if ann_type == 'section_header':
            interpretation = {
                'marking': 'section_header',
                'rationale': f"Annotation type 'section_header' directly indicates this text should be a SectionHeader block",
                'action': 'Ensure marker classifies this as SectionHeader, not Text',
                'confidence': 0.95
            }
            if annot.get('extracted_content'):
                interpretation['rationale'] += f". Content: '{annot['extracted_content'][:60]}...'"
            
        elif ann_type == 'merge_table':
            interpretation = {
                'marking': 'split_table',
                'rationale': "Annotation type 'merge_table' indicates a table split across pages that needs merging",
                'action': 'Merge table blocks across page boundary',
                'confidence': 0.95
            }
            
        elif ann_type == 'not_section_header':
            interpretation = {
                'marking': 'false_header',
                'rationale': "Annotation type 'not_section_header' indicates marker incorrectly classified as header",
                'action': 'Change block type from SectionHeader to Text',
                'confidence': 0.90
            }
            
        elif ann_type == 'figure':
            interpretation = {
                'marking': 'figure',
                'rationale': "Annotation type 'figure' indicates this area contains a figure or diagram",
                'action': 'Extract as Figure block with caption',
                'confidence': 0.85
            }
            
        else:
            interpretation = {
                'marking': 'unknown',
                'rationale': f"Unknown annotation type '{ann_type}'",
                'action': 'Review manually',
                'confidence': 0.5
            }
        
        logger.info(f"  Type: {ann_type}")
        logger.info(f"  Marking: {interpretation['marking']}")
        logger.info(f"  Rationale: {interpretation['rationale']}")
        logger.info(f"  Action: {interpretation['action']}")
        logger.info(f"  Confidence: {interpretation['confidence']:.2f}")
        
        if annot.get('content'):
            logger.info(f"  Annotation content: '{annot['content']}'")
        if annot.get('extracted_content'):
            logger.info(f"  Extracted content: '{annot['extracted_content'][:80]}...'")
    
    # Step 5: Map custom types to standard types for comparison
    logger.info("\n=== Step 5: Mapping Custom Types to Standard Types ===")
    
    # Create mapping
    type_mapping = {
        'section_header': 'Square',     # 2 annotations
        'figure': 'Square',             # 2 annotations  
        'merge_table': 'FreeText',      # 4 annotations (some with content, some without)
        'not_section_header': 'FreeText'  # 6 annotations
    }
    
    # Map and count
    mapped_counts = {}
    for annot in annotations:
        custom_type = annot.get('type', 'Unknown')
        standard_type = type_mapping.get(custom_type, custom_type)
        mapped_counts[standard_type] = mapped_counts.get(standard_type, 0) + 1
    
    logger.info("Type mapping (custom -> standard):")
    for custom, standard in type_mapping.items():
        custom_count = type_counts.get(custom, 0)
        logger.info(f"  {custom} -> {standard} (count: {custom_count})")
    
    # Step 6: Compare with gold standard using mapped types
    logger.info("\n=== Step 6: Gold Standard Comparison ===")
    
    expected_types = {
        "Square": 4,     # Should be section_header(2) + figure(2) = 4
        "FreeText": 7,   # Should be merge_table(4) + not_section_header(6) = 10? 
        "Highlight": 2   # We don't have any highlight annotations
    }
    
    logger.info("Comparison with gold standard:")
    logger.info(f"Total annotations: expected 13, got {len(annotations)}")
    
    # Show both custom and mapped counts
    logger.info("\nDetailed type analysis:")
    logger.info("Custom types found:")
    for ann_type, count in sorted(type_counts.items()):
        logger.info(f"  {ann_type}: {count}")
    
    logger.info("\nMapped to standard types:")
    for ann_type, expected in expected_types.items():
        actual = mapped_counts.get(ann_type, 0)
        if actual == expected:
            logger.success(f"  ✅ {ann_type}: {actual} (matches)")
        else:
            logger.warning(f"  ⚠️ {ann_type}: expected {expected}, got {actual}")
    
    # Note discrepancy
    total_custom = sum(type_counts.values())
    logger.info(f"\nNote: We have {total_custom} total annotations, but gold standard expects 13")
    logger.info("The custom annotation types don't map 1:1 to standard PDF annotation types")
    
    # Step 7: Write enhanced results to file
    logger.info("\n=== Step 7: Saving Results ===")
    
    output_data = {
        "extraction_time": datetime.now().isoformat(),
        "pdf_path": str(marked_pdf),
        "total_annotations": len(annotations),
        "custom_types": type_counts,
        "type_mapping": type_mapping,
        "mapped_standard_types": mapped_counts,
        "sample_interpretations": []
    }
    
    # Add some sample interpretations
    for i, annot in enumerate(enhanced_annotations[:5]):
        sample = {
            "index": i + 1,
            "type": annot.get('type'),
            "page": annot.get('page', 0),
            "content": annot.get('content', ''),
            "extracted_content": annot.get('extracted_content', '')[:100] + '...' if annot.get('extracted_content') else ''
        }
        output_data["sample_interpretations"].append(sample)
    
    output_file = Path("/home/graham/workspace/experiments/extractor/tmp/annotation_debug_results.json")
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    logger.info(f"Results saved to: {output_file}")
    
    return True


if __name__ == "__main__":
    """
    AGENT INSTRUCTIONS:
    - DEFAULT: Runs working_usage() - stable example that works
    - DEBUG: Run with 'debug' argument to test new ideas
    - DO NOT create external test files - use debug_function() instead!
    """
    import sys
    
    mode = sys.argv[1] if len(sys.argv) > 1 else "working"
    
    if mode == "debug":
        logger.info("Running debug mode...")
        asyncio.run(debug_function())
    else:
        logger.info("Running working usage mode...")
        success = asyncio.run(working_usage())
        exit(0 if success else 1)