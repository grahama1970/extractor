# Section Enhancement - Using LLM Processors

## Additional Context Providers

Beyond the basic tools, you have specialized LLM processors that provide context for specific content types:

### Form Processing
```bash
# When you encounter form elements
python llm_form.py analyze section_001.json
```
**Context it provides:**
- Identifies form fields, labels, input types
- Detects broken form structure (missing labels, orphaned inputs)
- Suggests proper HTML form structure
- Flags suspicious forms (too short, malformed)

**When to use:** Blocks containing form elements, input fields, checkboxes, dropdowns

### Handwriting Processing  
```bash
# When you encounter handwritten content
python llm_handwriting.py extract section_001.json
```
**Context it provides:**
- OCR for handwritten text
- Confidence scores for recognition
- Flags very short results as suspicious
- Converts handwriting to typed text

**When to use:** Blocks marked as "Handwriting" or containing handwritten annotations

### Equation Processing
```bash
# For mathematical equations
python llm_equation.py convert section_001.json
```
**Context it provides:**
- Converts equation images to LaTeX
- Formats mathematical notation properly
- Handles both display and inline equations
- Minimum height threshold (6% of page height)

**When to use:** Blocks marked as "Equation" or containing mathematical symbols

### Inline Math Processing
```bash
# For math within text
python llm_inlinemath.py process section_001.json
```
**Context it provides:**
- Identifies inline mathematical expressions
- Converts to proper LaTeX notation (e.g., $x^2 + y^2 = z^2$)
- Preserves surrounding text context

**When to use:** Text blocks containing mathematical expressions mixed with regular text

### Math Block Processing
```bash
# For larger mathematical content
python llm_mathblock.py process section_001.json  
```
**Context it provides:**
- Handles multi-line equations
- Complex mathematical proofs or derivations
- Matrix notation and advanced formatting

**When to use:** Large blocks of mathematical content spanning multiple lines

### Visual Understanding (CLIP)
```bash
# For visual similarity and understanding
python clip_visual_processor.py analyze section_001.json --query "circuit diagram"
```
**Context it provides:**
- Visual embeddings for images/figures
- Similarity matching with knowledge base
- Visual search capabilities
- Multi-modal understanding (text + image)

**When to use:** 
- When you need to understand what's in an image
- To find visually similar content in knowledge base
- For figure/diagram classification

## Enhanced Decision Process

### Example: Section with Mixed Content

```bash
# 1. Initial analysis shows mixed content types
cat section_005.json | jq '.blocks[].block_type' | sort | uniq -c
> 2 Text
> 1 Equation  
> 1 Form
> 1 Figure

# 2. Get specialized context for each type

# For the equation
python llm_equation.py convert section_005.json --block-id eq_001
> "LaTeX: E = mc^2, confidence: 0.95"

# For the form  
python llm_form.py analyze section_005.json --block-id form_001
> "Form structure: 3 inputs missing labels, suggest restructuring"

# For the figure
python clip_visual_processor.py analyze section_005.json --block-id fig_001
> "Visual match: Circuit diagram showing BHT module connections"

# 3. Make informed decisions
Based on LLM context:
- Equation needs LaTeX formatting
- Form needs label associations fixed
- Figure needs caption from visual understanding
```

### Example: Handwritten Annotations

```bash
# Detect handwritten content
python annotation_extractor.py find-handwritten section_002.json annotations.json
> "Found handwritten note at bbox [100, 200, 300, 250]"

# Extract the handwriting
python llm_handwriting.py extract section_002.json --bbox 100,200,300,250  
> "Extracted text: 'Important: This table continues on next page'"

# Use this context to guide enhancement
Decision: Merge table with next page based on handwritten note
```

### Example: Complex Mathematical Section

```bash
# Section full of equations
python llm_mathblock.py analyze section_008.json
> "Contains: 3 equation blocks, 2 inline expressions, 1 matrix"

# Process each appropriately
python llm_equation.py batch-convert section_008.json
> "Converted 3 display equations to LaTeX"

python llm_inlinemath.py process section_008.json
> "Fixed inline math: 'x2' → '$x^2$', 'sum from i=1 to n' → '$\sum_{i=1}^{n}$'"

# Visual validation of math rendering
python math_validator.py check-rendering section_008_enhanced.json
> "All equations render correctly in LaTeX"
```

## Integration Pattern

```python
def gather_llm_context(section):
    context = {}
    
    # Check each block type and get appropriate LLM context
    for block in section['blocks']:
        if block['type'] == 'Equation':
            context[block['id']] = llm_equation.convert(block)
        elif block['type'] == 'Form':
            context[block['id']] = llm_form.analyze(block)
        elif block['type'] == 'Handwriting':
            context[block['id']] = llm_handwriting.extract(block)
        elif 'math' in block.get('text', '').lower():
            context[block['id']] = llm_inlinemath.process(block)
        elif block['type'] == 'Figure':
            context[block['id']] = clip_visual.analyze(block)
            
    return context
```

## Remember

These LLM processors provide **specialized context** for specific content types. They don't make decisions - they give you information to make better decisions:

- **Forms**: Structure analysis and repair suggestions
- **Handwriting**: Text extraction from handwritten content
- **Equations**: LaTeX conversion and formatting
- **Visual**: Understanding what's in images/figures

Use them when you encounter their specific content types to get expert-level context for your enhancement decisions.