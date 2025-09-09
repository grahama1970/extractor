# Lean 4 Theorem Prover - PDF Object Schema Extensions

## New Fields Added by Stage 09

### For Text Blocks (object_type: "text")

```json
{
  "object_id": "existing_field",
  "object_type": "text",
  "text": "existing_field",
  
  // NEW FIELDS:
  "formal_requirements": [
    {
      "requirement": {
        "requirement_text": "The system shall provide authentication within 2 seconds",
        "modal_verb": "shall",
        "subject": "The system",
        "predicate": "provide authentication within 2 seconds",
        "source_type": "sentence",
        "list_position": null,
        "has_dependency": false,
        "confidence": 0.95,
        "source_block_id": "text_001",
        "source_page": 5,
        "source_section": ["2. Requirements", "2.1 Performance"]
      },
      "proof_result": {
        "status": "proved",
        "proof": "theorem requirement_001 : ∀ (s : System), s.authTime ≤ 2 := by ...",
        "tactics_used": ["intros", "apply", "exact"],
        "assumptions": ["System.authTime : ℝ≥0"]
      },
      "proof_duration_seconds": 45.3,
      "proof_timestamp": "2024-01-15T10:30:45Z",
      "success": true
    }
  ],
  "has_requirements": true,
  "requirement_count": 3,
  "proved_count": 2
}
```

### For Tables (object_type: "table")

```json
{
  "object_id": "existing_field",
  "object_type": "table",
  "pandas_df_dict": "existing_field",
  
  // NEW FIELDS:
  "formal_constraints": [
    {
      "constraint": {
        "constraint_text": "Temperature range must be between -40°C and 85°C",
        "constraint_type": "range",
        "parameters": {
          "temperature_min": -40,
          "temperature_max": 85,
          "unit": "celsius"
        },
        "source_cell": "row=3,col=2",
        "confidence": 0.98,
        "source_table_id": "table_005",
        "source_page": 12,
        "table_title": "Operating Conditions"
      },
      "proof_result": {
        "status": "verified",
        "proof": "theorem constraint_001 : ∀ (t : Temperature), -40 ≤ t.value ∧ t.value ≤ 85 := by ...",
        "verification_method": "smt_solver",
        "solver_output": "sat"
      },
      "proof_duration_seconds": 62.1,
      "proof_timestamp": "2024-01-15T10:32:15Z",
      "success": true
    }
  ],
  "has_constraints": true,
  "constraint_count": 5,
  "verified_count": 4
}
```

## Pipeline Metadata Fields

Added to the top-level pipeline data:

```json
{
  "pdf_objects": [...],
  
  // NEW FIELD:
  "lean4_processing": {
    "timestamp": "2024-01-15T10:35:00Z",
    "requirements_found": 42,
    "constraints_found": 15,
    "requirements_proved": 38,
    "constraints_verified": 14,
    "total_proof_time_seconds": 2847.5
  }
}
```

## Field Descriptions

### Requirement Fields
- `formal_requirements`: Array of requirement proofs extracted from text
- `has_requirements`: Boolean flag for quick filtering
- `requirement_count`: Total requirements found in this block
- `proved_count`: How many were successfully proved

### Requirement Object Fields
- `requirement_text`: The complete requirement statement
- `modal_verb`: Modal verb used (shall/must/will/should)
- `subject`: Who/what must fulfill the requirement
- `predicate`: What must be done
- `source_type`: Whether from a sentence or list item
- `list_position`: Position in list (1, 2, 3...) or null
- `has_dependency`: Boolean indicating if requirement references previous steps/conditions
- `confidence`: LLM confidence in extraction (0.0-1.0)
- `source_block_id`: ID of the source text block
- `source_page`: Page number in the PDF
- `source_section`: Section hierarchy path

### Constraint Fields  
- `formal_constraints`: Array of constraint proofs from tables
- `has_constraints`: Boolean flag for quick filtering
- `constraint_count`: Total constraints found in this table
- `verified_count`: How many were successfully verified

### Proof Result Fields
- `status`: "proved", "verified", "failed", or "error"
- `proof`: The actual Lean 4 proof code
- `tactics_used`: Lean 4 tactics employed
- `assumptions`: Required assumptions for the proof
- `verification_method`: For constraints (e.g., "smt_solver")
- `solver_output`: SMT solver results

## Usage in ArangoDB

These fields enable queries like:

```aql
// Find all proved requirements
FOR obj IN pdf_objects
  FILTER obj.has_requirements == true
  FOR req IN obj.formal_requirements
    FILTER req.success == true
    RETURN {
      text: req.requirement.requirement_text,
      proof: req.proof_result.proof,
      section: req.requirement.source_section
    }

// Find unverified table constraints
FOR obj IN pdf_objects
  FILTER obj.object_type == "table" AND obj.has_constraints == true
  LET failed = (
    FOR c IN obj.formal_constraints
      FILTER c.success == false
      RETURN c
  )
  FILTER LENGTH(failed) > 0
  RETURN {
    table: obj.table_title,
    failed_constraints: failed
  }

// Find requirements with dependencies
FOR obj IN pdf_objects
  FILTER obj.has_requirements == true
  FOR req IN obj.formal_requirements
    FILTER req.requirement.has_dependency == true
    RETURN {
      requirement: req.requirement.requirement_text,
      section: req.requirement.source_section,
      page: req.requirement.source_page,
      proved: req.success,
      list_position: req.requirement.list_position
    }
```