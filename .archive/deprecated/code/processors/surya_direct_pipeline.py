"""
Direct Surya model pipeline for optimized PDF processing.
Shows how to use Surya models directly instead of through marker's pipeline.'
"""
Module: surya_direct_pipeline.py

import asyncio
from typing import List, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
import numpy as np

# Direct Surya imports (these would replace marker's wrapped versions)
# from surya.detection import DetectionPredictor
# from surya.layout import LayoutPredictor  
# from surya.recognition import RecognitionPredictor
# from surya.table_rec import TableRecPredictor
# Note: TexifyPredictor has been removed, use RecognitionPredictor instead

# For now, we'll create a demonstration class structure
class SuryaDirectPipeline:
    """
    Optimized pipeline using Surya models directly with custom control.
    """
    
    def __init__(self, device='cuda', batch_size=8):
        self.device = device
        self.batch_size = batch_size
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        # Initialize models with custom settings
        self._init_models()
        
    def _init_models(self):
        """
        Initialize Surya models with optimized settings.
        """
        # In real implementation:
        # self.layout_model = LayoutPredictor(
        #     device=self.device,
        #     batch_size=self.batch_size,
        #     confidence_threshold=0.85
        # )
        
        # Model configuration
        self.model_config = {
            'layout': {
                'confidence_threshold': 0.85,
                'nms_threshold': 0.5,
                'batch_size': self.batch_size
            },
            'detection': {
                'confidence_threshold': 0.9,
                'min_area': 100,
                'batch_size': self.batch_size * 2  # Detection is faster
            },
            'ocr': {
                'confidence_threshold': 0.95,
                'batch_size': self.batch_size,
                'language_hints': ['en', 'es', 'fr']
            },
            'table': {
                'confidence_threshold': 0.8,
                'min_cells': 4,
                'batch_size': 4  # Tables are memory intensive
            },
            'texify': {
                'confidence_threshold': 0.9,
                'batch_size': 4,
                'max_tokens': 500
            }
        }
    
    async def process_document(self, pages: List[np.ndarray], 
                             parallel: bool = True) -> Dict:
        """
        Process entire document with optimized pipeline.
        """
        if parallel:
            return await self._process_parallel(pages)
        else:
            return self._process_sequential(pages)
    
    async def _process_parallel(self, pages: List[np.ndarray]) -> Dict:
        """
        Process pages in parallel with intelligent batching.
        """
        # Step 1: Layout detection for all pages (fast)
        layouts = await self._batch_layout_detection(pages)
        
        # Step 2: Group regions by type for batch processing
        grouped_regions = self._group_regions_by_type(layouts)
        
        # Step 3: Process each type in parallel
        tasks = []
        
        # Text regions (largest batch size)
        if grouped_regions['text']:
            tasks.append(self._batch_process_text(grouped_regions['text']))
        
        # Tables (smaller batch size)
        if grouped_regions['table']:
            tasks.append(self._batch_process_tables(grouped_regions['table']))
        
        # Math (medium batch size)
        if grouped_regions['math']:
            tasks.append(self._batch_process_math(grouped_regions['math']))
        
        # Code blocks (need special handling)
        if grouped_regions['code']:
            tasks.append(self._batch_process_code(grouped_regions['code']))
        
        # Wait for all processing
        results = await asyncio.gather(*tasks)
        
        # Step 4: Merge results maintaining page order
        return self._merge_results(results, layouts)
    
    def _group_regions_by_type(self, layouts: List[Dict]) -> Dict[str, List]:
        """
        Group regions by type for efficient batch processing.
        """
        grouped = {
            'text': [],
            'table': [],
            'math': [],
            'code': [],
            'image': [],
            'other': []
        }
        
        for page_idx, layout in enumerate(layouts):
            for region in layout['regions']:
                region['page_idx'] = page_idx
                region_type = self._classify_region(region)
                grouped[region_type].append(region)
        
        return grouped
    
    def _classify_region(self, region: Dict) -> str:
        """
        Intelligent region classification based on multiple signals.
        """
        # Primary classification from layout model
        base_type = region.get('type', 'text')
        
        # Refinement based on characteristics
        if base_type == 'text':
            # Check if it's actually code
            if self._looks_like_code(region):
                return 'code'
            # Check if it's math
            elif self._looks_like_math(region):
                return 'math'
        
        return base_type
    
    def _looks_like_code(self, region: Dict) -> bool:
        """
        Heuristics to identify code blocks.
        """
        indicators = [
            region.get('monospace_font', False),
            region.get('indentation_level', 0) > 2,
            region.get('has_brackets', False),
            region.get('line_numbers', False)
        ]
        return sum(indicators) >= 2
    
    def _looks_like_math(self, region: Dict) -> bool:
        """
        Heuristics to identify math regions.
        """
        indicators = [
            region.get('has_special_symbols', False),
            region.get('centered', False),
            region.get('italic_font', False),
            region.get('isolated', False)
        ]
        return sum(indicators) >= 2
    
    async def _batch_process_text(self, regions: List[Dict]) -> List[Dict]:
        """
        Batch process text regions with OCR.
        """
        results = []
        
        # Process in batches
        for i in range(0, len(regions), self.batch_size):
            batch = regions[i:i + self.batch_size]
            
            # Prepare batch images
            batch_images = [r['image'] for r in batch]
            
            # Run OCR (in real implementation)
            # ocr_results = self.recognition_model(batch_images)
            
            # Mock results for demo
            for j, region in enumerate(batch):
                results.append({
                    'region': region,
                    'text': f"OCR text for region {region.get('id', j)}",
                    'confidence': 0.95,
                    'processor': 'surya_ocr'
                })
        
        return results
    
    async def _batch_process_tables(self, regions: List[Dict]) -> List[Dict]:
        """
        Process tables with specialized handling.
        """
        results = []
        
        for region in regions:
            # Check table complexity
            complexity = self._analyze_table_complexity(region)
            
            if complexity['score'] > 0.7:
                # Complex table - mark for Claude processing
                results.append({
                    'region': region,
                    'needs_claude': True,
                    'complexity': complexity,
                    'processor': 'claude_recommended'
                })
            else:
                # Simple table - use Surya
                # table_result = self.table_model(region['image'])
                results.append({
                    'region': region,
                    'table_data': "[[Simple table data]]",
                    'confidence': 0.9,
                    'processor': 'surya_table'
                })
        
        return results
    
    def _analyze_table_complexity(self, region: Dict) -> Dict:
        """
        Analyze table complexity to decide processing strategy.
        """
        complexity_factors = {
            'merged_cells': 0.3,
            'nested_headers': 0.3,
            'irregular_structure': 0.2,
            'dense_content': 0.1,
            'special_formatting': 0.1
        }
        
        score = 0.0
        factors = []
        
        # Check for complexity indicators
        if region.get('has_merged_cells', False):
            score += complexity_factors['merged_cells']
            factors.append('merged_cells')
        
        if region.get('header_rows', 1) > 1:
            score += complexity_factors['nested_headers']
            factors.append('nested_headers')
        
        if region.get('irregular_grid', False):
            score += complexity_factors['irregular_structure']
            factors.append('irregular_structure')
        
        return {
            'score': min(score, 1.0),
            'factors': factors,
            'recommendation': 'claude' if score > 0.7 else 'surya'
        }
    
    async def _batch_process_math(self, regions: List[Dict]) -> List[Dict]:
        """
        Process math with Texify and complexity routing.
        """
        results = []
        
        for region in regions:
            # Always start with Texify
            # texify_result = self.texify_model(region['image'])
            
            # Check if Claude review needed
            needs_review = self._math_needs_review(region)
            
            results.append({
                'region': region,
                'latex': "\\sum_{i=1}^{n} x_i",  # Mock result
                'needs_claude_review': needs_review,
                'processor': 'texify' if not needs_review else 'texify+claude'
            })
        
        return results
    
    def _math_needs_review(self, region: Dict) -> bool:
        """
        Determine if math needs Claude review.
        """
        # Size-based heuristic
        if region.get('height', 0) > 100:
            return True
        
        # Multi-line equations
        if region.get('line_count', 1) > 1:
            return True
        
        # Complex notation indicators
        if region.get('has_matrices', False):
            return True
            
        return False
    
    async def _batch_process_code(self, regions: List[Dict]) -> List[Dict]:
        """
        Process code blocks - always route to Claude for analysis.
        """
        results = []
        
        for region in regions:
            # First get text via OCR
            # text = self.recognition_model(region['image'])
            
            results.append({
                'region': region,
                'raw_text': "def example(): pass",  # Mock
                'needs_claude': True,
                'claude_task': 'analyze_and_format_code',
                'processor': 'ocr+claude'
            })
        
        return results
    
    def _merge_results(self, results: List[List[Dict]], 
                      layouts: List[Dict]) -> Dict:
        """
        Merge all results back into document structure.
        """
        # Flatten results
        all_results = []
        for result_group in results:
            all_results.extend(result_group)
        
        # Create page-based structure
        document = {
            'pages': [],
            'metadata': {
                'total_regions': len(all_results),
                'processors_used': set(),
                'needs_claude_count': 0
            }
        }
        
        # Group by page
        for page_idx, layout in enumerate(layouts):
            page_results = [
                r for r in all_results 
                if r['region'].get('page_idx') == page_idx
            ]
            
            # Sort by position
            page_results.sort(
                key=lambda x: (
                    x['region'].get('y0', 0), 
                    x['region'].get('x0', 0)
                )
            )
            
            document['pages'].append({
                'page_num': page_idx,
                'layout': layout,
                'content': page_results
            })
            
            # Update metadata
            for result in page_results:
                document['metadata']['processors_used'].add(
                    result.get('processor', 'unknown')
                )
                if result.get('needs_claude', False):
                    document['metadata']['needs_claude_count'] += 1
        
        return document
    
    def get_performance_stats(self) -> Dict:
        """
        Get performance statistics for optimization.
        """
        return {
            'batch_sizes': self.model_config,
            'parallel_workers': self.executor._max_workers,
            'device': self.device,
            'memory_usage': self._get_memory_usage()
        }
    
    def _get_memory_usage(self) -> Dict:
        """
        Get current memory usage for monitoring.
        """
        if self.device == 'cuda':
            import torch
            return {
                'allocated': torch.cuda.memory_allocated() / 1024**3,  # GB
                'reserved': torch.cuda.memory_reserved() / 1024**3
            }
        return {'ram': 'Not implemented'}


# Configuration presets for different use cases
PIPELINE_PRESETS = {
    'speed': {
        'batch_size': 16,
        'parallel': True,
        'skip_complex': True,
        'description': 'Fastest processing, may skip complex regions'
    },
    'balanced': {
        'batch_size': 8,
        'parallel': True,
        'skip_complex': False,
        'description': 'Good balance of speed and quality'
    },
    'quality': {
        'batch_size': 4,
        'parallel': True,
        'skip_complex': False,
        'claude_review_all': True,
        'description': 'Highest quality, uses Claude for validation'
    },
    'memory_constrained': {
        'batch_size': 2,
        'parallel': False,
        'skip_complex': False,
        'description': 'For systems with limited GPU memory'
    }
}


if __name__ == "__main__":
    # Example usage
    print("Surya Direct Pipeline - Optimization Strategies")
    print("=" * 60)
    
    # Show presets
    print("\nAvailable Presets:")
    for name, config in PIPELINE_PRESETS.items():
        print(f"\n{name.upper()}:")
        print(f"  Description: {config['description']}")
        print(f"  Batch Size: {config['batch_size']}")
        print(f"  Parallel: {config['parallel']}")
    
    # Show processing flow
    print("\n\nOptimized Processing Flow:")
    print("1. Batch layout detection (all pages)")
    print("2. Intelligent region grouping by type")
    print("3. Parallel processing by region type:")
    print("   - Text: Large batches with Surya OCR")
    print("   - Tables: Complexity analysis → Surya or Claude")
    print("   - Math: Texify → Claude review if complex")
    print("   - Code: OCR → Always Claude for analysis")
    print("4. Merge results maintaining document order")
    
    # Show decision matrix
    print("\n\nRouting Decision Matrix:")
    print("-" * 60)
    print("Content Type | Simple → Processor | Complex → Processor")
    print("-" * 60)
    print("Text         | Surya OCR          | Surya OCR")
    print("Table        | Surya Table        | Claude Analysis")  
    print("Math         | Texify             | Texify + Claude")
    print("Code         | N/A                | OCR + Claude")
    print("Image        | N/A                | Claude Description")