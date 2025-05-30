"""Main CLI entry point for marker with slash command support.

This module integrates the traditional CLI commands with the new slash command system.
"""

import typer
from loguru import logger
import sys
from pathlib import Path
from typing import Optional

from marker.cli.agent_commands import app as agent_app
from marker.cli.slash_commands import registry as slash_registry


app = typer.Typer(
    name="marker",
    help="Marker PDF extraction tool with slash command support",
    add_completion=True
)

# Add existing commands as subcommand
app.add_typer(agent_app, name="agent", help="Agent-specific commands")


@app.command()
def slash(
    command: str = typer.Argument(..., help="Slash command to execute (e.g., 'marker-extract file.pdf')"),
    help_all: bool = typer.Option(False, "--help-all", help="Show help for all slash commands")
):
    """Execute a slash command."""
    try:
        if help_all:
            print(slash_registry.get_help())
            return
        
        # Parse command
        if not command.startswith('/'):
            # Allow without slash for convenience
            command = '/' + command
        
        # Execute command
        slash_registry.execute(command)
        
    except ValueError as e:
        logger.error(f"Command error: {e}")
        print(f"\n❌ {e}")
        print("\nUse --help-all to see available commands")
        raise typer.Exit(1)
    except Exception as e:
        logger.error(f"Execution failed: {e}")
        raise typer.Exit(1)


@app.command()
def extract(
    pdf_path: Path = typer.Argument(..., help="Path to PDF file"),
    output_format: str = typer.Option("markdown", "-f", "--format", help="Output format"),
    output_path: Optional[Path] = typer.Option(None, "-o", "--output", help="Output path"),
    max_pages: Optional[int] = typer.Option(None, "--max-pages", help="Maximum pages to process"),
    ocr_all_pages: bool = typer.Option(False, "--ocr-all", help="OCR all pages")
):
    """Extract content from a PDF (shorthand for slash command)."""
    # Build slash command
    cmd = f"/marker-extract {pdf_path}"
    
    if output_format != "markdown":
        cmd += f" --output-format {output_format}"
    if output_path:
        cmd += f" --output-path {output_path}"
    if max_pages:
        cmd += f" --max-pages {max_pages}"
    if ocr_all_pages:
        cmd += " --ocr-all-pages"
    
    # Execute via slash command
    try:
        slash_registry.execute(cmd)
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        raise typer.Exit(1)


@app.command()
def workflow(
    action: str = typer.Argument(..., help="Workflow action (list, create, run)"),
    args: Optional[str] = typer.Argument(None, help="Additional arguments")
):
    """Manage workflows (shorthand for slash commands)."""
    # Build slash command
    cmd = f"/marker-workflow {action}"
    if args:
        cmd += f" {args}"
    
    # Execute via slash command
    try:
        slash_registry.execute(cmd)
    except Exception as e:
        logger.error(f"Workflow command failed: {e}")
        raise typer.Exit(1)


@app.command()
def serve(
    action: str = typer.Option("start", help="Server action (start, stop, status)"),
    port: int = typer.Option(3000, "-p", "--port", help="Server port"),
    background: bool = typer.Option(False, "-b", "--background", help="Run in background")
):
    """Start MCP server (shorthand for slash command)."""
    # Build slash command
    cmd = f"/marker-serve {action}"
    
    if action == "start":
        cmd += f" --port {port}"
        if background:
            cmd += " --background"
    
    # Execute via slash command
    try:
        slash_registry.execute(cmd)
    except Exception as e:
        logger.error(f"Server command failed: {e}")
        raise typer.Exit(1)


@app.command()
def commands(
    category: Optional[str] = typer.Option(None, "-c", "--category", help="Filter by category"),
    format: str = typer.Option("text", "-f", "--format", help="Output format (text, json)")
):
    """List all available slash commands."""
    try:
        if category:
            commands = slash_registry.list_commands(category)
            if not commands:
                print(f"No commands found in category '{category}'")
                return
            
            print(f"\n📋 {category.title()} Commands:\n")
            for cmd in sorted(commands):
                command_obj = slash_registry.get_command(cmd)
                print(f"  /{cmd} - {command_obj.description}")
        else:
            # Show all commands by category
            print("\n🚀 Marker Slash Commands\n")
            
            for cat, cmds in sorted(slash_registry.categories.items()):
                print(f"📁 {cat.title()}:")
                for cmd in sorted(cmds):
                    command_obj = slash_registry.get_command(cmd)
                    print(f"  /{cmd} - {command_obj.description}")
                print()
        
        print("\n💡 Use '/marker-<command> --help' for detailed help on any command")
        print("   Or run 'marker slash <command>' to execute a slash command")
        
    except Exception as e:
        logger.error(f"Failed to list commands: {e}")
        raise typer.Exit(1)


@app.callback()
def callback(
    version: bool = typer.Option(None, "--version", "-v", help="Show version"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging")
):
    """Marker - PDF extraction tool with AI enhancements."""
    if version:
        from marker import __version__
        print(f"Marker version {__version__}")
        raise typer.Exit()
    
    if debug:
        logger.add(sys.stderr, level="DEBUG")


def main():
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()