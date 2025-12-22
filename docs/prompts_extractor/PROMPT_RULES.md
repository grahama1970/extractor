# Prompt Rules (Aligned with memory/devops shared conventions)

Use this checklist before running Kimi grading. It merges the common P0/P1 fixes used in
memory/devops.

## Schema & enums
- Keep schema and rules identical; no extra/undefined fields. Enums must match the text.
- Provide explicit failure stub JSON for missing/illegible input; include it in the schema.
- If ranges (confidence, sentence_count, etc.) are used, make them mutually exclusive and ordered; add a tie-breaker.

## Slots / missing fields
- Define behavior for missing/empty/non-string slots at top-level and per-item. State whether to null, stub, or drop.
- Always include all declared keys; use null/empty when unknown.

## Fallbacks / fences
- JSON only; one fence if fences are used. If output would be non-JSON, emit the global stub.
- Provide the exact stub literal inline (no placeholders or ellipses).

## Word-count / length clarity
- State the count algorithm once and whether ranges are inclusive. Clarify hyphenated token handling if relevant.

## Evidence priority (multimodal)
- Specify priority between image vs. OCR text vs. context when they conflict.

## Examples
- At least one positive and one edge/negative example. Include failure-stub example. No ellipses/placeholders; use realistic payloads (base64 images where applicable).
- Assistant examples must include every required field from the schema.

## Confidence / uncertainty
- If binary decisions exist, include a confidence field with 0–1 guidance and how to lower confidence when uncertain.

## Forbidden/unsafe content
- If applicable, instruct a final scan and stub if forbidden tokens are present.

## Header/meta bloat
- Keep system messages minimal; no markdown headers inside the system text.

## Attempt budget
- Max 3 grading attempts. If still failing, rewrite the prompt and regrade.
