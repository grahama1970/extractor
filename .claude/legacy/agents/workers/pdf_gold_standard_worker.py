#!/usr/bin/env python3
"""
PDF Gold Standard Worker

Manages gold standard datasets for PDF extraction validation.
Creates, updates, and validates against gold standards to ensure
extraction quality meets requirements (90% threshold).
"""

import json
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import hashlib
from difflib import SequenceMatcher

import typer
from loguru import logger
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

# Configure logger
logger.remove()
logger.add(lambda msg: print(msg, end=""), level="INFO", format="{message}")

app = typer.Typer(help="Manage PDF extraction gold standards")
console = Console()


class PDFGoldStandardManager:
    """Manages gold standard datasets for validation."""
    
    def __init__(self):
        self.gold_dir = Path.home() / ".cache" / "extractor" / "gold_standards"
        self.gold_dir.mkdir(parents=True, exist_ok=True)
        
        # Validation thresholds
        self.thresholds = {
            "exact_match": 0.95,      # For identical content
            "semantic_match": 0.90,    # For semantic equivalence
            "structure_match": 0.85,   # For structural similarity
            "minimum_acceptable": 0.90 # Absolute minimum (raised from 0.80 to meet requirements)
        }
        
    async def create_gold_standard(self, 
                                  pdf_path: Path,
                                  extracted_data: Dict,
                                  metadata: Optional[Dict] = None) -> Dict:
        """Create a new gold standard from extracted data.
        
        Args:
            pdf_path: Source PDF path
            extracted_data: Extracted data to use as gold standard
            metadata: Additional metadata about the gold standard
            
        Returns:
            Gold standard creation result
        """
        # Generate gold standard ID
        gold_id = self._generate_gold_id(pdf_path)
        
        # Prepare gold standard structure
        gold_standard = {
            "id": gold_id,
            "source_pdf": str(pdf_path),
            "created_at": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
            "data": extracted_data,
            "statistics": self._calculate_statistics(extracted_data),
            "version": "1.0"
        }
        
        # Save gold standard
        gold_file = self.gold_dir / f"{gold_id}.json"
        with open(gold_file, 'w') as f:
            json.dump(gold_standard, f, indent=2)
        
        logger.info(f"Created gold standard: {gold_id}")
        
        return {
            "success": True,
            "gold_id": gold_id,
            "path": str(gold_file),
            "statistics": gold_standard["statistics"]
        }
    
    async def validate_against_gold(self,
                                   pdf_path: Path,
                                   extracted_data: Dict,
                                   validation_level: str = "semantic") -> Dict:
        """Validate extracted data against gold standard.
        
        Args:
            pdf_path: Source PDF path  
            extracted_data: Data to validate
            validation_level: Level of validation (exact, semantic, structure)
            
        Returns:
            Validation results with scores and differences
        """
        # Find gold standard
        gold_id = self._generate_gold_id(pdf_path)
        gold_file = self.gold_dir / f"{gold_id}.json"
        
        if not gold_file.exists():
            return {
                "success": False,
                "error": "No gold standard found for this PDF",
                "gold_id": gold_id
            }
        
        # Load gold standard
        with open(gold_file) as f:
            gold_standard = json.load(f)
        
        # Perform validation
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Validating against gold standard...", total=None)
            
            if validation_level == "exact":
                results = await self._validate_exact(gold_standard["data"], extracted_data)
            elif validation_level == "semantic":
                results = await self._validate_semantic(gold_standard["data"], extracted_data)
            else:  # structure
                results = await self._validate_structure(gold_standard["data"], extracted_data)
            
            progress.update(task, completed=True)
        
        # Calculate overall score
        overall_score = self._calculate_overall_score(results)
        passed = overall_score >= self.thresholds[f"{validation_level}_match"]
        
        return {
            "success": True,
            "gold_id": gold_id,
            "validation_level": validation_level,
            "passed": passed,
            "overall_score": overall_score,
            "threshold": self.thresholds[f"{validation_level}_match"],
            "details": results,
            "recommendations": self._generate_recommendations(results, overall_score)
        }
    
    async def _validate_exact(self, gold_data: Dict, test_data: Dict) -> Dict:
        """Perform exact matching validation."""
        results = {
            "block_matches": [],
            "missing_blocks": [],
            "extra_blocks": [],
            "content_mismatches": []
        }
        
        gold_blocks = gold_data.get("blocks", [])
        test_blocks = test_data.get("blocks", [])
        
        # Match blocks by position
        for i, gold_block in enumerate(gold_blocks):
            if i < len(test_blocks):
                test_block = test_blocks[i]
                
                # Compare content
                if gold_block.get("content") == test_block.get("content"):
                    results["block_matches"].append({
                        "index": i,
                        "type": gold_block.get("type"),
                        "score": 1.0
                    })
                else:
                    # Calculate similarity
                    similarity = SequenceMatcher(
                        None,
                        gold_block.get("content", ""),
                        test_block.get("content", "")
                    ).ratio()
                    
                    results["content_mismatches"].append({
                        "index": i,
                        "type": gold_block.get("type"),
                        "gold_content": gold_block.get("content", "")[:100],
                        "test_content": test_block.get("content", "")[:100],
                        "similarity": similarity
                    })
            else:
                results["missing_blocks"].append({
                    "index": i,
                    "type": gold_block.get("type"),
                    "content": gold_block.get("content", "")[:100]
                })
        
        # Check for extra blocks
        if len(test_blocks) > len(gold_blocks):
            for i in range(len(gold_blocks), len(test_blocks)):
                results["extra_blocks"].append({
                    "index": i,
                    "type": test_blocks[i].get("type"),
                    "content": test_blocks[i].get("content", "")[:100]
                })
        
        return results
    
    async def _validate_semantic(self, gold_data: Dict, test_data: Dict) -> Dict:
        """Perform semantic validation allowing for formatting differences."""
        results = {
            "semantic_matches": [],
            "semantic_mismatches": [],
            "structural_differences": []
        }
        
        gold_blocks = gold_data.get("blocks", [])
        test_blocks = test_data.get("blocks", [])
        
        # Create semantic representations
        gold_semantic = self._create_semantic_representation(gold_blocks)
        test_semantic = self._create_semantic_representation(test_blocks)
        
        # Compare semantic content
        for gold_item in gold_semantic:
            best_match = self._find_best_semantic_match(gold_item, test_semantic)
            
            if best_match and best_match["score"] >= 0.85:
                results["semantic_matches"].append({
                    "gold_type": gold_item["type"],
                    "gold_content": gold_item["content"][:100],
                    "match_score": best_match["score"],
                    "match_content": best_match["content"][:100]
                })
            else:
                results["semantic_mismatches"].append({
                    "gold_type": gold_item["type"],
                    "gold_content": gold_item["content"][:100],
                    "best_match_score": best_match["score"] if best_match else 0.0
                })
        
        # Check structural patterns
        gold_structure = self._extract_structure_pattern(gold_blocks)
        test_structure = self._extract_structure_pattern(test_blocks)
        
        if gold_structure != test_structure:
            results["structural_differences"].append({
                "gold_pattern": gold_structure,
                "test_pattern": test_structure
            })
        
        return results
    
    async def _validate_structure(self, gold_data: Dict, test_data: Dict) -> Dict:
        """Validate document structure and hierarchy."""
        results = {
            "hierarchy_match": False,
            "section_matches": [],
            "type_distribution_match": False,
            "order_preserved": False
        }
        
        # Compare hierarchies
        gold_hierarchy = gold_data.get("hierarchy")
        test_hierarchy = test_data.get("hierarchy")
        
        if gold_hierarchy and test_hierarchy:
            results["hierarchy_match"] = self._compare_hierarchies(
                gold_hierarchy, 
                test_hierarchy
            )
        
        # Compare block type distributions
        gold_types = self._get_type_distribution(gold_data.get("blocks", []))
        test_types = self._get_type_distribution(test_data.get("blocks", []))
        
        type_similarity = self._calculate_distribution_similarity(gold_types, test_types)
        results["type_distribution_match"] = type_similarity >= 0.9
        results["type_distribution_score"] = type_similarity
        
        # Check order preservation
        gold_order = self._extract_type_order(gold_data.get("blocks", []))
        test_order = self._extract_type_order(test_data.get("blocks", []))
        
        order_score = SequenceMatcher(None, gold_order, test_order).ratio()
        results["order_preserved"] = order_score >= 0.85
        results["order_score"] = order_score
        
        return results
    
    def _create_semantic_representation(self, blocks: List[Dict]) -> List[Dict]:
        """Create semantic representation of blocks."""
        semantic_items = []
        
        for block in blocks:
            # Normalize content
            content = block.get("content", "")
            if isinstance(content, str):
                # Remove extra whitespace
                normalized = " ".join(content.split())
                # Remove common formatting
                normalized = normalized.replace("\n", " ").strip()
                
                if normalized:
                    semantic_items.append({
                        "type": block.get("type"),
                        "content": normalized,
                        "original_index": blocks.index(block)
                    })
        
        return semantic_items
    
    def _find_best_semantic_match(self, gold_item: Dict, test_items: List[Dict]) -> Optional[Dict]:
        """Find best semantic match for a gold item."""
        best_match = None
        best_score = 0.0
        
        for test_item in test_items:
            # Type must match or be compatible
            if not self._types_compatible(gold_item["type"], test_item["type"]):
                continue
            
            # Calculate content similarity
            score = SequenceMatcher(
                None,
                gold_item["content"],
                test_item["content"]
            ).ratio()
            
            if score > best_score:
                best_score = score
                best_match = {
                    **test_item,
                    "score": score
                }
        
        return best_match
    
    def _types_compatible(self, type1: str, type2: str) -> bool:
        """Check if two block types are compatible."""
        # Exact match
        if type1 == type2:
            return True
        
        # Compatible types
        compatible_pairs = [
            ("SectionHeader", "Heading"),
            ("Text", "Paragraph"),
            ("ListItem", "Text"),
            ("Caption", "Text")
        ]
        
        for pair in compatible_pairs:
            if (type1, type2) == pair or (type2, type1) == pair:
                return True
        
        return False
    
    def _extract_structure_pattern(self, blocks: List[Dict]) -> str:
        """Extract structural pattern from blocks."""
        pattern_parts = []
        
        current_section = None
        for block in blocks:
            block_type = block.get("type", "Unknown")
            
            if block_type in ["SectionHeader", "Heading"]:
                if current_section:
                    pattern_parts.append(f"Section({len(current_section)})")
                current_section = [block_type]
            elif current_section is not None:
                current_section.append(block_type)
        
        # Add final section
        if current_section:
            pattern_parts.append(f"Section({len(current_section)})")
        
        return "-".join(pattern_parts)
    
    def _compare_hierarchies(self, gold_hierarchy: Dict, test_hierarchy: Dict) -> bool:
        """Compare two hierarchy structures."""
        # Simple comparison - could be made more sophisticated
        def flatten_hierarchy(node, level=0):
            items = [(level, node.get("title", ""))]
            for child in node.get("children", []):
                items.extend(flatten_hierarchy(child, level + 1))
            return items
        
        gold_flat = flatten_hierarchy(gold_hierarchy)
        test_flat = flatten_hierarchy(test_hierarchy)
        
        # Compare flattened structures
        if len(gold_flat) != len(test_flat):
            return False
        
        matches = sum(1 for g, t in zip(gold_flat, test_flat) if g == t)
        return matches / len(gold_flat) >= 0.9
    
    def _get_type_distribution(self, blocks: List[Dict]) -> Dict[str, int]:
        """Get distribution of block types."""
        distribution = {}
        for block in blocks:
            block_type = block.get("type", "Unknown")
            distribution[block_type] = distribution.get(block_type, 0) + 1
        return distribution
    
    def _calculate_distribution_similarity(self, dist1: Dict, dist2: Dict) -> float:
        """Calculate similarity between two distributions."""
        all_types = set(dist1.keys()) | set(dist2.keys())
        
        if not all_types:
            return 1.0
        
        total_diff = 0
        total_count = 0
        
        for block_type in all_types:
            count1 = dist1.get(block_type, 0)
            count2 = dist2.get(block_type, 0)
            total_count += max(count1, count2)
            total_diff += abs(count1 - count2)
        
        if total_count == 0:
            return 1.0
        
        return 1.0 - (total_diff / total_count)
    
    def _extract_type_order(self, blocks: List[Dict]) -> List[str]:
        """Extract order of block types."""
        return [block.get("type", "Unknown") for block in blocks]
    
    def _calculate_overall_score(self, results: Dict) -> float:
        """Calculate overall validation score."""
        scores = []
        
        # For exact validation
        if "block_matches" in results:
            total_blocks = (
                len(results["block_matches"]) +
                len(results["missing_blocks"]) +
                len(results["content_mismatches"])
            )
            if total_blocks > 0:
                exact_score = len(results["block_matches"]) / total_blocks
                scores.append(exact_score)
        
        # For semantic validation
        if "semantic_matches" in results:
            total_items = (
                len(results["semantic_matches"]) +
                len(results["semantic_mismatches"])
            )
            if total_items > 0:
                semantic_score = len(results["semantic_matches"]) / total_items
                scores.append(semantic_score)
        
        # For structure validation
        if "type_distribution_score" in results:
            scores.append(results["type_distribution_score"])
        if "order_score" in results:
            scores.append(results["order_score"])
        
        # Return average of all scores
        return sum(scores) / len(scores) if scores else 0.0
    
    def _generate_recommendations(self, results: Dict, score: float) -> List[str]:
        """Generate recommendations based on validation results."""
        recommendations = []
        
        if score < 0.8:
            recommendations.append("Critical: Extraction quality below minimum threshold")
        
        # Check specific issues
        if results.get("missing_blocks"):
            count = len(results["missing_blocks"])
            recommendations.append(f"Missing {count} blocks from gold standard")
        
        if results.get("content_mismatches"):
            low_similarity = [
                m for m in results["content_mismatches"] 
                if m["similarity"] < 0.8
            ]
            if low_similarity:
                recommendations.append(f"Found {len(low_similarity)} blocks with low content similarity")
        
        if results.get("semantic_mismatches"):
            count = len(results["semantic_mismatches"])
            recommendations.append(f"Semantic mismatches in {count} blocks")
        
        if results.get("structural_differences"):
            recommendations.append("Document structure differs from gold standard")
        
        # Positive feedback
        if score >= 0.95:
            recommendations.insert(0, "Excellent: Extraction quality exceeds requirements")
        elif score >= 0.9:
            recommendations.insert(0, "Good: Extraction meets quality requirements")
        
        return recommendations
    
    def _calculate_statistics(self, data: Dict) -> Dict:
        """Calculate statistics for gold standard data."""
        blocks = data.get("blocks", [])
        
        stats = {
            "total_blocks": len(blocks),
            "block_types": {},
            "total_characters": 0,
            "average_block_length": 0
        }
        
        total_length = 0
        for block in blocks:
            block_type = block.get("type", "Unknown")
            stats["block_types"][block_type] = stats["block_types"].get(block_type, 0) + 1
            
            content = block.get("content", "")
            if isinstance(content, str):
                length = len(content)
                total_length += length
                stats["total_characters"] += length
        
        if blocks:
            stats["average_block_length"] = total_length / len(blocks)
        
        return stats
    
    def _generate_gold_id(self, pdf_path: Path) -> str:
        """Generate unique ID for gold standard."""
        return hashlib.md5(str(pdf_path.absolute()).encode()).hexdigest()[:12]
    
    async def list_gold_standards(self) -> List[Dict]:
        """List all available gold standards."""
        gold_standards = []
        
        for gold_file in self.gold_dir.glob("*.json"):
            try:
                with open(gold_file) as f:
                    data = json.load(f)
                
                gold_standards.append({
                    "id": data["id"],
                    "source_pdf": data["source_pdf"],
                    "created_at": data["created_at"],
                    "statistics": data.get("statistics", {}),
                    "file_path": str(gold_file)
                })
            except Exception as e:
                logger.warning(f"Failed to load {gold_file}: {e}")
        
        return gold_standards
    
    async def update_gold_standard(self, gold_id: str, new_data: Dict) -> Dict:
        """Update existing gold standard."""
        gold_file = self.gold_dir / f"{gold_id}.json"
        
        if not gold_file.exists():
            return {
                "success": False,
                "error": f"Gold standard {gold_id} not found"
            }
        
        # Load existing
        with open(gold_file) as f:
            gold_standard = json.load(f)
        
        # Update data
        gold_standard["data"] = new_data
        gold_standard["statistics"] = self._calculate_statistics(new_data)
        gold_standard["updated_at"] = datetime.utcnow().isoformat()
        gold_standard["version"] = str(float(gold_standard.get("version", "1.0")) + 0.1)
        
        # Save updated
        with open(gold_file, 'w') as f:
            json.dump(gold_standard, f, indent=2)
        
        return {
            "success": True,
            "gold_id": gold_id,
            "version": gold_standard["version"]
        }


# Initialize manager
manager = PDFGoldStandardManager()


@app.command("create")
def create_gold_standard(
    pdf_path: Path = typer.Argument(..., help="Path to source PDF"),
    data_file: Path = typer.Argument(..., help="JSON file with extracted data"),
    metadata: Optional[str] = typer.Option(None, "--metadata", "-m", help="Additional metadata JSON")
):
    """Create a new gold standard from extracted data."""
    if not pdf_path.exists():
        console.print(f"[red]Error: PDF not found: {pdf_path}[/red]")
        raise typer.Exit(1)
    
    if not data_file.exists():
        console.print(f"[red]Error: Data file not found: {data_file}[/red]")
        raise typer.Exit(1)
    
    async def run():
        # Load extracted data
        with open(data_file) as f:
            extracted_data = json.load(f)
        
        # Parse metadata if provided
        meta = None
        if metadata:
            try:
                meta = json.loads(metadata)
            except json.JSONDecodeError:
                console.print("[yellow]Warning: Invalid metadata JSON[/yellow]")
        
        # Create gold standard
        result = await manager.create_gold_standard(pdf_path, extracted_data, meta)
        
        if result["success"]:
            console.print(f"[green] Created gold standard: {result['gold_id']}[/green]")
            
            # Show statistics
            stats = result["statistics"]
            table = Table(title="Gold Standard Statistics")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")
            
            table.add_row("Total Blocks", str(stats.get("total_blocks", 0)))
            table.add_row("Total Characters", f"{stats.get('total_characters', 0):,}")
            table.add_row("Avg Block Length", f"{stats.get('average_block_length', 0):.1f}")
            
            console.print(table)
            console.print(f"\nSaved to: {result['path']}")
    
    asyncio.run(run())


@app.command("validate")
def validate(
    pdf_path: Path = typer.Argument(..., help="Path to source PDF"),
    data_file: Path = typer.Argument(..., help="JSON file with data to validate"),
    level: str = typer.Option("semantic", "--level", "-l", help="Validation level: exact/semantic/structure")
):
    """Validate extracted data against gold standard."""
    if not data_file.exists():
        console.print(f"[red]Error: Data file not found: {data_file}[/red]")
        raise typer.Exit(1)
    
    async def run():
        # Load data to validate
        with open(data_file) as f:
            test_data = json.load(f)
        
        # Validate
        result = await manager.validate_against_gold(pdf_path, test_data, level)
        
        if not result["success"]:
            console.print(f"[red]Error: {result['error']}[/red]")
            raise typer.Exit(1)
        
        # Show results
        passed = result["passed"]
        score = result["overall_score"]
        threshold = result["threshold"]
        
        # Color based on pass/fail
        color = "green" if passed else "red"
        status = "PASSED" if passed else "FAILED"
        
        console.print(Panel(
            f"[{color}]Validation {status}[/{color}]\n\n"
            f"Score: {score:.2%}\n"
            f"Threshold: {threshold:.2%}\n"
            f"Validation Level: {level}",
            title="Validation Results"
        ))
        
        # Show recommendations
        if result["recommendations"]:
            console.print("\n[bold]Recommendations:[/bold]")
            for rec in result["recommendations"]:
                console.print(f"  • {rec}")
        
        # Show details based on validation level
        details = result["details"]
        
        if level == "exact" and details.get("content_mismatches"):
            console.print("\n[yellow]Content Mismatches:[/yellow]")
            for mismatch in details["content_mismatches"][:5]:  # Show first 5
                console.print(f"  Block {mismatch['index']} ({mismatch['type']}): "
                            f"{mismatch['similarity']:.2%} similarity")
        
        if level == "semantic" and details.get("semantic_mismatches"):
            console.print(f"\n[yellow]Semantic Mismatches: {len(details['semantic_mismatches'])}[/yellow]")
        
        # Exit with error if failed
        if not passed:
            raise typer.Exit(1)
    
    asyncio.run(run())


@app.command("list")
def list_standards():
    """List all available gold standards."""
    async def run():
        standards = await manager.list_gold_standards()
        
        if not standards:
            console.print("[yellow]No gold standards found[/yellow]")
            return
        
        table = Table(title="Available Gold Standards")
        table.add_column("ID", style="cyan")
        table.add_column("Source PDF", style="green")
        table.add_column("Created", style="yellow")
        table.add_column("Blocks", style="magenta")
        
        for std in standards:
            table.add_row(
                std["id"],
                Path(std["source_pdf"]).name,
                std["created_at"][:10],
                str(std["statistics"].get("total_blocks", 0))
            )
        
        console.print(table)
    
    asyncio.run(run())


# Worker functions
async def working_usage():
    """Demonstrate gold standard management."""
    logger.info("Testing gold standard management...")
    
    # Create mock data
    test_data = {
        "blocks": [
            {"type": "Heading", "content": "Introduction"},
            {"type": "Text", "content": "This is a test document."},
            {"type": "Heading", "content": "Methods"},
            {"type": "Text", "content": "We used advanced techniques."}
        ]
    }
    
    # Create gold standard
    test_pdf = Path("test.pdf")
    result = await manager.create_gold_standard(test_pdf, test_data)
    logger.info(f"\nCreated gold standard: {result['gold_id']}")
    
    # Validate identical data (should pass)
    validation = await manager.validate_against_gold(test_pdf, test_data, "exact")
    logger.info(f"\nExact validation score: {validation['overall_score']:.2%}")
    
    # Validate with minor changes
    modified_data = {
        "blocks": [
            {"type": "Heading", "content": "Introduction"},
            {"type": "Text", "content": "This is a test document with minor changes."},
            {"type": "Heading", "content": "Methods"},
            {"type": "Text", "content": "We used advanced techniques."}
        ]
    }
    
    semantic_validation = await manager.validate_against_gold(
        test_pdf, modified_data, "semantic"
    )
    logger.info(f"Semantic validation score: {semantic_validation['overall_score']:.2%}")


async def debug_function():
    """Test validation edge cases."""
    logger.info("Testing validation edge cases...")
    
    # Test with missing blocks
    gold_data = {
        "blocks": [
            {"type": "Heading", "content": "Title"},
            {"type": "Text", "content": "Paragraph 1"},
            {"type": "Text", "content": "Paragraph 2"}
        ]
    }
    
    missing_block_data = {
        "blocks": [
            {"type": "Heading", "content": "Title"},
            {"type": "Text", "content": "Paragraph 1"}
        ]
    }
    
    # Mock validation
    manager_debug = PDFGoldStandardManager()
    exact_results = await manager_debug._validate_exact(gold_data, missing_block_data)
    
    logger.info(f"\nMissing blocks test:")
    logger.info(f"  Matches: {len(exact_results['block_matches'])}")
    logger.info(f"  Missing: {len(exact_results['missing_blocks'])}")
    
    # Test semantic matching
    semantic_items = manager_debug._create_semantic_representation(gold_data["blocks"])
    logger.info(f"\nSemantic representation created: {len(semantic_items)} items")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "working_usage":
        asyncio.run(working_usage())
    elif len(sys.argv) > 1 and sys.argv[1] == "debug":
        asyncio.run(debug_function())
    else:
        app()