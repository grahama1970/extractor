# Task List: Marker MCP Integration for Natrium (REVISED)

## Overview
This task list is based on the original 19 Natrium tasks. Marker is responsible for supporting Tasks 1 and 2 of the pipeline.

## Marker's Role in the 19-Task Pipeline

### Task 1: Extract Sections (extract_sections_001)
### Task 2: Parse Code Blocks (parse_code_blocks_001)

## Implementation Tasks

### Task 1.1: Create MCP Server with Extract Sections Support

**Goal**: Implement extract_sections to support Natrium Task 1

**Working Code Example**:

Create marker_mcp_server.py:

```python
#!/usr/bin/env python3
"""
Marker MCP Server - Supports Tasks 1 and 2 of Natrium pipeline
Based on original_natrium_task_list_gemini.md requirements
"""
from fastmcp import FastMCP
import re
import spacy
from pathlib import Path
from typing import Dict, List, Any
import hashlib

# Initialize MCP server
mcp = FastMCP(
    name="marker-mcp-server",
    version="0.1.0",
    description="PDF extraction for Natrium Tasks 1 and 2"
)

# Load spaCy as per original task requirements
nlp = spacy.load("en_core_web_sm")

@mcp.tool()
async def extract_sections(doc_path: str) -> dict:
    """
    Task 1: Extract hierarchical sections, requirements, and code blocks.
    Based on extract_sections_001 test requirements.
    
    Args:
        doc_path: Path to engineering document (PDF or markdown)
        
    Returns:
        Hierarchical structure with sections, requirements, code blocks
    """
    path = Path(doc_path)
    if not path.exists():
        return {"error": f"File not found: {doc_path}", "success": False}
    
    # Extract content based on file type
    if path.suffix == '.pdf':
        # Use marker's existing PDF extraction
        from marker.converters.pdf import PdfConverter
        converter = PdfConverter()
        content = converter.convert(path)
    else:
        content = path.read_text()
    
    # Hierarchical section pattern from original task
    section_pattern = re.compile(
        r'^(#{1,6}|\d+(?:\.\d+)*)\s+(.+?)$',
        re.MULTILINE
    )
    
    # Requirement patterns from original task
    requirement_patterns = [
        re.compile(r'(\w+[-\s]*\d+):\s*(.+?)\s+SHALL\s+(.+?)(?:\.|$)', re.IGNORECASE),
        re.compile(r'(\w+[-\s]*\d+):\s*(.+?)\s+MUST\s+(.+?)(?:\.|$)', re.IGNORECASE),
        re.compile(r'The\s+(.+?)\s+SHALL\s+(.+?)(?:\.|$)', re.IGNORECASE),
    ]
    
    # Code block pattern
    code_block_pattern = re.compile(
        r'```(\w*)\n(.*?)\n```',
        re.DOTALL
    )
    
    # Extract hierarchical sections
    sections = []
    for match in section_pattern.finditer(content):
        level_indicator = match.group(1)
        title = match.group(2)
        
        # Determine hierarchy level
        if level_indicator.startswith('#'):
            level = len(level_indicator)
        else:
            level = level_indicator.count('.') + 1
            
        sections.append({
            "level": level,
            "number": level_indicator,
            "title": title,
            "start_pos": match.start(),
            "text": ""  # Will be filled with section content
        })
    
    # Extract requirements
    requirements = []
    for pattern in requirement_patterns:
        for match in pattern.finditer(content):
            req_id = hashlib.md5(match.group(0).encode()).hexdigest()[:8]
            requirements.append({
                "id": req_id,
                "text": match.group(0),
                "type": "SHALL" if "SHALL" in match.group(0).upper() else "MUST",
                "section": _find_section_for_position(match.start(), sections)
            })
    
    # Extract code blocks
    code_blocks = []
    for match in code_block_pattern.finditer(content):
        language = match.group(1) or "unknown"
        code = match.group(2)
        code_blocks.append({
            "language": language,
            "content": code,
            "section": _find_section_for_position(match.start(), sections),
            "start_line": content[:match.start()].count('\n') + 1
        })
    
    return {
        "success": True,
        "sections": sections,
        "requirements": requirements,
        "code_blocks": code_blocks,
        "metadata": {
            "source": str(path),
            "total_sections": len(sections),
            "total_requirements": len(requirements),
            "total_code_blocks": len(code_blocks)
        }
    }

def _find_section_for_position(pos: int, sections: List[Dict]) -> str:
    """Find which section a position belongs to"""
    for i, section in enumerate(sections):
        if i + 1 < len(sections):
            if section["start_pos"] <= pos < sections[i + 1]["start_pos"]:
                return section["number"]
        else:
            if section["start_pos"] <= pos:
                return section["number"]
    return "0"  # Root level

@mcp.tool()
async def parse_code_blocks(code_blocks_json: list) -> dict:
    """
    Task 2: Parse code blocks using tree-sitter.
    Based on parse_code_blocks_001 test requirements.
    
    Args:
        code_blocks_json: List of code blocks from Task 1
        
    Returns:
        Parsed code with functions, classes, variables
    """
    from tree_sitter import Language, Parser
    import tree_sitter_python as tspython
    
    # Initialize tree-sitter
    PY_LANGUAGE = Language(tspython.language(), "python")
    parser = Parser()
    parser.set_language(PY_LANGUAGE)
    
    parsed_blocks = []
    
    for block in code_blocks_json:
        language = block.get("language", "unknown")
        content = block.get("content", "")
        
        if language == "python":
            tree = parser.parse(bytes(content, "utf8"))
            
            # Extract functions and classes as per original task
            functions = []
            classes = []
            
            def traverse(node, depth=0):
                if node.type == "function_definition":
                    func_name = None
                    for child in node.children:
                        if child.type == "identifier":
                            func_name = content[child.start_byte:child.end_byte]
                            break
                    if func_name:
                        functions.append({
                            "name": func_name,
                            "start_line": node.start_point[0] + 1,
                            "end_line": node.end_point[0] + 1
                        })
                        
                elif node.type == "class_definition":
                    class_name = None
                    for child in node.children:
                        if child.type == "identifier":
                            class_name = content[child.start_byte:child.end_byte]
                            break
                    if class_name:
                        classes.append({
                            "name": class_name,
                            "start_line": node.start_point[0] + 1,
                            "end_line": node.end_point[0] + 1
                        })
                
                for child in node.children:
                    traverse(child, depth + 1)
            
            traverse(tree.root_node)
            
            parsed_blocks.append({
                "language": language,
                "functions": functions,
                "classes": classes,
                "parse_success": True,
                "section": block.get("section"),
                "metadata": {
                    "total_functions": len(functions),
                    "total_classes": len(classes)
                }
            })
        else:
            # Non-Python languages - mark for manual review
            parsed_blocks.append({
                "language": language,
                "parse_success": False,
                "reason": f"Language {language} not supported by tree-sitter",
                "section": block.get("section"),
                "content": content  # Include for manual parsing
            })
    
    return {
        "success": True,
        "parsed_blocks": parsed_blocks,
        "total_blocks": len(parsed_blocks),
        "languages_found": list(set(b.get("language") for b in code_blocks_json))
    }

if __name__ == "__main__":
    import asyncio
    asyncio.run(mcp.run())
```

### Task 1.2: Add Validation Against Original Test Cases

**Goal**: Ensure outputs match expected format from original task list

**Validation Requirements**:
```python
# From original Task 1
assert "sections" in response
assert "requirements" in response  
assert "code_blocks" in response
assert all(req["type"] in ["SHALL", "MUST"] for req in response["requirements"])

# From original Task 2
assert "parsed_blocks" in response
assert all("functions" in block for block in response["parsed_blocks"] if block["language"] == "python")
```

### Task 1.3: Integration with Claude Evaluation

**Goal**: Support Claude evaluation pipeline from original tasks

The output must be structured for Claude evaluation as defined in Task 1:
- Include confidence scoring hooks
- Support halt conditions (confidence < 0.7)
- Provide clear extraction explanations

### Task 1.4: Handle Hierarchical Document Structures

**Goal**: Support complex engineering documents as per original examples

Must handle:
- Numbered sections (1, 1.1, 1.1.1)
- Markdown headers (##, ###)
- Mixed hierarchies
- Cross-references

### Task 1.5: Create Test Suite Based on Original Tests

**Goal**: Implement tests for extract_sections_001 and parse_code_blocks_001

Create tests/test_natrium_integration.py:
```python
import pytest
from marker_mcp_server import extract_sections, parse_code_blocks

async def test_extract_sections_001():
    """Test from original Natrium task list"""
    result = await extract_sections("test_documents/engineering_spec.md")
    
    assert result["success"] == True
    assert "sections" in result
    assert "requirements" in result
    assert "code_blocks" in result
    
    # Verify hierarchical structure
    sections = result["sections"]
    assert any(s["level"] == 1 for s in sections)
    assert any(s["level"] == 2 for s in sections)
    
    # Verify requirements extraction
    requirements = result["requirements"]
    assert len(requirements) > 0
    assert all(req["type"] in ["SHALL", "MUST"] for req in requirements)

async def test_parse_code_blocks_001():
    """Test from original Natrium task list"""
    # First extract code blocks
    extract_result = await extract_sections("test_documents/engineering_spec.md")
    code_blocks = extract_result["code_blocks"]
    
    # Then parse them
    parse_result = await parse_code_blocks(code_blocks)
    
    assert parse_result["success"] == True
    assert "parsed_blocks" in parse_result
    
    # Verify Python parsing
    python_blocks = [b for b in parse_result["parsed_blocks"] if b["language"] == "python"]
    assert all("functions" in block for block in python_blocks)
    assert all("classes" in block for block in python_blocks)
```

## Validation Checklist

Based on original task requirements:

- [ ] Extract hierarchical sections with proper nesting
- [ ] Extract SHALL/MUST requirements with IDs
- [ ] Extract code blocks with language detection
- [ ] Parse Python code blocks with tree-sitter
- [ ] Identify functions and classes in code
- [ ] Support PDF and markdown inputs
- [ ] Output format matches test expectations
- [ ] Ready for Claude evaluation (confidence scoring)
- [ ] Handle ambiguous sections appropriately
- [ ] Performance acceptable for large documents

## Dependencies to Add

```toml
[project.dependencies]
spacy = ">=3.0.0"
tree-sitter = ">=0.20.0"
tree-sitter-python = ">=0.20.0"
fastmcp = ">=0.1.0"
```

## Notes

This implementation directly supports Tasks 1 and 2 from the original 19-task Natrium pipeline. The outputs are structured to feed into Task 3 (formalization) which will be handled by Claude Max Proxy.
