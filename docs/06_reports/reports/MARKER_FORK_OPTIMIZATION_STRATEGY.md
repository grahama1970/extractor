# Marker Fork Optimization Strategy

## Executive Summary

Optimize the marker fork by using it as infrastructure while routing complex tasks to Claude Code Instance and accessing Surya models directly for better control.

## 1. Math/Equation Handling Strategy

### Current State (Marker + Texify)
- Basic LaTeX conversion
- Limited context understanding
- No error correction
- Single-pass processing

### Optimized Approach (Hybrid)
```python
class MathProcessor:
    def process_math(self, math_region, context):
        # Step 1: Use Texify for initial conversion
        latex = self.texify_model(math_region)
        
        # Step 2: Validate with simple heuristics
        if self.is_simple_equation(latex):
            return latex
        
        # Step 3: Complex math → Claude Code Instance
        if self.is_complex_math(latex, context):
            return self.claude_math_processor(
                latex=latex,
                context=context,
                task="verify_and_improve_latex"
            )
```

### When to Use Claude for Math:
- Multi-line equations with alignment
- Equations with errors or incomplete LaTeX
- Mathematical proofs or derivations
- Equations needing semantic understanding
- Matrix operations or complex notation

## 2. Direct Surya Model Usage

### Current (Through Marker)
```python
# Limited control, fixed pipeline
converter = PdfConverter(config)
result = converter(pdf_path)
```

### Optimized (Direct Access)
```python
from surya.detection import DetectionPredictor
from surya.layout import LayoutPredictor
from surya.recognition import RecognitionPredictor
from surya.table_rec import TableRecPredictor
from surya.texify import TexifyPredictor

class OptimizedSuryaPipeline:
    def __init__(self):
        self.layout = LayoutPredictor()
        self.detection = DetectionPredictor()
        self.recognition = RecognitionPredictor()
        self.table_rec = TableRecPredictor()
        self.texify = TexifyPredictor()
    
    def process_page(self, page_image, page_content):
        # Step 1: Layout detection with custom thresholds
        layout = self.layout(page_image, confidence_threshold=0.8)
        
        # Step 2: Selective processing based on layout
        for region in layout.regions:
            if region.type == "table" and region.complexity > 0.7:
                # Complex table → Claude
                yield self.process_complex_table_with_claude(region)
            elif region.type == "math":
                # Math → Texify + Claude validation
                yield self.process_math_with_validation(region)
            elif region.type == "code":
                # Code → Direct to Claude for analysis
                yield self.process_code_with_claude(region)
            else:
                # Simple text → Standard OCR
                yield self.recognition(region)
```

## 3. Task Routing Strategy

### Decision Matrix

| Content Type | Complexity | Primary Processor | Fallback | Use Claude When |
|-------------|------------|-------------------|----------|-----------------|
| Text | Simple | Surya OCR | - | Never |
| Text | Complex | Surya OCR | Claude | Garbled/unclear |
| Table | Simple | Surya Table | - | Never |
| Table | Complex | Surya Table | Claude | Multi-header, nested, financial |
| Math | Inline | Texify | - | Rarely |
| Math | Display | Texify | Claude | Complex notation, multi-line |
| Code | Any | Surya OCR | Claude | Always for analysis |
| Image | Diagram | - | Claude | Always for description |
| Lists | Any | Marker | - | Never |

### Implementation
```python
class IntelligentRouter:
    def __init__(self):
        self.complexity_analyzer = ComplexityAnalyzer()
        self.surya_pipeline = OptimizedSuryaPipeline()
        self.claude_service = ClaudeService()
        
    def route_content(self, content_block):
        complexity = self.complexity_analyzer.analyze(content_block)
        
        if content_block.type == "table":
            if complexity.score > 0.7 or complexity.has_merged_cells:
                return self.claude_service.process_table(
                    content_block,
                    context="Extract structured data preserving relationships"
                )
            else:
                return self.surya_pipeline.table_rec(content_block)
                
        elif content_block.type == "math":
            # Always start with Texify
            latex = self.surya_pipeline.texify(content_block)
            
            # Complex math gets Claude review
            if complexity.score > 0.6:
                return self.claude_service.validate_math(
                    latex=latex,
                    image=content_block.image,
                    context=content_block.surrounding_text
                )
            return latex
            
        elif content_block.type == "code":
            # Always use Claude for code understanding
            text = self.surya_pipeline.recognition(content_block)
            return self.claude_service.analyze_code(
                code=text,
                task="identify_language_and_improve_formatting"
            )
```

## 4. Claude Code Instance Integration Points

### High-Value Use Cases

1. **Table Understanding**
```python
# Instead of just extraction, understand the table
claude_result = claude.process_table(
    table_image,
    prompt="""
    1. Extract table structure and data
    2. Identify column relationships
    3. Detect any formulas or calculations
    4. Suggest better organization if needed
    5. Output as structured JSON
    """
)
```

2. **Math Context Enhancement**
```python
# Don't just convert, understand
claude_result = claude.process_math(
    math_image,
    surrounding_text,
    prompt="""
    1. Convert to LaTeX
    2. Identify the mathematical concept
    3. Check for errors
    4. Provide step-by-step explanation if it's a derivation
    5. Suggest cleaner notation if applicable
    """
)
```

3. **Code Analysis**
```python
# Full code understanding
claude_result = claude.analyze_code(
    code_block,
    prompt="""
    1. Identify programming language
    2. Check for syntax errors
    3. Add helpful comments
    4. Identify the algorithm/pattern
    5. Suggest improvements
    """
)
```

## 5. Performance Optimization

### Parallel Processing Strategy
```python
async def process_document_optimized(pdf_path):
    # Step 1: Fast layout detection on all pages
    layouts = await parallel_layout_detection(pdf_path)
    
    # Step 2: Group by complexity
    simple_blocks = []
    complex_blocks = []
    
    for layout in layouts:
        for block in layout.blocks:
            if needs_claude(block):
                complex_blocks.append(block)
            else:
                simple_blocks.append(block)
    
    # Step 3: Process in parallel
    simple_results = await batch_process_surya(simple_blocks)
    complex_results = await batch_process_claude(complex_blocks)
    
    # Step 4: Merge results maintaining order
    return merge_results(simple_results, complex_results)
```

### Caching Strategy
```python
class SmartCache:
    def __init__(self):
        self.surya_cache = {}  # Fast, in-memory
        self.claude_cache = {}  # Persistent, disk-based
        
    def get_or_process(self, content_block, processor):
        cache_key = self.generate_key(content_block)
        
        # Check appropriate cache
        if processor == "surya":
            if cache_key in self.surya_cache:
                return self.surya_cache[cache_key]
        else:  # claude
            if cache_key in self.claude_cache:
                return self.claude_cache[cache_key]
                
        # Process and cache
        result = processor(content_block)
        self.cache_result(cache_key, result, processor)
        return result
```

## 6. Configuration Recommendations

### Marker Config (Simplified)
```python
MARKER_CONFIG = {
    "use_llm": False,  # We'll handle LLM routing ourselves
    "parallel_factor": 4,  # Higher for better performance
    "disable_image_extraction": False,  # We need images for Claude
    "processors": [
        # Only essential processors
        "marker.core.processors.line_merge.LineMergeProcessor",
        "marker.core.processors.section_header.SectionHeaderProcessor",
        "marker.core.processors.list.ListProcessor",
    ]
}
```

### Custom Pipeline Config
```python
OPTIMIZATION_CONFIG = {
    "complexity_thresholds": {
        "table": 0.6,
        "math": 0.5,
        "code": 0.0,  # Always use Claude for code
    },
    "surya_settings": {
        "layout_confidence": 0.85,
        "ocr_confidence": 0.9,
        "batch_size": 8,
    },
    "claude_settings": {
        "model": "claude-3-opus-20240229",
        "temperature": 0.1,  # Low for consistency
        "max_retries": 2,
    },
    "performance": {
        "enable_caching": True,
        "parallel_claude_calls": 3,
        "parallel_surya_calls": 8,
    }
}
```

## 7. Implementation Priorities

### Phase 1: Foundation (Week 1)
1. Set up direct Surya model access
2. Implement complexity analyzer
3. Create basic routing logic
4. Set up caching system

### Phase 2: Claude Integration (Week 2)
1. Implement Claude processors for each content type
2. Create prompt templates
3. Add result validation
4. Implement fallback logic

### Phase 3: Optimization (Week 3)
1. Add parallel processing
2. Optimize batch sizes
3. Implement smart caching
4. Add performance monitoring

### Phase 4: Quality Loop (Week 4)
1. Add quality validation
2. Implement iterative improvement
3. Add confidence scoring
4. Create feedback system

## 8. Expected Improvements

### Quality Improvements
- **Tables**: 90%+ accuracy on complex tables (vs 70% current)
- **Math**: 95%+ LaTeX accuracy with context (vs 80% current)
- **Code**: 100% language detection, formatted output
- **Overall**: 30-40% reduction in post-processing needs

### Performance Targets
- **Simple documents**: Same speed as current (Surya only)
- **Complex documents**: 2-3x slower but much higher quality
- **Hybrid approach**: Optimal balance of speed and quality

## Conclusion

By using marker as infrastructure, Surya models for fast processing, and Claude for complex reasoning, you can achieve:

1. **Better Quality**: Claude handles all complex cases
2. **Better Performance**: Parallel processing and smart routing
3. **Better Control**: Direct access to all models
4. **Better Flexibility**: Easy to adjust routing rules

The key is to **use each tool for what it does best** rather than forcing everything through marker's pipeline.