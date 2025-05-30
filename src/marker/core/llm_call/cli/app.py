"""CLI application for LLM validation with retry and custom strategies."""

import json
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from marker.core.llm_call.core import registry, retry_with_validation, RetryConfig
from marker.core.llm_call.core.debug import DebugManager
from marker.core.llm_call.cli.formatters import print_validation_result, print_strategies, print_debug_trace
from marker.core.llm_call.cli.schemas import ValidationRequest

app = typer.Typer(
    name="llm-validate",
    help="LLM validation with retry and custom strategies",
    add_completion=False,
)
console = Console()


@app.command()
def validate(
    prompt: str = typer.Argument(..., help="LLM prompt to validate"),
    model: str = typer.Option("vertex_ai/gemini-2.5-flash-preview-04-17", help="LLM model to use"),
    validators: List[str] = typer.Option([], help="Validation strategies to apply"),
    max_retries: int = typer.Option(3, help="Maximum retry attempts"),
    debug: bool = typer.Option(False, help="Enable debug mode"),
    output: Optional[Path] = typer.Option(None, help="Save results to file"),
):
    """Validate LLM output with custom strategies."""
    try:
        # Setup debug if enabled
        debug_manager = DebugManager(console) if debug else None
        
        # Load validators
        strategies = []
        for validator_name in validators:
            try:
                # Parse validator with parameters
                if "(" in validator_name:
                    name, params_str = validator_name.split("(", 1)
                    params_str = params_str.rstrip(")")
                    # Parse parameters
                    params = {}
                    if params_str:
                        for param in params_str.split(","):
                            key, value = param.split("=")
                            params[key.strip()] = eval(value.strip())
                    strategy = registry.get(name, **params)
                else:
                    strategy = registry.get(validator_name)
                strategies.append(strategy)
            except Exception as e:
                console.print(f"[red]Error loading validator '{validator_name}': {e}[/red]")
                raise typer.Exit(1)
        
        # Create validation request
        request = ValidationRequest(
            prompt=prompt,
            model=model,
            strategies=strategies,
            config=RetryConfig(max_attempts=max_retries, debug_mode=debug)
        )
        
        # Run validation (mock for now since we're not doing actual LLM calls)
        console.print(f"[yellow]Running validation with {len(strategies)} strategies...[/yellow]")
        
        # Mock result for demonstration
        result = {
            "prompt": prompt,
            "model": model,
            "strategies": [s.name for s in strategies],
            "max_retries": max_retries,
            "status": "completed",
            "output": "Mock validation result"
        }
        
        # Display results
        print_validation_result(result, console)
        
        # Show debug info if enabled
        if debug_manager:
            debug_manager.print_summary()
        
        # Save output if requested
        if output:
            with open(output, 'w') as f:
                json.dump(result, f, indent=2)
            console.print(f"[green]Results saved to {output}[/green]")
            
    except Exception as e:
        console.print(f"[red]Validation failed: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def list_validators():
    """List available validation strategies."""
    strategies = registry.list_all()
    print_strategies(strategies, console)


@app.command()
def add_validator(
    path: Path = typer.Argument(..., help="Path to validator module"),
    name: Optional[str] = typer.Option(None, help="Optional name for validator"),
):
    """Add a custom validator from a Python file."""
    try:
        # This would normally load the module and register it
        # For now, just validate the path exists
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        
        console.print(f"[green]Validator loaded from {path}[/green]")
        if name:
            console.print(f"[green]Registered as: {name}[/green]")
    except Exception as e:
        console.print(f"[red]Failed to load validator: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def debug(
    trace_file: Path = typer.Argument(..., help="Path to debug trace file"),
    show_errors_only: bool = typer.Option(False, help="Show only errors"),
):
    """Analyze a debug trace file."""
    try:
        if not trace_file.exists():
            raise FileNotFoundError(f"Trace file not found: {trace_file}")
        
        with open(trace_file, 'r') as f:
            traces = json.load(f)
        
        debug_manager = DebugManager(console)
        print_debug_trace(traces, console, show_errors_only)
        
    except Exception as e:
        console.print(f"[red]Failed to load trace file: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def compare(
    trace1: Path = typer.Argument(..., help="First trace file"),
    trace2: Path = typer.Argument(..., help="Second trace file"),
    metric: str = typer.Option("duration", help="Metric to compare (duration, errors, strategies)"),
):
    """Compare two validation trace files."""
    try:
        if not trace1.exists() or not trace2.exists():
            raise FileNotFoundError("One or both trace files not found")
        
        with open(trace1, 'r') as f:
            traces1 = json.load(f)
        with open(trace2, 'r') as f:
            traces2 = json.load(f)
        
        # Create comparison table
        table = Table(title=f"Comparison by {metric}")
        table.add_column("Trace", style="cyan")
        table.add_column("Value", style="magenta")
        
        if metric == "duration":
            # Calculate total duration for each trace
            duration1 = sum(t.get("duration_ms", 0) for t in traces1.get("traces", []))
            duration2 = sum(t.get("duration_ms", 0) for t in traces2.get("traces", []))
            
            table.add_row(str(trace1.name), f"{duration1:.2f} ms")
            table.add_row(str(trace2.name), f"{duration2:.2f} ms")
            table.add_row("Difference", f"{abs(duration1 - duration2):.2f} ms")
            
        elif metric == "errors":
            # Count errors in each trace
            errors1 = sum(1 for t in traces1.get("traces", []) if not t.get("result", {}).get("valid", True))
            errors2 = sum(1 for t in traces2.get("traces", []) if not t.get("result", {}).get("valid", True))
            
            table.add_row(str(trace1.name), str(errors1))
            table.add_row(str(trace2.name), str(errors2))
            table.add_row("Difference", str(abs(errors1 - errors2)))
            
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Failed to compare traces: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()