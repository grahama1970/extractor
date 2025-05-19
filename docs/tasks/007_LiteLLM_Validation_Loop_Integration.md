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

## String Matching Library Choice: RapidFuzz vs FuzzyWuzzy

For implementing fuzzy string matching in our validation strategies (like citation checking and content matching), we will use **RapidFuzz** instead of FuzzyWuzzy. Research indicates RapidFuzz offers several important advantages:

1. **Performance**: RapidFuzz is significantly faster than FuzzyWuzzy (often 5-10x speedup), particularly for large sets of strings and complex operations.

2. **Licensing**: RapidFuzz uses the MIT license which is more permissive than FuzzyWuzzy's GPL license, allowing greater flexibility for integration with other libraries and projects.

3. **Correctness**: RapidFuzz fixes bugs in FuzzyWuzzy, particularly in the `partial_ratio` function. FuzzyWuzzy relies on an incorrect implementation of `get_matching_blocks()` in python-Levenshtein, which can lead to suboptimal string matches.

4. **Algorithmically Superior**: RapidFuzz uses more efficient implementations:
   - Bit-parallel algorithms for faster string comparison
   - Score cutoff optimizations to skip unnecessary computations
   - Better preprocessing with less Python GIL overhead

5. **Additional Algorithms**: RapidFuzz provides more string metrics like Hamming and Jaro-Winkler that aren't available in FuzzyWuzzy.

For citation validation and other text matching requirements, we'll implement validators with RapidFuzz to ensure optimal performance and accuracy.

## Hybrid Approach for Implementation

Based on our research of both the marker project's existing architecture and the ADVANCED-inference repository's validation approaches, we'll implement a hybrid approach that combines:

1. **Core Layer**: Enhance marker's functional validation approach with the richer error reporting and debug capabilities from ADVANCED-inference
2. **Cache Integration**: Use marker's existing LiteLLM Redis caching implementation
3. **Validation Strategies**: Add citation validation strategies using RapidFuzz for fuzzy matching
4. **Validation Registry**: Create a registry-based plugin system for custom validators
5. **Debug Tracing**: Implement comprehensive debug output with rich formatting

Example citation validator implementation:

```python
# validators/citation.py
from typing import Dict, Any, List
from rapidfuzz import fuzz, process
from ..base import ValidationResult, ValidationStrategy

@register_validator("citation_validator")
class CitationValidator:
    """Validate that citations in the response match reference text."""
    
    def __init__(self, min_score: float = 80.0):
        self.min_score = min_score
    
    @property
    def name(self) -> str:
        return f"citation_validator(min_score={self.min_score})"
    
    def validate(self, response: Any, context: Dict[str, Any]) -> ValidationResult:
        if not hasattr(response, 'citations') or not response.citations:
            return ValidationResult(
                valid=False,
                error="No citations found in response",
                suggestions=["Include citations for factual statements"]
            )
        
        citations = response.citations
        reference_texts = context.get("reference_texts", [])
        
        if not reference_texts:
            return ValidationResult(
                valid=True,
                debug_info={"warning": "No reference texts provided for validation"}
            )
        
        invalid_citations = []
        
        for i, citation in enumerate(citations):
            # Find best match in reference texts
            match = process.extractOne(
                citation.text, 
                reference_texts,
                scorer=fuzz.partial_ratio,
                score_cutoff=self.min_score
            )
            
            if not match:
                invalid_citations.append({
                    "index": i,
                    "text": citation.text,
                    "best_match_score": match[1] if match else 0,
                })
        
        if invalid_citations:
            return ValidationResult(
                valid=False,
                error=f"Found {len(invalid_citations)} invalid citations",
                debug_info={"invalid_citations": invalid_citations},
                suggestions=[
                    "Verify citation text matches source content",
                    "Check for typographical errors in citations",
                    "Ensure citations are taken from provided reference material"
                ]
            )
        
        return ValidationResult(
            valid=True,
            debug_info={"validated_citations": len(citations)}
        )
```

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
│   │   ├── citation.py    # Citation validators
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
  - Create `core/validators/` directory with text, structure, and citation validators
  - Use RapidFuzz for citation/text matching validators

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
  - Create `cli/formatters.py` with rich output formatting
  
- [ ] 2.4 Add input validators
  - Create `cli/validators.py` for validating CLI inputs
  
- [ ] 2.5 Define schemas
  - Create `cli/schemas.py` with Pydantic models
  
- [ ] 2.6 Create debug commands
  - Create `cli/debug_commands.py` for debugging functionality
  
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
  
- [ ] 3.2 Create image description validators
  
- [ ] 3.3 Create math validators
  
- [ ] 3.4 Create code validators
  
- [ ] 3.5 Create general validators
  
- [ ] 3.6 Create citation validators using RapidFuzz
  ```python
  # validators/citation.py
  from typing import Dict, Any, List
  from rapidfuzz import fuzz, process
  from ..base import ValidationResult
  from ..strategies import validator
  
  @validator("citation_match")
  class CitationMatchValidator:
      """Validates citations against reference texts using fuzzy matching."""
      
      def __init__(self, min_score: float = 80.0):
          self.min_score = min_score
      
      @property
      def name(self) -> str:
          return f"citation_match(min_score={self.min_score})"
      
      def validate(self, response: Any, context: Dict[str, Any]) -> ValidationResult:
          """Validate that citations match reference material."""
          citations = getattr(response, "citations", [])
          references = context.get("references", [])
          
          if not citations:
              return ValidationResult(
                  valid=False,
                  error="Response contains no citations",
                  suggestions=["Include citations for factual claims"]
              )
              
          if not references:
              return ValidationResult(
                  valid=True,
                  debug_info={"warning": "No reference texts provided for comparison"}
              )
              
          unmatched_citations = []
          
          for i, citation in enumerate(citations):
              citation_text = str(citation)
              # Use RapidFuzz to find best match in references
              best_match = process.extractOne(
                  citation_text,
                  references,
                  scorer=fuzz.partial_ratio,
                  score_cutoff=self.min_score  
              )
              
              if not best_match:
                  unmatched_citations.append({
                      "index": i,
                      "text": citation_text[:100] + "..." if len(citation_text) > 100 else citation_text,
                      "best_score": best_match[1] if best_match else 0
                  })
                  
          if unmatched_citations:
              return ValidationResult(
                  valid=False,
                  error=f"Found {len(unmatched_citations)} citations that don't match references",
                  debug_info={"unmatched": unmatched_citations},
                  suggestions=[
                      "Check citation accuracy",
                      "Ensure citations are from provided reference material",
                      "Fix citation formatting"
                  ]
              )
              
          return ValidationResult(
              valid=True,
              debug_info={"matched_citations": len(citations)}
          )
  ```
  
- [ ] 3.7 Create verification report
  - Create `/docs/reports/007_task_3_processor_validators.md`
  - Document each validator type
  - Show validation examples
  - Include test results
  - List use cases

- [ ] 3.8 Git commit feature

**Technical Specifications**:
- Modular validator design
- Easy to extend
- Well-documented
- High test coverage
- Performance optimized

**Acceptance Criteria**:
- All validators working
- High test coverage (>90%)
- Good documentation
- Easy to use and extend

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

- [ ] 4.2 Create validation wrapper for litellm calls
  - Implement retry logic with validation
  - Support structured outputs via Pydantic
  - Add custom validation strategies
  - Integrate with retry mechanism
  - Handle validation errors

- [ ] 4.3 Update existing LiteLLMService to integrate validation loop
  - Import validation components from the new module
  - Update the completion method to use retry_with_validation
  - Add cache initialization in service constructor
  - Handle Redis connection errors gracefully
  - Maintain backward compatibility

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

- [ ] 4.6 Create example implementations with Redis caching
  - Port the provided example exactly with caching enabled
  - Add cache verification example
  - Show custom validators
  - Demonstrate retry behavior
  - Include debug examples

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
  
- [ ] 5.2 Create pyproject.toml
  
- [ ] 5.3 Create MANIFEST.in
  
- [ ] 5.4 Create package structure
  
- [ ] 5.5 Create examples directory
  
- [ ] 5.6 Create installation documentation
  
- [ ] 5.7 Test installation process
  
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
