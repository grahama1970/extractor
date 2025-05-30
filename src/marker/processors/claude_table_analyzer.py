"""
Claude-powered table analyzer for complex table understanding.
Goes beyond simple extraction to understand relationships and meaning.
"""

import json
from typing import Dict, List, Optional, Tuple, Any
import base64
from io import BytesIO
from PIL import Image
import numpy as np


class ClaudeTableAnalyzer:
    """
    Advanced table analyzer using Claude for complex table understanding.
    """
    
    def __init__(self, claude_service, surya_table_model=None):
        self.claude = claude_service
        self.surya_table = surya_table_model
        
    def analyze_table(self, table_image: np.ndarray, 
                     context: Optional[str] = None,
                     page_num: Optional[int] = None) -> Dict:
        """
        Comprehensive table analysis with Claude.
        """
        # Step 1: Get basic structure from Surya (if available)
        surya_result = None
        if self.surya_table:
            surya_result = self._get_surya_structure(table_image)
        
        # Step 2: Determine complexity
        complexity = self._assess_complexity(table_image, surya_result)
        
        # Step 3: Route based on complexity
        if complexity['score'] < 0.3:
            # Simple table - Surya is sufficient
            return self._format_simple_result(surya_result)
        else:
            # Complex table - use Claude
            return self._analyze_with_claude(
                table_image, 
                surya_result, 
                context,
                complexity,
                page_num
            )
    
    def _assess_complexity(self, image: np.ndarray, 
                          surya_result: Optional[Dict]) -> Dict:
        """
        Assess table complexity to determine processing needs.
        """
        complexity_score = 0.0
        factors = []
        
        # Image-based complexity
        height, width = image.shape[:2]
        
        # Large tables are often complex
        if height > 500 or width > 800:
            complexity_score += 0.2
            factors.append("large_size")
        
        # Dense tables with many cells
        if surya_result:
            cell_count = len(surya_result.get('cells', []))
            if cell_count > 30:
                complexity_score += 0.2
                factors.append("high_cell_count")
            
            # Merged cells indicate complexity
            if any(cell.get('rowspan', 1) > 1 or 
                   cell.get('colspan', 1) > 1 
                   for cell in surya_result.get('cells', [])):
                complexity_score += 0.3
                factors.append("merged_cells")
        
        # Visual complexity indicators
        if self._has_nested_structure(image):
            complexity_score += 0.3
            factors.append("nested_structure")
        
        return {
            'score': min(complexity_score, 1.0),
            'factors': factors,
            'needs_claude': complexity_score > 0.3
        }
    
    def _has_nested_structure(self, image: np.ndarray) -> bool:
        """
        Detect nested table structures using image analysis.
        """
        # Simplified heuristic - in practice would use computer vision
        # Check for multiple levels of borders/lines
        return False  # Placeholder
    
    def _analyze_with_claude(self, table_image: np.ndarray,
                           surya_result: Optional[Dict],
                           context: Optional[str],
                           complexity: Dict,
                           page_num: Optional[int]) -> Dict:
        """
        Comprehensive table analysis using Claude.
        """
        # Prepare image
        image_b64 = self._encode_image(table_image)
        
        # Build sophisticated prompt
        prompt = self._build_analysis_prompt(
            surya_result, 
            context, 
            complexity,
            page_num
        )
        
        # Call Claude with structured output
        response = self.claude.process(
            prompt=prompt,
            images=[image_b64],
            temperature=0.1,
            max_tokens=2000
        )
        
        # Parse and enhance result
        result = self._parse_claude_response(response)
        
        # Add metadata
        result['complexity'] = complexity
        result['processor'] = 'claude_advanced'
        
        return result
    
    def _build_analysis_prompt(self, surya_result: Optional[Dict],
                             context: Optional[str],
                             complexity: Dict,
                             page_num: Optional[int]) -> str:
        """
        Build comprehensive prompt for Claude table analysis.
        """
        prompt = """You are analyzing a table from a document. Please provide a comprehensive analysis.

"""
        
        if surya_result:
            prompt += f"""Initial OCR extraction:
```json
{json.dumps(surya_result, indent=2)}
```

"""
        
        if context:
            prompt += f"Surrounding context: {context}\n\n"
        
        if page_num is not None:
            prompt += f"This table appears on page {page_num}.\n\n"
        
        prompt += f"""Complexity factors detected: {', '.join(complexity['factors'])}

Please analyze this table and provide:

1. **Structure Analysis**:
   - Identify all headers (row and column headers)
   - Detect merged cells and their spans
   - Identify the table's overall structure type

2. **Content Understanding**:
   - What type of data does this table contain?
   - What relationships exist between columns?
   - Are there any calculated fields or totals?

3. **Data Extraction**:
   - Extract all data preserving relationships
   - Handle merged cells appropriately
   - Maintain hierarchical relationships if present

4. **Semantic Analysis**:
   - What is the purpose of this table?
   - What key insights does it provide?
   - Are there any data quality issues?

5. **Structured Output**:
   Provide the extracted data in this JSON format:

```json
{
  "title": "table title if identifiable",
  "type": "financial|comparison|statistical|list|other",
  "headers": {
    "column": ["col1", "col2", ...],
    "row": ["row1", "row2", ...] 
  },
  "data": [
    ["cell1", "cell2", ...],
    ...
  ],
  "merged_cells": [
    {"row": 0, "col": 0, "rowspan": 2, "colspan": 1, "value": "..."}
  ],
  "relationships": [
    {"type": "calculation", "description": "Column C = A + B"}
  ],
  "insights": [
    "Key insight 1",
    "Key insight 2"
  ],
  "data_quality": {
    "issues": ["any identified issues"],
    "confidence": 0.95
  },
  "metadata": {
    "num_rows": 10,
    "num_cols": 5,
    "has_totals": true,
    "currency": "USD" 
  }
}
```

Be precise and thorough in your extraction."""
        
        return prompt
    
    def _encode_image(self, image: np.ndarray) -> str:
        """
        Encode image to base64 for Claude.
        """
        # Convert numpy array to PIL Image
        if len(image.shape) == 2:
            # Grayscale
            pil_image = Image.fromarray(image, mode='L')
        else:
            # Color
            pil_image = Image.fromarray(image, mode='RGB')
        
        # Encode to base64
        buffer = BytesIO()
        pil_image.save(buffer, format='PNG')
        return base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    def _parse_claude_response(self, response: str) -> Dict:
        """
        Parse Claude's response and extract structured data.
        """
        try:
            # Extract JSON from response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            else:
                # Look for JSON structure
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    raise ValueError("No JSON found in response")
            
            # Parse JSON
            result = json.loads(json_str.strip())
            
            # Validate structure
            required_fields = ['data', 'headers']
            for field in required_fields:
                if field not in result:
                    result[field] = [] if field == 'data' else {}
            
            # Add success flag
            result['success'] = True
            
            return result
            
        except Exception as e:
            # Return error structure
            return {
                'success': False,
                'error': str(e),
                'raw_response': response[:500],
                'data': [],
                'headers': {}
            }
    
    def _format_simple_result(self, surya_result: Dict) -> Dict:
        """
        Format simple Surya result in standard structure.
        """
        return {
            'success': True,
            'processor': 'surya_simple',
            'data': surya_result.get('data', []),
            'headers': surya_result.get('headers', {}),
            'complexity': {'score': 0.2, 'factors': []},
            'confidence': 0.9
        }
    
    def _get_surya_structure(self, image: np.ndarray) -> Dict:
        """
        Get basic structure from Surya table model.
        """
        # In practice, this would call the actual Surya model
        # For demo, return mock structure
        return {
            'cells': [
                {'row': 0, 'col': 0, 'text': 'Header 1'},
                {'row': 0, 'col': 1, 'text': 'Header 2'},
                {'row': 1, 'col': 0, 'text': 'Data 1'},
                {'row': 1, 'col': 1, 'text': 'Data 2'},
            ],
            'num_rows': 2,
            'num_cols': 2
        }


# Specialized table analyzers for different domains
class FinancialTableAnalyzer(ClaudeTableAnalyzer):
    """
    Specialized analyzer for financial tables.
    """
    
    def _build_analysis_prompt(self, *args, **kwargs):
        base_prompt = super()._build_analysis_prompt(*args, **kwargs)
        
        financial_additions = """

Additional financial analysis required:
- Identify currency and units
- Detect financial metrics (revenue, profit, expenses, etc.)
- Identify time periods (quarters, years, etc.)
- Calculate year-over-year changes if applicable
- Identify any financial ratios or KPIs
"""
        
        return base_prompt + financial_additions


class ScientificTableAnalyzer(ClaudeTableAnalyzer):
    """
    Specialized analyzer for scientific tables.
    """
    
    def _build_analysis_prompt(self, *args, **kwargs):
        base_prompt = super()._build_analysis_prompt(*args, **kwargs)
        
        scientific_additions = """

Additional scientific analysis required:
- Identify units of measurement
- Detect experimental conditions
- Identify control vs experimental groups
- Note statistical significance markers (*, †, etc.)
- Extract p-values or confidence intervals if present
- Identify any footnotes explaining methodology
"""
        
        return base_prompt + scientific_additions


# Example usage patterns
TABLE_ROUTING_RULES = {
    'financial_indicators': [
        'revenue', 'profit', 'earnings', 'assets', 'liabilities',
        '$', '€', '£', '¥', 'USD', 'EUR', 'GBP'
    ],
    'scientific_indicators': [
        'p-value', 'n=', '±', 'SD', 'SE', 'CI',
        'control', 'experimental', 'baseline'
    ],
    'complexity_thresholds': {
        'simple': 0.3,      # Use Surya only
        'moderate': 0.6,    # Use Surya + Claude validation  
        'complex': 1.0      # Full Claude analysis
    }
}


if __name__ == "__main__":
    # Examples of when to use Claude for tables
    examples = [
        {
            'description': 'Simple 3x3 table with clear headers',
            'use_claude': False,
            'reason': 'Surya handles simple grid structures well'
        },
        {
            'description': 'Financial statement with merged cells and subtotals',
            'use_claude': True,
            'reason': 'Complex structure and calculations need understanding'
        },
        {
            'description': 'Scientific data table with multiple header rows',
            'use_claude': True,
            'reason': 'Nested headers and scientific notation'
        },
        {
            'description': 'Simple list formatted as a table',
            'use_claude': False,
            'reason': 'Basic structure, no complex relationships'
        },
        {
            'description': 'Pivot table with row and column groupings',
            'use_claude': True,
            'reason': 'Hierarchical structure needs semantic understanding'
        }
    ]
    
    print("Table Processing Decision Guide:")
    print("=" * 60)
    
    for ex in examples:
        print(f"\nTable: {ex['description']}")
        print(f"Use Claude: {'Yes' if ex['use_claude'] else 'No'}")
        print(f"Reason: {ex['reason']}")
    
    print("\n\nClaude Table Analysis Capabilities:")
    print("- Understand merged cells and complex layouts")
    print("- Identify relationships between columns")
    print("- Extract semantic meaning and insights")
    print("- Handle financial and scientific notation")
    print("- Provide structured output with metadata")