# Extraction Journal

## 2025-11-26 Full pipeline rerun
- Ran stages 01→07 (tables, figures, reflow, requirements) + 06b layout + 09a annotator after fixes.
- Results: 6 raw tables, 1 figure, 3 sections, 20 requirements; annotated PNGs under scripts/artifacts/annotated_latest-*.png.
- Visual report below is regenerated via scripts/generate_enhanced_walkthrough.py (connectors removed; pairing via order + color swatches). Self-contained copy: scripts/artifacts/visuals_pipeline/walkthrough_local.md.

# Enhanced Pipeline Walkthrough

**Date:** 2025-11-26
**Format:** Side-by-side visualization of extracted artifacts.

### Page 1
<table>
<tr>
<td width="60%" style="vertical-align: top; border: 1px solid #ddd; padding: 0;">
<img src="scripts/artifacts/visuals_pipeline/annotated_p1_enhanced.png" width="100%" />
</td>
<td width="40%" style="vertical-align: top; padding: 15px; background-color: #fff;">
<div style='font-size:0.9em; color:#666; margin-bottom:8px;'>Order on page: S1 → F1 → T1 (top to bottom)</div>
<div><span style='display:inline-block;width:10px;height:10px;border-radius:50%;background:#198754;margin-right:6px;'></span><strong>[S1] 4.1.5.4. BHT (Branch History Table) submodule</strong></div>
<hr style='border: 0; border-top: 1px solid #eee; margin: 8px 0;'>
<div><span style='display:inline-block;width:10px;height:10px;border-radius:50%;background:#0d6efd;margin-right:6px;'></span><strong>[F1] Figure</strong></div>
<div style='font-size:0.85em;color:#555;'>page 1 • bbox [73.5, 323.9186492919922, 541.5, 504.8186859130859]</div>
<div style='font-size: 0.9em; font-style: italic; margin-bottom: 8px;'>The figure illustrates a four-state two-bit saturating counter used in a Branch History Table (BHT) to predict branch outcomes. States transition between &#x27;strongly not taken,&#x27; &#x27;weakly not taken,&#x27; &#x27;weakly taken,&#x27; and &#x27;strongly taken&#x27; based on whether branches are taken or not taken. Arrows indicate state transitions triggered by actual branch behavior.</div>
<hr style='border: 0; border-top: 1px solid #eee; margin: 8px 0;'>
<div><span style='display:inline-block;width:10px;height:10px;border-radius:50%;background:#dc3545;margin-right:6px;'></span><strong>[T1] INFER: Signal | IO | Description | Connection | Type</strong></div>
<div style='font-size:0.85em;color:#555;'>page 1 • bbox [72.0, 106.2877915783096, 541.92, 180.6652529536504]</div>
<div style='font-size: 0.9em; color: #555; margin-bottom: 4px;'>Dim: 1x5 | Density: 1.00</div>
<div style='font-size:0.8em;color:#666;'>Camelot acc: 100.00</div>
<div style='font-size: 0.8em; font-family: monospace; color: #666;'>Cols: 0, 1, 2, 3, 4</div>
<div style='font-size: 0.8em; font-family: monospace; background: #f5f5f5; padding: 2px;'>Signal | IO | Description | Connection</div>
<hr style='border: 0; border-top: 1px solid #eee; margin: 8px 0;'>
</td>
</tr>
</table>

### Page 2
<table>
<tr>
<td width="60%" style="vertical-align: top; border: 1px solid #ddd; padding: 0;">
<img src="scripts/artifacts/visuals_pipeline/annotated_p2_enhanced.png" width="100%" />
</td>
<td width="40%" style="vertical-align: top; padding: 15px; background-color: #fff;">
<div style='font-size:0.9em; color:#666; margin-bottom:8px;'>Order on page: T1 (top to bottom)</div>
<div><span style='display:inline-block;width:10px;height:10px;border-radius:50%;background:#dc3545;margin-right:6px;'></span><strong>[T1] INFER: clk_i | in | Subsystem Clock | SUBSYSTEM | logic</strong></div>
<div style='font-size:0.85em;color:#555;'>page 2 • bbox [72.0, 313.10511966070885, 541.92, 720.0218115722508]</div>
<div style='font-size: 0.9em; color: #555; margin-bottom: 4px;'>Dim: 4x5 | Density: 1.00</div>
<div style='font-size:0.8em;color:#666;'>Camelot acc: 100.00</div>
<div style='font-size: 0.8em; font-family: monospace; color: #666;'>Cols: 0, 1, 2, 3, 4</div>
<div style='font-size: 0.8em; font-family: monospace; background: #f5f5f5; padding: 2px;'>clk_i | in | Subsystem Clock | SUBSYSTEM</div>
<hr style='border: 0; border-top: 1px solid #eee; margin: 8px 0;'>
<h4>Requirements</h4>
<div style='background-color: #f5f5f5; padding: 6px; margin: 4px 0; border-left: 3px solid #ff6b35;'>
<div style='font-size: 0.85em; font-weight: bold; color: #ff6b35;'>req_000000</div>
<div style='font-size: 0.85em;'>All constraints specified by Table 1 shall hold for the document. Columns: Signal | IO | Description | Connection | Type.</div>
<div style='font-size: 0.75em; color: #666; margin-top: 2px;'>Modality: shall • Confidence: 0.60</div>
</div>
</td>
</tr>
</table>

### Page 3
<table>
<tr>
<td width="60%" style="vertical-align: top; border: 1px solid #ddd; padding: 0;">
<img src="scripts/artifacts/visuals_pipeline/annotated_p3_enhanced.png" width="100%" />
</td>
<td width="40%" style="vertical-align: top; padding: 15px; background-color: #fff;">
<div style='font-size:0.9em; color:#666; margin-bottom:8px;'>Order on page: S1 (top to bottom)</div>
<div><span style='display:inline-block;width:10px;height:10px;border-radius:50%;background:#198754;margin-right:6px;'></span><strong>[S1] 4.1.5.4.1. REQUIREMENTS (Simulated)</strong></div>
<hr style='border: 0; border-top: 1px solid #eee; margin: 8px 0;'>
<h4>Requirements</h4>
<div style='background-color: #fff9e6; padding: 6px; margin: 4px 0; border-left: 3px solid #ff6b35;'>
<div style='font-size: 0.85em; font-weight: bold; color: #ff6b35;'>REQ-BHT-1</div>
<div style='font-size: 0.85em;'>REQ-BHT-1: The BHT shall implement BHTDepth entries and index them using the lower bits of</div>
<div style='font-size: 0.75em; color: #666; margin-top: 2px;'>Modality: shall • Confidence: 0.90</div>
</div>
<div style='background-color: #f5f5f5; padding: 6px; margin: 4px 0; border-left: 3px solid #ff6b35;'>
<div style='font-size: 0.85em; font-weight: bold; color: #ff6b35;'>req_000002</div>
<div style='font-size: 0.85em;'>The width of VPC_i shall match CVA6Cfg.VLEN.</div>
<div style='font-size: 0.75em; color: #666; margin-top: 2px;'>Modality: shall • Confidence: 0.70</div>
</div>
<div style='background-color: #fff9e6; padding: 6px; margin: 4px 0; border-left: 3px solid #ff6b35;'>
<div style='font-size: 0.85em; font-weight: bold; color: #ff6b35;'>REQ-BHT-2</div>
<div style='font-size: 0.85em;'>REQ-BHT-2: Each BHT entry shall contain a two-bit saturating counter that encodes taken/not-taken</div>
<div style='font-size: 0.75em; color: #666; margin-top: 2px;'>Modality: shall • Confidence: 0.90</div>
</div>
<div style='background-color: #fff9e6; padding: 6px; margin: 4px 0; border-left: 3px solid #ff6b35;'>
<div style='font-size: 0.85em; font-weight: bold; color: #ff6b35;'>REQ-BHT-3</div>
<div style='font-size: 0.85em;'>REQ-BHT-3: The BHT shall accept update information from the execute stage (bht_update_i)
including the branch PC and resolved outcome, and shall updat...</div>
<div style='font-size: 0.75em; color: #666; margin-top: 2px;'>Modality: shall • Confidence: 0.90</div>
</div>
<div style='background-color: #fff9e6; padding: 6px; margin: 4px 0; border-left: 3px solid #ff6b35;'>
<div style='font-size: 0.85em; font-weight: bold; color: #ff6b35;'>REQ-BHT-4</div>
<div style='font-size: 0.85em;'>REQ-BHT-4: The BHT shall provide a prediction output (bht_prediction_o) aligned with the</div>
<div style='font-size: 0.75em; color: #666; margin-top: 2px;'>Modality: shall • Confidence: 0.90</div>
</div>
<div style='background-color: #fff9e6; padding: 6px; margin: 4px 0; border-left: 3px solid #ff6b35;'>
<div style='font-size: 0.85em; font-weight: bold; color: #ff6b35;'>REQ-BHT-5</div>
<div style='font-size: 0.85em;'>REQ-BHT-5: The BHT shall not be flushed by pipeline events.</div>
<div style='font-size: 0.75em; color: #666; margin-top: 2px;'>Modality: shall • Confidence: 0.90</div>
</div>
<div style='background-color: #fff9e6; padding: 6px; margin: 4px 0; border-left: 3px solid #ff6b35;'>
<div style='font-size: 0.85em; font-weight: bold; color: #ff6b35;'>REQ-BHT-6</div>
<div style='font-size: 0.85em;'>REQ-BHT-6: The subsystem clock clk_i and asynchronous active-low reset rst_ni shall be the only</div>
<div style='font-size: 0.75em; color: #666; margin-top: 2px;'>Modality: shall • Confidence: 0.90</div>
</div>
<div style='background-color: #fff9e6; padding: 6px; margin: 4px 0; border-left: 3px solid #ff6b35;'>
<div style='font-size: 0.85em; font-weight: bold; color: #ff6b35;'>REQ-BHT-7</div>
<div style='font-size: 0.85em;'>REQ-BHT-7: When a branch is pre-decoded by the instr_scan submodule, the BHT shall indicate
whether a VPC_i address hits and shall return the taken/no...</div>
<div style='font-size: 0.75em; color: #666; margin-top: 2px;'>Modality: shall • Confidence: 0.90</div>
</div>
<div style='background-color: #fff9e6; padding: 6px; margin: 4px 0; border-left: 3px solid #ff6b35;'>
<div style='font-size: 0.85em; font-weight: bold; color: #ff6b35;'>REQ-BHT-8</div>
<div style='font-size: 0.85em;'>REQ-BHT-8: In cv32a65x configuration, flush_bp_i shall be tied to 0.</div>
<div style='font-size: 0.75em; color: #666; margin-top: 2px;'>Modality: shall • Confidence: 0.90</div>
</div>
<div style='background-color: #f5f5f5; padding: 6px; margin: 4px 0; border-left: 3px solid #ff6b35;'>
<div style='font-size: 0.85em; font-weight: bold; color: #ff6b35;'>req_000010</div>
<div style='font-size: 0.85em;'>debug_mode_i shall be tied to 0 and shall not appear as an external port.</div>
<div style='font-size: 0.75em; color: #666; margin-top: 2px;'>Modality: shall • Confidence: 0.70</div>
</div>
<div style='background-color: #fff9e6; padding: 6px; margin: 4px 0; border-left: 3px solid #ff6b35;'>
<div style='font-size: 0.85em; font-weight: bold; color: #ff6b35;'>REQ-BHT-9</div>
<div style='font-size: 0.85em;'>REQ-BHT-9: All signal widths and types exposed by the BHT interfaces shall be consistent with the</div>
<div style='font-size: 0.75em; color: #666; margin-top: 2px;'>Modality: shall • Confidence: 0.90</div>
</div>
<div style='background-color: #fff9e6; padding: 6px; margin: 4px 0; border-left: 3px solid #ff6b35;'>
<div style='font-size: 0.85em; font-weight: bold; color: #ff6b35;'>REQ-BHT-10</div>
<div style='font-size: 0.85em;'>REQ-BHT-10: The prediction datapath shall not introduce structural hazards with instruction fetch;</div>
<div style='font-size: 0.75em; color: #666; margin-top: 2px;'>Modality: shall • Confidence: 0.90</div>
</div>
<div style='background-color: #f5f5f5; padding: 6px; margin: 4px 0; border-left: 3px solid #ff6b35;'>
<div style='font-size: 0.85em; font-weight: bold; color: #ff6b35;'>req_000013</div>
<div style='font-size: 0.85em;'>updates from the execute stage shall not stall front-end prediction availability.</div>
<div style='font-size: 0.75em; color: #666; margin-top: 2px;'>Modality: shall • Confidence: 0.70</div>
</div>
<div style='background-color: #f5f5f5; padding: 6px; margin: 4px 0; border-left: 3px solid #ff6b35;'>
<div style='font-size: 0.85em; font-weight: bold; color: #ff6b35;'>req_000014</div>
<div style='font-size: 0.85em;'>The BHT shall locate the entry indexed by the provided VPC and shall increment or decrement the</div>
<div style='font-size: 0.75em; color: #666; margin-top: 2px;'>Modality: shall • Confidence: 0.70</div>
</div>
<div style='background-color: #f5f5f5; padding: 6px; margin: 4px 0; border-left: 3px solid #ff6b35;'>
<div style='font-size: 0.85em; font-weight: bold; color: #ff6b35;'>req_000015</div>
<div style='font-size: 0.85em;'>The update shall saturate at the counter bounds and shall not invalidate other entries.</div>
<div style='font-size: 0.75em; color: #666; margin-top: 2px;'>Modality: shall • Confidence: 0.70</div>
</div>
<div style='background-color: #f5f5f5; padding: 6px; margin: 4px 0; border-left: 3px solid #ff6b35;'>
<div style='font-size: 0.85em; font-weight: bold; color: #ff6b35;'>req_000016</div>
<div style='font-size: 0.85em;'>If the indexed entry exists, the BHT shall return the current prediction in bht_prediction_o aligned to</div>
<div style='font-size: 0.75em; color: #666; margin-top: 2px;'>Modality: shall • Confidence: 0.70</div>
</div>
<div style='background-color: #f5f5f5; padding: 6px; margin: 4px 0; border-left: 3px solid #ff6b35;'>
<div style='font-size: 0.85em; font-weight: bold; color: #ff6b35;'>req_000017</div>
<div style='font-size: 0.85em;'>If the indexed entry does not exist, the BHT shall return a default not-taken prediction (unless</div>
<div style='font-size: 0.75em; color: #666; margin-top: 2px;'>Modality: shall • Confidence: 0.70</div>
</div>
</td>
</tr>
</table>

### Page 4
<table>
<tr>
<td width="60%" style="vertical-align: top; border: 1px solid #ddd; padding: 0;">
<img src="scripts/artifacts/visuals_pipeline/annotated_p4_enhanced.png" width="100%" />
</td>
<td width="40%" style="vertical-align: top; padding: 15px; background-color: #fff;">
<div style='font-size:0.9em; color:#666; margin-bottom:8px;'>Order on page: S1 → T1 (top to bottom)</div>
<div><span style='display:inline-block;width:10px;height:10px;border-radius:50%;background:#198754;margin-right:6px;'></span><strong>[S1] 4.1.5. TABLE MERGE SCENARIOS (Simulated)</strong></div>
<hr style='border: 0; border-top: 1px solid #eee; margin: 8px 0;'>
<div><span style='display:inline-block;width:10px;height:10px;border-radius:50%;background:#dc3545;margin-right:6px;'></span><strong>[T1] INFER: PC Range | Outcome | Count | Accuracy</strong></div>
<div style='font-size:0.85em;color:#555;'>page 4 • bbox [53.519999999999996, 471.6970614965162, 514.56, 598.858527718873]</div>
<div style='font-size: 0.9em; color: #555; margin-bottom: 4px;'>Dim: 7x4 | Density: 1.00</div>
<div style='font-size:0.8em;color:#666;'>Camelot acc: 100.00</div>
<div style='font-size: 0.8em; font-family: monospace; color: #666;'>Cols: 0, 1, 2, 3</div>
<div style='font-size: 0.8em; font-family: monospace; background: #f5f5f5; padding: 2px;'>PC Range | Outcome | Count | Accuracy</div>
<hr style='border: 0; border-top: 1px solid #eee; margin: 8px 0;'>
<h4>Requirements</h4>
<div style='background-color: #f5f5f5; padding: 6px; margin: 4px 0; border-left: 3px solid #ff6b35;'>
<div style='font-size: 0.85em; font-weight: bold; color: #ff6b35;'>req_000019</div>
<div style='font-size: 0.85em;'>All constraints specified by Table 1 shall hold for the document. Columns: 0 | 1 | 2 | 3.</div>
<div style='font-size: 0.75em; color: #666; margin-top: 2px;'>Modality: shall • Confidence: 0.60</div>
</div>
</td>
</tr>
</table>

### Page 5
<table>
<tr>
<td width="60%" style="vertical-align: top; border: 1px solid #ddd; padding: 0;">
<img src="scripts/artifacts/visuals_pipeline/annotated_p5_enhanced.png" width="100%" />
</td>
<td width="40%" style="vertical-align: top; padding: 15px; background-color: #fff;">
<div style='font-size:0.9em; color:#666; margin-bottom:8px;'>Order on page: T1 → T2 → T3 (top to bottom)</div>
<div><span style='display:inline-block;width:10px;height:10px;border-radius:50%;background:#dc3545;margin-right:6px;'></span><strong>[T1] INFER: 0x8000_0600-0x8000_06FF | not-taken | 67 | 85.2%</strong></div>
<div style='font-size:0.85em;color:#555;'>page 5 • bbox [53.519999999999996, 520.1623750378673, 514.56, 647.083913965465]</div>
<div style='font-size: 0.9em; color: #555; margin-bottom: 4px;'>Dim: 7x4 | Density: 1.00</div>
<div style='font-size:0.8em;color:#666;'>Camelot acc: 100.00</div>
<div style='font-size: 0.8em; font-family: monospace; color: #666;'>Cols: 0, 1, 2, 3</div>
<div style='font-size: 0.8em; font-family: monospace; background: #f5f5f5; padding: 2px;'>0x8000_0600-0x8000_0 | not-taken | 67 | 85.2%</div>
<hr style='border: 0; border-top: 1px solid #eee; margin: 8px 0;'>
<div><span style='display:inline-block;width:10px;height:10px;border-radius:50%;background:#dc3545;margin-right:6px;'></span><strong>[T2] INFER: Signal | Description | Width</strong></div>
<div style='font-size:0.85em;color:#555;'>page 5 • bbox [53.519999999999996, 347.65465010602844, 554.64, 438.8270221145107]</div>
<div style='font-size: 0.9em; color: #555; margin-bottom: 4px;'>Dim: 5x3 | Density: 1.00</div>
<div style='font-size:0.8em;color:#666;'>Camelot acc: 97.90</div>
<div style='font-size: 0.8em; font-family: monospace; color: #666;'>Cols: 0, 1, 2</div>
<div style='font-size: 0.8em; font-family: monospace; background: #f5f5f5; padding: 2px;'>Signal | Description | Width</div>
<hr style='border: 0; border-top: 1px solid #eee; margin: 8px 0;'>
<div><span style='display:inline-block;width:10px;height:10px;border-radius:50%;background:#dc3545;margin-right:6px;'></span><strong>[T3] INFER: Parameter | Value | Notes</strong></div>
<div style='font-size:0.85em;color:#555;'>page 5 • bbox [53.519999999999996, 218.5737655255983, 554.64, 309.50621023932143]</div>
<div style='font-size: 0.9em; color: #555; margin-bottom: 4px;'>Dim: 5x3 | Density: 1.00</div>
<div style='font-size:0.8em;color:#666;'>Camelot acc: 100.00</div>
<div style='font-size: 0.8em; font-family: monospace; color: #666;'>Cols: 0, 1, 2</div>
<div style='font-size: 0.8em; font-family: monospace; background: #f5f5f5; padding: 2px;'>Parameter | Value | Notes</div>
<hr style='border: 0; border-top: 1px solid #eee; margin: 8px 0;'>
<h4>Requirements</h4>
<div style='background-color: #f5f5f5; padding: 6px; margin: 4px 0; border-left: 3px solid #ff6b35;'>
<div style='font-size: 0.85em; font-weight: bold; color: #ff6b35;'>req_000018</div>
<div style='font-size: 0.85em;'>Table 4-2 and Table 4-3 are distinct datasets and shall not be merged.</div>
<div style='font-size: 0.75em; color: #666; margin-top: 2px;'>Modality: shall • Confidence: 0.70</div>
</div>
</td>
</tr>
</table>

## Section Hierarchy
      - 0.0.0.1 4.1.5.4. BHT (Branch History Table) submodule (pages 1-2)
          - 0.0.0.1.0.1 4.1.5.4.1. REQUIREMENTS (Simulated) (page 3)
    - 0.0.1 4.1.5. TABLE MERGE SCENARIOS (Simulated) (pages 4-5)

## Table Data (full)
- (p1) INFER: Signal | IO | Description | Connection | Type: 1x5, density=1.00, camelot_acc=100.00
- (p2) INFER: clk_i | in | Subsystem Clock | SUBSYSTEM | logic: 4x5, density=1.00, camelot_acc=100.00
- (p4) INFER: PC Range | Outcome | Count | Accuracy: 7x4, density=1.00, camelot_acc=100.00
- (p5) INFER: Parameter | Value | Notes: 5x3, density=1.00, camelot_acc=100.00
- (p5) INFER: Signal | Description | Width: 5x3, density=1.00, camelot_acc=97.90
- (p5) INFER: 0x8000_0600-0x8000_06FF | not-taken | 67 | 85.2%: 7x4, density=1.00, camelot_acc=100.00

## Layout Sketcher (text)
      - Section 0.0.0.1: 4.1.5.4. BHT (Branch History Table) submodule (pages 1-2)
        - Page 1: text_blocks=18, tables=1, figures=1
          - Dominant column: 2 (0.89 char share)
          - Table: 1x5, density=1.00, acc=100.00000000000001, area=34951.45664950015, w=469.91999999999996, h=74.3774613753408, nw=None, nh=None, aspect=None, title=INFER: Signal | IO | Description | Connection | Type
          - Text col 2: blocks=7, chars=568, y_norm=0.0012626262626262627, order=0, snippet="4.1.5.4. BHT (Branch History Table) subm … ACHE. It states whether the current bra…"
          - Text col 0: blocks=1, chars=47, y_norm=0.005050505050505051, order=1, snippet="instructions as shown in the following f … ctions as shown in the following figure."
          - Text col 1: blocks=1, chars=3, y_norm=0.011363636363636364, order=2, snippet="on"
          - Text col 2: blocks=2, chars=90, y_norm=0.005050505050505051, order=3, snippet="should be taken or not. The two bit coun … text"
          - Text col 2: blocks=1, chars=93, y_norm=0.008838383838383838, order=4, snippet="When a branch instruction is pre-decoded …  by instr_scan submodule, the BHT valid…"
        - Page 2: text_blocks=37, tables=1, figures=0
          - Dominant column: 0 (0.67 char share)
          - Table: 4x5, density=1.00, acc=100.0, area=191218.2918630718, w=469.91999999999996, h=406.916691911542, nw=None, nh=None, aspect=None, title=INFER: clk_i | in | Subsystem Clock | SUBSYSTEM | logic
          - Text col 0: blocks=2, chars=24, y_norm=0.0012626262626262627, order=0, snippet="clk_i in Subsyste … logic"
          - Text col 1: blocks=1, chars=8, y_norm=0.0012626262626262627, order=1, snippet="m Clock"
          - Text col 2: blocks=2, chars=11, y_norm=0.0012626262626262627, order=2, snippet="SUBSY … STEM"
          - Text col 0: blocks=2, chars=25, y_norm=0.0025252525252525255, order=3, snippet="rst_ni in Asynchro … logic"
          - Text col 1: blocks=2, chars=22, y_norm=0.0025252525252525255, order=4, snippet="nous reset … active low"
          - Section 0.0.0.1.0.1: 4.1.5.4.1. REQUIREMENTS (Simulated) (page 3)
            - Page 3: text_blocks=35, tables=0, figures=0
              - Dominant column: 1 (0.86 char share)
              - Text col 0: blocks=1, chars=36, y_norm=0.0012626262626262627, order=0, snippet="4.1.5.4.1. REQUIREMENTS (Simulated)"
              - Text col 1: blocks=1, chars=203, y_norm=0.0012626262626262627, order=1, snippet="This simulated section provides formal,  … hardware-oriented requirements for the …"
              - Text col 0: blocks=2, chars=51, y_norm=0.0025252525252525255, order=2, snippet="predictions to the front end. … Formal Requirements:"
              - Text col 1: blocks=1, chars=94, y_norm=0.0025252525252525255, order=3, snippet="of the Virtual PC (VPC), is updated upon …  branch resolution in the execute stage…"
              - Text col 0: blocks=1, chars=34, y_norm=0.003787878787878788, order=4, snippet="and shall saturate at its limits."
    - Section 0.0.1: 4.1.5. TABLE MERGE SCENARIOS (Simulated) (pages 4-5)
      - Page 4: text_blocks=8, tables=1, figures=0
        - Dominant column: 2 (0.96 char share)
        - Table: 7x4, density=1.00, acc=99.99999999999997, area=58626.522387155375, w=461.03999999999996, h=127.16146622235681, nw=None, nh=None, aspect=None, title=INFER: PC Range | Outcome | Count | Accuracy
        - Text col 2: blocks=2, chars=279, y_norm=0.0012626262626262627, order=0, snippet="4.1.5. TABLE MERGE SCENARIOS (Simulated) … ection formatting and introduces two ta…"
        - Text col 0: blocks=2, chars=33, y_norm=0.0025252525252525255, order=1, snippet="not be merged. … Mergeable Tables:"
        - Text col 2: blocks=2, chars=322, y_norm=0.0025252525252525255, order=2, snippet="Table 4-1. BHT Prediction Outcomes (Part … 000-0x8000_00FF taken 124 91.2% 0x8000_…"
      - Page 5: text_blocks=18, tables=3, figures=0
        - Dominant column: 2 (0.94 char share)
        - Table: 7x4, density=1.00, acc=99.99999999999997, area=45568.066694940935, w=461.03999999999996, h=126.92153892759768, nw=None, nh=None, aspect=None, title=INFER: 0x8000_0600-0x8000_06FF | not-taken | 67 | 85.2%
        - Table: 5x3, density=1.00, acc=97.89541724496593, area=45688.29906089064, w=501.12, h=91.17237200848228, nw=None, nh=None, aspect=None, title=INFER: Signal | Description | Width
        - Table: 5x3, density=1.00, acc=100.00000000000001, area=58515.90630717963, w=501.12, h=90.93244471372313, nw=None, nh=None, aspect=None, title=INFER: Parameter | Value | Notes
        - Text col 2: blocks=4, chars=482, y_norm=0.0012626262626262627, order=0, snippet="4.1.5. TABLE MERGE SCENARIOS (Simulated) … 2% 0x8000_0700-0x8000_07FF taken 189 94…"
        - Text col 0: blocks=2, chars=51, y_norm=0.005050505050505051, order=1, snippet="Non-Mergeable Tables: … Table 4-2. Interface Signals"
        - Text col 2: blocks=4, chars=280, y_norm=0.005050505050505051, order=2, snippet="Paragraph for Table 4-1 (continued): Add … lock 1 rst_ni Async reset (active-low) 1"
        - Text col 0: blocks=1, chars=26, y_norm=0.007575757575757576, order=3, snippet="Table 4-3. BHT Parameters"
        - Text col 2: blocks=7, chars=403, y_norm=0.007575757575757576, order=4, snippet="vpc_i Virtual PC input CVA6Cfg.VLEN … ry distinct from interface signals abov…"

## Pipeline Step Status
- **06b_layout_sketcher**: produced section/page layout summaries (see above).
- **07_reflow_section**: completed; 3 reflowed sections (`data/results/pipeline/07_reflow_section/json_output/07_reflowed.json`).
- **08_lean4_theorem_prover**: ran with proofs (`skip_proving=False`); 20 requirements processed, 12 proved, 9 failed. Output: `data/results/pipeline/08_lean4_theorem_prover/json_output/08_theorems.json`.
- **09_section_summarizer**: summaries generated (6 sections) at `data/results/pipeline/09_section_summarizer/json_output/09_summaries.json`.
- **10_arangodb_exporter**: flattened 59 objects to `data/results/pipeline/10_arangodb_exporter/json_output/10_flattened_data.json` (sample keys: `_key`, `doc_id`, `doc_set_id`, `page_num`, `bbox`, `object_type`); confirmation at `10_export_confirmation.json`.
