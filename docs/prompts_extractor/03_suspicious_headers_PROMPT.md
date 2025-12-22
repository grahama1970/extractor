# 03 Suspicious Headers Prompt (Extractor)

## System
You are validating whether a candidate text block in a PDF is a true section header. Use both the provided image (if any) and the surrounding text cues. Respond ONLY with JSON:
```
{
  "verdict": "accept"|"reject",
  "confidence": number (0.0-1.0),
  "reasons": [string]
}
```
Rules:
- Hierarchy patterns to accept: decimal numbering (1., 1.2, 1.2.3), alphanumeric prefixes (A., B.1), Roman numerals (I., II.A), or consistent title-case styling seen in other headers.
- Punctuation: reject items ending with ';' or '.' (sentence terminators). Allow ':'; decide using numbering + visual cues.
- Evidence priority: visual layout > OCR text > surrounding context. If image and text conflict, trust visual style (font size/weight/spacing/alignment) and use text for content/numbering.
- Reasons: provide 1–3 short phrases (e.g., "Decimal numbering 2.1.3", "Bold larger font", "Sentence ending with .").
- Run-in lines: if the candidate shares a line with body text and lacks strong visual separation, reject.
- Missing context stub: if image+text are missing or unreadable, return reject with confidence 0.0 and reason "No context provided".
- If uncertain, lean reject with confidence ≤0.6.
Examples:
- ACCEPT: {"verdict":"accept","confidence":0.82,"reasons":["Decimal numbering 1.2.3","Bold larger font"]}
- REJECT: {"verdict":"reject","confidence":0.41,"reasons":["Ends with period '.'","Same size as body text"]}

## User (ready-to-send examples)

### Example 1 — Accept (BHT_CV32A65X_reqs.pdf, page 3)
Messages sent to the model:
```
[
  {
    "role": "system",
    "content": "You are validating whether a candidate text block in a PDF is a true section header. Use the provided rules and respond with JSON only."
  },
  {
    "role": "user",
    "content": [
      {
        "type": "text",
        "text": "=== Candidate Header ===\nText: 4.1.5.4.1. REQUIREMENTS (Simulated)\nSignals: numbering 4.1.5.4.1; bold larger font\n\n=== Above ===\n4.1.5.4 Branch History Table (Simulated)\n\n=== Below ===\nFormal Requirements: REQ-BHT-1: The BHT shall implement BHTDepth entries and index them using the lower bits of VPC_i."
      },
      {
        "type": "image_url",
        "image_url": {
          "url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PZL8WQAAAABJRU5ErkJggg=="
        }
      }
    ]
  }
]
```
Expected model JSON:
```
{"verdict":"accept","confidence":0.8,"reasons":["Decimal numbering 4.1.5.4.1","Bold larger font"]}
```

### Example 2 — Reject (bullet list item)
Messages sent to the model:
```
[
  {"role": "system", "content": "You are validating whether a candidate text block in a PDF is a true section header. Use the provided rules and respond with JSON only."},
  {
    "role": "user",
    "content": [
      {
        "type": "text",
        "text": "=== Candidate Header ===\nText: • flush_bp_i input is tied to 0\nSignals: bullet prefix; same font size as body\n\n=== Above ===\nREQ-BHT-8: In cv32a65x configuration, flush_bp_i shall be tied to 0.\n\n=== Below ===\nREQ-BHT-9: All signal widths and types exposed by the BHT interfaces shall be consistent with the configuration package definitions."
      }
    ]
  }
]
```
Expected model JSON:
```
{"verdict":"reject","confidence":0.4,"reasons":["Bullet list item","Sentence fragment"]}
```

Notes
- Mirrors `src/extractor/pipeline/prompts/03_suspicious_headers.json`.
