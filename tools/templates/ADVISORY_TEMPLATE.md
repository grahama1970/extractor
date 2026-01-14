# Advisory (Fuzzy) Check Template

Advisory checks are **non-blocking**. They should never decide PASS/FAIL unless you're okay with flakiness.

## Inputs (artifacts)
Specify what the judge will inspect:
- file snapshots (e.g., JSON output, HTML output, diff)
- logs
- screenshots (if applicable)

## Rubric
- 0–10 score with short justification
- 3 concrete improvement suggestions

## Example prompt
"""
Review the artifact(s) below.
Return:
- score 0–10
- 3 actionable suggestions
"""

## Output location
Write results to:
- `soft_judge.txt` (or `out/advisory_<task>.txt`)
