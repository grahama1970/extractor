"""Formatting utilities for CLI output using rich."""

from typing import Any, Dict, List

from rich.console import Console
from rich.table import Table
from rich.tree import Tree
from rich.panel import Panel
from rich.syntax import Syntax
from rich import box


def print_validation_result(result: Dict[str, Any], console: Console):
    """Print validation result with rich formatting."""
    # Create a panel for the result
    panel = Panel(
        f"[bold]Validation Result[/bold]\n\n"
        f"Model: {result.get('model', 'N/A')}\n"
        f"Status: [green]{result.get('status', 'unknown')}[/green]\n"
        f"Strategies: {', '.join(result.get('strategies', []))}\n"
        f"Max Retries: {result.get('max_retries', 0)}\n\n"
        f"Output: {result.get('output', 'N/A')}",
        title="Validation Summary",
        border_style="green"
    )
    console.print(panel)


def print_strategies(strategies: List[Dict[str, Any]], console: Console):
    """Print available strategies in a formatted table."""
    table = Table(title="Available Validation Strategies", box=box.ROUNDED)
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Module", style="magenta")
    table.add_column("Description", style="green")
    
    for strategy in strategies:
        table.add_row(
            strategy.get('name', 'Unknown'),
            strategy.get('module', 'N/A'),
            strategy.get('description', 'No description available')
        )
    
    console.print(table)


def print_debug_trace(traces: Dict[str, Any], console: Console, errors_only: bool = False):
    """Print debug trace information."""
    tree = Tree("Validation Trace")
    
    for trace in traces.get("traces", []):
        if errors_only and trace.get("result", {}).get("valid", True):
            continue
            
        strategy_node = tree.add(f"[cyan]{trace.get('strategy_name', 'Unknown')}[/cyan]")
        
        # Add timing information
        duration = trace.get("duration_ms", 0)
        strategy_node.add(f"Duration: [yellow]{duration:.2f} ms[/yellow]")
        
        # Add result information
        result = trace.get("result", {})
        is_valid = result.get("valid", False)
        status_color = "green" if is_valid else "red"
        strategy_node.add(f"Status: [{status_color}]{'Valid' if is_valid else 'Invalid'}[/{status_color}]")
        
        if not is_valid and result.get("error"):
            error_node = strategy_node.add("[red]Error[/red]")
            error_node.add(result["error"])
            
        if result.get("suggestions"):
            suggestions_node = strategy_node.add("[yellow]Suggestions[/yellow]")
            for suggestion in result["suggestions"]:
                suggestions_node.add(suggestion)
                
        # Add debug info if available
        if result.get("debug_info"):
            debug_node = strategy_node.add("[blue]Debug Info[/blue]")
            for key, value in result["debug_info"].items():
                debug_node.add(f"{key}: {value}")
                
        # Add children traces
        if trace.get("children"):
            for child in trace["children"]:
                _add_child_trace(strategy_node, child, errors_only)
    
    console.print(tree)


def _add_child_trace(parent_node, trace: Dict[str, Any], errors_only: bool):
    """Recursively add child traces to the tree."""
    if errors_only and trace.get("result", {}).get("valid", True):
        return
        
    child_node = parent_node.add(f"[cyan]{trace.get('strategy_name', 'Unknown')}[/cyan]")
    
    duration = trace.get("duration_ms", 0)
    child_node.add(f"Duration: [yellow]{duration:.2f} ms[/yellow]")
    
    result = trace.get("result", {})
    is_valid = result.get("valid", False)
    status_color = "green" if is_valid else "red"
    child_node.add(f"Status: [{status_color}]{'Valid' if is_valid else 'Invalid'}[/{status_color}]")
    
    if not is_valid and result.get("error"):
        error_node = child_node.add("[red]Error[/red]")
        error_node.add(result["error"])
        
    if trace.get("children"):
        for child in trace["children"]:
            _add_child_trace(child_node, child, errors_only)


def print_validator_details(validator: Dict[str, Any], console: Console):
    """Print detailed information about a validator."""
    panel = Panel(
        f"[bold]Validator Details[/bold]\n\n"
        f"Name: {validator.get('name', 'Unknown')}\n"
        f"Class: {validator.get('class', 'N/A')}\n"
        f"Module: {validator.get('module', 'N/A')}\n"
        f"Description: {validator.get('description', 'No description available')}\n\n"
        f"Parameters:\n{_format_parameters(validator.get('parameters', {}))}",
        title=f"Validator: {validator.get('name', 'Unknown')}",
        border_style="cyan"
    )
    console.print(panel)


def _format_parameters(params: Dict[str, Any]) -> str:
    """Format validator parameters for display."""
    if not params:
        return "  None"
    
    lines = []
    for key, value in params.items():
        lines.append(f"  - {key}: {value}")
    return "\n".join(lines)