# Complete Pipeline Validation Report

Generated: 2025-08-02T11:02:23.882600
Pipeline Version: 1.0_validated
PDF: /home/graham/workspace/experiments/extractor/.claude/agents/extract_pdf_pipeline_poc/final/inputs/BHT_CV32A65X_marked.pdf

---

## Stage Results Summary

### 1_marker
- success: True
- page_count: 2

### 2_annotations
- success: True
- pdf_id: BHT_CV32A65X_marked

### 3_camelot
- success: True
- tables: {0: [{'page': 0, 'method': 'lattice', 'bbox': [60.0, 97.92, 560.88, 185.76], 'accuracy': 100.00000000000001, 'whitespace': 76.19047619047619, 'order': 1, 'shape': (3, 7), 'data': [{0: '', 1: '', 2: '', 3: '', 4: '', 5: '', 6: ''}, {0: '', 1: 'Signal', 2: 'IO', 3: 'Descripti \non', 4: 'connexi \non', 5: 'Type', 6: ''}, {0: '', 1: '', 2: '', 3: '', 4: '', 5: '', 6: ''}], 'parsing_report': {'accuracy': 100.00000000000001, 'whitespace': 76.19047619047619, 'order': 1, 'page': 1}}, {'page': 0, 'method': 'stream', 'bbox': [61.99999699999999, 467.78564751226526, 552.6894310379392, 768.1419171682884], 'accuracy': 100.00000000000001, 'shape': (9, 1), 'data': [{0: '4.1.5.4. BHT (Branch History Table) submodule'}, {0: 'BHT is implemented as a memory which is composed of  BHTDepth configuration parameter'}, {0: 'entries. The lower address bits of the virtual address point to the memory entry.'}, {0: 'When a branch instruction is resolved by the EX_STAGE module, the branch PC and the taken'}, {0: '(or not taken) status information is stored in the Branch History Table.'}, {0: 'The Branch History Table is a table of two-bit saturating counters that takes the virtual address of'}, {0: 'the current fetched instruction by the CACHE. It states whether the current branch request'}, {0: 'should be taken or not. The two bit counter is updated by the successive execution of the'}, {0: 'instructions as shown in the following figure.'}]}], 1: [{'page': 1, 'method': 'lattice', 'bbox': [54.72, 312.0, 555.6, 724.3199999999999], 'accuracy': 100.0, 'whitespace': 40.476190476190474, 'order': 1, 'shape': (6, 7), 'data': [{0: '', 1: '', 2: '', 3: '', 4: '', 5: '', 6: ''}, {0: '', 1: 'clk_i', 2: 'in', 3: 'Subsyste \nm Clock', 4: 'SUBSY \nSTEM', 5: 'logic', 6: ''}, {0: '', 1: 'rst_ni', 2: 'in', 3: 'Asynchro \nnous reset \nactive low', 4: 'SUBSY \nSTEM', 5: 'logic', 6: ''}, {0: '', 1: 'vpc_i', 2: 'in', 3: 'Virtual PC', 4: 'CACHE', 5: 'logic[CVA6Cfg.VLEN-1:0]', 6: ''}, {0: '', 1: 'bht_updat \ne_i', 2: 'in', 3: 'Update \nbht with \nresolved \naddress', 4: 'EXECU \nTE', 5: 'bht_update_t', 6: ''}, {0: '', 1: 'bht_predi \nction_o', 2: 'ou \nt', 3: 'Prediction \nfrom bht', 4: 'FRONT \nEND', 5: 'ariane_pkg::bht_prediction_t[CVA6Cfg.IN \nSTR_PER_FETCH-1:0]', 6: ''}], 'parsing_report': {'accuracy': 100.0, 'whitespace': 40.476190476190474, 'order': 1, 'page': 2}}]}
- pages_processed: 2

### 4_suspicious
- count: 1


## Gold Standard Comparisons

### 1_marker
- Exact Match: False
- Missing Keys: ['validation_summary', 'metadata', 'document']
- Extra Keys: ['blocks', 'block_count']

### 2_annotations
- Exact Match: False
- Missing Keys: ['learned_patterns', 'statistics', 'metadata']
- Extra Keys: ['annotation_count', 'pdf_id']
- Different Values: 1 fields


## Raw Responses

### Stage 1: Marker Extraction Raw Response
```json
{
  "success": null,
  "block_count": 56,
  "first_3_blocks": [
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
      "uuid": "23185b98-9f25-43e1-bbe7-03303fdea0a1"
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
      "uuid": "4e364b73-8c45-4626-bf73-f08e5efefe88"
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
      "uuid": "12cdc565-64fd-4e83-bd1a-d4dcbfcdb4e9"
    }
  ]
}
```

### Stage 2: Annotations Raw Response
```json
{
  "pdf_id": "BHT_CV32A65X_marked",
  "annotation_count": 8,
  "annotations": [
    {
      "page": 0,
      "type": "FreeText",
      "content": "Merge Table ",
      "author": "Graham Anderson",
      "rect": [
        243.5695037841797,
        733.2899780273438,
        400.89630126953125,
        767.2489013671875
      ],
      "flags": 4,
      "creation_date": "",
      "subject": "",
      "modified_date": "D:20250712122114Z00'00'"
    },
    {
      "page": 0,
      "type": "FreeText",
      "content": "Section Header",
      "author": "Graham Anderson",
      "rect": [
        69.42581176757812,
        42.60369873046875,
        258.1748962402344,
        76.5626220703125
      ],
      "flags": 4,
      "creation_date": "",
      "subject": "",
      "modified_date": "D:20250707165930Z00'00'"
    },
    {
      "page": 0,
      "type": "FreeText",
      "content": "Figure",
      "author": "Graham Anderson",
      "rect": [
        67.19325256347656,
        341.7665100097656,
        146.71719360351562,
        375.72540283203125
      ],
      "flags": 4,
      "creation_date": "",
      "subject": "",
      "modified_date": "D:20250707165929Z00'00'"
    },
    {
      "page": 0,
      "type": "FreeText",
      "content": "Table Header",
      "author": "Graham Anderson",
      "rect": [
        391.36700439453125,
        572.1069946289062,
        552.6591796875,
        606.06591796875
      ],
      "flags": 4,
      "creation_date": "",
      "subject": "",
      "modified_date": "D:20250712122137Z00'00'"
    },
    {
      "page": 1,
      "type": "FreeText",
      "content": "Merge Table ",
      "author": "Graham Anderson",
      "rect": [
        236.87179565429688,
        -0.91552734375,
        394.1986083984375,
        33.04339599609375
      ],
      "flags": 4,
      "creation_date": "",
      "subject": "",
      "modified_date": "D:20250712122207Z00'00'"
    },
    {
      "page": 1,
      "type": "FreeText",
      "content": "Text, NOT a Section Header",
      "author": "Graham Anderson",
      "rect": [
        193.58270263671875,
        633.1112060546875,
        556.1859741210938,
        667.070068359375
      ],
      "flags": 4,
      "creation_date": "",
      "subject": "",
      "modified_date": "D:20250707202926Z00'00'"
    },
    {
      "page": 1,
      "type": "FreeText",
      "content": "Text, NOT a Section Header",
      "author": "Graham Anderson",
      "rect": [
        218.13670349121094,
        528.9210205078125,
        580.7401123046875,
        562.8798828125
      ],
      "flags": 4,
      "creation_date": "",
      "subject": "",
      "modified_date": "D:20250707202928Z00'00'"
    },
    {
      "page": 1,
      "type": "FreeText",
      "content": "Table Data",
      "author": "Graham Anderson",
      "rect": [
        59.51478958129883,
        32.548095703125,
        190.1376953125,
        66.50701904296875
      ],
      "flags": 4,
      "creation_date": "",
      "subject": "",
      "modified_date": "D:20250712122218Z00'00'"
    }
  ]
}
```

### Stage 3: Camelot Raw Response
```json
{
  "table_pages": [
    0,
    1
  ],
  "extraction_count": 3,
  "first_result": {
    "page": 0,
    "method": "lattice",
    "bbox": [
      60.0,
      97.92,
      560.88,
      185.76
    ],
    "accuracy": 100.00000000000001,
    "whitespace": 76.19047619047619,
    "order": 1,
    "shape": [
      3,
      7
    ],
    "data": [
      {
        "0": "",
        "1": "",
        "2": "",
        "3": "",
        "4": "",
        "5": "",
        "6": ""
      },
      {
        "0": "",
        "1": "Signal",
        "2": "IO",
        "3": "Descripti \non",
        "4": "connexi \non",
        "5": "Type",
        "6": ""
      },
      {
        "0": "",
        "1": "",
        "2": "",
        "3": "",
        "4": "",
        "5": "",
        "6": ""
      }
    ],
    "parsing_report": {
      "accuracy": 100.00000000000001,
      "whitespace": 76.19047619047619,
      "order": 1,
      "page": 1
    }
  }
}
```

### Stage 4: Suspicious Detection Raw Analysis
```json
{
  "total_blocks": 56,
  "block_types": {
    "SectionHeader": 1,
    "Text": 9,
    "Figure": 1,
    "Table": 3,
    "TableCell": 42
  },
  "suspicious_analysis": [
    {
      "uuid": "23185b98-9f25-43e1-bbe7-03303fdea0a1",
      "type": "SectionHeader",
      "text": "4.1.5.4. BHT (Branch History Table) submodule",
      "page": 0,
      "checks": [
        {
          "check": "known_fragment",
          "is_fragment": false
        }
      ]
    },
    {
      "uuid": "fc560368-71ec-45ef-8bc1-33d7ee8084e7",
      "type": "Table",
      "text": "The BHT is never flushed.",
      "page": 0,
      "checks": [
        {
          "check": "camelot_validation",
          "found": true
        },
        {
          "check": "sentence_structure",
          "has_sentence": false
        }
      ]
    },
    {
      "uuid": "a7f79bb4-b7e1-456b-890f-a3267883e2d7",
      "type": "Table",
      "text": "SignalIODescripticonnexiTypeonon",
      "page": 0,
      "checks": [
        {
          "check": "camelot_validation",
          "found": true
        },
        {
          "check": "sentence_structure",
          "has_sentence": false
        }
      ]
    },
    {
      "uuid": "a62faaa4-0c3d-49f4-a50a-44650dc402a3",
      "type": "Table",
      "text": "clk_iinSubsystem ClockSUBSYSTEMlogicrst_niinAsynchronous resetactive lowSUBSYSTEMlogicvpc_iinVirtual",
      "page": 1,
      "checks": [
        {
          "check": "camelot_validation",
          "found": true
        },
        {
          "check": "sentence_structure",
          "has_sentence": true
        }
      ],
      "suspicious": true,
      "score": 0.9,
      "reasons": [
        "table_is_actually_text"
      ]
    }
  ],
  "suspicious_count": 1
}
```


## Detailed Gold Standard Differences

### 1_marker Differences
```diff
--- marker_extraction_gold

+++ marker_extraction_actual

@@ -1,302 +1,733 @@

 {

-  "document": {

-    "filepath": "BHT_CV32A65X_marked.pdf",

-    "pages": [

-      {

-        "bbox": [

-          0,

-          0,

-          612,

-          792

-        ],

-        "children": [

-          {

-            "bbox": [

-              70.5,

-              81.9,

-              315.0,

-              95.5

-            ],

-            "block_id": 0,

-            "block_type": "SectionHeader",

-            "heading_level": 3,

-            "metadata": {

-              "validation": {

-                "confidence": 0.95,

-                "is_suspicious": false,

-                "quality_score": 0.92,

-                "suspicious_reason": null

-              }

-            },

-            "text": "4.1.5.4. BHT (Branch History Table) submodule"

-          },

-          {

-            "bbox": [

-              70.5,

-              116.25,

-              537.0,

-              152.1

-            ],

-            "block_id": 1,

-            "block_type": "Text",

-            "metadata": {

-              "validation": {

-                "confidence": 0.93,

-                "is_suspicious": false,

-                "quality_score": 0.91,

-                "suspicious_reason": null

... (50 more lines)
```

### 2_annotations Differences
```diff
--- annotations_gold

+++ annotations_actual

@@ -1,119 +1,134 @@

 {

+  "annotation_count": 8,

   "annotations": [

     {

-      "bbox": [

-        72.0,

-        575.0,

-        202.0,

-        588.0

+      "author": "Graham Anderson",

+      "content": "Merge Table ",

+      "creation_date": "",

+      "flags": 4,

+      "modified_date": "D:20250712122114Z00'00'",

+      "page": 0,

+      "rect": [

+        243.5695037841797,

+        733.2899780273438,

+        400.89630126953125,

+        767.2489013671875

       ],

-      "confidence": 0.95,

-      "learned_pattern": "single_row_table_to_text",

-      "page": 0,

-      "reason": "Single-row table should be text",

-      "type": "merge_table"

+      "subject": "",

+      "type": "FreeText"

     },

     {

-      "bbox": [

-        72.0,

-        611.0,

-        541.0,

-        686.0

+      "author": "Graham Anderson",

+      "content": "Section Header",

+      "creation_date": "",

+      "flags": 4,

+      "modified_date": "D:20250707165930Z00'00'",

+      "page": 0,

+      "rect": [

+        69.42581176757812,

+        42.60369873046875,

+        258.1748962402344,

+        76.5626220703125

       ],

... (50 more lines)
```
