# Definition of Done (DoD) Checklist

This checklist ensures every task has verifiable completion criteria before implementation begins.

## Pre-Implementation Checklist

Before starting any task, verify:

- [ ] **Questions/Blockers** resolved (marked "None" in task file)
- [ ] **Sanity scripts** exist and pass for non-standard dependencies
- [ ] **Definition of Done** section exists with:
  - Test file path and function name
  - Assertion describing what the test proves

## Definition of Done Format

Every task must have this section:

```markdown
## Definition of Done

- **Test**: `tests/path/to/test_file.py::test_function_name`
- **Assertion**: [What the test proves in plain English]
```

### Examples

#### Good DoD (Specific, Verifiable)

```markdown
## Definition of Done

- **Test**: `tests/core/providers/test_docx_provider.py::test_docx_provider_basic_extraction`
- **Assertion**: DOCXProvider extracts headings as HEADING blocks, paragraphs as TEXT blocks
```

#### Good DoD (Multiple Tests)

```markdown
## Definition of Done

- **Test**: `tests/pipeline/test_s11_lean4.py::test_lean4_proof_compiles`
- **Test**: `tests/pipeline/test_s11_lean4.py::test_lean4_invalid_proof_fails`
- **Assertion**: Lean4 step validates theorem proofs, rejects invalid proofs with exit code 1
```

#### Bad DoD (Vague, Not Verifiable)

```markdown
## Definition of Done

- Tests pass
- Code works correctly
- Feature implemented
```

## Sanity Script Requirements

For non-standard dependencies (NOT json, pathlib, requests, numpy, pandas):

| Criteria | Required |
|----------|----------|
| Shows correct imports | Yes |
| Documents parameters | Yes |
| Provides working example | Yes |
| Exit codes: 0=PASS, 1=FAIL, 42=CLARIFY | Yes |

### When Sanity Scripts Are Required

- Little-known packages (camelot, ebooklib, marker)
- Complex APIs (pdftext, transformers)
- User-generated code
- Any dependency where the API is non-obvious

### When Sanity Scripts Are NOT Required

- Standard library (json, os, pathlib, typing)
- Well-known packages (requests, numpy, pandas, pytest)
- Rule: "If a junior dev could use it from memory, skip sanity"

## Verification Commands

```bash
# Run all sanity scripts
for f in tools/tasks_loop/sanity/*.py; do python "$f" || exit 1; done

# Run specific test
pytest tests/path/to/test_file.py::test_function_name -v

# Collect tests (check for import errors)
pytest tests/ --collect-only

# Run quality gate
make smokes-cli
```

## Task Completion Flow

```
1. Task defined with DoD section
       ↓
2. Sanity scripts verified (if needed)
       ↓
3. Implementation begins
       ↓
4. Run DoD tests
       ↓
   ┌───────────────┐
   │ Tests pass?   │
   └───────┬───────┘
       ↓ Yes    ↓ No
   Mark done    Fix and retry
```

## Exit Codes

| Code | Meaning | Action |
|------|---------|--------|
| 0 | PASS | Task complete |
| 1 | FAIL | Fix issues |
| 42 | CLARIFY | Need human input |
| 3 | SKIP | NOT allowed for implementation tasks |
