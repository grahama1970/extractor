#!/usr/bin/env python3
"""
Report Generator Utility - Generates analysis reports from pipeline execution results.

This utility creates detailed markdown reports to prevent agent hallucinations by
providing concrete execution data and analysis.
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional


def generate_pipeline_report(summary_path: Path, output_dir: Path) -> Path:
    """
    Generate a detailed analysis report from pipeline execution summary.
    
    Args:
        summary_path: Path to pipeline_summary.json
        output_dir: Directory to save reports
        
    Returns:
        Path to generated report
    """
    # Load pipeline summary
    with open(summary_path, 'r') as f:
        pipeline_data = json.load(f)
    
    # Create reports directory
    reports_dir = output_dir / "reports"
    reports_dir.mkdir(exist_ok=True)
    
    # Generate report filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_name = f"pipeline_analysis_{timestamp}.md"
    report_path = reports_dir / report_name
    
    # Generate report content
    report_content = _generate_report_content(pipeline_data, output_dir)
    
    # Write report
    with open(report_path, 'w') as f:
        f.write(report_content)
    
    # Update latest symlink
    latest_link = reports_dir / "latest.md"
    if latest_link.exists():
        latest_link.unlink()
    latest_link.symlink_to(report_name)
    
    print(f"✅ Pipeline analysis report generated: {report_path}")
    print(f"📊 Report contains actual execution data to prevent hallucinations")
    print(f"🔗 Latest report available at: {latest_link}")
    
    return report_path


def _generate_report_content(pipeline_data: Dict[str, Any], output_dir: Path) -> str:
    """Generate the markdown report content."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Extract key metrics
    total_processors = pipeline_data['processors']['total']
    successful = pipeline_data['processors']['successful']
    failed = pipeline_data['processors']['failed']
    duration = pipeline_data['total_duration']
    
    # Start report
    report = f"""# Pipeline Execution Report - {timestamp}

**THIS REPORT CONTAINS ACTUAL EXECUTION DATA TO PREVENT AGENT HALLUCINATIONS**

## Executive Summary

- **Status**: {pipeline_data['pipeline_status'].upper()}
- **Duration**: {duration:.2f} seconds
- **Success Rate**: {successful}/{total_processors} processors
- **PDF Processed**: {pipeline_data['pdf_path']}

## Execution Facts (ACTUAL RESULTS)

### Processor Results

"""
    
    # Add processor results
    for proc_name, result in pipeline_data['results'].items():
        status = "✅ SUCCESS" if result['success'] else "❌ FAILED"
        report += f"**{proc_name}**: {status} ({result['duration']:.3f}s)\n"
        if result.get('error'):
            report += f"  Error: {result['error']}\n"
        report += "\n"
    
    # Add annotation learning details if available
    if 'annotation_learner' in pipeline_data['results'] and pipeline_data['results']['annotation_learner']['success']:
        report += _add_annotation_learning_section(output_dir)
    
    # Add extraction details
    report += _add_extraction_details(pipeline_data)
    
    # Add actionable recommendations
    report += "\n## Actionable Recommendations\n\n"
    recommendations = _generate_recommendations(pipeline_data)
    for i, rec in enumerate(recommendations, 1):
        report += f"{i}. {rec}\n\n"
    
    # Add debugging information
    report += """## DEBUGGING INFORMATION (PREVENT HALLUCINATIONS)

This section contains ACTUAL execution data to prevent false assumptions:

### Actual Execution Timeline
```
"""
    
    # Add execution log
    for log_entry in pipeline_data['execution_log']:
        if log_entry['status'] in ['started', 'completed', 'failed']:
            report += f"{log_entry['timestamp']} | {log_entry['step']} | {log_entry['status']} | {log_entry['details']}\n"
    
    report += "```\n\n"
    
    # Add output files information
    report += "### Files Actually Created\n"
    output_files = pipeline_data.get('output_files', [])
    report += f"Output files generated: {len(output_files)}\n\n"
    
    for file_path in output_files:
        if Path(file_path).exists():
            size = Path(file_path).stat().st_size
            report += f"- {file_path} ({size} bytes)\n"
    
    # Add raw data section
    report += "\n## Raw Data (JSON)\n\n"
    report += "### Pipeline Summary\n```json\n"
    report += json.dumps(pipeline_data, indent=2)
    report += "\n```\n"
    
    # Add learned rules if available
    learned_rules_path = Path("tmp/learned_rules.json")
    if learned_rules_path.exists():
        report += "\n### Learned Rules\n```json\n"
        with open(learned_rules_path, 'r') as f:
            rules_data = json.load(f)
        report += json.dumps(rules_data, indent=2)
        report += "\n```\n"
    
    return report


def _add_annotation_learning_section(output_dir: Path) -> str:
    """Add annotation learning results section."""
    section = "\n### Annotation Learning Results\n\n"
    
    # Try to load learned rules
    learned_rules_path = Path("tmp/learned_rules.json")
    if learned_rules_path.exists():
        with open(learned_rules_path, 'r') as f:
            rules_data = json.load(f)
        
        stats = rules_data.get('learning_stats', {})
        rules = rules_data.get('rules', [])
        
        section += f"- **Rules Created**: {len(rules)}\n"
        section += f"- **Annotations Processed**: {stats.get('annotations_processed', 0)}\n"
        section += f"- **PDFs Analyzed**: {stats.get('pdfs_analyzed', 0)}\n\n"
        
        # Count rule types
        rule_types = {}
        for rule in rules:
            rule_type = rule.get('rule_type', 'unknown')
            rule_types[rule_type] = rule_types.get(rule_type, 0) + 1
        
        if rule_types:
            section += "**Rule Types Created:**\n"
            for rule_type, count in rule_types.items():
                section += f"- {rule_type}: {count} rules\n"
    
    return section


def _add_extraction_details(pipeline_data: Dict[str, Any]) -> str:
    """Add extraction details section."""
    section = "\n### Extraction Details\n\n"
    
    # Check marker extraction results
    marker_result = pipeline_data['results'].get('marker_extractor', {})
    if marker_result.get('success'):
        # Extract block count from execution log
        for log_entry in pipeline_data['execution_log']:
            if log_entry['step'] == 'Marker Extraction' and 'Extracted' in log_entry['details']:
                section += f"- **Blocks Extracted**: {log_entry['details']}\n"
                break
    
    # Check hierarchy builder results
    hierarchy_result = pipeline_data['results'].get('hierarchy_builder', {})
    if hierarchy_result.get('success'):
        for log_entry in pipeline_data['execution_log']:
            if log_entry['step'] == 'Hierarchy Builder' and 'Built hierarchy' in log_entry['details']:
                section += f"- **Hierarchy**: {log_entry['details']}\n"
                break
    
    # Check output files
    output_files = pipeline_data.get('output_files', [])
    if output_files:
        section += f"- **Output Files Generated**: {len(output_files)}\n"
        
        # Check if ArangoDB output has content
        for file_path in output_files:
            if 'arangodb' in file_path and Path(file_path).exists():
                with open(file_path, 'r') as f:
                    arango_data = json.load(f)
                
                sections_count = len(arango_data.get('vertices', {}).get('sections', []))
                edges_count = sum(len(edges) for edges in arango_data.get('edges', {}).values())
                
                section += f"- **ArangoDB Sections**: {sections_count}\n"
                section += f"- **ArangoDB Edges**: {edges_count}\n"
    
    return section


def _generate_recommendations(pipeline_data: Dict[str, Any]) -> List[str]:
    """Generate actionable recommendations based on pipeline results."""
    recommendations = []
    
    # Check for failures
    failed_processors = []
    for proc_name, result in pipeline_data['results'].items():
        if not result['success']:
            failed_processors.append((proc_name, result.get('error', 'Unknown error')))
    
    if failed_processors:
        for proc_name, error in failed_processors:
            if "marker" in error.lower() and "no such file" in error.lower():
                recommendations.append(
                    f"CRITICAL: Install marker-pdf CLI to fix {proc_name} failure:\n"
                    "  Solution: pip install marker-pdf"
                )
            elif "rank_bm25" in error.lower():
                recommendations.append(
                    f"WARNING: BM25 module missing for {proc_name}:\n"
                    "  Solution: uv add rank-bm25"
                )
            else:
                recommendations.append(f"ERROR in {proc_name}: {error}")
    
    # Check for performance issues
    slow_processors = []
    for proc_name, result in pipeline_data['results'].items():
        if result['success'] and result['duration'] > 5.0:
            slow_processors.append(proc_name)
    
    if slow_processors:
        recommendations.append(
            f"PERFORMANCE: Slow processors detected: {', '.join(slow_processors)}\n"
            "  Consider: Enable parallel processing, check system resources"
        )
    
    # Check for empty output
    output_files = pipeline_data.get('output_files', [])
    if output_files:
        for file_path in output_files:
            if 'arangodb' in file_path and Path(file_path).exists():
                with open(file_path, 'r') as f:
                    arango_data = json.load(f)
                
                sections_count = len(arango_data.get('vertices', {}).get('sections', []))
                if sections_count == 0:
                    recommendations.append(
                        "CRITICAL: No sections extracted despite successful pipeline:\n"
                        "  - Check if marker output contains SectionHeader blocks\n"
                        "  - Verify hierarchy builder is processing blocks correctly\n"
                        "  - Consider adjusting block type detection logic"
                    )
    
    # If everything succeeded
    if not failed_processors and not any("CRITICAL" in rec for rec in recommendations):
        recommendations.append("SUCCESS: All processors completed successfully. Pipeline is working correctly.")
    
    return recommendations


# Usage functions for testing
async def working_usage():
    """Demonstrate report generation with a sample pipeline summary."""
    # Create sample data
    sample_summary = {
        "pipeline_status": "completed",
        "pdf_path": "test.pdf",
        "total_duration": 10.5,
        "processors": {
            "total": 2,
            "successful": 2,
            "failed": 0
        },
        "results": {
            "extractor": {"success": True, "duration": 5.2, "error": None},
            "cleaner": {"success": True, "duration": 2.1, "error": None}
        },
        "execution_log": [],
        "output_files": []
    }
    
    # Save to temp file
    temp_path = Path("/tmp/test_summary.json")
    with open(temp_path, 'w') as f:
        json.dump(sample_summary, f)
    
    # Generate report
    report_path = generate_pipeline_report(temp_path, Path("/tmp"))
    print(f"Generated report: {report_path}")
    return True


async def debug_function():
    """Debug report generation with current pipeline summary."""
    summary_path = Path("output/pipeline_summary.json")
    if summary_path.exists():
        report_path = generate_pipeline_report(summary_path, Path("output"))
        print(f"Generated report from current data: {report_path}")
        
        # Read and display key findings
        with open(report_path, 'r') as f:
            content = f.read()
        
        if "CRITICAL" in content:
            print("\n⚠️ CRITICAL ISSUES FOUND:")
            for line in content.split('\n'):
                if "CRITICAL" in line:
                    print(f"  - {line.strip()}")
    else:
        print("No pipeline summary found. Run the pipeline first.")


if __name__ == "__main__":
    import sys
    import asyncio
    
    mode = sys.argv[1] if len(sys.argv) > 1 else "working"
    
    if mode == "debug":
        print("Running debug mode...")
        asyncio.run(debug_function())
    else:
        print("Running working usage mode...")
        asyncio.run(working_usage())