"""
Test language detection for simple code blocks without functions or classes.
"""
from marker.processors.code import CodeProcessor
from marker.schema.blocks.code import Code
from marker.schema.polygon import PolygonBox

def test_simple_code_detection():
    """Test language detection on simple code snippets without functions/classes."""
    
    print("=== Testing Simple Code Detection ===\n")
    
    # Create processor
    processor = CodeProcessor({'enable_language_detection': True})
    
    # Test cases: simple code without functions or classes
    test_cases = [
        # Python simple statements
        {
            'code': '''import pandas as pd
import numpy as np

data = pd.read_csv('file.csv')
print(data.head())
mean_value = data['column'].mean()''',
            'expected': 'python',
            'description': 'Python imports and simple operations'
        },
        
        # Python list comprehension
        {
            'code': '''squares = [x**2 for x in range(10)]
filtered = [x for x in data if x > 0]
result = sum(squares) / len(squares)''',
            'expected': 'python',
            'description': 'Python list comprehensions'
        },
        
        # JavaScript simple code
        {
            'code': '''const items = [1, 2, 3, 4, 5];
const doubled = items.map(x => x * 2);
console.log(doubled);''',
            'expected': 'javascript',
            'description': 'JavaScript array operations'
        },
        
        # Bash commands
        {
            'code': '''#!/bin/bash
echo "Starting process..."
cd /path/to/directory
python script.py --arg value''',
            'expected': 'bash',
            'description': 'Bash script commands'
        },
        
        # SQL query
        {
            'code': '''SELECT name, age, email
FROM users
WHERE age > 18
ORDER BY name ASC;''',
            'expected': 'sql',
            'description': 'SQL query'
        },
        
        # JSON data
        {
            'code': '''{
    "name": "John Doe",
    "age": 30,
    "skills": ["Python", "JavaScript"]
}''',
            'expected': 'json',
            'description': 'JSON data structure'
        },
        
        # YAML config
        {
            'code': '''database:
  host: localhost
  port: 5432
  name: myapp
settings:
  debug: true''',
            'expected': 'yaml',
            'description': 'YAML configuration'
        },
        
        # Python type checking example (no functions)
        {
            'code': '''from typing import List, Dict

names: List[str] = ["Alice", "Bob"]
scores: Dict[str, int] = {"Alice": 95, "Bob": 87}
average: float = sum(scores.values()) / len(scores)''',
            'expected': 'python',
            'description': 'Python with type annotations (no functions)'
        }
    ]
    
    results = []
    
    for test in test_cases:
        # Create code block
        block = Code(
            polygon=PolygonBox(polygon=[[0, 0], [100, 0], [100, 100], [0, 100]]),
            code=test['code'],
            block_id=0,
            page_id=0
        )
        
        # Detect language
        detected = processor.detect_language(block)
        
        # Store result
        is_correct = detected == test['expected']
        results.append({
            'description': test['description'],
            'expected': test['expected'],
            'detected': detected,
            'correct': is_correct
        })
        
        print(f"{test['description']}:")
        print(f"  Expected: {test['expected']}")
        print(f"  Detected: {detected} {'✓' if is_correct else '✗'}")
        print()
    
    # Calculate accuracy
    total = len(results)
    correct = sum(1 for r in results if r['correct'])
    accuracy = correct / total * 100
    
    print(f"\nResults Summary:")
    print(f"Total tests: {total}")
    print(f"Correct: {correct}")
    print(f"Accuracy: {accuracy:.1f}%")
    
    # Show failures
    failures = [r for r in results if not r['correct']]
    if failures:
        print("\nFailed detections:")
        for f in failures:
            print(f"  {f['description']}: expected {f['expected']}, got {f['detected']}")
    
    return accuracy

if __name__ == "__main__":
    accuracy = test_simple_code_detection()
    success = accuracy >= 80
    print(f"\n{'SUCCESS' if success else 'FAILURE'}: Language detection accuracy {accuracy:.1f}%")
    exit(0 if success else 1)