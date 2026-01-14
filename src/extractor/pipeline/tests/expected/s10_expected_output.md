# Full Document Export

## 4.1.5.4. BHT (Branch History Table) submodule (ID: section_0)

BHT is implemented as a memory which is composed of BHTDepth configuration parameter entries. The lower address bits of the virtual address point to the memory entry. When a branch instruction is resolved by the EX_STAGE module, the branch PC and the taken (or not taken) status information is stored in the Branch History Table. The Branch History Table is a table of two-bit saturating counters that takes the virtual address of the current fetched instruction by the CACHE. It states whether the current branch request should be taken or not. The two bit counter is updated by the successive execution of the instructions as shown in the following figure.

### Figure

![Figure](pipeline/06_figure_extractor/visual_output/figure_001.png)

When a branch instruction is pre-decoded by instr_scan submodule, the BHT valids whether the PC address is in the BHT and provides the taken or not prediction. The BHT is never flushed.

### INFER: Signal | IO | Description | Connection | Type

| 0                | 1   | 2                                | 3          | 4                                                          |
| :--------------- | :-- | :------------------------------- | :--------- | :--------------------------------------------------------- |
| Signal           | IO  | Description                      | Connection | Type                                                       |
| clk_i            | in  | Subsystem Clock                  | SUBSYSTEM  | logic                                                      |
| vpc_i            | in  | Virtual PC                       | CACHE      | logic[CVA6Cfg.VLEN-1:0]                                    |
| bht_update_i     | in  | Update bht with resolved address | EXECUTE    | bht_update_t                                               |
| bht_prediction_o | out | Prediction from bht              | FRONT END  | ariane_pkg::bht_prediction_t[CVA6Cfg.IN STR_PER_FETCH-1:0] |

Due to cv32a65x configuration, some ports are tied to a static value. These ports do not appear in the above table, they are listed below For any HW configuration,

As DebugEn = False, ● debug_mode_i input is tied to 0

## 4.1.5.4.1. REQUIREMENTS (Simulated) (ID: section_1)

This simulated section provides formal, hardware-oriented requirements for the Branch History Table
(BHT) described in Section 4.1.5.4. The BHT uses two-bit saturating counters indexed by the lower bits of the Virtual PC (VPC), is updated upon branch resolution in the execute stage, and provides predictions to the front end.

Formal Requirements:

REQ-BHT-1: The BHT shall implement BHTDepth entries and index them using the lower bits of VPC_i. The width of VPC_i shall match CVA6Cfg.VLEN.

REQ-BHT-2: Each BHT entry shall contain a two-bit saturating counter that encodes taken/not-taken and shall saturate at its limits.

REQ-BHT-3: The BHT shall accept update information from the execute stage (bht_update_i)
including the branch PC and resolved outcome, and shall update the corresponding counter accordingly.

REQ-BHT-4: The BHT shall provide a prediction output (bht_prediction_o) aligned with the front-end fetch group width (CVA6Cfg.INSTR_PER_FETCH).

REQ-BHT-5: The BHT shall not be flushed by pipeline events. Only rst_ni shall initialize internal state.

REQ-BHT-6: The subsystem clock clk_i and asynchronous active-low reset rst_ni shall be the only clock/reset inputs required for BHT operation.

REQ-BHT-7: When a branch is pre-decoded by the instr_scan submodule, the BHT shall indicate
whether a VPC_i address hits and shall return the taken/not-taken prediction to the front end in the same fetch cycle when available.

REQ-BHT-8: In cv32a65x configuration, flush_bp_i shall be tied to 0. When DebugEn is False, debug_mode_i shall be tied to 0 and shall not appear as an external port.

REQ-BHT-9: All signal widths and types exposed by the BHT interfaces shall be consistent with the configuration package definitions (e.g., CVA6Cfg.VLEN and any package enums used by prediction/update types).

REQ-BHT-10: The prediction datapath shall not introduce structural hazards with instruction fetch; updates from the execute stage shall not stall front-end prediction availability.

Conditional Requirements:

When bht_update_i.valid is True: The BHT shall locate the entry indexed by the provided VPC and shall increment or decrement the two-bit counter based on the resolved outcome (taken/not-taken). The update shall saturate at the counter bounds and shall not invalidate other entries.

When a fetch request presents VPC_i: If the indexed entry exists, the BHT shall return the current prediction in bht_prediction_o aligned to the fetch slot. If the indexed entry does not exist, the BHT shall return a default not-taken prediction.

### Requirement Proof Summary

| ID                    | Type     | Status      | Theorem           |
| :-------------------- | :------- | :---------- | :---------------- |
| **REQ-4.1.5.4.1-001** | PHYSICAL | ✅ Verified | `bht_depth_eq`    |
| **REQ-4.1.5.4.1-002** | PHYSICAL | ✅ Verified | `bht_sat_cnt`     |
| **REQ-4.1.5.4.1-003** | FUNCTION | ✅ Verified | `bht_update`      |
| **REQ-4.1.5.4.1-004** | FUNCTION | ✅ Verified | `bht_prediction`  |
| **REQ-4.1.5.4.1-005** | FUNCTION | ✅ Verified | `bht_flush`       |
| **REQ-4.1.5.4.1-006** | PHYSICAL | ✅ Verified | `bht_clock`       |
| **REQ-4.1.5.4.1-007** | FUNCTION | ✅ Verified | `bht_lookup`      |
| **REQ-4.1.5.4.1-008** | PHYSICAL | ✅ Verified | `bht_debug`       |
| **REQ-4.1.5.4.1-009** | PHYSICAL | ✅ Verified | `bht_signals`     |
| **REQ-4.1.5.4.1-010** | FUNCTION | ✅ Verified | `bht_hazards`     |
| **REQ-4.1.5.4.1-011** | FUNCTION | ✅ Verified | `bht_cond_update` |
| **REQ-4.1.5.4.1-012** | FUNCTION | ✅ Verified | `bht_cond_lookup` |

> **[REQ-4.1.5.4.1-001] [PHYSICAL]** The BHT shall implement BHTDepth entries and index them using the lower bits of VPC*i. The width of VPC_i shall match CVA6Cfg.VLEN.
> \_Source: "REQ-BHT-1: The BHT shall implement BHTDepth entries and index them using the lower bits of VPC_i. The width of VPC_i shall match CVA6Cfg.VLEN."*
>
> | Proof Status | Strategy              | Details                           |
> | :----------- | :-------------------- | :-------------------------------- |
> | ✅ Verified  | scillm-certainly-iter | `Theorem: ` <br> `Msg: Verified.` |

> **[REQ-4.1.5.4.1-002] [PHYSICAL]** Each BHT entry shall contain a two-bit saturating counter that encodes taken/not-taken and shall saturate at its limits.
> _Source: "REQ-BHT-2: Each BHT entry shall contain a two-bit saturating counter that encodes taken/not-taken and shall saturate at its limits."_
>
> | Proof Status | Strategy              | Details                           |
> | :----------- | :-------------------- | :-------------------------------- |
> | ✅ Verified  | scillm-certainly-iter | `Theorem: ` <br> `Msg: Verified.` |

> **[REQ-4.1.5.4.1-003] [FUNCTION]** The BHT shall accept update information from the execute stage (bht*update_i) including the branch PC and resolved outcome, and shall update the corresponding counter accordingly.
> \_Source: "REQ-BHT-3: The BHT shall accept update information from the execute stage (bht_update_i) including the branch PC and resolved outcome, and shall update the corresponding counter accordingly."*
>
> | Proof Status | Strategy              | Details                           |
> | :----------- | :-------------------- | :-------------------------------- |
> | ✅ Verified  | scillm-certainly-iter | `Theorem: ` <br> `Msg: Verified.` |

> **[REQ-4.1.5.4.1-004] [FUNCTION]** The BHT shall provide a prediction output (bht*prediction_o) aligned with the front-end fetch group width (CVA6Cfg.INSTR_PER_FETCH).
> \_Source: "REQ-BHT-4: The BHT shall provide a prediction output (bht_prediction_o) aligned with the front-end fetch group width (CVA6Cfg.INSTR_PER_FETCH)."*
>
> | Proof Status | Strategy              | Details                           |
> | :----------- | :-------------------- | :-------------------------------- |
> | ✅ Verified  | scillm-certainly-iter | `Theorem: ` <br> `Msg: Verified.` |

> **[REQ-4.1.5.4.1-005] [FUNCTION]** The BHT shall not be flushed by pipeline events. Only rst*ni shall initialize internal state.
> \_Source: "REQ-BHT-5: The BHT shall not be flushed by pipeline events. Only rst_ni shall initialize internal state."*
>
> | Proof Status | Strategy              | Details                           |
> | :----------- | :-------------------- | :-------------------------------- |
> | ✅ Verified  | scillm-certainly-iter | `Theorem: ` <br> `Msg: Verified.` |

> **[REQ-4.1.5.4.1-006] [PHYSICAL]** The subsystem clock clk*i and asynchronous active-low reset rst_ni shall be the only clock/reset inputs required for BHT operation.
> \_Source: "REQ-BHT-6: The subsystem clock clk_i and asynchronous active-low reset rst_ni shall be the only clock/reset inputs required for BHT operation."*
>
> | Proof Status | Strategy              | Details                           |
> | :----------- | :-------------------- | :-------------------------------- |
> | ✅ Verified  | scillm-certainly-iter | `Theorem: ` <br> `Msg: Verified.` |

> **[REQ-4.1.5.4.1-007] [FUNCTION]** When a branch is pre-decoded by the instr*scan submodule, the BHT shall indicate whether a VPC_i address hits and shall return the taken/not-taken prediction to the front end in the same fetch cycle when available.
> \_Source: "REQ-BHT-7: When a branch is pre-decoded by the instr_scan submodule, the BHT shall indicate whether a VPC_i address hits and shall return the taken/not-taken prediction to the front end in the same fetch cycle when available."*
>
> | Proof Status | Strategy              | Details                           |
> | :----------- | :-------------------- | :-------------------------------- |
> | ✅ Verified  | scillm-certainly-iter | `Theorem: ` <br> `Msg: Verified.` |

> **[REQ-4.1.5.4.1-008] [PHYSICAL]** In cv32a65x configuration, flush*bp_i shall be tied to 0. When DebugEn is False, debug_mode_i shall be tied to 0 and shall not appear as an external port.
> \_Source: "REQ-BHT-8: In cv32a65x configuration, flush_bp_i shall be tied to 0. When DebugEn is False, debug_mode_i shall be tied to 0 and shall not appear as an external port."*
>
> | Proof Status | Strategy              | Details                           |
> | :----------- | :-------------------- | :-------------------------------- |
> | ✅ Verified  | scillm-certainly-iter | `Theorem: ` <br> `Msg: Verified.` |

> **[REQ-4.1.5.4.1-009] [PHYSICAL]** All signal widths and types exposed by the BHT interfaces shall be consistent with the configuration package definitions (e.g., CVA6Cfg.VLEN and any package enums used by prediction/update types).
> _Source: "REQ-BHT-9: All signal widths and types exposed by the BHT interfaces shall be consistent with the configuration package definitions (e.g., CVA6Cfg.VLEN and any package enums used by prediction/update types)."_
>
> | Proof Status | Strategy              | Details                           |
> | :----------- | :-------------------- | :-------------------------------- |
> | ✅ Verified  | scillm-certainly-iter | `Theorem: ` <br> `Msg: Verified.` |

> **[REQ-4.1.5.4.1-010] [FUNCTION]** The prediction datapath shall not introduce structural hazards with instruction fetch; updates from the execute stage shall not stall front-end prediction availability.
> _Source: "REQ-BHT-10: The prediction datapath shall not introduce structural hazards with instruction fetch; updates from the execute stage shall not stall front-end prediction availability."_
>
> | Proof Status | Strategy              | Details                           |
> | :----------- | :-------------------- | :-------------------------------- |
> | ✅ Verified  | scillm-certainly-iter | `Theorem: ` <br> `Msg: Verified.` |

> **[REQ-4.1.5.4.1-011] [FUNCTION]** When bht*update_i.valid is True: The BHT shall locate the entry indexed by the provided VPC and shall increment or decrement the two-bit counter based on the resolved outcome (taken/not-taken). The update shall saturate at the counter bounds and shall not invalidate other entries.
> \_Source: "Conditional Requirements: When bht_update_i.valid is True: The BHT shall locate the entry indexed by the provided VPC and shall increment or decrement the two-bit counter based on the resolved outcome (taken/not-taken). The update shall saturate at the counter bounds and shall not invalidate other entries."*
>
> | Proof Status | Strategy              | Details                           |
> | :----------- | :-------------------- | :-------------------------------- |
> | ✅ Verified  | scillm-certainly-iter | `Theorem: ` <br> `Msg: Verified.` |

> **[REQ-4.1.5.4.1-012] [FUNCTION]** When a fetch request presents VPC*i: If the indexed entry exists, the BHT shall return the current prediction in bht_prediction_o aligned to the fetch slot. If the indexed entry does not exist, the BHT shall return a default not-taken prediction.
> \_Source: "When a fetch request presents VPC_i: If the indexed entry exists, the BHT shall return the current prediction in bht_prediction_o aligned to the fetch slot. If the indexed entry does not exist, the BHT shall return a default not-taken prediction"*
>
> | Proof Status | Strategy              | Details                           |
> | :----------- | :-------------------- | :-------------------------------- |
> | ✅ Verified  | scillm-certainly-iter | `Theorem: ` <br> `Msg: Verified.` |

## 4.1.5. TABLE MERGE SCENARIOS (Simulated) (ID: section_2)

> **[REQ-4.1.5-001] [FUNCTION]** Table-merge logic shall merge a logically single table that is split across pages.
> _Source: "This simulated section mirrors the BHT section formatting and introduces two table scenarios to exercise table-merge
> logic: (1) a logically single table split across pages that should be merged;"_
>
> | Proof Status | Strategy              | Details                           |
> | :----------- | :-------------------- | :-------------------------------- |
> | ✅ Verified  | scillm-certainly-iter | `Theorem: ` <br> `Msg: Verified.` |

Table 4-1. BHT Prediction Outcomes (Part 1)

### INFER: PC Range | Outcome | Count | Accuracy

| 0                       | 1         | 2     | 3        |
| :---------------------- | :-------- | :---- | :------- |
| PC Range                | Outcome   | Count | Accuracy |
| 0x8000_0000-0x8000_00FF | taken     | 124   | 91.2%    |
| 0x8000_0100-0x8000_01FF | not-taken | 98    | 88.4%    |
| 0x8000_0200-0x8000_02FF | taken     | 206   | 93.7%    |
| 0x8000_0300-0x8000_03FF | taken     | 151   | 89.6%    |
| 0x8000_0400-0x8000_04FF | not-taken | 74    | 86.1%    |
| 0x8000_0500-0x8000_05FF | taken     | 132   | 92.0%    |
| 0x8000_0600-0x8000_06FF | not-taken | 67    | 85.2%    |
| 0x8000_0700-0x8000_07FF | taken     | 189   | 94.1%    |
| 0x8000_0800-0x8000_08FF | taken     | 203   | 92.7%    |
| 0x8000_0900-0x8000_09FF | not-taken | 81    | 87.5%    |
| 0x8000_0A00-0x8000_0AFF | taken     | 117   | 90.6%    |
| 0x8000_0B00-0x8000_0BFF | taken     | 176   | 91.4%    |
| 0x8000_0C00-0x8000_0CFF | not-taken | 72    | 84.9%    |

Paragraph for Table 4-1: This table summarizes a subset of BHT prediction statistics. The continuation appears on the next page and should be merged with this part.

Continuation of Table 4-1: The rows below are part of the same dataset and should be merged. Table 4-1. BHT Prediction Outcomes (Continued)

Non-Mergeable Tables: Table 4-2 and Table 4-3 are distinct datasets and shall not be merged. Each is preceded by its own paragraph. Table 4-2. Interface Signals

### INFER: Signal | Description | Width

| 0                | 1                        | 2                       |
| :--------------- | :----------------------- | :---------------------- |
| Signal           | Description              | Width                   |
| clk_i            | Subsystem clock          | 1                       |
| rst_ni           | Async reset (active-low) | 1                       |
| vpc_i            | Virtual PC input         | CVA6Cfg.VLEN            |
| bht_prediction_o | Prediction vector        | CVA6Cfg.INSTR_PER_FETCH |

Paragraph for Table 4-2: Interface-level information unrelated to Table 4-3. Table 4-3. BHT Parameters

### INFER: Parameter | Value | Notes

| 0                 | 1                | 2            |
| :---------------- | :--------------- | :----------- |
| Parameter         | Value            | Notes        |
| BHTDepth          | 1024             | Configurable |
| CounterType       | 2-bit saturating | Standard     |
| DefaultPrediction | not-taken        | On miss      |
| FlushPolicy       | none             | Per spec     |

Paragraph for Table 4-3: Parameter summary distinct from interface signals above.
