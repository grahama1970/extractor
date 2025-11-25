# Enhanced Pipeline Walkthrough

**Date:** 2025-11-25  
**Run:** `data/results/latest_run` (pipeline 01–11; tables=6, figures=1; lattice-first sticky strategy with IOU dedupe guard; requirements enabled)

## Annotated Pages (latest_run)

### Page 1
<table>
<tr>
<td width="60%" style="vertical-align: top; border: 1px solid #ddd; padding: 0;">
  <img src="scripts/artifacts/annotated_latest-1.png" width="100%" style="display:block;" />
</td>
<td width="40%" style="vertical-align: top; padding: 14px; background-color: #fff;">
<div style='font-size: 0.85em; color: #777;'>Order on page: S1 → F1 → T1 (top to bottom)</div>
<h4>Sections</h4>
<div><a href="#section-s1">[S1]</a> 4.1.5.4. BHT (Branch History Table) submodule</div>
<div style='font-size: 0.85em; color: #777;'>Header overlay at top of page</div>
<h4>Figures</h4>
<div><a href="#figure-f1">[F1]</a> BHT State Transition Diagram</div>
<div style='font-size: 0.9em; color: #555;'>page 1 • bbox [73.5, 323.9, 541.5, 504.8]</div>
<div style='font-size: 0.9em; color: #555; margin-top:6px;'>The figure illustrates a four-state two-bit saturating counter used in a Branch History Table (BHT) to predict branch outcomes. States transition between ‘strongly not taken,’ ‘weakly not taken,’ ‘weakly taken,’ and ‘strongly taken’ based on whether a branch is taken or not taken. Arrows indicate state transitions triggered by branch execution results.</div>
<h4>Tables</h4>
<div><a href="#table-t1">[T1]</a> Signal | IO | Description | Connection | Type</div>
<div style='font-size: 0.9em; color: #555;'>1×5 • density 1.00 • acc 100%</div>
<div style='font-size: 0.85em; color: #777;'>Merged table continues onto page 2</div>
</td>
</tr>
</table>

### Page 2
<table>
<tr>
<td width="60%" style="vertical-align: top; border: 1px solid #ddd; padding: 0;">
<img src="scripts/artifacts/annotated_latest-2.png" width="100%" />
</td>
<td width="40%" style="vertical-align: top; padding: 14px; background-color: #fff;">
<h4>Tables</h4>
<div><a href="#table-t2">[T2]</a> clk_i | in | Subsystem Clock | SUBSYSTEM | logic</div>
<div style='font-size: 0.9em; color: #555;'>4×5 • density 1.00 • acc 100%</div>
<h4>Requirements</h4>
<div><a href="#req-r1">[R1]</a> Requirement inferred from T2 (see R1 below)</div>
<div style='font-size: 0.85em; color: #777;'>Requirement overlay shares bbox with T2</div>
</td>
</tr>
</table>

### Page 3
<table>
<tr>
<td width="60%" style="vertical-align: top; border: 1px solid #ddd; padding: 0;">
<img src="scripts/artifacts/annotated_latest-3.png" width="100%" />
</td>
<td width="40%" style="vertical-align: top; padding: 14px; background-color: #fff;">
<h4>Sections</h4>
<div><a href="#section-s2">[S2]</a> 4.1.5.4.1. REQUIREMENTS (Simulated)</div>
</td>
</tr>
</table>

### Page 4
<table>
<tr>
<td width="60%" style="vertical-align: top; border: 1px solid #ddd; padding: 0;">
<img src="scripts/artifacts/annotated_latest-4.png" width="100%" />
</td>
<td width="40%" style="vertical-align: top; padding: 14px; background-color: #fff;">
<h4>Sections</h4>
<div><a href="#section-s3">[S3]</a> 4.1.5. TABLE MERGE SCENARIOS (Simulated)</div>
<h4>Tables</h4>
<div><a href="#table-t3">[T3]</a> PC Range | Outcome | Count | Accuracy</div>
<div style='font-size: 0.9em; color: #555;'>7×4 • density 1.00 • acc 100%</div>
</td>
</tr>
</table>

### Page 5
<table>
<tr>
<td width="60%" style="vertical-align: top; border: 1px solid #ddd; padding: 0;">
<img src="scripts/artifacts/annotated_latest-5.png" width="100%" />
</td>
<td width="40%" style="vertical-align: top; padding: 14px; background-color: #fff;">
<h4>Headers</h4>
<div>Header candidate overlay (page 5) at bbox [54.0, 295.07, 174.15, 306.57]</div>
<h4>Tables</h4>
<div><a href="#table-t4">[T4]</a> 0x8000_0600-0x8000_06FF | not-taken | 67 | 85.2%</div>
<div style='font-size: 0.9em; color: #555;'>7×4 • density 1.00 • acc 100%</div>
<div><a href="#table-t5">[T5]</a> Signal | Description | Width</div>
<div style='font-size: 0.9em; color: #555;'>5×3 • density 1.00 • acc 97.9%</div>
<div><a href="#table-t6">[T6]</a> Parameter | Value | Notes</div>
<div style='font-size: 0.9em; color: #555;'>5×3 • density 1.00 • acc 100%</div>
<h4>Sections</h4>
<div><a href="#section-s3">[S3]</a> 4.1.5. TABLE MERGE SCENARIOS (Simulated)</div>
</td>
</tr>
</table>

## Section Hierarchy
- <a id="section-s1"></a><strong>4.1.5.4. BHT (Branch History Table) submodule</strong> (pages 1–2)
  - <a id="section-s2"></a><strong>4.1.5.4.1. REQUIREMENTS (Simulated)</strong> (page 3)
- <a id="section-s3"></a><strong>4.1.5. TABLE MERGE SCENARIOS (Simulated)</strong> (pages 4–5)

## Table Catalog (metrics & links)
- <a id="table-t1"></a>**T1 — Signal | IO | Description | Connection | Type** (page 1)  
  Shape 1×5 • density 1.00 • acc 100% • bbox 469.9×74.4 pts • image `data/results/latest_run/05_table_extractor/image_output/page_1_table_1.png`  
  Preview: `Signal | IO | Description | Connection | Type`
- <a id="table-t2"></a>**T2 — clk_i | in | Subsystem Clock | SUBSYSTEM | logic** (page 2)  
  Shape 4×5 • density 1.00 • acc 100% • bbox 469.9×406.9 pts • image `data/results/latest_run/05_table_extractor/image_output/page_2_table_1.png`  
  Preview: `clk_i | in | Subsystem Clock | SUBSYSTEM | logic`
- <a id="table-t3"></a>**T3 — PC Range | Outcome | Count | Accuracy** (page 4)  
  Shape 7×4 • density 1.00 • acc 100% • bbox 461.0×127.2 pts • image `data/results/latest_run/05_table_extractor/image_output/page_4_table_1.png`  
  Preview: `PC Range | Outcome | Count | Accuracy`
- <a id="table-t4"></a>**T4 — 0x8000_0600-0x8000_06FF | not-taken | 67 | 85.2%** (page 5)  
  Shape 7×4 • density 1.00 • acc 100% • bbox 461.0×126.9 pts • image `data/results/latest_run/05_table_extractor/image_output/page_5_table_1.png`  
  Preview: `0x8000_0600-0x8000_06FF | not-taken | 67 | 85.2%`
- <a id="table-t5"></a>**T5 — Signal | Description | Width** (page 5)  
  Shape 5×3 • density 1.00 • acc 97.9% • bbox 501.1×91.2 pts • image `data/results/latest_run/05_table_extractor/image_output/page_5_table_2.png`  
  Preview: `Signal | Description | Width`
- <a id="table-t6"></a>**T6 — Parameter | Value | Notes** (page 5)  
  Shape 5×3 • density 1.00 • acc 100% • bbox 501.1×90.9 pts • image `data/results/latest_run/05_table_extractor/image_output/page_5_table_3.png`  
  Preview: `Parameter | Value | Notes`

**Deduping note:** Previous duplicates came from an uninitialized overlap flag. Now we: (1) stick to the last successful *lattice* strategy per page, (2) fall back only when the page is empty/fragmented, and (3) apply a final IOU≥0.70 guard that keeps the higher-score table. Result: 6 unique tables (matches gold target).

## Figures
- <a id="figure-f1"></a>**F1 — BHT State Transition Diagram** (page 1)  
  bbox [73.5, 323.9, 541.5, 504.8]; image `data/results/latest_run/06_figure_extractor/image_output/figure_001.png`  
  Summary: four-state two-bit saturating counter for branch prediction.

## Requirements
- <a id="req-r1"></a>**R1 — Table-derived requirement (page 2)**  
  Text: “All constraints specified by Table 1 shall hold for the document. Columns: Signal | IO | Description | Connection | Type.”  
  From table T2 (bbox [72.0, 313.11, 541.92, 720.02]); modality: shall; confidence 0.6.

## Layout Sketcher (textual)
- **S1 layout (pages 1–2, grid=12, cols=3):** 55 text blocks, 2 tables, 1 figure. Largest elements: Table T2 (page 2, area≈191k), Figure F1 (page 1, area≈84k), main paragraph block (area≈70k). Columns overlap lightly (overlapped=true on some text).  
  Assets: T1 `page_1_table_1.png`, T2 `page_2_table_1.png`, F1 `figure_001.png`.
- **S2 layout (page 3, grid=12, cols=2):** 35 text blocks, no tables/figures. Tall narrow paragraphs dominate (top area≈13k). Good for linear reflow.
- **S3 layout (pages 4–5, grid=12, cols=3):** 26 text blocks, 4 tables. Largest tables: T3 (page 4, area≈58.6k), T4 (page 5, area≈58.5k); followed by text block (area≈48k). Assets: T3 `page_4_table_1.png`, T4 `page_5_table_1.png`, T5 `page_5_table_2.png`, T6 `page_5_table_3.png`.

## Reflowed JSON (flattened for ArangoDB)
- Source: `data/results/latest_run/10_arangodb_exporter/json_output/10_flattened_data.json`
- Objects exported: 53 (text + tables + figure) with summaries attached; see `10_export_confirmation.json`.
- Sample (pretty-printed):

```json
[
  {"_key":"0e8e2163bd32ef50e9b8a42a6d94d4bf","page":0,"object_type":"Text","section_title":"4.1.5.4. BHT (Branch History Table) submodule","text_preview":"4.1.5.4. BHT (Branch History Table) submodule"},
  {"_key":"4b27a3c36d6f037e8a3d8384fe65ded9","page":2,"object_type":"Table","section_title":"4.1.5.4. BHT (Branch History Table) submodule","text_preview":"clk_i | in | Subsystem Clock | SUBSYSTEM | logic\n--- | --- | --- | --- | ---\nvpc"},
  {"_key":"de89b2d4780869a60c62d8b8fbb1851f","page":0,"object_type":"Figure","section_title":"4.1.5.4. BHT (Branch History Table) submodule","text_preview":"Figure: BHT State Transition Diagram\nThe figure illustrates a four-state two-bit"}
]
```

## Notes
- Requirements miner (with `--extract-requirements`) extracted 1 requirement (`req_000000`) from the page-2 interface table (Signal|IO|Description|Connection|Type). `07_requirements.json` now populated; Arango export includes it.
- Annotated previews for all pages are saved under `scripts/artifacts/annotated_latest-*.png` for visual confirmation.
