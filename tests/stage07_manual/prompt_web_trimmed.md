SYSTEM INSTRUCTIONS:

You are a technical editor. Given raw PDF-extracted section text plus structured context (tables with pandas metrics, figure descriptions, and nearby annotations), produce a clean Markdown reflow of the section.
- Fix broken words, hyphenation across lines, and common OCR errors.
- Keep semantics but remove duplicated headers/footers.
- Respect original table intent; do not invent data. If tables are present, incorporate them as Markdown tables only if reliable; otherwise summarize them.

Output strictly JSON with keys:
  - "reflowed_text": "string (Markdown)"
  - "ocr_corrections": {"erroneous": "corrected", ...}
  - "improvements_made": "short description of the fixes"
  - "summary": "1–3 sentences summarizing the section content"
Do not include explanations outside JSON.


USER CONTENT (paste below and upload the images listed):

Section: BHT (Branch History Table) submodule

Raw text:
4.1.5.4. BHT (Branch History Table) submodule

BHT is implemented as a memory which is composed of BHTDepth configuration parameter
entries. The lower address bits of the virtual address point to the memory entry.

When a branch instruction is resolved by the EX_STAGE module, the branch PC and the taken
(or not taken) status information is stored in the Branch History Table.

The Branch History Table is a table of two-bit saturating counters that takes the virtual address of
the current fetched instruction by the CACHE. It states whether the current branch request
should be taken or not. The two bit counter is updated by the successive execution of the
instructions as shown in the following figure.

When a branch instruction is pre-decoded by instr_scan submodule, the BHT valids whether the
PC address is in the BHT and provides the taken or not prediction.

The BHT is never flushed.

SignalIODescripticonnexiTypeonon

clk_iinSubsyste
m ClockSUBSY
STEMlogicrst_niinAsynchro
nous reset
active lowSUBSY
STEMlogicvpc_iinVirtual PCCACHElogic[CVA6Cfg.VLEN-1:0]bht_updat
e_iinUpdate
bht with
resolved
addressEXECU
TEbht_update_tbht_predi
ction_oou
tPrediction
from bhtFRONT
ENDariane_pkg::bht_prediction_t[CVA6Cfg.IN
STR_PER_FETCH-1:0]

Due to cv32a65x configuration, some ports are tied to a static value. These ports do not appear in
the above table, they are listed below

For any HW configuration,

● flush_bp_i input is tied to 0

As DebugEn = False,

● debug_mode_i input is tied to 0

● flush_bp_i input is tied to 0

● debug_mode_i input is tied to 0

Table summary:
Shape: (1, 5) columns: 0, 1, 2, 3, 4

Tables sample rows (all tables, up to 3 rows each):
- table1 (density=1.0, dtypes={"0": "object", "1": "object", "2": "object", "3": "object", "4": "object"}):
[
  {
    "0": "Signal",
    "1": "IO",
    "2": "Descripti\non",
    "3": "connexi\non",
    "4": "Type"
  }
]
- table2 (density=0.72, dtypes={"0": "object", "1": "object", "2": "object", "3": "object", "4": "object"}):
[
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
  }
]

Figure description:
Figure present; automated description unavailable due to model response. Please review the nearby text context.

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


Section JSON (sanitized; full embedded below and written to tests/stage07_manual/section_full_sanitized.json):

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


API REQUEST EXAMPLES (for reference):

OpenAI Responses (JSON mode) skeleton:
```json
{
  "model": "gpt-5-mini",
  "response_format": {
    "type": "json_object"
  },
  "input": [
    {
      "role": "user",
      "content": [
        {
          "type": "input_text",
          "text": "<paste USER CONTENT text>"
        },
        {
          "type": "input_image",
          "image_url": "<attach images via UI>"
        }
      ]
    }
  ]
}
```

Chat Completions skeleton:
```json
{
  "model": "gpt-5-mini",
  "messages": [
    {
      "role": "system",
      "content": "<paste SYSTEM INSTRUCTIONS>"
    },
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "<paste USER CONTENT text>"
        },
        {
          "type": "image_url",
          "image_url": {
            "url": "<attach images via UI>"
          }
        }
      ]
    }
  ]
}
```

Full payload files are generated alongside this prompt:
 - tests/stage07_manual/responses_input.json
 - tests/stage07_manual/chat_messages.json

Attach these images in the chat UI (do not change filenames):
 - images/section.png
 - images/table1.png
 - images/table2.png
 - images/figure1.png
 - images/annotation1.png
 - images/annotation2.png

Trimmed Attach List (auto-triage applied):
 - images/section.png