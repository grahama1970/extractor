# Camelot Table Extraction Upgrade Analysis

## Current Implementation Analysis

### 1. Current Camelot Usage in 04_table_extractor.py

The current implementation has a sophisticated dual-flavor approach:

```python
def extract_table_with_camelot_advanced(pdf_path: Path, page_num: int, bbox: List[float]) -> Tuple[Optional[pd.DataFrame], Dict[str, Any]]:
```

**Current Features:**
1. **Dual-Flavor Extraction**: Uses both `lattice` and `stream` flavors
2. **Quality Scoring**: Calculates parsing scores based on non-empty cells and table dimensions
3. **Fixed Parameters**: Uses hardcoded parameters for each flavor:
   - Lattice: `line_tol=2, join_tol=2, edge_tol=50, process_background=True`
   - Stream: `row_tol=2, column_tol=0, edge_tol=50`

### 2. Example Implementation Analysis

From `examples/table_extractor.py`:
- Uses a `TableQualityEvaluator` class with parameter exploration
- Tests different parameter combinations but with limited scope
- Focuses on quality metrics like accuracy, completeness, and consistency

From `examples/table_quality_evaluator.py`:
```python
param_combinations = list(chain(
    ({'flavor': 'lattice', 'line_scale': ls} for ls in [15, 40, 80]),
    ({'flavor': 'stream', 'edge_tol': et, 'min_text_height': mth, 'split_text': st} 
     for (et, mth, st) in product([500, 1000, 1500], [1.0, 2.0, 3.0], [True, False]))
))
```

### 3. Table Similarity Heuristics

From `pdf_extractor/table_extractor.py`:
- Simple header matching for similarity calculation
- Multi-page table detection based on position and column similarity
- Conservative/aggressive merge strategies

## Proposed Upgrades

### 1. Enhanced Camelot Parameter Exploration

**Problem**: Current implementation uses fixed parameters that may not work for all table types.

**Solution**: Implement dynamic parameter exploration when Camelot fails or produces low-quality results.

```python
class CamelotParameterExplorer:
    """Advanced parameter exploration for Camelot table extraction."""
    
    # Comprehensive parameter sets for different table types
    LATTICE_PARAMS = {
        'standard': {
            'line_scale': [15, 25, 40, 50],
            'line_tol': [2, 3, 5],
            'joint_tol': [2, 3, 5],
            'threshold_blocksize': [15, 25, 35],
            'threshold_constant': [-1, -2, -3],
        },
        'dense': {
            'line_scale': [10, 15, 20],
            'line_tol': [1, 2],
            'process_background': [True, False],
        },
        'engineering': {
            'line_scale': [30, 40, 50, 60],
            'line_overlap': [0.5, 0.7, 0.9],
            'char_margin': [1.0, 2.0, 3.0],
        }
    }
    
    STREAM_PARAMS = {
        'standard': {
            'edge_tol': [50, 100, 500],
            'row_tol': [2, 5, 10],
            'column_tol': [0, 2, 5],
        },
        'complex': {
            'edge_tol': [100, 500, 1000, 1500],
            'min_text_height': [1.0, 2.0, 3.0, 5.0],
            'min_text_v_overlap': [0.1, 0.3, 0.5],
            'split_text': [True, False],
            'flag_size': [True, False],
            'strip_text': [' ', '\n', ''],
        }
    }
```

### 2. Intelligent Table Type Detection

**Enhancement**: Detect table characteristics before extraction to choose optimal parameters.

```python
def detect_table_characteristics(pdf_path: Path, page_num: int, bbox: List[float]) -> Dict[str, Any]:
    """Analyze table region to determine optimal extraction strategy."""
    
    # Extract visual features
    with fitz.open(pdf_path) as doc:
        page = doc[page_num]
        # Analyze for:
        # - Line density (lattice vs stream)
        # - Background colors/shading
        # - Text density
        # - Cell uniformity
        # - Border presence
        
    characteristics = {
        'has_visible_borders': detect_borders(page, bbox),
        'has_background_colors': detect_backgrounds(page, bbox),
        'text_density': calculate_text_density(page, bbox),
        'likely_type': 'lattice' if has_borders else 'stream',
        'complexity': 'complex' if text_density > 0.7 else 'standard'
    }
    
    return characteristics
```

### 3. Advanced Quality Metrics

**Enhancement**: More sophisticated quality evaluation beyond basic metrics.

```python
def evaluate_extraction_quality_advanced(df: pd.DataFrame, table_text: str, visual_features: Dict) -> Dict[str, float]:
    """Advanced quality evaluation considering multiple factors."""
    
    metrics = {
        # Structural integrity
        'column_consistency': check_column_consistency(df),
        'row_alignment': check_row_alignment(df),
        'cell_completeness': check_cell_completeness(df),
        
        # Content quality
        'ocr_confidence': estimate_ocr_quality(df),
        'numeric_validity': check_numeric_columns(df),
        'header_detection': validate_headers(df),
        
        # Visual correlation
        'text_coverage': compare_with_original_text(df, table_text),
        'spatial_accuracy': check_spatial_alignment(df, visual_features),
        
        # Engineering-specific
        'unit_consistency': check_engineering_units(df),
        'value_ranges': validate_engineering_values(df)
    }
    
    return metrics
```

### 4. Fallback Strategy Chain

**Enhancement**: Implement a comprehensive fallback chain when initial extraction fails.

```python
class TableExtractionStrategy:
    """Manages extraction strategies with intelligent fallbacks."""
    
    def extract_with_fallbacks(self, pdf_path: Path, page_num: int, bbox: List[float]) -> Tuple[pd.DataFrame, Dict]:
        """Try multiple extraction strategies in order of likelihood."""
        
        strategies = [
            # 1. Standard extraction with detected parameters
            lambda: self.extract_with_detected_params(pdf_path, page_num, bbox),
            
            # 2. Exhaustive parameter search
            lambda: self.extract_with_parameter_exploration(pdf_path, page_num, bbox),
            
            # 3. Image-based extraction with OCR
            lambda: self.extract_from_image_with_ocr(pdf_path, page_num, bbox),
            
            # 4. Hybrid approach - combine multiple methods
            lambda: self.extract_with_hybrid_approach(pdf_path, page_num, bbox),
            
            # 5. Manual structure inference
            lambda: self.extract_with_structure_inference(pdf_path, page_num, bbox)
        ]
        
        for strategy in strategies:
            try:
                result = strategy()
                if self.is_valid_extraction(result):
                    return result
            except Exception as e:
                logger.warning(f"Strategy failed: {e}")
                continue
                
        # Final fallback - return structured error info
        return None, {"error": "All extraction strategies failed"}
```

### 5. Table Merging Improvements

**Enhancement**: More sophisticated table merging based on structural and semantic similarity.

```python
def calculate_table_similarity_advanced(table1: Dict, table2: Dict) -> float:
    """Advanced similarity calculation using multiple factors."""
    
    scores = {
        # Structural similarity
        'column_match': compare_column_structure(table1, table2),
        'header_similarity': calculate_header_similarity_fuzzy(table1, table2),
        'dimension_compatibility': check_dimension_compatibility(table1, table2),
        
        # Content similarity
        'value_patterns': compare_value_patterns(table1, table2),
        'data_types': compare_data_types(table1, table2),
        
        # Contextual similarity
        'section_context': compare_section_context(table1, table2),
        'proximity_score': calculate_proximity_score(table1, table2),
        
        # Engineering-specific
        'unit_compatibility': check_unit_compatibility(table1, table2),
        'reference_continuity': check_reference_patterns(table1, table2)
    }
    
    # Weighted combination
    weights = {
        'column_match': 0.3,
        'header_similarity': 0.2,
        'value_patterns': 0.15,
        'proximity_score': 0.15,
        'other': 0.2
    }
    
    return calculate_weighted_score(scores, weights)
```

## Implementation Plan

### Phase 1: Parameter Exploration Enhancement
1. Create `CamelotParameterExplorer` class
2. Implement table characteristic detection
3. Add parameter recommendation based on characteristics
4. Test with engineering PDFs

### Phase 2: Quality Metrics Upgrade
1. Implement advanced quality metrics
2. Add OCR confidence estimation
3. Create engineering-specific validators
4. Benchmark against current implementation

### Phase 3: Fallback Strategy Implementation
1. Create strategy chain manager
2. Implement image-based extraction fallback
3. Add hybrid extraction methods
4. Test edge cases

### Phase 4: Integration and Testing
1. Integrate with existing pipeline
2. Add comprehensive logging
3. Create performance benchmarks
4. Document parameter selection logic

## Key Improvements Over Current Implementation

1. **Dynamic Parameter Selection**: Instead of fixed parameters, intelligently select based on table characteristics
2. **Comprehensive Fallback Chain**: Multiple extraction strategies ensure higher success rate
3. **Engineering-Specific Features**: Special handling for engineering tables with units, references, and technical notation
4. **Advanced Quality Metrics**: Better evaluation of extraction quality with domain-specific checks
5. **Improved Merging Logic**: More sophisticated similarity calculation for better multi-page table handling

## Example Usage

```python
# Enhanced extraction with automatic parameter optimization
async def extract_table_enhanced(pdf_path: Path, page_num: int, bbox: List[float]) -> Dict:
    """Enhanced table extraction with intelligent parameter selection."""
    
    # Detect table characteristics
    characteristics = detect_table_characteristics(pdf_path, page_num, bbox)
    
    # Get recommended parameters
    explorer = CamelotParameterExplorer()
    recommended_params = explorer.get_recommended_params(characteristics)
    
    # Try extraction with fallback chain
    strategy = TableExtractionStrategy()
    df, metrics = strategy.extract_with_fallbacks(
        pdf_path, page_num, bbox, 
        initial_params=recommended_params
    )
    
    # Evaluate quality
    quality = evaluate_extraction_quality_advanced(df, metrics)
    
    return {
        'dataframe': df,
        'quality': quality,
        'extraction_method': metrics.get('method'),
        'parameters_used': metrics.get('params'),
        'characteristics': characteristics
    }
```

## Conclusion

The proposed upgrades significantly enhance the robustness and accuracy of table extraction, especially for complex engineering PDFs where standard parameters often fail. The intelligent parameter selection, comprehensive fallback strategies, and engineering-specific features ensure higher success rates and better quality extractions.