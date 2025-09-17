Pipeline Contracts + Smokes — Working Prompt (Tailored)

Mission

- For each pipeline step, define:
  - Message/response contract (if LLM involved)
  - File/artifact contract (always)
  - 1–3 smokes (≤90s total per stage; offline whenever possible)
- Only after contracts + smokes are green, propose the smallest boundary change (prompts/rules/adapter). Do not edit stage core unless unavoidable.

Global Constraints

- Message shape (LLMs): user.content is parts → [{type:"text"}, {type:"image_url"}, …]; JSON guard at top of first text part; no provider-specific shapes.
- Response policy: strict JSON; response_format={"type":"json_object"}; clean_json_string allowed; extra/missing keys fail.
- Adapter logs per call: logs/{stage}/{id}/{req.json, raw.txt, verdict.json}.
- Offline first: prefer smokes that don’t hit network or DB; network smokes are opt-in.
- Time: each stage’s smokepack ≤90s.

Stage Checklist (fill per stage)

01_annotation_processor
- Purpose: Extract annotations; save crops; compute features; produce clean PDF.
- Contracts:
  - Files: image_output/*.png; json_output/01_annotations.json
  - JSON keys: annotations[], computed_features, relevant_to[], clean_pdf_path
- Smokes:
  - artifacts_offline: run helpers; assert at least one image and clean PDF exist.
  - schema_shape: json_output/01_annotations.json contains annotations[] and clean_pdf_path.

03_suspicious_headers
- Purpose: Verify suspicious headers with vision LLM.
- Contracts:
  - Message: text + one image; JSON guard; response_format json_object
  - JSON: {is_header:boolean, reasoning:string}
- Smokes:
  - adapter_text_only (opt-in): return strict JSON with keys; dump artifacts.
  - vision_min (opt-in): one real crop image; strict JSON; logs exist.

04_section_builder
- Purpose: Build hierarchical sections from verified blocks.
- Contracts:
  - Files: json_output/04_sections.json
  - JSON: sections[] with id, title, level, blocks[]
- Smokes:
  - minimal_blocks_offline: small fake verified blocks → sections[] non-empty; blocks[] present.

05_table_extractor
- Purpose: Extract tables with Camelot; save images; metrics.
- Contracts:
  - Files: json_output/05_tables.json; images under image_output/
  - JSON: tables[] with bbox, pandas_metrics.shape
- Smokes:
  - camelot_callable_offline: import and call try_camelot_strategy; returns list; skips if deps missing.
  - image_extract_offline: quick bbox render to file (optional).

06_figure_extractor
- Purpose: Extract figures; save images; optional LLM descriptions.
- Contracts:
  - Files: json_output/06_figures.json; images under image_output/
  - JSON: figures[] with bbox, image_path; ai_description optional
- Smokes:
  - extract_offline: render a small bbox to image; assert file exists (skip descriptions).

07_reflow_section
- Purpose: Reflow sections with text/vision context; merge tables; strict JSON.
- Contracts:
  - Message: standardized parts; JSON guard; response_format json_object
  - JSON: {reflowed_json, ocr_corrections, improvements_made, summary}
- Smokes (opt-in):
  - text_only_strict: strict JSON returned; logs.
  - vision_three_images: section + two tables images; strict JSON returned; logs.

09_section_summarizer
- Purpose: Summarize sections to summary_json.
- Contracts:
  - Message: text-only; JSON guard
  - JSON: {summary_json:{bullets[], length}}
- Smokes (opt-in):
  - adapter_strict: strict JSON returned; logs.

10_arangodb_exporter
- Purpose: Flatten reflow into pdf_objects with order.
- Contracts:
  - Files: json_output/10_flattened_data.json or DB confirmation
  - JSON: pdf_objects[] with object_index_in_doc
- Smokes:
  - flatten_minimal_offline: synthetic sections → ≥3 objects with ordering key.

11_arango_create_graph
- Purpose: Build relationships using FAISS + hierarchy; optional rationales.
- Contracts:
  - DB: edge collection created; indexes present (skip in offline)
  - JSON: N/A; focus on function behavior
- Smokes:
  - weights_math_offline: hierarchy_distance + combined weight within [0,1]; FAISS optional build guarded.

12_insert_annotations
- Purpose: Insert annotations into DB; bridge to pdf_objects.
- Contracts:
  - DB collections and graph ensured
- Smokes:
  - import_only_offline: module imports; CLI function exists; skip DB work.

14_report_generator
- Purpose: Aggregate outputs; compute stats; write report.
- Contracts:
  - Files: report JSON
  - JSON: stats include overall_quality_score and stage counts
- Smokes:
  - synth_pipeline_dir_offline: minimal json_output dirs → stats computed; key fields present.

Deliverables

- scripts/smokes/*: self-contained runners for operational checks.
- tests/contracts/*: schema strictness unit tests.
- prompts/*: updated prompts with prompt_version and JSON‑only guard.
- rules/*: YAML for tunable thresholds.
- CI: run prompt‑lint, contracts, smoke-01; optional 07 text nightly.

Notes

- Network/API-dependent smokes are opt-in and must skip gracefully if secrets are absent.
- All adapter-based smokes must dump logs/{stage}/{id}/ with req.json, raw.txt, verdict.json.

