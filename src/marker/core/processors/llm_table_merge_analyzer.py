"""
LLM Table Merge Analyzer using Claude Code Instance

This module uses a Claude Code instance to make intelligent decisions about
whether contiguous tables should be merged based on content analysis.
"""

import json
import subprocess
import tempfile
from typing import Dict, List, Optional, Tuple, Any
from loguru import logger

class LLMTableMergeAnalyzer:
    """
    Uses Claude Code instance to analyze table content and determine
    if contiguous tables should be merged.
    """
    
    def __init__(self, claude_path: str = "claude"):
        """
        Initialize the analyzer.
        
        Args:
            claude_path: Path to Claude Code CLI executable
        """
        self.claude_path = claude_path
        
    def should_merge_tables(self, 
                           table1_data: Dict[str, Any], 
                           table2_data: Dict[str, Any],
                           context: Optional[Dict[str, Any]] = None) -> Tuple[bool, float, str]:
        """
        Determine if two contiguous tables should be merged.
        
        Args:
            table1_data: First table's data (CSV, JSON, text)
            table2_data: Second table's data (CSV, JSON, text)
            context: Additional context (surrounding text, document type, etc.)
            
        Returns:
            Tuple of (should_merge, confidence_score, reasoning)
        """
        
        # Prepare the analysis prompt
        analysis_prompt = self._create_analysis_prompt(table1_data, table2_data, context)
        
        # Create temporary file for the prompt
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(analysis_prompt)
            prompt_file = f.name
        
        try:
            # Call Claude Code instance
            result = subprocess.run(
                [self.claude_path, "analyze", prompt_file],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                response = result.stdout.strip()
                return self._parse_claude_response(response)
            else:
                logger.error(f"Claude Code failed: {result.stderr}")
                return False, 0.0, "Analysis failed"
                
        except subprocess.TimeoutExpired:
            logger.error("Claude Code analysis timed out")
            return False, 0.0, "Analysis timed out"
        except Exception as e:
            logger.error(f"Claude Code analysis error: {e}")
            return False, 0.0, f"Analysis error: {e}"
        finally:
            # Clean up temp file
            try:
                import os
                os.unlink(prompt_file)
            except:
                pass
    
    def _create_analysis_prompt(self, 
                               table1_data: Dict[str, Any], 
                               table2_data: Dict[str, Any],
                               context: Optional[Dict[str, Any]] = None) -> str:
        """Create the analysis prompt for Claude."""
        
        prompt = """# Table Merge Analysis Task

You are analyzing two contiguous tables to determine if they should be merged into a single table.

## Table 1 Data:
"""
        
        # Add table 1 information
        if 'csv' in table1_data and table1_data['csv']:
            prompt += f"### CSV Format:\n```csv\n{table1_data['csv']}\n```\n\n"
        
        if 'json_data' in table1_data and table1_data['json_data']:
            prompt += f"### JSON Format:\n```json\n{json.dumps(table1_data['json_data'], indent=2)}\n```\n\n"
        
        if 'text' in table1_data and table1_data['text']:
            prompt += f"### Text Content:\n{table1_data['text']}\n\n"
        
        if 'metadata' in table1_data and table1_data['metadata']:
            prompt += f"### Metadata:\n{json.dumps(table1_data['metadata'], indent=2)}\n\n"
        
        prompt += """## Table 2 Data:
"""
        
        # Add table 2 information
        if 'csv' in table2_data and table2_data['csv']:
            prompt += f"### CSV Format:\n```csv\n{table2_data['csv']}\n```\n\n"
        
        if 'json_data' in table2_data and table2_data['json_data']:
            prompt += f"### JSON Format:\n```json\n{json.dumps(table2_data['json_data'], indent=2)}\n```\n\n"
        
        if 'text' in table2_data and table2_data['text']:
            prompt += f"### Text Content:\n{table2_data['text']}\n\n"
        
        if 'metadata' in table2_data and table2_data['metadata']:
            prompt += f"### Metadata:\n{json.dumps(table2_data['metadata'], indent=2)}\n\n"
        
        # Add context if available
        if context:
            prompt += "## Document Context:\n"
            if 'surrounding_text' in context:
                prompt += f"### Surrounding Text:\n{context['surrounding_text']}\n\n"
            if 'document_type' in context:
                prompt += f"### Document Type: {context['document_type']}\n\n"
            if 'page_info' in context:
                prompt += f"### Page Information: {context['page_info']}\n\n"
        
        prompt += """## Analysis Guidelines:

Consider these factors when deciding whether to merge:

1. **Content Continuity**: Do the tables contain related data that logically belongs together?
2. **Column Structure**: Do they have similar or compatible column structures?
3. **Semantic Relationship**: Are they parts of the same logical table (e.g., split across pages)?
4. **Data Flow**: Does table 2 continue the data pattern from table 1?
5. **Headers**: Does table 2 repeat headers or continue without headers?
6. **Context Clues**: Does surrounding text suggest they should be combined?

## Response Format:

Provide your response in this exact JSON format:

```json
{
    "should_merge": true/false,
    "confidence": 0.85,
    "reasoning": "Detailed explanation of your decision including specific evidence from the tables",
    "merge_type": "vertical/horizontal/none",
    "concerns": ["Any potential issues with merging"],
    "benefits": ["Benefits of merging if applicable"]
}
```

**Important**: 
- Confidence should be 0.0 to 1.0
- Be conservative - only recommend merging if you're reasonably confident
- Consider that incorrectly merging tables is often worse than keeping them separate
- Look for clear evidence of continuation or logical relationship

Please analyze these tables and provide your recommendation.
"""
        
        return prompt
    
    def _parse_claude_response(self, response: str) -> Tuple[bool, float, str]:
        """Parse Claude's response and extract decision."""
        try:
            # Look for JSON in the response
            import re
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                parsed = json.loads(json_str)
                
                should_merge = parsed.get('should_merge', False)
                confidence = float(parsed.get('confidence', 0.0))
                reasoning = parsed.get('reasoning', 'No reasoning provided')
                
                # Include additional details in reasoning if available
                if 'concerns' in parsed and parsed['concerns']:
                    reasoning += f"\nConcerns: {', '.join(parsed['concerns'])}"
                if 'benefits' in parsed and parsed['benefits']:
                    reasoning += f"\nBenefits: {', '.join(parsed['benefits'])}"
                
                return should_merge, confidence, reasoning
            else:
                # Fallback parsing for non-JSON responses
                should_merge = 'should_merge": true' in response.lower() or 'merge: true' in response.lower()
                confidence = 0.5  # Default confidence for fallback
                reasoning = response[:500] + "..." if len(response) > 500 else response
                
                return should_merge, confidence, reasoning
                
        except Exception as e:
            logger.error(f"Failed to parse Claude response: {e}")
            return False, 0.0, f"Parse error: {e}"
    
    def analyze_table_sequence(self, 
                              tables: List[Dict[str, Any]], 
                              context: Optional[Dict[str, Any]] = None) -> List[List[int]]:
        """
        Analyze a sequence of tables and return merge groups.
        
        Args:
            tables: List of table data dictionaries
            context: Document context
            
        Returns:
            List of lists where each inner list contains indices of tables to merge
        """
        if len(tables) < 2:
            return [[i] for i in range(len(tables))]
        
        merge_groups = []
        current_group = [0]
        
        for i in range(1, len(tables)):
            should_merge, confidence, reasoning = self.should_merge_tables(
                tables[i-1], 
                tables[i], 
                context
            )
            
            logger.info(f"Table {i-1} -> {i}: merge={should_merge}, confidence={confidence:.2f}")
            logger.debug(f"Reasoning: {reasoning}")
            
            # Only merge if confidence is high enough
            if should_merge and confidence >= 0.7:
                current_group.append(i)
            else:
                merge_groups.append(current_group)
                current_group = [i]
        
        # Add the last group
        merge_groups.append(current_group)
        
        return merge_groups


# Integration with enhanced table processor
def integrate_llm_merge_analyzer():
    """
    Example of how to integrate this with the enhanced table processor.
    """
    
    # In enhanced_table.py, replace the heuristic merge logic with:
    
    def llm_enhanced_merge_tables(self, document):
        """Enhanced merge using LLM analysis."""
        
        # Collect all tables with their data
        tables_data = []
        table_blocks = []
        
        for page in document.pages:
            for block in page.contained_blocks(document, self.block_types):
                # Extract table data for analysis
                table_data = {
                    'csv': block.generate_csv(document, []) if hasattr(block, 'generate_csv') else None,
                    'json_data': block.generate_json(document, []) if hasattr(block, 'generate_json') else None,
                    'text': block.raw_text(document),
                    'metadata': {
                        'page_id': block.page_id,
                        'bbox': block.polygon.bbox if hasattr(block, 'polygon') else None,
                        'extraction_method': getattr(block, 'extraction_method', None)
                    }
                }
                tables_data.append(table_data)
                table_blocks.append(block)
        
        if len(tables_data) < 2:
            return
        
        # Use LLM analyzer
        analyzer = LLMTableMergeAnalyzer()
        
        # Get document context
        context = {
            'document_type': 'research_paper',  # Could be detected
            'total_pages': len(document.pages)
        }
        
        # Analyze table sequence
        merge_groups = analyzer.analyze_table_sequence(tables_data, context)
        
        # Perform merges based on LLM recommendations
        for group in merge_groups:
            if len(group) > 1:
                # Merge tables in this group
                primary_block = table_blocks[group[0]]
                original_tables = []
                
                for i in group:
                    block = table_blocks[i]
                    original_tables.append({
                        'id': f"table_page{block.page_id}_{i}",
                        'data': tables_data[i]
                    })
                
                # Update merge info with LLM decision
                if hasattr(primary_block, 'update_merge_info'):
                    primary_block.update_merge_info(
                        merge_type="llm_analyzed",
                        original_tables=original_tables,
                        confidence=0.9,  # High confidence since LLM made the decision
                        merge_method="claude_code_llm"
                    )
                
                logger.info(f"LLM recommended merging {len(group)} tables")


if __name__ == "__main__":
    # Example usage
    analyzer = LLMTableMergeAnalyzer()
    
    # Example table data
    table1 = {
        'csv': 'Name,Age\nJohn,25\nJane,30',
        'text': 'Table showing employee data'
    }
    
    table2 = {
        'csv': 'Name,Age\nBob,35\nAlice,28',  
        'text': 'Continuation of employee data'
    }
    
    should_merge, confidence, reasoning = analyzer.should_merge_tables(table1, table2)
    print(f"Should merge: {should_merge}")
    print(f"Confidence: {confidence}")
    print(f"Reasoning: {reasoning}")