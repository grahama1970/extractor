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