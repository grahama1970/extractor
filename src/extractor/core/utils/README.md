# Utils Module

**Role in Pipeline:** 🟢 *Crucial*

Contains shared helper functions used throughout converters, processors, and renderers.
Examples: geometric utilities (`matrix_distance`), font download, table IOU calculation, etc.

Removing it would definitely break PDF→JSON runs.

Guideline: keep generic helpers here; move domain-specific logic to a dedicated sub-package.
