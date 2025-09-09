Below is a concise “upgrade plan” that you can apply to the JSON you are already producing.  
It keeps the schema backward-compatible (nothing is deleted), but adds extra fields that a downstream “agent” can exploit to resolve ambiguities faster and with fewer hard-coded rules.

────────────────────────────────────────
1.  One canonical record per annotation
────────────────────────────────────────
Problem in current file  
•  The same semantic annotation appears twice – once with author/ content filled-in and once empty  
  (e.g. indices 1 & 4, 2 & 5, 3 & 6 …).  
•  Down-stream code has to de-duplicate.

Fix  
Add a boolean  `"is_empty_placeholder": false` (true for the empty duplicates).  
A post-processor can then drop the placeholders so the agent never sees them.

────────────────────────────────────────
2.  Give the agent the *exact* original text
────────────────────────────────────────
Currently the agent must reconstruct the original text from the union of `pdf_blocks` and `nearby_blocks`.  
Add a single string:

    "original_snippet": "4.1.5.4. BHT (Branch History Table) submodule"

which is already available in `nearby_blocks[0].text` for section headers, but is missing for tables / figures.  
This removes the need for fragile “join” logic.

────────────────────────────────────────
3.  Normalised bounding box
────────────────────────────────────────
Absolute coordinates are page-specific.  
Add a second rectangle expressed in *percentage of page width/height*:

    "norm_rect": [0.11, 0.04, 0.42, 0.09]   // x1,y1,x2,y2 in 0-1 range

This makes distance calculations and inter-page stitching much simpler.

────────────────────────────────────────
4.  Cross-page links for table merge
────────────────────────────────────────
`"type": "merge_table"` annotations already have high confidence, but the agent still has to *find* the matching piece on the next page.  
Add an explicit pointer:

    "continuation_ref": {
        "page": 1,
        "block_no": 37,
        "norm_rect": [0.47, 0.03, 0.77, 0.07]
    }

The extractor can compute this at run-time because it knows page order and already produced indices 9 & 12.

────────────────────────────────────────
5.  Enrich the *features* with layout hints
────────────────────────────────────────
Add a small set of extra flags that are trivial to compute but expensive for the agent to infer:

    "features": {
        …existing fields…,
        "font_size_pt": 10.5,
        "font_name": "Times-Bold",
        "is_bold": true,
        "line_height": 13.2,
        "indent_mm": 0,
        "align": "left"
    }

These are extracted directly from the PDF operator stream and help the agent decide whether “Merge Table” is a *caption* or an *instruction*.

────────────────────────────────────────
6.  Explicit “context window”
────────────────────────────────────────
Instead of a flat list `nearby_blocks`, give the agent a *window* that has already been pruned and ordered:

    "context_window": [
        { "text": "…", "role": "parent_section",  "distance_mm": 0 },
        { "text": "…", "role": "same_line",       "distance_mm": 12 },
        { "text": "…", "role": "next_paragraph",  "distance_mm": 35 }
    ]

The extractor can compute roles with simple heuristics (same-line = y-overlap, parent-section = nearest preceding header block, …).

────────────────────────────────────────
7.  Schema sketch (additions only)
────────────────────────────────────────
{
  …existing fields…,
  "is_empty_placeholder": false,
  "original_snippet": "…",
  "norm_rect": [0.11,0.04,0.42,0.09],
  "continuation_ref": { …optional… },
  "features": {
      …existing…,
      "font_size_pt": 10.5,
      "font_name": "Times-Bold",
      "is_bold": true,
      "line_height": 13.2,
      "indent_mm": 0,
      "align": "left"
  },
  "context_window": [
      { "text": "…", "role": "parent_section", "distance_mm": 0 }
  ]
}

────────────────────────────────────────
8.  What the agent gains
────────────────────────────────────────
•  No need for fragile string heuristics to reconstruct the snippet.  
•  No need to de-duplicate annotations.  
•  Distance calculations become unit-agnostic (percentages).  
•  Table stitching becomes a simple pointer chase.  
•  Layout hints (boldness, font size) make classification of “section header vs caption vs instruction” deterministic.