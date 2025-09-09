#!/usr/bin/env python3
"""
Form Processor Worker - Knowledge-First Sub-Agent

This sub-agent processes forms, fillable fields, and interactive document elements
using historical patterns from ArangoDB. It identifies form fields, extracts
structure, and provides semantic understanding of form layouts.

Key Features:
- Direct ArangoDB queries for form patterns
- Field type classification (text, checkbox, radio, etc.)
- Form structure extraction
- Field relationship mapping
- Validation rule detection
- Multi-language form support

Usage:
    # Direct execution
    python form_processor_worker.py process_form '{"blocks": [...], "context": {...}}'
    
    # From processor
    result = FormProcessor().process_form(blocks, context)
"""

import json
import sys
import subprocess
import re
import os
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv, find_dotenv

# Configure logging
logger.remove()
logger.add(sys.stderr, level="INFO")

# Load environment variables
load_dotenv(find_dotenv())

# Get path from environment or use default
ARANGO_WORKER_PATH = os.getenv(
    "ARANGO_WORKER_PATH",
    str(Path.home() / "workspace" / "experiments" / "cc_executor" / ".claude" / "agents" / "workers" / "arango_tools_worker.py")
)

if not Path(ARANGO_WORKER_PATH).exists():
    logger.warning(f"ArangoDB worker not found at {ARANGO_WORKER_PATH}. Set ARANGO_WORKER_PATH env variable.")


class FormProcessor:
    """Knowledge-first form processing using ArangoDB patterns."""
    
    def __init__(self):
        """Initialize the form processor."""
        self.field_types = [
            "text_input",
            "checkbox", 
            "radio_button",
            "dropdown",
            "date_field",
            "signature",
            "multi_line_text",
            "numeric_field",
            "email_field",
            "phone_field"
        ]
        
        # Common form field indicators
        self.field_indicators = {
            'labels': ['name', 'date', 'address', 'phone', 'email', 'signature', 
                      'dob', 'ssn', 'id', 'number', 'amount', 'quantity'],
            'patterns': {
                'fill_line': r'_{3,}',
                'checkbox': r'\[[\s\*xX]?\]|\([\s\*xX]?\)|☐|☑|☒',
                'date_format': r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|MM[/-]DD[/-]YYYY',
                'field_delimiter': r':\s*_{3,}|:\s*\[[\s\*xX]?\]',
                'label_value': r'([^:]+):\s*(.+)',
            }
        }
        
    def _call_arango(self, method: str, **kwargs: Any) -> Dict[str, Any]:
        """Direct call to ArangoDB worker - NO generic prompts!"""
        try:
            args_json = json.dumps(kwargs)
            result = subprocess.run(
                [sys.executable, ARANGO_WORKER_PATH, method, args_json],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                logger.error(f"ArangoDB worker error: {result.stderr}")
                return {"error": result.stderr}
                
            return json.loads(result.stdout)
        except Exception as e:
            logger.error(f"Failed to call ArangoDB: {e}")
            return {"error": str(e)}
    
    def process_form(self, blocks: List[Dict[str, Any]], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process form blocks using knowledge-first approach.
        
        Args:
            blocks: List of blocks potentially containing form elements
            context: Context including page info, document type
            
        Returns:
            Dictionary with form structure and field information
        """
        logger.info(f"Processing potential form with {len(blocks)} blocks")
        
        # Step 1: Identify form fields in blocks
        identified_fields = self._identify_form_fields(blocks)
        
        # Step 2: Query similar form patterns
        form_patterns = self._query_form_patterns(identified_fields, context)
        
        # Step 3: Query field type patterns
        field_classifications = self._classify_field_types(identified_fields, form_patterns)
        
        # Step 4: Extract form structure
        form_structure = self._extract_form_structure(blocks, field_classifications)
        
        # Step 5: Query validation patterns
        validation_rules = self._query_validation_patterns(field_classifications)
        
        # Step 6: Build final form representation
        form_result = self._build_form_representation(
            identified_fields, field_classifications, form_structure, validation_rules
        )
        
        # Step 7: Store successful pattern if high confidence
        if form_result['confidence'] > 0.8 and len(form_result['fields']) > 2:
            self._store_form_pattern(form_result)
        
        return form_result
    
    def _identify_form_fields(self, blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Identify potential form fields in blocks."""
        fields = []
        
        for idx, block in enumerate(blocks):
            text = block.get('text', '').strip()
            if not text:
                continue
            
            # Check for fill lines
            fill_lines = re.findall(self.field_indicators['patterns']['fill_line'], text)
            if fill_lines:
                fields.append({
                    'block_index': idx,
                    'text': text,
                    'type_hint': 'fill_line',
                    'fill_line_count': len(fill_lines),
                    'bbox': block.get('bbox', [0, 0, 100, 100])
                })
            
            # Check for checkboxes
            checkboxes = re.findall(self.field_indicators['patterns']['checkbox'], text)
            if checkboxes:
                fields.append({
                    'block_index': idx,
                    'text': text,
                    'type_hint': 'checkbox',
                    'checkbox_count': len(checkboxes),
                    'bbox': block.get('bbox', [0, 0, 100, 100])
                })
            
            # Check for labeled fields
            label_match = re.search(self.field_indicators['patterns']['field_delimiter'], text)
            if label_match:
                # Extract label
                label_end = label_match.start()
                label = text[:label_end].strip()
                
                fields.append({
                    'block_index': idx,
                    'text': text,
                    'type_hint': 'labeled_field',
                    'label': label,
                    'bbox': block.get('bbox', [0, 0, 100, 100])
                })
            
            # Check for common field labels
            text_lower = text.lower()
            for label in self.field_indicators['labels']:
                if label in text_lower:
                    fields.append({
                        'block_index': idx,
                        'text': text,
                        'type_hint': 'known_label',
                        'detected_label': label,
                        'bbox': block.get('bbox', [0, 0, 100, 100])
                    })
                    break
        
        return fields
    
    def _query_form_patterns(self, fields: List[Dict[str, Any]], context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Query for similar form patterns in knowledge base."""
        if not fields:
            return []
        
        # Build feature vector for form
        features = {
            "field_count": len(fields),
            "has_checkboxes": any(f['type_hint'] == 'checkbox' for f in fields),
            "has_fill_lines": any(f['type_hint'] == 'fill_line' for f in fields),
            "has_signature": any('signature' in f.get('text', '').lower() for f in fields),
            "has_date_fields": any('date' in f.get('text', '').lower() for f in fields),
            "field_labels": [f.get('label', f.get('detected_label', '')) for f in fields if f.get('label') or f.get('detected_label')]
        }
        
        # Query similar forms
        query = """
        FOR form IN pdf_forms
          LET label_similarity = (
            LENGTH(
              INTERSECTION(@field_labels, form.field_labels)
            ) / 
            MAX([LENGTH(@field_labels), LENGTH(form.field_labels), 1])
          )
          LET feature_match = (
            (ABS(@field_count - form.field_count) < 5 ? 1 : 0) +
            (@has_checkboxes == form.has_checkboxes ? 1 : 0) +
            (@has_fill_lines == form.has_fill_lines ? 1 : 0) +
            (@has_signature == form.has_signature ? 1 : 0) +
            (@has_date_fields == form.has_date_fields ? 1 : 0)
          ) / 5.0
          LET total_score = (label_similarity * 0.6) + (feature_match * 0.4)
          FILTER total_score > 0.3
          SORT total_score DESC
          LIMIT 10
          RETURN {
            form: form,
            similarity: total_score,
            form_type: form.form_type,
            field_structure: form.field_structure,
            common_validations: form.validation_rules
          }
        """
        
        result = self._call_arango(
            "query",
            aql=query,
            bind_vars=json.dumps(features)
        )
        
        if "error" in result:
            logger.warning(f"Form pattern query failed: {result['error']}")
            return []
            
        return result.get('result', [])
    
    def _classify_field_types(self, fields: List[Dict[str, Any]], form_patterns: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
        """Classify each field's type based on patterns."""
        classifications = {}
        
        # Use form patterns to inform classification
        pattern_field_types = {}
        if form_patterns:
            # Aggregate field types from similar forms
            for pattern in form_patterns[:3]:  # Top 3 patterns
                for field_info in pattern.get('field_structure', []):
                    label = field_info.get('label', '').lower()
                    if label:
                        pattern_field_types[label] = field_info.get('field_type', 'text_input')
        
        for field in fields:
            block_idx = field['block_index']
            text = field['text'].lower()
            
            # Start with default classification
            field_type = 'text_input'
            confidence = 0.5
            attributes = {}
            
            # Check pattern-based classification first
            for label, ptype in pattern_field_types.items():
                if label in text:
                    field_type = ptype
                    confidence = 0.8
                    break
            
            # Apply rule-based classification
            if field['type_hint'] == 'checkbox':
                field_type = 'checkbox'
                confidence = 0.9
                attributes['options'] = self._extract_checkbox_options(field['text'])
            
            elif 'signature' in text:
                field_type = 'signature'
                confidence = 0.95
            
            elif any(date_kw in text for date_kw in ['date', 'dob', 'birth']):
                field_type = 'date_field'
                confidence = 0.85
                attributes['format'] = self._detect_date_format(field['text'])
            
            elif any(email_kw in text for email_kw in ['email', 'e-mail']):
                field_type = 'email_field'
                confidence = 0.9
            
            elif any(phone_kw in text for phone_kw in ['phone', 'tel', 'mobile', 'fax']):
                field_type = 'phone_field'
                confidence = 0.85
            
            elif any(num_kw in text for num_kw in ['amount', 'quantity', 'number', 'count', 'ssn', 'id']):
                field_type = 'numeric_field'
                confidence = 0.7
            
            elif field.get('fill_line_count', 0) > 1 or '\n' in field['text']:
                field_type = 'multi_line_text'
                confidence = 0.7
            
            # Query for specific field classification if uncertain
            if confidence < 0.7:
                specific_class = self._query_field_classification(field)
                if specific_class:
                    field_type = specific_class.get('field_type', field_type)
                    confidence = specific_class.get('confidence', confidence)
            
            classifications[block_idx] = {
                'field_type': field_type,
                'confidence': confidence,
                'attributes': attributes,
                'original_text': field['text'],
                'bbox': field['bbox']
            }
        
        return classifications
    
    def _query_field_classification(self, field: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Query for specific field type classification."""
        query = """
        FOR pattern IN form_field_patterns
          LET text_similarity = BM25(pattern.field_text, @field_text)
          FILTER text_similarity > 0.5
          SORT text_similarity DESC
          LIMIT 1
          RETURN {
            field_type: pattern.field_type,
            confidence: pattern.classification_confidence * text_similarity,
            attributes: pattern.common_attributes
          }
        """
        
        result = self._call_arango(
            "query",
            aql=query,
            bind_vars=json.dumps({"field_text": field['text']})
        )
        
        if "error" not in result and result.get('result'):
            return result['result'][0]
        
        return None
    
    def _extract_form_structure(self, blocks: List[Dict[str, Any]], classifications: Dict[int, Dict[str, Any]]) -> Dict[str, Any]:
        """Extract the overall form structure."""
        # Group fields by proximity
        field_groups = []
        current_group = []
        last_y = None
        
        for idx, classification in sorted(classifications.items()):
            bbox = classification['bbox']
            y_pos = bbox[1]
            
            # Check if this field is on a new line (>20 pixels difference)
            if last_y is None or abs(y_pos - last_y) > 20:
                if current_group:
                    field_groups.append(current_group)
                current_group = [(idx, classification)]
                last_y = y_pos
            else:
                current_group.append((idx, classification))
        
        if current_group:
            field_groups.append(current_group)
        
        # Identify sections
        sections = []
        for group in field_groups:
            # Check if group represents a section header
            if len(group) == 1 and group[0][1]['field_type'] == 'text_input':
                text = group[0][1]['original_text']
                if text.isupper() or text.endswith(':'):
                    sections.append({
                        'type': 'section_header',
                        'text': text,
                        'fields': []
                    })
                    continue
            
            # Regular field group
            if sections:
                sections[-1]['fields'].extend([
                    {
                        'index': idx,
                        'type': cls['field_type'],
                        'text': cls['original_text']
                    }
                    for idx, cls in group
                ])
            else:
                # No sections yet, create a default one
                sections.append({
                    'type': 'main',
                    'text': 'Form Fields',
                    'fields': [
                        {
                            'index': idx,
                            'type': cls['field_type'],
                            'text': cls['original_text']
                        }
                        for idx, cls in group
                    ]
                })
        
        return {
            'sections': sections,
            'field_count': len(classifications),
            'has_sections': len(sections) > 1
        }
    
    def _query_validation_patterns(self, classifications: Dict[int, Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Query for validation rules based on field types."""
        validations = {}
        
        # Group by field type for efficient querying
        fields_by_type = {}
        for idx, cls in classifications.items():
            field_type = cls['field_type']
            if field_type not in fields_by_type:
                fields_by_type[field_type] = []
            fields_by_type[field_type].append({
                'index': idx,
                'text': cls['original_text']
            })
        
        # Query validation rules for each field type
        for field_type, fields in fields_by_type.items():
            query = """
            FOR rule IN form_validation_rules
              FILTER rule.field_type == @field_type
              RETURN {
                rule_type: rule.rule_type,
                pattern: rule.validation_pattern,
                error_message: rule.error_message,
                is_required: rule.is_required,
                examples: rule.valid_examples
              }
            """
            
            result = self._call_arango(
                "query",
                aql=query,
                bind_vars=json.dumps({"field_type": field_type})
            )
            
            if "error" not in result:
                validations[field_type] = result.get('result', [])
        
        return validations
    
    def _build_form_representation(
        self,
        identified_fields: List[Dict[str, Any]],
        classifications: Dict[int, Dict[str, Any]],
        structure: Dict[str, Any],
        validations: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """Build final form representation."""
        # Calculate overall confidence
        if classifications:
            avg_confidence = sum(c['confidence'] for c in classifications.values()) / len(classifications)
        else:
            avg_confidence = 0.0
        
        # Build field list with full information
        fields = []
        for idx, classification in classifications.items():
            field = {
                'id': f'field_{idx}',
                'type': classification['field_type'],
                'label': self._extract_field_label(classification['original_text']),
                'original_text': classification['original_text'],
                'confidence': classification['confidence'],
                'attributes': classification.get('attributes', {}),
                'bbox': classification['bbox'],
                'validations': validations.get(classification['field_type'], [])
            }
            fields.append(field)
        
        # Determine form type
        form_type = self._determine_form_type(fields, structure)
        
        return {
            'form_type': form_type,
            'confidence': avg_confidence,
            'fields': fields,
            'structure': structure,
            'field_count': len(fields),
            'has_required_fields': any(
                any(v.get('is_required', False) for v in field['validations'])
                for field in fields
            ),
            'metadata': {
                'extraction_method': 'knowledge_first',
                'patterns_matched': len(identified_fields)
            }
        }
    
    def _extract_field_label(self, text: str) -> str:
        """Extract clean label from field text."""
        # Remove fill lines
        text = re.sub(self.field_indicators['patterns']['fill_line'], '', text)
        
        # Extract label before colon
        if ':' in text:
            label = text.split(':')[0].strip()
        else:
            # Take first line or first few words
            lines = text.strip().split('\n')
            label = lines[0] if lines else text
            words = label.split()
            if len(words) > 5:
                label = ' '.join(words[:5]) + '...'
        
        return label.strip()
    
    def _extract_checkbox_options(self, text: str) -> List[str]:
        """Extract checkbox options from text."""
        options = []
        
        # Split by checkboxes
        parts = re.split(self.field_indicators['patterns']['checkbox'], text)
        
        for part in parts[1:]:  # Skip text before first checkbox
            option = part.strip()
            if option:
                # Take text until next checkbox or newline
                option = option.split('\n')[0].strip()
                if option:
                    options.append(option)
        
        return options
    
    def _detect_date_format(self, text: str) -> str:
        """Detect date format from text."""
        if 'MM/DD/YYYY' in text or 'mm/dd/yyyy' in text:
            return 'MM/DD/YYYY'
        elif 'DD/MM/YYYY' in text or 'dd/mm/yyyy' in text:
            return 'DD/MM/YYYY'
        elif 'YYYY-MM-DD' in text or 'yyyy-mm-dd' in text:
            return 'YYYY-MM-DD'
        else:
            return 'unknown'
    
    def _determine_form_type(self, fields: List[Dict[str, Any]], structure: Dict[str, Any]) -> str:
        """Determine the type of form based on fields."""
        field_labels = [f['label'].lower() for f in fields]
        field_types = [f['type'] for f in fields]
        
        # Check for specific form types
        if any('tax' in label for label in field_labels):
            return 'tax_form'
        elif any('medical' in label or 'patient' in label for label in field_labels):
            return 'medical_form'
        elif any('application' in label for label in field_labels):
            return 'application_form'
        elif any('survey' in label or 'feedback' in label for label in field_labels):
            return 'survey_form'
        elif 'signature' in field_types and any('agreement' in label or 'consent' in label for label in field_labels):
            return 'consent_form'
        elif any('invoice' in label or 'payment' in label for label in field_labels):
            return 'invoice_form'
        else:
            return 'general_form'
    
    def _store_form_pattern(self, form_result: Dict[str, Any]) -> None:
        """Store successful form pattern for future use."""
        pattern = {
            "object_type": "pdf_form",
            "form_type": form_result['form_type'],
            "field_count": form_result['field_count'],
            "field_labels": [f['label'] for f in form_result['fields']],
            "field_structure": [
                {
                    "label": f['label'],
                    "field_type": f['type'],
                    "attributes": f.get('attributes', {})
                }
                for f in form_result['fields']
            ],
            "has_checkboxes": any(f['type'] == 'checkbox' for f in form_result['fields']),
            "has_fill_lines": any(f['type'] in ['text_input', 'multi_line_text'] for f in form_result['fields']),
            "has_signature": any(f['type'] == 'signature' for f in form_result['fields']),
            "has_date_fields": any(f['type'] == 'date_field' for f in form_result['fields']),
            "validation_rules": {},
            "confidence": form_result['confidence']
        }
        
        # Add validation rules
        for field in form_result['fields']:
            if field['validations']:
                pattern['validation_rules'][field['type']] = field['validations']
        
        # Store in ArangoDB
        result = self._call_arango("insert", collection="pdf_forms", document=json.dumps(pattern))
        
        if "error" not in result:
            logger.info(f"Stored form pattern: {form_result['form_type']}")


# Usage functions for testing
def working_usage():
    """Demonstrate working usage of form processor."""
    processor = FormProcessor()
    
    # Test form blocks
    test_blocks = [
        {
            "text": "PATIENT INFORMATION FORM",
            "bbox": [100, 50, 400, 80]
        },
        {
            "text": "Name: _________________________________",
            "bbox": [100, 100, 400, 120]
        },
        {
            "text": "Date of Birth: ____/____/______",
            "bbox": [100, 130, 300, 150]
        },
        {
            "text": "☐ Male ☐ Female ☐ Other",
            "bbox": [100, 160, 300, 180]
        },
        {
            "text": "Email: _________________________________",
            "bbox": [100, 190, 400, 210]
        },
        {
            "text": "Signature: _______________________________ Date: __________",
            "bbox": [100, 250, 500, 270]
        }
    ]
    
    context = {
        "page_number": 0,
        "document_type": "medical"
    }
    
    # Process the form
    result = processor.process_form(test_blocks, context)
    
    print(f"Form type: {result['form_type']}")
    print(f"Confidence: {result['confidence']:.2f}")
    print(f"Fields found: {result['field_count']}")
    
    for field in result['fields']:
        print(f"\n- {field['label']}")
        print(f"  Type: {field['type']}")
        print(f"  Confidence: {field['confidence']:.2f}")
    
    return True


def debug_function():
    """Debug function for testing various form types."""
    processor = FormProcessor()
    
    test_cases = [
        {
            "name": "Tax form",
            "blocks": [
                {"text": "FORM 1040 - TAX RETURN", "bbox": [100, 50, 400, 80]},
                {"text": "First Name: _____________ Last Name: _____________", "bbox": [100, 100, 500, 120]},
                {"text": "Social Security Number: ___-__-____", "bbox": [100, 130, 350, 150]},
                {"text": "Filing Status: ☐ Single ☐ Married ☐ Head of Household", "bbox": [100, 160, 500, 180]}
            ]
        },
        {
            "name": "Survey form",
            "blocks": [
                {"text": "CUSTOMER SATISFACTION SURVEY", "bbox": [100, 50, 400, 80]},
                {"text": "How satisfied are you with our service?", "bbox": [100, 100, 400, 120]},
                {"text": "☐ Very Satisfied ☐ Satisfied ☐ Neutral ☐ Dissatisfied", "bbox": [100, 130, 500, 150]},
                {"text": "Comments:\n_________________________________________\n_________________________________________", "bbox": [100, 170, 500, 220]}
            ]
        }
    ]
    
    for test in test_cases:
        print(f"\n=== Testing: {test['name']} ===")
        result = processor.process_form(test['blocks'], {"page_number": 0})
        print(f"Type: {result['form_type']} (confidence: {result['confidence']:.2f})")
        print(f"Structure: {len(result['structure']['sections'])} sections")
        print(f"Fields: {[f['type'] for f in result['fields']]}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "working"
    
    if mode == "debug":
        debug_function()
    elif len(sys.argv) == 3 and sys.argv[1] == "process_form":
        # Direct execution mode
        data = json.loads(sys.argv[2])
        processor = FormProcessor()
        result = processor.process_form(data['blocks'], data.get('context', {}))
        print(json.dumps(result))
    else:
        working_usage()