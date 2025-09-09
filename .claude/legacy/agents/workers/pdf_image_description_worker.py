#!/usr/bin/env python3
"""
Image Description Worker - Knowledge-First Sub-Agent

This sub-agent generates descriptions for images, figures, charts, and diagrams
using historical patterns from ArangoDB. It uses CLIP embeddings to find
visually similar images and applies their descriptions as templates.

Key Features:
- Direct ArangoDB queries for image patterns
- CLIP embedding similarity search
- Chart/diagram type classification
- Caption extraction and enhancement
- Multi-modal understanding (image + text)
- Domain-specific descriptions

Usage:
    # Direct execution
    python image_description_worker.py describe_image '{"image_data": {...}, "context": {...}}'
    
    # From processor
    result = ImageDescriptionWorker().describe_image(image_data, context)
"""

import json
import sys
import subprocess
import re
import os
from typing import Dict, Any, List, Optional
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


class ImageDescriptionWorker:
    """Knowledge-first image description using ArangoDB patterns."""
    
    def __init__(self):
        """Initialize the image description worker."""
        self.image_types = [
            "photograph",
            "line_chart",
            "bar_chart",
            "pie_chart",
            "scatter_plot",
            "flowchart",
            "diagram",
            "schematic",
            "map",
            "infographic",
            "table_image",
            "equation_image",
            "logo",
            "icon"
        ]
        
        self.domain_indicators = {
            'scientific': ['axis', 'data', 'experiment', 'measurement', 'variable'],
            'medical': ['anatomy', 'patient', 'diagnosis', 'treatment', 'scan'],
            'technical': ['component', 'system', 'process', 'architecture', 'flow'],
            'business': ['revenue', 'profit', 'market', 'growth', 'performance'],
            'educational': ['example', 'illustration', 'concept', 'learning', 'step']
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
    
    def describe_image(self, image_data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate image description using knowledge-first approach.
        
        Args:
            image_data: Image information including CLIP embedding, caption, bbox
            context: Context including surrounding text, document type
            
        Returns:
            Dictionary with description and metadata
        """
        logger.info("Generating image description using knowledge-first approach")
        
        # Step 1: Find visually similar images
        similar_images = self._query_similar_images(image_data)
        
        # Step 2: Classify image type
        image_type = self._classify_image_type(image_data, similar_images, context)
        
        # Step 3: Extract and enhance caption
        caption_info = self._process_caption(image_data, context)
        
        # Step 4: Query domain-specific patterns
        domain_patterns = self._query_domain_patterns(image_type, caption_info, context)
        
        # Step 5: Generate description from patterns
        description = self._generate_description(
            image_data, similar_images, image_type, caption_info, domain_patterns
        )
        
        # Step 6: Validate and refine
        refined_description = self._refine_description(description, context)
        
        # Step 7: Store successful pattern
        if refined_description['confidence'] > 0.8:
            self._store_description_pattern(image_data, refined_description)
        
        return refined_description
    
    def _query_similar_images(self, image_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Query for visually similar images using CLIP embeddings."""
        embedding = image_data.get('clip_embedding')
        if not embedding:
            logger.warning("No CLIP embedding available for image")
            return []
        
        # Query similar images
        query = """
        FOR img IN pdf_images
          FILTER img.clip_embedding != null
          LET visual_similarity = COSINE_SIMILARITY(@embedding, img.clip_embedding)
          FILTER visual_similarity > 0.7
          SORT visual_similarity DESC
          LIMIT 10
          RETURN {
            image: img,
            similarity: visual_similarity,
            description: img.description,
            image_type: img.image_type,
            domain: img.domain,
            key_elements: img.key_elements,
            caption: img.original_caption
          }
        """
        
        result = self._call_arango(
            "query",
            aql=query,
            bind_vars=json.dumps({"embedding": embedding})
        )
        
        if "error" in result:
            logger.warning(f"Similar image query failed: {result['error']}")
            return []
            
        return result.get('result', [])
    
    def _classify_image_type(self, image_data: Dict[str, Any], similar_images: List[Dict[str, Any]], context: Dict[str, Any]) -> str:
        """Classify the type of image based on patterns and context."""
        # Aggregate votes from similar images
        type_votes = {}
        for img in similar_images[:5]:  # Top 5
            img_type = img.get('image_type', 'unknown')
            similarity = img.get('similarity', 0)
            type_votes[img_type] = type_votes.get(img_type, 0) + similarity
        
        # Check caption for type indicators
        caption = image_data.get('caption', '').lower()
        if caption:
            if 'figure' in caption or 'fig.' in caption:
                type_votes['diagram'] = type_votes.get('diagram', 0) + 0.3
            if 'table' in caption:
                type_votes['table_image'] = type_votes.get('table_image', 0) + 0.5
            if 'chart' in caption or 'graph' in caption:
                type_votes['chart'] = type_votes.get('chart', 0) + 0.4
            if 'equation' in caption or 'formula' in caption:
                type_votes['equation_image'] = type_votes.get('equation_image', 0) + 0.5
        
        # Check surrounding text
        surrounding = context.get('surrounding_text', '').lower()
        if 'shows' in surrounding or 'illustrates' in surrounding:
            type_votes['diagram'] = type_votes.get('diagram', 0) + 0.2
        if 'data' in surrounding or 'results' in surrounding:
            type_votes['chart'] = type_votes.get('chart', 0) + 0.2
        
        # Get best type
        if type_votes:
            best_type = max(type_votes.items(), key=lambda x: x[1])
            if best_type[1] > 0.3:
                return best_type[0]
        
        # Default based on aspect ratio and position
        bbox = image_data.get('bbox', [0, 0, 100, 100])
        aspect_ratio = (bbox[2] - bbox[0]) / max(bbox[3] - bbox[1], 1)
        
        if aspect_ratio > 2:  # Wide image
            return 'table_image'
        elif aspect_ratio < 0.5:  # Tall image
            return 'flowchart'
        else:
            return 'diagram'
    
    def _process_caption(self, image_data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and process image caption."""
        caption = image_data.get('caption', '')
        
        # Check if caption is in surrounding blocks
        if not caption and context.get('surrounding_blocks'):
            for block in context['surrounding_blocks']:
                text = block.get('text', '').strip()
                # Common caption patterns
                if re.match(r'^(Figure|Fig\.|Table|Chart|Diagram)\s+\d+', text, re.IGNORECASE):
                    caption = text
                    break
        
        # Parse caption structure
        caption_parts = {
            'full_text': caption,
            'label': '',
            'number': '',
            'title': '',
            'description': ''
        }
        
        if caption:
            # Extract label and number
            label_match = re.match(r'^(Figure|Fig\.|Table|Chart|Diagram)\s+(\d+[\.\d]*)', caption, re.IGNORECASE)
            if label_match:
                caption_parts['label'] = label_match.group(1)
                caption_parts['number'] = label_match.group(2)
                
                # Extract title and description
                remainder = caption[label_match.end():].strip()
                if ':' in remainder:
                    parts = remainder.split(':', 1)
                    caption_parts['title'] = parts[0].strip()
                    caption_parts['description'] = parts[1].strip()
                elif '.' in remainder:
                    parts = remainder.split('.', 1)
                    caption_parts['title'] = parts[0].strip()
                    if len(parts) > 1:
                        caption_parts['description'] = parts[1].strip()
                else:
                    caption_parts['title'] = remainder
        
        return caption_parts
    
    def _query_domain_patterns(self, image_type: str, caption_info: Dict[str, Any], context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Query for domain-specific description patterns."""
        # Detect domain from caption and context
        all_text = f"{caption_info['full_text']} {context.get('surrounding_text', '')}".lower()
        
        detected_domain = 'general'
        max_score = 0
        
        for domain, indicators in self.domain_indicators.items():
            score = sum(1 for ind in indicators if ind in all_text)
            if score > max_score:
                max_score = score
                detected_domain = domain
        
        # Query domain-specific patterns
        query = """
        FOR pattern IN image_description_patterns
          FILTER pattern.image_type == @image_type OR pattern.image_type == "general"
          FILTER pattern.domain == @domain OR pattern.domain == "general"
          LET relevance = (
            (pattern.image_type == @image_type ? 2 : 1) +
            (pattern.domain == @domain ? 2 : 1) +
            (pattern.has_caption == @has_caption ? 1 : 0)
          ) / 5.0
          FILTER relevance > 0.4
          SORT relevance DESC
          LIMIT 5
          RETURN {
            pattern: pattern,
            relevance: relevance,
            description_template: pattern.template,
            key_elements: pattern.common_elements,
            style_guide: pattern.style
          }
        """
        
        result = self._call_arango(
            "query",
            aql=query,
            bind_vars=json.dumps({
                "image_type": image_type,
                "domain": detected_domain,
                "has_caption": bool(caption_info['full_text'])
            })
        )
        
        if "error" in result:
            logger.warning(f"Domain pattern query failed: {result['error']}")
            return []
            
        return result.get('result', [])
    
    def _generate_description(
        self,
        image_data: Dict[str, Any],
        similar_images: List[Dict[str, Any]],
        image_type: str,
        caption_info: Dict[str, Any],
        domain_patterns: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate description based on patterns and similar images."""
        logger.info(f"Generating description for {image_type}")
        
        # Start with caption if available
        base_description = caption_info['description'] or caption_info['title'] or ""
        
        # Collect key elements from similar images
        key_elements = set()
        description_fragments = []
        
        for img in similar_images[:3]:  # Top 3
            if img.get('key_elements'):
                key_elements.update(img['key_elements'])
            if img.get('description'):
                description_fragments.append({
                    'text': img['description'],
                    'similarity': img['similarity']
                })
        
        # Apply domain patterns
        if domain_patterns:
            best_pattern = domain_patterns[0]
            template = best_pattern.get('description_template', '')
            
            if template and '{' in template:
                # Fill in template
                description = template.format(
                    type=image_type,
                    caption=base_description,
                    elements=', '.join(list(key_elements)[:3]) if key_elements else 'visual elements'
                )
            else:
                description = base_description
        else:
            description = base_description
        
        # Enhance with similar image descriptions
        if not description and description_fragments:
            # Use most similar description as base
            best_fragment = max(description_fragments, key=lambda x: x['similarity'])
            description = best_fragment['text']
        
        # Build metadata
        confidence = 0.5
        if similar_images:
            # Higher confidence with more similar images
            avg_similarity = sum(img['similarity'] for img in similar_images[:3]) / min(3, len(similar_images))
            confidence = avg_similarity
        
        if caption_info['full_text']:
            confidence = min(confidence + 0.2, 1.0)
        
        return {
            'description': description or f"A {image_type} showing {', '.join(list(key_elements)[:3]) if key_elements else 'content'}",
            'image_type': image_type,
            'confidence': confidence,
            'key_elements': list(key_elements),
            'caption': caption_info,
            'source_method': 'pattern_based' if domain_patterns else 'similarity_based'
        }
    
    def _refine_description(self, description: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Refine and validate the generated description."""
        refined = description.copy()
        
        # Ensure description is not empty
        if not refined['description'] or refined['description'] == 'A  showing ':
            refined['description'] = f"An image of type {refined['image_type']}"
            refined['confidence'] *= 0.5
        
        # Add context if description is too generic
        if len(refined['description']) < 30 and context.get('surrounding_text'):
            # Extract relevant context
            surrounding = context['surrounding_text'][:100]
            if 'shows' in surrounding.lower():
                shows_idx = surrounding.lower().index('shows')
                context_fragment = surrounding[shows_idx:shows_idx+50].strip()
                refined['description'] = f"{refined['description']}. The context indicates it {context_fragment}"
        
        # Ensure proper sentence structure
        desc = refined['description']
        if desc and not desc.endswith('.'):
            desc += '.'
        if desc and desc[0].islower():
            desc = desc[0].upper() + desc[1:]
        refined['description'] = desc
        
        # Add accessibility note for complex images
        if refined['image_type'] in ['flowchart', 'diagram', 'schematic']:
            refined['accessibility_note'] = "Complex visual that may require detailed text description for full accessibility"
        
        return refined
    
    def _store_description_pattern(self, image_data: Dict[str, Any], description_result: Dict[str, Any]) -> None:
        """Store successful image description for future use."""
        pattern = {
            "object_type": "pdf_image",
            "clip_embedding": image_data.get('clip_embedding'),
            "description": description_result['description'],
            "image_type": description_result['image_type'],
            "domain": self._detect_domain(description_result['description']),
            "key_elements": description_result.get('key_elements', []),
            "original_caption": description_result['caption']['full_text'],
            "confidence": description_result['confidence'],
            "bbox": image_data.get('bbox'),
            "has_caption": bool(description_result['caption']['full_text'])
        }
        
        # Store in ArangoDB
        result = self._call_arango("insert", collection="pdf_images", document=json.dumps(pattern))
        
        if "error" not in result:
            logger.info(f"Stored image description pattern: {description_result['image_type']}")
    
    def _detect_domain(self, text: str) -> str:
        """Detect domain from text content."""
        text_lower = text.lower()
        
        domain_scores = {}
        for domain, indicators in self.domain_indicators.items():
            score = sum(1 for ind in indicators if ind in text_lower)
            if score > 0:
                domain_scores[domain] = score
        
        if domain_scores:
            return max(domain_scores.items(), key=lambda x: x[1])[0]
        
        return 'general'


# Usage functions for testing
def working_usage():
    """Demonstrate working usage of image description worker."""
    worker = ImageDescriptionWorker()
    
    # Test image data
    test_image = {
        "clip_embedding": [0.1] * 512,  # Dummy embedding
        "caption": "Figure 3: System architecture showing data flow",
        "bbox": [100, 200, 500, 400]
    }
    
    context = {
        "surrounding_text": "The diagram illustrates how data flows through the processing pipeline.",
        "page_number": 5
    }
    
    # Generate description
    result = worker.describe_image(test_image, context)
    
    print(f"Description: {result['description']}")
    print(f"Image type: {result['image_type']}")
    print(f"Confidence: {result['confidence']:.2f}")
    print(f"Key elements: {result.get('key_elements', [])}")
    
    return True


def debug_function():
    """Debug function for testing various image types."""
    worker = ImageDescriptionWorker()
    
    test_cases = [
        {
            "name": "Bar chart",
            "image": {
                "caption": "Figure 1: Annual revenue by region (2020-2023)",
                "bbox": [100, 100, 500, 300]
            },
            "context": {
                "surrounding_text": "Sales data shows significant growth in the Asian market."
            }
        },
        {
            "name": "Medical diagram",
            "image": {
                "caption": "Anatomical illustration of the human heart",
                "bbox": [150, 150, 450, 450]
            },
            "context": {
                "surrounding_text": "The cardiac anatomy reveals four chambers with specialized valves."
            }
        },
        {
            "name": "Flowchart",
            "image": {
                "caption": "",  # No caption
                "bbox": [100, 100, 600, 800]
            },
            "context": {
                "surrounding_text": "The process flow shows decision points and parallel workflows."
            }
        }
    ]
    
    for test in test_cases:
        print(f"\n=== Testing: {test['name']} ===")
        # Add dummy CLIP embedding for testing
        test['image']['clip_embedding'] = [0.1] * 512
        
        result = worker.describe_image(test['image'], test['context'])
        print(f"Type: {result['image_type']}")
        print(f"Description: {result['description']}")
        print(f"Method: {result.get('source_method', 'unknown')}")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "working"
    
    if mode == "debug":
        debug_function()
    elif len(sys.argv) == 3 and sys.argv[1] == "describe_image":
        # Direct execution mode
        data = json.loads(sys.argv[2])
        worker = ImageDescriptionWorker()
        result = worker.describe_image(data['image_data'], data.get('context', {}))
        print(json.dumps(result))
    else:
        working_usage()