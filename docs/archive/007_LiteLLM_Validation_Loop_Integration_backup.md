# Task 007: LiteLLM Validation Loop Integration ⏳ Not Started

**Objective**: Create a highly modular, flexible, and debuggable validation loop system following the 3-layer architecture that can be easily integrated into Marker and dropped into other projects like the ArangoDB experiment.

**Requirements**:
1. Follow 3-layer architecture (core/cli/mcp) for modularity
2. Create standalone package that can be dropped into any project
3. Integrate seamlessly with Marker's existing LiteLLMService
4. Support both sync and async operations
5. Include comprehensive CLI interface with rich formatting
6. **Flexible validation system**: Easy to add new validation strategies
7. **Plugin architecture**: Support for custom validators without modifying core
8. **Debug-first design**: Complete traceability of validation steps
9. **Composable validators**: Chain and combine validation strategies
10. Provide simple enable/disable mechanism
11. Default behavior should remain unchanged (only Pydantic validation)
12. **Hot-reload support**: Load new validators without restart
13. **Validation profiling**: Performance metrics for each validator
14. **A/B testing**: Support multiple validation strategies per use case

## Overview

The validation loop functionality provides intelligent retry mechanisms with custom validation strategies for LLM calls. This integration will follow the 3-layer architecture to ensure maximum modularity and reusability across projects.

### Core Implementation Approach

Based on the provided example, the system will:
1. Leverage LiteLLM's built-in `enable_json_schema_validation` for basic Pydantic validation
2. Add a flexible layer for custom validation strategies beyond JSON schema
3. Implement retry logic that can handle validation failures intelligently
4. Maintain simplicity - validation remains optional and doesn't complicate basic usage

```python
# Simple usage (like the provided example)
import litellm
from litellm import completion
from pydantic import BaseModel

litellm.enable_json_schema_validation = True

class CalendarEvent(BaseModel):
    name: str
    date: str
    participants: list[str]

resp = completion(
    model="gemini/gemini-1.5-pro",
    messages=messages,
    response_format=CalendarEvent,
)

# Advanced usage with custom validation
from llm_validation import completion_with_validation

resp = completion_with_validation(
    model="gemini/gemini-1.5-pro",
    messages=messages,
    response_format=CalendarEvent,
    validation_strategies=[
        validate_participants_count,  # Custom validator
        validate_date_format,        # Custom validator
    ],
    max_retries=3
)
```

**IMPORTANT**: 
1. Each sub-task MUST include creation of a verification report in `/docs/reports/` with actual command outputs and performance results.
2. Task 8 (Final Verification) enforces MANDATORY iteration on ALL incomplete tasks. The agent MUST continue working until 100% completion is achieved - no partial completion is acceptable.

## Architecture Design

Following the 3-layer architecture with emphasis on flexibility and debuggability:

```
llm_validation/
├── core/                   # Pure validation logic (plugin-based)
│   ├── __init__.py
│   ├── base.py            # Abstract base classes & protocols
│   ├── retry.py           # Retry mechanisms with hooks
│   ├── strategies.py      # Strategy registry & loader
│   ├── pipeline.py        # Validation pipeline orchestration
│   ├── debug.py           # Debugging infrastructure
│   ├── validators/        # Pluggable validators
│   │   ├── __init__.py
│   │   ├── base.py        # Base validator classes
│   │   ├── text.py        # Text validators
│   │   ├── structure.py   # Structure validators
│   │   ├── content.py     # Content validators
│   │   └── custom/        # User-defined validators
│   └── utils.py           # Utilities & helpers
├── cli/                   # CLI with typer and rich
│   ├── __init__.py
│   ├── app.py             # Typer app
│   ├── formatters.py      # Rich formatting & debug output
│   ├── validators.py      # Input validators
│   ├── debug_commands.py  # Debug/inspection commands
│   └── schemas.py         # Pydantic models
└── mcp/                   # MCP integration (future)
    ├── __init__.py
    ├── schema.py          # JSON schemas
    └── wrapper.py         # FastMCP wrapper
```

### Key Design Principles

1. **Plugin Architecture**: 
   - Validators are plugins that can be dynamically loaded
   - Custom validators can be added without modifying core
   - Strategy registry allows runtime discovery
   - Decorators for easy validator registration

2. **Debug-First Design**:
   - Every validation step is traceable
   - Debug mode provides detailed execution flow
   - Validation context carries debugging information
   - Built-in profiling and metrics

3. **Flexible Composition**:
   - Validators can be chained and composed
   - Conditional validation based on context
   - Multiple validation strategies per use case
   - Easy A/B testing of strategies

4. **Extension Points**:
   - Custom retry strategies
   - Custom validators
   - Custom formatters
   - Custom debug handlers

## Verification Requirements

**CRITICAL**: For each task, verification MUST include:

1. **Actual Python Function Outputs**: 
   - Raw outputs from function executions (not theoretical or expected outputs)
   - Screenshots or logs showing actual function return values
   - Variable state dumps during critical operations

2. **Actual CLI Command Outputs**:
   - Terminal outputs from running CLI commands (not simulated outputs)
   - Complete command logs including errors and warnings
   - Performance data from real executions

3. **Verification Standards**:
   - NO hypothetical outputs allowed - all results must be from actual execution
   - NO ambiguous results - all outputs must show clear success/failure status
   - NO partial verification - both function and CLI outputs must be validated
   - If execution produces errors, include complete error messages and resolution steps

4. **Reproducibility Requirements**:
   - Include environment details (Python version, dependency versions)
   - Document exact steps to reproduce each verification
   - Include timing information for performance-sensitive operations

Each task is considered incomplete until BOTH Python function outputs AND CLI command outputs are verified with actual execution results. Theoretical, expected, or simulated outputs are NOT acceptable.

## Mandatory Project Compliance Verification

**CRITICAL REQUIREMENT**: Every implementation MUST be verified against project standards:

1. **Code Style and Syntax Compliance**:
   - ALL code MUST be verified against rules in `/home/graham/workspace/experiments/marker/docs/INDEX.md`
   - No exceptions or deviations from project standards are permitted
   - Verification must be documented with specific references to relevant sections of the INDEX.md

2. **Verification Process**:
   - Before submitting any task as complete, run verification against project standards
   - Document compliance point-by-point in the verification report
   - Include any automated linting or verification tool outputs
   - Address ANY deviation, no matter how minor

3. **Documentation in Verification Reports**:
   - Each verification report MUST include a "Project Compliance" section
   - This section MUST list each relevant rule from INDEX.md and how the implementation complies
   - Any exceptions must be explicitly approved and documented with justification

This verification against project standards is MANDATORY for ALL tasks - no exceptions.

## MANDATORY Research Process

**CRITICAL REQUIREMENT**: For EACH task, the agent MUST:

1. **ALWAYS prioritize current documentation and repository code** over model training data:
   - Model training data is often outdated for code projects
   - MUST verify all implementation details against current documentation links
   - When documentation and model knowledge conflict, documentation ALWAYS takes precedence
   - Implementations MUST follow patterns from actual repository code, not theoretical patterns

2. **Use `perplexity_ask`** to research:
   - 3-layer architecture patterns for Python packages
   - Modular validation system designs
   - CLI design patterns with typer and rich
   - Best practices for drop-in modules

3. **Use `WebSearch`** to find:
   - GitHub repos with modular LLM validation
   - Examples of 3-layer architecture implementations
   - Drop-in Python package patterns
   - CLI tools with typer and rich

4. **Document all findings** in task reports:
   - Links to source repositories
   - Code snippets that work
   - Architecture patterns
   - Integration examples
   - **Version information and documentation dates** to ensure currency

Example Research Queries:
```
perplexity_ask: "python 3 layer architecture modular package design 2024"
WebSearch: "site:github.com typer rich cli validation module"
```

## Implementation Tasks (Ordered by Priority/Complexity)

### Task 1: Create Core Layer with Flexible Validation ⏳ Not Started

**Priority**: HIGH | **Complexity**: MEDIUM | **Impact**: HIGH

**Research Requirements**:
- [ ] Use `perplexity_ask` to find "plugin architecture patterns python 2024"
- [ ] Use `WebSearch` for "modular validation strategy pattern github"
- [ ] Search GitHub for "python debug validation pipeline"
- [ ] Find best practices for extensible validation systems

**Implementation Steps**:
- [ ] 1.1 Create package structure
  - Create `/marker/llm_validation/` directory
  - Create `core/` subdirectory
  - Add `__init__.py` files
  - Create `setup.py` for standalone installation
  - Add pyproject.toml configuration

- [ ] 1.2 Design flexible validation interface
  - Create `core/base.py` with abstract base classes
  
  ```python
  # core/base.py
  from abc import ABC, abstractmethod
  from typing import Any, Dict, Optional, Protocol
  from dataclasses import dataclass
  from pydantic import BaseModel
  
  @dataclass
  class ValidationResult:
      valid: bool
      error: Optional[str] = None
      debug_info: Optional[Dict[str, Any]] = None
      suggestions: Optional[list[str]] = None
  
  class ValidationStrategy(Protocol):
      """Protocol for validation strategies."""
      
      def validate(self, response: Any, context: Dict[str, Any]) -> ValidationResult:
          """Validate the response."""
          ...
      
      @property
      def name(self) -> str:
          """Strategy name for debugging."""
          ...
  
  class AsyncValidationStrategy(Protocol):
      """Protocol for async validation strategies."""
      
      async def validate(self, response: Any, context: Dict[str, Any]) -> ValidationResult:
          """Validate the response asynchronously."""
          ...
  ```

- [ ] 1.3 Implement retry mechanism with debugging
  - Create `core/retry.py`
  
  ```python
  # core/retry.py
  import asyncio
  from typing import Callable, List, Optional, Any
  from dataclasses import dataclass
  from loguru import logger
  import litellm
  from .base import ValidationStrategy, ValidationResult
  
  @dataclass
  class RetryConfig:
      max_attempts: int = 3
      backoff_factor: float = 2.0
      initial_delay: float = 1.0
      max_delay: float = 60.0
      debug_mode: bool = False
  
  async def retry_with_validation(
      llm_call: Callable,
      messages: List[Dict[str, str]],
      response_format: BaseModel,
      validation_strategies: List[ValidationStrategy],
      config: RetryConfig = RetryConfig()
  ) -> Any:
      """Retry LLM calls with validation."""
      litellm.enable_json_schema_validation = True
      
      for attempt in range(config.max_attempts):
          try:
              if config.debug_mode:
                  logger.debug(f"Attempt {attempt + 1}/{config.max_attempts}")
              
              # Make LLM call
              response = await llm_call(
                  messages=messages,
                  response_format=response_format
              )
              
              # Apply validation strategies
              all_valid = True
              validation_errors = []
              
              for strategy in validation_strategies:
                  result = strategy.validate(response, {"attempt": attempt})
                  
                  if config.debug_mode:
                      logger.debug(f"{strategy.name}: {result}")
                  
                  if not result.valid:
                      all_valid = False
                      validation_errors.append(result.error)
              
              if all_valid:
                  return response
              
              # Add validation feedback to conversation
              messages.append({
                  "role": "assistant",
                  "content": str(response)
              })
              messages.append({
                  "role": "user",
                  "content": f"Please fix these validation errors: {'; '.join(validation_errors)}"
              })
              
              # Calculate delay
              delay = min(
                  config.initial_delay * (config.backoff_factor ** attempt),
                  config.max_delay
              )
              await asyncio.sleep(delay)
              
          except Exception as e:
              logger.error(f"Attempt {attempt + 1} failed: {e}")
              if attempt == config.max_attempts - 1:
                  raise
      
      raise Exception(f"Failed after {config.max_attempts} attempts")
  ```

- [ ] 1.4 Create pluggable validation system
  - Create `core/strategies.py`
  
  ```python
  # core/strategies.py
  from typing import Dict, Type, Any
  from .base import ValidationStrategy, ValidationResult
  import importlib
  import inspect
  from pathlib import Path
  
  class StrategyRegistry:
      """Registry for validation strategies."""
      
      def __init__(self):
          self._strategies: Dict[str, Type[ValidationStrategy]] = {}
          self._instances: Dict[str, ValidationStrategy] = {}
      
      def register(self, name: str, strategy_class: Type[ValidationStrategy]):
          """Register a validation strategy."""
          self._strategies[name] = strategy_class
      
      def get(self, name: str, **kwargs) -> ValidationStrategy:
          """Get a strategy instance."""
          if name not in self._instances:
              if name not in self._strategies:
                  raise ValueError(f"Strategy '{name}' not found")
              self._instances[name] = self._strategies[name](**kwargs)
          return self._instances[name]
      
      def discover_strategies(self, path: Path):
          """Discover and load strategies from a directory."""
          for py_file in path.glob("*.py"):
              if py_file.name.startswith("_"):
                  continue
              
              module_name = py_file.stem
              module = importlib.import_module(f".{module_name}", package=path.parent.name)
              
              for name, obj in inspect.getmembers(module):
                  if (inspect.isclass(obj) and 
                      issubclass(obj, ValidationStrategy) and 
                      obj != ValidationStrategy):
                      self.register(name.lower(), obj)
  
  # Global registry
  registry = StrategyRegistry()
  
  # Decorator for easy registration
  def validator(name: str):
      """Decorator to register a validator."""
      def decorator(cls):
          registry.register(name, cls)
          return cls
      return decorator
  ```

- [ ] 1.5 Build debugging infrastructure
  - Create `core/debug.py`
  
  ```python
  # core/debug.py
  from dataclasses import dataclass, field
  from typing import List, Dict, Any, Optional
  from datetime import datetime
  import json
  from rich.console import Console
  from rich.table import Table
  from rich.tree import Tree
  
  @dataclass
  class ValidationTrace:
      """Trace information for a validation run."""
      strategy_name: str
      start_time: datetime
      end_time: Optional[datetime] = None
      result: Optional[ValidationResult] = None
      context: Dict[str, Any] = field(default_factory=dict)
      children: List['ValidationTrace'] = field(default_factory=list)
  
  class DebugManager:
      """Manages debug information for validation runs."""
      
      def __init__(self, console: Console = None):
          self.console = console or Console()
          self.traces: List[ValidationTrace] = []
          self.current_trace: Optional[ValidationTrace] = None
      
      def start_trace(self, strategy_name: str, context: Dict[str, Any]):
          """Start a new trace."""
          trace = ValidationTrace(
              strategy_name=strategy_name,
              start_time=datetime.now(),
              context=context
          )
          
          if self.current_trace:
              self.current_trace.children.append(trace)
          else:
              self.traces.append(trace)
          
          self.current_trace = trace
          return trace
      
      def end_trace(self, result: ValidationResult):
          """End the current trace."""
          if self.current_trace:
              self.current_trace.end_time = datetime.now()
              self.current_trace.result = result
              
              # Move up to parent
              parent = None
              for trace in self.traces:
                  if self.current_trace in trace.children:
                      parent = trace
                      break
              self.current_trace = parent
      
      def print_summary(self):
          """Print debug summary."""
          table = Table(title="Validation Summary")
          table.add_column("Strategy", style="cyan")
          table.add_column("Duration (ms)", style="magenta")
          table.add_column("Result", style="green")
          table.add_column("Error", style="red")
          
          for trace in self.traces:
              self._add_trace_to_table(table, trace)
          
          self.console.print(table)
      
      def _add_trace_to_table(self, table: Table, trace: ValidationTrace, level: int = 0):
          """Add a trace to the summary table."""
          duration = (trace.end_time - trace.start_time).total_seconds() * 1000 if trace.end_time else 0
          indent = "  " * level
          
          table.add_row(
              f"{indent}{trace.strategy_name}",
              f"{duration:.2f}",
              "✓" if trace.result and trace.result.valid else "✗",
              trace.result.error if trace.result and trace.result.error else ""
          )
          
          for child in trace.children:
              self._add_trace_to_table(table, child, level + 1)
  ```

- [ ] 1.6 Implement core validators
  - Create `core/validators/` directory
  
  ```python
  # core/validators/text.py
  from ..base import ValidationResult
  from ..strategies import validator
  
  @validator("length_check")
  class LengthValidator:
      """Validates text length."""
      
      def __init__(self, min_length: int = 10, max_length: int = 1000):
          self.min_length = min_length
          self.max_length = max_length
      
      @property
      def name(self) -> str:
          return f"length_check({self.min_length}-{self.max_length})"
      
      def validate(self, response: Any, context: Dict[str, Any]) -> ValidationResult:
          text = str(response)
          length = len(text.split())
          
          if length < self.min_length:
              return ValidationResult(
                  valid=False,
                  error=f"Response too short: {length} words (min: {self.min_length})",
                  debug_info={"word_count": length}
              )
          
          if length > self.max_length:
              return ValidationResult(
                  valid=False,
                  error=f"Response too long: {length} words (max: {self.max_length})",
                  debug_info={"word_count": length}
              )
          
          return ValidationResult(valid=True, debug_info={"word_count": length})
  
  @validator("required_fields")
  class RequiredFieldsValidator:
      """Validates that required fields are present."""
      
      def __init__(self, fields: List[str]):
          self.fields = fields
      
      @property
      def name(self) -> str:
          return f"required_fields({','.join(self.fields)})"
      
      def validate(self, response: Any, context: Dict[str, Any]) -> ValidationResult:
          if hasattr(response, '__dict__'):
              response_dict = response.__dict__
          else:
              response_dict = response
          
          missing_fields = []
          for field in self.fields:
              if field not in response_dict or response_dict[field] is None:
                  missing_fields.append(field)
          
          if missing_fields:
              return ValidationResult(
                  valid=False,
                  error=f"Missing required fields: {', '.join(missing_fields)}",
                  debug_info={"missing_fields": missing_fields}
              )
          
          return ValidationResult(valid=True)
  ```

- [ ] 1.7 Add validation utilities
  - Create `core/utils.py`
  
  ```python
  # core/utils.py
  from typing import Dict, Any, List
  import json
  from pathlib import Path
  
  def load_config(path: Path) -> Dict[str, Any]:
      """Load configuration from JSON file."""
      with open(path) as f:
          return json.load(f)
  
  def save_validation_report(traces: List[ValidationTrace], path: Path):
      """Save validation traces to a report file."""
      report = {
          "timestamp": datetime.now().isoformat(),
          "traces": [_trace_to_dict(trace) for trace in traces]
      }
      
      with open(path, 'w') as f:
          json.dump(report, f, indent=2)
  
  def _trace_to_dict(trace: ValidationTrace) -> Dict[str, Any]:
      """Convert trace to dictionary."""
      return {
          "strategy_name": trace.strategy_name,
          "start_time": trace.start_time.isoformat(),
          "end_time": trace.end_time.isoformat() if trace.end_time else None,
          "duration_ms": (trace.end_time - trace.start_time).total_seconds() * 1000 if trace.end_time else None,
          "result": {
              "valid": trace.result.valid,
              "error": trace.result.error,
              "debug_info": trace.result.debug_info
          } if trace.result else None,
          "context": trace.context,
          "children": [_trace_to_dict(child) for child in trace.children]
      }
  ```

- [ ] 1.8 Create comprehensive tests
  - Test plugin architecture
  - Verify dynamic loading
  - Test debug features
  - Check performance impact
  - Test edge cases
  - Validate extensibility

- [ ] 1.9 Create verification report
  - Create `/docs/reports/007_task_1_core_layer.md`
  - Document plugin architecture
  - Show debugging examples
  - Include performance metrics
  - List extension points

- [ ] 1.10 Git commit feature

**Technical Specifications**:
- Plugin-based architecture
- Full debugging support
- Strategy hot-reloading
- Minimal dependencies
- Under 300 lines per file
- Type-safe interfaces

**Verification Method**:
- Plugin loading tests
- Debug output validation
- Performance benchmarks
- Extension point tests

**Acceptance Criteria**:
- Easy to add new validators
- Debugging tools working
- Plugin system functional
- All tests pass
- Documentation complete

### Task 2: Create CLI Layer ⏳ Not Started

**Priority**: HIGH | **Complexity**: MEDIUM | **Impact**: HIGH

**Research Requirements**:
- [ ] Use `perplexity_ask` for "typer rich cli best practices"
- [ ] Use `WebSearch` for "python cli tools 3 layer architecture"
- [ ] Find examples of modular CLI tools
- [ ] Research rich formatting patterns

**Implementation Steps**:
- [ ] 2.1 Create CLI structure
  - Create `cli/` directory
  - Add `__init__.py` file
  - Create main app structure
  - Set up imports from core
  - Configure package exports

- [ ] 2.2 Implement Typer app
  - Create `cli/app.py`
  
  ```python
  # cli/app.py
  import typer
  from typing import List, Optional
  from pathlib import Path
  from rich.console import Console
  from rich.table import Table
  
  from ..core import registry, retry_with_validation, RetryConfig
  from ..core.debug import DebugManager
  from .formatters import print_validation_result, print_strategies
  from .schemas import ValidationRequest
  
  app = typer.Typer(
      name="llm-validate",
      help="LLM validation with retry and custom strategies",
      add_completion=False,
  )
  console = Console()
  
  @app.command()
  def validate(
      prompt: str = typer.Argument(..., help="LLM prompt to validate"),
      model: str = typer.Option("gemini/gemini-1.5-pro", help="LLM model to use"),
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
                  strategy = registry.get(validator_name)
                  strategies.append(strategy)
              except ValueError as e:
                  console.print(f"[red]Error loading validator '{validator_name}': {e}[/red]")
                  raise typer.Exit(1)
          
          # Create validation request
          request = ValidationRequest(
              prompt=prompt,
              model=model,
              strategies=strategies,
              config=RetryConfig(max_attempts=max_retries, debug_mode=debug)
          )
          
          # Run validation
          result = retry_with_validation(
              llm_call=lambda messages, response_format: completion(
                  model=request.model,
                  messages=messages,
                  response_format=response_format
              ),
              messages=[{"role": "user", "content": request.prompt}],
              response_format=None,  # Will be set based on use case
              validation_strategies=request.strategies,
              config=request.config
          )
          
          # Display results
          print_validation_result(result, console)
          
          # Show debug info if enabled
          if debug_manager:
              debug_manager.print_summary()
          
          # Save output if requested
          if output:
              save_results(result, output)
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
          registry.load_from_file(path, name)
          console.print(f"[green]Validator loaded from {path}[/green]")
      except Exception as e:
          console.print(f"[red]Failed to load validator: {e}[/red]")
          raise typer.Exit(1)
  
  @app.command()
  def debug(
      trace_file: Path = typer.Argument(..., help="Path to debug trace file"),
  ):
      """Analyze a debug trace file."""
      try:
          traces = load_traces(trace_file)
          debug_manager = DebugManager(console)
          debug_manager.traces = traces
          debug_manager.print_summary()
      except Exception as e:
          console.print(f"[red]Failed to load trace file: {e}[/red]")
          raise typer.Exit(1)
  
  if __name__ == "__main__":
      app()
  ```

- [ ] 2.3 Create formatters
  - Create `cli/formatters.py`
  
  ```python
  # cli/formatters.py
  from rich.console import Console
  from rich.table import Table
  from rich.panel import Panel
  from rich.syntax import Syntax
  from typing import Any, List, Dict
  from ..core.base import ValidationResult
  
  def print_validation_result(result: Any, console: Console):
      """Pretty print validation result."""
      if hasattr(result, '__dict__'):
          # Pydantic model
          data = result.dict() if hasattr(result, 'dict') else result.__dict__
          syntax = Syntax(
              json.dumps(data, indent=2),
              "json",
              theme="monokai",
              line_numbers=True
          )
          console.print(Panel(syntax, title="Validation Result", border_style="green"))
      else:
          # Plain response
          console.print(Panel(str(result), title="Validation Result", border_style="green"))
  
  def print_strategies(strategies: List[Dict[str, Any]], console: Console):
      """Print available strategies in a table."""
      table = Table(title="Available Validation Strategies")
      table.add_column("Name", style="cyan")
      table.add_column("Description", style="white")
      table.add_column("Parameters", style="yellow")
      
      for strategy in strategies:
          params = ", ".join(f"{k}={v}" for k, v in strategy.get("params", {}).items())
          table.add_row(
              strategy["name"],
              strategy.get("description", "No description"),
              params or "None"
          )
      
      console.print(table)
  
  def print_validation_error(error: ValidationResult, console: Console):
      """Print validation error with details."""
      console.print(f"[red]✗[/red] Validation failed: {error.error}")
      
      if error.debug_info:
          console.print("Debug info:")
          for key, value in error.debug_info.items():
              console.print(f"  {key}: {value}")
      
      if error.suggestions:
          console.print("Suggestions:")
          for suggestion in error.suggestions:
              console.print(f"  • {suggestion}")
  
  def print_progress(current: int, total: int, message: str, console: Console):
      """Print progress bar."""
      progress = current / total
      bar_length = 30
      filled = int(bar_length * progress)
      bar = "█" * filled + "░" * (bar_length - filled)
      
      console.print(f"\r[{bar}] {current}/{total} - {message}", end="")
  ```

- [ ] 2.4 Add input validators
  - Create `cli/validators.py`
  
  ```python
  # cli/validators.py
  import typer
  from pathlib import Path
  from typing import List
  
  def validate_file_path(path: Path) -> Path:
      """Validate that a file path exists."""
      if not path.exists():
          raise typer.BadParameter(f"File does not exist: {path}")
      if not path.is_file():
          raise typer.BadParameter(f"Path is not a file: {path}")
      return path
  
  def validate_directory_path(path: Path) -> Path:
      """Validate that a directory path exists."""
      if not path.exists():
          raise typer.BadParameter(f"Directory does not exist: {path}")
      if not path.is_dir():
          raise typer.BadParameter(f"Path is not a directory: {path}")
      return path
  
  def validate_validators(validators: List[str]) -> List[str]:
      """Validate that validator names are valid."""
      from ..core import registry
      
      invalid = []
      for validator in validators:
          try:
              registry.get(validator)
          except ValueError:
              invalid.append(validator)
      
      if invalid:
          raise typer.BadParameter(f"Invalid validators: {', '.join(invalid)}")
      
      return validators
  
  def validate_model_name(model: str) -> str:
      """Validate model name format."""
      if "/" not in model:
          raise typer.BadParameter(
              f"Model must be in provider/model format (e.g., 'openai/gpt-4'): {model}"
          )
      return model
  ```

- [ ] 2.5 Define schemas
  - Create `cli/schemas.py`
  
  ```python
  # cli/schemas.py
  from pydantic import BaseModel, Field
  from typing import List, Optional, Dict, Any
  from ..core.base import ValidationStrategy
  from ..core.retry import RetryConfig
  
  class ValidationRequest(BaseModel):
      """Request schema for validation."""
      prompt: str = Field(..., description="LLM prompt to validate")
      model: str = Field(..., description="LLM model to use")
      strategies: List[ValidationStrategy] = Field(
          default_factory=list,
          description="Validation strategies to apply"
      )
      config: RetryConfig = Field(
          default_factory=RetryConfig,
          description="Retry configuration"
      )
  
  class ValidationResponse(BaseModel):
      """Response schema for validation results."""
      success: bool = Field(..., description="Whether validation succeeded")
      result: Optional[Dict[str, Any]] = Field(None, description="LLM response")
      attempts: int = Field(..., description="Number of attempts made")
      errors: List[str] = Field(default_factory=list, description="Validation errors")
      duration_ms: float = Field(..., description="Total duration in milliseconds")
      trace_id: Optional[str] = Field(None, description="Debug trace ID")
  
  class StrategyInfo(BaseModel):
      """Information about a validation strategy."""
      name: str = Field(..., description="Strategy name")
      description: str = Field(..., description="Strategy description")
      parameters: Dict[str, Any] = Field(
          default_factory=dict,
          description="Strategy parameters"
      )
      examples: List[str] = Field(
          default_factory=list,
          description="Usage examples"
      )
  
  class ConfigSchema(BaseModel):
      """Configuration schema for the CLI."""
      default_model: str = Field(
          "gemini/gemini-1.5-pro",
          description="Default LLM model"
      )
      max_retries: int = Field(3, description="Default max retries")
      timeout: float = Field(30.0, description="Request timeout")
      debug_mode: bool = Field(False, description="Enable debug by default")
      validator_paths: List[Path] = Field(
          default_factory=list,
          description="Paths to custom validator directories"
      )
  ```

- [ ] 2.6 Create debug commands
  - Create `cli/debug_commands.py`
  
  ```python
  # cli/debug_commands.py
  import typer
  from pathlib import Path
  from rich.console import Console
  from rich.tree import Tree
  from rich.syntax import Syntax
  
  debug_app = typer.Typer(help="Debug and inspection commands")
  console = Console()
  
  @debug_app.command()
  def trace(
      trace_file: Path,
      filter_strategy: Optional[str] = None,
      show_errors_only: bool = False,
  ):
      """Visualize a debug trace file."""
      traces = load_traces(trace_file)
      tree = Tree("Validation Trace")
      
      for trace in traces:
          if filter_strategy and trace.strategy_name != filter_strategy:
              continue
          if show_errors_only and trace.result and trace.result.valid:
              continue
          
          add_trace_to_tree(tree, trace)
      
      console.print(tree)
  
  @debug_app.command()
  def compare(
      trace1: Path,
      trace2: Path,
      metric: str = "duration",
  ):
      """Compare two debug traces."""
      traces1 = load_traces(trace1)
      traces2 = load_traces(trace2)
      
      comparison = compare_traces(traces1, traces2, metric)
      print_comparison(comparison, console)
  
  @debug_app.command()
  def export(
      trace_file: Path,
      output: Path,
      format: str = "json",
  ):
      """Export trace to different formats."""
      traces = load_traces(trace_file)
      
      if format == "json":
          export_json(traces, output)
      elif format == "csv":
          export_csv(traces, output)
      elif format == "html":
          export_html(traces, output)
      else:
          raise typer.BadParameter(f"Unknown format: {format}")
      
      console.print(f"[green]Exported to {output}[/green]")
  ```

- [ ] 2.7 Create CLI tests
  - Test all commands
  - Verify output formatting
  - Test error handling
  - Check help text
  - Validate configurations

- [ ] 2.8 Create verification report
  - Create `/docs/reports/007_task_2_cli_layer.md`
  - Document CLI interface
  - Show example commands
  - Include output samples
  - List all options

- [ ] 2.9 Git commit feature

**Technical Specifications**:
- Typer for CLI framework
- Rich for formatting
- Clear command structure
- Comprehensive help
- Intuitive interface

**Verification Method**:
- CLI integration tests
- Manual command testing
- Output validation
- Error handling tests

**Example CLI Usage**:
```bash
# List available validators
llm-validate list-validators

# Validate with specific strategies
llm-validate validate "Summarize this text" \
  --validators length_check,required_fields \
  --max-retries 5 \
  --debug

# Add custom validator
llm-validate add-validator ./custom_validators/citation_check.py

# Debug a validation run
llm-validate debug trace.json --show-errors-only

# Compare two traces
llm-validate debug compare trace1.json trace2.json --metric duration
```

**Acceptance Criteria**:
- All commands working
- Rich formatting applied
- Help text comprehensive
- Tests passing

### Task 3: Create Processor-Specific Validators ⏳ Not Started

**Priority**: MEDIUM | **Complexity**: MEDIUM | **Impact**: HIGH

**Research Requirements**:
- [ ] Use `perplexity_ask` for "llm output validation patterns table math image"
- [ ] Use `WebSearch` for "pydantic custom validators"
- [ ] Find domain-specific validation examples
- [ ] Research table/image/math validation patterns

**Implementation Steps**:
- [ ] 3.1 Create table validators
  - Validate HTML structure
  
  ```python
  # llm_validation/validators/table.py
  from bs4 import BeautifulSoup
  from ..base import ValidationResult
  from ..strategies import validator
  from typing import Dict, Any
  
  @validator("table_structure")
  class TableStructureValidator:
      """Validates HTML table structure."""
      
      def __init__(self, min_rows: int = 1, min_cols: int = 1):
          self.min_rows = min_rows
          self.min_cols = min_cols
      
      @property
      def name(self) -> str:
          return f"table_structure(rows>={self.min_rows}, cols>={self.min_cols})"
      
      def validate(self, response: Any, context: Dict[str, Any]) -> ValidationResult:
          html = response.get("table_html", "")
          
          try:
              soup = BeautifulSoup(html, 'html.parser')
              table = soup.find('table')
              
              if not table:
                  return ValidationResult(
                      valid=False,
                      error="No table tag found in HTML",
                      suggestions=["Ensure response contains <table> tag"]
                  )
              
              rows = table.find_all('tr')
              if len(rows) < self.min_rows:
                  return ValidationResult(
                      valid=False,
                      error=f"Table has {len(rows)} rows, minimum {self.min_rows} required",
                      debug_info={"row_count": len(rows)}
                  )
              
              # Check column consistency
              col_counts = []
              for row in rows:
                  cells = row.find_all(['td', 'th'])
                  col_counts.append(len(cells))
              
              if col_counts and min(col_counts) < self.min_cols:
                  return ValidationResult(
                      valid=False,
                      error=f"Table has inconsistent columns: {col_counts}",
                      debug_info={"column_counts": col_counts}
                  )
              
              return ValidationResult(
                  valid=True,
                  debug_info={
                      "row_count": len(rows),
                      "column_counts": col_counts
                  }
              )
              
          except Exception as e:
              return ValidationResult(
                  valid=False,
                  error=f"HTML parsing error: {str(e)}",
                  suggestions=["Check HTML syntax"]
              )
  
  @validator("table_completeness")
  class TableCompletenessValidator:
      """Validates table has no empty cells."""
      
      @property
      def name(self) -> str:
          return "table_completeness"
      
      def validate(self, response: Any, context: Dict[str, Any]) -> ValidationResult:
          html = response.get("table_html", "")
          
          try:
              soup = BeautifulSoup(html, 'html.parser')
              empty_cells = []
              
              for i, row in enumerate(soup.find_all('tr')):
                  for j, cell in enumerate(row.find_all(['td', 'th'])):
                      if not cell.text.strip():
                          empty_cells.append((i, j))
              
              if empty_cells:
                  return ValidationResult(
                      valid=False,
                      error=f"Found {len(empty_cells)} empty cells",
                      debug_info={"empty_cells": empty_cells},
                      suggestions=[f"Fill empty cell at row {r}, col {c}" for r, c in empty_cells[:3]]
                  )
              
              return ValidationResult(valid=True)
              
          except Exception as e:
              return ValidationResult(
                  valid=False,
                  error=f"Table validation error: {str(e)}"
              )
  ```

- [ ] 3.2 Create image description validators
  
  ```python
  # llm_validation/validators/image.py
  from ..base import ValidationResult
  from ..strategies import validator
  import re
  
  @validator("image_description_quality")
  class ImageDescriptionValidator:
      """Validates image description quality."""
      
      def __init__(
          self, 
          min_words: int = 20,
          max_words: int = 200,
          required_elements: list[str] = None
      ):
          self.min_words = min_words
          self.max_words = max_words
          self.required_elements = required_elements or []
      
      @property
      def name(self) -> str:
          return f"image_description_quality({self.min_words}-{self.max_words} words)"
      
      def validate(self, response: Any, context: Dict[str, Any]) -> ValidationResult:
          description = response.get("image_description", "")
          words = description.split()
          word_count = len(words)
          
          # Check word count
          if word_count < self.min_words:
              return ValidationResult(
                  valid=False,
                  error=f"Description too short: {word_count} words (min: {self.min_words})",
                  suggestions=[f"Add more detail - at least {self.min_words - word_count} more words"]
              )
          
          if word_count > self.max_words:
              return ValidationResult(
                  valid=False,
                  error=f"Description too long: {word_count} words (max: {self.max_words})",
                  suggestions=[f"Remove {word_count - self.max_words} words"]
              )
          
          # Check required elements
          missing_elements = []
          for element in self.required_elements:
              if element.lower() not in description.lower():
                  missing_elements.append(element)
          
          if missing_elements:
              return ValidationResult(
                  valid=False,
                  error=f"Missing required elements: {', '.join(missing_elements)}",
                  suggestions=[f"Include {element} in description" for element in missing_elements]
              )
          
          return ValidationResult(
              valid=True,
              debug_info={"word_count": word_count}
          )
  
  @validator("image_technical_details")
  class ImageTechnicalValidator:
      """Validates technical aspects of image descriptions."""
      
      @property
      def name(self) -> str:
          return "image_technical_details"
      
      def validate(self, response: Any, context: Dict[str, Any]) -> ValidationResult:
          description = response.get("image_description", "")
          
          # Check for specific technical details
          checks = {
              "dimensions": r"\d+\s*x\s*\d+",
              "color_info": r"(color|colour|grayscale|black.?and.?white)",
              "object_count": r"\d+\s+(objects?|items?|elements?)",
          }
          
          missing = []
          for check_name, pattern in checks.items():
              if not re.search(pattern, description, re.IGNORECASE):
                  missing.append(check_name)
          
          if missing:
              return ValidationResult(
                  valid=False,
                  error=f"Missing technical details: {', '.join(missing)}",
                  suggestions=[f"Include {detail}" for detail in missing]
              )
          
          return ValidationResult(valid=True)
  ```

- [ ] 3.3 Create math validators
  
  ```python
  # llm_validation/validators/math.py
  from ..base import ValidationResult
  from ..strategies import validator
  import re
  
  @validator("latex_syntax")
  class LatexSyntaxValidator:
      """Validates LaTeX equation syntax."""
      
      @property
      def name(self) -> str:
          return "latex_syntax"
      
      def validate(self, response: Any, context: Dict[str, Any]) -> ValidationResult:
          equation = response.get("equation", "")
          
          # Check for common LaTeX errors
          errors = []
          
          # Unmatched braces
          if equation.count('{') != equation.count('}'):
              errors.append("Unmatched curly braces")
          
          # Unmatched brackets
          if equation.count('[') != equation.count(']'):
              errors.append("Unmatched square brackets")
          
          # Unmatched parentheses
          if equation.count('(') != equation.count(')'):
              errors.append("Unmatched parentheses")
          
          # Check for proper fencing
          if not (equation.startswith('$') and equation.endswith('$')):
              errors.append("Equation not properly fenced with $ symbols")
          
          # Common LaTeX command errors
          invalid_commands = re.findall(r'\\[a-zA-Z]+(?![a-zA-Z{])', equation)
          known_commands = ['\\frac', '\\sqrt', '\\sum', '\\int', '\\alpha', '\\beta']
          for cmd in invalid_commands:
              if cmd not in known_commands:
                  errors.append(f"Unknown LaTeX command: {cmd}")
          
          if errors:
              return ValidationResult(
                  valid=False,
                  error="LaTeX syntax errors found",
                  debug_info={"errors": errors},
                  suggestions=errors
              )
          
          return ValidationResult(valid=True)
  
  @validator("math_completeness")
  class MathCompletenessValidator:
      """Validates mathematical equation completeness."""
      
      @property
      def name(self) -> str:
          return "math_completeness"
      
      def validate(self, response: Any, context: Dict[str, Any]) -> ValidationResult:
          equation = response.get("equation", "")
          
          # Check for incomplete patterns
          incomplete_patterns = [
              (r'=\s*$', "Equation ends with equals sign"),
              (r'[+\-*/]\s*$', "Equation ends with operator"),
              (r'^\s*[+\-*/]', "Equation starts with operator"),
              (r'\.\.\.$', "Equation trails off with ellipsis"),
          ]
          
          for pattern, error in incomplete_patterns:
              if re.search(pattern, equation):
                  return ValidationResult(
                      valid=False,
                      error=error,
                      suggestions=["Complete the equation"]
                  )
          
          return ValidationResult(valid=True)
  ```

- [ ] 3.4 Create code validators
  
  ```python
  # llm_validation/validators/code.py
  from ..base import ValidationResult
  from ..strategies import validator
  import ast
  
  @validator("code_syntax")
  class CodeSyntaxValidator:
      """Validates code syntax."""
      
      def __init__(self, language: str = "python"):
          self.language = language
      
      @property
      def name(self) -> str:
          return f"code_syntax({self.language})"
      
      def validate(self, response: Any, context: Dict[str, Any]) -> ValidationResult:
          code = response.get("code", "")
          language = response.get("language", self.language)
          
          if language.lower() == "python":
              try:
                  ast.parse(code)
                  return ValidationResult(valid=True)
              except SyntaxError as e:
                  return ValidationResult(
                      valid=False,
                      error=f"Python syntax error: {e.msg}",
                      debug_info={"line": e.lineno, "offset": e.offset},
                      suggestions=[f"Fix syntax error at line {e.lineno}"]
                  )
          
          # Add more language validators as needed
          return ValidationResult(
              valid=True,
              debug_info={"note": f"No syntax validation for {language}"}
          )
  
  @validator("code_completeness")
  class CodeCompletenessValidator:
      """Validates that code is complete and runnable."""
      
      @property
      def name(self) -> str:
          return "code_completeness"
      
      def validate(self, response: Any, context: Dict[str, Any]) -> ValidationResult:
          code = response.get("code", "")
          
          incomplete_patterns = [
              ("...", "Code contains ellipsis placeholder"),
              ("# TODO", "Code contains TODO comment"),
              ("pass", "Code contains placeholder pass statement"),
              ("raise NotImplementedError", "Code contains NotImplementedError"),
          ]
          
          for pattern, error in incomplete_patterns:
              if pattern in code:
                  return ValidationResult(
                      valid=False,
                      error=error,
                      suggestions=["Complete the implementation"]
                  )
          
          return ValidationResult(valid=True)
  ```

- [ ] 3.5 Create general validators
  
  ```python
  # llm_validation/validators/general.py
  from ..base import ValidationResult
  from ..strategies import validator
  from typing import Any, Dict, List
  import re
  
  @validator("field_presence")
  class FieldPresenceValidator:
      """Validates that required fields are present and non-empty."""
      
      def __init__(self, required_fields: List[str]):
          self.required_fields = required_fields
      
      @property
      def name(self) -> str:
          return f"field_presence({','.join(self.required_fields)})"
      
      def validate(self, response: Any, context: Dict[str, Any]) -> ValidationResult:
          if hasattr(response, '__dict__'):
              data = response.__dict__
          else:
              data = response
          
          missing = []
          empty = []
          
          for field in self.required_fields:
              if field not in data:
                  missing.append(field)
              elif not data[field]:
                  empty.append(field)
          
          errors = []
          if missing:
              errors.append(f"Missing fields: {', '.join(missing)}")
          if empty:
              errors.append(f"Empty fields: {', '.join(empty)}")
          
          if errors:
              return ValidationResult(
                  valid=False,
                  error="; ".join(errors),
                  suggestions=[f"Provide value for {field}" for field in missing + empty]
              )
          
          return ValidationResult(valid=True)
  
  @validator("format_consistency")
  class FormatConsistencyValidator:
      """Validates format consistency across fields."""
      
      def __init__(self, format_rules: Dict[str, str]):
          self.format_rules = format_rules
      
      @property
      def name(self) -> str:
          return "format_consistency"
      
      def validate(self, response: Any, context: Dict[str, Any]) -> ValidationResult:
          if hasattr(response, '__dict__'):
              data = response.__dict__
          else:
              data = response
          
          format_errors = []
          
          for field, pattern in self.format_rules.items():
              if field in data and data[field]:
                  value = str(data[field])
                  if not re.match(pattern, value):
                      format_errors.append(f"{field}: '{value}' doesn't match pattern {pattern}")
          
          if format_errors:
              return ValidationResult(
                  valid=False,
                  error="Format validation failed",
                  debug_info={"errors": format_errors},
                  suggestions=format_errors
              )
          
          return ValidationResult(valid=True)
  ```

- [ ] 3.6 Create verification report
  - Create `/docs/reports/007_task_3_processor_validators.md`
  - Document each validator type
  - Show validation examples
  - Include test results
  - List use cases

- [ ] 3.7 Git commit feature

**Technical Specifications**:
- Modular validator design
- Easy to extend
- Well-documented
- High test coverage
- Performance optimized

**Verification Method**:
```python
# Test example
from llm_validation.validators.table import TableStructureValidator

validator = TableStructureValidator(min_rows=2, min_cols=3)
response = {"table_html": "<table><tr><td>A</td><td>B</td></tr></table>"}
result = validator.validate(response, {})
assert not result.valid
assert "minimum 2 required" in result.error
```

**Acceptance Criteria**:
- All validators working
- High test coverage (>90%)
- Good documentation
- Easy to use and extend

### Task 3A: Create MCP Layer (Future) ⏳ Not Started

**Priority**: LOW | **Complexity**: LOW | **Impact**: MEDIUM

**Research Requirements**:
- [ ] Use `perplexity_ask` for "fastmcp integration patterns"
- [ ] Use `WebSearch` for "mcp python tools"
- [ ] Find MCP implementation examples
- [ ] Research JSON schema patterns

**Implementation Steps**:
- [ ] 3A.1 Create MCP structure
  - Create `mcp/` directory
  - Add `__init__.py` file
  - Plan MCP integration
  - Document future use
  - Add placeholder files

- [ ] 3A.2 Define schemas
  - Create `mcp/schema.py`
  - Add JSON schemas
  - Map CLI commands
  - Define parameters
  - Document schemas

- [ ] 3A.3 Create wrapper
  - Create `mcp/wrapper.py`
  - Add FastMCP skeleton
  - Map to core functions
  - Plan serialization
  - Document integration

- [ ] 3A.4 Add MCP tests
  - Create placeholder tests
  - Document test strategy
  - Plan integration tests
  - Define test data
  - Create test framework

- [ ] 3A.5 Create documentation
  - Document MCP plans
  - Create integration guide
  - Add examples
  - Define roadmap
  - List requirements

- [ ] 3A.6 Create verification report
  - Create `/docs/reports/007_task_3a_mcp_layer.md`
  - Document future plans
  - Show architecture
  - List requirements
  - Define timeline

- [ ] 3A.7 Git commit feature

**Technical Specifications**:
- FastMCP compatibility
- JSON schema compliance
- Clear documentation
- Future expansion ready
- Minimal implementation

**Verification Method**:
- Documentation review
- Schema validation
- Architecture check
- Placeholder tests

**Acceptance Criteria**:
- Structure in place
- Documentation complete
- Schemas defined
- Integration planned

### Task 4: LiteLLM Integration Based on Provided Example ⏳ Not Started

**Priority**: HIGH | **Complexity**: LOW | **Impact**: HIGH

**Research Requirements**:
- [ ] Use `perplexity_ask` for "litellm vertex ai structured outputs documentation"
- [ ] Use `WebSearch` for "litellm json mode pydantic validation"
- [ ] Find LiteLLM documentation for specific providers
- [ ] Study existing litellm cache implementation at marker/services/utils/litellm_cache.py

**Key Documentation Links**:
- [LiteLLM JSON Mode & Structured Outputs](https://docs.litellm.ai/docs/completion/json_mode)
- [LiteLLM Caching](https://docs.litellm.ai/docs/proxy/caching)
- [Vertex AI Support](https://docs.litellm.ai/docs/providers/vertex)
- [Response Format Guide](https://docs.litellm.ai/docs/completion/response_format)

**Implementation Steps**:
- [ ] 4.1 Update LiteLLMService to support json_schema_validation with Redis caching
  - Add `enable_json_schema_validation` config option
  - Implement verbose mode toggle
  - Add support for response_format with Pydantic models
  - Integrate Redis caching from marker/services/utils/litellm_cache.py
  - Handle cache initialization and fallback

  ```python
  # Example implementation based on provided code
  import litellm
  from litellm import completion
  from pydantic import BaseModel
  from marker.services.utils.litellm_cache import initialize_litellm_cache
  
  class LiteLLMService(BaseService):
      enable_json_schema_validation: bool = False
      verbose_mode: bool = False
      use_caching: bool = True
      
      def __init__(self, config):
          super().__init__(config)
          
          # Initialize caching if enabled
          if self.use_caching:
              initialize_litellm_cache()
          
          if self.enable_json_schema_validation:
              litellm.enable_json_schema_validation = True
          if self.verbose_mode:
              litellm.set_verbose = True
  ```

- [ ] 4.2 Create validation wrapper for litellm calls
  - Implement retry logic with validation
  - Support structured outputs via Pydantic
  - Add custom validation strategies
  - Integrate with retry mechanism
  - Handle validation errors

  ```python
  async def completion_with_validation(
      model: str,
      messages: list,
      response_format: BaseModel,
      validation_strategies: list = None,
      max_retries: int = 3
  ):
      litellm.enable_json_schema_validation = True
      
      for attempt in range(max_retries):
          try:
              resp = completion(
                  model=model,
                  messages=messages,
                  response_format=response_format,
              )
              
              # Apply custom validation strategies
              if validation_strategies:
                  for strategy in validation_strategies:
                      result = strategy(resp)
                      if not result.valid:
                          messages.append({
                              "role": "assistant",
                              "content": str(resp)
                          })
                          messages.append({
                              "role": "user", 
                              "content": f"Validation error: {result.error}"
                          })
                          continue
              
              return resp
          except Exception as e:
              if attempt == max_retries - 1:
                  raise
              continue
  ```

- [ ] 4.3 Update existing LiteLLMService to integrate validation loop
  - Import validation components from the new module
  - Update the completion method to use retry_with_validation
  - Add cache initialization in service constructor
  - Handle Redis connection errors gracefully
  - Maintain backward compatibility
  
  ```python
  # marker/services/litellm.py (updated)
  import os
  from marker.services.utils.litellm_cache import initialize_litellm_cache
  from llm_validation.core import retry_with_validation, registry
  
  class LiteLLMService(BaseService):
      enable_json_schema_validation: bool = False
      verbose_mode: bool = False
      use_caching: bool = True
      enable_validation_loop: bool = False
      
      def __init__(self, config: GoogleServiceConfig):
          super().__init__(config)
          
          # Initialize Redis caching if enabled
          if self.use_caching:
              try:
                  initialize_litellm_cache()
                  logger.info("✅ LiteLLM Redis caching initialized")
              except Exception as e:
                  logger.warning(f"⚠️ Cache initialization failed: {e}. Using default.")
          
          # Configure litellm settings
          if self.enable_json_schema_validation:
              litellm.enable_json_schema_validation = True
          if self.verbose_mode:
              litellm.set_verbose = True
              os.environ["LITELLM_LOG"] = "DEBUG"
  ```

- [ ] 4.4 Update processors to use new validation
  - Import validation wrapper
  - Define response schemas as Pydantic models
  - Add validation strategies per processor
  - Test with real use cases
  - Document changes

- [ ] 4.5 Add configuration options
  - Add to Marker config parser
  - Support CLI flags
  - Create environment variables for Redis
  - Document all options including caching
  - Create example configs
  
  ```python
  # marker/config/parser.py (additions)
  @dataclass
  class LiteLLMConfig:
      enable_json_schema_validation: bool = False
      verbose_mode: bool = False
      use_caching: bool = True
      redis_host: str = field(
          default_factory=lambda: os.getenv("REDIS_HOST", "localhost")
      )
      redis_port: int = field(
          default_factory=lambda: int(os.getenv("REDIS_PORT", 6379))
      )
      redis_password: Optional[str] = field(
          default_factory=lambda: os.getenv("REDIS_PASSWORD", None)
      )
      cache_ttl: int = field(
          default_factory=lambda: int(os.getenv("LITELLM_CACHE_TTL", 24 * 60 * 60))
      )
      enable_validation_loop: bool = False
      max_validation_retries: int = 3
  ```

- [ ] 4.6 Create example implementations with Redis caching
  - Port the provided example exactly with caching enabled
  - Add cache verification example
  - Show custom validators
  - Demonstrate retry behavior
  - Include debug examples

  ```python
  # Example with Redis caching and validation
  import litellm, os
  from litellm import completion 
  from pydantic import BaseModel
  from marker.services.utils.litellm_cache import initialize_litellm_cache
  from llm_validation.core import retry_with_validation, registry
  
  # Initialize caching
  initialize_litellm_cache()
  
  # Enable validation
  litellm.enable_json_schema_validation = True
  litellm.set_verbose = True
  
  class CalendarEvent(BaseModel):
      name: str
      date: str
      participants: list[str]
  
  messages = [
      {"role": "system", "content": "Extract the event information."},
      {"role": "user", "content": "Alice and Bob are going to a science fair on Friday."},
  ]
  
  # Call with validation and caching
  result = await retry_with_validation(
      llm_call=lambda messages, response_format: completion(
          model="gemini/gemini-1.5-pro",
          messages=messages,
          response_format=response_format,
      ),
      messages=messages,
      response_format=CalendarEvent,
      validation_strategies=[
          registry.get("field_presence", required_fields=["name", "date", "participants"]),
      ],
      config=RetryConfig(max_attempts=3, debug_mode=True),
  )
  
  # Check cache hit on second call
  response2 = completion(
      model="gemini/gemini-1.5-pro",
      messages=messages,
      response_format=CalendarEvent,
  )
  
  # Verify cache hit
  cache_hit = getattr(response2, "_hidden_params", {}).get("cache_hit")
  print(f"Cache hit: {cache_hit}")
  ```

- [ ] 4.7 Create verification report
  - Create `/docs/reports/007_task_4_litellm_integration.md`
  - Show working example from user
  - Document Redis caching integration
  - Include cache performance benchmarks
  - List any limitations

- [ ] 4.8 Git commit feature

**Working Example to Implement**:
```python
# This is the exact example provided by the user with caching
import litellm, os
from litellm import completion 
from pydantic import BaseModel
from marker.services.utils.litellm_cache import initialize_litellm_cache

# Initialize Redis caching
initialize_litellm_cache()

messages=[
    {"role": "system", "content": "Extract the event information."},
    {"role": "user", "content": "Alice and Bob are going to a science fair on Friday."},
]

litellm.enable_json_schema_validation = True
litellm.set_verbose = True

class CalendarEvent(BaseModel):
    name: str
    date: str
    participants: list[str]

# First call - will miss cache
resp = completion(
    model="gemini/gemini-1.5-pro",
    messages=messages,
    response_format=CalendarEvent,
)

print("Received={}".format(resp))

# Second call - should hit cache
resp2 = completion(
    model="gemini/gemini-1.5-pro",
    messages=messages,
    response_format=CalendarEvent,
)

# Check if it was a cache hit
cache_hit = getattr(resp2, "_hidden_params", {}).get("cache_hit")
print(f"Second call cache hit: {cache_hit}")
```

**Technical Specifications**:
- Use litellm's built-in json_schema_validation
- Integrate existing Redis caching from marker/services/utils/litellm_cache.py
- Maintain existing behavior (zero breaking changes)
- Follow user's example pattern exactly
- Support both cached and non-cached modes
- Graceful fallback if Redis unavailable

**Verification Method**:
- Run exact user example with caching
- Test cache hits and misses
- Verify Pydantic validation works
- Check retry behavior with validation
- Test Redis connection failures
- Benchmark cache performance

**Acceptance Criteria**:
- User's example works as-is with caching
- Redis integration is seamless
- Cache fallback works correctly
- Validation is optional (backward compatible)
- All existing tests pass
- Cache improves performance

### Task 5: Create Standalone Package ⏳ Not Started

**Priority**: MEDIUM | **Complexity**: LOW | **Impact**: HIGH

**Research Requirements**:
- [ ] Use `perplexity_ask` for "python standalone package best practices 2024"
- [ ] Use `WebSearch` for "python package pyproject.toml setup.py"
- [ ] Find modern packaging examples
- [ ] Research pip installation patterns

**Implementation Steps**:
- [ ] 5.1 Create package files
  - Create `setup.py`
  
  ```python
  # setup.py
  from setuptools import setup, find_packages
  import pathlib
  
  here = pathlib.Path(__file__).parent.resolve()
  long_description = (here / "README.md").read_text(encoding="utf-8")
  
  setup(
      name="llm-validation",
      version="0.1.0",
      author="Your Name",
      author_email="your.email@example.com",
      description="Modular validation system for LLM outputs with retry logic",
      long_description=long_description,
      long_description_content_type="text/markdown",
      url="https://github.com/yourusername/llm-validation",
      packages=find_packages(),
      classifiers=[
          "Development Status :: 3 - Alpha",
          "Intended Audience :: Developers",
          "Topic :: Software Development :: Libraries :: Python Modules",
          "License :: OSI Approved :: MIT License",
          "Programming Language :: Python :: 3",
          "Programming Language :: Python :: 3.8",
          "Programming Language :: Python :: 3.9",
          "Programming Language :: Python :: 3.10",
          "Programming Language :: Python :: 3.11",
      ],
      python_requires=">=3.8",
      install_requires=[
          "litellm>=1.0.0",
          "pydantic>=2.0.0",
          "typer>=0.9.0",
          "rich>=13.0.0",
          "loguru>=0.7.0",
      ],
      extras_require={
          "dev": ["pytest>=7.0", "pytest-asyncio>=0.21", "black>=23.0", "mypy>=1.0"],
          "docs": ["mkdocs>=1.5", "mkdocs-material>=9.0"],
      },
      entry_points={
          "console_scripts": [
              "llm-validate=llm_validation.cli.app:app",
          ],
      },
      include_package_data=True,
      package_data={
          "llm_validation": ["validators/*.py"],
      },
  )
  ```

- [ ] 5.2 Create pyproject.toml
  
  ```toml
  # pyproject.toml
  [build-system]
  requires = ["setuptools>=61.0", "wheel"]
  build-backend = "setuptools.build_meta"
  
  [project]
  name = "llm-validation"
  version = "0.1.0"
  description = "Modular validation system for LLM outputs with retry logic"
  readme = "README.md"
  authors = [
      {name = "Your Name", email = "your.email@example.com"}
  ]
  license = {text = "MIT"}
  classifiers = [
      "Development Status :: 3 - Alpha",
      "Intended Audience :: Developers",
      "Topic :: Software Development :: Libraries :: Python Modules",
      "License :: OSI Approved :: MIT License",
      "Programming Language :: Python :: 3",
      "Programming Language :: Python :: 3.8",
      "Programming Language :: Python :: 3.9",
      "Programming Language :: Python :: 3.10",
      "Programming Language :: Python :: 3.11",
  ]
  requires-python = ">=3.8"
  dependencies = [
      "litellm>=1.0.0",
      "pydantic>=2.0.0",
      "typer>=0.9.0",
      "rich>=13.0.0",
      "loguru>=0.7.0",
  ]
  
  [project.optional-dependencies]
  dev = [
      "pytest>=7.0",
      "pytest-asyncio>=0.21",
      "black>=23.0",
      "mypy>=1.0",
      "ruff>=0.1.0",
  ]
  docs = [
      "mkdocs>=1.5",
      "mkdocs-material>=9.0",
      "mkdocstrings[python]>=0.22",
  ]
  
  [project.scripts]
  llm-validate = "llm_validation.cli.app:main"
  
  [project.urls]
  Homepage = "https://github.com/yourusername/llm-validation"
  Documentation = "https://llm-validation.readthedocs.io"
  Repository = "https://github.com/yourusername/llm-validation"
  Issues = "https://github.com/yourusername/llm-validation/issues"
  
  [tool.setuptools.packages.find]
  where = ["llm_validation"]
  include = ["llm_validation*"]
  
  [tool.black]
  line-length = 88
  target-version = ['py38', 'py39', 'py310', 'py311']
  
  [tool.ruff]
  line-length = 88
  select = ["E", "F", "W", "I", "N", "UP"]
  ignore = ["E501"]
  
  [tool.mypy]
  python_version = "3.8"
  warn_return_any = true
  warn_unused_configs = true
  disallow_untyped_defs = true
  ```

- [ ] 5.3 Create MANIFEST.in
  
  ```
  # MANIFEST.in
  include README.md
  include LICENSE
  include CHANGELOG.md
  include requirements.txt
  recursive-include llm_validation *.py
  recursive-include llm_validation/validators *.py
  recursive-include examples *.py *.md
  recursive-include docs *.md *.png
  prune tests
  prune .github
  global-exclude *.pyc
  global-exclude __pycache__
  ```

- [ ] 5.4 Create package structure
  
  ```python
  # llm_validation/__init__.py
  """LLM Validation - Modular validation system for LLM outputs."""
  
  __version__ = "0.1.0"
  __author__ = "Your Name"
  __email__ = "your.email@example.com"
  
  from .core import (
      ValidationResult,
      ValidationStrategy,
      retry_with_validation,
      registry,
      validator,
  )
  from .core.retry import RetryConfig
  from .core.debug import DebugManager
  
  __all__ = [
      "ValidationResult",
      "ValidationStrategy",
      "retry_with_validation",
      "registry",
      "validator",
      "RetryConfig",
      "DebugManager",
  ]
  
  # Auto-discover built-in validators
  from pathlib import Path
  validator_dir = Path(__file__).parent / "validators"
  if validator_dir.exists():
      registry.discover_strategies(validator_dir)
  ```

- [ ] 5.5 Create examples directory
  
  ```python
  # examples/basic_usage.py
  """Basic usage example for llm-validation."""
  
  import asyncio
  from pydantic import BaseModel
  from llm_validation import retry_with_validation, validator, RetryConfig
  import litellm
  
  # Define a response schema
  class EventInfo(BaseModel):
      name: str
      date: str
      participants: list[str]
  
  # Create a custom validator
  @validator("participant_count")
  class ParticipantCountValidator:
      def __init__(self, min_count: int = 2):
          self.min_count = min_count
      
      @property
      def name(self) -> str:
          return f"participant_count(min={self.min_count})"
      
      def validate(self, response, context):
          count = len(response.participants)
          if count < self.min_count:
              return ValidationResult(
                  valid=False,
                  error=f"Need at least {self.min_count} participants, got {count}"
              )
          return ValidationResult(valid=True)
  
  async def main():
      # Enable LiteLLM validation
      litellm.enable_json_schema_validation = True
      
      # Create messages
      messages = [
          {"role": "system", "content": "Extract event information."},
          {"role": "user", "content": "Alice and Bob are going to a science fair on Friday."},
      ]
      
      # Run with validation
      result = await retry_with_validation(
          llm_call=lambda messages, response_format: litellm.completion(
              model="gemini/gemini-1.5-pro",
              messages=messages,
              response_format=response_format,
          ),
          messages=messages,
          response_format=EventInfo,
          validation_strategies=[
              registry.get("participant_count", min_count=1),
          ],
          config=RetryConfig(max_attempts=3, debug_mode=True),
      )
      
      print(f"Result: {result}")
  
  if __name__ == "__main__":
      asyncio.run(main())
  ```

- [ ] 5.6 Create installation documentation
  
  ```markdown
  # Installation Guide
  
  ## Quick Install
  
  ```bash
  pip install llm-validation
  ```
  
  ## Install from Source
  
  ```bash
  git clone https://github.com/yourusername/llm-validation.git
  cd llm-validation
  pip install -e .
  ```
  
  ## Development Setup
  
  ```bash
  # Clone the repository
  git clone https://github.com/yourusername/llm-validation.git
  cd llm-validation
  
  # Create virtual environment
  python -m venv venv
  source venv/bin/activate  # On Windows: venv\Scripts\activate
  
  # Install with dev dependencies
  pip install -e ".[dev]"
  
  # Run tests
  pytest
  ```
  
  ## Verify Installation
  
  ```bash
  # Check CLI is installed
  llm-validate --version
  
  # List available validators
  llm-validate list-validators
  ```
  
  ## Troubleshooting
  
  ### Common Issues
  
  1. **ImportError**: Make sure all dependencies are installed
     ```bash
     pip install -r requirements.txt
     ```
  
  2. **Command not found**: Ensure the package is in your PATH
     ```bash
     export PATH=$PATH:~/.local/bin
     ```
  ```

- [ ] 5.7 Test installation process
  
  ```bash
  # Create test script: test_install.sh
  #!/bin/bash
  
  # Create clean test environment
  python -m venv test_env
  source test_env/bin/activate
  
  # Test pip install
  pip install .
  
  # Verify installation
  python -c "import llm_validation; print(llm_validation.__version__)"
  
  # Test CLI
  llm-validate --version
  llm-validate list-validators
  
  # Run example
  python examples/basic_usage.py
  
  # Cleanup
  deactivate
  rm -rf test_env
  ```

- [ ] 5.8 Create verification report
  - Create `/docs/reports/007_task_5_standalone_package.md`
  - Document packaging structure
  - Show installation process
  - Include test results
  - List all files created

- [ ] 5.9 Git commit feature

**Technical Specifications**:
- Modern Python packaging (PEP 517/518)
- Minimal dependencies
- Easy installation
- Clear documentation
- Cross-platform support

**Verification Method**:
```bash
# Test package building
python -m build

# Test installation
pip install dist/llm_validation-0.1.0-py3-none-any.whl

# Verify imports
python -c "from llm_validation import retry_with_validation, validator"

# Test CLI
llm-validate --help
```

**Acceptance Criteria**:
- Package builds without errors
- Installs via pip successfully
- All imports work correctly
- CLI commands functional
- Examples run without issues

### Task 6: Documentation ⏳ Not Started

**Priority**: MEDIUM | **Complexity**: LOW | **Impact**: HIGH

**Research Requirements**:
- [ ] Use `perplexity_ask` for "python package documentation best practices"
- [ ] Use `WebSearch` for "modular library documentation"
- [ ] Find documentation patterns
- [ ] Research tutorial formats

**Implementation Steps**:
- [ ] 6.1 Create README
  - Write comprehensive README
  - Add quick start guide
  - Include examples
  - Add badges
  - List features

- [ ] 6.2 API documentation
  - Document core API
  - Document CLI commands
  - Add code examples
  - Include type hints
  - Create reference

- [ ] 6.3 Create tutorials
  - Getting started tutorial
  - Integration tutorial
  - Custom validator tutorial
  - Advanced usage
  - Best practices

- [ ] 6.4 Architecture docs
  - Document 3-layer design
  - Show module structure
  - Explain design decisions
  - Add diagrams
  - Include examples

- [ ] 6.5 Migration guide
  - From examples to module
  - Integration steps
  - Configuration migration
  - Breaking changes
  - Update checklist

- [ ] 6.6 Create verification report
  - Create `/docs/reports/007_task_6_documentation.md`
  - List all docs
  - Check completeness
  - Verify accuracy
  - Get feedback

- [ ] 6.7 Git commit feature

**Technical Specifications**:
- Comprehensive coverage
- Clear examples
- Good organization
- Searchable content
- Multiple formats

**Verification Method**:
- Documentation review
- Example testing
- User feedback
- Coverage check

**Acceptance Criteria**:
- All features documented
- Examples working
- Tutorials complete
- API reference done

### Task 7: Demo Other Project Integration ⏳ Not Started

**Priority**: LOW | **Complexity**: LOW | **Impact**: HIGH

**Research Requirements**:
- [ ] Use `perplexity_ask` for "python module portability patterns"
- [ ] Use `WebSearch` for "drop-in library examples"
- [ ] Find integration patterns
- [ ] Research compatibility

**Implementation Steps**:
- [ ] 7.1 Prepare ArangoDB integration
  - Copy module to ArangoDB project
  - Update import paths
  - Configure for ArangoDB
  - Test basic functionality
  - Document process

- [ ] 7.2 Create integration example
  - Write example script
  - Show configuration
  - Demonstrate usage
  - Test with real data
  - Document results

- [ ] 7.3 Test compatibility
  - Verify no conflicts
  - Check dependencies
  - Test functionality
  - Measure performance
  - Document issues

- [ ] 7.4 Create integration guide
  - Document steps
  - Show configuration
  - Include examples
  - Add troubleshooting
  - List best practices

- [ ] 7.5 Gather feedback
  - Test with users
  - Document issues
  - Collect suggestions
  - Update documentation
  - Plan improvements

- [ ] 7.6 Create verification report
  - Create `/docs/reports/007_task_7_demo_integration.md`
  - Document integration
  - Show working example
  - Include feedback
  - List improvements

- [ ] 7.7 Git commit feature

**Technical Specifications**:
- Clean integration
- No modifications needed
- Clear documentation
- Working examples
- Performance acceptable

**Verification Method**:
- Integration tests
- User testing
- Performance tests
- Documentation review

**Acceptance Criteria**:
- Integration successful
- Examples working
- Documentation complete
- User feedback positive

### Task 8: Completion Verification and Iteration ⏳ Not Started

**Priority**: CRITICAL | **Complexity**: LOW | **Impact**: CRITICAL

**Implementation Steps**:
- [ ] 8.1 Review all task reports
  - Read all reports in `/docs/reports/007_task_*`
  - Create checklist of incomplete features
  - Identify failed tests or missing functionality
  - Document specific issues preventing completion
  - Prioritize fixes by impact

- [ ] 8.2 Create task completion matrix
  - Build comprehensive status table
  - Mark each sub-task as COMPLETE/INCOMPLETE
  - List specific failures for incomplete tasks
  - Identify blocking dependencies
  - Calculate overall completion percentage

- [ ] 8.3 Iterate on incomplete tasks
  - Return to first incomplete task
  - Fix identified issues
  - Re-run validation tests
  - Update verification report
  - Continue until task passes

- [ ] 8.4 Re-validate completed tasks
  - Ensure no regressions from fixes
  - Run integration tests
  - Verify cross-task compatibility
  - Update affected reports
  - Document any new limitations

- [ ] 8.5 Final comprehensive validation
  - Run all tests
  - Execute performance benchmarks
  - Test CLI interface
  - Verify documentation accuracy
  - Test in both Marker and ArangoDB

- [ ] 8.6 Create final summary report
  - Create `/docs/reports/007_final_summary.md`
  - Include completion matrix
  - Document all working features
  - List any remaining limitations
  - Provide usage recommendations

- [ ] 8.7 Mark task complete only if ALL sub-tasks pass
  - Verify 100% task completion
  - Confirm all reports show success
  - Ensure no critical issues remain
  - Get final approval
  - Update task status to ✅ Complete

**Technical Specifications**:
- Zero tolerance for incomplete features
- Mandatory iteration until completion
- All tests must pass
- All reports must verify success
- No theoretical completions allowed

**Verification Method**:
- Task completion matrix showing 100%
- All reports confirming success
- Rich table with final status

**Acceptance Criteria**:
- ALL tasks marked COMPLETE
- ALL verification reports show success
- ALL tests pass without issues
- ALL features work in production
- Module works in both Marker and ArangoDB

**CRITICAL ITERATION REQUIREMENT**:
This task CANNOT be marked complete until ALL previous tasks are verified as COMPLETE with passing tests and working functionality. The agent MUST continue iterating on incomplete tasks until 100% completion is achieved.

## Usage Table

| Command / Function | Description | Example Usage | Expected Output |
|-------------------|-------------|---------------|-----------------|
| `llm-validate` | CLI tool for validation | `llm-validate --help` | Show help text |
| `llm-validate test` | Test validation | `llm-validate test "prompt" --validators length,format` | Validation results |
| `llm-validate debug` | Debug validation | `llm-validate debug "prompt" --trace --profile` | Debug trace |
| `llm-validate list` | List available validators | `llm-validate list` | Available validators |
| `from llm_validation.core import validate` | Core validation | `result = validate(response, strategies)` | Validation result |
| `@validator("custom_name")` | Register custom validator | See example below | Validator registered |
| `llm-validate config` | Configure validation | `llm-validate config --set retry.max_attempts=5` | Config updated |

## Example: Adding Custom Validators

```python
# custom_validators.py
from llm_validation.core.base import validator, ValidationResult
from llm_validation.core.debug import debug_trace

@validator("citation_exists")
@debug_trace  # Enable debugging for this validator
class CitationValidator:
    """Validates that citations exist in the database."""
    
    def __init__(self, db_connection):
        self.db = db_connection
    
    async def validate(self, response: dict, context: dict) -> ValidationResult:
        citation = response.get("citation")
        if not citation:
            return ValidationResult(
                valid=False,
                error="No citation found",
                debug_info={"response": response}
            )
        
        # Check database
        exists = await self.db.check_citation(citation)
        return ValidationResult(
            valid=exists,
            error=f"Citation '{citation}' not found" if not exists else None,
            debug_info={
                "citation": citation,
                "exists": exists,
                "db_query_time": context.get("query_time")
            }
        )
```

## Example: Debugging Validation Pipeline

```python
from llm_validation.core import ValidationPipeline
from llm_validation.core.debug import DebugMode

# Create pipeline with debugging
pipeline = ValidationPipeline(debug_mode=DebugMode.TRACE)

# Add validators
pipeline.add_validator("length_check", min_words=10, max_words=50)
pipeline.add_validator("citation_exists", db_connection=db)
pipeline.add_validator("format_check", required_fields=["title", "content"])

# Run with debugging
result = await pipeline.validate(response, debug=True)

# Access debug information
print(result.debug_trace)  # Step-by-step execution
print(result.timing_info)  # Performance metrics
print(result.validator_states)  # State at each step
```

## Example: Custom Retry Strategy

```python
from llm_validation.core.retry import RetryStrategy, register_strategy

@register_strategy("adaptive_backoff")
class AdaptiveBackoffStrategy(RetryStrategy):
    """Adjusts backoff based on error type."""
    
    def calculate_delay(self, attempt: int, error: Exception) -> float:
        if isinstance(error, RateLimitError):
            return min(60, 2 ** attempt)  # Exponential for rate limits
        elif isinstance(error, ValidationError):
            return 1  # Quick retry for validation errors
        else:
            return attempt * 2  # Linear for other errors
```

## Version Control Plan

- **Initial Commit**: Create task-007-start tag before implementation
- **Feature Commits**: After each layer completion
- **Integration Commits**: After Marker integration  
- **Package Commits**: After packaging complete
- **Final Tag**: Create task-007-complete after all tests pass

## Resources

**Python Packages**:
- typer: CLI framework
- rich: Terminal formatting
- pydantic: Data validation
- litellm: LLM integration
- asyncio: Async support

**Documentation**:
- [3-Layer Architecture Guide](../architecture/3_LAYER_ARCHITECTURE.md)
- [Typer Documentation](https://typer.tiangolo.com/)
- [Rich Documentation](https://rich.readthedocs.io/)
- [Python Packaging Guide](https://packaging.python.org/)

## Progress Tracking

- Start date: TBD
- Current phase: Planning
- Expected completion: TBD
- Completion criteria: Module works in both Marker and other projects

## Report Documentation Requirements

Each sub-task MUST have a corresponding verification report in `/docs/reports/` following these requirements:

### Report Structure:
Each report must include:
1. **Task Summary**: Brief description of what was implemented
2. **Research Findings**: Links to repos, code examples found, best practices discovered
3. **Non-Mocked Results**: Real command outputs and performance metrics
4. **Performance Metrics**: Actual benchmarks with real data
5. **Code Examples**: Working code with verified output
6. **Verification Evidence**: Logs or metrics proving functionality
7. **Limitations Found**: Any discovered issues or constraints
8. **External Resources Used**: All GitHub repos, articles, and examples referenced

### Report Naming Convention:
`/docs/reports/007_task_[SUBTASK]_[feature_name].md`

## Context Management

When context length is running low during implementation, use the following approach to compact and resume work:

1. Issue the `/compact` command to create a concise summary of current progress
2. The summary will include:
   - Completed tasks and key functionality
   - Current task in progress with specific subtask
   - Known issues or blockers
   - Next steps to resume work
   - Key decisions made or patterns established

---

This task document serves as the comprehensive implementation guide. Update status emojis and checkboxes as tasks are completed to maintain progress tracking.
