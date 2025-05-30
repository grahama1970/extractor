"""Debug commands for the CLI application."""

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from marker.core.llm_call.cli.schemas import DebugReport, TraceInfo


debug_app = typer.Typer(help="Debug commands for validation traces")
console = Console()


@debug_app.command()
def analyze(
    trace_file: Path = typer.Argument(..., help="Path to trace file"),
    metric: str = typer.Option("all", help="Metric to analyze (duration, errors, strategies, all)"),
):
    """Analyze a validation trace file."""
    try:
        with open(trace_file, 'r') as f:
            data = json.load(f)
        
        report = DebugReport(**data)
        
        if metric == "all" or metric == "duration":
            _analyze_duration(report)
        
        if metric == "all" or metric == "errors":
            _analyze_errors(report)
        
        if metric == "all" or metric == "strategies":
            _analyze_strategies(report)
            
    except Exception as e:
        console.print(f"[red]Error analyzing trace: {e}[/red]")
        raise typer.Exit(1)


@debug_app.command()
def export(
    trace_file: Path = typer.Argument(..., help="Path to trace file"),
    output: Path = typer.Argument(..., help="Output file path"),
    format: str = typer.Option("json", help="Output format (json, csv, markdown)"),
):
    """Export trace data to different formats."""
    try:
        with open(trace_file, 'r') as f:
            data = json.load(f)
        
        report = DebugReport(**data)
        
        if format == "json":
            with open(output, 'w') as f:
                json.dump(data, f, indent=2)
        elif format == "csv":
            _export_csv(report, output)
        elif format == "markdown":
            _export_markdown(report, output)
        else:
            console.print(f"[red]Unsupported format: {format}[/red]")
            raise typer.Exit(1)
            
        console.print(f"[green]Exported to {output}[/green]")
        
    except Exception as e:
        console.print(f"[red]Error exporting trace: {e}[/red]")
        raise typer.Exit(1)


def _analyze_duration(report: DebugReport):
    """Analyze duration metrics."""
    table = Table(title="Duration Analysis")
    table.add_column("Strategy", style="cyan")
    table.add_column("Count", style="magenta")
    table.add_column("Total (ms)", style="green")
    table.add_column("Avg (ms)", style="yellow")
    table.add_column("Min (ms)", style="blue")
    table.add_column("Max (ms)", style="red")
    
    strategy_stats = {}
    
    def collect_stats(trace: TraceInfo):
        name = trace.strategy_name
        duration = trace.duration_ms or 0
        
        if name not in strategy_stats:
            strategy_stats[name] = {
                'count': 0,
                'total': 0,
                'durations': []
            }
        
        strategy_stats[name]['count'] += 1
        strategy_stats[name]['total'] += duration
        strategy_stats[name]['durations'].append(duration)
        
        for child in trace.children:
            collect_stats(child)
    
    for trace in report.traces:
        collect_stats(trace)
    
    for name, stats in strategy_stats.items():
        durations = stats['durations']
        avg = stats['total'] / stats['count'] if stats['count'] > 0 else 0
        min_val = min(durations) if durations else 0
        max_val = max(durations) if durations else 0
        
        table.add_row(
            name,
            str(stats['count']),
            f"{stats['total']:.2f}",
            f"{avg:.2f}",
            f"{min_val:.2f}",
            f"{max_val:.2f}"
        )
    
    console.print(table)


def _analyze_errors(report: DebugReport):
    """Analyze error metrics."""
    table = Table(title="Error Analysis")
    table.add_column("Strategy", style="cyan")
    table.add_column("Total", style="magenta")
    table.add_column("Errors", style="red")
    table.add_column("Success Rate", style="green")
    
    error_stats = {}
    
    def collect_errors(trace: TraceInfo):
        name = trace.strategy_name
        is_error = not trace.result.get('valid', True)
        
        if name not in error_stats:
            error_stats[name] = {
                'total': 0,
                'errors': 0
            }
        
        error_stats[name]['total'] += 1
        if is_error:
            error_stats[name]['errors'] += 1
        
        for child in trace.children:
            collect_errors(child)
    
    for trace in report.traces:
        collect_errors(trace)
    
    for name, stats in error_stats.items():
        success_rate = ((stats['total'] - stats['errors']) / stats['total'] * 100) if stats['total'] > 0 else 0
        
        table.add_row(
            name,
            str(stats['total']),
            str(stats['errors']),
            f"{success_rate:.1f}%"
        )
    
    console.print(table)


def _analyze_strategies(report: DebugReport):
    """Analyze strategy usage."""
    table = Table(title="Strategy Usage")
    table.add_column("Strategy", style="cyan")
    table.add_column("Usage Count", style="magenta")
    table.add_column("Percentage", style="green")
    
    usage_count = {}
    total = 0
    
    def count_usage(trace: TraceInfo):
        nonlocal total
        name = trace.strategy_name
        usage_count[name] = usage_count.get(name, 0) + 1
        total += 1
        
        for child in trace.children:
            count_usage(child)
    
    for trace in report.traces:
        count_usage(trace)
    
    for name, count in sorted(usage_count.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / total * 100) if total > 0 else 0
        table.add_row(name, str(count), f"{percentage:.1f}%")
    
    console.print(table)


def _export_csv(report: DebugReport, output: Path):
    """Export trace data to CSV format."""
    import csv
    
    with open(output, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Strategy', 'Start Time', 'End Time', 'Duration (ms)', 'Valid', 'Error'])
        
        def write_trace(trace: TraceInfo):
            writer.writerow([
                trace.strategy_name,
                trace.start_time,
                trace.end_time or '',
                f"{trace.duration_ms:.2f}" if trace.duration_ms else '',
                trace.result.get('valid', ''),
                trace.result.get('error', '')
            ])
            
            for child in trace.children:
                write_trace(child)
        
        for trace in report.traces:
            write_trace(trace)


def _export_markdown(report: DebugReport, output: Path):
    """Export trace data to Markdown format."""
    lines = [
        f"# Validation Trace Report",
        f"",
        f"**Generated**: {report.timestamp}",
        f"",
        f"## Summary",
        f"",
        f"Total traces: {len(report.traces)}",
        f"",
        f"## Traces",
        f""
    ]
    
    def format_trace(trace: TraceInfo, level: int = 0):
        indent = "  " * level
        lines.append(f"{indent}- **{trace.strategy_name}**")
        lines.append(f"{indent}  - Duration: {trace.duration_ms:.2f} ms" if trace.duration_ms else f"{indent}  - Duration: N/A")
        lines.append(f"{indent}  - Valid: {trace.result.get('valid', 'Unknown')}")
        
        if trace.result.get('error'):
            lines.append(f"{indent}  - Error: {trace.result['error']}")
        
        for child in trace.children:
            format_trace(child, level + 1)
    
    for trace in report.traces:
        format_trace(trace)
    
    with open(output, 'w') as f:
        f.write("\n".join(lines))