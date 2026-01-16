# Bug: Headers Priors Stub Module

---

bug_id: headers_priors_stub
title: "Remove or Implement headers/priors.py Stub"
status: done
severity: low
reported: 2024-01-15

symptoms:

- File `src/extractor/pipeline/utils/headers/priors.py` contains only stub code
- Users start asking "What is this?"

resolution:

- Validated it was unused in `s03_suspicious_headers.py`
- Removed all imports
- Deleted the file

gate: null
fix_criteria:
stub_removed_or_implemented: true

context:

- file:///home/graham/workspace/experiments/extractor/src/extractor/pipeline/utils/headers/priors.py

---

## Analysis

This was a stub for a future feature that was never implemented. It was causing confusion.
Upon review, the import in `s03` was unused, so the file was safe to delete.

## Resolution

- Removed import from `src/extractor/pipeline/steps/s03_suspicious_headers.py`.
- Removed from `src/extractor/pipeline/utils/headers/__init__.py`.
- Deleted `src/extractor/pipeline/utils/headers/priors.py`.
