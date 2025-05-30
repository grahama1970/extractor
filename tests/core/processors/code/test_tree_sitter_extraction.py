"""
Test script for verifying the tree-sitter language detection integration.

This script directly tests the tree-sitter code metadata extraction functionality
without using any mocked components, in accordance with project standards.
"""
import json
import os
from pathlib import Path
from marker.services.utils.tree_sitter_utils import extract_code_metadata

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
    """Test the tree-sitter code metadata extraction directly without mocks."""
    print("Testing tree-sitter code metadata extraction...")
    
    # Create output directory
    output_dir = Path("test_results/tree_sitter_extraction")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    results = []
    
    # For each sample, test the metadata extraction
    for lang, code in test_code_samples.items():
        print(f"\nTesting extraction for {lang}...")
        
        # Extract metadata using tree-sitter directly
        metadata = extract_code_metadata(code, lang)
        
        # Check if extraction was successful
        success = metadata.get('tree_sitter_success', False)
        
        # Check if any functions or classes were found
        functions_found = len(metadata.get('functions', []))
        classes_found = len(metadata.get('classes', []))
        
        result = {
            "language": lang,
            "success": success,
            "functions_found": functions_found,
            "classes_found": classes_found,
            "error": metadata.get('error'),
            "code_preview": code[:100].replace('\n', '\\n') + "..."
        }
        
        results.append(result)
        
        print(f"  Success: {'✓' if success else '✗'}")
        print(f"  Functions found: {functions_found}")
        print(f"  Classes found: {classes_found}")
        if not success:
            print(f"  Error: {metadata.get('error')}")
        
        # Print function details if any found
        if functions_found > 0:
            print(f"  Functions:")
            for i, func in enumerate(metadata.get('functions', [])[:3]):  # Show up to 3 functions
                print(f"    {i+1}. {func.get('name', 'unnamed')} - {len(func.get('parameters', []))} parameters")
    
    # Calculate summary statistics
    success_count = sum(1 for r in results if r["success"])
    total_count = len(results)
    success_rate = success_count / total_count if total_count > 0 else 0
    
    total_functions = sum(r["functions_found"] for r in results)
    total_classes = sum(r["classes_found"] for r in results)
    
    print(f"\nSummary:")
    print(f"Total samples tested: {total_count}")
    print(f"Successful extractions: {success_count} ({success_rate:.2%})")
    print(f"Total functions found: {total_functions}")
    print(f"Total classes found: {total_classes}")
    
    # Save results to JSON file
    summary = {
        "total_samples": total_count,
        "successful_extractions": success_count,
        "success_rate": success_rate,
        "total_functions": total_functions,
        "total_classes": total_classes,
        "results": results
    }
    
    results_file = output_dir / "extraction_results.json"
    with open(results_file, 'w') as f:
        json.dump(summary, f, indent=2)
        
    print(f"\nDetailed results saved to: {results_file}")
    
    # Generate a Markdown report
    report_path = output_dir / "extraction_report.md"
    
    with open(report_path, 'w') as f:
        f.write("# Tree-Sitter Code Metadata Extraction Test Report\n\n")
        f.write("## Summary\n")
        f.write(f"- **Total Samples**: {total_count}\n")
        f.write(f"- **Successful Extractions**: {success_count} ({success_rate:.2%})\n")
        f.write(f"- **Total Functions Found**: {total_functions}\n")
        f.write(f"- **Total Classes Found**: {total_classes}\n\n")
        
        f.write("## Performance Metrics\n")
        f.write("| Metric | Result | Target | Status |\n")
        f.write("|--------|--------|--------|--------|\n")
        f.write(f"| Success Rate | {success_rate:.2%} | >90% | {'PASS' if success_rate > 0.9 else 'FAIL'} |\n")
        f.write(f"| Average Functions/Classes | {(total_functions + total_classes)/total_count:.1f} | >1.0 | {'PASS' if (total_functions + total_classes)/total_count > 1.0 else 'FAIL'} |\n\n")
        
        f.write("## Detailed Results\n\n")
        f.write("| Language | Success | Functions | Classes | Error |\n")
        f.write("|----------|---------|-----------|---------|-------|\n")
        
        for r in results:
            error_text = r["error"] if r["error"] else "-"
            if error_text and len(error_text) > 20:
                error_text = error_text[:20] + "..."
            f.write(f"| {r['language']} | {'✓' if r['success'] else '✗'} | {r['functions_found']} | {r['classes_found']} | {error_text} |\n")
        
        f.write("\n## Code Samples Tested\n\n")
        for i, r in enumerate(results):
            f.write(f"### Sample {i+1}: {r['language']}\n")
            f.write("```\n")
            f.write(test_code_samples[r['language']][:200])
            f.write("\n...\n```\n\n")
    
    print(f"Report saved to: {report_path}")

if __name__ == "__main__":
    test_language_detection()