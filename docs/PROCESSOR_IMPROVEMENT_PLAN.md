# Processor Improvement Implementation Plan

## Phase 1: Critical Single-Item Edge Cases (Week 1)

### Day 1-2: Text-Based Processors

1. **Text Processor** (`text.py`)
```python
def validate_text_block(self, block, document):
    """Add validation for single-item and edge cases"""
    text = block.raw_text(document)
    
    # Single word detection
    if len(text.split()) == 1:
        word = text.strip()
        # Check if it's a list marker
        if word.endswith(('.', ':', ')')):
            block.is_suspicious = True
            block.suspicious_reason = "Single word with punctuation - likely list marker"
        # Check if it's a page number
        elif word.isdigit():
            block.is_suspicious = True
            block.suspicious_reason = "Single digit - likely page number"
    
    # Single character detection
    if len(text.strip()) == 1:
        block.is_suspicious = True
        block.suspicious_reason = "Single character - likely OCR artifact or marker"
    
    # Empty or whitespace only
    if not text.strip():
        block.ignore_for_output = True
        return False
    
    return True
```

2. **Section Header Processor** (`sectionheader.py`)
```python
def validate_header(self, block):
    """Enhanced header validation"""
    text = block.text.strip()
    
    # Single word headers need extra validation
    if len(text.split()) == 1:
        # Check against valid single-word headers
        valid_single_headers = {
            'Introduction', 'Abstract', 'References', 
            'Conclusion', 'Appendix', 'Index', 'Preface'
        }
        if text.title() not in valid_single_headers:
            block.is_suspicious = True
            block.suspicious_reason = f"Single word '{text}' unlikely to be header"
    
    # Headers ending with punctuation (beyond comma)
    if text and text[-1] in '.!?;':
        block.is_suspicious = True
        block.suspicious_reason = "Headers typically don't end with punctuation"
```

### Day 3-4: Structured Content Processors

3. **Table Processor** (`table.py`)
```python
def validate_table_structure(self, table, cells):
    """Validate table isn't misclassified content"""
    
    # Single cell table
    if len(cells) == 1:
        table.is_suspicious = True
        table.suspicious_reason = "Single cell table - likely misclassified"
        return False
    
    # Single row table (might be aligned text)
    unique_rows = set(cell.row_id for cell in cells)
    if len(unique_rows) == 1:
        table.is_suspicious = True
        table.suspicious_reason = "Single row table - might be headers or aligned text"
    
    # Single column table (might be a list)
    unique_cols = set(cell.col_id for cell in cells)
    if len(unique_cols) == 1:
        table.is_suspicious = True
        table.suspicious_reason = "Single column table - might be a list"
    
    # Check for text-like content in tables
    if self.looks_like_sentences(cells):
        table.is_suspicious = True
        table.suspicious_reason = "Table contains sentence-like content"
```

4. **List Processor** (`list.py`)
```python
def validate_list_group(self, block, document):
    """Validate list group isn't misclassified"""
    
    # Single item list
    if len(block.structure) == 1:
        list_item = document.get_block(block.structure[0])
        text = list_item.raw_text(document)
        
        # Check if it's actually a paragraph with number
        if len(text) > 100 and text.count('.') > 2:
            block.is_suspicious = True
            block.suspicious_reason = "Single item list with paragraph-length content"
```

### Day 5: Code and Complex Processors

5. **Code Processor** (`code.py`)
```python
def validate_code_block(self, block):
    """Validate code block isn't misclassified"""
    
    # Single line code
    lines = block.code.split('\n')
    if len(lines) == 1:
        line = lines[0].strip()
        # Short single lines might be inline code
        if len(line) < 80:
            block.is_suspicious = True
            block.suspicious_reason = "Single short line - might be inline code"
        # Check if it's actually a command or path
        if line.startswith(('/', '\\', 'C:', '$', '>')):
            block.metadata['code_type'] = 'command_or_path'
    
    # Empty code block
    if not block.code.strip():
        block.ignore_for_output = True
        return False
```

## Phase 2: Boundary Validation (Week 2)

### Dimension Validators

```python
class DimensionValidator:
    """Shared dimension validation for all processors"""
    
    MIN_BLOCK_HEIGHT = 10  # pixels
    MIN_BLOCK_WIDTH = 20   # pixels
    MAX_ASPECT_RATIO = 50  # width/height or height/width
    
    @staticmethod
    def validate_dimensions(block) -> tuple[bool, str]:
        """Returns (is_valid, reason)"""
        height = block.polygon.height
        width = block.polygon.width
        
        if height < DimensionValidator.MIN_BLOCK_HEIGHT:
            return False, f"Height {height}px below minimum"
        
        if width < DimensionValidator.MIN_BLOCK_WIDTH:
            return False, f"Width {width}px below minimum"
        
        aspect_ratio = max(width/height, height/width)
        if aspect_ratio > DimensionValidator.MAX_ASPECT_RATIO:
            return False, f"Aspect ratio {aspect_ratio:.1f} too extreme"
        
        return True, "OK"
```

### Content Size Validators

```python
class ContentValidator:
    """Validate content size limits"""
    
    MAX_TEXT_LENGTH = 100000     # characters
    MAX_TABLE_CELLS = 10000      # cells
    MAX_CODE_LINES = 5000        # lines
    MAX_LIST_ITEMS = 1000        # items
    
    @staticmethod
    def validate_text_size(text) -> tuple[bool, str]:
        if len(text) > ContentValidator.MAX_TEXT_LENGTH:
            return False, f"Text length {len(text)} exceeds maximum"
        return True, "OK"
```

## Phase 3: Confidence Scoring Standardization (Week 3)

### Unified Confidence Framework

```python
class ConfidenceCalculator:
    """Standardized confidence calculation across all processors"""
    
    def __init__(self):
        self.factors = {}
        self.weights = {}
    
    def add_factor(self, name: str, value: float, weight: float = 1.0):
        """Add a confidence factor (0.0 to 1.0)"""
        self.factors[name] = max(0.0, min(1.0, value))
        self.weights[name] = weight
    
    def calculate(self) -> float:
        """Calculate weighted confidence score"""
        if not self.factors:
            return 0.0
        
        weighted_sum = sum(
            self.factors[f] * self.weights[f] 
            for f in self.factors
        )
        total_weight = sum(self.weights.values())
        
        return weighted_sum / total_weight if total_weight > 0 else 0.0
    
    def get_report(self) -> dict:
        """Get detailed confidence breakdown"""
        return {
            'overall': self.calculate(),
            'factors': self.factors.copy(),
            'weights': self.weights.copy()
        }
```

### Processor Integration

```python
# Example: Text Processor with confidence
def calculate_text_confidence(self, block, document):
    calc = ConfidenceCalculator()
    
    # Geometric confidence
    text = block.raw_text(document)
    lines = block.structure_blocks(document)
    
    # Factor 1: Alignment consistency  
    alignment_score = self.calculate_alignment_score(lines)
    calc.add_factor('alignment', alignment_score, weight=1.5)
    
    # Factor 2: Text coherence
    coherence_score = self.calculate_text_coherence(text)
    calc.add_factor('coherence', coherence_score, weight=2.0)
    
    # Factor 3: Size consistency
    size_score = self.calculate_size_consistency(lines)
    calc.add_factor('size_consistency', size_score, weight=1.0)
    
    # Factor 4: No suspicious patterns
    suspicious_score = 0.0 if block.is_suspicious else 1.0
    calc.add_factor('no_suspicious', suspicious_score, weight=3.0)
    
    confidence = calc.calculate()
    block.confidence = confidence
    block.confidence_report = calc.get_report()
    
    return confidence
```

## Phase 4: Type Confusion Detection (Week 4)

### Cross-Type Validators

```python
class TypeConfusionDetector:
    """Detect when content might be misclassified"""
    
    @staticmethod
    def table_or_aligned_text(cells) -> float:
        """Returns probability this is aligned text not a table"""
        # Few columns suggests aligned text
        unique_cols = len(set(c.col_id for c in cells))
        if unique_cols <= 2:
            score = 0.3
        else:
            score = 0.0
        
        # Consistent column widths suggest table
        col_widths = defaultdict(list)
        for cell in cells:
            col_widths[cell.col_id].append(cell.polygon.width)
        
        width_variance = sum(
            np.std(widths) for widths in col_widths.values()
        ) / len(col_widths)
        
        if width_variance < 10:  # pixels
            score += 0.0  # Consistent = table
        else:
            score += 0.3  # Inconsistent = maybe text
        
        # Sentence-like content suggests text
        text_content = ' '.join(c.text for c in cells)
        if text_content.count('. ') > 5:
            score += 0.4
        
        return min(1.0, score)
```

## Phase 5: Implementation Strategy

### 1. Create Base Validator Class

```python
class BaseValidator:
    """Base class for all processor validators"""
    
    def validate_single_item(self, block) -> bool:
        """Override in subclasses"""
        raise NotImplementedError
    
    def validate_dimensions(self, block) -> bool:
        """Use shared dimension validator"""
        valid, reason = DimensionValidator.validate_dimensions(block)
        if not valid:
            block.is_suspicious = True
            block.suspicious_reason = reason
        return valid
    
    def validate_content_size(self, block) -> bool:
        """Override in subclasses"""
        raise NotImplementedError
    
    def calculate_confidence(self, block) -> float:
        """Override in subclasses"""
        raise NotImplementedError
```

### 2. Testing Strategy

```python
# Test file: test_edge_cases.py
class TestEdgeCases:
    """Test all edge cases across processors"""
    
    def test_single_item_detection(self):
        """Test single-item edge cases"""
        test_cases = [
            # Text processor
            {"type": "Text", "content": "1.", "expected": "suspicious"},
            {"type": "Text", "content": "•", "expected": "suspicious"},
            
            # Table processor  
            {"type": "Table", "cells": 1, "expected": "suspicious"},
            
            # List processor
            {"type": "List", "items": 1, "expected": "check_content"},
            
            # Code processor
            {"type": "Code", "lines": 1, "length": 20, "expected": "suspicious"}
        ]
        
        for case in test_cases:
            result = process_block(case)
            assert result.status == case["expected"]
```

### 3. Rollout Plan

**Week 1**: 
- Implement single-item detection
- Deploy to dev environment
- Run on test corpus

**Week 2**:
- Add boundary validation
- Test on edge case documents
- Fix any false positives

**Week 3**:
- Standardize confidence scoring
- Update downstream processors
- Measure accuracy improvement

**Week 4**:
- Add type confusion detection
- Full integration testing
- Deploy to production

## Success Metrics

1. **Reduction in misclassified blocks**: Target 50% reduction
2. **Improved confidence accuracy**: Confidence should correlate with accuracy
3. **Better edge case handling**: 90% of edge cases detected
4. **No regression on normal cases**: Maintain current accuracy on standard documents

## Conclusion

This plan addresses the critical gaps found in the processor analysis, with single-item detection being the highest priority. The phased approach allows for iterative improvement and testing, ensuring robustness before full deployment.