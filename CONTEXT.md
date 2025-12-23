# Pipeline Refactoring Status: "Broken Extraction"

## Current Situation

The pipeline refactoring (splitting large step files into `steps/` + `utils/runner.py`) was performed aggressively but seemingly without sufficient care for dependencies.

**Status:**

- **09a**: Fixed dead code, seems okay.
- **01 (Annotation Processor)**: ✅ NOW WORKING after fixing missing imports (`sys`, `fitz`, `Config`) and package shadowing.
- **02 (Marker Extractor)**: ❌ FAILING due to missing `import uuid` in `marker_runner.py`.
- **General Pattern**: Most extracted runner files are likely missing imports (`sys`, `json`, `uuid`, etc.) and helper classes (`Config`) that were left behind in the step files.

## Identified "Aspirational" Patterns

1. **Missing Imports**: Functions moved to `utils/runner.py` use modules (`uuid`, `sys`, `fitz`) that aren't imported.
2. **Missing Definitions**: Classes like `Config` are used in runners but defined in step files (circular dependency risk).
3. **Missing Exports**: Step files import `run` from runners, but sometimes the runner or `__init__.py` isn't set up correctly.
4. **Package Shadowing**: Creating `utils/annotations/` directory shadowed existing `utils/annotations.py` module, breaking downstream imports (03).

## Immediate Goal

Stop "whack-a-mole" fixing. We need to:

1. Scan ALL extracted runners for missing imports (lint/static analysis).
2. Fix 02 (`uuid`) and then likely 03, 04, etc.
3. Be honest with Copilot: the refactoring structure is correct, but the execution left broken code.
