"""Debug infrastructure for validation runs.
Module: debug.py

Provides detailed tracing and debugging capabilities for the validation system.
"""

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger
from rich.console import Console
from rich.table import Table
from rich.tree import Tree

from extractor.core.llm_call.core.base import ValidationResult


@dataclass
class ValidationTrace:
    """Trace information for a validation run."""
    
    strategy_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    result: Optional[ValidationResult] = None
    context: Dict[str, Any] = field(default_factory=dict)
    children: List['ValidationTrace'] = field(default_factory=list)
    
    @property
    def duration_ms(self) -> float:
        """Get duration in milliseconds."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert trace to dictionary for serialization."""
        return {
            "strategy_name": self.strategy_name,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "result": {
                "valid": self.result.valid,
                "error": self.result.error,
                "debug_info": self.result.debug_info,
                "suggestions": self.result.suggestions
            } if self.result else None,
            "context": self.context,
            "children": [child.to_dict() for child in self.children]
        }


class DebugManager:
    """Manages debug information for validation runs."""
    
    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
        self.traces: List[ValidationTrace] = []
        self.current_trace: Optional[ValidationTrace] = None
        self.start_time = datetime.now()
        self._trace_stack: List[ValidationTrace] = []
    
    def start_trace(self, strategy_name: str, context: Dict[str, Any]) -> ValidationTrace:
        """Start a new trace.
        
        Args:
            strategy_name: Name of the validation strategy
            context: Context information for the trace
            
        Returns:
            The created ValidationTrace instance
        """
        trace = ValidationTrace(
            strategy_name=strategy_name,
            start_time=datetime.now(),
            context=context
        )
        
        if self._trace_stack:
            # Add as child of current trace
            self._trace_stack[-1].children.append(trace)
        else:
            # Add as root trace
            self.traces.append(trace)
        
        self._trace_stack.append(trace)
        self.current_trace = trace
        
        logger.debug(f"Started trace: {strategy_name} at depth {len(self._trace_stack)}")
        
        return trace
    
    def end_trace(self, result: ValidationResult) -> None:
        """End the current trace.
        
        Args:
            result: The validation result
        """
        if not self._trace_stack:
            logger.warning("No active trace to end")
            return
        
        current = self._trace_stack.pop()
        current.end_time = datetime.now()
        current.result = result
        
        logger.debug(
            f"Ended trace: {current.strategy_name} "
            f"(duration: {current.duration_ms:.2f}ms, valid: {result.valid})"
        )
        
        # Update current trace pointer
        self.current_trace = self._trace_stack[-1] if self._trace_stack else None
    
    def print_summary(self) -> None:
        """Print debug summary."""
        self.console.print("\n[bold]Validation Summary[/bold]")
        
        # Create summary table
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Strategy", style="cyan", width=30)
        table.add_column("Duration (ms)", style="magenta", justify="right")
        table.add_column("Result", style="green", justify="center")
        table.add_column("Error", style="red", width=40)
        
        # Add rows for each trace
        for trace in self.traces:
            self._add_trace_to_table(table, trace)
        
        self.console.print(table)
        
        # Print overall statistics
        total_duration = (datetime.now() - self.start_time).total_seconds() * 1000
        self.console.print(f"\n[bold]Total Duration:[/bold] {total_duration:.2f}ms")
        
        # Count successful vs failed validations
        total, successful = self._count_validations(self.traces)
        self.console.print(
            f"[bold]Validations:[/bold] {successful}/{total} successful "
            f"({(successful/total*100 if total > 0 else 0):.1f}%)"
        )
    
    def _add_trace_to_table(self, table: Table, trace: ValidationTrace, level: int = 0) -> None:
        """Add a trace to the summary table."""
        indent = "  " * level
        
        result_symbol = "" if trace.result and trace.result.valid else ""
        result_color = "green" if trace.result and trace.result.valid else "red"
        
        error_text = ""
        if trace.result and trace.result.error:
            error_text = trace.result.error[:40] + "..." if len(trace.result.error) > 40 else trace.result.error
        
        table.add_row(
            f"{indent}{trace.strategy_name}",
            f"{trace.duration_ms:.2f}",
            f"[{result_color}]{result_symbol}[/{result_color}]",
            error_text
        )
        
        # Add children
        for child in trace.children:
            self._add_trace_to_table(table, child, level + 1)
    
    def _count_validations(self, traces: List[ValidationTrace]) -> tuple[int, int]:
        """Count total and successful validations."""
        total = 0
        successful = 0
        
        for trace in traces:
            if trace.result:
                total += 1
                if trace.result.valid:
                    successful += 1
            
            # Count children
            child_total, child_successful = self._count_validations(trace.children)
            total += child_total
            successful += child_successful
        
        return total, successful
    
    def save_traces(self, file_path: Path) -> None:
        """Save traces to a JSON file.
        
        Args:
            file_path: Path to save the traces to
        """
        traces_data = {
            "start_time": self.start_time.isoformat(),
            "end_time": datetime.now().isoformat(),
            "duration_ms": (datetime.now() - self.start_time).total_seconds() * 1000,
            "traces": [trace.to_dict() for trace in self.traces]
        }
        
        with open(file_path, 'w') as f:
            json.dump(traces_data, f, indent=2)
        
        logger.info(f"Saved debug traces to: {file_path}")
    
    def visualize_trace_tree(self) -> None:
        """Visualize traces as a tree structure."""
        tree = Tree("[bold]Validation Trace Tree[/bold]")
        
        for trace in self.traces:
            self._add_trace_to_tree(tree, trace)
        
        self.console.print(tree)
    
    def _add_trace_to_tree(self, tree: Tree, trace: ValidationTrace) -> None:
        """Add a trace to the tree visualization."""
        # Create node text
        status = "" if trace.result and trace.result.valid else ""
        color = "green" if trace.result and trace.result.valid else "red"
        
        node_text = (
            f"[{color}]{status}[/{color}] {trace.strategy_name} "
            f"[dim]({trace.duration_ms:.1f}ms)[/dim]"
        )
        
        if trace.result and trace.result.error:
            node_text += f" - [red]{trace.result.error[:50]}...[/red]"
        
        # Add node to tree
        node = tree.add(node_text)
        
        # Add children
        for child in trace.children:
            self._add_trace_to_tree(node, child)


def debug_trace(func):
    """Decorator to automatically trace validation function calls.
    
    Example:
        @debug_trace
        def validate(self, response, context):
            ...
    """
    def wrapper(self, response, context):
        debug_manager = context.get("debug_manager")
        
        if debug_manager:
            trace = debug_manager.start_trace(
                strategy_name=getattr(self, "name", self.__class__.__name__),
                context={"response": str(response)[:100], **context}
            )
            
            try:
                result = func(self, response, context)
                debug_manager.end_trace(result)
                return result
            except Exception as e:
                error_result = ValidationResult(
                    valid=False,
                    error=f"Exception: {str(e)}"
                )
                debug_manager.end_trace(error_result)
                raise
        else:
            return func(self, response, context)
    
    return wrapper


def load_traces(file_path: Path) -> List[ValidationTrace]:
    """Load traces from a JSON file.
    
    Args:
        file_path: Path to the trace file
        
    Returns:
        List of ValidationTrace objects
    """
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    def dict_to_trace(trace_dict: Dict[str, Any]) -> ValidationTrace:
        """Convert dictionary to ValidationTrace."""
        trace = ValidationTrace(
            strategy_name=trace_dict["strategy_name"],
            start_time=datetime.fromisoformat(trace_dict["start_time"]),
            end_time=datetime.fromisoformat(trace_dict["end_time"]) if trace_dict["end_time"] else None,
            context=trace_dict["context"]
        )
        
        if trace_dict["result"]:
            trace.result = ValidationResult(
                valid=trace_dict["result"]["valid"],
                error=trace_dict["result"]["error"],
                debug_info=trace_dict["result"]["debug_info"],
                suggestions=trace_dict["result"]["suggestions"]
            )
        
        # Convert children
        trace.children = [dict_to_trace(child) for child in trace_dict.get("children", [])]
        
        return trace
    
    return [dict_to_trace(trace_dict) for trace_dict in data["traces"]]