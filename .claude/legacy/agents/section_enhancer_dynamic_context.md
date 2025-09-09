# Dynamic Context Loading for Section Enhancement

## The Challenge

When spawning 10 concurrent sub-agents for section enhancement, each section might need different context:
- Section 1: Has tables → needs Camelot, pandas, table workers
- Section 2: Just text → needs only text cleaning
- Section 3: Has equations → needs LaTeX templates, math workers
- Section 4: Has forms → needs form templates and processors

## Solution Approaches

### Approach 1: Pre-Analysis Categorization (Recommended)

The orchestrator analyzes all sections FIRST, then creates context-aware batches:

```python
# In section_enhancer_orchestrator.py

def create_context_aware_batches(self, sections_file: str) -> Dict[str, Any]:
    """
    Analyze sections first, then batch by content type with appropriate context.
    """
    with open(sections_file) as f:
        all_sections = json.load(f)['sections']
    
    # Categorize sections by content type
    categorized = {
        'text_only': [],
        'table_heavy': [],
        'math_heavy': [],
        'form_sections': [],
        'mixed_complex': []
    }
    
    for section in all_sections:
        content_types = self._analyze_section_content(section)
        
        if content_types == ['Text']:
            categorized['text_only'].append(section)
        elif 'Table' in content_types and len(content_types) > 2:
            categorized['table_heavy'].append(section)
        elif 'Equation' in content_types or 'Math' in content_types:
            categorized['math_heavy'].append(section)
        elif 'Form' in content_types:
            categorized['form_sections'].append(section)
        else:
            categorized['mixed_complex'].append(section)
    
    # Create specialized batches with targeted prompts
    batches = []
    
    # Text-only batch with minimal context
    if categorized['text_only']:
        batches.append({
            'batch_id': 'text_batch_001',
            'sections': categorized['text_only'][:20],  # Can handle more simple sections
            'prompt_file': 'section_enhancer_text_only.md',
            'context': {
                'workers': ['text_cleaning', 'block_merger', 'block_consolidator'],
                'skip_tools': ['camelot', 'pandas', 'equation_processors']
            }
        })
    
    # Table-heavy batch with full table context
    if categorized['table_heavy']:
        batches.append({
            'batch_id': 'table_batch_001',
            'sections': categorized['table_heavy'][:5],  # Fewer due to complexity
            'prompt_file': 'section_enhancer_table_focused.md',
            'context': {
                'workers': ['camelot', 'pandas_analyzer', 'table_merger', 'table_header_fixer'],
                'templates': ['llm_table.py patterns'],
                'emphasis': 'Compare extraction methods, use visual validation'
            }
        })
    
    # Math batch with equation context
    if categorized['math_heavy']:
        batches.append({
            'batch_id': 'math_batch_001', 
            'sections': categorized['math_heavy'][:10],
            'prompt_file': 'section_enhancer_math_focused.md',
            'context': {
                'workers': ['equation', 'text_cleaning'],
                'templates': ['llm_equation.py', 'llm_mathblock.py', 'llm_inlinemath.py'],
                'emphasis': 'Extract equation regions for clear LaTeX conversion'
            }
        })
    
    return {
        'batches': batches,
        'total_sections': len(all_sections),
        'batch_count': len(batches)
    }

def _analyze_section_content(self, section: Dict) -> List[str]:
    """Determine what content types are in this section."""
    content_types = set()
    
    for block in section.get('blocks', []):
        block_type = block.get('block_type', 'Unknown')
        content_types.add(block_type)
        
        # Also check text content for hints
        text = block.get('text', '').lower()
        if any(indicator in text for indicator in ['$', '\\frac', '\\sum', '=']):
            content_types.add('Math')
        if any(indicator in text for indicator in ['<input', '<form', 'checkbox']):
            content_types.add('Form')
            
    return list(content_types)
```

### Approach 2: Tiered Prompts

Create different prompt levels that sub-agents can choose from:

```markdown
# section_enhancer_tiered.md

You are enhancing sections. First, determine the complexity level:

## Quick Assessment
Look at your section's content types:
- Only text blocks → Use Tier 1 (Simple)
- Has tables → Use Tier 2 (Tables) 
- Has math/equations → Use Tier 3 (Math)
- Has forms → Use Tier 4 (Forms)
- Multiple complex types → Use Tier 5 (Full)

## Tier 1: Simple Text Enhancement
Minimal toolset for text-only sections:
```bash
python text_cleaning.py analyze section.json
python block_consolidator.py merge section.json
```

## Tier 2: Table Enhancement
[Include all table-specific guidance and tools]

## Tier 3: Math Enhancement  
[Include all math-specific guidance and tools]

## Tier 4: Form Enhancement
[Include all form-specific guidance and tools]

## Tier 5: Full Enhancement
[Include everything for complex sections]
```

### Approach 3: Dynamic Worker Loading in Prompt

Let the agent decide which workers to load based on initial inspection:

```markdown
# section_enhancer_dynamic.md

## Phase 1: Content Assessment

First, examine your section to determine needed tools:

```bash
# Quick content analysis
cat section.json | jq '.blocks[].block_type' | sort | uniq -c

# Visual inspection
python semantic_section_processor.py create-image section.json --pdf doc.pdf
```

Based on what you find, load only relevant context:

### If you see tables:
```bash
# Load table context
python camelot_extractor.py --help
python pandas_analyzer.py --help
python table_merger_worker.py --help

# Now you know these tools are available
```

### If you see equations:
```bash
# Load math context
cat llm_equation.py | grep "prompt ="  # See the template
cat llm_mathblock.py | grep "prompt ="  # See the template
```

### If you see forms:
```bash
# Load form context
cat llm_form.py | grep "prompt ="  # See the template
```

## Phase 2: Enhancement
Now use only the tools you loaded context for...
```

### Approach 4: Hybrid - Smart Batching + Fallback

Combine approaches for flexibility:

```python
# Create mostly homogeneous batches, but include fallback for outliers

def create_smart_batches(self, sections):
    # Primary categorization
    categorized = self._categorize_sections(sections)
    
    # Create specialized batches (80% of sections)
    specialized_batches = self._create_specialized_batches(categorized)
    
    # Create mixed batches for outliers (20% of sections)
    mixed_batch = {
        'batch_id': 'mixed_001',
        'sections': categorized['outliers'][:5],
        'prompt_file': 'section_enhancer_adaptive.md',  # Has all tools but guides dynamic use
        'context': {
            'strategy': 'Assess each section individually and load appropriate tools',
            'all_workers_available': True,
            'use_tiered_approach': True
        }
    }
    
    return specialized_batches + [mixed_batch]
```

## Recommendation: Approach 1 + Approach 3

**Best practice**: Combine smart batching with dynamic loading guidance:

1. **Orchestrator** does pre-analysis and creates content-aware batches
2. **Specialized prompts** for each batch type (text-only, table-heavy, etc.)
3. **Dynamic loading guidance** within each prompt for edge cases

This gives you:
- Efficiency from homogeneous batches
- Flexibility for sections that don't fit perfectly
- Reduced context overhead for simple sections
- Full context available when truly needed

Example implementation in orchestrator:

```python
# The orchestrator would output:
{
    "manifest": {
        "batches": [
            {
                "batch_id": "text_001",
                "section_count": 20,
                "prompt": "section_enhancer_text_only.md",
                "primary_tools": ["text_cleaning", "block_merger"],
                "excluded_tools": ["camelot", "math_processors"]
            },
            {
                "batch_id": "table_001", 
                "section_count": 5,
                "prompt": "section_enhancer_table_focused.md",
                "primary_tools": ["camelot", "pandas", "table_workers"],
                "excluded_tools": ["form_processors"]
            }
        ]
    }
}
```

This way, each sub-agent gets a focused prompt with only the relevant context for their batch type!