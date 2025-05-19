"""Debug the Python type hints detection issue."""
from marker.processors.code import CodeProcessor
from marker.schema.blocks.code import Code
from marker.schema.polygon import PolygonBox

# The problematic code sample
code_sample = '''from typing import List, Dict

names: List[str] = ["Alice", "Bob"]
scores: Dict[str, int] = {"Alice": 95, "Bob": 87}
average: float = sum(scores.values()) / len(scores)'''

# Create processor and test
processor = CodeProcessor({'enable_language_detection': True})

block = Code(
    polygon=PolygonBox(polygon=[[0, 0], [100, 0], [100, 100], [0, 100]]),
    code=code_sample,
    block_id=0,
    page_id=0
)

print("Testing code:")
print(code_sample)
print("\nDetection process:")

# Test heuristic detection
heuristic_lang, heuristic_conf = processor._heuristic_detection(code_sample)
print(f"Heuristic: {heuristic_lang} (confidence: {heuristic_conf})")

# Full detection
detected = processor.detect_language(block)
print(f"Final detection: {detected}")

# Check what indicators are present
print("\nIndicators found:")
indicators = {
    'has typing import': 'from typing' in code_sample,
    'has List[': 'List[' in code_sample,
    'has Dict[': 'Dict[' in code_sample,  
    'has : float': ': float' in code_sample,
    'has : int': ': int' in code_sample,
    'has : str': ': str' in code_sample,
    'has values()': 'values()' in code_sample,
    'has sum()': 'sum(' in code_sample
}

for key, value in indicators.items():
    print(f"  {key}: {value}")