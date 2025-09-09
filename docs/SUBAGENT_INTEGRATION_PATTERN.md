# Sub-Agent Integration Pattern for Extractor

## Key Insight
Instead of writing direct database code or implementing complex logic, use specialized sub-agents:

### Current Sub-Agents Available

1. **knowledge_architect** (`/.claude/agents/knowledge_architect.md`)
   - Query historical patterns
   - Store learning outcomes
   - Find similar PDF blocks
   - Track pattern evolution

2. **code_reviewer** (if available)
   - Review extraction logic
   - Suggest improvements
   - Validate patterns

3. **researcher** (if available)
   - Find best practices for PDF extraction
   - Research edge cases
   - Compare extraction methods

## Pattern: Using Sub-Agents in Processors

Instead of:
```python
class PatternAwareHeaderProcessor(BaseProcessor):
    def __init__(self):
        self.db = DatabaseArchitect(config)  # ❌ Direct DB code
        
    async def query_patterns(self):
        cursor = self.db.aql.execute(...)  # ❌ Writing queries
```

Do this:
```python
class PatternAwareHeaderProcessor(BaseProcessor):
    async def query_patterns(self, text):
        # ✅ Use sub-agent via Task tool
        result = await Task(
            description="Query similar headers",
            prompt=f'''You are the Knowledge Architect. 
            Find similar PDF blocks to: "{text}"
            Check if they were headers or not.'''
        )
        return result
```

## Integration Points

### 1. During Extraction
```python
# In SectionHeaderProcessor
if self._is_suspicious_header(block):
    # Ask knowledge_architect to record this pattern
    Task(
        description="Record header pattern",
        prompt=f"Record that '{text}' is NOT a header because {reason}"
    )
```

### 2. After Extraction
```python
# In unified_extractor
if result["success"]:
    # Ask knowledge_architect to analyze extraction
    Task(
        description="Analyze extraction patterns",
        prompt=f"Analyze PDF {pdf_path} extraction. Found {n} headers..."
    )
```

### 3. Learning Loop
```python
# Periodic pattern mining
Task(
    description="Mine header patterns",
    prompt="Find common patterns in misclassified headers from last week"
)
```

## Benefits

1. **Separation of Concerns**: Each agent focuses on their expertise
2. **No Infrastructure Code**: Sub-agents handle DB connections, queries, etc.
3. **Natural Language Interface**: Describe what you need, not how to do it
4. **Collective Intelligence**: Agents can collaborate and share insights

## Example: Complete Integration

```python
class SmartSectionHeaderProcessor(SectionHeaderProcessor):
    def __call__(self, document: Document):
        # Regular processing
        super().__call__(document)
        
        # Learn from this extraction
        self._record_extraction_patterns(document)
        
    def _record_extraction_patterns(self, document):
        # Delegate to knowledge_architect
        Task(
            description="Record extraction patterns",
            prompt=f'''You are the Knowledge Architect.
            
            We just processed a PDF with these results:
            - Total headers found: {header_count}
            - Headers rejected for ending with comma: {comma_count}
            - Suspicious patterns found: {patterns}
            
            Please:
            1. Record these patterns for future use
            2. Check if we've seen similar patterns before
            3. Update confidence scores for our rules
            '''
        )
```

## Remember

- **Sub-agents are specialists**: Use them for their expertise
- **Task tool is the interface**: Natural language requests to sub-agents
- **Don't reimplement**: If a sub-agent can do it, let them
- **Collective learning**: Every extraction improves the system