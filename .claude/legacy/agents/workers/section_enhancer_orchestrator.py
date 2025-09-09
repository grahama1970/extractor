#!/usr/bin/env python3
"""
Section Enhancement Orchestrator - Creates batches of sections for concurrent enhancement

This worker follows the same pattern as pdf_block_fixer_worker.py:
1. Creates batches of 10 sections each
2. Each batch contains sections with their full context
3. Sub-agents process batches using ALL available workers
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from loguru import logger

class SectionEnhancerOrchestrator:
    """Creates and manages section enhancement batches."""
    
    def __init__(self, batch_dir: str = "/tmp/section_batches"):
        self.batch_dir = Path(batch_dir)
        self.batch_dir.mkdir(exist_ok=True)
        self.batch_size = 10  # Sections per batch
        
    def create_section_batches(self, sections_file: str, max_sections_per_batch: int = 10) -> Dict[str, Any]:
        """
        Create content-aware batches with specific context for each batch type.
        
        Args:
            sections_file: Path to sections.json from Stage 6
            max_sections_per_batch: Max sections per batch (default 10)
            
        Returns:
            Dict with batch files and manifest
        """
        # Clear previous batches
        for old_file in self.batch_dir.glob("batch_*.json"):
            old_file.unlink()
            
        # Load and analyze sections
        with open(sections_file) as f:
            data = json.load(f)
            
        all_sections = data.get("sections", data) if isinstance(data, dict) else data
        
        # Analyze and categorize sections
        categorized = self._categorize_sections_by_content(all_sections)
        
        # Create content-specific batches
        batch_files = []
        batch_configs = []
        
        # Text-only sections (can handle more per batch)
        if categorized['text_only']:
            batch_file, config = self._create_text_batch(categorized['text_only'], max_sections=20)
            if batch_file:
                batch_files.append(batch_file)
                batch_configs.append(config)
        
        # Table-heavy sections (fewer per batch due to complexity)
        if categorized['table_heavy']:
            batch_file, config = self._create_table_batch(categorized['table_heavy'], max_sections=5)
            if batch_file:
                batch_files.append(batch_file)
                batch_configs.append(config)
        
        # Math sections
        if categorized['math_heavy']:
            batch_file, config = self._create_math_batch(categorized['math_heavy'], max_sections=10)
            if batch_file:
                batch_files.append(batch_file)
                batch_configs.append(config)
                
        # Form sections
        if categorized['form_sections']:
            batch_file, config = self._create_form_batch(categorized['form_sections'], max_sections=8)
            if batch_file:
                batch_files.append(batch_file)
                batch_configs.append(config)
        
        # Mixed/complex sections
        if categorized['mixed_complex']:
            batch_file, config = self._create_mixed_batch(categorized['mixed_complex'], max_sections=5)
            if batch_file:
                batch_files.append(batch_file)
                batch_configs.append(config)
            
        # Create manifest
        manifest = {
            "timestamp": datetime.now().isoformat(),
            "source_file": sections_file,
            "total_sections": len(sections),
            "batch_count": len(batch_files),
            "batch_size": max_sections_per_batch,
            "batch_files": batch_files,
            "output_pattern": str(self.batch_dir / "enhanced_batch_*.json"),
            "merge_command": f"python {__file__} merge-enhancements"
        }
        
        manifest_file = self.batch_dir / "enhancement_manifest.json"
        with open(manifest_file, 'w') as f:
            json.dump(manifest, f, indent=2)
            
        logger.info(f"Created {len(batch_files)} section batches")
        logger.info(f"Manifest: {manifest_file}")
        
        return {
            "success": True,
            "batch_count": len(batch_files),
            "total_sections": len(sections),
            "manifest": str(manifest_file),
            "batch_files": batch_files
        }
        
    def apply_enhancements_with_jq(self, original_sections_file: str, enhanced_dir: str = None) -> Dict[str, Any]:
        """
        Apply enhanced sections back to original using UUID mapping (like Stage 5.5).
        
        Args:
            original_sections_file: Original sections.json 
            enhanced_dir: Directory with enhanced_batch_*.json files
            
        Returns:
            Result with updated sections
        """
        import subprocess
        import tempfile
        
        if not enhanced_dir:
            enhanced_dir = self.batch_dir
            
        # Find all enhanced batch files
        enhanced_files = sorted(Path(enhanced_dir).glob("enhanced_batch_*.json"))
        
        if not enhanced_files:
            return {
                "success": False,
                "error": "No enhanced batch files found"
            }
            
        # Create decisions map from all enhanced batches
        decisions = {}
        
        for enhanced_file in enhanced_files:
            with open(enhanced_file) as f:
                batch_data = json.load(f)
                
            for section in batch_data.get("enhanced_sections", []):
                uuid = section.get("uuid")
                if uuid:
                    decisions[uuid] = {
                        "action": "replace",
                        "enhanced_content": section.get("enhanced_content", section.get("content")),
                        "enhancements_applied": section.get("enhancements_applied", []),
                        "confidence": section.get("confidence", 1.0),
                        "metadata": section.get("metadata", {})
                    }
                    
        # Save decisions
        decisions_file = Path(enhanced_dir) / "enhancement_decisions.json"
        with open(decisions_file, 'w') as f:
            json.dump(decisions, f, indent=2)
            
        # Apply enhancements using jq (similar to block fixer)
        output_file = Path(enhanced_dir) / "sections_enhanced.json"
        
        jq_command = """
        # Load decisions
        . as $original |
        (inputs | to_entries | map({(.key): .value}) | add) as $decisions |
        
        # Apply enhancements
        $original | {
            sections: [
                .sections[] | 
                if .uuid and ($decisions[.uuid] // null) then
                    if $decisions[.uuid].action == "replace" then
                        . + {
                            content: $decisions[.uuid].enhanced_content,
                            original_content: .content,
                            enhancements_applied: $decisions[.uuid].enhancements_applied,
                            confidence: $decisions[.uuid].confidence,
                            metadata: (.metadata + $decisions[.uuid].metadata)
                        }
                    else .
                    end
                else .
                end
            ],
            enhancement_stats: {
                total_sections: (.sections | length),
                enhanced_sections: ($decisions | length),
                timestamp: now | todate
            }
        }
        """
        
        # Write jq script
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jq', delete=False) as f:
            f.write(jq_command)
            jq_script = f.name
            
        try:
            # Run jq
            cmd = [
                "jq", "-s", "-f", jq_script,
                original_sections_file,
                str(decisions_file)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            # Save output
            with open(output_file, 'w') as f:
                f.write(result.stdout)
                
            # Count changes
            with open(original_sections_file) as f:
                original_data = json.load(f)
            with open(output_file) as f:
                enhanced_data = json.load(f)
                
            return {
                "success": True,
                "output_file": str(output_file),
                "original_sections": len(original_data.get("sections", [])),
                "enhanced_sections": len(decisions),
                "total_sections": len(enhanced_data.get("sections", []))
            }
            
        except subprocess.CalledProcessError as e:
            return {
                "success": False,
                "error": f"jq command failed: {e.stderr}"
            }
        finally:
            # Cleanup
            Path(jq_script).unlink(missing_ok=True)
    
    def _categorize_sections_by_content(self, sections: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Categorize sections by their primary content type.
        
        Args:
            sections: List of sections to categorize
            
        Returns:
            Dictionary with categorized sections
        """
        from collections import Counter
        
        categorized = {
            'text_only': [],
            'table_heavy': [],
            'math_heavy': [],
            'form_sections': [],
            'mixed_complex': []
        }
        
        for section in sections:
            blocks = section.get('blocks', [])
            if not blocks:
                categorized['text_only'].append(section)
                continue
                
            # Count block types
            block_types = Counter(b.get('block_type', 'Unknown') for b in blocks)
            total_blocks = sum(block_types.values())
            
            # Calculate ratios
            table_ratio = block_types.get('Table', 0) / total_blocks if total_blocks > 0 else 0
            math_ratio = (block_types.get('Equation', 0) + block_types.get('Math', 0)) / total_blocks if total_blocks > 0 else 0
            form_ratio = block_types.get('Form', 0) / total_blocks if total_blocks > 0 else 0
            
            # Categorize based on content distribution
            if table_ratio > 0.3:  # More than 30% tables
                categorized['table_heavy'].append(section)
            elif math_ratio > 0.2:  # More than 20% math
                categorized['math_heavy'].append(section)
            elif form_ratio > 0.1:  # Any significant form content
                categorized['form_sections'].append(section)
            elif set(block_types.keys()) <= {'Text', 'SectionHeader'}:  # Only text and headers
                categorized['text_only'].append(section)
            else:
                categorized['mixed_complex'].append(section)
                
        return categorized
    
    def _create_text_batch(self, sections: List[Dict[str, Any]]) -> Tuple[str, Dict[str, Any]]:
        """Create a batch file for text-only sections."""
        batch_id = f"text_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        batch_file = self.batch_dir / f"batch_{batch_id}.json"
        
        batch_data = {
            "batch_id": batch_id,
            "batch_type": "text_only",
            "section_count": len(sections),
            "sections": sections,
            "processing_hints": {
                "primary_tools": ["text_cleaning", "block_consolidator"],
                "skip_tools": ["camelot", "pandas", "table_tools", "math_tools"],
                "focus": "Text formatting and structure"
            }
        }
        
        with open(batch_file, 'w') as f:
            json.dump(batch_data, f, indent=2)
            
        config = {
            "batch_id": batch_id,
            "prompt_file": "section_enhancer_text_only.md",
            "max_processing_time": 300,  # 5 minutes for text batches
            "resource_allocation": 0.1  # 10% resources
        }
        
        return str(batch_file), config
    
    def _create_table_batch(self, sections: List[Dict[str, Any]]) -> Tuple[str, Dict[str, Any]]:
        """Create a batch file for table-heavy sections with rich metadata."""
        batch_id = f"table_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        batch_file = self.batch_dir / f"batch_{batch_id}.json"
        
        # Enrich sections with metadata
        enriched_sections = []
        for section in sections:
            enriched_section = self._enrich_section_metadata(section, content_type="table_heavy")
            enriched_sections.append(enriched_section)
        
        batch_data = {
            "batch_id": batch_id,
            "batch_type": "table_heavy",
            "section_count": len(enriched_sections),
            "sections": enriched_sections,
            "processing_hints": {
                "primary_tools": ["camelot", "pandas_analyzer", "table_merger", "table_header_fixer"],
                "visual_validation": True,
                "focus": "Table extraction and structure"
            }
        }
        
        with open(batch_file, 'w') as f:
            json.dump(batch_data, f, indent=2)
            
        config = {
            "batch_id": batch_id,
            "prompt_file": "section_enhancer_concise.md",  # Use concise prompt
            "max_processing_time": 900,  # 15 minutes for table batches
            "resource_allocation": 0.3  # 30% resources
        }
        
        return str(batch_file), config
    
    def _create_math_batch(self, sections: List[Dict[str, Any]]) -> Tuple[str, Dict[str, Any]]:
        """Create a batch file for math-heavy sections."""
        batch_id = f"math_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        batch_file = self.batch_dir / f"batch_{batch_id}.json"
        
        batch_data = {
            "batch_id": batch_id,
            "batch_type": "math_heavy",
            "section_count": len(sections),
            "sections": sections,
            "processing_hints": {
                "primary_tools": ["equation", "llm_equation", "llm_mathblock"],
                "templates": ["llm_equation.py", "llm_mathblock.py", "llm_inlinemath.py"],
                "focus": "Equation extraction and LaTeX conversion"
            }
        }
        
        with open(batch_file, 'w') as f:
            json.dump(batch_data, f, indent=2)
            
        config = {
            "batch_id": batch_id,
            "prompt_file": "section_enhancer_math_focused.md",
            "max_processing_time": 600,  # 10 minutes
            "resource_allocation": 0.2  # 20% resources
        }
        
        return str(batch_file), config
    
    def _create_form_batch(self, sections: List[Dict[str, Any]]) -> Tuple[str, Dict[str, Any]]:
        """Create a batch file for form sections."""
        batch_id = f"form_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        batch_file = self.batch_dir / f"batch_{batch_id}.json"
        
        batch_data = {
            "batch_id": batch_id,
            "batch_type": "form_sections",
            "section_count": len(sections),
            "sections": sections,
            "processing_hints": {
                "primary_tools": ["llm_form", "form_field_extractor"],
                "templates": ["llm_form.py"],
                "focus": "Form structure and field extraction"
            }
        }
        
        with open(batch_file, 'w') as f:
            json.dump(batch_data, f, indent=2)
            
        config = {
            "batch_id": batch_id,
            "prompt_file": "section_enhancer_form_focused.md",
            "max_processing_time": 600,
            "resource_allocation": 0.2
        }
        
        return str(batch_file), config
    
    def _create_mixed_batch(self, sections: List[Dict[str, Any]]) -> Tuple[str, Dict[str, Any]]:
        """Create a batch file for mixed/complex sections."""
        batch_id = f"mixed_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        batch_file = self.batch_dir / f"batch_{batch_id}.json"
        
        batch_data = {
            "batch_id": batch_id,
            "batch_type": "mixed_complex",
            "section_count": len(sections),
            "sections": sections,
            "processing_hints": {
                "strategy": "Analyze each section individually",
                "all_tools_available": True,
                "focus": "Dynamic tool selection based on content"
            }
        }
        
        with open(batch_file, 'w') as f:
            json.dump(batch_data, f, indent=2)
            
        config = {
            "batch_id": batch_id,
            "prompt_file": "section_enhancer_adaptive.md",
            "max_processing_time": 1200,  # 20 minutes
            "resource_allocation": 0.4  # 40% resources
        }
        
        return str(batch_file), config
    
    def _enrich_section_metadata(self, section: Dict[str, Any], content_type: str) -> Dict[str, Any]:
        """Enrich section with comprehensive metadata for self-contained processing.
        
        This metadata accumulates as previous pipeline stages execute:
        - Stage 1-3: Basic extraction adds confidence scores
        - Stage 4: Suspicious block detection adds quality metrics  
        - Stage 5: JSON creation adds structure analysis
        - Stage 6: Section organization adds relationships
        - Stage 7: Annotations are matched and added
        - Stage 8: This enrichment adds final recommendations
        """
        
        # Start with original section (already has metadata from previous stages)
        enriched = section.copy()
        
        # Aggregate existing metadata from previous stages
        existing_metadata = section.get("metadata", {})
        
        # Build comprehensive metadata
        metadata = {
            # From previous stages
            "extraction_confidence": existing_metadata.get("extraction_confidence", {}),
            "suspicious_blocks": existing_metadata.get("suspicious_blocks", []),
            "section_hierarchy": existing_metadata.get("hierarchy", {}),
            "annotation_matches": existing_metadata.get("annotations", []),
            
            # New analysis for enhancement
            "content_analysis": self._analyze_section_content(section),
            "extraction_quality": self._assess_extraction_quality(section),
            "visual_assets": self._generate_visual_assets(section),
            "knowledge_base_insights": self._search_knowledge_base(section),
            "recommended_tools": [],
            "agent_notes": {}
        }
        
        # Generate recommendations based on ALL accumulated metadata
        recommendations = self._generate_tool_recommendations(metadata, content_type)
        metadata["recommended_tools"] = recommendations
        
        # Generate agent notes incorporating all context
        metadata["agent_notes"] = self._generate_agent_notes(metadata, content_type)
        
        enriched["metadata"] = metadata
        return enriched
    
    def _analyze_section_content(self, section: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze what content types are in the section."""
        blocks = section.get("blocks", [])
        block_types = {}
        
        for block in blocks:
            block_type = block.get("block_type", "Unknown")
            block_types[block_type] = block_types.get(block_type, 0) + 1
        
        return {
            "block_types": block_types,
            "total_blocks": len(blocks),
            "has_tables": "Table" in block_types,
            "has_equations": "Equation" in block_types or "Math" in block_types,
            "has_forms": "Form" in block_types,
            "has_images": "Figure" in block_types or "Image" in block_types
        }
    
    def _assess_extraction_quality(self, section: Dict[str, Any]) -> Dict[str, Any]:
        """Assess quality of existing extractions using metadata from previous stages."""
        quality = {
            "tables": [],
            "overall_confidence": 1.0
        }
        
        # Check existing metadata from Stage 4 (suspicious block detection)
        suspicious_blocks = section.get("metadata", {}).get("suspicious_blocks", [])
        
        for i, block in enumerate(section.get("blocks", [])):
            if block.get("block_type") == "Table":
                # Use existing quality metrics if available
                existing_quality = block.get("metadata", {}).get("quality_metrics", {})
                
                table_quality = {
                    "table_id": f"t{i}",
                    "marker_confidence": existing_quality.get("confidence", block.get("confidence", 0.5)),
                    "camelot_attempted": existing_quality.get("camelot_attempted", False),
                    "camelot_confidence": existing_quality.get("camelot_confidence", None),
                    "has_borders": self._detect_table_borders(block),
                    "pandas_metrics": existing_quality.get("pandas_metrics", self._get_pandas_metrics(block))
                }
                
                # Check if this block was flagged as suspicious
                if any(s["block_id"] == block.get("block_id") for s in suspicious_blocks):
                    table_quality["is_suspicious"] = True
                    table_quality["suspicious_reasons"] = [s["reason"] for s in suspicious_blocks 
                                                          if s["block_id"] == block.get("block_id")]
                
                # Add quality issues
                issues = []
                if "Descripti" in block.get("text", "") or "|on|" in block.get("text", ""):
                    issues.append("split_headers")
                    table_quality["pandas_metrics"]["header_quality"] = "split_detected"
                
                table_quality["issues"] = issues
                quality["tables"].append(table_quality)
                quality["overall_confidence"] = min(quality["overall_confidence"], 
                                                   table_quality["marker_confidence"])
        
        return quality
    
    def _generate_tool_recommendations(self, metadata: Dict[str, Any], 
                                      content_type: str) -> List[Dict[str, Any]]:
        """Generate specific tool recommendations based on ALL metadata."""
        recommendations = []
        
        # First, check if annotations already tell us what to do
        for annotation in metadata.get("annotation_matches", []):
            if "merge table" in annotation.get("content", "").lower():
                recommendations.append({
                    "tool": "table_merger_worker",
                    "reason": f"Annotation requests: {annotation['content']}",
                    "command": "python table_merger_worker.py analyze section.json",
                    "priority": "high",
                    "source": "human_annotation"
                })
        
        # Check table quality
        for table in metadata["extraction_quality"].get("tables", []):
            # If Camelot wasn't tried yet and quality is low
            if (table["marker_confidence"] < 0.7 and 
                not table.get("camelot_attempted") and 
                table["has_borders"]):
                recommendations.append({
                    "tool": "camelot_extractor",
                    "reason": f"marker_confidence {table['marker_confidence']:.2f} < 0.7, has_borders=true",
                    "command": f"python camelot_extractor.py extract-tables doc.pdf --page N --lattice --line-width 15",
                    "priority": "high",
                    "expected_improvement": f"{table['marker_confidence']:.2f} → 0.85+"
                })
            
            # If marked suspicious in Stage 4
            if table.get("is_suspicious"):
                recommendations.append({
                    "tool": "visual_validator",
                    "reason": f"Stage 4 flagged as suspicious: {', '.join(table['suspicious_reasons'])}",
                    "command": f"python visual_validator.py check {table['table_id']}",
                    "priority": "high"
                })
            
            if "split_headers" in table.get("issues", []):
                recommendations.append({
                    "tool": "table_header_fixer",
                    "reason": "Split headers detected in table",
                    "command": f"python table_header_fixer.py fix-headers {table['table_id']}.json",
                    "priority": "medium"
                })
        
        # Check for equations based on accumulated metadata
        if metadata["content_analysis"]["has_equations"]:
            recommendations.append({
                "tool": "pdf_snapshot",
                "reason": "Equation blocks present without LaTeX",
                "command": "python pdf_snapshot.py doc.pdf --page N --bbox EQUATION_BBOX -o equation.png",
                "priority": "low"
            })
        
        return recommendations
    
    def _generate_agent_notes(self, metadata: Dict[str, Any], content_type: str) -> Dict[str, Any]:
        """Generate helpful notes incorporating ALL pipeline context."""
        notes = {
            "summary": "",
            "key_observations": [],
            "recommended_approach": {},
            "gotchas": [],
            "expected_outcome": {},
            "pipeline_context": {}
        }
        
        # Add context from previous stages
        notes["pipeline_context"] = {
            "stage_4_suspicious": len(metadata.get("suspicious_blocks", [])),
            "stage_7_annotations": len(metadata.get("annotation_matches", [])),
            "extraction_attempts": sum(1 for t in metadata["extraction_quality"].get("tables", []) 
                                     if t.get("camelot_attempted", False))
        }
        
        # Summarize main issues
        issues = []
        if metadata["extraction_quality"]["overall_confidence"] < 0.8:
            issues.append(f"Low extraction confidence ({metadata['extraction_quality']['overall_confidence']:.2f})")
        
        if metadata.get("suspicious_blocks"):
            issues.append(f"{len(metadata['suspicious_blocks'])} suspicious blocks from Stage 4")
            
        if metadata.get("annotation_matches"):
            issues.append(f"{len(metadata['annotation_matches'])} human annotations to address")
        
        for table in metadata["extraction_quality"].get("tables", []):
            if table.get("issues"):
                issues.append(f"Table {table['table_id']} has: {', '.join(table['issues'])}")
        
        notes["summary"] = ". ".join(issues) if issues else "Section appears well-extracted"
        
        # Add specific observations based on accumulated knowledge
        if metadata.get("annotation_matches"):
            notes["key_observations"].append("Human annotations available - these take priority")
            
        if any(t.get("camelot_attempted") for t in metadata["extraction_quality"].get("tables", [])):
            notes["key_observations"].append("Camelot already attempted in previous stages")
        
        if content_type == "table_heavy":
            notes["key_observations"].append("Multiple tables detected - check for continuations")
            if any(t["has_borders"] for t in metadata["extraction_quality"].get("tables", [])):
                notes["key_observations"].append("Tables have borders - Camelot should work well")
        
        # Add insights from knowledge base
        if metadata.get("knowledge_base_insights", {}).get("similar_sections"):
            best_match = metadata["knowledge_base_insights"]["similar_sections"][0]
            notes["recommended_approach"]["historical"] = (
                f"Similar case solved with: {best_match['solution']} "
                f"(improved {best_match['outcome']})"
            )
        
        # Complexity assessment based on ALL factors
        complexity = "low"
        factors = 0
        
        if len(metadata["recommended_tools"]) > 2:
            factors += 1
        if metadata["extraction_quality"]["overall_confidence"] < 0.7:
            factors += 1
        if metadata.get("suspicious_blocks"):
            factors += 1
        if not metadata.get("annotation_matches"):  # No human guidance
            factors += 1
            
        if factors >= 3:
            complexity = "high"
        elif factors >= 1:
            complexity = "medium"
            
        notes["complexity"] = complexity
        notes["expected_outcome"] = {
            "time_estimate": {"low": "30s", "medium": "2min", "high": "5min"}[complexity],
            "confidence_improvement": "Significant" if complexity != "low" else "Minor"
        }
        
        return notes
    
    def _detect_table_borders(self, table_block: Dict[str, Any]) -> bool:
        """Simple heuristic to detect if table has borders."""
        # Check existing metadata first
        if table_block.get("metadata", {}).get("has_borders") is not None:
            return table_block["metadata"]["has_borders"]
            
        # Fallback to text analysis
        text = table_block.get("text", "")
        # Tables with | characters likely have borders
        return "|" in text
    
    def _get_pandas_metrics(self, table_block: Dict[str, Any]) -> Dict[str, Any]:
        """Get pandas-style metrics for table (simplified)."""
        # In real implementation, would actually parse table
        text = table_block.get("text", "")
        lines = text.split("\n")
        
        return {
            "shape": [len(lines), len(lines[0].split("|")) if lines else 0],
            "has_headers": len(lines) > 1,
            "null_percentage": 0.0  # Simplified
        }
    
    def _generate_visual_assets(self, section: Dict[str, Any]) -> Dict[str, Any]:
        """Generate paths to visual assets (in real implementation, would create them)."""
        section_id = section.get("section_id", "unknown")
        
        # Check if assets already exist from previous stages
        existing_assets = section.get("metadata", {}).get("visual_assets", {})
        
        return {
            "section_image": existing_assets.get("section_image", f"/tmp/sections/{section_id}_full.png"),
            "table_images": existing_assets.get("table_images", 
                                              [f"/tmp/sections/{section_id}_table_{i}.png" 
                                               for i in range(len([b for b in section.get("blocks", []) 
                                                                 if b.get("block_type") == "Table"]))]),
            "equation_snapshots": existing_assets.get("equation_snapshots", [])
        }
    
    def _find_relevant_annotations(self, section: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find annotations relevant to this section."""
        # Use annotations already matched in Stage 7
        return section.get("metadata", {}).get("annotation_matches", [])
    
    def _search_knowledge_base(self, section: Dict[str, Any]) -> Dict[str, Any]:
        """Search knowledge base for similar sections and solutions."""
        # In real implementation, would query ArangoDB
        # This would include results from all previous successful enhancements
        return {
            "similar_sections": [
                {
                    "similarity_score": 0.89,
                    "problem": "Table with split headers in technical spec",
                    "solution": "Camelot with lattice mode",
                    "outcome": "0.65 → 0.91 confidence",
                    "document": "Similar PDF from 2 weeks ago"
                }
            ],
            "learned_patterns": [
                {
                    "pattern": "Tables with borders + low confidence → use Camelot",
                    "success_rate": 0.92,
                    "occurrences": 47
                }
            ],
            "previous_attempts": section.get("metadata", {}).get("enhancement_attempts", [])
        }


def working_usage():
    """Demonstrate section enhancement orchestration."""
    orchestrator = SectionEnhancerOrchestrator()
    
    # Example sections file
    sections = {
        "sections": [
            {"id": "s1", "type": "text", "content": "Introduction paragraph"},
            {"id": "s2", "type": "table", "content": "Financial data table"},
            {"id": "s3", "type": "equation", "content": "E = mc^2"},
            {"id": "s4", "type": "code", "content": "def hello(): print('world')"},
            {"id": "s5", "type": "text", "content": "Conclusion paragraph"}
        ]
    }
    
    # Save test file
    test_file = "/tmp/test_sections.json"
    with open(test_file, 'w') as f:
        json.dump(sections, f)
        
    # Split sections
    result = orchestrator.split_sections_by_type(test_file)
    
    print(f"✓ Created manifest: {result['manifest']}")
    print(f"✓ Sub-agent tasks: {len(result['sub_agent_tasks'])}")
    
    # Show tasks
    print("\nConcurrent tasks to spawn:")
    for task in result['sub_agent_tasks']:
        print(f"  - {task['agent']} → {task['section_count']} {task['section_type']} sections")
        
    return True


def debug_function():
    """Test edge cases and error handling."""
    orchestrator = SectionEnhancerOrchestrator("/tmp/debug_enhancement")
    
    # Test with mixed/unknown types
    sections = {
        "sections": [
            {"id": "s1", "type": "text", "content": "Text"},
            {"id": "s2", "type": "unknown", "content": "Mystery"},
            {"id": "s3", "type": "figure", "content": "Image"},
            {"id": "s4", "type": "table", "content": "Data"},
            {"id": "s5"},  # No type
        ]
    }
    
    test_file = "/tmp/debug_sections.json"
    with open(test_file, 'w') as f:
        json.dump(sections, f)
        
    result = orchestrator.split_sections_by_type(test_file)
    
    print(f"Debug result: {json.dumps(result, indent=2)}")
    
    # Test merge
    enhanced_files = [
        "/tmp/debug_enhancement/enhanced_text.json",
        "/tmp/debug_enhancement/enhanced_table.json"
    ]
    
    # Create fake enhanced files
    for file in enhanced_files:
        Path(file).parent.mkdir(exist_ok=True)
        with open(file, 'w') as f:
            json.dump({"sections": [{"enhanced": True}], "type": "test"}, f)
            
    merge_result = orchestrator.merge_enhanced_sections(enhanced_files, "/tmp/merged.json")
    print(f"Merge result: {merge_result}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python section_enhancer_orchestrator.py create-batches <sections.json>")
        print("  python section_enhancer_orchestrator.py apply-enhancements <original_sections.json>")
        print("  python section_enhancer_orchestrator.py working  # Demo mode")
        print("  python section_enhancer_orchestrator.py debug    # Debug mode")
        sys.exit(1)
        
    command = sys.argv[1]
    
    if command == "create-batches":
        if len(sys.argv) < 3:
            print("Error: Missing sections.json file")
            sys.exit(1)
            
        orchestrator = SectionEnhancerOrchestrator()
        result = orchestrator.create_section_batches(sys.argv[2])
        
        if result["success"]:
            print(f"✓ Created {result['batch_count']} batches for {result['total_sections']} sections")
            print(f"✓ Manifest: {result['manifest']}")
            print("\nNext step: Spawn concurrent sub-agents using section_enhancer_prompt.md on each batch:")
            for i, batch_file in enumerate(result['batch_files'][:3]):
                print(f"  - Batch {i}: {batch_file}")
            if len(result['batch_files']) > 3:
                print(f"  ... and {len(result['batch_files']) - 3} more batches")
        else:
            print(f"✗ Failed to create batches")
            
    elif command == "apply-enhancements":
        if len(sys.argv) < 3:
            print("Error: Missing original sections.json file")
            print("Usage: python section_enhancer_orchestrator.py apply-enhancements <original_sections.json>")
            sys.exit(1)
            
        orchestrator = SectionEnhancerOrchestrator()
        result = orchestrator.apply_enhancements_with_jq(sys.argv[2])
        
        if result["success"]:
            print(f"✓ Applied enhancements successfully")
            print(f"  Original sections: {result['original_sections']}")
            print(f"  Enhanced sections: {result['enhanced_sections']}")  
            print(f"  Output: {result['output_file']}")
        else:
            print(f"✗ Failed: {result.get('error', 'Unknown error')}")
            
    elif command == "debug":
        print("Running debug mode...")
        debug_function()
    else:
        print("Running working usage mode...")
        working_usage()