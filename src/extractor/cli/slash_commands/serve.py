"""Serve slash command for marker MCP server.
Module: serve.py

Provides commands for starting and managing the marker MCP server.
"""

from pathlib import Path
from typing import Optional, List
import typer
from loguru import logger
import subprocess
import json
import time
import os

from .base import SlashCommand


class ServeCommand(SlashCommand):
    """MCP server management command."""
    
    def __init__(self):
        super().__init__(
            name="marker-serve",
            description="Start and manage the marker MCP server",
            category="server"
        )
    
    def _setup_commands(self):
        """Setup serve command handlers."""
        
        @self.app.command()
        def start(
            port: int = typer.Option(3000, help="Port to run server on"),
            host: str = typer.Option("localhost", help="Host to bind to"),
            debug: bool = typer.Option(False, help="Enable debug mode"),
            background: bool = typer.Option(False, help="Run in background"),
            config_file: Optional[str] = typer.Option(None, help="Path to config file")
        ):
            """Start the marker MCP server."""
            try:
                print(f" Starting marker MCP server on {host}:{port}...")
                
                # Build command
                cmd = ["uv", "run", "python", "-m", "marker.mcp_server"]
                
                # Add options
                env = os.environ.copy()
                env["MCP_SERVER_PORT"] = str(port)
                env["MCP_SERVER_HOST"] = host
                
                if debug:
                    env["MCP_DEBUG"] = "1"
                    env["LOGURU_LEVEL"] = "DEBUG"
                
                if config_file:
                    config_path = Path(config_file)
                    if not config_path.exists():
                        print(f" Config file not found: {config_file}")
                        raise typer.Exit(1)
                    env["MCP_CONFIG_FILE"] = str(config_path.absolute())
                
                if background:
                    # Run in background
                    pid_file = Path.home() / ".marker" / "mcp_server.pid"
                    pid_file.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Start process
                    process = subprocess.Popen(
                        cmd,
                        env=env,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        start_new_session=True
                    )
                    
                    # Save PID
                    with open(pid_file, 'w') as f:
                        f.write(str(process.pid))
                    
                    # Wait a bit to check if it started
                    time.sleep(2)
                    
                    if process.poll() is None:
                        print(f" Server started in background (PID: {process.pid})")
                        print(f"   Access at: http://{host}:{port}")
                        print(f"   Stop with: /marker-serve stop")
                    else:
                        print(" Server failed to start")
                        stderr = process.stderr.read().decode() if process.stderr else ""
                        if stderr:
                            print(f"Error: {stderr}")
                        raise typer.Exit(1)
                else:
                    # Run in foreground
                    print("\nServer output:")
                    print("-" * 50)
                    
                    try:
                        subprocess.run(cmd, env=env, check=True)
                    except KeyboardInterrupt:
                        print("\n\n Server stopped")
                    except subprocess.CalledProcessError as e:
                        print(f"\n Server error: {e}")
                        raise typer.Exit(1)
                
            except Exception as e:
                logger.error(f"Failed to start server: {e}")
                raise typer.Exit(1)
        
        @self.app.command()
        def stop(
            force: bool = typer.Option(False, help="Force stop")
        ):
            """Stop the marker MCP server."""
            try:
                pid_file = Path.home() / ".marker" / "mcp_server.pid"
                
                if not pid_file.exists():
                    print(" No server PID file found. Server may not be running.")
                    raise typer.Exit(1)
                
                with open(pid_file, 'r') as f:
                    pid = int(f.read().strip())
                
                print(f" Stopping server (PID: {pid})...")
                
                try:
                    import signal
                    os.kill(pid, signal.SIGTERM if not force else signal.SIGKILL)
                    
                    # Wait for process to stop
                    for _ in range(10):
                        try:
                            os.kill(pid, 0)  # Check if process exists
                            time.sleep(0.5)
                        except ProcessLookupError:
                            break
                    
                    # Clean up PID file
                    pid_file.unlink()
                    
                    print(" Server stopped")
                    
                except ProcessLookupError:
                    print("⚠️  Server process not found. Cleaning up PID file.")
                    pid_file.unlink()
                
            except Exception as e:
                logger.error(f"Failed to stop server: {e}")
                raise typer.Exit(1)
        
        @self.app.command()
        def status(
            check_health: bool = typer.Option(True, help="Check server health")
        ):
            """Check MCP server status."""
            try:
                pid_file = Path.home() / ".marker" / "mcp_server.pid"
                
                if not pid_file.exists():
                    print(" Server is not running (no PID file)")
                    raise typer.Exit(1)
                
                with open(pid_file, 'r') as f:
                    pid = int(f.read().strip())
                
                # Check if process is running
                try:
                    os.kill(pid, 0)
                    print(f" Server is running (PID: {pid})")
                    
                    if check_health:
                        # Try to connect to server
                        import requests
                        try:
                            # Read port from env or default
                            port = int(os.environ.get("MCP_SERVER_PORT", "3000"))
                            host = os.environ.get("MCP_SERVER_HOST", "localhost")
                            
                            response = requests.get(f"http://{host}:{port}/health", timeout=2)
                            if response.status_code == 200:
                                print(f" Server is healthy")
                                health_data = response.json()
                                print(f"   Version: {health_data.get('version', 'unknown')}")
                                print(f"   Uptime: {health_data.get('uptime', 'unknown')}")
                            else:
                                print(f"⚠️  Server returned status {response.status_code}")
                        except requests.exceptions.RequestException:
                            print("⚠️  Could not connect to server (may still be starting)")
                    
                except ProcessLookupError:
                    print(f" Server process {pid} not found")
                    print("   Cleaning up stale PID file")
                    pid_file.unlink()
                    raise typer.Exit(1)
                
            except Exception as e:
                logger.error(f"Failed to check status: {e}")
                raise typer.Exit(1)
        
        @self.app.command()
        def config(
            output_path: Optional[str] = typer.Option(None, help="Save config to file"),
            show: bool = typer.Option(False, help="Show current config")
        ):
            """Generate or show MCP configuration."""
            try:
                if show:
                    # Show current config
                    config_locations = [
                        Path.home() / ".config" / "Claude" / "claude_desktop_config.json",
                        Path.home() / ".marker" / "mcp_config.json",
                        Path("marker_mcp.json")
                    ]
                    
                    config_found = False
                    for config_path in config_locations:
                        if config_path.exists():
                            print(f"\n Config found at: {config_path}")
                            with open(config_path, 'r') as f:
                                config = json.load(f)
                            print(json.dumps(config, indent=2))
                            config_found = True
                    
                    if not config_found:
                        print(" No MCP configuration found")
                    
                else:
                    # Generate config
                    config = {
                        "mcpServers": {
                            "marker": {
                                "command": "uv",
                                "args": ["run", "python", "-m", "marker.mcp_server"],
                                "env": {
                                    "MARKER_CLAUDE_API_KEY": "${ANTHROPIC_API_KEY}",
                                    "MARKER_ARANGODB_URL": "http://localhost:8529",
                                    "MARKER_ARANGODB_USERNAME": "root",
                                    "MARKER_ARANGODB_DATABASE": "marker",
                                    "MCP_SERVER_PORT": "3000",
                                    "MCP_SERVER_HOST": "localhost"
                                }
                            }
                        }
                    }
                    
                    if output_path:
                        output_file = Path(output_path)
                        output_file.parent.mkdir(parents=True, exist_ok=True)
                        
                        with open(output_file, 'w') as f:
                            json.dump(config, f, indent=2)
                        
                        print(f" Configuration saved to: {output_file}")
                    else:
                        print(" MCP Configuration for Claude Desktop:\n")
                        print(json.dumps(config, indent=2))
                        
                        # Show where to save it
                        claude_config = Path.home() / ".config" / "Claude" / "claude_desktop_config.json"
                        print(f"\n Save this to: {claude_config}")
                        print("   Or use: /marker-serve config --output-path ~/.config/Claude/claude_desktop_config.json")
                
            except Exception as e:
                logger.error(f"Config operation failed: {e}")
                raise typer.Exit(1)
        
        @self.app.command()
        def tools(
            list_all: bool = typer.Option(False, help="List all available tools"),
            search: Optional[str] = typer.Option(None, help="Search for tools")
        ):
            """List available MCP tools."""
            try:
                # Define available tools
                tools = [
                    {
                        "name": "extract_pdf",
                        "description": "Extract content from PDF documents",
                        "parameters": ["pdf_path", "output_format", "max_pages"]
                    },
                    {
                        "name": "extract_tables",
                        "description": "Extract tables from PDF documents",
                        "parameters": ["pdf_path", "format", "page"]
                    },
                    {
                        "name": "extract_code",
                        "description": "Extract code blocks from documents",
                        "parameters": ["pdf_path", "language", "combine"]
                    },
                    {
                        "name": "analyze_with_claude",
                        "description": "Run Claude AI analysis on documents",
                        "parameters": ["json_path", "analysis_type"]
                    },
                    {
                        "name": "generate_qa",
                        "description": "Generate question-answer pairs",
                        "parameters": ["json_path", "num_questions", "qa_type"]
                    },
                    {
                        "name": "import_to_arangodb",
                        "description": "Import documents to ArangoDB",
                        "parameters": ["json_path", "database", "skip_existing"]
                    },
                    {
                        "name": "search_arangodb",
                        "description": "Search content in ArangoDB",
                        "parameters": ["query", "collection", "limit"]
                    },
                    {
                        "name": "run_workflow",
                        "description": "Execute document processing workflow",
                        "parameters": ["workflow_name", "input_path"]
                    }
                ]
                
                # Filter if search term provided
                if search:
                    tools = [t for t in tools if search.lower() in t['name'].lower() or search.lower() in t['description'].lower()]
                
                if not tools:
                    print("No tools found matching search criteria")
                    return
                
                print("️  Available MCP Tools:\n")
                
                for tool in tools:
                    print(f" {tool['name']}")
                    print(f"   {tool['description']}")
                    print(f"   Parameters: {', '.join(tool['parameters'])}")
                    print()
                
                if not list_all and len(tools) == 8:
                    print(" Use --list-all to see all available tools")
                
            except Exception as e:
                logger.error(f"Failed to list tools: {e}")
                raise typer.Exit(1)
    
    def get_examples(self) -> List[str]:
        """Get example usage."""
        return [
            "/marker-serve start --port 3000 --debug",
            "/marker-serve start --background",
            "/marker-serve stop",
            "/marker-serve status --check-health",
            "/marker-serve config --output-path ~/.config/Claude/claude_desktop_config.json",
            "/marker-serve tools --search extract",
        ]