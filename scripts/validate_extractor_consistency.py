#!/usr/bin/env python3
"""
Module: validate_extractor_consistency.py
Description: Validates that extractor produces consistent JSON output across PDF, HTML, and DOCX formats

External Dependencies:
- extractor: Local package (forked from marker-pdf)
- loguru: https://pypi.org/project/loguru/

Sample Input:
>>> document_base = "test_document"  # Will look for test_document.pdf, .html, .docx

Expected Output:
>>> {
...     "pdf": {"success": True, "blocks": 42, "text_length": 5000},
...     "html": {"success": True, "blocks": 41, "text_length": 4950},
...     "docx": {"success": True, "blocks": 40, "text_length": 4900},
...     "consistency": 0.95
... }

Example Usage:
>>> python validate_extractor_consistency.py test_document
"""

import sys
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple
from loguru import logger
import difflib

# Configure logging
logger.remove()
logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level} | {message}")


def extract_with_extractor(file_path: str) -> Dict[str, Any]:
    """Extract content using extractor for any supported format"""
    file_path = Path(file_path)
    file_type = file_path.suffix.lower().lstrip('.')
    
    try:
        from extractor.models import load_all_models
        from extractor.output import output_as_json
        
        # Load models once
        models = load_all_models()
        
        if file_type == "pdf":
            from extractor.converters.pdf import PdfConverter
            converter = PdfConverter(
                artifact_dict=models,
                processor_list=None,
                renderer=output_as_json
            )
            rendered = converter(str(file_path))
            return rendered.output
            
        elif file_type in ["html", "htm"]:
            from extractor.providers.html import HTMLProvider
            from extractor.converters.extraction import ExtractorConverter
            
            provider = HTMLProvider()
            document = provider.load(str(file_path))
            converter = ExtractorConverter(
                artifact_dict=models,
                processor_list=None,
                renderer=output_as_json
            )
            rendered = converter(document)
            return rendered.output
            
        elif file_type in ["docx", "doc"]:
            from extractor.providers.word import WordProvider
            from extractor.converters.extraction import ExtractorConverter
            
            provider = WordProvider()
            document = provider.load(str(file_path))
            converter = ExtractorConverter(
                artifact_dict=models,
                processor_list=None,
                renderer=output_as_json
            )
            rendered = converter(document)
            return rendered.output
            
        else:
            return {"error": f"Unsupported file type: {file_type}"}
            
    except Exception as e:
        logger.error(f"Failed to extract {file_path}: {e}")
        return {"error": str(e)}


def analyze_extraction_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze extraction result to get key metrics"""
    if "error" in result:
        return {"success": False, "error": result["error"]}
    
    analysis = {
        "success": True,
        "pages": 0,
        "blocks": 0,
        "text_length": 0,
        "tables": 0,
        "images": 0,
        "equations": 0,
        "all_text": []
    }
    
    # Extract metrics from result structure
    if "pages" in result:
        analysis["pages"] = len(result["pages"])
        
        for page in result["pages"]:
            if "blocks" in page:
                for block in page["blocks"]:
                    analysis["blocks"] += 1
                    
                    # Get block type
                    block_type = block.get("type", "").lower()
                    
                    # Count specific types
                    if "table" in block_type:
                        analysis["tables"] += 1
                    elif "image" in block_type or "figure" in block_type:
                        analysis["images"] += 1
                    elif "equation" in block_type or "math" in block_type:
                        analysis["equations"] += 1
                    
                    # Extract text
                    if "text" in block:
                        text = block["text"]
                        analysis["text_length"] += len(text)
                        analysis["all_text"].append(text)
    
    return analysis


def calculate_consistency(analyses: Dict[str, Dict[str, Any]]) -> Tuple[float, Dict[str, Any]]:
    """Calculate consistency score between different format extractions"""
    formats = list(analyses.keys())
    if len(formats) < 2:
        return 1.0, {"message": "Only one format to compare"}
    
    # Extract successful analyses
    successful = {fmt: data for fmt, data in analyses.items() if data.get("success", False)}
    
    if len(successful) < 2:
        return 0.0, {"message": "Need at least 2 successful extractions to compare"}
    
    consistency_scores = []
    comparisons = {}
    
    # Compare each pair of formats
    for i in range(len(formats)):
        for j in range(i + 1, len(formats)):
            fmt1, fmt2 = formats[i], formats[j]
            
            if fmt1 not in successful or fmt2 not in successful:
                continue
            
            data1, data2 = successful[fmt1], successful[fmt2]
            
            # Compare text content
            text1 = " ".join(data1.get("all_text", []))
            text2 = " ".join(data2.get("all_text", []))
            
            # Use sequence matcher for similarity
            matcher = difflib.SequenceMatcher(None, text1, text2)
            text_similarity = matcher.ratio()
            
            # Compare metrics
            metrics_similarity = 1.0
            metric_diffs = {}
            
            for metric in ["blocks", "tables", "images", "equations"]:
                val1 = data1.get(metric, 0)
                val2 = data2.get(metric, 0)
                
                if val1 == 0 and val2 == 0:
                    continue
                
                # Calculate relative difference
                max_val = max(val1, val2)
                diff = abs(val1 - val2) / max_val if max_val > 0 else 0
                metric_diffs[metric] = {
                    fmt1: val1,
                    fmt2: val2,
                    "diff_percent": diff * 100
                }
                
                # Penalize metric differences
                metrics_similarity *= (1 - diff * 0.5)  # 50% penalty for differences
            
            # Overall similarity is weighted average
            overall_similarity = (text_similarity * 0.7 + metrics_similarity * 0.3)
            
            consistency_scores.append(overall_similarity)
            comparisons[f"{fmt1}_vs_{fmt2}"] = {
                "text_similarity": text_similarity,
                "metrics_similarity": metrics_similarity,
                "overall_similarity": overall_similarity,
                "metric_differences": metric_diffs
            }
    
    # Average consistency score
    avg_consistency = sum(consistency_scores) / len(consistency_scores) if consistency_scores else 0.0
    
    return avg_consistency, comparisons


def validate_document_formats(base_name: str) -> Dict[str, Any]:
    """Validate extraction consistency across different formats of the same document"""
    base_path = Path(base_name)
    
    # Try different extensions
    formats = ["pdf", "html", "docx"]
    results = {}
    analyses = {}
    
    logger.info(f"Validating extraction consistency for: {base_name}")
    
    for fmt in formats:
        # Try with and without extension
        if base_path.suffix:
            file_path = base_path.with_suffix(f".{fmt}")
        else:
            file_path = Path(f"{base_name}.{fmt}")
        
        if file_path.exists():
            logger.info(f"Extracting {fmt.upper()}: {file_path}")
            
            # Extract content
            result = extract_with_extractor(str(file_path))
            results[fmt] = result
            
            # Analyze result
            analysis = analyze_extraction_result(result)
            analyses[fmt] = analysis
            
            # Log summary
            if analysis["success"]:
                logger.success(
                    f"{fmt.upper()}: {analysis['blocks']} blocks, "
                    f"{analysis['text_length']} chars, "
                    f"{analysis['tables']} tables, "
                    f"{analysis['images']} images"
                )
            else:
                logger.error(f"{fmt.upper()}: {analysis.get('error', 'Unknown error')}")
        else:
            logger.warning(f"{fmt.upper()} file not found: {file_path}")
            analyses[fmt] = {"success": False, "error": "File not found"}
    
    # Calculate consistency
    consistency_score, comparisons = calculate_consistency(analyses)
    
    # Build final report
    report = {
        "base_document": base_name,
        "formats_analyzed": {fmt: analyses[fmt] for fmt in formats},
        "consistency_score": consistency_score,
        "comparisons": comparisons,
        "recommendation": get_recommendation(consistency_score, analyses)
    }
    
    return report


def get_recommendation(consistency_score: float, analyses: Dict[str, Any]) -> str:
    """Generate recommendation based on consistency score"""
    successful_formats = [fmt for fmt, data in analyses.items() if data.get("success", False)]
    
    if len(successful_formats) == 0:
        return "❌ CRITICAL: No formats could be extracted successfully"
    elif len(successful_formats) == 1:
        return f"⚠️  WARNING: Only {successful_formats[0]} could be extracted"
    elif consistency_score >= 0.9:
        return "✅ EXCELLENT: Extractor produces highly consistent output across formats"
    elif consistency_score >= 0.7:
        return "✅ GOOD: Extractor produces reasonably consistent output across formats"
    elif consistency_score >= 0.5:
        return "⚠️  WARNING: Extractor shows moderate inconsistencies across formats"
    else:
        return "❌ POOR: Extractor produces inconsistent output across formats"


def print_detailed_report(report: Dict[str, Any]):
    """Print a detailed report of the validation results"""
    print("\n" + "="*80)
    print("EXTRACTOR CONSISTENCY VALIDATION REPORT")
    print("="*80)
    print(f"Document: {report['base_document']}")
    print(f"Overall Consistency Score: {report['consistency_score']:.2%}")
    print(f"Recommendation: {report['recommendation']}")
    
    print("\n" + "-"*80)
    print("FORMAT ANALYSIS:")
    print("-"*80)
    
    for fmt, analysis in report["formats_analyzed"].items():
        if analysis.get("success", False):
            print(f"\n{fmt.upper()}:")
            print(f"  ✅ Success")
            print(f"  📄 Blocks: {analysis.get('blocks', 0)}")
            print(f"  📝 Text Length: {analysis.get('text_length', 0):,} characters")
            print(f"  📊 Tables: {analysis.get('tables', 0)}")
            print(f"  🖼️  Images: {analysis.get('images', 0)}")
            print(f"  🔢 Equations: {analysis.get('equations', 0)}")
        else:
            print(f"\n{fmt.upper()}:")
            print(f"  ❌ Failed: {analysis.get('error', 'Unknown error')}")
    
    if report.get("comparisons"):
        print("\n" + "-"*80)
        print("FORMAT COMPARISONS:")
        print("-"*80)
        
        for comparison, data in report["comparisons"].items():
            print(f"\n{comparison}:")
            print(f"  Text Similarity: {data['text_similarity']:.2%}")
            print(f"  Metrics Similarity: {data['metrics_similarity']:.2%}")
            print(f"  Overall Similarity: {data['overall_similarity']:.2%}")
            
            if data.get("metric_differences"):
                print("  Metric Differences:")
                for metric, diff in data["metric_differences"].items():
                    formats = comparison.split("_vs_")
                    print(f"    {metric}: {formats[0]}={diff[formats[0]]}, "
                          f"{formats[1]}={diff[formats[1]]} "
                          f"(diff: {diff['diff_percent']:.1f}%)")
    
    print("\n" + "="*80)


if __name__ == "__main__":
    # Get document base name from command line or use default
    if len(sys.argv) > 1:
        document_base = sys.argv[1]
    else:
        # Default test document
        document_base = "test_document"
        print(f"Usage: {sys.argv[0]} <document_base_name>")
        print(f"Using default: {document_base}")
    
    # Run validation
    report = validate_document_formats(document_base)
    
    # Print detailed report
    print_detailed_report(report)
    
    # Save report to JSON
    report_file = f"extractor_consistency_report_{Path(document_base).stem}.json"
    with open(report_file, 'w') as f:
        # Remove the all_text field to keep file size reasonable
        clean_report = report.copy()
        for fmt_data in clean_report["formats_analyzed"].values():
            if "all_text" in fmt_data:
                del fmt_data["all_text"]
        json.dump(clean_report, f, indent=2)
    
    print(f"\nDetailed report saved to: {report_file}")
    
    # Exit with appropriate code
    if report["consistency_score"] >= 0.7:
        logger.success("✅ Validation PASSED")
        sys.exit(0)
    else:
        logger.error("❌ Validation FAILED")
        sys.exit(1)