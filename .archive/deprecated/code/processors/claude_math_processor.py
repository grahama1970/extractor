"""
Claude-enhanced math processor that improves upon Texify's output.'
Demonstrates when and how to use Claude Code Instance for better math handling.
"""
Module: claude_math_processor.py

import base64
from typing import Dict, List, Optional, Tuple
from extractor.core.schema.blocks.equation import Equation
from extractor.core.schema.blocks.text import TextInlineMath
import numpy as np


class ClaudeMathProcessor:
    """
    Intelligent math processor that routes between Texify and Claude
    based on complexity and quality requirements.
    """
    
    def __init__(self, texify_model, claude_service):
        self.texify = texify_model
        self.claude = claude_service
        
    def process_math_block(self, math_block, context: Optional[str] = None) -> Dict:
        """
        Process a math block with intelligent routing.
        """
        # Step 1: Get initial Texify conversion
        texify_result = self._get_texify_result(math_block)
        
        # Step 2: Analyze complexity
        complexity = self._analyze_complexity(texify_result, math_block)
        
        # Step 3: Route based on complexity
        if complexity['needs_claude']:
            return self._process_with_claude(
                math_block, 
                texify_result, 
                context,
                complexity
            )
        else:
            return {
                'latex': texify_result,
                'processor': 'texify',
                'confidence': complexity['confidence']
            }
    
    def _analyze_complexity(self, latex: str, math_block) -> Dict:
        """
        Determine if Claude processing is needed.
        """
        needs_claude = False
        confidence = 1.0
        reasons = []
        
        # Check for complex patterns that Texify struggles with
        complex_patterns = [
            (r'\\begin{align', 'multi-line alignment'),
            (r'\\begin{cases', 'piecewise functions'),
            (r'\\matrix', 'matrix operations'),
            (r'\\underset', 'complex annotations'),
            (r'\\overset', 'complex annotations'),
            (r'\\sum.*\\sum', 'nested summations'),
            (r'\\int.*\\int', 'multiple integrals'),
        ]
        
        for pattern, reason in complex_patterns:
            if pattern in latex:
                needs_claude = True
                confidence *= 0.8
                reasons.append(reason)
        
        # Check for potential errors
        error_indicators = [
            ('$$', 'incorrect delimiters'),
            ('\\\\\\\\', 'excessive line breaks'),
            ('{{{', 'nested brace errors'),
            ('_^', 'subscript/superscript errors'),
        ]
        
        for indicator, reason in error_indicators:
            if indicator in latex:
                needs_claude = True
                confidence *= 0.7
                reasons.append(reason)
        
        # Check image characteristics
        if hasattr(math_block, 'bbox'):
            bbox = math_block.bbox
            height = bbox.y1 - bbox.y0
            width = bbox.x1 - bbox.x0
            
            # Large equations often need better handling
            if height > 100 or width > 400:
                needs_claude = True
                confidence *= 0.9
                reasons.append('large equation size')
        
        return {
            'needs_claude': needs_claude,
            'confidence': confidence,
            'reasons': reasons,
            'complexity_score': 1.0 - confidence
        }
    
    def _process_with_claude(self, math_block, texify_result: str, 
                           context: Optional[str], complexity: Dict) -> Dict:
        """
        Use Claude to improve math processing.
        """
        # Prepare image for Claude
        image_base64 = self._prepare_image(math_block)
        
        # Build comprehensive prompt
        prompt = self._build_claude_prompt(
            texify_result, 
            context, 
            complexity['reasons']
        )
        
        # Call Claude
        claude_response = self.claude.process(
            prompt=prompt,
            images=[image_base64] if image_base64 else None,
            temperature=0.1,  # Low temperature for consistency
            max_tokens=1000
        )
        
        # Parse and validate response
        result = self._parse_claude_response(claude_response)
        
        # Fallback to Texify if Claude fails
        if not result['success']:
            return {
                'latex': texify_result,
                'processor': 'texify_fallback',
                'confidence': complexity['confidence'] * 0.5,
                'error': result.get('error')
            }
        
        return {
            'latex': result['latex'],
            'processor': 'claude',
            'confidence': result['confidence'],
            'explanation': result.get('explanation'),
            'corrections': result.get('corrections', [])
        }
    
    def _build_claude_prompt(self, texify_latex: str, context: Optional[str], 
                           issues: List[str]) -> str:
        """
        Build an effective prompt for Claude.
        """
        prompt = f"""You are helping convert a mathematical equation image to LaTeX.

Initial Texify conversion:
```latex
{texify_latex}
```

Detected potential issues: {', '.join(issues) if issues else 'None'}

{f'Surrounding context: {context}' if context else ''}

Please:
1. Analyze the equation image carefully
2. Correct any errors in the Texify output
3. Ensure proper LaTeX syntax and formatting
4. For multi-line equations, use appropriate environments (align, gather, etc.)
5. For matrices, use proper matrix environments
6. Preserve the mathematical meaning exactly

Respond in this JSON format:
{{
    "latex": "corrected LaTeX code",
    "confidence": 0.95,
    "corrections": ["list of corrections made"],
    "explanation": "brief explanation of the math if complex"
}}

Important:
- Do NOT include $ or $$ delimiters in the latex field
- Use \\begin{{equation}} or \\begin{{align}} for display math
- Ensure all braces are balanced
- Use standard LaTeX commands only"""

        return prompt
    
    def _prepare_image(self, math_block) -> Optional[str]:
        """
        Extract and encode the math region image.
        """
        if not hasattr(math_block, 'image'):
            return None
            
        try:
            # Get the image array
            image = math_block.image
            
            # Convert to base64
            import io
            from PIL import Image
            
            # Ensure it's a PIL Image
            if isinstance(image, np.ndarray):
                image = Image.fromarray(image)
            
            # Convert to base64
            buffer = io.BytesIO()
            image.save(buffer, format='PNG')
            image_base64 = base64.b64encode(buffer.getvalue()).decode()
            
            return image_base64
            
        except Exception as e:
            print(f"Error preparing image: {e}")
            return None
    
    def _parse_claude_response(self, response: str) -> Dict:
        """
        Parse and validate Claude's response.'
        """
        try:
            import json
            
            # Extract JSON from response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            else:
                # Try to parse the whole response
                json_str = response
            
            result = json.loads(json_str.strip())
            
            # Validate required fields
            if 'latex' not in result:
                return {'success': False, 'error': 'Missing latex field'}
            
            # Set defaults
            result['success'] = True
            result['confidence'] = result.get('confidence', 0.9)
            
            return result
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Failed to parse Claude response: {str(e)}'
            }
    
    def _get_texify_result(self, math_block) -> str:
        """
        Get initial Texify conversion.
        """
        try:
            if hasattr(math_block, 'latex') and math_block.latex:
                return math_block.latex
            
            # Run Texify
            result = self.texify(math_block.image)
            return result
            
        except Exception as e:
            return f"\\text{{Texify error: {str(e)}}}"


# Example usage function
def create_math_processor(texify_model, claude_service):
    """
    Factory function to create a math processor.
    """
    return ClaudeMathProcessor(texify_model, claude_service)


# Complexity thresholds for different math types
MATH_COMPLEXITY_RULES = {
    'inline': {
        'max_length': 50,
        'max_depth': 2,
        'needs_claude': False
    },
    'display_simple': {
        'max_length': 100,
        'max_depth': 3,
        'needs_claude': False
    },
    'display_complex': {
        'max_length': float('inf'),
        'max_depth': float('inf'),
        'needs_claude': True
    },
    'multi_line': {
        'needs_claude': True,
        'preferred_env': 'align'
    },
    'matrix': {
        'needs_claude': True,
        'preferred_env': 'bmatrix'
    },
    'cases': {
        'needs_claude': True,
        'preferred_env': 'cases'
    }
}


if __name__ == "__main__":
    # Example of when to use Claude vs Texify
    examples = [
        {
            'latex': 'x^2 + y^2 = z^2',
            'use_claude': False,
            'reason': 'Simple equation, Texify handles well'
        },
        {
            'latex': '\\begin{align} x &= \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a} \\\\ y &= mx + c \\end{align}',
            'use_claude': True,
            'reason': 'Multi-line alignment needs verification'
        },
        {
            'latex': '\\begin{bmatrix} a & b & c \\\\ d & e & f \\\\ g & h & i \\end{bmatrix}',
            'use_claude': True,
            'reason': 'Matrix formatting often has errors'
        },
        {
            'latex': '\\int_0^\\infty e^{-x^2} dx = \\frac{\\sqrt{\\pi}}{2}',
            'use_claude': False,
            'reason': 'Standard integral, Texify is sufficient'
        },
        {
            'latex': '\\sum_{n=1}^{\\infty} \\sum_{k=1}^{n} \\frac{1}{k \\cdot 2^n}',
            'use_claude': True,
            'reason': 'Nested operations benefit from validation'
        }
    ]
    
    print("Math Processing Decision Guide:")
    print("=" * 60)
    
    for ex in examples:
        print(f"\nLaTeX: {ex['latex'][:50]}...")
        print(f"Use Claude: {'Yes' if ex['use_claude'] else 'No'}")
        print(f"Reason: {ex['reason']}")