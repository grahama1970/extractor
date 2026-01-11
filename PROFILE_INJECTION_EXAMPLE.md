# S08 Profile Injection - Example Prompt

## How Profile Becomes Few-Shot Prompt

### Input: PDF Profile

```json
{
  "requirement_type_examples": {
    "formal_with_id": {
      "input": "REQ-BHT-1: The BHT shall implement BHTDepth entries...",
      "output": { "id": "REQ-BHT-1", "text": "...", "type": "Function" }
    },
    "conditional": {
      "input": "When reset is asserted, all counters shall return to 2'b01.",
      "output": {
        "id": null,
        "text": "...",
        "is_conditional": true,
        "condition_text": "When reset is asserted"
      }
    }
  }
}
```

### Output: LLM Prompt (System Message)

```
You are a Requirements Engineer extracting requirements from hardware specifications.

DOCUMENT PROFILE:
This document uses the following requirement formats:

1. FORMAL WITH ID
   Input:  "REQ-BHT-1: The BHT shall implement BHTDepth entries and index them using the lower bits of VPC_i."
   Output: {"id": "REQ-BHT-1", "text": "The BHT shall implement BHTDepth entries...", "type": "Function", "confidence": 0.99}

2. CONDITIONAL
   Input:  "When reset is asserted, all BHT counters shall return to the weakly-not-taken state (2'b01)."
   Output: {"id": null, "text": "All BHT counters shall return to the weakly-not-taken state", "type": "Function", "is_conditional": true, "condition_text": "When reset is asserted"}

3. TABLE-BASED
   Input:  "Table Row: bht_prediction_o | out | Prediction from bht | FRONT END | ariane_pkg::bht_prediction_t"
   Output: {"id": null, "text": "The bht_prediction_o signal shall be an output...", "type": "Interface", "is_table_row": true}

EXTRACTION RULES:
- Requirements contain modal verbs: shall, must, will
- Conditional requirements have: when, if, unless clauses
- Provide VERBATIM citation_snippet for each requirement
- Maintain source order

Now extract from this section:
```

### User Message

```
Section: "4.1.5.4.1. REQUIREMENTS (Simulated)"

TEXT:
This simulated section provides formal, hardware-oriented requirements for the Branch History Table...

REQ-BHT-1: The BHT shall implement BHTDepth entries and index them using...
REQ-BHT-2: Each BHT entry shall contain a two-bit saturating counter...

Conditional Requirements:

When reset is asserted, all BHT counters shall return to...
```

### Expected LLM Response

```json
[
  {
    "id": "REQ-BHT-1",
    "text": "The BHT shall implement BHTDepth entries and index them using the lower bits of VPC_i",
    "type": "Function",
    "confidence": 0.99,
    "citation_snippet": "REQ-BHT-1: The BHT shall implement BHTDepth entries...",
    "is_conditional": false
  },
  {
    "id": "REQ-BHT-2",
    "text": "Each BHT entry shall contain a two-bit saturating counter",
    "type": "Function",
    "confidence": 0.99,
    "is_conditional": false
  },
  {
    "id": null,
    "text": "All BHT counters shall return to the weakly-not-taken state",
    "type": "Function",
    "confidence": 0.95,
    "is_conditional": true,
    "condition_text": "When reset is asserted"
  }
]
```

## Implementation

```python
def build_prompt_with_profile(section_data, profile_path):
    profile = json.loads(profile_path.read_text())

    # Build system message with examples
    system_msg = "You are a Requirements Engineer.\n\nDOCUMENT PROFILE:\n"

    for req_type, example in profile["requirement_type_examples"].items():
        system_msg += f"\n{example['description'].upper()}\n"
        system_msg += f"Input:  \"{example['input']}\"\n"
        system_msg += f"Output: {json.dumps(example['output'])}\n"

    system_msg += "\n" + profile["extraction_instructions"]["for_llm"]

    # User message with actual content
    user_msg = f"Section: \"{section_data['title']}\"\n\nTEXT:\n{section_data['text']}"

    return {
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg}
        ]
    }
```

This transforms the profile into a **few-shot learning prompt** automatically.
