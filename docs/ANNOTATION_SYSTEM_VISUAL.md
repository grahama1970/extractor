# Annotation System Visual Overview

## The Complete Annotation Knowledge Loop

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          ANNOTATION KNOWLEDGE SYSTEM                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. ANNOTATION EXTRACTION                                                    │
│  ┌────────────┐     ┌────────────┐     ┌────────────┐                     │
│  │   QB50     │     │    BHT     │     │  Future    │                     │
│  │ (103 annos)│     │ (X annos)  │     │   PDFs     │                     │
│  └─────┬──────┘     └─────┬──────┘     └─────┬──────┘                     │
│        │                   │                   │                             │
│        └───────────────────┴───────────────────┘                           │
│                            │                                                 │
│                            ▼                                                 │
│  2. KNOWLEDGE BASE (ArangoDB)                                               │
│  ┌─────────────────────────────────────────────────────────┐              │
│  │ Collection: pdf_annotations                              │              │
│  │ ┌─────────────────────────────────────────────────────┐ │              │
│  │ │ • Merge Table @ page 1, bbox:[81,75,528,716]        │ │              │
│  │ │ • Section Header @ page 3, bbox:[100,150,300,180]   │ │              │
│  │ │ • Green Box (Important) @ page 9                    │ │              │
│  │ │ • ... (searchable by BM25)                          │ │              │
│  │ └─────────────────────────────────────────────────────┘ │              │
│  └─────────────────────────────────────────────────────────┘              │
│                            │                                                 │
│                            ▼                                                 │
│  3. EXTRACTION PIPELINE                                                      │
│  ┌─────────────────────────────────────────────────────────┐              │
│  │  New PDF → Extract Blocks → Check Each Block:           │              │
│  │                                                          │              │
│  │  Block: {type: "Text", content: "Col1 Col2 Col3..."}    │              │
│  │     ↓                                                    │              │
│  │  QUESTION: "Does this look wrong?"                      │              │
│  │     ↓ YES                                               │              │
│  │  SEARCH: "text misidentified table merge page_1"        │              │
│  │     ↓                                                    │              │
│  │  RESULTS: [                                             │              │
│  │    {anno: "Merge Table", score: 0.95},                  │              │
│  │    {anno: "Table split", score: 0.87}                   │              │
│  │  ]                                                       │              │
│  │     ↓                                                    │              │
│  │  APPLY: Change type to "Table", mark for merge          │              │
│  └─────────────────────────────────────────────────────────┘              │
│                            │                                                 │
│                            ▼                                                 │
│  4. FEATURE RELEVANCE LEARNING                                              │
│  ┌─────────────────────────────────────────────────────────┐              │
│  │  Track Success Rates:                                    │              │
│  │  • MERGE_TABLE: 89% success (cross-document pattern)    │              │
│  │  • FORCE_SECTION_HEADER: 95% success                    │              │
│  │  • GREEN_BOX_IMPORTANT: 100% success                    │              │
│  │                                                          │              │
│  │  Learn Patterns:                                        │              │
│  │  • Tables after headers often need merging              │              │
│  │  • Green boxes always mark critical content             │              │
│  │  • Section headers have consistent formatting           │              │
│  └─────────────────────────────────────────────────────────┘              │
│                            │                                                 │
│                            └────────────────┐                               │
│                                             │ FEEDBACK LOOP                  │
│                                             ▼                               │
│                                    Store Results & Improve                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Real Example: QB50 Table Correction

```
BEFORE (Misidentified):
┌─────────────────────────────────────┐
│ Block Type: Text                    │
│ Content: "Issue No. Issue Date..."  │
│ Page: 1                             │
│ BBox: [81, 90, 528, 108]           │
└─────────────────────────────────────┘
                ↓
        Pipeline Detects Issue
                ↓
┌─────────────────────────────────────┐
│ SEARCH KNOWLEDGE BASE:              │
│                                     │
│ Query: "text table page_1 81 90"    │
│                                     │
│ Found Annotation:                   │
│ • "Merge Table" @ [81,75,528,716]   │
│ • Overlaps with block!              │
│ • Instruction: MERGE_TABLE          │
└─────────────────────────────────────┘
                ↓
AFTER (Corrected):
┌─────────────────────────────────────┐
│ Block Type: Table ✓                 │
│ Content: "Issue No. Issue Date..."  │
│ Page: 1                             │
│ BBox: [81, 90, 528, 108]           │
│ needs_merge: true                   │
│ correction_source: "annotation"     │
└─────────────────────────────────────┘
```

## Cross-Document Knowledge Transfer

```
BHT PDF Experience:                    QB50 PDF Processing:
┌─────────────────┐                   ┌─────────────────┐
│ Found pattern:  │                   │ New document    │
│ Tables after    │      INFORMS      │ encounters      │
│ "Requirements"  │ ────────────────> │ similar table   │
│ headers split   │                   │ after header    │
└─────────────────┘                   └─────────────────┘
        ↓                                      ↓
  Stored in KB                          Search finds BHT
        ↓                                  annotation
┌─────────────────┐                   ┌─────────────────┐
│ Annotation DB:  │                   │ Apply learned   │
│ "Merge Table"   │ <──── SEARCH ──── │ correction      │
│ after headers   │                   │ automatically   │
└─────────────────┘                   └─────────────────┘
```

## The Power of This System

1. **Self-Improving**: Every annotated PDF makes future extractions better
2. **Cross-Document**: Patterns from one document help all others
3. **Explainable**: Can trace why each correction was made
4. **Measurable**: Annotations provide ground truth for scoring

## Key Insight

The annotations ARE the gold standard - they're not just data to extract, they're the teacher showing the system how to extract correctly!