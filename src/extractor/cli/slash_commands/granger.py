"""
Module: granger.py
Description: Granger ecosystem integration slash commands for marker

External Dependencies:
- typer: https://typer.tiangolo.com/
- loguru: https://loguru.readthedocs.io/

Sample Input:
>>> /granger-daily-verify --project marker

Expected Output:
>>>  Granger Daily Verification for: marker
>>>  Slash command integration: PASS (7 commands registered)
>>>  MCP integration: PASS (server configured)
>>>  Module communication: PASS (messages directory found)
>>>  Configuration: PASS (all required files present)
>>>  Dependencies: PASS (all required packages installed)

Example Usage:
>>> from extractor.cli.slash_commands import registry
>>> registry.execute("/granger-daily-verify --project marker")
"""

from pathlib import Path
from typing import Optional, List, Dict, Any
import typer
from loguru import logger
import json
import sys
from datetime import datetime

from .base import CommandGroup, format_output


class GrangerCommands(CommandGroup):
    """Granger ecosystem integration commands."""
    
    def __init__(self):
        super().__init__(
            name="granger",
            description="Granger ecosystem integration and verification",
            category="system"
        )
    
    def _setup_commands(self):
        """Setup Granger command handlers."""
        super()._setup_commands()
        
        @self.app.command()
        def daily_verify(
            project: str = typer.Option("marker", help="Project name to verify"),
            verbose: bool = typer.Option(False, help="Show detailed output"),
            output: Optional[str] = typer.Option(None, help="Save results to JSON file")
        ):
            """Run Granger daily verification for the project."""
            try:
                # Import the verification module
                sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / "scripts"))
                from granger_daily_verify import GrangerVerifier
                
                logger.info(f"Running Granger daily verification for: {project}")
                
                # Run verification
                verifier = GrangerVerifier(project)
                results = verifier.verify_all()
                
                # Display results
                print(f"\n Granger Daily Verification for: {project}")
                print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print("-" * 60)
                
                # Show check results
                for check_name, check_result in results["checks"].items():
                    status = check_result["status"]
                    message = check_result["message"]
                    
                    icon = {
                        "PASS": "",
                        "FAIL": "",
                        "PARTIAL": "⚠️ ",
                        "ERROR": ""
                    }.get(status, "")
                    
                    print(f"{icon} {check_name.replace('_', ' ').title()}: {status}")
                    print(f"   {message}")
                    
                    if verbose and "details" in check_result:
                        details = check_result["details"]
                        if isinstance(details, dict):
                            for key, value in details.items():
                                print(f"   - {key}: {value}")
                        else:
                            print(f"   Details: {details}")
                
                # Show warnings
                if results["warnings"]:
                    print(f"\n⚠️  Warnings ({len(results['warnings'])}):")
                    for warning in results["warnings"]:
                        print(f"   - {warning['message']}")
                        if "suggestion" in warning:
                            print(f"      {warning['suggestion']}")
                
                # Show errors
                if results["errors"]:
                    print(f"\n Errors ({len(results['errors'])}):")
                    for error in results["errors"]:
                        print(f"   - {error}")
                
                # Overall status
                print("\n" + "=" * 60)
                status_icon = {
                    "PASS": "",
                    "PASS_WITH_WARNINGS": "⚠️ ",
                    "PARTIAL": "⚠️ ",
                    "FAIL": "",
                    "ERROR": ""
                }.get(results["overall_status"], "")
                
                print(f"{status_icon} Overall Status: {results['overall_status']}")
                
                # Save to file if requested
                if output:
                    output_path = Path(output)
                    output_path.write_text(json.dumps(results, indent=2))
                    print(f"\n Results saved to: {output_path}")
                
                # Exit based on status
                if results["overall_status"] in ["FAIL", "ERROR"]:
                    raise typer.Exit(1)
                    
            except Exception as e:
                logger.error(f"Verification failed: {e}")
                print(f"\n Fatal error: {e}")
                raise typer.Exit(2)
        
        @self.app.command()
        def status(
            component: Optional[str] = typer.Option(None, help="Specific component to check")
        ):
            """Check status of Granger ecosystem components."""
            try:
                print("\n Granger Ecosystem Status\n")
                
                components = {
                    "marker": "Processing spoke for document extraction",
                    "arangodb": "Graph database for document storage",
                    "unsloth": "Fine-tuning pipeline (if available)",
                    "sparta": "Source code spoke (if available)"
                }
                
                if component:
                    if component in components:
                        print(f" {component}: {components[component]}")
                        # TODO: Add actual status checks
                        print(f"   Status: Active")
                    else:
                        print(f" Unknown component: {component}")
                else:
                    for comp, desc in components.items():
                        print(f" {comp}: {desc}")
                        # TODO: Add actual status checks
                        print(f"   Status: {'Active' if comp == 'marker' else 'Unknown'}")
                
                print("\n Use /granger-daily-verify for detailed verification")
                
            except Exception as e:
                logger.error(f"Status check failed: {e}")
                raise typer.Exit(1)
        
        @self.app.command()
        def sync(
            direction: str = typer.Argument(..., help="Sync direction: to-arangodb or from-arangodb"),
            dry_run: bool = typer.Option(False, help="Show what would be synced without doing it")
        ):
            """Sync data between Marker and other Granger components."""
            try:
                if direction not in ["to-arangodb", "from-arangodb"]:
                    print(" Invalid direction. Use 'to-arangodb' or 'from-arangodb'")
                    raise typer.Exit(1)
                
                print(f"\n Syncing {direction}")
                
                if dry_run:
                    print("   (DRY RUN - no changes will be made)")
                
                # Check messages directory
                messages_dir = Path(__file__).parent.parent.parent.parent / "messages"
                if not messages_dir.exists():
                    print(" Messages directory not found")
                    raise typer.Exit(1)
                
                # Count messages
                if direction == "to-arangodb":
                    msg_dir = messages_dir / "to_arangodb"
                else:
                    msg_dir = messages_dir / "from_arangodb"
                
                if msg_dir.exists():
                    messages = list(msg_dir.glob("*.json"))
                    print(f"   Found {len(messages)} messages to process")
                    
                    if not dry_run and messages:
                        # TODO: Implement actual sync logic
                        print("   ⚠️  Sync functionality not yet implemented")
                else:
                    print(f"   No messages found in {msg_dir}")
                
            except Exception as e:
                logger.error(f"Sync failed: {e}")
                raise typer.Exit(1)
    
    def get_examples(self) -> List[str]:
        """Get example usage."""
        return [
            "/granger-daily-verify --project marker",
            "/granger-daily-verify --verbose --output results.json",
            "/granger-status",
            "/granger-status --component arangodb",
            "/granger-sync to-arangodb --dry-run",
        ]


# Module validation
if __name__ == "__main__":
    # Test command group
    commands = GrangerCommands()
    
    print(" Granger commands module loaded successfully")
    print(f" Commands: {', '.join(commands.list_commands())}")
    print("\nExamples:")
    for example in commands.get_examples():
        print(f"  {example}")