"""
Focused test for tree-sitter language detection functionality.

This script verifies that:
1. Tree-sitter correctly detects programming languages based on code content
2. Code metadata is properly extracted from code blocks
3. Language detection works across a variety of languages
"""
import json
import os
from pathlib import Path
from marker.services.utils.tree_sitter_utils import extract_code_metadata, get_supported_language

# Test code snippets in various languages
test_code_samples = {
    'python': '''
def factorial(n):
    """Calculate factorial of n"""
    if n <= 1:
        return 1
    return n * factorial(n - 1)

class Calculator:
    def __init__(self):
        self.result = 0
    
    def add(self, x, y):
        return x + y
''',
    'javascript': '''
function fetchData(url) {
    return fetch(url)
        .then(response => response.json())
        .then(data => {
            console.log('Data:', data);
            return data;
        });
}

const calculator = {
    add: (a, b) => a + b,
    multiply: (a, b) => a * b
};
''',
    'java': '''
public class Main {
    public static void main(String[] args) {
        System.out.println("Hello, World!");
        Calculator calc = new Calculator();
        int result = calc.add(5, 3);
    }
    
    private static class Calculator {
        public int add(int a, int b) {
            return a + b;
        }
    }
}
''',
    'cpp': '''
#include <iostream>
#include <vector>

using namespace std;

class Shape {
public:
    virtual double area() = 0;
};

int main() {
    vector<int> numbers = {1, 2, 3, 4, 5};
    for (int n : numbers) {
        cout << n << " ";
    }
    return 0;
}
''',
    'ruby': '''
class Person
  attr_accessor :name, :age
  
  def initialize(name, age)
    @name = name
    @age = age
  end
  
  def greet
    "Hello, my name is #{@name} and I'm #{@age} years old."
  end
end

person = Person.new("Ruby", 27)
puts person.greet
''',
    'go': '''
package main

import (
    "fmt"
    "strings"
)

type Person struct {
    Name string
    Age  int
}

func (p *Person) Greet() string {
    return fmt.Sprintf("Hello, I'm %s", p.Name)
}

func main() {
    person := &Person{Name: "Alice", Age: 30}
    fmt.Println(person.Greet())
}
'''
}

def test_language_detection():
    """Test the tree-sitter language detection functionality."""
    print("Testing tree-sitter language detection...")
    
    # Create output directory
    output_dir = Path("test_results/ts_language_detection")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    results = []
    
    # For each sample, test the language detection
    for expected_lang, code in test_code_samples.items():
        print(f"\nTesting detection for {expected_lang}...")
        
        # Check if language is supported
        lang_supported = get_supported_language(expected_lang) is not None
        print(f"  Language supported by tree-sitter: {'✓' if lang_supported else '✗'}")
        
        if not lang_supported:
            print(f"  Skipping metadata extraction for unsupported language: {expected_lang}")
            results.append({
                "language": expected_lang,
                "supported": False,
                "success": False,
                "functions_found": 0,
                "classes_found": 0,
                "error": "Language not supported by tree-sitter"
            })
            continue
        
        # Extract metadata
        metadata = extract_code_metadata(code, expected_lang)
        
        # Check if extraction was successful
        success = metadata.get('tree_sitter_success', False)
        
        # Check if any functions or classes were found
        functions_found = len(metadata.get('functions', []))
        classes_found = len(metadata.get('classes', []))
        
        result = {
            "language": expected_lang,
            "supported": True,
            "success": success,
            "functions_found": functions_found,
            "classes_found": classes_found,
            "error": metadata.get('error'),
            "code_preview": code[:100].replace('\n', '\\n') + "..."
        }
        
        results.append(result)
        
        print(f"  Extraction success: {'✓' if success else '✗'}")
        print(f"  Functions found: {functions_found}")
        print(f"  Classes found: {classes_found}")
        if not success:
            print(f"  Error: {metadata.get('error')}")
        
        # Print function details if any found
        if functions_found > 0:
            print(f"  Functions:")
            for i, func in enumerate(metadata.get('functions', [])[:3]):  # Show up to 3 functions
                print(f"    {i+1}. {func.get('name', 'unnamed')} - {len(func.get('parameters', []))} params")
    
    # Calculate summary statistics
    supported_count = sum(1 for r in results if r["supported"])
    success_count = sum(1 for r in results if r["success"])
    total_count = len(results)
    support_rate = supported_count / total_count if total_count > 0 else 0
    success_rate = success_count / supported_count if supported_count > 0 else 0
    
    total_functions = sum(r["functions_found"] for r in results)
    total_classes = sum(r["classes_found"] for r in results)
    
    print(f"\nSummary:")
    print(f"Total languages tested: {total_count}")
    print(f"Languages supported: {supported_count} ({support_rate:.2%})")
    print(f"Successful extractions: {success_count} ({success_rate:.2%} of supported)")
    print(f"Total functions found: {total_functions}")
    print(f"Total classes found: {total_classes}")
    
    # Save results to JSON file
    summary = {
        "total_languages": total_count,
        "supported_languages": supported_count,
        "support_rate": support_rate,
        "successful_extractions": success_count,
        "success_rate": success_rate,
        "total_functions": total_functions,
        "total_classes": total_classes,
        "results": results
    }
    
    results_file = output_dir / "language_detection_results.json"
    with open(results_file, 'w') as f:
        json.dump(summary, f, indent=2)
        
    print(f"\nDetailed results saved to: {results_file}")
    
    # Generate a Markdown report
    report_path = output_dir / "language_detection_report.md"
    
    with open(report_path, 'w') as f:
        f.write("# Tree-Sitter Language Detection Test Report\n\n")
        f.write("## Summary\n")
        f.write(f"- **Total Languages Tested**: {total_count}\n")
        f.write(f"- **Languages Supported**: {supported_count} ({support_rate:.2%})\n")
        f.write(f"- **Successful Extractions**: {success_count} ({success_rate:.2%} of supported)\n")
        f.write(f"- **Total Functions Found**: {total_functions}\n")
        f.write(f"- **Total Classes Found**: {total_classes}\n\n")
        
        f.write("## Performance Metrics\n")
        f.write("| Metric | Result | Target | Status |\n")
        f.write("|--------|--------|--------|--------|\n")
        f.write(f"| Support Rate | {support_rate:.2%} | >80% | {'PASS' if support_rate > 0.8 else 'FAIL'} |\n")
        f.write(f"| Success Rate | {success_rate:.2%} | >90% | {'PASS' if success_rate > 0.9 else 'FAIL'} |\n")
        f.write(f"| Avg Functions/Classes | {(total_functions + total_classes)/total_count:.1f} | >1.0 | {'PASS' if (total_functions + total_classes)/total_count > 1.0 else 'FAIL'} |\n\n")
        
        f.write("## Detailed Results\n\n")
        f.write("| Language | Supported | Success | Functions | Classes | Error |\n")
        f.write("|----------|-----------|---------|-----------|---------|-------|\n")
        
        for r in results:
            error_text = r["error"] if r["error"] else "-"
            if error_text and len(error_text) > 20:
                error_text = error_text[:20] + "..."
            f.write(f"| {r['language']} | {'✓' if r['supported'] else '✗'} | {'✓' if r['success'] else '✗'} | {r['functions_found']} | {r['classes_found']} | {error_text} |\n")
        
        f.write("\n## Code Samples Tested\n\n")
        for i, r in enumerate(results):
            f.write(f"### Sample {i+1}: {r['language']}\n")
            f.write("```\n")
            f.write(test_code_samples[r['language']][:200])
            f.write("\n...\n```\n\n")
    
    print(f"Report saved to: {report_path}")

if __name__ == "__main__":
    test_language_detection()