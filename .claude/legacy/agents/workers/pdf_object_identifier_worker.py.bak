#!/usr/bin/env python3
"""
PDF Object Identifier Worker - Knowledge-First Sub-Agent

This sub-agent identifies and classifies PDF objects (tables, figures, equations, forms)
using historical patterns from ArangoDB. It queries the knowledge base to make
evidence-based classification decisions.

Key Features:
- Direct ArangoDB queries (no generic prompts)
- CLIP embeddings for visual similarity
- BM25 text search for content patterns
- Learned rules from annotations
- Confidence scoring based on historical accuracy

Usage:
    # Direct execution
    python pdf_object_identifier_worker.py identify_object '{"block": {...}, "context": {...}}'
    
    # From processor
    result = PDFObjectIdentifier().identify_object(block, context)
"""

import json
import sys
import os
from typing import Dict, Any, List
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv, find_dotenv
from arango import ArangoClient
from arango.exceptions import ArangoError

# Configure logging
logger.remove()
logger.add(sys.stderr, level="INFO")

# Load environment variables
load_dotenv(find_dotenv())


class PDFObjectIdentifier:
    """Knowledge-first PDF object identification using ArangoDB patterns."""
    
    def __init__(self):
        """Initialize the PDF object identifier."""
        self.object_types = [
            "table",
            "figure", 
            "equation",
            "form",
            "chart",
            "diagram",
            "code_block",
            "footnote",
            "header",
            "footer",
            "page_number",
            "caption"
        ]
        
        # Initialize ArangoDB connection
        self._init_db()
        
    def _init_db(self):
        """Initialize ArangoDB connection."""
        try:
            # Connection parameters from environment
            host = os.getenv("ARANGO_HOST", "http://localhost:8529")
            username = os.getenv("ARANGO_USER", "root")
            password = os.getenv("ARANGO_PASSWORD", "")
            database = os.getenv("ARANGO_DATABASE", "extractor_kb")
            
            # Create client
            self.client = ArangoClient(hosts=host)
            
            # Connect to database
            self.db = self.client.db(database, username=username, password=password)
            
            # Ensure collections exist
            self._ensure_collections()
            
            logger.info(f"Connected to ArangoDB at {host}/{database}")
            
        except Exception as e:
            logger.error(f"Failed to connect to ArangoDB: {e}")
            self.db = None
            
    def _ensure_collections(self):
        """Ensure required collections exist."""
        collections = [
            "pdf_objects",
            "block_classifications", 
            "annotation_learned_rules",
            "pdf_equations",
            "pdf_forms",
            "pdf_images"
        ]
        
        for col_name in collections:
            if not self.db.has_collection(col_name):
                self.db.create_collection(col_name)
                logger.info(f"Created collection: {col_name}")
    
    def identify_object(self, block: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Identify PDF object type using knowledge-first approach.
        
        Args:
            block: Block data including text, bbox, visual features
            context: Context including surrounding blocks, page info
            
        Returns:
            Dictionary with identification results and confidence
        """
        logger.info(f"Identifying object: {block.get('block_type', 'unknown')}")
        
        if not self.db:
            logger.warning("No database connection, returning default classification")
            return {
                "identified_type": "unknown",
                "confidence": 0.0,
                "type_scores": {},
                "evidence": [],
                "reasoning": "No database connection available",
                "requires_specialized_processor": False
            }
        
        # Step 1: Query similar blocks by text content
        text_patterns = self._query_text_patterns(block)
        
        # Step 2: Query visual similarity if CLIP embeddings available
        visual_patterns = []
        if block.get('clip_embedding'):
            visual_patterns = self._query_visual_patterns(block)
        
        # Step 3: Query structural patterns (bbox, position, size)
        structural_patterns = self._query_structural_patterns(block, context)
        
        # Step 4: Check annotation-learned rules
        learned_rules = self._query_learned_rules(block)
        
        # Step 5: Combine evidence and make decision
        decision = self._make_identification_decision(
            block, text_patterns, visual_patterns, structural_patterns, learned_rules
        )
        
        # Step 6: Store decision for future learning
        if decision['confidence'] > 0.8:
            self._store_identification_pattern(block, decision)
        
        return decision
    
    def _query_text_patterns(self, block: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Query similar blocks by text content using BM25."""
        text = block.get('text', '').strip()
        if not text:
            return []
        
        try:
            # Query for similar text patterns
            query = """
            FOR doc IN pdf_objects
              FILTER doc.object_type == 'block_classification'
              LET text_similarity = BM25(doc.block_text, @text)
              FILTER text_similarity > 0.3
              SORT text_similarity DESC
              LIMIT 10
              RETURN {
                pattern: doc,
                similarity: text_similarity,
                classified_type: doc.classified_type,
                confidence: doc.classification_confidence,
                indicators: doc.text_indicators
              }
            """
            
            cursor = self.db.aql.execute(query, bind_vars={"text": text})
            return list(cursor)
            
        except ArangoError as e:
            logger.warning(f"Text pattern query failed: {e}")
            return []
    
    def _query_visual_patterns(self, block: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Query visually similar blocks using CLIP embeddings."""
        embedding = block.get('clip_embedding')
        if not embedding:
            return []
        
        try:
            # Query for visual similarity
            query = """
            FOR doc IN pdf_objects
              FILTER doc.object_type == 'block_classification'
              FILTER doc.clip_embedding != null
              LET visual_similarity = COSINE_SIMILARITY(@embedding, doc.clip_embedding)
              FILTER visual_similarity > 0.7
              SORT visual_similarity DESC
              LIMIT 10
              RETURN {
                pattern: doc,
                similarity: visual_similarity,
                classified_type: doc.classified_type,
                visual_features: doc.visual_features
              }
            """
            
            cursor = self.db.aql.execute(query, bind_vars={"embedding": embedding})
            return list(cursor)
            
        except ArangoError as e:
            logger.warning(f"Visual pattern query failed: {e}")
            return []
    
    def _query_structural_patterns(self, block: Dict[str, Any], context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Query blocks with similar structural properties."""
        bbox = block.get('bbox', [0, 0, 100, 100])
        page_height = context.get('page_height', 792)  # Default US Letter
        
        # Calculate relative position and size
        rel_y = bbox[1] / page_height
        rel_height = (bbox[3] - bbox[1]) / page_height
        aspect_ratio = (bbox[2] - bbox[0]) / max(bbox[3] - bbox[1], 1)
        
        try:
            # Query for structural patterns
            query = """
            FOR doc IN pdf_objects
              FILTER doc.object_type == 'block_structure_pattern'
              FILTER ABS(doc.relative_y - @rel_y) < 0.1
              FILTER ABS(doc.relative_height - @rel_height) < 0.1
              FILTER ABS(doc.aspect_ratio - @aspect_ratio) < 0.5
              RETURN {
                pattern: doc,
                classified_type: doc.typical_type,
                position_indicator: doc.position_meaning,
                size_indicator: doc.size_meaning
              }
            """
            
            cursor = self.db.aql.execute(
                query,
                bind_vars={
                    "rel_y": rel_y,
                    "rel_height": rel_height,
                    "aspect_ratio": aspect_ratio
                }
            )
            return list(cursor)
            
        except ArangoError as e:
            logger.warning(f"Structural pattern query failed: {e}")
            return []
    
    def _query_learned_rules(self, block: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Query rules learned from annotations."""
        # Build feature vector for rule matching
        features: Dict[str, Any] = {
            "has_numbers": bool(any(c.isdigit() for c in block.get('text', ''))),
            "has_table_keywords": any(kw in block.get('text', '').lower() 
                                    for kw in ['table', 'figure', 'equation', 'chart']),
            "text_length": len(block.get('text', '')),
            "line_count": block.get('text', '').count('\n') + 1,
            "has_special_chars": bool(any(c in block.get('text', '') 
                                        for c in ['=', '+', '-', '*', '/', '∑', '∫']))
        }
        
        try:
            # Query learned classification rules
            query = """
            FOR rule IN annotation_learned_rules
              FILTER rule.rule_type == 'object_classification'
              LET feature_match = (
                (@has_numbers == rule.features.has_numbers ? 1 : 0) +
                (@has_table_keywords == rule.features.has_table_keywords ? 1 : 0) +
                (ABS(@text_length - rule.features.text_length) < 50 ? 1 : 0) +
                (ABS(@line_count - rule.features.line_count) < 3 ? 1 : 0) +
                (@has_special_chars == rule.features.has_special_chars ? 1 : 0)
              ) / 5.0
              FILTER feature_match > 0.6
              SORT feature_match DESC
              LIMIT 5
              RETURN {
                rule: rule,
                match_score: feature_match,
                classified_type: rule.classification,
                confidence: rule.rule_confidence
              }
            """
            
            cursor = self.db.aql.execute(query, bind_vars=features)
            return list(cursor)
            
        except ArangoError as e:
            logger.warning(f"Learned rules query failed: {e}")
            return []
    
    def _make_identification_decision(
        self,
        block: Dict[str, Any],
        text_patterns: List[Dict[str, Any]],
        visual_patterns: List[Dict[str, Any]], 
        structural_patterns: List[Dict[str, Any]],
        learned_rules: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Combine evidence from all sources to make classification decision."""
        
        # Aggregate votes for each object type
        type_scores = {obj_type: 0.0 for obj_type in self.object_types}
        evidence: List[Dict[str, Any]] = []
        
        # Weight text pattern evidence
        for pattern in text_patterns[:5]:  # Top 5
            obj_type = pattern.get('classified_type')
            if obj_type in type_scores:
                score = pattern.get('similarity', 0) * pattern.get('confidence', 1.0)
                type_scores[obj_type] += score * 0.3  # 30% weight
                evidence.append({
                    "source": "text_pattern",
                    "type": obj_type,
                    "score": score,
                    "pattern": pattern.get('pattern', {}).get('_id')
                })
        
        # Weight visual pattern evidence (highest weight for visual similarity)
        for pattern in visual_patterns[:3]:  # Top 3
            obj_type = pattern.get('classified_type')
            if obj_type in type_scores:
                score = pattern.get('similarity', 0)
                type_scores[obj_type] += score * 0.4  # 40% weight
                evidence.append({
                    "source": "visual_pattern",
                    "type": obj_type,
                    "score": score,
                    "features": pattern.get('visual_features', [])
                })
        
        # Weight structural pattern evidence
        for pattern in structural_patterns:
            obj_type = pattern.get('classified_type')
            if obj_type in type_scores:
                type_scores[obj_type] += 0.15  # 15% weight
                evidence.append({
                    "source": "structural_pattern",
                    "type": obj_type,
                    "indicator": pattern.get('position_indicator')
                })
        
        # Weight learned rules
        for rule in learned_rules[:3]:  # Top 3
            obj_type = rule.get('classified_type')
            if obj_type in type_scores:
                score = rule.get('match_score', 0) * rule.get('confidence', 1.0)
                type_scores[obj_type] += score * 0.15  # 15% weight
                evidence.append({
                    "source": "learned_rule",
                    "type": obj_type,
                    "score": score,
                    "rule": rule.get('rule', {}).get('_id')
                })
        
        # Find best classification
        best_type = max(type_scores.items(), key=lambda x: x[1])
        identified_type = best_type[0] if best_type[1] > 0.3 else "unknown"
        confidence = min(best_type[1], 1.0)
        
        # Apply heuristic adjustments
        if identified_type == "table" and "table" in block.get('text', '').lower():
            confidence = min(confidence * 1.2, 1.0)
        elif identified_type == "figure" and "figure" in block.get('text', '').lower():
            confidence = min(confidence * 1.2, 1.0)
        
        return {
            "identified_type": identified_type,
            "confidence": confidence,
            "type_scores": type_scores,
            "evidence": evidence,
            "reasoning": self._generate_reasoning(identified_type, evidence),
            "requires_specialized_processor": identified_type in ["table", "equation", "form", "chart"]
        }
    
    def _generate_reasoning(self, identified_type: str, evidence: List[Dict[str, Any]]) -> str:
        """Generate human-readable reasoning for the classification."""
        if not evidence:
            return "No historical evidence found for classification"
        
        reasoning_parts: List[str] = []
        
        # Group evidence by source
        by_source: Dict[str, List[Dict[str, Any]]] = {}
        for e in evidence:
            source = e['source']
            if source not in by_source:
                by_source[source] = []
            by_source[source].append(e)
        
        if 'visual_pattern' in by_source:
            reasoning_parts.append(f"Visual similarity to {len(by_source['visual_pattern'])} known {identified_type}s")
        
        if 'text_pattern' in by_source:
            reasoning_parts.append(f"Text patterns match {len(by_source['text_pattern'])} historical {identified_type}s")
        
        if 'structural_pattern' in by_source:
            indicators = [e.get('indicator') for e in by_source['structural_pattern'] if e.get('indicator')]
            if indicators:
                # Filter out None values and convert to strings
                valid_indicators = [str(ind) for ind in indicators if ind is not None]
                if valid_indicators:
                    reasoning_parts.append(f"Position/size indicates: {', '.join(set(valid_indicators))}")
        
        if 'learned_rule' in by_source:
            reasoning_parts.append(f"Matches {len(by_source['learned_rule'])} learned classification rules")
        
        return "; ".join(reasoning_parts)
    
    def _store_identification_pattern(self, block: Dict[str, Any], decision: Dict[str, Any]) -> None:
        """Store successful identification pattern for future use."""
        if not self.db:
            return
            
        pattern: Dict[str, Any] = {
            "object_type": "block_classification",
            "block_text": block.get('text', ''),
            "block_type": block.get('block_type'),
            "classified_type": decision['identified_type'],
            "classification_confidence": decision['confidence'],
            "text_indicators": self._extract_text_indicators(block),
            "visual_features": block.get('visual_features', []),
            "clip_embedding": block.get('clip_embedding'),
            "bbox": block.get('bbox'),
            "evidence": decision['evidence']
        }
        
        try:
            # Store in ArangoDB
            collection = self.db.collection("pdf_objects")
            collection.insert(pattern)
            logger.info(f"Stored classification pattern: {decision['identified_type']}")
        except ArangoError as e:
            logger.error(f"Failed to store pattern: {e}")
    
    def _extract_text_indicators(self, block: Dict[str, Any]) -> List[str]:
        """Extract text-based indicators for object type."""
        text = block.get('text', '').lower()
        indicators: List[str] = []
        
        # Table indicators
        if any(kw in text for kw in ['table', 'tab.', 'tbl']):
            indicators.append('table_keyword')
        if text.count('|') > 2:
            indicators.append('pipe_delimited')
        if text.count('\t') > 2:
            indicators.append('tab_delimited')
            
        # Figure indicators
        if any(kw in text for kw in ['figure', 'fig.', 'image', 'diagram']):
            indicators.append('figure_keyword')
            
        # Equation indicators
        if any(kw in text for kw in ['equation', 'eq.', 'formula']):
            indicators.append('equation_keyword')
        if any(c in text for c in ['∑', '∫', '∂', '√', '∞']):
            indicators.append('math_symbols')
            
        # Form indicators
        if any(kw in text for kw in ['name:', 'date:', 'signature:', 'address:']):
            indicators.append('form_fields')
        if text.count('_____') > 1:
            indicators.append('fill_lines')
            
        return indicators


# Usage functions for testing
def working_usage():
    """Demonstrate working usage of PDF object identifier."""
    identifier = PDFObjectIdentifier()
    
    # Example block to identify
    test_block: Dict[str, Any] = {
        "block_type": "Unknown",
        "text": "Table 1: Comparison of extraction methods\n| Method | Accuracy | Speed |\n|--------|----------|-------|\n| Marker | 92% | Fast |",
        "bbox": [100, 200, 500, 350],
        "page": 0
    }
    
    context: Dict[str, Any] = {
        "page_height": 792,
        "surrounding_blocks": []
    }
    
    # Identify the object
    result = identifier.identify_object(test_block, context)
    
    print(f"Identified as: {result['identified_type']}")
    print(f"Confidence: {result['confidence']:.2f}")
    print(f"Reasoning: {result['reasoning']}")
    print(f"Requires specialized processor: {result['requires_specialized_processor']}")
    
    return True


def debug_function():
    """Debug function for testing edge cases."""
    identifier = PDFObjectIdentifier()
    
    # Test various block types
    test_cases: List[Dict[str, Any]] = [
        {
            "name": "Equation block",
            "block": {
                "text": "∫₀^∞ e^(-x²) dx = √π/2",
                "bbox": [200, 300, 400, 350]
            }
        },
        {
            "name": "Form block",
            "block": {
                "text": "Name: ________________\nDate: ________________\nSignature: ________________",
                "bbox": [100, 100, 500, 200]
            }
        },
        {
            "name": "Figure caption",
            "block": {
                "text": "Figure 3. System architecture overview showing the knowledge-first approach",
                "bbox": [150, 500, 450, 520]
            }
        }
    ]
    
    for test in test_cases:
        print(f"\n=== Testing: {test['name']} ===")
        result = identifier.identify_object(test['block'], {"page_height": 792})
        print(f"Type: {result['identified_type']} (confidence: {result['confidence']:.2f})")
        print(f"Top scores: {sorted(result['type_scores'].items(), key=lambda x: x[1], reverse=True)[:3]}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "working"
    
    if mode == "debug":
        debug_function()
    elif len(sys.argv) == 3 and sys.argv[1] == "identify_object":
        # Direct execution mode
        data = json.loads(sys.argv[2])
        identifier = PDFObjectIdentifier()
        result = identifier.identify_object(data['block'], data.get('context', {}))
        print(json.dumps(result))
    else:
        working_usage()