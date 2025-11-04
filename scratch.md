Clarifying questions (to lock acceptance)

  - Sections
      - Please confirm the 3 expected reflowed section titles
        (or top‑level headings) so I can assert by title, not
        just count.
        > We need section heirarchu as well, do you recall the step: src/extractor/pipeline/steps/04_section_builder.py ?
       - 4.1.5.4. BHT (Branch History Table) submodule
          - 4.1.5.4.1. REQUIREMENTS (Simulated)
       - 4.1.5. TABLE MERGE SCENARIOS (Simulated)

- Tables (Stage 05 vs Stage 07)
      - Your gold says “1 merged (pages 0+1) + 4 unmerged.” Should this be enforced in Stage
  07 (logical) only, or do you also want a Stage 05 raw count invariant (exact or a range)?
  the sketcher and reflow step determine if a table should merge
  - Merge detail
      - For the merged group, do you want the pages array fixed to [0,1] and a minimum row
  count, or just presence of that pair?
   > user your best judgment. a page span array like [start,end] is acceptable


  - Figures (Stage 06)
      - Enforce only count==1, or also page==0 and bbox within a tolerance (e.g., page
  width/height ranges)?
> we should imc;lude thart data and the figure description from the scillm chutes call

  - Requirements (Stage 07r)
      - Lock to exact total (36) or keep “>=10” as you originally stated? Confirm
  “conditional==2” as the gold. Any other buckets (by_source, by_section) to pin?
  - Formalization
      - You mentioned “how many were formalized.” Do we have a gold count for “formalized/proved” to assert now?
  > we do not yet. For now, >=10 is fine. We need to see what scillm/certainly generates first in the pipeline step

  - Text/content checks
      - Any section-level text substrings you want guaranteed present (e.g., section titles or key phrases), or keep structural only?
      > I don't understand what you mean. src/extractor/pipeline/steps/04_section_builder.py should have all the relevamt code
  - Tolerances vs exact
      - Should counts be exact equals, or allow small drift (±1) where OCR/table heuristics
      > drift is fine for now
  may fluctuate?
  - Env pinning
      - OK to bake STAGE07REQ_STRICT_CONDITIONAL=1 into the verifier run for this PDF so the
  2 conditionals stay stable?
  > this is fine for npow
  - CI wiring
      - Confirm: use SPARTA_INVARIANTS=config/invariants/
  with_requirements_noannots_clean.json as the CI gate for this PDF, fail on any mismatch.
  > proceed