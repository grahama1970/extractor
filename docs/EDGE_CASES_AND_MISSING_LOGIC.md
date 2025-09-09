# Edge Cases and Missing Logic in Extractor Processors

## Pattern Analysis: Common Missing Logic Across All Processors

### 1. Single-Item Pattern (Critical)

**Pattern**: When a structure contains only one item, it often indicates misclassification.

**Found in `llm_table.py` (fixed):**
```python
# Single sentence incorrectly classified as table
if text and text[-1] in '.!?' and '\n' not in text:
    block.is_suspicious = True
    block.suspicious_reason = "Single sentence detected - should be text, not table"
```

**Missing in Other Processors:**

#### Text Processor
```python
# MISSING: Single word text blocks
if len(block.structure) == 1 and len(text.split()) == 1:
    # Could be: page number, header fragment, list marker
    pass

# MISSING: Single character blocks  
if len(text.strip()) == 1:
    # Often bullets, markers, or OCR artifacts
    pass
```

#### List Processor
```python
# MISSING: Single item lists
if len(block.structure) == 1:
    # Might be a paragraph with initial number/bullet
    pass
```

#### Code Processor
```python
# MISSING: Single line of code
if '\n' not in code_text and len(code_text) < 80:
    # Could be inline code, not a code block
    pass
```

### 2. Empty/Minimal Content Pattern

**Issue**: Processors don't consistently handle empty or near-empty blocks.

#### Missing Validations:
```python
# Text Processor - MISSING
if not text.strip() or text.isspace():
    block.ignore_for_output = True
    return

# Table Processor - MISSING  
if len(cells) == 0:
    block.block_type = BlockTypes.Text  # Downgrade to text
    return

# Code Processor - MISSING
if code_text.strip() == '' or all(line.isspace() for line in lines):
    block.ignore_for_output = True
    return
```

### 3. Boundary/Extreme Values Pattern

**Issue**: No validation for extreme dimensions, counts, or ratios.

#### Missing Checks:
```python
# Table Processor - MISSING
if table_width < 50 or table_height < 20:  # pixels
    # Too small to be a real table
    pass

if num_cells > 10000:
    # Suspiciously large table
    pass

if aspect_ratio > 20:  # width/height
    # Might need rotation or is misclassified
    pass

# Text Processor - MISSING
if block.polygon.height < min_text_height:
    # Might be noise or watermark
    pass

if len(text) > 50000:  # characters
    # Suspiciously long text block
    pass
```

### 4. Type Confusion Pattern

**Issue**: Content that looks like one type but is actually another.

#### Common Confusions Not Handled:

1. **Aligned text misclassified as table:**
```python
# MISSING in table processor
def looks_like_aligned_text(cells):
    # Check if "table" is just space-aligned text
    if all(cell.colspan == 1 for cell in cells):
        if len(set(cell.col_id for cell in cells)) == 2:
            # Might be two-column aligned text, not table
            return True
```

2. **Formatted text misclassified as code:**
```python
# MISSING in code processor  
def is_formatted_text_not_code(text):
    # Check for prose-like patterns
    if text.count('. ') > 5 and text.count(';') < 2:
        # Likely formatted text, not code
        return True
```

3. **Headers misclassified as regular text:**
```python
# MISSING in text processor
def might_be_header(text, font_info):
    if len(text.split()) < 7 and text.isupper():
        return True
    if font_info and font_info.size > avg_font_size * 1.5:
        return True
```

### 5. Continuation/Split Detection Pattern

**Issue**: Poor handling of content split across pages/columns.

#### Missing Logic:

```python
# Text Processor - INCOMPLETE
def is_sentence_fragment(text):
    # Check if text doesn't start with capital
    if text and not text[0].isupper() and text[0].isalpha():
        return True
    # Check if text doesn't end with sentence terminator
    if text and text[-1] not in '.!?;:':
        return True
    return False

# Table Processor - MISSING
def is_table_fragment(cells, page_position):
    # Check if table starts mid-row
    if min(cell.row_id for cell in cells) != 0:
        return True
    # Check if table is at page boundary
    if page_position == 'bottom' and not has_bottom_border:
        return True
```

### 6. Language/Locale Pattern

**Issue**: Assumptions about English text break for other languages.

#### Missing Handling:

```python
# MISSING in all text processors
def detect_text_direction(text):
    # RTL languages need different processing
    rtl_chars = sum(1 for c in text if '\u0590' <= c <= '\u08FF')
    return 'rtl' if rtl_chars > len(text) * 0.3 else 'ltr'

# MISSING in list processor
def get_list_markers_for_locale(locale):
    # Different cultures use different markers
    if locale.startswith('ja'):
        return ['・', '◆', '○', '※']
    elif locale.startswith('ar'):
        return ['◄', '•', '◦', '-']
```

### 7. Quality/Confidence Pattern

**Issue**: Inconsistent or missing confidence scoring.

#### Standardized Approach Needed:

```python
class ConfidenceFactors:
    """Standard confidence factors all processors should consider"""
    
    def calculate_geometric_confidence(self, block):
        factors = {
            'alignment': self.check_alignment_score(block),
            'size_consistency': self.check_size_consistency(block),
            'spacing_regularity': self.check_spacing_pattern(block),
            'position_logic': self.check_position_makes_sense(block)
        }
        return sum(factors.values()) / len(factors)
    
    def calculate_content_confidence(self, block):
        factors = {
            'text_coherence': self.check_text_makes_sense(block),
            'format_consistency': self.check_format_pattern(block),
            'expected_content': self.check_content_matches_type(block)
        }
        return sum(factors.values()) / len(factors)
```

### 8. OCR Error Pattern

**Issue**: No systematic handling of common OCR errors.

#### Missing OCR Error Detection:

```python
# MISSING in all processors
class OCRErrorDetector:
    
    COMMON_OCR_ERRORS = {
        'rn': 'm',  # "rn" often misread as "m"
        'l1': 'll', # "l1" misread as "ll"  
        'O0': 'OO', # "O0" confusion
        'S5': 'SS', # "S5" confusion
    }
    
    def detect_suspicious_patterns(self, text):
        # Check for impossible letter combinations
        if re.search(r'[0-9][A-Za-z][0-9]', text):  # 5a5
            return True
        # Check for mixed similar characters
        if 'O0o' in text or 'l1I' in text:
            return True
        # Check for isolated special characters
        if re.search(r'\s[^\w\s]\s', text):  # " @ "
            return True
```

### 9. Metadata/Annotation Pattern

**Issue**: Processors don't leverage existing annotations/metadata.

#### Missing Integration:

```python
# MISSING in all processors
def check_human_annotations(self, block, document):
    """Check if humans have annotated this block type before"""
    if hasattr(document, 'annotations'):
        similar = self.find_similar_blocks(block, document.annotations)
        if similar:
            # Use human annotation to guide processing
            return similar.classification
```

### 10. Recovery/Fallback Pattern

**Issue**: Most processors fail hard instead of graceful degradation.

#### Missing Fallback Chains:

```python
# MISSING pattern in processors
class ProcessorWithFallback:
    
    def process(self, block):
        try:
            result = self.primary_method(block)
            if self.validate_result(result):
                return result
        except Exception as e:
            logger.warning(f"Primary method failed: {e}")
        
        # Try fallback methods
        for fallback in self.fallback_methods:
            try:
                result = fallback(block)
                if self.validate_result(result):
                    block.processed_by = fallback.__name__
                    return result
            except Exception:
                continue
        
        # Final fallback - mark as suspicious
        block.is_suspicious = True
        block.needs_human_review = True
        return self.safe_default(block)
```

## Specific Processor Edge Cases

### Table Processor Deep Dive

**Missing Edge Cases:**

1. **Tables with merged cells spanning entire width:**
```python
# Not handled - these often indicate section breaks in tables
if any(cell.colspan == max_cols for cell in cells):
    # Might be a section header within table
    pass
```

2. **Rotated tables:**
```python
# Incomplete - only checks cell ratios
def detect_rotation_angle(cells):
    # Should check text orientation within cells
    # Should check if headers are on the side
    # Should check reading order
    pass
```

3. **Multi-page tables:**
```python
# Not handled - no continuity checking
def is_continued_table(table1, table2):
    # Check if column headers match
    # Check if column count matches
    # Check if styling matches
    pass
```

### Code Processor Deep Dive

**Missing Edge Cases:**

1. **Log files misclassified as code:**
```python
# Not detected
def is_log_file(text):
    log_patterns = [
        r'^\d{4}-\d{2}-\d{2}',  # Dates
        r'\[INFO\]|\[ERROR\]|\[DEBUG\]',  # Log levels
        r'^[\d:]+\s+\w+:',  # Timestamps
    ]
    matches = sum(1 for p in log_patterns if re.search(p, text, re.M))
    return matches >= 2
```

2. **Configuration files:**
```python
# Partially handled but incomplete
def detect_config_format(text):
    # Missing: .env files, .properties files, etc.
    if all(line.strip() == '' or '=' in line for line in lines):
        return 'properties'
```

### Text Processor Deep Dive

**Missing Edge Cases:**

1. **Watermarks and backgrounds:**
```python
# Not detected
def is_watermark_text(block):
    # Check opacity/color if available
    # Check if text repeats across pages
    # Check if text is diagonal
    pass
```

2. **Margin notes:**
```python
# Not handled
def is_margin_note(block, page):
    margin_threshold = page.width * 0.15
    if (block.x_start < margin_threshold or 
        block.x_end > page.width - margin_threshold):
        # Likely a margin note
        return True
```

## Critical Patterns Summary

1. **Single-Item Detection**: The most critical missing pattern
2. **Type Confusion**: Second most critical - content misclassification
3. **Boundary Validation**: Prevents processing of invalid data
4. **Confidence Scoring**: Enables downstream processors to make better decisions
5. **Fallback Chains**: Improves robustness significantly

## Implementation Priority

1. **Immediate**: Add single-item detection to all processors
2. **High**: Implement boundary validation 
3. **High**: Standardize confidence scoring
4. **Medium**: Add type confusion detection
5. **Medium**: Implement fallback chains
6. **Low**: Add OCR error detection
7. **Low**: Implement locale-specific handling