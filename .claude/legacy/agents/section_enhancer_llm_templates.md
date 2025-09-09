# Section Enhancement - LLM Prompt Templates

## Using LLM Processors as Templates

The files in `/src/extractor/core/processors/llm/` are NOT tools to call. They are EXAMPLES showing you how to structure LLM prompts for specific content types.

### Form Processing Template
From `llm_form.py`:
```python
form_rewriting_prompt = """I'm going to send you an image of a form and HTML for the form.
Please rewrite the HTML, based on the image, to correct any structural issues and formatting.
Return only the HTML in a code block.
"""
```

**When you encounter forms**, use this pattern:
- Send the form image AND current HTML/text
- Ask for structural corrections
- Focus on fixing labels, inputs, field associations

### Handwriting Extraction Template  
From `llm_handwriting.py`:
```python
handwriting_generation_prompt = """You are an expert at reading handwriting.
I'm going to send you an image of a handwritten block, and I want you to return
the text of the handwriting, with any simple formatting converted to markdown.
Do not include any explanation, just the text.
"""
```

**When you encounter handwriting**, use this pattern:
- Send ONLY the handwritten region image
- Ask for direct text extraction
- Request markdown formatting for structure

### Equation Conversion Template
From `llm_equation.py`:
```python
equation_latex_prompt = r"""Convert the equation in this image to LaTeX.
Make it well-formatted and correct any errors you see.
Do not include $ or $$ delimiters.
"""
```

**When you encounter equations**, use this pattern:
- Send the equation image
- Request LaTeX output
- Specify NO delimiters (you add them based on context)

### Your Enhancement Prompts Should Follow These Patterns

#### Example: Fixing a Form in a Section

```markdown
I have a form block that appears broken. Here's the context:

**Visual appearance** (from section image):
[Image shows a form with 3 input fields and labels above them]

**Current extraction**:
```
Name: [    ]
Email: [    ]
Phone: [    ]
```

**Issues identified**:
- Labels not properly associated with inputs
- Missing form structure tags
- No field types specified

Please provide the corrected structure maintaining the visual layout.
```

#### Example: Extracting Handwritten Annotation

```markdown
I have a handwritten annotation on this PDF section:

**Image of handwritten text**:
[Cropped image of just the handwriting]

**Context**: This appears next to a table about signal specifications.

Please extract the handwritten text. Return only the text content.
```

#### Example: Converting Complex Equation

```markdown
This section contains a mathematical equation that needs proper formatting:

**Equation image**:
[Image of equation]

**Current OCR text**: "E = mc2"

**Context**: This is in a physics section about relativity.

Convert to proper LaTeX format. Consider superscripts and special symbols.
```

### Pattern Recognition from Templates

The LLM processor files teach you:

1. **Be specific about input format** (image + text/HTML)
2. **Give clear output requirements** (LaTeX, HTML, plain text)
3. **Provide context when helpful** (section type, surrounding content)
4. **Keep prompts focused** on one task (convert, extract, fix)

### Visual Understanding Pattern

From `clip_visual_processor.py` concepts:

```markdown
I need to understand what this figure represents:

**Figure image**:
[Image of diagram]

**Surrounding text mentions**: "BHT module", "signal flow", "prediction logic"

**Current caption**: "Figure 4.1"

What does this diagram show? Provide a descriptive caption.
```

## Remember

- These files are TEMPLATES, not tools to execute
- They show best practices for LLM prompts
- Adapt the patterns to your specific enhancement needs
- Include both visual (image) and textual context when available