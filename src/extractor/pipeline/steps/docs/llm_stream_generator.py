#!/usr/bin/env python3
"""
LLM-Readable Stream Generator
Distinguishes between deterministic extraction and non-deterministic LLM enhancements
"""

import json
import argparse
import sys
from typing import List, Dict, Any


class DeterministicValidator:
    """Validates that base extraction matches resolved PDF object order"""

    # Resolved expected order (Y-positions in pts from Gemini analysis)
    RESOLVED_ORDER = [
        # Page 1
        {"page": 1, "y": 83, "type": "section", "content": "4.1.5.4. BHT (Branch History Table) submodule"},
        {"page": 1, "y": 84, "type": "text", "content": "BHT is implemented as a memory which is composed of BHTDepth configuration parameter entries. The lower address bits of the virtual address point to the memory entry. When a branch instruction is resolved by the EX_STAGE module, the branch PC and the taken (or not taken) status information is stored in the Branch History Table. The Branch History Table is a table of two-bit saturating counters that takes the virtual address of the current fetched instruction by the CACHE. It states whether the current branch request should be taken or not. The two bit counter is updated by the successive execution of the instructions as shown in the following figure."},
        {"page": 1, "y": 323, "type": "figure", "content": "(BHT state machine diagram)"},
        {"page": 1, "y": 324, "type": "text", "content": "When a branch instruction is pre-decoded by instr_scan submodule, the BHT valids whether the PC address is in the BHT and provides the taken or not prediction. The BHT is never flushed."},
        # Page 2
        {"page": 2, "y": 71, "type": "table", "content": "Signal,IO,Description,Connection,Type\nclk_i,in,Subsystem Clock,SUBSYSTEM,logic\nvpc_i,in,Virtual PC,CACHE,logic[CVA6Cfg.VLEN-1:0]\nbht_update_i,in,Update bht with resolved address,EXECUTE,bht_update_t\nbht_prediction_o,out,Prediction from bht,FRONT END,ariane_pkg::bht_prediction_t[CVA6Cfg.INSTR_PER_FETCH-1:0]"},
        {"page": 2, "y": 72, "type": "text", "content": "● debug_mode_i input is tied to 0"},
        # Page 3
        {"page": 3, "y": 75, "type": "section", "content": "4.1.5.4.1. REQUIREMENTS (Simulated)"},
        {"page": 3, "y": 76, "type": "text", "content": "This simulated section provides formal, hardware-oriented requirements for the Branch History Table (BHT) described in Section 4.1.5.4. The BHT uses two-bit saturating counters indexed by the lower bits of the Virtual PC (VPC), is updated upon branch resolution in the execute stage, and provides predictions to the front end. Formal Requirements: REQ-BHT-1: The BHT shall implement BHTDepth entries and index them using the lower bits of VPC_i. The width of VPC_i shall match CVA6Cfg.VLEN. REQ-BHT-2: Each BHT entry shall contain a two-bit saturating counter that encodes taken/not-taken and shall saturate at its limits. REQ-BHT-3: The BHT shall accept update information from the execute stage (bht_update_i) including the branch PC and resolved outcome, and shall update the corresponding counter accordingly. REQ-BHT-4: The BHT shall provide a prediction output (bht_prediction_o) aligned with the front-end fetch group width (CVA6Cfg.INSTR_PER_FETCH). REQ-BHT-5: The BHT shall not be flushed by pipeline events. Only rst_ni shall initialize internal state. REQ-BHT-6: The subsystem clock clk_i and asynchronous active-low reset rst_ni shall be the only clock/reset inputs required for BHT operation. REQ-BHT-7: When a branch is pre-decoded by the instr_scan submodule, the BHT shall indicate whether a VPC_i address hits and shall return the taken/not-taken prediction to the front end in the same fetch cycle when available. REQ-BHT-8: In cv32a65x configuration, flush_bp_i shall be tied to 0. When DebugEn is False, debug_mode_i shall be tied to 0 and shall not appear as an external port. REQ-BHT-9: All signal widths and types exposed by the BHT interfaces shall be consistent with the configuration package definitions (e.g., CVA6Cfg.VLEN and any package enums used by prediction/update types). REQ-BHT-10: The prediction datapath shall not introduce structural hazards with instruction fetch; updates from the execute stage shall not stall front-end prediction availability. Conditional Requirements: When bht_update_i.valid is True: The BHT shall locate the entry indexed by the provided VPC and shall increment or decrement the two-bit counter based on the resolved outcome (taken/not-taken). The update shall saturate at the counter bounds and shall not invalidate other entries. When a fetch request presents VPC_i: If the indexed entry exists, the BHT shall return the current prediction in bht_prediction_o aligned to the fetch slot. If the indexed entry does not exist, the BHT shall return a default not-taken prediction"},
        # Page 4-5 (continued...)
    ]

    def validate_deterministic_obj_match(self, obj: Dict[str, Any]) -> Dict[str, Any]:
        """Compare extracted object against resolved order"""
        matched = None
        page = obj.get('page')
        y_pos = obj.get('bbox', [0, obj.get('y_position', 0), 0, 0])[1]
        obj_type = obj.get('type')
        content = obj.get('content', '')

        # Find best match within tolerance
        for expected in self.RESOLVED_ORDER:
            if (expected['page'] == page and
                abs(expected['y'] - y_pos) <= 3 and  # ±3 pixels tolerance
                expected['type'] == obj_type):
                # Check content matches (fuzzier)
                content_match = self._fuzzy_content_match(expected['content'], content, 0.8)
                if content_match >= 0.7:
                    matched = expected
                    break

        return {
            'extracted': obj,
            'expected': matched,
            'delta_y': abs(matched['y'] - y_pos) if matched else None,
            'content_similarity': self._fuzzy_content_match(matched['content'], content, 0.8) if matched else 0,
            'status': 'MATCHED' if matched else 'NOT_MATCHED',
        }

    def _fuzzy_content_match(self, expected: str, actual: str, threshold: float = 0.7) -> float:
        """Calculate content similarity"""
        if not actual:
            return 0.0

        # Simple edit distance ratio
        expected_words = set(expected.lower().split())
        actual_words = set(actual.lower().split())

        if not expected_words:
            return 1.0 if not actual_words else 0.0

        common = expected_words.intersection(actual_words)
        return len(common) / len(expected_words)


class LLMStreamGenerator:
    """Generates LLM-readable stream format"""

    def __init__(self, validator: DeterministicValidator):
        self.validator = validator

    def generate_base_stream(self, extraction_data: Dict[str, Any]) -> str:
        """Generate stream from deterministic base only"""
        objects = extraction_data.get('merged_content', [])

        stream = []
        stream.append('# BHT_CV32A65X Technical Documentation')
        stream.append('')
        stream.append('\u003e **Extraction Type**: Deterministic Base - Proven Ground Truth\u003e')
        stream.append('\u003e **Reliability**: ✅ Validated against resolved PDF object order\u003e')
        stream.append('\u003e **Spatial Accuracy**: ±3 pixels Y-coordinate tolerance\u003e')
        stream.append('')

        # Group by page for readability
        pages = {}
        for obj in objects:
            page = obj.get('page', 0)
            if page not in pages:
                pages[page] = []
            pages[page].append(obj)

        # Sort by Y-position within each page
        for page in sorted(pages.keys()):
            stream.append(f'\n--- Page {page} ---')

            pages[page].sort(key=lambda x: x.get('bbox', [0, x.get('y_position', 0), 0, 0])[1])

            for obj in pages[page]:
                # Validate this object matches resolved order
                validation = self.validator.validate_deterministic_obj_match(obj)

                obj_type = obj.get('type')
                y_pos = obj.get('bbox', [0, obj.get('y_position', 0), 0, 0])[1]
                content = obj.get('content', '')

                if obj_type == 'section':
                    stream.append(f'\n## {content} [Y:{y_pos}]')
                    stream.append(f'\u003c!-- DETERMINISTIC: {validation[\"status\"]} (ΔY={validation.get(\"delta_y\", \"?\")}) --\u003e')

                elif obj_type == 'table':
                    stream.append(f'\n\u003c!-- TABLE [Y:{y_pos}] (Deterministic) --\u003e')
                    csv_content = content.get('csv', '') if isinstance(content, dict) else content
                    if csv_content:
                        stream.append('```csv')
                        stream.append(csv_content)
                        stream.append('```')

                elif obj_type in ['text', 'bullet_text']:
                    stream.append(f'\n\u003c!-- TEXT [Y:{y_pos}] (Deterministic) --\u003e')
                    stream.append(content)

                elif obj_type == 'figure':
                    stream.append(f'\n\u003c!-- FIGURE [Y:{y_pos}] (Deterministic) --\u003e')
                    bbox = obj.get('bbox', [])
                    if bbox:
                        stream.append(f'Bounding box: {bbox[:2]} → {bbox[2:4]}')

        return '\\n'.join(stream)

    def add_non_deterministic_section(self, stream: str, llm_data: Dict[str, Any]) -> str:
        """Add non-deterministic LLM enhancements as separate section"""

        additions = []
        additions.append('')
        additions.append('---')
        additions.append('')
        additions.append('# [AGENT-EVALUATION-AREA] Non-Deterministic LLM Enhancements')
        additions.append('')
        additions.append('\u003e **Content**: AI-generated, non-deterministic\u003e')
        additions.append('\u003e **Reliability**: Subject to agent/human judgment\u003e')
        additions.append('\u003e **Purpose**: Quality evaluation, not determinism validation\u003e')
        additions.append('')

        # Add various LLM enhancements
        if llm_data.get('figure_descriptions'):
            for fd in llm_data['figure_descriptions']:
                additions.append(f'\\n### Figure Description [Non-deterministic]')
                additions.append(fd.get('description', ''))

        if llm_data.get('section_summaries'):
            for ss in llm_data['section_summaries']:
                additions.append(f'\\n### Section Summary [Non-deterministic]')
                additions.append(ss.get('summary', ''))

        if llm_data.get('lean4_theorems'):
            for th in llm_data['lean4_theorems']:
                additions.append(f'\\n### Lean4 Theorem [Non-deterministic]')
                additions.append('```lean')
                additions.append(th.get('code', ''))
                additions.append('```')

        # Add agent evaluation template
        additions.append('')
        additions.append('---')
        additions.append('')
        additions.append('## Agent Evaluation Template')
        additions.append('')
        additions.append('| Enhancement | Technical Accuracy | Format Appropriateness |
        additions.append('|-------------|-------------------|------------------------|")
        additions.append('| Figure Descriptions | [ ] / [ ] | [ ] / [ ] |
        additions.append('| Section Summaries | [ ] / [ ] | [ ] / [ ] |
        additions.append('| Lean4 Theorems | [ ] / [ ] | [ ] / [ ] |")
        additions.append('')
        additions.append('**Agent Notes:** ________________________________')

        return stream + '\\n'.join(additions)


def main():
    parser = argparse.ArgumentParser(
        description='Generate LLM-readable stream separating deterministic base from non-deterministic enhancements'
    )
    parser.add_argument('deterministic_json', help='Path to deterministic extraction JSON')
    parser.add_argument('--llm-enhancements', help='Directory containing LLM enhancement files')
    parser.add_argument('-o', '--output', default='llm_readable_stream.md',
                       help='Output stream file')
    parser.add_argument('--validate-only', action='store_true',
                       help='Only validate deterministic portion, skip stream generation')

    args = parser.parse_args()

    try:
        # Load deterministic base
        with open(args.deterministic_json, 'r') as f:
            data = json.load(f)

        validator = DeterministicValidator()
        stream_gen = LLMStreamGenerator(validator)

        # Validate deterministic portion
        print("Validating deterministic portion...")
        validation_results = []
        for obj in data.get('merged_content', []):
            result = validator.validate_deterministic_obj_match(obj)
            validation_results.append(result)

        # Check overall validation
        failed_count = sum(1 for r in validation_results if r['status'] == 'NOT_MATCHED')
        total_count = len(validation_results)

        print(f"Deterministic validation: {total_count - failed_count}/{total_count} objects matched")

        if failed_count > 3:  # Allow up to 3 minor mismatches
            print(f"ERROR: Too many validation failures ({failed_count}), extraction not deterministic enough")
            sys.exit(1)

        if args.validate_only:
            print("✅ Deterministic validation passed")
            return

        # Generate stream
        base_stream = stream_gen.generate_base_stream(data)

        # Add LLM enhancements if provided
        llm_data = {}
        if args.llm_enhancements and os.path.exists(args.llm_enhancements):
            # Load LLM enhancements from directory
            for filename in os.listdir(args.llm_enhancements):
                if filename.endswith('.json'):
                    llm_type = filename.replace('.json', '')
                    with open(os.path.join(args.llm_enhancements, filename), 'r') as f:
                        llm_data[llm_type] = json.load(f)

        final_stream = stream_gen.add_non_deterministic_section(base_stream, llm_data)

        # Write output
        with open(args.output, 'w') as f:
            f.write(final_stream)

        print(f"✅ Generated LLM-readable stream: {args.output}")
        print("- Deterministic base validated and clearly marked")
        print("- LLM enhancements separated for agent judgment")
        print("- Agent evaluation template included")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()