Clarifying questions (to lock acceptance)

  - Sections
      - Please confirm the 3 expected reflowed section titles
        (or top‑level headings) so I can assert by title, not
        just count.
        > there are 3 sections. You are trating the section with (Continued) as the same seection
  - Merged table
      - Do we have a canonical header key (e.g., “Table 4‑1 …
        continued”) to anchor the multi‑page merge, or should I
        rely on exact header row similarity + adjacency across
        pages 0–1?
        > the table header is the first table on page 0. it's a single row and shuld be identified by camelot
  - Figure explanation
      - Should the overlay label include a truncated caption,
        or is it sufficient to store the caption in the PDF
        annotation comment (current 09a behavior) and keep a
        compact “FIG” label on the page?
        > the figure should be an scillm chutes call for a proper explanation. If there is a surrounding title, include the title, as you have code for this which expands the extracted figure
  - Requirements: conditional definition
      - Is the keyword heuristic acceptable (“if”, “when”,
        “unless”, “provided that”, “only when”), or do you have
        an explicit rulebook you want applied?
        > look at /home/graham/workspace/experiments/extractor/src/extractor/pipeline/steps/07_requirements_miner.py
        are the rules NOT clear to you