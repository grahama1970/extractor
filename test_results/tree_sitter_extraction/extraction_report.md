# Tree-Sitter Code Metadata Extraction Test Report

## Summary
- **Total Samples**: 6
- **Successful Extractions**: 6 (100.00%)
- **Total Functions Found**: 10
- **Total Classes Found**: 5

## Performance Metrics
| Metric | Result | Target | Status |
|--------|--------|--------|--------|
| Success Rate | 100.00% | >90% | PASS |
| Average Functions/Classes | 2.5 | >1.0 | PASS |

## Detailed Results

| Language | Success | Functions | Classes | Error |
|----------|---------|-----------|---------|-------|
| python | ✓ | 3 | 1 | - |
| javascript | ✓ | 1 | 0 | - |
| java | ✓ | 2 | 2 | - |
| cpp | ✓ | 1 | 1 | - |
| ruby | ✓ | 1 | 1 | - |
| go | ✓ | 2 | 0 | - |

## Code Samples Tested

### Sample 1: python
```

def factorial(n):
    """Calculate factorial of n"""
    if n <= 1:
        return 1
    return n * factorial(n - 1)

class Calculator:
    def __init__(self):
        self.result = 0
    
    def ad
...
```

### Sample 2: javascript
```

function fetchData(url) {
    return fetch(url)
        .then(response => response.json())
        .then(data => {
            console.log('Data:', data);
            return data;
        });
}

cons
...
```

### Sample 3: java
```

public class Main {
    public static void main(String[] args) {
        System.out.println("Hello, World!");
        Calculator calc = new Calculator();
        int result = calc.add(5, 3);
    }
  
...
```

### Sample 4: cpp
```

#include <iostream>
#include <vector>

using namespace std;

class Shape {
public:
    virtual double area() = 0;
};

int main() {
    vector<int> numbers = {1, 2, 3, 4, 5};
    for (int n : numbers)
...
```

### Sample 5: ruby
```

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

per
...
```

### Sample 6: go
```

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

func main()
...
```

