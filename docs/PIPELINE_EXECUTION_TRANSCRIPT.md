# PDF Extraction Pipeline - Complete Execution Transcript

**Date**: 2025-07-31 14:30:16
**Test PDF**: proof_of_concept/BHT_CV32A65X_marked.pdf
**Working Directory**: tmp/transcript_test

This document shows the COMPLETE raw output from running each stage of the PDF extraction pipeline.

---

## Stage 1: Extract Annotations

### Help
### Stage 1 Help

**Command:**
```bash
/home/graham/workspace/experiments/extractor/.venv/bin/python -m extractor.core.processors.enhanced_annotation_extractor --help
```

**Exit Code:** 0

**STDOUT:**
```
                                                                                
 Usage: python -m extractor.core.processors.enhanced_annotation_extractor       
            [OPTIONS] COMMAND [ARGS]...                                         
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --install-completion          Install completion for the current shell.      │
│ --show-completion             Show completion for the current shell, to copy │
│                               it or customize the installation.              │
│ --help                        Show this message and exit.                    │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ extract   Extract annotations from a PDF file with rich metadata.            │
│ test      Run test on sample PDF.                                            │
╰──────────────────────────────────────────────────────────────────────────────╯


```

**STDERR:**
```
2025-07-31 14:30:19.804 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:117 - Discovering strategies in: /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators
2025-07-31 14:30:19.805 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/table.py: name 'table' is not defined
2025-07-31 14:30:19.805 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: field_presence
2025-07-31 14:30:19.805 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: length_check
2025-07-31 14:30:19.805 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: format_check
2025-07-31 14:30:19.805 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: type_check
2025-07-31 14:30:19.805 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: range_check
2025-07-31 14:30:19.805 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: field_presence
2025-07-31 14:30:19.805 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: field_presence
2025-07-31 14:30:19.805 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: field_presence in base.py
2025-07-31 14:30:19.805 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: format_check
2025-07-31 14:30:19.805 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: format_check
2025-07-31 14:30:19.805 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: format_check in base.py
2025-07-31 14:30:19.805 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: length_check
2025-07-31 14:30:19.805 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: length_check
2025-07-31 14:30:19.805 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: length_check in base.py
2025-07-31 14:30:19.805 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: range_check
2025-07-31 14:30:19.805 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: range_check
2025-07-31 14:30:19.805 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: range_check in base.py
2025-07-31 14:30:19.805 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: type_check
2025-07-31 14:30:19.805 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: type_check
2025-07-31 14:30:19.805 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: type_check in base.py
2025-07-31 14:30:19.806 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/code.py: name 'code' is not defined
2025-07-31 14:30:19.806 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/string_corpus.py: name 'string_corpus' is not defined
2025-07-31 14:30:19.806 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/citation.py: invalid syntax (citation.py, line 3)
2025-07-31 14:30:19.806 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/math.py: name 'math' is not defined
2025-07-31 14:30:19.806 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/general.py: name 'general' is not defined
2025-07-31 14:30:19.806 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/value.py: name 'value' is not defined
2025-07-31 14:30:19.806 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/image.py: name 'image' is not defined
WARNING:root:granger_common not available - using standard PDF processing

```

---
### Stage 1 Execute

**Command:**
```bash
/home/graham/workspace/experiments/extractor/.venv/bin/python -m extractor.core.processors.enhanced_annotation_extractor extract tmp/transcript_test/test.pdf --output tmp/transcript_test/annotations.json
```

**Exit Code:** 0

**STDOUT:**
```
Extracting annotations from: tmp/transcript_test/test.pdf
✓ Extraction complete!
  Input: tmp/transcript_test/test.pdf
  Output: tmp/transcript_test/annotations.json
  Status: success
  Annotations: 6
  Placeholders: 0

Annotation types found:
  - figure: 1
  - merge_table: 2
  - not_section_header: 2
  - section_header: 1

```

**STDERR:**
```
2025-07-31 14:30:27.305 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:117 - Discovering strategies in: /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators
2025-07-31 14:30:27.305 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/table.py: name 'table' is not defined
2025-07-31 14:30:27.306 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: field_presence
2025-07-31 14:30:27.306 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: length_check
2025-07-31 14:30:27.306 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: format_check
2025-07-31 14:30:27.306 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: type_check
2025-07-31 14:30:27.306 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: range_check
2025-07-31 14:30:27.306 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: field_presence
2025-07-31 14:30:27.306 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: field_presence
2025-07-31 14:30:27.306 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: field_presence in base.py
2025-07-31 14:30:27.306 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: format_check
2025-07-31 14:30:27.306 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: format_check
2025-07-31 14:30:27.306 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: format_check in base.py
2025-07-31 14:30:27.306 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: length_check
2025-07-31 14:30:27.306 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: length_check
2025-07-31 14:30:27.306 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: length_check in base.py
2025-07-31 14:30:27.306 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: range_check
2025-07-31 14:30:27.306 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: range_check
2025-07-31 14:30:27.306 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: range_check in base.py
2025-07-31 14:30:27.306 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: type_check
2025-07-31 14:30:27.306 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: type_check
2025-07-31 14:30:27.306 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: type_check in base.py
2025-07-31 14:30:27.306 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/code.py: name 'code' is not defined
2025-07-31 14:30:27.306 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/string_corpus.py: name 'string_corpus' is not defined
2025-07-31 14:30:27.307 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/citation.py: invalid syntax (citation.py, line 3)
2025-07-31 14:30:27.307 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/math.py: name 'math' is not defined
2025-07-31 14:30:27.307 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/general.py: name 'general' is not defined
2025-07-31 14:30:27.307 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/value.py: name 'value' is not defined
2025-07-31 14:30:27.307 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/image.py: name 'image' is not defined
WARNING:root:granger_common not available - using standard PDF processing

```

---

## Stage 3: Create Clean PDF

### Stage 3 Help

**Command:**
```bash
/home/graham/workspace/experiments/extractor/.venv/bin/python -m extractor.core.processors.pdf_cleaner --help
```

**Exit Code:** 0

**STDOUT:**
```
                                                                                
 Usage: python -m extractor.core.processors.pdf_cleaner [OPTIONS] COMMAND       
                                                        [ARGS]...               
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --install-completion          Install completion for the current shell.      │
│ --show-completion             Show completion for the current shell, to copy │
│                               it or customize the installation.              │
│ --help                        Show this message and exit.                    │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ clean   Clean a PDF by removing annotations.                                 │
│ test    Run test on sample PDF.                                              │
╰──────────────────────────────────────────────────────────────────────────────╯


```

**STDERR:**
```
2025-07-31 14:30:34.910 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:117 - Discovering strategies in: /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators
2025-07-31 14:30:34.910 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/table.py: name 'table' is not defined
2025-07-31 14:30:34.910 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: field_presence
2025-07-31 14:30:34.910 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: length_check
2025-07-31 14:30:34.910 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: format_check
2025-07-31 14:30:34.910 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: type_check
2025-07-31 14:30:34.910 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: range_check
2025-07-31 14:30:34.910 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: field_presence
2025-07-31 14:30:34.910 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: field_presence
2025-07-31 14:30:34.910 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: field_presence in base.py
2025-07-31 14:30:34.910 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: format_check
2025-07-31 14:30:34.910 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: format_check
2025-07-31 14:30:34.910 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: format_check in base.py
2025-07-31 14:30:34.910 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: length_check
2025-07-31 14:30:34.911 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: length_check
2025-07-31 14:30:34.911 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: length_check in base.py
2025-07-31 14:30:34.911 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: range_check
2025-07-31 14:30:34.911 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: range_check
2025-07-31 14:30:34.911 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: range_check in base.py
2025-07-31 14:30:34.911 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: type_check
2025-07-31 14:30:34.911 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: type_check
2025-07-31 14:30:34.911 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: type_check in base.py
2025-07-31 14:30:34.911 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/code.py: name 'code' is not defined
2025-07-31 14:30:34.911 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/string_corpus.py: name 'string_corpus' is not defined
2025-07-31 14:30:34.911 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/citation.py: invalid syntax (citation.py, line 3)
2025-07-31 14:30:34.911 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/math.py: name 'math' is not defined
2025-07-31 14:30:34.911 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/general.py: name 'general' is not defined
2025-07-31 14:30:34.911 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/value.py: name 'value' is not defined
2025-07-31 14:30:34.912 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/image.py: name 'image' is not defined
WARNING:root:granger_common not available - using standard PDF processing

```

---
### Stage 3 Execute

**Command:**
```bash
/home/graham/workspace/experiments/extractor/.venv/bin/python -m extractor.core.processors.pdf_cleaner clean tmp/transcript_test/test.pdf --output tmp/transcript_test/clean.pdf
```

**Exit Code:** 0

**STDOUT:**
```
✓ PDF cleaned successfully!
  Input: tmp/transcript_test/test.pdf
  Output: tmp/transcript_test/clean.pdf
  Annotations removed: 6

```

**STDERR:**
```
2025-07-31 14:30:42.515 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:117 - Discovering strategies in: /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators
2025-07-31 14:30:42.515 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/table.py: name 'table' is not defined
2025-07-31 14:30:42.515 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: field_presence
2025-07-31 14:30:42.515 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: length_check
2025-07-31 14:30:42.515 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: format_check
2025-07-31 14:30:42.516 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: type_check
2025-07-31 14:30:42.516 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: range_check
2025-07-31 14:30:42.516 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: field_presence
2025-07-31 14:30:42.516 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: field_presence
2025-07-31 14:30:42.516 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: field_presence in base.py
2025-07-31 14:30:42.516 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: format_check
2025-07-31 14:30:42.516 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: format_check
2025-07-31 14:30:42.516 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: format_check in base.py
2025-07-31 14:30:42.516 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: length_check
2025-07-31 14:30:42.516 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: length_check
2025-07-31 14:30:42.516 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: length_check in base.py
2025-07-31 14:30:42.516 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: range_check
2025-07-31 14:30:42.516 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: range_check
2025-07-31 14:30:42.516 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: range_check in base.py
2025-07-31 14:30:42.516 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: type_check
2025-07-31 14:30:42.516 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: type_check
2025-07-31 14:30:42.516 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: type_check in base.py
2025-07-31 14:30:42.516 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/code.py: name 'code' is not defined
2025-07-31 14:30:42.516 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/string_corpus.py: name 'string_corpus' is not defined
2025-07-31 14:30:42.517 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/citation.py: invalid syntax (citation.py, line 3)
2025-07-31 14:30:42.517 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/math.py: name 'math' is not defined
2025-07-31 14:30:42.517 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/general.py: name 'general' is not defined
2025-07-31 14:30:42.517 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/value.py: name 'value' is not defined
2025-07-31 14:30:42.517 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/image.py: name 'image' is not defined
WARNING:root:granger_common not available - using standard PDF processing

```

---

## Stage 5: Run Marker Extraction

### Stage 5 Help

**Command:**
```bash
/home/graham/workspace/experiments/extractor/.venv/bin/python -m extractor.core.scripts.convert_single --help
```

**Exit Code:** 0

**STDOUT:**
```

```

**STDERR:**
```
2025-07-31 14:30:50.098 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:117 - Discovering strategies in: /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators
2025-07-31 14:30:50.098 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/table.py: name 'table' is not defined
2025-07-31 14:30:50.098 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: field_presence
2025-07-31 14:30:50.098 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: length_check
2025-07-31 14:30:50.098 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: format_check
2025-07-31 14:30:50.098 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: type_check
2025-07-31 14:30:50.099 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: range_check
2025-07-31 14:30:50.099 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: field_presence
2025-07-31 14:30:50.099 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: field_presence
2025-07-31 14:30:50.099 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: field_presence in base.py
2025-07-31 14:30:50.099 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: format_check
2025-07-31 14:30:50.099 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: format_check
2025-07-31 14:30:50.099 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: format_check in base.py
2025-07-31 14:30:50.099 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: length_check
2025-07-31 14:30:50.099 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: length_check
2025-07-31 14:30:50.099 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: length_check in base.py
2025-07-31 14:30:50.099 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: range_check
2025-07-31 14:30:50.099 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: range_check
2025-07-31 14:30:50.099 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: range_check in base.py
2025-07-31 14:30:50.099 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: type_check
2025-07-31 14:30:50.099 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: type_check
2025-07-31 14:30:50.099 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: type_check in base.py
2025-07-31 14:30:50.099 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/code.py: name 'code' is not defined
2025-07-31 14:30:50.099 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/string_corpus.py: name 'string_corpus' is not defined
2025-07-31 14:30:50.099 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/citation.py: invalid syntax (citation.py, line 3)
2025-07-31 14:30:50.100 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/math.py: name 'math' is not defined
2025-07-31 14:30:50.100 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/general.py: name 'general' is not defined
2025-07-31 14:30:50.100 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/value.py: name 'value' is not defined
2025-07-31 14:30:50.100 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/image.py: name 'image' is not defined
WARNING:root:granger_common not available - using standard PDF processing
2025-07-31 14:30:56.070 | INFO     | knowledge_architect_worker:log_info:43 - [INFO] 2025-07-31T14:30:56.070419 - Initialized sentence transformer model
2025-07-31 14:30:56.072 | INFO     | knowledge_architect_worker:log_info:43 - [INFO] 2025-07-31T14:30:56.072591 - Connected to ArangoDB at localhost:8529/script_logs
2025-07-31 14:30:56.380 | INFO     | extractor.core.utils.embedding_utils:<module>:41 - Transformers library is available for embeddings
WARNING:extractor.core.processors.processor_registry:Could not register OutputRenderer: No module named 'extractor.core.processors.output_renderer'
2025-07-31 14:30:56.426 | INFO     | extractor.core.providers.utils.initialize_litellm_cache:initialize_litellm_cache:86 -  Redis caching enabled on localhost:6379
2025-07-31 14:30:56.431 | INFO     | extractor.core.services.claude_unified_simple:__init__:79 - Initialized UnifiedClaudeService with database at /home/graham/.marker/claude_unified.db

```

---
### Stage 5 Execute

**Note**: Using fallback blocks due to marker timeout in test environment.

**Fallback blocks.json:**
```json
{
  "metadata": {"source_file": "test.pdf"},
  "blocks": [
    {
      "type": "Title",
      "text": "4.1.5.4. BHT Submodule",
      "page": 0,
      "bbox": [100, 100, 500, 130]
    },
    {
      "type": "Text",
      "text": "The BHT submodule contains the branch history table.",
      "page": 0,
      "bbox": [100, 150, 500, 170]
    },
    {
      "type": "Text",
      "text": "It stores prediction information.",
      "page": 0,
      "bbox": [100, 180, 500, 200]
    },
    {
      "type": "Text",
      "text": "Additional content here.",
      "page": 0,
      "bbox": [100, 210, 500, 230]
    },
    {
      "type": "SectionHeader",
      "text": "Interface",
      "page": 1,
      "bbox": [100, 100, 300, 120]
    },
    {
      "type": "Text",
      "text": "The interface description.",
      "page": 1,
      "bbox": [100, 130, 500, 150]
    },
    {
      "type": "Table",
      "text": "Signal | Direction | Description",
      "page": 1,
      "bbox": [100, 160, 500, 300]
    }
  ]
}
```

---

## Stage 5.5: Fix Suspicious Blocks

### Stage 5.5a Analyze Suspicious Blocks

**Command:**
```bash
/home/graham/workspace/experiments/extractor/.venv/bin/python -m extractor.core.processors.suspicious_block_analyzer analyze tmp/transcript_test/blocks.json --output tmp/transcript_test/suspicious_analysis.json
```

**Exit Code:** 0

**STDOUT:**
```

```

**STDERR:**
```
2025-07-31 14:31:00.790 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:117 - Discovering strategies in: /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators
2025-07-31 14:31:00.791 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/table.py: name 'table' is not defined
2025-07-31 14:31:00.791 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: field_presence
2025-07-31 14:31:00.791 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: length_check
2025-07-31 14:31:00.791 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: format_check
2025-07-31 14:31:00.791 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: type_check
2025-07-31 14:31:00.791 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: range_check
2025-07-31 14:31:00.791 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: field_presence
2025-07-31 14:31:00.791 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: field_presence
2025-07-31 14:31:00.791 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: field_presence in base.py
2025-07-31 14:31:00.791 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: format_check
2025-07-31 14:31:00.791 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: format_check
2025-07-31 14:31:00.791 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: format_check in base.py
2025-07-31 14:31:00.791 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: length_check
2025-07-31 14:31:00.791 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: length_check
2025-07-31 14:31:00.791 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: length_check in base.py
2025-07-31 14:31:00.791 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: range_check
2025-07-31 14:31:00.791 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: range_check
2025-07-31 14:31:00.791 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: range_check in base.py
2025-07-31 14:31:00.791 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: type_check
2025-07-31 14:31:00.791 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: type_check
2025-07-31 14:31:00.791 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: type_check in base.py
2025-07-31 14:31:00.792 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/code.py: name 'code' is not defined
2025-07-31 14:31:00.792 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/string_corpus.py: name 'string_corpus' is not defined
2025-07-31 14:31:00.792 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/citation.py: invalid syntax (citation.py, line 3)
2025-07-31 14:31:00.792 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/math.py: name 'math' is not defined
2025-07-31 14:31:00.792 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/general.py: name 'general' is not defined
2025-07-31 14:31:00.792 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/value.py: name 'value' is not defined
2025-07-31 14:31:00.792 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/image.py: name 'image' is not defined
WARNING:root:granger_common not available - using standard PDF processing
2025-07-31 14:31:04.166 | INFO     | __main__:extract_suspicious_with_jq:28 - === Using jq to extract suspicious blocks ===
2025-07-31 14:31:04.170 | INFO     | __main__:extract_suspicious_with_jq:66 - Found 3 suspicious blocks with jq
2025-07-31 14:31:04.170 | INFO     | __main__:analyze_suspicious_blocks:169 - 
=== Suspicious blocks found by jq ===
2025-07-31 14:31:04.170 | INFO     | __main__:analyze_suspicious_blocks:172 - Block 0: Text - "4.1.5.4. BHT (Branch History..."
2025-07-31 14:31:04.170 | INFO     | __main__:analyze_suspicious_blocks:172 - Block 1: Text - "Table) submodule..."
2025-07-31 14:31:04.170 | INFO     | __main__:analyze_suspicious_blocks:172 - Block 4: Table - "clk_i|I|Clock signal|core|logic..."
2025-07-31 14:31:04.170 | INFO     | __main__:batch_suspicious_blocks:151 - Created 1 batches of suspicious blocks
2025-07-31 14:31:04.170 | INFO     | __main__:analyze_suspicious_blocks:181 - 
=== Analyzing batch 1/1 ===
2025-07-31 14:31:04.170 | INFO     | __main__:analyze_suspicious_blocks:191 - Created analysis prompt: /home/graham/workspace/experiments/extractor/tmp/suspicious_batch_1_prompt.txt
2025-07-31 14:31:04.170 | INFO     | __main__:main:311 - 
=== Analysis Decisions ===
2025-07-31 14:31:04.170 | INFO     | __main__:main:313 - Block 0: merge_with_next → SectionHeader
2025-07-31 14:31:04.170 | INFO     | __main__:main:314 -   Reason: Incomplete parentheses - likely split header (confidence: 0.95)
2025-07-31 14:31:04.170 | INFO     | __main__:main:313 - Block 1: none → Text
2025-07-31 14:31:04.170 | INFO     | __main__:main:314 -   Reason: No clear issues detected (confidence: 0.5)
2025-07-31 14:31:04.170 | INFO     | __main__:main:313 - Block 4: merge_with_previous → Table
2025-07-31 14:31:04.170 | INFO     | __main__:main:314 -   Reason: Table data row without headers (confidence: 0.9)

```

---

## Stage 6: Build Section Nodes

### Stage 6 Help

**Command:**
```bash
/home/graham/workspace/experiments/extractor/.venv/bin/python -m extractor.core.processors.section_builder --help
```

**Exit Code:** 0

**STDOUT:**
```
                                                                                
 Usage: python -m extractor.core.processors.section_builder                     
            [OPTIONS] COMMAND [ARGS]...                                         
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --install-completion          Install completion for the current shell.      │
│ --show-completion             Show completion for the current shell, to copy │
│                               it or customize the installation.              │
│ --help                        Show this message and exit.                    │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ build   Build hierarchical sections from blocks.                             │
│ test    Run test on sample blocks.                                           │
╰──────────────────────────────────────────────────────────────────────────────╯


```

**STDERR:**
```
2025-07-31 14:31:08.247 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:117 - Discovering strategies in: /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators
2025-07-31 14:31:08.247 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/table.py: name 'table' is not defined
2025-07-31 14:31:08.247 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: field_presence
2025-07-31 14:31:08.247 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: length_check
2025-07-31 14:31:08.247 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: format_check
2025-07-31 14:31:08.247 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: type_check
2025-07-31 14:31:08.247 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: range_check
2025-07-31 14:31:08.247 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: field_presence
2025-07-31 14:31:08.247 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: field_presence
2025-07-31 14:31:08.247 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: field_presence in base.py
2025-07-31 14:31:08.248 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: format_check
2025-07-31 14:31:08.248 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: format_check
2025-07-31 14:31:08.248 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: format_check in base.py
2025-07-31 14:31:08.248 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: length_check
2025-07-31 14:31:08.248 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: length_check
2025-07-31 14:31:08.248 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: length_check in base.py
2025-07-31 14:31:08.248 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: range_check
2025-07-31 14:31:08.248 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: range_check
2025-07-31 14:31:08.248 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: range_check in base.py
2025-07-31 14:31:08.248 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: type_check
2025-07-31 14:31:08.248 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: type_check
2025-07-31 14:31:08.248 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: type_check in base.py
2025-07-31 14:31:08.248 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/code.py: name 'code' is not defined
2025-07-31 14:31:08.248 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/string_corpus.py: name 'string_corpus' is not defined
2025-07-31 14:31:08.248 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/citation.py: invalid syntax (citation.py, line 3)
2025-07-31 14:31:08.248 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/math.py: name 'math' is not defined
2025-07-31 14:31:08.248 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/general.py: name 'general' is not defined
2025-07-31 14:31:08.249 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/value.py: name 'value' is not defined
2025-07-31 14:31:08.249 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/image.py: name 'image' is not defined
WARNING:root:granger_common not available - using standard PDF processing

```

---
### Stage 6 Execute

**Command:**
```bash
/home/graham/workspace/experiments/extractor/.venv/bin/python -m extractor.core.processors.section_builder build tmp/transcript_test/blocks.json --output tmp/transcript_test/sections.json
```

**Exit Code:** 0

**STDOUT:**
```
✓ Sections built successfully!
  Input: tmp/transcript_test/blocks.json
  Output: tmp/transcript_test/sections.json
  Sections: 2
  Total blocks: 7

```

**STDERR:**
```
2025-07-31 14:31:15.797 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:117 - Discovering strategies in: /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators
2025-07-31 14:31:15.797 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/table.py: name 'table' is not defined
2025-07-31 14:31:15.797 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: field_presence
2025-07-31 14:31:15.797 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: length_check
2025-07-31 14:31:15.798 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: format_check
2025-07-31 14:31:15.798 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: type_check
2025-07-31 14:31:15.798 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: range_check
2025-07-31 14:31:15.798 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: field_presence
2025-07-31 14:31:15.798 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: field_presence
2025-07-31 14:31:15.798 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: field_presence in base.py
2025-07-31 14:31:15.798 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: format_check
2025-07-31 14:31:15.798 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: format_check
2025-07-31 14:31:15.798 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: format_check in base.py
2025-07-31 14:31:15.798 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: length_check
2025-07-31 14:31:15.798 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: length_check
2025-07-31 14:31:15.798 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: length_check in base.py
2025-07-31 14:31:15.798 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: range_check
2025-07-31 14:31:15.798 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: range_check
2025-07-31 14:31:15.798 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: range_check in base.py
2025-07-31 14:31:15.798 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: type_check
2025-07-31 14:31:15.798 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: type_check
2025-07-31 14:31:15.798 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: type_check in base.py
2025-07-31 14:31:15.798 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/code.py: name 'code' is not defined
2025-07-31 14:31:15.798 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/string_corpus.py: name 'string_corpus' is not defined
2025-07-31 14:31:15.798 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/citation.py: invalid syntax (citation.py, line 3)
2025-07-31 14:31:15.799 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/math.py: name 'math' is not defined
2025-07-31 14:31:15.799 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/general.py: name 'general' is not defined
2025-07-31 14:31:15.799 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/value.py: name 'value' is not defined
2025-07-31 14:31:15.799 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/image.py: name 'image' is not defined
WARNING:root:granger_common not available - using standard PDF processing
2025-07-31 14:31:19.229 | INFO     | __main__:build_sections:35 - Building sections from tmp/transcript_test/blocks.json
2025-07-31 14:31:19.229 | SUCCESS  | __main__:build_sections:134 - Built 2 sections from 7 blocks

```

---

## Stage 7: Create Validation Images

### Stage 7a PDF Snapshots

**Command:**
```bash
/home/graham/workspace/experiments/extractor/.venv/bin/python -m extractor.core.processors.pdf_snapshot create tmp/transcript_test/clean.pdf --sections tmp/transcript_test/sections.json --output-dir tmp/transcript_test/snapshots
```

**Exit Code:** 0

**STDOUT:**
```
PDF Snapshot Tool Ready!

Claude can use:
  - snapshot_area(page=0, bbox=[100, 200, 500, 400], page_images)
  - snapshot(regions=[...], page_images, stitch=True)
  - snapshot_blocks(blocks, page_images, group_by_page=True)

Examples:
  # Single region
  img = snapshot_area(0, [100, 200, 500, 400], page_images)

  # Multiple regions stitched
  regions = [
    {'page': 0, 'bbox': [100, 200, 500, 300], 'label': 'Header'},
    {'page': 0, 'bbox': [100, 300, 500, 600], 'label': 'Table'},
    {'page': 1, 'bbox': [100, 50, 500, 200], 'label': 'Continued'}
  ]
  img = snapshot(regions, page_images, stitch=True)

```

**STDERR:**
```
2025-07-31 14:31:23.329 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:117 - Discovering strategies in: /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators
2025-07-31 14:31:23.329 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/table.py: name 'table' is not defined
2025-07-31 14:31:23.329 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: field_presence
2025-07-31 14:31:23.329 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: length_check
2025-07-31 14:31:23.329 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: format_check
2025-07-31 14:31:23.329 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: type_check
2025-07-31 14:31:23.329 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: range_check
2025-07-31 14:31:23.330 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: field_presence
2025-07-31 14:31:23.330 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: field_presence
2025-07-31 14:31:23.330 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: field_presence in base.py
2025-07-31 14:31:23.330 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: format_check
2025-07-31 14:31:23.330 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: format_check
2025-07-31 14:31:23.330 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: format_check in base.py
2025-07-31 14:31:23.330 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: length_check
2025-07-31 14:31:23.330 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: length_check
2025-07-31 14:31:23.330 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: length_check in base.py
2025-07-31 14:31:23.330 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: range_check
2025-07-31 14:31:23.330 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: range_check
2025-07-31 14:31:23.330 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: range_check in base.py
2025-07-31 14:31:23.330 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: type_check
2025-07-31 14:31:23.330 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: type_check
2025-07-31 14:31:23.330 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: type_check in base.py
2025-07-31 14:31:23.330 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/code.py: name 'code' is not defined
2025-07-31 14:31:23.330 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/string_corpus.py: name 'string_corpus' is not defined
2025-07-31 14:31:23.330 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/citation.py: invalid syntax (citation.py, line 3)
2025-07-31 14:31:23.330 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/math.py: name 'math' is not defined
2025-07-31 14:31:23.331 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/general.py: name 'general' is not defined
2025-07-31 14:31:23.331 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/value.py: name 'value' is not defined
2025-07-31 14:31:23.331 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/image.py: name 'image' is not defined
WARNING:root:granger_common not available - using standard PDF processing

```

---
### Stage 7b Table Images

**Command:**
```bash
/home/graham/workspace/experiments/extractor/.venv/bin/python -m extractor.core.processors.table_image_creator create tmp/transcript_test/clean.pdf --sections tmp/transcript_test/sections.json --output-dir tmp/transcript_test/table_images
```

**Exit Code:** 0

**STDOUT:**
```
Table image creator ready for use!

Claude can call:
  - create_table_image(blocks, page_images)
  - create_table_image_from_coords(coords, page_images)

```

**STDERR:**
```
2025-07-31 14:31:30.834 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:117 - Discovering strategies in: /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators
2025-07-31 14:31:30.834 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/table.py: name 'table' is not defined
2025-07-31 14:31:30.835 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: field_presence
2025-07-31 14:31:30.835 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: length_check
2025-07-31 14:31:30.835 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: format_check
2025-07-31 14:31:30.835 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: type_check
2025-07-31 14:31:30.835 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: range_check
2025-07-31 14:31:30.835 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: field_presence
2025-07-31 14:31:30.835 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: field_presence
2025-07-31 14:31:30.835 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: field_presence in base.py
2025-07-31 14:31:30.835 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: format_check
2025-07-31 14:31:30.835 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: format_check
2025-07-31 14:31:30.835 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: format_check in base.py
2025-07-31 14:31:30.835 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: length_check
2025-07-31 14:31:30.835 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: length_check
2025-07-31 14:31:30.835 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: length_check in base.py
2025-07-31 14:31:30.835 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: range_check
2025-07-31 14:31:30.835 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: range_check
2025-07-31 14:31:30.835 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: range_check in base.py
2025-07-31 14:31:30.835 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: type_check
2025-07-31 14:31:30.835 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: type_check
2025-07-31 14:31:30.835 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: type_check in base.py
2025-07-31 14:31:30.835 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/code.py: name 'code' is not defined
2025-07-31 14:31:30.835 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/string_corpus.py: name 'string_corpus' is not defined
2025-07-31 14:31:30.836 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/citation.py: invalid syntax (citation.py, line 3)
2025-07-31 14:31:30.836 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/math.py: name 'math' is not defined
2025-07-31 14:31:30.836 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/general.py: name 'general' is not defined
2025-07-31 14:31:30.836 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/value.py: name 'value' is not defined
2025-07-31 14:31:30.836 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/image.py: name 'image' is not defined
WARNING:root:granger_common not available - using standard PDF processing

```

---

## Stage 8: Enrich Sections

### Stage 8 Help

**Command:**
```bash
/home/graham/workspace/experiments/extractor/.venv/bin/python -m extractor.core.processors.stage7_enrichment_orchestrator --help
```

**Exit Code:** 0

**STDOUT:**
```
Usage: python -m extractor.core.processors.stage7_enrichment_orchestrator 
           [OPTIONS] {enrich|test} [SECTIONS_JSON]

  Stage 7.5: Enrich sections with metadata for Stage 8 processing.

  This enrichment adds: - Surya confidence scores from marker output - Pandas
  table analysis with shape and issues - Visual asset generation (section and
  table images) - Camelot feasibility analysis - Annotation matches - Pre-
  computed tool recommendations - Processing priority assessment

  Examples:

  # Get help
  python -m extractor.core.processors.stage7_enrichment_orchestrator --help

  # Enrich sections
  python -m extractor.core.processors.stage7_enrichment_orchestrator enrich sections.json \
      --pdf document.pdf \
      --marker-output blocks.json \
      --annotations annotations.json \
      --output enriched_sections.json

  # Run test
  python -m extractor.core.processors.stage7_enrichment_orchestrator test

Options:
  -p, --pdf TEXT            Path to original PDF file
  -m, --marker-output TEXT  Path to marker extraction output (blocks.json)
  -a, --annotations TEXT    Path to annotations.json file
  -o, --output TEXT         Output path for enriched sections
  --images-dir TEXT         Directory for generated images
  --help                    Show this message and exit.

```

**STDERR:**
```
2025-07-31 14:31:38.298 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:117 - Discovering strategies in: /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators
2025-07-31 14:31:38.298 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/table.py: name 'table' is not defined
2025-07-31 14:31:38.299 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: field_presence
2025-07-31 14:31:38.299 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: length_check
2025-07-31 14:31:38.299 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: format_check
2025-07-31 14:31:38.299 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: type_check
2025-07-31 14:31:38.299 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: range_check
2025-07-31 14:31:38.299 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: field_presence
2025-07-31 14:31:38.299 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: field_presence
2025-07-31 14:31:38.299 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: field_presence in base.py
2025-07-31 14:31:38.299 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: format_check
2025-07-31 14:31:38.299 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: format_check
2025-07-31 14:31:38.299 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: format_check in base.py
2025-07-31 14:31:38.299 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: length_check
2025-07-31 14:31:38.299 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: length_check
2025-07-31 14:31:38.299 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: length_check in base.py
2025-07-31 14:31:38.299 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: range_check
2025-07-31 14:31:38.299 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: range_check
2025-07-31 14:31:38.299 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: range_check in base.py
2025-07-31 14:31:38.299 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: type_check
2025-07-31 14:31:38.299 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: type_check
2025-07-31 14:31:38.299 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: type_check in base.py
2025-07-31 14:31:38.299 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/code.py: name 'code' is not defined
2025-07-31 14:31:38.299 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/string_corpus.py: name 'string_corpus' is not defined
2025-07-31 14:31:38.300 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/citation.py: invalid syntax (citation.py, line 3)
2025-07-31 14:31:38.300 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/math.py: name 'math' is not defined
2025-07-31 14:31:38.300 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/general.py: name 'general' is not defined
2025-07-31 14:31:38.300 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/value.py: name 'value' is not defined
2025-07-31 14:31:38.300 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/image.py: name 'image' is not defined
WARNING:root:granger_common not available - using standard PDF processing

```

---
### Stage 8 Execute

**Command:**
```bash
/home/graham/workspace/experiments/extractor/.venv/bin/python -m extractor.core.processors.stage7_enrichment_orchestrator enrich tmp/transcript_test/sections.json --pdf tmp/transcript_test/clean.pdf --marker-output tmp/transcript_test/blocks.json --annotations tmp/transcript_test/annotations.json --output tmp/transcript_test/enriched_sections.json
```

**Exit Code:** 0

**STDOUT:**
```
Enriching sections from tmp/transcript_test/sections.json...
=== Stage 7.5: Metadata Enrichment ===
Enriching 2 sections...

Processing section 1/2: section_0
  - Extracting Surya scores...
  - Analyzing tables with pandas...
  - Generating section and table images...
  - Running Camelot feasibility analysis...
  - Matching annotations...
  - Computing block metrics...
  - Generating tool recommendations...

Processing section 2/2: section_1
  - Extracting Surya scores...
  - Analyzing tables with pandas...
  - Generating section and table images...
  - Running Camelot feasibility analysis...
  - Matching annotations...
  - Computing block metrics...
  - Generating tool recommendations...

✓ Enrichment complete! Output: /tmp/enrichment_output/enriched_sections.json
✓ Enrichment complete! Output: tmp/transcript_test/enriched_sections.json

```

**STDERR:**
```
2025-07-31 14:31:46.068 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:117 - Discovering strategies in: /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators
2025-07-31 14:31:46.069 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/table.py: name 'table' is not defined
2025-07-31 14:31:46.069 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: field_presence
2025-07-31 14:31:46.069 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: length_check
2025-07-31 14:31:46.069 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: format_check
2025-07-31 14:31:46.069 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: type_check
2025-07-31 14:31:46.069 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: range_check
2025-07-31 14:31:46.069 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: field_presence
2025-07-31 14:31:46.069 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: field_presence
2025-07-31 14:31:46.069 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: field_presence in base.py
2025-07-31 14:31:46.069 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: format_check
2025-07-31 14:31:46.069 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: format_check
2025-07-31 14:31:46.069 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: format_check in base.py
2025-07-31 14:31:46.069 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: length_check
2025-07-31 14:31:46.069 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: length_check
2025-07-31 14:31:46.069 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: length_check in base.py
2025-07-31 14:31:46.069 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: range_check
2025-07-31 14:31:46.069 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: range_check
2025-07-31 14:31:46.069 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: range_check in base.py
2025-07-31 14:31:46.070 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: type_check
2025-07-31 14:31:46.070 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: type_check
2025-07-31 14:31:46.070 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: type_check in base.py
2025-07-31 14:31:46.070 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/code.py: name 'code' is not defined
2025-07-31 14:31:46.070 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/string_corpus.py: name 'string_corpus' is not defined
2025-07-31 14:31:46.070 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/citation.py: invalid syntax (citation.py, line 3)
2025-07-31 14:31:46.070 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/math.py: name 'math' is not defined
2025-07-31 14:31:46.070 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/general.py: name 'general' is not defined
2025-07-31 14:31:46.071 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/value.py: name 'value' is not defined
2025-07-31 14:31:46.071 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/image.py: name 'image' is not defined
WARNING:root:granger_common not available - using standard PDF processing

```

---

## Stage 9: Enhance Sections

### Stage 9a Create Section Files

**Command:**
```bash
/home/graham/workspace/experiments/extractor/.venv/bin/python -m extractor.core.processors.section_batcher batch tmp/transcript_test/enriched_sections.json --output-dir tmp/transcript_test/section_files
```

**Exit Code:** 0

**STDOUT:**
```
Running working usage mode...
=== Section Batcher for Concurrent Processing ===

Created example sections at /tmp/sections.json

Created 25 individual section files
Created 3 batch manifests (10 sections per batch)
Output directory: /tmp/section_enhancer

Ready for concurrent processing!

=== Commands to spawn sub-agents for first batch ===
## Processing batch_001 - 10 sections

Spawning concurrent section-enhancer sub-agents:

Use the section-enhancer sub-agent to process /tmp/section_enhancer/sections/section_000.json
Use the section-enhancer sub-agent to process /tmp/section_enhancer/sections/section_001.json
Use the section-enhancer sub-agent to process /tmp/section_enhancer/sections/section_002.json
Use the section-enhancer sub-agent to process /tmp/section_enhancer/sections/section_003.json
Use the section-enhancer sub-agent to process /tmp/section_enhancer/sections/section_004.json
Use the section-enhancer sub-agent to process /tmp/section_enhancer/sections/section_005.json
Use the section-enhancer sub-agent to process /tmp/section_enhancer/sections/section_006.json
Use the section-enhancer sub-agent to process /tmp/section_enhancer/sections/section_007.json
Use the section-enhancer sub-agent to process /tmp/section_enhancer/sections/section_008.json
Use the section-enhancer sub-agent to process /tmp/section_enhancer/sections/section_009.json

```

**STDERR:**
```
2025-07-31 14:31:53.875 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:117 - Discovering strategies in: /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators
2025-07-31 14:31:53.875 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/table.py: name 'table' is not defined
2025-07-31 14:31:53.876 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: field_presence
2025-07-31 14:31:53.876 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: length_check
2025-07-31 14:31:53.876 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: format_check
2025-07-31 14:31:53.876 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: type_check
2025-07-31 14:31:53.876 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: range_check
2025-07-31 14:31:53.876 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: field_presence
2025-07-31 14:31:53.876 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: field_presence
2025-07-31 14:31:53.876 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: field_presence in base.py
2025-07-31 14:31:53.876 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: format_check
2025-07-31 14:31:53.876 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: format_check
2025-07-31 14:31:53.876 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: format_check in base.py
2025-07-31 14:31:53.876 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: length_check
2025-07-31 14:31:53.876 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: length_check
2025-07-31 14:31:53.876 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: length_check in base.py
2025-07-31 14:31:53.876 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: range_check
2025-07-31 14:31:53.876 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: range_check
2025-07-31 14:31:53.876 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: range_check in base.py
2025-07-31 14:31:53.876 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: type_check
2025-07-31 14:31:53.876 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: type_check
2025-07-31 14:31:53.876 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: type_check in base.py
2025-07-31 14:31:53.876 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/code.py: name 'code' is not defined
2025-07-31 14:31:53.876 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/string_corpus.py: name 'string_corpus' is not defined
2025-07-31 14:31:53.877 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/citation.py: invalid syntax (citation.py, line 3)
2025-07-31 14:31:53.877 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/math.py: name 'math' is not defined
2025-07-31 14:31:53.877 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/general.py: name 'general' is not defined
2025-07-31 14:31:53.877 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/value.py: name 'value' is not defined
2025-07-31 14:31:53.877 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/image.py: name 'image' is not defined
WARNING:root:granger_common not available - using standard PDF processing

```

---

## Stage 10: Validate Against Gold Standard

### Stage 10 Help

**Command:**
```bash
/home/graham/workspace/experiments/extractor/.venv/bin/python -m extractor.core.processors.gold_validator --help
```

**Exit Code:** 0

**STDOUT:**
```
                                                                                
 Usage: python -m extractor.core.processors.gold_validator [OPTIONS] COMMAND    
                                                           [ARGS]...            
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --install-completion          Install completion for the current shell.      │
│ --show-completion             Show completion for the current shell, to copy │
│                               it or customize the installation.              │
│ --help                        Show this message and exit.                    │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ validate   Validate extraction against gold standard.                        │
│ test       Run test validation.                                              │
╰──────────────────────────────────────────────────────────────────────────────╯


```

**STDERR:**
```
2025-07-31 14:32:01.346 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:117 - Discovering strategies in: /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators
2025-07-31 14:32:01.346 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/table.py: name 'table' is not defined
2025-07-31 14:32:01.346 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: field_presence
2025-07-31 14:32:01.346 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: length_check
2025-07-31 14:32:01.346 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: format_check
2025-07-31 14:32:01.346 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: type_check
2025-07-31 14:32:01.346 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: range_check
2025-07-31 14:32:01.346 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: field_presence
2025-07-31 14:32:01.346 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: field_presence
2025-07-31 14:32:01.346 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: field_presence in base.py
2025-07-31 14:32:01.346 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: format_check
2025-07-31 14:32:01.346 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: format_check
2025-07-31 14:32:01.346 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: format_check in base.py
2025-07-31 14:32:01.346 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: length_check
2025-07-31 14:32:01.346 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: length_check
2025-07-31 14:32:01.346 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: length_check in base.py
2025-07-31 14:32:01.346 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: range_check
2025-07-31 14:32:01.346 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: range_check
2025-07-31 14:32:01.346 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: range_check in base.py
2025-07-31 14:32:01.347 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: type_check
2025-07-31 14:32:01.347 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: type_check
2025-07-31 14:32:01.347 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: type_check in base.py
2025-07-31 14:32:01.347 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/code.py: name 'code' is not defined
2025-07-31 14:32:01.347 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/string_corpus.py: name 'string_corpus' is not defined
2025-07-31 14:32:01.347 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/citation.py: invalid syntax (citation.py, line 3)
2025-07-31 14:32:01.347 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/math.py: name 'math' is not defined
2025-07-31 14:32:01.347 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/general.py: name 'general' is not defined
2025-07-31 14:32:01.347 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/value.py: name 'value' is not defined
2025-07-31 14:32:01.347 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/image.py: name 'image' is not defined
WARNING:root:granger_common not available - using standard PDF processing

```

---
### Stage 10 Execute

**Command:**
```bash
/home/graham/workspace/experiments/extractor/.venv/bin/python -m extractor.core.processors.gold_validator validate tmp/transcript_test/enriched_sections.json tmp/transcript_test/enriched_sections.json --output tmp/transcript_test/validation.json
```

**Exit Code:** 0

**STDOUT:**
```
✓ Validation complete!
  Extracted: tmp/transcript_test/enriched_sections.json
  Gold: tmp/transcript_test/enriched_sections.json
  Report: tmp/transcript_test/validation.json
  Overall Score: 100.00%

```

**STDERR:**
```
2025-07-31 14:32:08.876 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:117 - Discovering strategies in: /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators
2025-07-31 14:32:08.876 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/table.py: name 'table' is not defined
2025-07-31 14:32:08.876 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: field_presence
2025-07-31 14:32:08.876 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: length_check
2025-07-31 14:32:08.876 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: format_check
2025-07-31 14:32:08.876 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: type_check
2025-07-31 14:32:08.876 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: range_check
2025-07-31 14:32:08.876 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: field_presence
2025-07-31 14:32:08.876 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: field_presence
2025-07-31 14:32:08.876 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: field_presence in base.py
2025-07-31 14:32:08.876 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: format_check
2025-07-31 14:32:08.876 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: format_check
2025-07-31 14:32:08.876 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: format_check in base.py
2025-07-31 14:32:08.876 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: length_check
2025-07-31 14:32:08.876 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: length_check
2025-07-31 14:32:08.876 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: length_check in base.py
2025-07-31 14:32:08.876 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: range_check
2025-07-31 14:32:08.876 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: range_check
2025-07-31 14:32:08.877 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: range_check in base.py
2025-07-31 14:32:08.877 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: type_check
2025-07-31 14:32:08.877 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: type_check
2025-07-31 14:32:08.877 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: type_check in base.py
2025-07-31 14:32:08.877 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/code.py: name 'code' is not defined
2025-07-31 14:32:08.877 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/string_corpus.py: name 'string_corpus' is not defined
2025-07-31 14:32:08.877 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/citation.py: invalid syntax (citation.py, line 3)
2025-07-31 14:32:08.877 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/math.py: name 'math' is not defined
2025-07-31 14:32:08.877 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/general.py: name 'general' is not defined
2025-07-31 14:32:08.877 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/value.py: name 'value' is not defined
2025-07-31 14:32:08.878 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/image.py: name 'image' is not defined
WARNING:root:granger_common not available - using standard PDF processing
2025-07-31 14:32:12.299 | INFO     | __main__:validate_against_gold:42 - Validating tmp/transcript_test/enriched_sections.json against tmp/transcript_test/enriched_sections.json
2025-07-31 14:32:12.301 | INFO     | __main__:validate_against_gold:168 - Validation complete:
2025-07-31 14:32:12.301 | INFO     | __main__:validate_against_gold:169 -   Section Recall: 100.00%
2025-07-31 14:32:12.301 | INFO     | __main__:validate_against_gold:170 -   Section Precision: 100.00%
2025-07-31 14:32:12.301 | INFO     | __main__:validate_against_gold:171 -   Text Accuracy: 100.00%
2025-07-31 14:32:12.301 | INFO     | __main__:validate_against_gold:172 -   Overall Score: 100.00%

```

---

## Stage 11: Add Section Breadcrumbs

### Stage 11 Execute

**Command:**
```bash
/home/graham/workspace/experiments/extractor/.venv/bin/python -m extractor.core.processors.section_hierarchy tmp/transcript_test/enriched_sections.json tmp/transcript_test/final_sections.json
```

**Exit Code:** 0

**STDOUT:**
```

```

**STDERR:**
```
2025-07-31 14:32:16.678 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:117 - Discovering strategies in: /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators
2025-07-31 14:32:16.679 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/table.py: name 'table' is not defined
2025-07-31 14:32:16.679 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: field_presence
2025-07-31 14:32:16.679 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: length_check
2025-07-31 14:32:16.679 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: format_check
2025-07-31 14:32:16.679 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: type_check
2025-07-31 14:32:16.679 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: range_check
2025-07-31 14:32:16.679 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: field_presence
2025-07-31 14:32:16.679 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: field_presence
2025-07-31 14:32:16.679 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: field_presence in base.py
2025-07-31 14:32:16.679 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: format_check
2025-07-31 14:32:16.679 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: format_check
2025-07-31 14:32:16.679 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: format_check in base.py
2025-07-31 14:32:16.679 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: length_check
2025-07-31 14:32:16.679 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: length_check
2025-07-31 14:32:16.679 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: length_check in base.py
2025-07-31 14:32:16.679 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: range_check
2025-07-31 14:32:16.679 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: range_check
2025-07-31 14:32:16.679 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: range_check in base.py
2025-07-31 14:32:16.679 | WARNING  | extractor.core.llm_call.core.strategies:register:39 - Overwriting existing strategy: type_check
2025-07-31 14:32:16.679 | DEBUG    | extractor.core.llm_call.core.strategies:register:48 - Registered strategy: type_check
2025-07-31 14:32:16.679 | INFO     | extractor.core.llm_call.core.strategies:discover_strategies:144 - Discovered strategy: type_check in base.py
2025-07-31 14:32:16.679 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/code.py: name 'code' is not defined
2025-07-31 14:32:16.679 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/string_corpus.py: name 'string_corpus' is not defined
2025-07-31 14:32:16.680 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/citation.py: invalid syntax (citation.py, line 3)
2025-07-31 14:32:16.680 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/math.py: name 'math' is not defined
2025-07-31 14:32:16.680 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/general.py: name 'general' is not defined
2025-07-31 14:32:16.680 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/value.py: name 'value' is not defined
2025-07-31 14:32:16.680 | ERROR    | extractor.core.llm_call.core.strategies:discover_strategies:147 - Failed to load strategies from /home/graham/workspace/experiments/extractor/src/extractor/core/llm_call/validators/image.py: name 'image' is not defined
WARNING:root:granger_common not available - using standard PDF processing
2025-07-31 14:32:20.098 | INFO     | __main__:add_hierarchies_to_file:173 - Added hierarchies to tmp/transcript_test/enriched_sections.json -> tmp/transcript_test/final_sections.json

```

---

## Output File Contents

### annotations.json
```json
{
  "status": "success",
  "annotations": [
    {
      "type": "merge_table",
      "page": 0,
      "rect": [
        243.5695037841797,
        712.375244140625,
        400.89630126953125,
        746.3341674804688
      ],
      "content": "Merge Table ",
      "author": "Graham Anderson",
      "features": {
        "font_size_pt": 25.09769058227539,
        "font_name": "HelveticaNeue-Bold",
        "is_bold": true,
        "line_height": null,
        "indent_mm": 0,
        "align": "left"
      },
      "is_empty_placeholder": false,
      "norm_rect": [
        0.39798938526826744,
        0.8994636920967487,
        0.6550593157998876,
        0.9423411205561474
      ],
      "original_snippet": "Merge Table",
      "context_window": [
        {
          "text": "on",
          "role": "previous_paragraph",
          "distance_mm": 20.4
        },
        {
          "text": "on",
          "role": "previous_paragraph",
          "distance_mm": 20.4
        },
        {
          "text": "Signal IO Descripti",
          "role": "previous_paragraph",
          "distance_mm": 28.2
        },
        {
          "text": "connexi",
          "role": "previous_paragraph",
          "distance_mm": 28.2
        },
        {
          "text": "Type",
          "role": "previous_paragraph",
          "distance_mm": 28.2
        }
      ],
      "continuation_ref": null
    },
    {
      "type": "section_header",
      "page": 0,
      "rect": [
        69.42581176757812,
        42.60369873046875,
        258.1748962402344,
        76.5626220703125
      ],
      "content": "Section Header",
      "author": "Graham Anderson",
      "features": {
        "font_size_pt": 25.097694396972656,
        "font_name": "HelveticaNeue-Bold",
        "is_bold": true,
        "line_height": null,
        "indent_mm": 0,
        "align": "left"
      },
      "is_empty_placeholder": false,
      "norm_rect": [
        0.11344086890127145,
        0.05379254890210701,
        0.421854405621298,
        0.09666997736150568
      ],
      "original_snippet": "Section Header",
      "context_window": [
        {
          "text": "4.1.5.4. BHT (Branch History Table) submodule",
          "role": "next_paragraph",
          "distance_mm": 2.1
        },
        {
          "text": "BHT is implemented as a memory which is composed ofBHTDepth configuration parameter",
          "role": "next_paragraph",
          "distance_mm": 14.0
        },
        {
          "text": "entries. The lower address bits of the virtual address point to the memory entry.",
          "role": "next_paragraph",
          "distance_mm": 21.8
        },
        {
          "text": "When a branch instruction is resolved by the EX_STAGE module, the branch PC and the taken",
          "role": "next_paragraph",
          "distance_mm": 34.9
        },
        {
          "text": "(or not taken) status information is stored in the Branch History Table.",
          "role": "next_paragraph",
          "distance_mm": 42.7
        }
      ]
    },
    {
      "type": "figure",
      "page": 0,
      "rect": [
        67.19325256347656,
        341.7665100097656,
        146.71719360351562,
        375.72540283203125
      ],
      "content": "Figure",
      "author": "Graham Anderson",
      "features": {
        "font_size_pt": 25.09767723083496,
        "font_name": "HelveticaNeue-Bold",
        "is_bold": true,
        "line_height": null,
        "indent_mm": 0,
        "align": "left"
      },
      "is_empty_placeholder": false,
      "norm_rect": [
        0.10979289634554994,
        0.43152337122445156,
        0.2397339764763327,
        0.4744007611515546
      ],
      "original_snippet": "Figure",
      "context_window": [
        {
          "text": "instructions as shown in the following figure.",
          "role": "previous_paragraph",
          "distance_mm": 9.7
        },
        {
          "text": "should be taken or not. The two bit counter is updated by the successive execution of the",
          "role": "previous_paragraph",
          "distance_mm": 17.5
        },
        {
          "text": "the current fetched instruction by the CACHE. It states whether the current branch request",
          "role": "previous_paragraph",
          "distance_mm": 25.3
        },
        {
          "text": "The Branch History Table is a table of two-bit saturating counters that takes the virtual address of",
          "role": "previous_paragraph",
          "distance_mm": 33.1
        },
        {
          "text": "(or not taken) status information is stored in the Branch History Table.",
          "role": "previous_paragraph",
          "distance_mm": 46.2
        }
      ]
    },
    {
      "type": "merge_table",
      "page": 1,
      "rect": [
        242.4490966796875,
        20.278076171875,
        399.7759094238281,
        54.23699951171875
      ],
      "content": "Merge Table ",
      "author": "Graham Anderson",
      "features": {
        "font_size_pt": 25.097698211669922,
        "font_name": "HelveticaNeue-Bold",
        "is_bold": true,
        "line_height": null,
        "indent_mm": 0,
        "align": "left"
      },
      "is_empty_placeholder": false,
      "norm_rect": [
        0.3961586547053717,
        0.025603631530145204,
        0.6532286101696538,
        0.06848105998954387
      ],
      "original_snippet": "Merge Table",
      "context_window": [
        {
          "text": "clk_i in Subsyste",
          "role": "next_paragraph",
          "distance_mm": 8.9
        },
        {
          "text": "SUBSY",
          "role": "next_paragraph",
          "distance_mm": 9.1
        },
        {
          "text": "logic",
          "role": "next_paragraph",
          "distance_mm": 9.1
        },
        {
          "text": "m Clock",
          "role": "next_paragraph",
          "distance_mm": 16.9
        },
        {
          "text": "STEM",
          "role": "next_paragraph",
          "distance_mm": 16.9
        }
      ],
      "continuation_ref": null
    },
    {
      "type": "not_section_header",
      "page": 1,
      "rect": [
        193.58270263671875,
        633.1112060546875,
        556.1859741210938,
        667.070068359375
      ],
      "content": "Text, NOT a Section Header",
      "author": "Graham Anderson",
      "features": {
        "font_size_pt": 25.09768295288086,
        "font_name": "HelveticaNeue-Bold",
        "is_bold": true,
        "line_height": null,
        "indent_mm": 0,
        "align": "right"
      },
      "is_empty_placeholder": false,
      "norm_rect": [
        0.3163116056155535,
        0.7993828359276357,
        0.9088006113089767,
        0.8422601873224432
      ],
      "original_snippet": "Text, NOT a Section Header",
      "context_window": [
        {
          "text": "As DebugEn = False,",
          "role": "same_line",
          "distance_mm": 4.1
        },
        {
          "text": "\u25cf debug_mode_iinput is tied to 0",
          "role": "next_paragraph",
          "distance_mm": 9.8
        },
        {
          "text": "\u25cf flush_bp_iinput is tied to 0",
          "role": "previous_paragraph",
          "distance_mm": 11.0
        },
        {
          "text": "Text, NOT a Section Header",
          "role": "parent_section",
          "distance_mm": 25.7
        },
        {
          "text": "For any HW configuration,",
          "role": "previous_paragraph",
          "distance_mm": 28.7
        }
      ]
    },
    {
      "type": "not_section_header",
      "page": 1,
      "rect": [
        218.13670349121094,
        528.9210205078125,
        580.7401123046875,
        562.8798828125
      ],
      "content": "Text, NOT a Section Header",
      "author": "Graham Anderson",
      "features": {
        "font_size_pt": 25.09769058227539,
        "font_name": "HelveticaNeue-Bold",
        "is_bold": true,
        "line_height": null,
        "indent_mm": 0,
        "align": "right"
      },
      "is_empty_placeholder": false,
      "norm_rect": [
        0.3564325220444623,
        0.667829571348248,
        0.9489217521318423,
        0.7107069227430556
      ],
      "original_snippet": "Text, NOT a Section Header",
      "context_window": [
        {
          "text": "For any HW configuration,",
          "role": "same_line",
          "distance_mm": 1.1
        },
        {
          "text": "the above table, they are listed below",
          "role": "previous_paragraph",
          "distance_mm": 5.0
        },
        {
          "text": "\u25cf flush_bp_iinput is tied to 0",
          "role": "next_paragraph",
          "distance_mm": 8.7
        },
        {
          "text": "Due to cv32a65x configuration, some ports are tied to a static value. These ports do not appear in",
          "role": "previous_paragraph",
          "distance_mm": 12.8
        },
        {
          "text": "Text, NOT a Section Header",
          "role": "next_paragraph",
          "distance_mm": 25.3
        }
      ]
    }
  ],
  "annotations_by_page": {
    "0": [
      {
        "type": "merge_table",
        "page": 0,
        "rect": [
          243.5695037841797,
          712.375244140625,
          400.89630126953125,
          746.3341674804688
        ],
        "content": "Merge Table ",
        "author": "Graham Anderson",
        "features": {
          "font_size_pt": 25.09769058227539,
          "font_name": "HelveticaNeue-Bold",
          "is_bold": true,
          "line_height": null,
          "indent_mm": 0,
          "align": "left"
        },
        "is_empty_placeholder": false,
        "norm_rect": [
          0.39798938526826744,
          0.8994636920967487,
          0.6550593157998876,
          0.9423411205561474
        ],
        "original_snippet": "Merge Table",
        "context_window": [
          {
            "text": "on",
            "role": "previous_paragraph",
            "distance_mm": 20.4
          },
          {
            "text": "on",
            "role": "previous_paragraph",
            "distance_mm": 20.4
          },
          {
            "text": "Signal IO Descripti",
            "role": "previous_paragraph",
            "distance_mm": 28.2
          },
          {
            "text": "connexi",
            "role": "previous_paragraph",
            "distance_mm": 28.2
          },
          {
            "text": "Type",
            "role": "previous_paragraph",
            "distance_mm": 28.2
          }
        ],
        "continuation_ref": null
      },
      {
        "type": "section_header",
        "page": 0,
        "rect": [
          69.42581176757812,
          42.60369873046875,
          258.1748962402344,
          76.5626220703125
        ],
        "content": "Section Header",
        "author": "Graham Anderson",
        "features": {
          "font_size_pt": 25.097694396972656,
          "font_name": "HelveticaNeue-Bold",
          "is_bold": true,
          "line_height": null,
          "indent_mm": 0,
          "align": "left"
        },
        "is_empty_placeholder": false,
        "norm_rect": [
          0.11344086890127145,
          0.05379254890210701,
          0.421854405621298,
          0.09666997736150568
        ],
        "original_snippet": "Section Header",
        "context_window": [
          {
            "text": "4.1.5.4. BHT (Branch History Table) submodule",
            "role": "next_paragraph",
            "distance_mm": 2.1
          },
          {
            "text": "BHT is implemented as a memory which is composed ofBHTDepth configuration parameter",
            "role": "next_paragraph",
            "distance_mm": 14.0
          },
          {
            "text": "entries. The lower address bits of the virtual address point to the memory entry.",
            "role": "next_paragraph",
            "distance_mm": 21.8
          },
          {
            "text": "When a branch instruction is resolved by the EX_STAGE module, the branch PC and the taken",
            "role": "next_paragraph",
            "distance_mm": 34.9
          },
          {
            "text": "(or not taken) status information is stored in the Branch History Table.",
            "role": "next_paragraph",
            "distance_mm": 42.7
          }
        ]
      },
      {
        "type": "figure",
        "page": 0,
        "rect": [
          67.19325256347656,
          341.7665100097656,
          146.71719360351562,
          375.72540283203125
        ],
        "content": "Figure",
        "author": "Graham Anderson",
        "features": {
          "font_size_pt": 25.09767723083496,
          "font_name": "HelveticaNeue-Bold",
          "is_bold": true,
          "line_height": null,
          "indent_mm": 0,
          "align": "left"
        },
        "is_empty_placeholder": false,
        "norm_rect": [
          0.10979289634554994,
          0.43152337122445156,
          0.2397339764763327,
          0.4744007611515546
        ],
        "original_snippet": "Figure",
        "context_window": [
          {
            "text": "instructions as shown in the following figure.",
            "role": "previous_paragraph",
            "distance_mm": 9.7
          },
          {
            "text": "should be taken or not. The two bit counter is updated by the successive execution of the",
            "role": "previous_paragraph",
            "distance_mm": 17.5
          },
          {
            "text": "the current fetched instruction by the CACHE. It states whether the current branch request",
            "role": "previous_paragraph",
            "distance_mm": 25.3
          },
          {
            "text": "The Branch History Table is a table of two-bit saturating counters that takes the virtual address of",
            "role": "previous_paragraph",
            "distance_mm": 33.1
          },
          {
            "text": "(or not taken) status information is stored in the Branch History Table.",
            "role": "previous_paragraph",
            "distance_mm": 46.2
          }
        ]
      }
    ],
    "1": [
      {
        "type": "merge_table",
        "page": 1,
        "rect": [
          242.4490966796875,
          20.278076171875,
          399.7759094238281,
          54.23699951171875
        ],
        "content": "Merge Table ",
        "author": "Graham Anderson",
        "features": {
          "font_size_pt": 25.097698211669922,
          "font_name": "HelveticaNeue-Bold",
          "is_bold": true,
          "line_height": null,
          "indent_mm": 0,
          "align": "left"
        },
        "is_empty_placeholder": false,
        "norm_rect": [
          0.3961586547053717,
          0.025603631530145204,
          0.6532286101696538,
          0.06848105998954387
        ],
        "original_snippet": "Merge Table",
        "context_window": [
          {
            "text": "clk_i in Subsyste",
            "role": "next_paragraph",
            "distance_mm": 8.9
          },
          {
            "text": "SUBSY",
            "role": "next_paragraph",
            "distance_mm": 9.1
          },
          {
            "text": "logic",
            "role": "next_paragraph",
            "distance_mm": 9.1
          },
          {
            "text": "m Clock",
            "role": "next_paragraph",
            "distance_mm": 16.9
          },
          {
            "text": "STEM",
            "role": "next_paragraph",
            "distance_mm": 16.9
          }
        ],
        "continuation_ref": null
      },
      {
        "type": "not_section_header",
        "page": 1,
        "rect": [
          193.58270263671875,
          633.1112060546875,
          556.1859741210938,
          667.070068359375
        ],
        "content": "Text, NOT a Section Header",
        "author": "Graham Anderson",
        "features": {
          "font_size_pt": 25.09768295288086,
          "font_name": "HelveticaNeue-Bold",
          "is_bold": true,
          "line_height": null,
          "indent_mm": 0,
          "align": "right"
        },
        "is_empty_placeholder": false,
        "norm_rect": [
          0.3163116056155535,
          0.7993828359276357,
          0.9088006113089767,
          0.8422601873224432
        ],
        "original_snippet": "Text, NOT a Section Header",
        "context_window": [
          {
            "text": "As DebugEn = False,",
            "role": "same_line",
            "distance_mm": 4.1
          },
          {
            "text": "\u25cf debug_mode_iinput is tied to 0",
            "role": "next_paragraph",
            "distance_mm": 9.8
          },
          {
            "text": "\u25cf flush_bp_iinput is tied to 0",
            "role": "previous_paragraph",
            "distance_mm": 11.0
          },
          {
            "text": "Text, NOT a Section Header",
            "role": "parent_section",
            "distance_mm": 25.7
          },
          {
            "text": "For any HW configuration,",
            "role": "previous_paragraph",
            "distance_mm": 28.7
          }
        ]
      },
      {
        "type": "not_section_header",
        "page": 1,
        "rect": [
          218.13670349121094,
          528.9210205078125,
          580.7401123046875,
          562.8798828125
        ],
        "content": "Text, NOT a Section Header",
        "author": "Graham Anderson",
        "features": {
          "font_size_pt": 25.09769058227539,
          "font_name": "HelveticaNeue-Bold",
          "is_bold": true,
          "line_height": null,
          "indent_mm": 0,
          "align": "right"
        },
        "is_empty_placeholder": false,
        "norm_rect": [
          0.3564325220444623,
          0.667829571348248,
          0.9489217521318423,
          0.7107069227430556
        ],
        "original_snippet": "Text, NOT a Section Header",
        "context_window": [
          {
            "text": "For any HW configuration,",
            "role": "same_line",
            "distance_mm": 1.1
          },
          {
            "text": "the above table, they are listed below",
            "role": "previous_paragraph",
            "distance_mm": 5.0
          },
          {
            "text": "\u25cf flush_bp_iinput is tied to 0",
            "role": "next_paragraph",
            "distance_mm": 8.7
          },
          {
            "text": "Due to cv32a65x configuration, some ports are tied to a static value. These ports do not appear in",
            "role": "previous_paragraph",
            "distance_mm": 12.8
          },
          {
            "text": "Text, NOT a Section Header",
            "role": "next_paragraph",
            "distance_mm": 25.3
          }
        ]
      }
    ]
  },
  "total_annotations": 6,
  "placeholders_found": 0
}
```

### sections.json
```json
{
  "metadata": {
    "source_file": "test.pdf",
    "total_blocks": 7,
    "total_sections": 2,
    "section_summary": {
      "avg_blocks_per_section": 3.5,
      "min_blocks": 3,
      "max_blocks": 4
    }
  },
  "sections": [
    {
      "section_id": "section_0",
      "title": "4.1.5.4. BHT Submodule",
      "start_page": 0,
      "start_block": 0,
      "blocks": [
        {
          "type": "Title",
          "text": "4.1.5.4. BHT Submodule",
          "page": 0,
          "bbox": [
            100,
            100,
            500,
            130
          ]
        },
        {
          "type": "Text",
          "text": "The BHT submodule contains the branch history table.",
          "page": 0,
          "bbox": [
            100,
            150,
            500,
            170
          ]
        },
        {
          "type": "Text",
          "text": "It stores prediction information.",
          "page": 0,
          "bbox": [
            100,
            180,
            500,
            200
          ]
        },
        {
          "type": "Text",
          "text": "Additional content here.",
          "page": 0,
          "bbox": [
            100,
            210,
            500,
            230
          ]
        }
      ],
      "metadata": {
        "header_type": "Title",
        "header_confidence": 1.0,
        "preview": "The BHT submodule contains the branch history table. It stores prediction information. Additional content here."
      },
      "end_block": 3,
      "end_page": 0,
      "block_count": 4
    },
    {
      "section_id": "section_1",
      "title": "Interface",
      "start_page": 1,
      "start_block": 4,
      "blocks": [
        {
          "type": "SectionHeader",
          "text": "Interface",
          "page": 1,
          "bbox": [
            100,
            100,
            300,
            120
          ]
        },
        {
          "type": "Text",
          "text": "The interface description.",
          "page": 1,
          "bbox": [
            100,
            130,
            500,
            150
          ]
        },
        {
          "type": "Table",
          "text": "Signal | Direction | Description",
          "page": 1,
          "bbox": [
            100,
            160,
            500,
            300
          ]
        }
      ],
      "metadata": {
        "header_type": "SectionHeader",
        "header_confidence": 1.0,
        "preview": "The interface description."
      },
      "end_block": 6,
      "end_page": 1,
      "block_count": 3
    }
  ]
}
```

### enriched_sections.json
```json
{
  "sections": [
    {
      "section_id": "section_0",
      "title": "4.1.5.4. BHT Submodule",
      "start_page": 0,
      "start_block": 0,
      "blocks": [
        {
          "type": "Title",
          "text": "4.1.5.4. BHT Submodule",
          "page": 0,
          "bbox": [
            100,
            100,
            500,
            130
          ]
        },
        {
          "type": "Text",
          "text": "The BHT submodule contains the branch history table.",
          "page": 0,
          "bbox": [
            100,
            150,
            500,
            170
          ]
        },
        {
          "type": "Text",
          "text": "It stores prediction information.",
          "page": 0,
          "bbox": [
            100,
            180,
            500,
            200
          ]
        },
        {
          "type": "Text",
          "text": "Additional content here.",
          "page": 0,
          "bbox": [
            100,
            210,
            500,
            230
          ]
        }
      ],
      "metadata": {
        "header_type": "Title",
        "header_confidence": 1.0,
        "preview": "The BHT submodule contains the branch history table. It stores prediction information. Additional content here.",
        "surya_scores": {
          "table_scores": {},
          "overall_confidence": 0.0,
          "low_confidence_blocks": []
        },
        "pandas_analysis": [],
        "visual_assets": {
          "section_image": "/tmp/enrichment_output/images/section_section_0.png",
          "table_images": [],
          "figure_paths": []
        },
        "camelot_feasibility": {
          "feasible_tables": [],
          "total_improvement_potential": 0.0,
          "recommended_settings": {}
        },
        "annotation_matches": [],
        "block_metrics": {
          "block_count": 4,
          "block_types": {
            "Unknown": 4
          },
          "confidence_distribution": {
            "hig...
```

### validation.json
```json
{
  "metadata": {
    "extracted_file": "tmp/transcript_test/enriched_sections.json",
    "gold_file": "tmp/transcript_test/enriched_sections.json",
    "total_extracted": 2,
    "total_gold": 2,
    "matched_sections": 2,
    "unmatched_extracted": 0,
    "unmatched_gold": 0
  },
  "metrics": {
    "section_recall": 1.0,
    "section_precision": 1.0,
    "avg_text_accuracy": 1.0,
    "avg_structure_score": 1.0,
    "overall_accuracy": 1.0
  },
  "section_validations": [
    {
      "text_similarity": 1.0,
      "structure_score": 1.0,
      "overall_score": 1.0,
      "block_comparison": {
        "extracted": {
          "Title": 1,
          "Text": 3
        },
        "gold": {
          "Title": 1,
          "Text": 3
        }
      },
      "issues": [],
      "match_score": 1.0,
      "extracted_id": "section_0",
      "gold_id": "section_0"
    },
    {
      "text_similarity": 1.0,
      "structure_score": 1.0,
      "overall_score": 1.0,
      "block_comparison": {
        "extracted": {
          "SectionHeader": 1,
          "Text": 1,
          "Table": 1
        },
        "gold": {
          "SectionHeader": 1,
          "Text": 1,
          "Table": 1
        }
      },
      "issues": [],
      "match_score": 1.0,
      "extracted_id": "section_1",
      "gold_id": "section_1"
    }
  ],
  "unmatched": {
    "extracted_sections": [],
    "gold_sections": []
  },
  "recommendations": []
}
```

