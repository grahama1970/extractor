# Suspicious Block Detection in Marker-PDF Extraction

## Overview

Yes, we still use marker-pdf for the initial extraction, but **WITHOUT the --use_llm flag**. Instead, we implement smart suspicious block detection that identifies which blocks need sub-agent validation.

## How Suspicious Block Detection Works

### 1. During Marker Extraction (Group 2)

```python
class EnhancedMarkerExtractor:
    """Marker extraction with suspicious block flagging."""
    
    def extract_with_suspicious_flags(self, pdf_path: str) -> Dict:
        # Run marker WITHOUT --use_llm
        blocks = marker_extract(pdf_path, use_llm=False)
        
        # Flag suspicious blocks
        suspicious_blocks = []
        for i, block in enumerate(blocks):
            suspicion_score, reasons = self.analyze_block(block, i, blocks)
            if suspicion_score > 0:
                suspicious_blocks.append({
                    "index": i,
                    "type": block.type,
                    "score": suspicion_score,
                    "reasons": reasons
                })
        
        return {
            "blocks": blocks,
            "suspicious": suspicious_blocks,
            "total_blocks": len(blocks),
            "suspicious_count": len(suspicious_blocks)
        }
```

### 2. Suspicious Pattern Detection

```mermaid
graph TD
    subgraph "Header Suspicion Patterns"
        H1[Ends with comma] --> S1[Score: 0.9]
        H2[Starts with 'As' or 'For'] --> S2[Score: 0.8]
        H3[Split across blocks] --> S3[Score: 0.95]
        H4[All lowercase] --> S4[Score: 0.7]
        H5[Very short <3 chars] --> S5[Score: 0.85]
    end
    
    subgraph "Table Suspicion Patterns"
        T1[Low Surya confidence] --> S6[Score: 0.9]
        T2[Irregular cell count] --> S7[Score: 0.8]
        T3[Split across pages] --> S8[Score: 0.95]
        T4[No clear headers] --> S9[Score: 0.7]
    end
    
    subgraph "Text Suspicion Patterns"
        TX1[Hyphenated at end] --> S10[Score: 0.6]
        TX2[Starts mid-sentence] --> S11[Score: 0.7]
        TX3[Orphaned single line] --> S12[Score: 0.5]
    end
```

### 3. Workflow Planner Analysis (Group 3)

```python
def analyze_suspicious_blocks(blocks: List[Dict], suspicious: List[Dict]) -> Dict:
    """Workflow planner creates targeted processing plan."""
    
    plan = {
        "headers_to_validate": [],
        "tables_to_reprocess": [],
        "blocks_to_merge": [],
        "figures_to_analyze": []
    }
    
    # Group suspicious blocks by type
    for sus in suspicious:
        block = blocks[sus["index"]]
        
        if block["type"] == "SectionHeader":
            # ALL headers need validation for structure
            plan["headers_to_validate"].append(sus["index"])
            
        elif block["type"] == "Table" and sus["score"] > 0.8:
            # High suspicion tables need reprocessing
            plan["tables_to_reprocess"].append({
                "index": sus["index"],
                "method": "camelot" if "low_confidence" in sus["reasons"] else "llm"
            })
            
        elif "split" in sus["reasons"]:
            # Find adjacent blocks to merge
            plan["blocks_to_merge"].append({
                "indices": [sus["index"], sus["index"] + 1],
                "type": "merge_split"
            })
    
    return plan
```

## Real Example: BHT PDF Suspicious Blocks

```mermaid
flowchart TD
    subgraph "Marker Extraction Results"
        B1[Block 0: Image - OK]
        B2[Block 1: '1. INTRODUCTION' - OK]
        B11[Block 11: 'Descripti' - SUSPICIOUS]
        B12[Block 12: 'on' - SUSPICIOUS]
        B17[Block 17: 'For any HW configuration,' - SUSPICIOUS]
        B23[Block 23: TABLE I - Low confidence]
        B42[Block 42: 'As can be seen' - SUSPICIOUS]
    end
    
    subgraph "Workflow Planner Decision"
        B11 & B12 --> MERGE[Merge Split Header]
        B17 --> VALIDATE1[Validate: Comma ending]
        B23 --> CAMELOT[Reprocess with Camelot]
        B42 --> VALIDATE2[Validate: Starts with 'As']
    end
    
    subgraph "Sub-Agent Assignment"
        VALIDATE1 --> SA1[pdf_section_header agent]
        VALIDATE2 --> SA1
        CAMELOT --> SA2[pdf_table_analyzer agent]
        MERGE --> SA3[pdf_block_merger agent]
    end
```

## Efficiency Gains

### Traditional Marker with --use_llm
```
Every block → LLM call
5,000 blocks = 5,000 LLM calls
Time: 42 minutes
Cost: $0.50
```

### Our Approach
```
Marker (no LLM) → Flag suspicious → Target sub-agents
5,000 blocks → 230 suspicious → 66 LLM calls (after cache)
Time: 43 seconds  
Cost: $0.0066
```

## Suspicious Block Categories

| Category | Detection Criteria | Action | Sub-Agent |
|----------|-------------------|---------|-----------|
| Split Headers | Adjacent blocks form words | Merge | pdf_block_merger |
| False Headers | Ends with comma, starts with As/For | Validate | pdf_section_header |
| Low Confidence Tables | Surya score < 0.7 | Reprocess | pdf_table_analyzer + Camelot |
| Split Tables | Table continues on next page | Merge | pdf_table_merge |
| Orphaned Text | Single line between sections | Reassign | pdf_content_assigner |
| Complex Figures | Contains text/equations | Analyze | pdf_figure_analyzer |

## Implementation in Our Pipeline

1. **Marker extracts WITHOUT LLM** (fast)
2. **Suspicious patterns flagged** during extraction
3. **Workflow planner** analyzes patterns
4. **Only suspicious blocks** sent to sub-agents
5. **Knowledge base** reduces future suspicions

This approach gives us:
- Speed of raw marker extraction
- Intelligence of targeted LLM validation
- Learning that improves over time
- Cost savings of 76x vs marker --use_llm