# 09 Section Summarizer Prompt (Extractor)

## System (ready to send)
```
You are a JSON-only assistant. Respond with exactly one JSON object matching {
  "summary": "concise summary",
  "sentence_count": integer,
  "key_concepts": ["concept1", "concept2", "..."] (3–7 items)
}. Do not include text outside the JSON object. If input text is empty or insufficient, return an empty string for summary and an empty list for key_concepts (but still valid JSON).
```

## User (ready to send example)
```
Summarize the following document section in 2–4 sentences and list 3–7 key concepts.
Keep the summary consistent with any previous summaries provided.

Previous summaries:
- 4.1.5.4 Branch History Table (Simulated): The BHT uses two-bit saturating counters indexed by VPC bits to predict branches and updates on resolution.

Section title: 4.1.5.4.1. REQUIREMENTS (Simulated)
Level: 3
Text:
The BHT uses two-bit saturating counters indexed by the lower bits of the Virtual PC (VPC) and updates on branch resolution in the execute stage, providing predictions to the front end.
REQ-BHT-1: The BHT shall implement BHTDepth entries and index them using the lower bits of VPC_i.
REQ-BHT-2: Each BHT entry shall contain a two-bit saturating counter that encodes taken/not-taken and shall saturate at its limits.
REQ-BHT-3: The BHT shall accept update information from the execute stage including the branch PC and resolved outcome, and shall update the corresponding counter accordingly.
REQ-BHT-4: The BHT shall provide a prediction output aligned with the front-end fetch group width.
REQ-BHT-5: The BHT shall not be flushed by pipeline events; only rst_ni initializes internal state.
REQ-BHT-6: The subsystem clock clk_i and asynchronous active-low reset rst_ni shall be the only clock/reset inputs required for BHT operation.
REQ-BHT-7: When a branch is pre-decoded, the BHT shall indicate whether the address hits and return the taken/not-taken prediction in the same fetch cycle when available.
REQ-BHT-8: In cv32a65x configuration, flush_bp_i shall be tied to 0; when DebugEn is False, debug_mode_i shall be tied to 0.
REQ-BHT-9: All signal widths and types exposed by the BHT interfaces shall match the configuration package definitions.
REQ-BHT-10: The prediction datapath shall not introduce structural hazards with instruction fetch; updates shall not stall front-end prediction availability.

Return strictly JSON:
{
  "summary": "concise summary",
  "sentence_count": integer,
  "key_concepts": ["concept1", "concept2", "..."]
}
```

## Expected model output (example)
```
{
  "summary": "Requirements specify a two-bit counter BHT indexed by VPC bits, updated on branch resolution, delivering front-end predictions without stalls. It defines interface signals, reset behavior, and ties flush/debug controls in the cv32a65x configuration.",
  "sentence_count": 3,
  "key_concepts": ["BHT depth", "saturating counters", "branch prediction", "execute-stage updates"]
}
```
