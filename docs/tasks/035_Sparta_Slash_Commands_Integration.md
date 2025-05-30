# Task 035: Sparta Slash Commands Integration

## Overview
Integrate slash command functionality from the sparta project into marker, creating a comprehensive CLI interface that leverages Claude Code's slash command capabilities for document processing workflows.

## Analysis of Sparta Commands

### Core Command Categories:
1. **Extract Commands** - Content extraction from resources to markdown
2. **ArangoDB Commands** - Comprehensive database operations and memory management
3. **LLM Commands** - Universal LLM interface with validation
4. **Test Commands** - Enhanced testing with reporting
5. **Workflow Commands** - Processing workflow configuration
6. **Terminal Commands** - System utilities and monitoring
7. **Serve Commands** - MCP server management
8. **Allure Dashboard** - Multi-project test reporting

### Key Patterns Identified:
- Slash command syntax: `/command [arguments]`
- MCP server integration for Claude Desktop
- Comprehensive validation and reporting
- Memory management through ArangoDB
- Multi-model LLM support with validation
- Enhanced test iteration with automated fixes

## Implementation Plan

### Task 1: Create Slash Command Infrastructure
- [ ] Create `/marker/cli/slash_commands/` directory structure
- [ ] Implement base command registry and dispatcher
- [ ] Add command validation and help system
- [ ] Integrate with existing CLI using typer

### Task 2: Document Processing Commands
- [ ] `/marker-extract [pdf_path] [output_format]` - Extract content from PDFs
- [ ] `/marker-convert [input] [output] [options]` - Convert documents
- [ ] `/marker-analyze [pdf_path]` - Analyze document structure
- [ ] `/marker-table [pdf_path]` - Extract tables specifically
- [ ] `/marker-code [pdf_path]` - Extract code blocks with language detection

### Task 3: ArangoDB Integration Commands
- [ ] `/marker-db-setup` - Initialize ArangoDB for marker
- [ ] `/marker-db-import [json_path]` - Import extraction results
- [ ] `/marker-db-search "[query]"` - Search extracted content
- [ ] `/marker-db-export [format]` - Export from database
- [ ] `/marker-db-visualize` - Generate visualization of document structure

### Task 4: Claude Integration Commands
- [ ] `/marker-claude-analyze [pdf_path] [analysis_type]` - Run Claude analysis
- [ ] `/marker-claude-verify [json_path]` - Verify extraction results
- [ ] `/marker-claude-merge [table_data]` - Analyze table merges
- [ ] `/marker-claude-describe [image_path]` - Describe images with multimodal

### Task 5: Quality Assurance Commands
- [ ] `/marker-qa-generate [document]` - Generate QA pairs
- [ ] `/marker-qa-validate [qa_pairs]` - Validate QA accuracy
- [ ] `/marker-qa-test [document]` - Run comprehensive QA tests
- [ ] `/marker-qa-report` - Generate QA quality report

### Task 6: Workflow Commands
- [ ] `/marker-workflow list` - List available workflows
- [ ] `/marker-workflow create [name]` - Create custom workflow
- [ ] `/marker-workflow run [workflow] [input]` - Execute workflow
- [ ] `/marker-workflow status` - Check workflow status

### Task 7: Testing and Validation Commands
- [ ] `/marker-test [pattern]` - Run tests with pattern matching
- [ ] `/marker-test-iterate` - Run tests with automatic fixes
- [ ] `/marker-validate [output]` - Validate extraction output
- [ ] `/marker-benchmark [pdf]` - Run performance benchmarks

### Task 8: MCP Server Commands
- [ ] `/marker-serve` - Start marker MCP server
- [ ] `/marker-mcp-config` - Generate MCP configuration
- [ ] `/marker-mcp-status` - Check MCP server status
- [ ] `/marker-mcp-tools` - List available MCP tools

## Command Implementation Template

```python
# marker/cli/slash_commands/base.py
from typing import Optional, Dict, Any
import typer
from loguru import logger

class SlashCommand:
    """Base class for slash commands."""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.app = typer.Typer(help=description)
    
    def execute(self, *args, **kwargs) -> Any:
        """Execute the command."""
        raise NotImplementedError

# marker/cli/slash_commands/extract.py
class ExtractCommand(SlashCommand):
    """Extract content from PDFs."""
    
    def __init__(self):
        super().__init__("marker-extract", "Extract content from PDF documents")
        
    @app.command()
    def extract(
        self,
        pdf_path: str = typer.Argument(..., help="Path to PDF file"),
        output_format: str = typer.Option("markdown", help="Output format"),
        output_path: Optional[str] = typer.Option(None, help="Output path")
    ):
        """Extract content from a PDF document."""
        # Implementation here
```

## Integration with Claude Desktop

### MCP Configuration:
```json
{
  "mcpServers": {
    "marker": {
      "command": "uv",
      "args": ["run", "marker-mcp-serve"],
      "env": {
        "MARKER_CLAUDE_API_KEY": "${ANTHROPIC_API_KEY}",
        "MARKER_ARANGODB_URL": "http://localhost:8529"
      }
    }
  }
}
```

## Verification Requirements

1. **Command Registration**: All commands properly registered and discoverable
2. **Help System**: Comprehensive help for each command
3. **Error Handling**: Graceful error handling with clear messages
4. **Integration Tests**: Tests for each command category
5. **Documentation**: Updated docs with slash command reference
6. **MCP Compatibility**: Commands work through MCP server

## Success Criteria

- [ ] All planned slash commands implemented
- [ ] Commands accessible via `/marker-*` syntax
- [ ] Integration with Claude Desktop verified
- [ ] Comprehensive test coverage
- [ ] Documentation complete
- [ ] Performance benchmarks pass

## Notes

- Leverage existing marker functionality, don't duplicate
- Maintain consistency with sparta command patterns
- Focus on user-friendly command names and arguments
- Ensure all commands have proper validation
- Add progress indicators for long-running operations