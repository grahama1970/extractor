# Extractor Core Functionality Tasks

**Working Directory:** `/home/graham/workspace/experiments/extractor`
**Created:** 2025-06-25

---

## Task 1: Stabilise Output Pipeline  
*Priority: HIGH*

| ❓ | File / Area | Problem | Action |
|---|--------------|---------|--------|
| ☐ | `core/output.py` (`text_from_rendered`) | Duplicate `elif isinstance(rendered, str)` causes unreachable code and silent failures. | Deduplicate branches and add full return typing so every renderer path works. |
| ☐ | `core/output.py` (`output_to_format`) | When user passes `output_path` without extension, wrong file saved if `.` present in filename. | Normalise path logic; always append correct ext regardless of existing dot. |
| ☐ | `core/output.py` (`convert_if_not_rgb`) | Alpha-channel images raise error when saving as JPEG. | Auto-convert `RGBA` → `RGB` before save (already partially done, ensure path used everywhere). |

---

## Task 2: Configuration & Settings  
*Priority: HIGH*

- ☐ Replace dual `@computed_field`+`@property` decorators in `core/settings.py` with correct Pydantic v2 `@computed_field(return_type=...)` signatures.
- ☐ Expose `Settings.verify()` helper that prints missing env vars for quick CLI debugging (`extractor doctor`).
- ☐ Ensure `TORCH_DEVICE_MODEL` + `MODEL_DTYPE` correctly detect CUDA, MPS, CPU combos.

---

## Task 3: Dependency Cleanup / Legacy Rename  
*Priority: HIGH*

- ☐ Remove stale `marker` imports – create thin shim module only if absolutely required for backwards compatibility.
- ☐ Update documentation snippets (`README.md`, examples) to use `extractor` package.

---

## Task 4: Font Handling  
*Priority: MEDIUM*

- ☐ Call `util.download_font()` lazily from first renderer that needs the font (e.g. `MarkdownRenderer.__init__`).
- ☐ Add `--no-font-download` CLI flag to skip in limited environments.

---

## Task 5: CLI & Public API  
*Priority: MEDIUM*

| Step | Deliverable |
|------|-------------|
| 1 | Create `extractor.api` with `convert_pdf`, `convert_docx`, `convert_pptx`, `convert_xml`, `convert_html`. |
| 2 | CLI wrapper (`extractor <file>`): detect type, call correct function, output Markdown by default. |
| 3 | Provide `--json`, `--html` flags to switch renderer without changing code. |

---

## Task 6: Logging & Error Handling  
*Priority: MEDIUM*

- ☐ Integrate `logging` (or `loguru`) in `core/logger.py` with JSON formatter.
- ☐ Replace silent failures with explicit logger calls + helpful tracebacks.

---

## Task 7: (Optional) Test & CI  
*Priority: LOW*

- PyTest suite and CI pipeline remain desirable but **can be addressed after core functionality is stable**.

---

## Success Criteria

- [ ] PDF/DOCX/PPTX/XML/HTML → Markdown runs end-to-end with a single command.
- [ ] CLI shows helpful error if environment misconfigured (fonts, CUDA, API keys).
- [ ] No stale `marker` references in code path executed by default CLI.
- [ ] Logs written to `conversion_results/logs/` with at least INFO level events.
- [ ] README quick-start commands succeed unmodified.
