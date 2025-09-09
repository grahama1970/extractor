Below is an **exhaustive inventory** of every line that is **stubbed / mocked / hallucinated / non-working** in the three POC scripts **excluding** `annotation_storage.py`.

I have classified them by **type of stub** and given the exact file, line range, and a one-line explanation.

---

### 1. Missing / Hallucinated Imports
| File | Lines | Stub |
|---|---|---|
| `poc_00_extract_annotations.py` | 183-185 | `from extractor.core.storage.annotation_storage import AnnotationStorage` – package does not exist. |
| `poc_01_marker_extraction.py` | 65 | `"marker"` CLI is invoked via `subprocess` but **never installed** or listed in requirements. |
| `poc_02_relabel_suspicious.py` | 45-48 | `claude` CLI is invoked via `subprocess` but **never installed** or authenticated. |

---

### 2. Hard-coded, Non-existent File Paths
| File | Lines | Stub |
|---|---|---|
| `poc_00_extract_annotations.py` | 96-97 | `project_root / "tmp" / "pipeline_run" / "annotations.json"` – directory never created. |
|  | 104-107 | `project_root / "gold_standards" / "gold_standard_learned_annotations.json"` – never shipped. |
|  | 327, 332 | `inputs/BHT_CV32A65X_marked.pdf` and `proof_of_concept/BHT_CV32A65X_marked.pdf` – may not exist. |
| `poc_01_marker_extraction.py` | 62 | `tmp/raw_marker_blocks.json` – file is **read if present** but **never written**; cache always cold. |
|  | 89 | `marker_output/{pdf_stem}/{pdf_stem}.json` – directory tree never ensured. |
| `poc_02_relabel_suspicious.py` | 288-300 | Same three paths as POC-00 for annotations; same problem. |

---

### 3. Silent No-Op / Mock Implementations
| File | Lines | Stub |
|---|---|---|
| `poc_00_extract_annotations.py` | 171-179 | `ArangoDBAnnotationStore.store_annotation` – only appends to an **in-memory list**. |
|  | 187-196 | `ArangoDBAnnotationStore.search_annotations` – only searches the same in-memory list. |
| `poc_01_marker_extraction.py` | 55-58 | `extract_with_marker` – if `cached_file` absent, **always falls back to subprocess**; but subprocess path is stubbed because `marker` missing (see above). |
|  | 82-84 | `output_file.exists()` check – if subprocess succeeds but path is wrong, raises `FileNotFoundError`. |
| `poc_02_relabel_suspicious.py` | 167-168 | `extract_visual_context` – returns `None` when PyMuPDF or Pillow unavailable; downstream silently degrades to **heuristic-only** mode without warning. |
|  | 222-226 | `analyze_with_claude` – if `claude` CLI fails or missing, silently falls back to `analyze_without_vision`. |
|  | 232-246 | Claude subprocess **never** actually sends the PNG over stdin (pipe just fails), so **every call** drops to fallback. |

---

### 4. Guaranteed Runtime Exceptions
| File | Lines | Stub |
|---|---|---|
| `poc_00_extract_annotations.py` | 120, 123 | `logger.success(...)` – `AttributeError`; Loguru has no `.success`. |
| `poc_01_marker_extraction.py` | 135, 165 | Same `.success` calls. |
| `poc_02_relabel_suspicious.py` | 374, 446 | Same `.success` calls. |
| `poc_00_extract_annotations.py` | 137 | `doc = fitz.open(str(pdf_path))` **unconditionally executed** even when `pdf_path.exists()` is false (logic bug). |
| `poc_01_marker_extraction.py` | 78 | `subprocess.run(..., timeout=60)` – will raise `TimeoutExpired` on large PDFs; no retry / handling. |

---

### 5. Unreachable / Dead Code
| File | Lines | Stub |
|---|---|---|
| `poc_00_extract_annotations.py` | 88-92 | `map_type_to_instruction` is defined but **never used** in the PDF extraction path; only `map_annotation_to_instruction` is called. |
| `poc_02_relabel_suspicious.py` | 260-270 | `_calculate_overlap` and `_find_overlapping_text` are defined but **never invoked** because all annotation context is mocked. |

---

### 6. Configuration / Environment Assumptions
| File | Lines | Stub |
|---|---|---|
| All files | 30-38 | `find_dotenv()` followed by `project_root = Path(env_path).parent` – if `.env` is missing, silently defaults to `Path.cwd()` which may not be the repo root. |
| `poc_01_marker_extraction.py` | 66 | `--max_pages 10` is hard-coded; production users will silently lose pages > 10. |

---

### Summary Count
- **Missing imports / CLIs**: 3  
- **Non-existent file paths**: 8  
- **Silent no-op / mock methods**: 6  
- **Guaranteed exceptions**: 5  
- **Dead / unreachable code**: 2  
- **Environment / configuration stubs**: 2  

**Total distinct stubs outside `annotation_storage.py`: 26**