# Semantic Agents Architecture Fix

## The Problem

Currently, semantic agents run in Stage 5 (LLM Enhancement) AFTER marker has already made all extraction decisions. This is fundamentally wrong because:

1. **Too Late**: By Stage 5, the document structure is already set
2. **Limited Context**: Agents can only see marker's output, not the original decision context
3. **Band-aid Approach**: Agents try to "fix" mistakes instead of preventing them
4. **Lost Information**: Original Surya predictions, Camelot results, spatial analysis are not available

## The Solution: Integrate Semantic Agents INTO Extraction

### Current Architecture (WRONG)
```
Marker Extraction → Fixed Structure → Semantic Agents Try to Fix
```

### Correct Architecture
```
Marker + Semantic Agents → Correct Structure First Time
```

## Implementation: Enhanced Marker Processor

```python
class SemanticMarkerProcessor:
    """Enhanced marker processor that uses semantic agents during extraction."""
    
    def __init__(self):
        self.table_merger_agent = SemanticTableMerger()
        self.section_fixer_agent = SemanticSectionFixer()
        self.text_merger_agent = SemanticTextMerger()
        
    async def process_blocks(self, raw_blocks, surya_data, page_images):
        """Process blocks with semantic agent assistance."""
        
        enhanced_blocks = []
        
        for i, block in enumerate(raw_blocks):
            # 1. BEFORE classifying, gather ALL context
            context = await self._gather_block_context(
                block, 
                raw_blocks, 
                surya_data,
                page_images,
                nearby_blocks=raw_blocks[max(0,i-2):i+3]
            )
            
            # 2. Classification decision WITH semantic agent
            if block.get("potential_type") == "table":
                # Check if this should merge with nearby tables
                merge_decision = await self.table_merger_agent.analyze_merge(
                    block,
                    context.nearby_tables,
                    context.pandas_analysis,
                    context.camelot_results,
                    context.surya_predictions,
                    context.spatial_info
                )
                
                if merge_decision.should_merge:
                    block = self._merge_tables(block, merge_decision)
                    
            elif block.get("potential_type") == "header":
                # Verify this is really a header
                header_decision = await self.section_fixer_agent.verify_header(
                    block,
                    context.surrounding_text,
                    context.document_structure,
                    context.annotations
                )
                
                if not header_decision.is_valid_header:
                    block["block_type"] = "Text"
                    
            enhanced_blocks.append(block)
            
        return enhanced_blocks
```

## Semantic Agent Integration Points

### 1. Table Merge Decision (DURING extraction)
```python
# When marker finds potential table blocks
async def should_merge_tables(self, table1, table2, full_context):
    """Called DURING extraction when adjacent tables detected."""
    
    # Gather ALL available data
    context = TableContext(
        table1_data=table1,
        table2_data=table2,
        surya_predictions=full_context.surya_model_output,
        camelot_results=await self._try_camelot_extraction(table1, table2),
        pandas_stats=await self._analyze_with_pandas(table1, table2),
        annotations=full_context.annotations_nearby,
        spatial_info=self._calculate_spatial_relationship(table1, table2),
        page_renders=full_context.page_images
    )
    
    # Semantic agent makes decision WITH FULL CONTEXT
    decision = await self.table_merger_agent.make_merge_decision(context)
    
    return decision
```

### 2. Section Header Validation (DURING extraction)
```python
# When marker finds potential section header
async def validate_section_header(self, potential_header, full_context):
    """Called DURING extraction for each potential header."""
    
    context = HeaderContext(
        text=potential_header.text,
        position=potential_header.bbox,
        font_info=potential_header.font_data,
        surrounding_blocks=full_context.nearby_blocks,
        document_outline=full_context.current_outline,
        annotations=full_context.annotations,
        historical_patterns=await self._query_header_patterns(potential_header)
    )
    
    # Semantic agent validates WITH FULL CONTEXT
    validation = await self.section_fixer_agent.validate_header(context)
    
    return validation
```

### 3. Text Block Merging (DURING extraction)
```python
# When marker finds text blocks that might be split
async def should_merge_text_blocks(self, text1, text2, full_context):
    """Called DURING extraction for potentially split paragraphs."""
    
    context = TextContext(
        block1=text1,
        block2=text2,
        linguistic_analysis=await self._analyze_text_continuity(text1, text2),
        layout_analysis=full_context.layout_data,
        annotations=full_context.annotations
    )
    
    # Semantic agent decides WITH FULL CONTEXT
    merge_decision = await self.text_merger_agent.should_merge(context)
    
    return merge_decision
```

## Key Differences

### OLD: Stage 5 Cleanup
- Sees only marker output
- Missing original context
- Can only try to fix mistakes
- No access to Surya/Camelot/spatial data

### NEW: Stage 2 Integration  
- Sees EVERYTHING during extraction
- Full context for every decision
- Prevents mistakes from happening
- Access to all data sources simultaneously

## Benefits

1. **Accuracy**: Decisions made with full context
2. **Efficiency**: No need to fix mistakes later
3. **Learning**: Agents learn from actual extraction decisions
4. **Flexibility**: Easy to add new context sources
5. **Transparency**: Clear decision trail for each block

## Implementation Priority

1. **Table Merger Agent** - Most critical for document quality
2. **Section Fixer Agent** - Prevents navigation issues  
3. **Text Merger Agent** - Improves readability

## Conclusion

The semantic agents must be integrated INTO the extraction process, not applied afterward. This requires refactoring the marker processor to call semantic agents at decision points, providing them with ALL available context to make intelligent decisions the first time.