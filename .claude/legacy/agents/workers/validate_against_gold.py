#!/usr/bin/env python3
"""
Validate extraction results against gold standard.

This script compares the extraction output with the gold standard to measure accuracy.
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple
from difflib import SequenceMatcher
from loguru import logger

# Configure logger
logger.remove()
logger.add(lambda msg: print(msg, end=""), level="INFO", format="{message}")


def normalize_text(text: str) -> str:
    """Normalize text for comparison."""
    # Remove extra whitespace, normalize case
    return " ".join(text.split()).strip().lower()


def calculate_text_similarity(text1: str, text2: str) -> float:
    """Calculate similarity between two texts."""
    return SequenceMatcher(None, normalize_text(text1), normalize_text(text2)).ratio()


def validate_blocks(extracted: List[Dict], gold: List[Dict]) -> Dict:
    """Validate extracted blocks against gold standard."""
    results = {
        "total_gold": len(gold),
        "total_extracted": len(extracted),
        "matches": [],
        "mismatches": [],
        "missing": [],
        "extra": []
    }
    
    # Match blocks by position and content
    matched_gold = set()
    matched_extracted = set()
    
    for i, gold_block in enumerate(gold):
        best_match = None
        best_score = 0
        best_idx = -1
        
        # Find best matching extracted block
        for j, ext_block in enumerate(extracted):
            if j in matched_extracted:
                continue
                
            # Compare block types
            gold_type = gold_block.get("block_type", gold_block.get("type", ""))
            ext_type = ext_block.get("type", "")
            
            if gold_type != ext_type:
                continue
            
            # Compare text content
            gold_text = gold_block.get("text", "")
            ext_text = ext_block.get("text", "")
            
            similarity = calculate_text_similarity(gold_text, ext_text)
            
            if similarity > best_score and similarity > 0.8:  # 80% threshold
                best_match = ext_block
                best_score = similarity
                best_idx = j
        
        if best_match:
            matched_gold.add(i)
            matched_extracted.add(best_idx)
            results["matches"].append({
                "gold_idx": i,
                "extracted_idx": best_idx,
                "type": gold_block.get("block_type", gold_block.get("type", "")),
                "similarity": best_score,
                "gold_text": gold_block.get("text", "")[:50] + "...",
                "extracted_text": best_match.get("text", "")[:50] + "..."
            })
        else:
            results["missing"].append({
                "gold_idx": i,
                "type": gold_block.get("block_type", gold_block.get("type", "")),
                "text": gold_block.get("text", "")[:50] + "..."
            })
    
    # Find extra blocks in extraction
    for j, ext_block in enumerate(extracted):
        if j not in matched_extracted:
            results["extra"].append({
                "extracted_idx": j,
                "type": ext_block.get("type", ""),
                "text": ext_block.get("text", "")[:50] + "..."
            })
    
    # Calculate accuracy
    results["accuracy"] = len(results["matches"]) / len(gold) if gold else 0
    results["precision"] = len(results["matches"]) / len(extracted) if extracted else 0
    results["recall"] = len(results["matches"]) / len(gold) if gold else 0
    
    return results


def load_gold_blocks(gold_data: Dict) -> List[Dict]:
    """Extract blocks from gold standard format."""
    blocks = []
    
    # Handle nested structure
    if "document" in gold_data and "pages" in gold_data["document"]:
        for page in gold_data["document"]["pages"]:
            if "children" in page:
                blocks.extend(page["children"])
    elif "blocks" in gold_data:
        blocks = gold_data["blocks"]
    
    return blocks


async def working_usage():
    """Validate extraction against gold standard."""
    # Load extraction results
    extraction_path = Path("/tmp/bht_extraction_result.json")
    gold_path = Path("/home/graham/workspace/experiments/extractor/gold_standards/gold_standard_raw_marker_stage2.json")
    
    if not extraction_path.exists():
        logger.error(f"Extraction results not found: {extraction_path}")
        return
    
    if not gold_path.exists():
        logger.error(f"Gold standard not found: {gold_path}")
        return
    
    # Load files
    with open(extraction_path) as f:
        extraction = json.load(f)
    
    with open(gold_path) as f:
        gold_standard = json.load(f)
    
    logger.info("Validating extraction against gold standard...")
    logger.info(f"Gold standard: {gold_standard['metadata']['description']}")
    
    # Extract blocks
    extracted_blocks = extraction.get("blocks", [])
    gold_blocks = load_gold_blocks(gold_standard)
    
    logger.info(f"\nBlock counts:")
    logger.info(f"  Gold standard: {len(gold_blocks)} blocks")
    logger.info(f"  Extracted: {len(extracted_blocks)} blocks")
    
    # Validate
    validation = validate_blocks(extracted_blocks, gold_blocks)
    
    logger.info(f"\nValidation Results:")
    logger.info(f"  Accuracy: {validation['accuracy']:.1%}")
    logger.info(f"  Precision: {validation['precision']:.1%}")
    logger.info(f"  Recall: {validation['recall']:.1%}")
    logger.info(f"  Matches: {len(validation['matches'])}")
    logger.info(f"  Missing: {len(validation['missing'])}")
    logger.info(f"  Extra: {len(validation['extra'])}")
    
    # Show examples of issues
    if validation["missing"]:
        logger.warning(f"\nExample missing blocks:")
        for miss in validation["missing"][:3]:
            logger.warning(f"  - {miss['type']}: {miss['text']}")
    
    if validation["extra"]:
        logger.warning(f"\nExample extra blocks:")
        for extra in validation["extra"][:3]:
            logger.warning(f"  - {extra['type']}: {extra['text']}")
    
    # Check sub-agent processing
    logger.info(f"\nSub-agent Processing:")
    suspicious_count = extraction.get("metadata", {}).get("suspicious_processed", 0)
    logger.info(f"  Suspicious blocks processed: {suspicious_count}")
    
    if suspicious_count == 0:
        logger.error("  ⚠️  NO SUSPICIOUS BLOCKS WERE PROCESSED BY SUB-AGENTS!")
        logger.error("  The sub-agent post-processing phase was skipped!")
    
    # Save validation report
    report_path = Path("/tmp/validation_report.json")
    with open(report_path, 'w') as f:
        json.dump(validation, f, indent=2)
    logger.info(f"\nValidation report saved to: {report_path}")
    
    return validation


async def debug_function():
    """Debug gold standard structure."""
    gold_path = Path("/home/graham/workspace/experiments/extractor/gold_standards/gold_standard_raw_marker_stage2.json")
    
    with open(gold_path) as f:
        gold = json.load(f)
    
    logger.info("Gold standard structure:")
    logger.info(f"Keys: {list(gold.keys())}")
    logger.info(f"Metadata: {gold['metadata']}")
    
    blocks = load_gold_blocks(gold)
    logger.info(f"\nExtracted {len(blocks)} blocks")
    
    # Count by type
    type_counts = {}
    for block in blocks:
        block_type = block.get("block_type", block.get("type", "Unknown"))
        type_counts[block_type] = type_counts.get(block_type, 0) + 1
    
    logger.info("\nBlock types in gold standard:")
    for block_type, count in type_counts.items():
        logger.info(f"  {block_type}: {count}")


if __name__ == "__main__":
    import asyncio
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "debug":
        asyncio.run(debug_function())
    else:
        asyncio.run(working_usage())