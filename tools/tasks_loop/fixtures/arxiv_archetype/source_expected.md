# 1. Introduction
This document is a synthetic test fixture.

## Abstract
This paper presents a canonical ArXiv archetype for PDF extraction calibration. We focus on the intersection of layout-aware parsing and VLM-enriched data recovery.

## 1. Background
Scientific papers often use 2-column layouts to maximize data density. This tests column detection. Difficult boundaries often occur when text spans multiple lines and contains scientific notation like H₂O or CO₂. Ligatures such as 'ffi' and 'fl' can also cause issues if not mapped properly.

### Equations
∮ E · dA = Q / ε₀

## 2. Methodology
We evaluate the pipeline using a 'Twin-First' approach, injecting chaos into synthetic fixtures.

### References
[1] Doe, J. 'Scientific PDF Parsing'. 2024.

### Table 1: System Data (Configured)
| ID | Value | Description |
|---|---|---|
| R0 | VAL_0 | Data row 0 |
| R1 | VAL_1 | Data row 1 |
| R2 | VAL_2 | Data row 2 |
| R3 | VAL_3 | Data row 3 |
| R4 | VAL_4 | Data row 4 |
| R5 | VAL_5 | TABLE CONTINUES |
| R6 | VAL_6 | Data row 6 |
| R7 | VAL_7 | Data row 7 |
| R8 | VAL_8 | Data row 8 |
| R9 | VAL_9 | Data row 9 |
*(Table continues on next page...)*

| R10 | VAL_10 | Data row 10 |
| R11 | VAL_11 | Data row 11 |
| R12 | VAL_12 | Data row 12 |
| R13 | VAL_13 | Data row 13 |
| R14 | VAL_14 | Data row 14 |
| R15 | VAL_15 | Data row 15 |

# 2. Requirements
- **REQ-SYN-001**: The system shall handle synthetic data.
- **REQ-SYN-002**: The system must ignore false headers.

## Examples (Non-Normative)
This is not a requirement, just a comment.
The researchers should eventually consider testing.

## Critical Requirements
- **REQ-SCI-001**: The pipeline shall correctly segment 2-column layouts.
- **REQ-SCI-002**: Equations must be preserved as discrete blocks.