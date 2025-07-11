"""
Module: arangodb_validator.py
Description: Validation utilities for ArangoDB documents

External Dependencies:
- re: https://docs.python.org/3/library/re.html
"""

import re
from typing import Dict, Any, List, Optional, Tuple


class ArangoDBDocumentValidator:
    """Validates documents for ArangoDB compliance"""
    
    # ArangoDB constraints
    MAX_ID_LENGTH = 254  # ArangoDB limit
    INVALID_ID_CHARS = re.compile(r'[^a-zA-Z0-9_\-:.]')
    
    @staticmethod
    def validate_document_id(doc_id: str) -> Tuple[bool, Optional[str]]:
        """
        Validate ArangoDB document ID.
        
        Returns:
            (is_valid, error_message)
        """
        if not doc_id:
            return False, "Document ID cannot be empty"
            
        if len(doc_id) > ArangoDBDocumentValidator.MAX_ID_LENGTH:
            return False, f"Document ID exceeds maximum length of {ArangoDBDocumentValidator.MAX_ID_LENGTH}"
            
        if ' ' in doc_id:
            return False, "Document ID cannot contain spaces"
            
        if '/' in doc_id and not re.match(r'^[a-zA-Z0-9_\-]+/[a-zA-Z0-9_\-:.]+$', doc_id):
            return False, "Invalid document ID format with slash"
            
        if ArangoDBDocumentValidator.INVALID_ID_CHARS.search(doc_id.split('/')[-1]):
            return False, "Document ID contains invalid characters"
            
        return True, None
    
    @staticmethod
    def validate_edge_reference(ref: str) -> Tuple[bool, Optional[str]]:
        """
        Validate ArangoDB edge reference (_from or _to).
        
        Returns:
            (is_valid, error_message)
        """
        if not ref:
            return False, "Edge reference cannot be empty"
            
        if '/' not in ref:
            return False, "Edge reference must be in format 'collection/key'"
            
        parts = ref.split('/')
        if len(parts) != 2:
            return False, "Edge reference must have exactly one slash"
            
        collection, key = parts
        if not collection or not key:
            return False, "Collection and key cannot be empty"
            
        return ArangoDBDocumentValidator.validate_document_id(ref)
    
    @staticmethod
    def validate_document(doc: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate a complete ArangoDB document.
        
        Returns:
            (is_valid, list_of_errors)
        """
        errors = []
        
        # Check _id field
        if '_id' in doc:
            is_valid, error = ArangoDBDocumentValidator.validate_document_id(doc['_id'])
            if not is_valid:
                errors.append(f"_id: {error}")
        
        # Check _from field (for edges)
        if '_from' in doc:
            is_valid, error = ArangoDBDocumentValidator.validate_edge_reference(doc['_from'])
            if not is_valid:
                errors.append(f"_from: {error}")
                
        # Check _to field (for edges)
        if '_to' in doc:
            is_valid, error = ArangoDBDocumentValidator.validate_edge_reference(doc['_to'])
            if not is_valid:
                errors.append(f"_to: {error}")
                
        return len(errors) == 0, errors


if __name__ == "__main__":
    """Validation test"""
    validator = ArangoDBDocumentValidator()
    
    # Test cases
    test_cases = [
        {'_id': 'docs/valid_id_123'},
        {'_id': 'docs/has spaces'},  # Should fail
        {'_id': 'docs/has/slash'},  # Should fail
        {'_id': ''},  # Should fail
        {'_id': 'docs/' + 'A' * 250},  # Should fail - too long
        {'_from': 'invalid'},  # Should fail
        {'_from': 'users/123', '_to': 'posts/456'},  # Should pass
    ]
    
    for doc in test_cases:
        is_valid, errors = validator.validate_document(doc)
        if is_valid:
            print(f"✅ Valid: {doc}")
        else:
            print(f"❌ Invalid: {doc} - Errors: {errors}")
            
    print("\n✅ ArangoDB validator created successfully!")