# Sub-Agent Architecture Analysis

## Overview

The sub-agent system in `/home/graham/.claude/agents/` represents a sophisticated, modular architecture for task execution. This analysis examines the structure, patterns, and integration mechanisms of 19 active sub-agents.

## Architecture Components

### 1. Core Structure

```
~/.claude/agents/
├── *.md                    # Agent definitions (19 active agents)
├── workers/               # Python implementations
├── core/                  # Shared state management
├── hooks/                 # Pre/post execution hooks
├── tools/                 # Agent dispatch tools
├── tests/                 # Scenarios and verification
├── docs/                  # Architecture documentation
└── examples/              # Usage examples
```

### 2. Sub-Agent Categories

#### Research & Information Gathering (3 agents)
- **web-researcher**: Web scraping and research with caching
- **arxiv-researcher**: Academic paper research and analysis
- **youtube-researcher**: Video transcript extraction and processing

#### Code Analysis & Review (4 agents)
- **code-analyzer**: Static code analysis using tree-sitter
- **code-reviewer**: Security and quality analysis
- **codebase-analyzer**: Whole codebase analysis and metrics
- **python-template-reviewer**: Python template validation

#### Data Processing & Analysis (3 agents)
- **dataset-curator**: Dataset discovery and preparation
- **data-analyst**: Statistical analysis and modeling
- **validation-specialist**: Data validation and verification

#### Visualization (2 agents)
- **d3-visualizer**: D3.js interactive visualizations with React frontend
- **d3-visualization-creator**: Chart creation with example templates

#### Execution & Orchestration (4 agents)
- **llm-executor**: Single LLM execution
- **llm-orchestrator**: Multi-LLM coordination
- **shell-executor**: Shell command execution
- **workflow-planner**: Multi-agent workflow planning

#### Knowledge Management (1 agent)
- **knowledge-architect**: Central knowledge base and state management

#### Utilities (2 agents)
- **refactor-applier**: Apply code refactoring
- **web-downloader**: Download web resources

## Key Patterns

### 1. Agent Definition Pattern

Each agent follows a standardized YAML frontmatter + markdown structure:

```yaml
---
name: agent-name
description: Brief description
tools: python
type: [orchestrator|architect|analyzer|executor|curator]
capabilities:
  - capability_1
  - capability_2
tags:
  - tag1
  - tag2
priority: 0-100
workers: path/to/worker.py
scenarios: path/to/scenarios.md
---
```

### 2. Worker Implementation Pattern

Every worker follows consistent patterns:

```python
#!/usr/bin/env python3
"""Worker description"""

import typer
from loguru import logger

app = typer.Typer()

# Configure logging
logger.remove()
logger.add(sys.stderr, level="INFO")

@app.command()
def main_function():
    """Command implementation"""
    pass

def working_usage():
    """Stable usage example"""
    pass

def debug_function():
    """Debug/testing function"""
    pass

if __name__ == "__main__":
    app()
```

### 3. Knowledge First Pattern

The workflow-planner demonstrates the "Knowledge First" approach:

1. **Task Classification**: Analyze request type
2. **Historical Lookup**: Query knowledge-architect for successful patterns
3. **Plan Generation**: Use historical data or safe fallback
4. **Execution**: Return structured plan for master agent

### 4. Shared State Management

Via ArangoDB, agents can:
- Register themselves with capabilities
- Start/end work sessions
- Share state between agents
- Store knowledge for future use
- Track performance metrics

Example from `core/arango_state.py`:
```python
state = get_shared_state()
agent_id = state.register_agent(
    agent_type="curator",
    capabilities=["dataset_discovery", "data_cleaning"]
)
session_id = state.start_session("Analyze sales data")
state.save_state("dataset_info", {...})
```

## Hook System

### Pre-execution Hooks (`pre-tool`)
- Python environment validation
- Dangerous command blocking
- Directory creation for file operations
- Warning for missing error handling

### Post-execution Hooks (`post-tool`)
- Execution logging
- Failure tracking
- Performance metrics

### Specialized Hooks
- **python-template-enforcer**: Ensures working_usage/debug_function pattern
- **kill_zombie_mcp**: Cleans up hanging processes
- **security-audit**: Security validation
- **dependency-checker**: Validates dependencies

## Integration Mechanisms

### 1. Direct Usage
```bash
claude -p "Use the web-researcher agent to find information about X"
```

### 2. Programmatic Usage
```python
from agents.workers.web_researcher_worker import search_web
results = search_web("query")
```

### 3. Multi-Agent Workflows
```python
from agents.workers.workflow_planner_worker import WorkflowPlanner
planner = WorkflowPlanner()
plan = planner.create_workflow_plan("Complex task description")
```

### 4. Claude Dispatcher
The `tools/claude_dispatcher` provides centralized agent invocation with:
- Agent discovery
- Parameter validation
- Error handling
- Result formatting

## Advanced Features

### 1. D3 Visualizer Architecture
- Full React/TypeScript frontend (`d3-viewer-app/`)
- WebSocket server for real-time updates
- Multiple chart types (line, bar, scatter, heatmap, etc.)
- Resizable panels and interactive controls

### 2. Error Handling Pattern
Consistent error handling across all workers:
```python
try:
    result = perform_operation()
    return {"success": True, "data": result}
except SpecificError as e:
    logger.error(f"Operation failed: {e}")
    return {"success": False, "error": str(e)}
```

### 3. Testing Infrastructure
- Scenario-based testing for each agent
- Security and quality analysis tools
- Documentation verification
- Coverage reporting

## Best Practices Observed

1. **Consistent Naming**: Kebab-case for agents, snake_case for workers
2. **Typer CLI**: All workers use typer for consistent CLI interface
3. **Loguru Logging**: Standardized logging across all components
4. **Error Propagation**: Structured error returns with success flags
5. **Documentation**: Each agent has markdown docs + scenarios
6. **Modularity**: Clear separation between agent definition and implementation

## Conclusion

The sub-agent architecture represents a mature, well-designed system for modular task execution. Key strengths include:

- **Clear Separation of Concerns**: Each agent has a specific role
- **Knowledge Persistence**: Shared state via ArangoDB
- **Extensibility**: Easy to add new agents following patterns
- **Safety**: Multiple hooks ensure safe execution
- **Testability**: Comprehensive testing infrastructure

The system effectively implements the "Knowledge First" philosophy, where agents learn from past successes and share knowledge for continuous improvement.