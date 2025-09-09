# Final Secure Pipeline Report

Generated: 2025-08-02T11:27:02.935661
Pipeline Version: 3.0_secure
PDF: /home/graham/workspace/experiments/extractor/.claude/agents/extract_pdf_pipeline_poc/final/inputs/BHT_CV32A65X_marked.pdf

## Pipeline Summary
- Total Time: 0:00:01.659323
- Blocks Processed: 56
- Suspicious Found: 2
- Corrections Applied: 2
- Average Confidence: 85.14%

## Stage Results

### 1_marker
- success: True
- block_count: 56

### 2_annotations
- success: True
- count: 8

### 3_camelot
- success: True
- pages_processed: 2
- tables_found: 3

### 4_suspicious
- count: 2
- reasons: {'garbled_table_text': 2, 'table_is_actually_text': 1}

### 5_claude
- analyzed: 2

### 6_corrections
- success: True
- total_corrected: 2

## Corrections Applied

**Page 0:**
- Text: "SignalIODescripticonnexiTypeonon"
- Changed from: Table → Text
- Confidence: 80.00%
- Reason: Garbled text indicates OCR issue, likely regular text (fallback)

**Page 1:**
- Text: "clk_iinSubsystem ClockSUBSYSTEMlogicrst_niinAsynchronous resetactive lowSUBSYSTEMlogicvpc_iinVirtual"
- Changed from: Table → Text
- Confidence: 90.00%
- Reason: Table block contains complete sentence structure (fallback)

## Gold Standard Comparison
- Exact Match: False

**page_count:**
  - Actual: 2
  - Expected: 2
  - Match: ✓

**block_count:**
  - Actual: 14
  - Expected: 10
  - Match: ✗

## Raw Output Samples

### Marker Extraction (first 3 blocks)
```json
[
  {
    "block_type": "SectionHeader",
    "text": "4.1.5.4. BHT (Branch History Table) submodule",
    "html": "<h2>4.1.5.4. BHT (Branch History Table) submodule</h2>",
    "page": 0,
    "bbox": [
      71.12109375,
      81.93603515625,
      315.0429992675781,
      95.47119140625
    ],
    "uuid": "55205060-bf0f-496f-af96-0467b7eae0ec"
  },
  {
    "block_type": "Text",
    "text": "BHT is implemented as a memory which is composed of BHTDepth configuration parameter entries. The lower address bits of the virtual address point to the memory entry.",
    "html": "<p block-type=\"Text\">BHT is implemented as a memory which is composed of <b>BHTDepth configuration parameter</b> entries. The lower address bits of the virtual address point to the memory entry.</p>",
    "page": 0,
    "bbox": [
      71.2705078125,
      116.3056640625,
      536.09765625,
      152.0771484375
    ],
    "uuid": "e389e143-b683-4618-bd1d-0e22b8a737af"
  },
  {
    "block_type": "Text",
    "text": "When a branch instruction is resolved by the EX_STAGE module, the branch PC and the taken (or not taken) status information is stored in the Branch History Table.",
    "html": "<p block-type=\"Text\">When a branch instruction is resolved by the EX_STAGE module, the branch PC and the taken (or not taken) status information is stored in the Branch History Table.</p>",
    "page": 0,
    "bbox": [
      71.71875,
      175.4736328125,
      531.9140625,
      210.64764404296875
    ],
    "uuid": "bff7b9e1-74f3-4b0e-821a-4bcad8843cf2"
  }
]
```

### Suspicious Blocks (first 2)
```json
{
  "text": "SignalIODescripticonnexiTypeonon...",
  "type": "Text",
  "score": 0.7,
  "reasons": [
    "garbled_table_text"
  ]
}
{
  "text": "clk_iinSubsystem ClockSUBSYSTEMlogicrst_niinAsynch...",
  "type": "Text",
  "score": 1.0,
  "reasons": [
    "table_is_actually_text",
    "garbled_table_text"
  ]
}
```