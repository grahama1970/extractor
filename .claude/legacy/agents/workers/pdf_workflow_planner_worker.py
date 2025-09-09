#!/usr/bin/env python3
"""
PDF Workflow Planner Worker

Plans and optimizes PDF extraction workflows based on document characteristics.
Creates DAG execution plans and coordinates sub-agent sequencing.
"""

import json
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime
import os

import typer
from loguru import logger
from rich.console import Console
from rich.tree import Tree
from rich.table import Table
import networkx as nx
from anthropic import AsyncAnthropic

# Configure logger
logger.remove()
logger.add(lambda msg: print(msg, end=""), level="INFO", format="{message}")

app = typer.Typer(help="Plan optimal PDF extraction workflows")
console = Console()


class PDFWorkflowPlanner:
    """Plans PDF extraction workflows based on document analysis."""
    
    def __init__(self):
        # Initialize Claude client for intelligent planning
        api_key = os.getenv("CLAUDE_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
        if api_key:
            self.client = AsyncAnthropic(api_key=api_key)
            self.model = "claude-3-haiku-20240307"
        else:
            self.client = None
            logger.warning("No Claude API key - using heuristic planning")
        
        # Standard workflow templates
        self.workflow_templates = self._load_workflow_templates()
        
    def _load_workflow_templates(self) -> Dict[str, Dict]:
        """Load predefined workflow templates."""
        return {
            "academic_paper": {
                "name": "Academic Paper Workflow",
                "stages": [
                    {"stage": 1, "agents": ["pdf-section", "pdf-suspicious-validator"], "parallel": True},
                    {"stage": 2, "agents": ["pdf-table", "pdf-equation"], "parallel": True},
                    {"stage": 3, "agents": ["pdf-reference", "pdf-citation"], "parallel": True},
                    {"stage": 4, "agents": ["pdf-text-cleaner"], "parallel": False}
                ],
                "characteristics": ["has_abstract", "has_references", "has_equations"]
            },
            "financial_report": {
                "name": "Financial Report Workflow", 
                "stages": [
                    {"stage": 1, "agents": ["pdf-section"], "parallel": False},
                    {"stage": 2, "agents": ["pdf-table", "pdf-chart"], "parallel": True},
                    {"stage": 3, "agents": ["pdf-number-validator"], "parallel": False}
                ],
                "characteristics": ["has_tables", "has_financial_data", "has_charts"]
            },
            "form_document": {
                "name": "Form Document Workflow",
                "stages": [
                    {"stage": 1, "agents": ["pdf-form"], "parallel": False},
                    {"stage": 2, "agents": ["pdf-field-extractor"], "parallel": False},
                    {"stage": 3, "agents": ["pdf-validation"], "parallel": False}
                ],
                "characteristics": ["has_form_fields", "has_checkboxes", "fillable"]
            },
            "generic": {
                "name": "Generic Document Workflow",
                "stages": [
                    {"stage": 1, "agents": ["pdf-section", "pdf-suspicious-validator"], "parallel": True},
                    {"stage": 2, "agents": ["pdf-table", "pdf-object-identifier"], "parallel": True},
                    {"stage": 3, "agents": ["pdf-text-cleaner"], "parallel": False}
                ],
                "characteristics": []
            }
        }
    
    async def analyze_document(self, blocks: List[Dict]) -> Dict:
        """Analyze document characteristics to determine optimal workflow."""
        characteristics = {
            "total_blocks": len(blocks),
            "block_types": {},
            "has_tables": False,
            "has_equations": False,
            "has_images": False,
            "has_form_fields": False,
            "has_references": False,
            "has_abstract": False,
            "has_financial_data": False,
            "has_charts": False,
            "estimated_complexity": "low",
            "suspicious_blocks": 0
        }
        
        # Count block types
        for block in blocks:
            block_type = block.get("type", "Unknown")
            characteristics["block_types"][block_type] = characteristics["block_types"].get(block_type, 0) + 1
            
            # Check specific characteristics
            if block_type == "Table":
                characteristics["has_tables"] = True
            elif block_type == "Equation":
                characteristics["has_equations"] = True
            elif block_type == "Image":
                characteristics["has_images"] = True
            elif block_type == "FormField":
                characteristics["has_form_fields"] = True
                
            # Check text content
            text = block.get("text", "").lower()
            if "references" in text or "bibliography" in text:
                characteristics["has_references"] = True
            if "abstract" in text and block.get("type") == "SectionHeader":
                characteristics["has_abstract"] = True
            if any(term in text for term in ["revenue", "profit", "income", "balance sheet"]):
                characteristics["has_financial_data"] = True
                
            # Count suspicious blocks
            if block.get("suspicious", False) or block.get("suspicion_score", 0) > 0:
                characteristics["suspicious_blocks"] += 1
        
        # Estimate complexity
        if characteristics["total_blocks"] > 500:
            characteristics["estimated_complexity"] = "high"
        elif characteristics["total_blocks"] > 200:
            characteristics["estimated_complexity"] = "medium"
        
        # Use Claude for deeper analysis if available
        if self.client and characteristics["estimated_complexity"] != "low":
            enhanced = await self._claude_document_analysis(blocks[:10], characteristics)
            characteristics.update(enhanced)
        
        return characteristics
    
    async def _claude_document_analysis(self, sample_blocks: List[Dict], initial_analysis: Dict) -> Dict:
        """Use Claude for deeper document understanding."""
        # Sample text from first blocks
        sample_text = "\n".join([b.get("text", "")[:200] for b in sample_blocks if b.get("text")])
        
        prompt = f"""Analyze this document sample and initial analysis to determine the document type and optimal processing strategy.

Sample text:
{sample_text}

Initial analysis:
- Total blocks: {initial_analysis['total_blocks']}
- Block types: {json.dumps(initial_analysis['block_types'])}
- Has tables: {initial_analysis['has_tables']}
- Has equations: {initial_analysis['has_equations']}

Provide a JSON response with:
1. "document_type": Classification (academic_paper, financial_report, technical_manual, etc.)
2. "confidence": 0.0 to 1.0
3. "processing_hints": List of specific processing recommendations
4. "potential_issues": List of extraction challenges to watch for

Respond with valid JSON only."""

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=500,
                temperature=0.1,
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Parse response
            import re
            json_match = re.search(r'\{.*\}', response.content[0].text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return {
                    "document_type": result.get("document_type", "generic"),
                    "ai_confidence": result.get("confidence", 0.5),
                    "processing_hints": result.get("processing_hints", []),
                    "potential_issues": result.get("potential_issues", [])
                }
        except Exception as e:
            logger.debug(f"Claude analysis failed: {e}")
        
        return {}
    
    def select_workflow_template(self, characteristics: Dict) -> Dict:
        """Select best workflow template based on characteristics."""
        best_match = None
        best_score = 0
        
        for template_name, template in self.workflow_templates.items():
            score = 0
            
            # Score based on matching characteristics
            for char in template["characteristics"]:
                if characteristics.get(char, False):
                    score += 1
            
            # Bonus for exact document type match
            if characteristics.get("document_type") == template_name:
                score += 3
                
            if score > best_score:
                best_score = score
                best_match = template_name
        
        # Default to generic if no good match
        if best_score == 0:
            best_match = "generic"
            
        logger.info(f"Selected workflow: {best_match} (score: {best_score})")
        return self.workflow_templates[best_match]
    
    def optimize_workflow(self, template: Dict, characteristics: Dict) -> List[Dict]:
        """Optimize workflow based on document characteristics."""
        optimized_stages = []
        
        for stage in template["stages"]:
            # Filter out unnecessary agents
            agents = []
            for agent in stage["agents"]:
                # Skip table agent if no tables
                if agent == "pdf-table" and not characteristics.get("has_tables"):
                    continue
                # Skip equation agent if no equations
                if agent == "pdf-equation" and not characteristics.get("has_equations"):
                    continue
                # Skip form agent if no forms
                if agent == "pdf-form" and not characteristics.get("has_form_fields"):
                    continue
                    
                agents.append(agent)
            
            if agents:
                optimized_stages.append({
                    "stage": stage["stage"],
                    "agents": agents,
                    "parallel": stage["parallel"] and len(agents) > 1
                })
        
        # Add suspicious validator if needed
        if characteristics.get("suspicious_blocks", 0) > 0:
            # Ensure validator is in stage 1
            if optimized_stages and "pdf-suspicious-validator" not in optimized_stages[0]["agents"]:
                optimized_stages[0]["agents"].append("pdf-suspicious-validator")
                optimized_stages[0]["parallel"] = True
        
        return optimized_stages
    
    def create_dag(self, stages: List[Dict]) -> nx.DiGraph:
        """Create execution DAG from workflow stages."""
        dag = nx.DiGraph()
        
        # Add nodes for each agent
        for stage in stages:
            for agent in stage["agents"]:
                dag.add_node(agent, stage=stage["stage"])
        
        # Add edges between stages
        for i in range(len(stages) - 1):
            current_agents = stages[i]["agents"]
            next_agents = stages[i + 1]["agents"]
            
            for current in current_agents:
                for next_agent in next_agents:
                    dag.add_edge(current, next_agent)
        
        return dag
    
    async def plan_workflow(self, 
                          blocks: List[Dict],
                          constraints: Optional[Dict] = None) -> Dict:
        """Create complete workflow plan for document."""
        # Analyze document
        characteristics = await self.analyze_document(blocks)
        
        # Select and optimize workflow
        template = self.select_workflow_template(characteristics)
        stages = self.optimize_workflow(template, characteristics)
        
        # Create DAG
        dag = self.create_dag(stages)
        
        # Apply constraints if provided
        if constraints:
            stages = self._apply_constraints(stages, constraints)
        
        # Calculate estimated time and cost
        estimates = self._calculate_estimates(stages, characteristics)
        
        return {
            "workflow_name": template["name"],
            "document_characteristics": characteristics,
            "stages": stages,
            "dag": nx.node_link_data(dag),  # Serializable format
            "estimates": estimates,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def _apply_constraints(self, stages: List[Dict], constraints: Dict) -> List[Dict]:
        """Apply user constraints to workflow."""
        # Max parallel agents
        if "max_parallel" in constraints:
            max_parallel = constraints["max_parallel"]
            for stage in stages:
                if len(stage["agents"]) > max_parallel:
                    stage["parallel"] = False
        
        # Excluded agents
        if "exclude_agents" in constraints:
            excluded = set(constraints["exclude_agents"])
            for stage in stages:
                stage["agents"] = [a for a in stage["agents"] if a not in excluded]
        
        # Time limit - remove later stages if needed
        if "max_time_seconds" in constraints:
            # Rough estimate: 10 seconds per stage
            max_stages = constraints["max_time_seconds"] // 10
            stages = stages[:max_stages]
        
        return stages
    
    def _calculate_estimates(self, stages: List[Dict], characteristics: Dict) -> Dict:
        """Estimate time and cost for workflow."""
        # Base estimates per agent (seconds)
        agent_times = {
            "pdf-section": 5,
            "pdf-suspicious-validator": 10,  # LLM calls
            "pdf-table": 15,  # Complex analysis
            "pdf-equation": 8,
            "pdf-text-cleaner": 3,
            "pdf-form": 12,
            "pdf-reference": 10
        }
        
        total_time = 0
        for stage in stages:
            if stage["parallel"]:
                # Parallel execution - take max time
                stage_time = max(agent_times.get(agent, 5) for agent in stage["agents"])
            else:
                # Sequential execution - sum times
                stage_time = sum(agent_times.get(agent, 5) for agent in stage["agents"])
            
            total_time += stage_time
        
        # Adjust for document size
        size_factor = min(characteristics["total_blocks"] / 100, 3.0)
        total_time *= size_factor
        
        # Cost estimate (rough)
        llm_agents = ["pdf-suspicious-validator", "pdf-table", "pdf-equation"]
        llm_calls = sum(1 for s in stages for a in s["agents"] if a in llm_agents)
        estimated_cost = llm_calls * 0.001  # ~$0.001 per Haiku call
        
        return {
            "estimated_time_seconds": round(total_time),
            "estimated_cost_usd": round(estimated_cost, 4),
            "total_stages": len(stages),
            "total_agents": sum(len(s["agents"]) for s in stages),
            "parallel_stages": sum(1 for s in stages if s["parallel"])
        }
    
    def visualize_workflow(self, workflow: Dict) -> Tree:
        """Create visual representation of workflow."""
        tree = Tree(f"[bold]{workflow['workflow_name']}[/bold]")
        
        # Add characteristics
        char_node = tree.add("[cyan]Document Characteristics[/cyan]")
        chars = workflow["document_characteristics"]
        char_node.add(f"Total blocks: {chars['total_blocks']}")
        char_node.add(f"Complexity: {chars['estimated_complexity']}")
        if chars.get("document_type"):
            char_node.add(f"Type: {chars['document_type']}")
        
        # Add stages
        stages_node = tree.add("[green]Execution Stages[/green]")
        for stage in workflow["stages"]:
            stage_label = f"Stage {stage['stage']}"
            if stage["parallel"]:
                stage_label += " [yellow](parallel)[/yellow]"
            
            stage_node = stages_node.add(stage_label)
            for agent in stage["agents"]:
                stage_node.add(f"→ {agent}")
        
        # Add estimates
        est_node = tree.add("[magenta]Estimates[/magenta]")
        estimates = workflow["estimates"]
        est_node.add(f"Time: ~{estimates['estimated_time_seconds']} seconds")
        est_node.add(f"Cost: ~${estimates['estimated_cost_usd']:.4f}")
        
        return tree


# Initialize planner
planner = PDFWorkflowPlanner()


@app.command("plan")
def plan(
    blocks_file: Path = typer.Argument(..., help="JSON file with document blocks"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Save plan to file"),
    visualize: bool = typer.Option(True, "--visualize/--no-visualize", help="Show visual plan"),
    max_parallel: Optional[int] = typer.Option(None, "--max-parallel", help="Max parallel agents"),
    exclude: Optional[List[str]] = typer.Option(None, "--exclude", help="Agents to exclude")
):
    """Plan optimal workflow for PDF extraction."""
    if not blocks_file.exists():
        console.print(f"[red]Error: File not found: {blocks_file}[/red]")
        raise typer.Exit(1)
    
    async def run():
        # Load blocks
        with open(blocks_file) as f:
            data = json.load(f)
        
        blocks = data if isinstance(data, list) else data.get("blocks", [])
        
        # Build constraints
        constraints = {}
        if max_parallel:
            constraints["max_parallel"] = max_parallel
        if exclude:
            constraints["exclude_agents"] = exclude
        
        # Plan workflow
        with console.status("Planning optimal workflow..."):
            workflow = await planner.plan_workflow(blocks, constraints)
        
        # Visualize
        if visualize:
            tree = planner.visualize_workflow(workflow)
            console.print(tree)
        
        # Save if requested
        if output:
            with open(output, 'w') as f:
                json.dump(workflow, f, indent=2)
            console.print(f"\n[green]✓ Saved workflow plan to {output}[/green]")
        
        return workflow
    
    asyncio.run(run())


@app.command("templates")
def templates():
    """List available workflow templates."""
    table = Table(title="Workflow Templates")
    table.add_column("Template", style="cyan")
    table.add_column("Description", style="green")
    table.add_column("Characteristics", style="yellow")
    
    for name, template in planner.workflow_templates.items():
        chars = ", ".join(template["characteristics"]) or "None"
        table.add_row(name, template["name"], chars)
    
    console.print(table)


@app.command("analyze")
def analyze(
    blocks_file: Path = typer.Argument(..., help="JSON file with document blocks")
):
    """Analyze document characteristics."""
    if not blocks_file.exists():
        console.print(f"[red]Error: File not found: {blocks_file}[/red]")
        raise typer.Exit(1)
    
    async def run():
        # Load blocks
        with open(blocks_file) as f:
            data = json.load(f)
        
        blocks = data if isinstance(data, list) else data.get("blocks", [])
        
        # Analyze
        with console.status("Analyzing document..."):
            characteristics = await planner.analyze_document(blocks)
        
        # Display results
        table = Table(title="Document Characteristics")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")
        
        # Basic stats
        table.add_row("Total Blocks", str(characteristics["total_blocks"]))
        table.add_row("Complexity", characteristics["estimated_complexity"])
        
        # Block types
        if characteristics["block_types"]:
            types_str = ", ".join(f"{k}: {v}" for k, v in characteristics["block_types"].items())
            table.add_row("Block Types", types_str)
        
        # Features
        features = []
        for key, value in characteristics.items():
            if key.startswith("has_") and value:
                features.append(key.replace("has_", ""))
        if features:
            table.add_row("Features", ", ".join(features))
        
        # AI analysis
        if "document_type" in characteristics:
            table.add_row("Document Type", characteristics["document_type"])
            table.add_row("AI Confidence", f"{characteristics.get('ai_confidence', 0):.2%}")
        
        console.print(table)
        
        # Show hints if available
        if "processing_hints" in characteristics:
            console.print("\n[bold]Processing Hints:[/bold]")
            for hint in characteristics["processing_hints"]:
                console.print(f"  • {hint}")
    
    asyncio.run(run())


# Worker functions
async def working_usage():
    """Demonstrate workflow planning capabilities."""
    logger.info("Testing workflow planning...")
    
    # Sample blocks representing different document types
    academic_blocks = [
        {"type": "SectionHeader", "text": "Abstract"},
        {"type": "Text", "text": "This paper presents..."},
        {"type": "SectionHeader", "text": "1. Introduction"},
        {"type": "Text", "text": "Machine learning has..."},
        {"type": "Table", "cells": [["Method", "Accuracy"], ["Our", "95%"]]},
        {"type": "Equation", "text": "E = mc^2"},
        {"type": "SectionHeader", "text": "References"}
    ]
    
    # Plan workflow
    workflow = await planner.plan_workflow(academic_blocks)
    
    logger.info(f"\nPlanned workflow: {workflow['workflow_name']}")
    logger.info(f"Stages: {len(workflow['stages'])}")
    logger.info(f"Estimated time: {workflow['estimates']['estimated_time_seconds']}s")
    
    # Show stages
    for stage in workflow["stages"]:
        agents = ", ".join(stage["agents"])
        parallel = " (parallel)" if stage["parallel"] else ""
        logger.info(f"  Stage {stage['stage']}: {agents}{parallel}")


async def debug_function():
    """Test edge cases and constraints."""
    logger.info("Testing workflow planning edge cases...")
    
    # Test 1: Empty document
    empty_workflow = await planner.plan_workflow([])
    logger.info(f"\nEmpty document workflow: {empty_workflow['workflow_name']}")
    
    # Test 2: Large document with constraints
    large_blocks = [{"type": "Text", "text": f"Block {i}"} for i in range(1000)]
    
    constrained = await planner.plan_workflow(
        large_blocks,
        constraints={
            "max_parallel": 2,
            "max_time_seconds": 30,
            "exclude_agents": ["pdf-equation"]
        }
    )
    
    logger.info(f"\nConstrained workflow:")
    logger.info(f"  Stages: {len(constrained['stages'])}")
    logger.info(f"  Max agents per stage: {max(len(s['agents']) for s in constrained['stages'])}")
    
    # Test 3: Document type detection
    financial_blocks = [
        {"type": "Text", "text": "Annual Revenue: $1.2M"},
        {"type": "Table", "text": "Balance Sheet"},
        {"type": "Text", "text": "Profit margin increased by 15%"}
    ]
    
    financial = await planner.plan_workflow(financial_blocks)
    logger.info(f"\nFinancial document detected: {financial['document_characteristics'].get('has_financial_data')}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "working_usage":
        asyncio.run(working_usage())
    elif len(sys.argv) > 1 and sys.argv[1] == "debug":
        asyncio.run(debug_function())
    else:
        app()