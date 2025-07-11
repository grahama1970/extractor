# Processors Module

**Role in Pipeline:** 🟢 *Crucial*

Processors perform **content-specific post-processing** on the `Document` after conversion but before rendering. Examples:

| Category | Examples |
|----------|----------|
| Clean-up | merging hyphenated words, fixing encoding glitches |
| Structure | detecting section hierarchy, abstract, references |
| Tables    | post-merging cell spans, header detection |
| Images    | running figure caption heuristics |

They are linked from the converters and run automatically; removing this package would break PDF→JSON fidelity.

Sub-directories are named by domain (e.g. `text/`, `tables/`, `math/`). Stub or experimental processors can be moved later, but the directory itself stays.
