SYSTEM INSTRUCTIONS:

You are a technical reflow engine. Given a PDF-extracted section JSON, compact pandas tables, and a small set of images, output a single reflowed section JSON that merges contiguous content for LLM use and DB storage.

Core requirements
- Merge contiguous text into coherent paragraphs (fix hyphenation, broken words, OCR joins). Remove duplicated headers/footers and page artifacts.
- Merge contiguous tables, including those that span pages, into one logical table positioned at the first fragment.
- Preserve reading order: top→bottom, left→right, across pages.
- Prefer provided pandas/compact tables for content; use images only for context or disambiguation.

Data Integrity (strict)
- Tables: DO NOT change cell content. No spelling corrections, translations, unit changes, rounding, normalization, inference, or reformatting. Keep numeric formats as-is.
- Allowed in tables only: remove intra-cell newlines/excess spaces (join without changing character order); flatten multi-row headers by concatenation.
- Forbidden in tables: reordering rows/columns, filling blanks, deduping, computing totals.
- Text/Headings/Lists: Fix OCR splits/hyphenation and obvious typos only outside tables. Record fixes in ocr_corrections.

Return ONLY this JSON object (no extra text):
{
  "section_id": string,
  "title": string,
  "blocks": [
    { "type": "heading", "level": int, "text": string, "source": { "pages": [int], "block_ids": [string] } },
    { "type": "paragraph", "text": string, 
      "source": { "pages": [int], "block_ids": [string] } },
    { "type": "list", "style": "bulleted|numbered", "items": [string, ...], 
      "source": { "pages": [int], "block_ids": [string] } },
    { "type": "table", 
      "title": string | null,
      "columns": [string], 
      "rows": [[string|number|null, ...]], 
      "confidence": { "status": "high|medium|low", "density": number|null, "source": "camelot+pandas" },
      "markdown": string | null, 
      "markdown_provenance": "image" | null, 
      "image_refs": [string, ...],
      "source": { "table_indices": [int], "page_indices": [int] } },
    { "type": "figure", "title": string | null, "caption": string | null, "alt": string, "image_ref": string, 
      "source": { "pages": [int], "block_ids": [string] } }
  ],
  "ocr_corrections": { "erroneous": "corrected", ... },
  "improvements_made": string,
  "summary": string
}

Notes
- Tables: build from provided columns+rows; ensure exact cell content; trim whitespace only. Include markdown only if pandas failed or confidence is low, in which case set markdown_provenance="image" and add relevant image_refs.
- Use provided titles from 'Titles (tables & figures)'. If none literal, use the INFERRED: title as-is (light rephrasing allowed).
- Figures: include a concise caption and set image_ref to the uploaded filename (e.g., images/figure1.png).
- Return strict JSON only.


USER CONTENT (paste below and upload the images listed):

Section: BHT (Branch History Table) submodule

Table summary:
Shape: (1, 5) columns: 0, 1, 2, 3, 4

Relevant annotations:
- 4.1.5.4. BHT (Branch History Table) submodule
- Figure


Section JSON Summary:
{
  "id": "section_0",
  "title": "BHT (Branch History Table) submodule",
  "level": 4,
  "page_start": 0,
  "page_end": 1,
  "section_number": "4.1.5.4",
  "section_hash": "1402d30f1a7ebbc4e5645fc6234aedff",
  "blocks_count": 16
}


Tables (pandas, compact):

```json
{
  "tables_compact": [
    {
      "index": 1,
      "columns": [
        "0",
        "1",
        "2",
        "3",
        "4"
      ],
      "rows": [
        [
          "Signal",
          "IO",
          "Descripti \non",
          "connexi \non",
          "Type"
        ]
      ],
      "confidence": 0.8
    },
    {
      "index": 2,
      "columns": [
        "0",
        "1",
        "2",
        "3",
        "4"
      ],
      "rows": [
        [
          "clk_i",
          "in \nin \nin \nou \nt",
          "Subsyste \nm Clock",
          "SUBSY \nSTEM",
          "logic"
        ],
        [
          "rst_ni",
          "",
          "Asynchro \nnous reset \nactive low",
          "SUBSY \nSTEM",
          "logic"
        ],
        [
          "vpc_i \nin \nVirtual PC \nCACHE \nlogic[CVA6Cfg.VLEN-1:0]",
          "",
          "",
          "",
          ""
        ],
        [
          "bht_updat \ne_i",
          "",
          "Update \nbht with \nresolved \naddress",
          "EXECU \nTE",
          "bht_update_t"
        ],
        [
          "bht_predi \nction_o",
          "",
          "Prediction \nfrom bht",
          "FRONT \nEND",
          "ariane_pkg::bht_prediction_t[CVA6Cfg.IN \nSTR_PER_FETCH-1:0]"
        ]
      ],
      "confidence": 0.86
    }
  ]
}
```


Titles (tables & figures):

```json
{
  "tables_titles": [
    {
      "index": 1,
      "title": "4.1.5.4. BHT (Branch History Table) submodule",
      "derived": "literal"
    },
    {
      "index": 2,
      "title": "INFERRED: Table - 0, 1, 2",
      "derived": "inferred"
    }
  ],
  "figures_titles": [
    {
      "index": 1,
      "title": "The Branch History Table is a table of two-bit saturating counters that takes the virtual address of\nthe current fetched instruction by the CACHE. It states whether the current branch request\nshould be taken or not. The two bit counter is updated by the successive execution of the\ninstructions as shown in the following figure.",
      "derived": "literal"
    }
  ],
  "guidance": "Use literal titles when present. If 'INFERRED:' prefix exists, treat as a suggested caption; you may lightly rephrase while preserving meaning."
}
```

Full payload files are generated alongside this prompt:
 - tests/stage07_manual/responses_input.json
 - tests/stage07_manual/chat_messages.json

Attach these images in the chat UI (do not change filenames):
 - images/section.png
 - images/figure1.png
 - images/annotation1.png
 - images/annotation2.png


Section JSON (sanitized):

```json
{
  "title": "4.1.5.4. BHT (Branch History Table) submodule",
  "level": 4,
  "blocks": [
    {
      "block_type": "SectionHeader",
      "page_idx": 0,
      "page": 0,
      "text": "4.1.5.4. BHT (Branch History Table) submodule",
      "first_span_font": {
        "name": "AAAAAA+ArialMT",
        "size": 15.329999923706055,
        "bold": false,
        "italic": false,
        "weight": 435.0,
        "color": 12204325,
        "color_rgb": [
          186,
          57,
          37
        ],
        "color_hex": "#BA3925",
        "color_bucket": "red"
      },
      "bbox": [
        70.61138606071472,
        81.92204421758652,
        315.0429992675781,
        95.43723195791245
      ],
      "surya_confidence": 0.9999847412109375,
      "quality_score": 0.9999847412109375,
      "is_suspicious": false,
      "block_id": 0,
      "id": "/page/0/SectionHeader/0",
      "section_titles": [
        "BHT (Branch History Table) submodule"
      ],
      "section_hashes": [
        "1402d30f1a7ebbc4e5645fc6234aedff"
      ],
      "section_number": "4.1.5.4",
      "section_level": 4,
      "section_depth": [
        4,
        1,
        5,
        4
      ]
    },
    {
      "block_type": "Text",
      "page_idx": 0,
      "page": 0,
      "text": "BHT is implemented as a memory which is composed of BHTDepth configuration parameter\nentries. The lower address bits of the virtual address point to the memory entry.",
      "first_span_font": {
        "name": "BAAAAA+TimesNewRomanPSMT",
        "size": 16.0,
        "bold": false,
        "italic": false,
        "weight": 550.0,
        "color": 0,
        "color_rgb": [
          0,
          0,
          0
        ],
        "color_hex": "#000000",
        "color_bucket": "black"
      },
      "bbox": [
        70.79368507862091,
        116.00405931472778,
        536.939715385437,
        152.04847025871277
      ],
      "surya_confidence": 0.9999785423278809,
      "quality_score": 0.9999785423278809,
      "is_suspicious": false,
      "block_id": 1,
      "id": "/page/0/Text/1",
      "section_titles": [
        "4.1.5.4. BHT (Branch History Table) submodule"
      ],
      "section_hashes": [
        "1402d30f1a7ebbc4e5645fc6234aedff"
      ],
      "section_number": "4.1.5.4",
      "section_level": 4,
      "section_depth": [
        4,
        1,
        5,
        4
      ]
    },
    {
      "block_type": "Text",
      "page_idx": 0,
      "page": 0,
      "text": "When a branch instruction is resolved by the EX_STAGE module, the branch PC and the taken\n(or not taken) status information is stored in the Branch History Table.",
      "first_span_font": {
        "name": "BAAAAA+TimesNewRomanPSMT",
        "size": 16.0,
        "bold": false,
        "italic": false,
        "weight": 550.0,
        "color": 0,
        "color_rgb": [
          0,
          0,
          0
        ],
        "color_hex": "#000000",
        "color_bucket": "black"
      },
      "bbox": [
        71.76277899742126,
        175.36721670627594,
        531.7939403057098,
        210.64764404296875
      ],
      "surya_confidence": 0.9999843835830688,
      "quality_score": 0.9999843835830688,
      "is_suspicious": false,
      "block_id": 2,
      "id": "/page/0/Text/2",
      "section_titles": [
        "4.1.5.4. BHT (Branch History Table) submodule"
      ],
      "section_hashes": [
        "1402d30f1a7ebbc4e5645fc6234aedff"
      ],
      "section_number": "4.1.5.4",
      "section_level": 4,
      "section_depth": [
        4,
        1,
        5,
        4
      ]
    },
    {
      "block_type": "Text",
      "page_idx": 0,
      "page": 0,
      "text": "The Branch History Table is a table of two-bit saturating counters that takes the virtual address of\nthe current fetched instruction by the CACHE. It states whether the current branch request\nshould be taken or not. The two bit counter is updated by the successive execution of the\ninstructions as shown in the following figure.",
      "first_span_font": {
        "name": "BAAAAA+TimesNewRomanPSMT",
        "size": 16.0,
        "bold": false,
        "italic": false,
        "weight": 550.0,
        "color": 0,
        "color_rgb": [
          0,
          0,
          0
        ],
        "color_hex": "#000000",
        "color_bucket": "black"
      },
      "bbox": [
        71.8624370098114,
        234.1325225830078,
        542.6190912723541,
        313.9601135253906
      ],
      "surya_confidence": 0.9999972581863403,
      "quality_score": 0.9999972581863403,
      "is_suspicious": false,
      "block_id": 3,
      "id": "/page/0/Text/3",
      "section_titles": [
        "4.1.5.4. BHT (Branch History Table) submodule"
      ],
      "section_hashes": [
        "1402d30f1a7ebbc4e5645fc6234aedff"
      ],
      "section_number": "4.1.5.4",
      "section_level": 4,
      "section_depth": [
        4,
        1,
        5,
        4
      ]
    },
    {
      "block_type": "Figure",
      "page_idx": 0,
      "page": 0,
      "text": "",
      "bbox": [
        72.21784257888794,
        342.1806650161743,
        541.3334956169128,
        491.3015298843384
      ],
      "surya_confidence": 0.9999994039535522,
      "quality_score": 0.9999994039535522,
      "is_suspicious": false,
      "block_id": 4,
      "id": "/page/0/Figure/4",
      "section_titles": [
        "4.1.5.4. BHT (Branch History Table) submodule"
      ],
      "section_hashes": [
        "1402d30f1a7ebbc4e5645fc6234aedff"
      ],
      "section_number": "4.1.5.4",
      "section_level": 4,
      "section_depth": [
        4,
        1,
        5,
        4
      ]
    },
    {
      "block_type": "Text",
      "page_idx": 0,
      "page": 0,
      "text": "When a branch instruction is pre-decoded by instr_scan submodule, the BHT valids whether the\nPC address is in the BHT and provides the taken or not prediction.",
      "first_span_font": {
        "name": "BAAAAA+TimesNewRomanPSMT",
        "size": 16.0,
        "bold": false,
        "italic": false,
        "weight": 550.0,
        "color": 0,
        "color_rgb": [
          0,
          0,
          0
        ],
        "color_hex": "#000000",
        "color_bucket": "black"
      },
      "bbox": [
        71.94184970855713,
        516.1880993843079,
        536.3081345558167,
        551.2413024902344
      ],
      "surya_confidence": 0.9961636066436768,
      "quality_score": 0.9961636066436768,
      "is_suspicious": false,
      "block_id": 5,
      "id": "/page/0/Text/5",
      "section_titles": [
        "4.1.5.4. BHT (Branch History Table) submodule"
      ],
      "section_hashes": [
        "1402d30f1a7ebbc4e5645fc6234aedff"
      ],
      "section_number": "4.1.5.4",
      "section_level": 4,
      "section_depth": [
        4,
        1,
        5,
        4
      ]
    },
    {
      "block_type": "Table",
      "page_idx": 0,
      "page": 0,
      "text": "The BHT is never flushed.",
      "bbox": [
        71.98325228691101,
        575.5436682701111,
        202.55295860767365,
        588.5241436958313
      ],
      "surya_confidence": 0.9030722975730896,
      "quality_score": 0.9030722975730896,
      "is_suspicious": false,
      "block_id": 6,
      "id": "/page/0/Table/6",
      "section_titles": [
        "4.1.5.4. BHT (Branch History Table) submodule"
      ],
      "section_hashes": [
        "1402d30f1a7ebbc4e5645fc6234aedff"
      ],
      "section_number": "4.1.5.4",
      "section_level": 4,
      "section_depth": [
        4,
        1,
        5,
        4
      ]
    },
    {
      "block_type": "Table",
      "page_idx": 0,
      "page": 0,
      "text": "SignalIODescripticonnexiTypeonon",
      "bbox": [
        70.94346392154694,
        611.4220762252808,
        542.1482691764832,
        686.6947660446167
      ],
      "surya_confidence": 0.9999796152114868,
      "quality_score": 0.9999796152114868,
      "is_suspicious": false,
      "block_id": 7,
      "id": "/page/0/Table/7",
      "section_titles": [
        "4.1.5.4. BHT (Branch History Table) submodule"
      ],
      "section_hashes": [
        "1402d30f1a7ebbc4e5645fc6234aedff"
      ],
      "section_number": "4.1.5.4",
      "section_level": 4,
      "section_depth": [
        4,
        1,
        5,
        4
      ]
    },
    {
      "block_type": "Table",
      "page_idx": 1,
      "page": 1,
      "text": "clk_iinSubsyste\nm ClockSUBSY\nSTEMlogicrst_niinAsynchro\nnous reset\nactive lowSUBSY\nSTEMlogicvpc_iinVirtual PCCACHElogic[CVA6Cfg.VLEN-1:0]bht_updat\ne_iinUpdate\nbht with\nresolved\naddressEXECU\nTEbht_update_tbht_predi\nction_oou\ntPrediction\nfrom bhtFRONT\nENDariane_pkg::bht_prediction_t[CVA6Cfg.IN\nSTR_PER_FETCH-1:0]",
      "bbox": [
        70.20759236812592,
        70.94134068489075,
        541.4924669265747,
        476.13603687286377
      ],
      "surya_confidence": 0.9998537302017212,
      "quality_score": 0.9998537302017212,
      "is_suspicious": false,
      "block_id": 0,
      "id": "/page/1/Table/0",
      "section_titles": [
        "4.1.5.4. BHT (Branch History Table) submodule"
      ],
      "section_hashes": [
        "1402d30f1a7ebbc4e5645fc6234aedff"
      ],
      "section_number": "4.1.5.4",
      "section_level": 4,
      "section_depth": [
        4,
        1,
        5,
        4
      ]
    },
    {
      "block_type": "Text",
      "page_idx": 1,
      "page": 1,
      "text": "Due to cv32a65x configuration, some ports are tied to a static value. These ports do not appear in\nthe above table, they are listed below",
      "first_span_font": {
        "name": "BAAAAA+TimesNewRomanPSMT",
        "size": 16.0,
        "bold": false,
        "italic": false,
        "weight": 550.0,
        "color": 0,
        "color_rgb": [
          0,
          0,
          0
        ],
        "color_hex": "#000000",
        "color_bucket": "black"
      },
      "bbox": [
        71.3538783788681,
        480.4820861816406,
        540.7695450782776,
        514.9887142181396
      ],
      "surya_confidence": 0.9999977350234985,
      "quality_score": 0.9999977350234985,
      "is_suspicious": false,
      "block_id": 1,
      "id": "/page/1/Text/1",
      "section_titles": [
        "4.1.5.4. BHT (Branch History Table) submodule"
      ],
      "section_hashes": [
        "1402d30f1a7ebbc4e5645fc6234aedff"
      ],
      "section_number": "4.1.5.4",
      "section_level": 4,
      "section_depth": [
        4,
        1,
        5,
        4
      ]
    },
    {
      "block_type": "Text",
      "page_idx": 1,
      "page": 1,
      "text": "For any HW configuration,",
      "first_span_font": {
        "name": "CAAAAA+TimesNewRomanPS-BoldMT",
        "size": 16.0,
        "bold": true,
        "italic": false,
        "weight": 788.0,
        "color": 0,
        "color_rgb": [
          0,
          0,
          0
        ],
        "color_hex": "#000000",
        "color_bucket": "black"
      },
      "bbox": [
        71.677794277668,
        537.1313366889954,
        215.21133184432983,
        552.2455630302429
      ],
      "surya_confidence": 0.9999287128448486,
      "quality_score": 0.9999287128448486,
      "is_suspicious": false,
      "block_id": 2,
      "id": "/page/1/Text/2",
      "section_titles": [
        "4.1.5.4. BHT (Branch History Table) submodule"
      ],
      "section_hashes": [
        "1402d30f1a7ebbc4e5645fc6234aedff"
      ],
      "section_number": "4.1.5.4",
      "section_level": 4,
      "section_depth": [
        4,
        1,
        5,
        4
      ]
    },
    {
      "block_type": "ListItem",
      "page_idx": 1,
      "page": 1,
      "text": "● flush_bp_i input is tied to 0",
      "first_span_font": {
        "name": "EAAAAA+ArialMT",
        "size": 16.0,
        "bold": false,
        "italic": false,
        "weight": 435.0,
        "color": 0,
        "color_rgb": [
          0,
          0,
          0
        ],
        "color_hex": "#000000",
        "color_bucket": "black"
      },
      "bbox": [
        142.57235938310623,
        586.496561050415,
        315.0221872329712,
        601.571605682373
      ],
      "surya_confidence": 0.9999797344207764,
      "quality_score": 0.9999797344207764,
      "is_suspicious": false,
      "block_id": 3,
      "id": "/page/1/ListItem/3",
      "section_titles": [
        "4.1.5.4. BHT (Branch History Table) submodule"
      ],
      "section_hashes": [
        "1402d30f1a7ebbc4e5645fc6234aedff"
      ],
      "section_number": "4.1.5.4",
      "section_level": 4,
      "section_depth": [
        4,
        1,
        5,
        4
      ]
    },
    {
      "block_type": "Text",
      "page_idx": 1,
      "page": 1,
      "text": "As DebugEn = False,",
      "first_span_font": {
        "name": "CAAAAA+TimesNewRomanPS-BoldMT",
        "size": 16.0,
        "bold": true,
        "italic": false,
        "weight": 788.0,
        "color": 0,
        "color_rgb": [
          0,
          0,
          0
        ],
        "color_hex": "#000000",
        "color_bucket": "black"
      },
      "bbox": [
        72.0,
        643.7772932052612,
        180.5193636417389,
        659.9843587875366
      ],
      "surya_confidence": 0.9956228137016296,
      "quality_score": 0.9956228137016296,
      "is_suspicious": false,
      "block_id": 4,
      "id": "/page/1/Text/4",
      "section_titles": [
        "4.1.5.4. BHT (Branch History Table) submodule"
      ],
      "section_hashes": [
        "1402d30f1a7ebbc4e5645fc6234aedff"
      ],
      "section_number": "4.1.5.4",
      "section_level": 4,
      "section_depth": [
        4,
        1,
        5,
        4
      ]
    },
    {
      "block_type": "ListItem",
      "page_idx": 1,
      "page": 1,
      "text": "● debug_mode_i input is tied to 0",
      "first_span_font": {
        "name": "EAAAAA+ArialMT",
        "size": 16.0,
        "bold": false,
        "italic": false,
        "weight": 435.0,
        "color": 0,
        "color_rgb": [
          0,
          0,
          0
        ],
        "color_hex": "#000000",
        "color_bucket": "black"
      },
      "bbox": [
        141.7667326927185,
        693.5548696517944,
        330.29065561294556,
        710.0409278869629
      ],
      "surya_confidence": 0.9999969005584717,
      "quality_score": 0.9999969005584717,
      "is_suspicious": false,
      "block_id": 5,
      "id": "/page/1/ListItem/5",
      "section_titles": [
        "4.1.5.4. BHT (Branch History Table) submodule"
      ],
      "section_hashes": [
        "1402d30f1a7ebbc4e5645fc6234aedff"
      ],
      "section_number": "4.1.5.4",
      "section_level": 4,
      "section_depth": [
        4,
        1,
        5,
        4
      ]
    },
    {
      "block_type": "Text",
      "page_idx": 1,
      "page": 1,
      "text": "● flush_bp_i input is tied to 0",
      "first_span_font": {
        "name": "EAAAAA+ArialMT",
        "size": 16.0,
        "bold": false,
        "italic": false,
        "weight": 435.0,
        "color": 0,
        "color_rgb": [
          0,
          0,
          0
        ],
        "color_hex": "#000000",
        "color_bucket": "black"
      },
      "bbox": [
        142.57235938310623,
        586.496561050415,
        315.0221872329712,
        601.571605682373
      ],
      "quality_score": 0.5,
      "is_suspicious": false,
      "block_id": 142,
      "id": "/page/1/Text/142",
      "section_titles": [
        "4.1.5.4. BHT (Branch History Table) submodule"
      ],
      "section_hashes": [
        "1402d30f1a7ebbc4e5645fc6234aedff"
      ],
      "section_number": "4.1.5.4",
      "section_level": 4,
      "section_depth": [
        4,
        1,
        5,
        4
      ]
    },
    {
      "block_type": "Text",
      "page_idx": 1,
      "page": 1,
      "text": "● debug_mode_i input is tied to 0",
      "first_span_font": {
        "name": "EAAAAA+ArialMT",
        "size": 16.0,
        "bold": false,
        "italic": false,
        "weight": 435.0,
        "color": 0,
        "color_rgb": [
          0,
          0,
          0
        ],
        "color_hex": "#000000",
        "color_bucket": "black"
      },
      "bbox": [
        141.7667326927185,
        693.5548696517944,
        330.29065561294556,
        710.0409278869629
      ],
      "quality_score": 0.5,
      "is_suspicious": false,
      "block_id": 143,
      "id": "/page/1/Text/143",
      "section_titles": [
        "4.1.5.4. BHT (Branch History Table) submodule"
      ],
      "section_hashes": [
        "1402d30f1a7ebbc4e5645fc6234aedff"
      ],
      "section_number": "4.1.5.4",
      "section_level": 4,
      "section_depth": [
        4,
        1,
        5,
        4
      ]
    }
  ],
  "page_start": 0,
  "page_end": 1,
  "bbox": [
    70.20759236812592,
    70.94134068489075,
    542.6190912723541,
    710.0409278869629
  ],
  "metadata": {
    "section_number": "4.1.5.4",
    "section_depth": [
      4,
      1,
      5,
      4
    ],
    "section_hash": "1402d30f1a7ebbc4e5645fc6234aedff",
    "block_count": 16,
    "validation_method": "stage03_or_fallback",
    "diagnostics": [],
    "title_display": "BHT (Branch History Table) submodule",
    "pages": [
      0,
      1
    ],
    "page_start": 0,
    "page_end": 1,
    "page_count": 2,
    "composite_size_bytes": 316547,
    "composite_width": 1224,
    "composite_height": 3171,
    "visual_path": "04_section_builder/image_output/section_section_0.png"
  },
  "display_title": "BHT (Branch History Table) submodule",
  "id": "section_0",
  "parent_id": null,
  "pages": [
    0,
    1
  ],
  "has_visual": true,
  "visual_path": "04_section_builder/image_output/section_section_0.png"
}
```


Tables Full Data (sanitized):

```json
{
  "tables_full": [
    {
      "index": 1,
      "metrics": {
        "shape": [
          1,
          5
        ],
        "columns": [
          "0",
          "1",
          "2",
          "3",
          "4"
        ],
        "dtypes": {
          "0": "object",
          "1": "object",
          "2": "object",
          "3": "object",
          "4": "object"
        },
        "null_counts": {
          "0": 0,
          "1": 0,
          "2": 0,
          "3": 0,
          "4": 0
        },
        "total_cells": 5,
        "non_empty_cells": 5,
        "data_density": 1.0
      },
      "pandas_df": [
        {
          "0": "Signal",
          "1": "IO",
          "2": "Descripti\non",
          "3": "connexi\non",
          "4": "Type"
        }
      ]
    },
    {
      "index": 2,
      "metrics": {
        "shape": [
          5,
          5
        ],
        "columns": [
          "0",
          "1",
          "2",
          "3",
          "4"
        ],
        "dtypes": {
          "0": "object",
          "1": "object",
          "2": "object",
          "3": "object",
          "4": "object"
        },
        "null_counts": {
          "0": 0,
          "1": 0,
          "2": 0,
          "3": 0,
          "4": 0
        },
        "total_cells": 25,
        "non_empty_cells": 18,
        "data_density": 0.72
      },
      "pandas_df": [
        {
          "0": "clk_i",
          "1": "in\nin\nin\nou\nt",
          "2": "Subsyste\nm Clock",
          "3": "SUBSY\nSTEM",
          "4": "logic"
        },
        {
          "0": "rst_ni",
          "1": "",
          "2": "Asynchro\nnous reset\nactive low",
          "3": "SUBSY\nSTEM",
          "4": "logic"
        },
        {
          "0": "vpc_i\nin\nVirtual PC\nCACHE\nlogic[CVA6Cfg.VLEN-1:0]",
          "1": "",
          "2": "",
          "3": "",
          "4": ""
        },
        {
          "0": "bht_updat\ne_i",
          "1": "",
          "2": "Update\nbht with\nresolved\naddress",
          "3": "EXECU\nTE",
          "4": "bht_update_t"
        },
        {
          "0": "bht_predi\nction_o",
          "1": "",
          "2": "Prediction\nfrom bht",
          "3": "FRONT\nEND",
          "4": "ariane_pkg::bht_prediction_t[CVA6Cfg.IN\nSTR_PER_FETCH-1:0]"
        }
      ]
    }
  ]
}
```